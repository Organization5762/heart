use std::fs::{File, OpenOptions};
use std::os::fd::{AsRawFd, RawFd};
use std::os::unix::fs::OpenOptionsExt;
use std::sync::atomic::{fence, Ordering};
use std::time::Duration;

use super::backend::MatrixBackend;
use super::config::{MatrixConfigNative, WiringProfile};
use super::frame::FrameBuffer;
use super::tuning::runtime_tuning;

const RP1H_DEVICE_PATH: &str = "/dev/rp1-hub75";
const RP1H_MAPPING_ADAFRUIT_HAT_PWM: u8 = 0;
const RP1H_MAPPING_ELECTRODRAGON_P0: u8 = 1;
const RP1H_MAPPING_REGULAR: u8 = 2;
const RP1H_FORMAT_RGB888: u8 = 0;
#[allow(dead_code)]
const RP1H_STREAM_RIO32: u32 = 0;
#[allow(dead_code)]
const RP1H_STREAM_RGB6_PACKED: u32 = 1;
#[allow(dead_code)]
const RP1H_STREAM_RGB6_BYTE: u32 = 2;
const RP1H_STREAM_STATE32: u32 = 3;
const RP1H_F_E_LINE_PRESENT: u32 = 1 << 0;
#[allow(dead_code)]
const RP1H_QUEUE_F_NONBLOCK: u32 = 1 << 0;
const RP1H_QUEUE_F_REPLACE_PENDING: u32 = 1 << 1;
const RP1H_WORKER_F_EXTERNAL_VSYNC: u32 = 1 << 0;
const RP1H_SLOT_COUNT: u32 = 2;
const RP1H_CONFIG: libc::c_ulong = iowr::<Rp1hConfig>(b'H', 0x40);
#[allow(dead_code)]
const RP1H_PACK_FRAME: libc::c_ulong = iow::<Rp1hPackFrame>(b'H', 0x41);
const RP1H_GET_STATS: libc::c_ulong = ior::<Rp1hStats>(b'H', 0x42);
const RP1H_QUEUE_FRAME: libc::c_ulong = iowr::<Rp1hQueueFrame>(b'H', 0x43);
const RP1H_WAIT_PRESENT: libc::c_ulong = iowr::<Rp1hWaitPresent>(b'H', 0x44);
const RP1H_SIGNAL_VSYNC: libc::c_ulong = iowr::<Rp1hVsync>(b'H', 0x45);
const RP1H_GET_PRESENT_STATS: libc::c_ulong = ior::<Rp1hPresentStats>(b'H', 0x46);
const RP1H_START_WORKER: libc::c_ulong = iow::<Rp1hWorkerControl>(b'H', 0x47);
const RP1H_STOP_WORKER: libc::c_ulong = iow::<Rp1hWorkerControl>(b'H', 0x48);
const RP1H_GET_WORKER_STATUS: libc::c_ulong = ior::<Rp1hWorkerStatus>(b'H', 0x49);
const RP1_SRAM_HOST_BASE: libc::off_t = 0x1f00400000;
const RP1_SRAM_MAP_SIZE: usize = 0x10000;
const EXTERNAL_SRAM_SLOT_OFFSET_ENV: &str = "HEART_RP1_HUB75_EXTERNAL_SRAM_SLOT_OFFSET";

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
struct Rp1hConfig {
    size: u32,
    cols: u16,
    rows: u16,
    pwm_bits: u8,
    mapping: u8,
    format: u8,
    reserved0: u8,
    flags: u32,
    frame_bytes: u32,
    mmap_size: u32,
    words_offset: u32,
    words_per_frame: u32,
    stream_format: u32,
    bits_per_pixel: u32,
    panel_count: u32,
    words_per_row_plane: u32,
    bytes_per_row_plane: u32,
    words_per_row_plane_aligned: u32,
    bytes_per_row_plane_aligned: u32,
    lane_count: u32,
    chain_length: u32,
    addr_line_count: u32,
    slot_count: u32,
    slot_stride_bytes: u32,
    reserved1: u32,
    dwell_shift_limit: u32,
}

#[derive(Debug)]
pub(crate) struct Rp1Hub75Backend {
    device: File,
    config: Rp1hConfig,
    mapping: MmapMapping,
    external_sram_slot: Option<SramSlotPublisher>,
    frame_loader: Rp1Hub75FrameLoader,
    worker_started: bool,
    wait_timeout_ns: Option<i64>,
    signal_vsync_after_queue: bool,
    require_progress_after_queued_frames: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug)]
struct Rp1hPackFrame {
    size: u32,
    length: u32,
    data: u64,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Rp1Hub75Stats {
    pub frames_packed: u32,
    pub bytes_packed: u64,
    pub last_error: u32,
    pub words_per_frame: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
struct Rp1hStats {
    size: u32,
    frames_packed: u32,
    bytes_packed: u64,
    last_error: u32,
    words_per_frame: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug)]
struct Rp1hQueueFrame {
    size: u32,
    length: u32,
    flags: u32,
    slot_index: u32,
    data: u64,
    seq: u32,
    reserved0: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug)]
struct Rp1hWaitPresent {
    size: u32,
    seq: u32,
    timeout_ns: i64,
    presented_seq: u32,
    reserved0: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug)]
struct Rp1hVsync {
    size: u32,
    flags: u32,
    presented_seq: u32,
    displayed_slot: u32,
    reserved0: [u32; 2],
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
struct Rp1hPresentStats {
    size: u32,
    frames_queued: u32,
    frames_presented: u32,
    frames_dropped: u32,
    vsync_count: u32,
    queued_seq: u32,
    presented_seq: u32,
    displayed_slot: u32,
    pending_slot: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug)]
struct Rp1hWorkerControl {
    size: u32,
    flags: u32,
    status_timeout_ms: u32,
    reserved0: [u32; 5],
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
struct Rp1hWorkerStatus {
    size: u32,
    state: u32,
    flags: u32,
    status_timeout_ms: u32,
    worker_seq: u32,
    vsync_count: u32,
    queued_seq: u32,
    presented_seq: u32,
    displayed_slot: u32,
    pending_slot: u32,
    frames_queued: u32,
    frames_presented: u32,
    frames_dropped: u32,
    last_error: u32,
    last_vsync_ns: u64,
    reserved0: [u32; 4],
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
struct Rp1hMmapHeader {
    magic: u32,
    version: u16,
    header_size: u16,
    cols: u16,
    rows: u16,
    pwm_bits: u8,
    mapping: u8,
    format: u8,
    reserved0: u8,
    flags: u32,
    frame_seq: u32,
    words_offset: u32,
    words_per_frame: u32,
    pins: [u32; 14],
    dwell: [u32; 11],
    stream_format: u32,
    bits_per_pixel: u32,
    row_pairs: u32,
    plane_count: u32,
    panel_count: u32,
    words_per_row_plane: u32,
    bytes_per_row_plane: u32,
    words_per_row_plane_aligned: u32,
    bytes_per_row_plane_aligned: u32,
    lane_count: u32,
    chain_length: u32,
    addr_line_count: u32,
    slot_count: u32,
    slot_stride_bytes: u32,
    producer_head: u32,
    consumer_tail: u32,
    buffer_dma_addr_lo: u32,
    buffer_dma_addr_hi: u32,
    slot_dma_addr_lo: [u32; 2],
    slot_dma_addr_hi: [u32; 2],
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Rp1Hub75PresentStats {
    pub frames_queued: u32,
    pub frames_presented: u32,
    pub frames_dropped: u32,
    pub vsync_count: u32,
    pub queued_seq: u32,
    pub presented_seq: u32,
    pub displayed_slot: u32,
    pub pending_slot: u32,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Rp1Hub75WorkerStatus {
    pub state: u32,
    pub flags: u32,
    pub status_timeout_ms: u32,
    pub worker_seq: u32,
    pub vsync_count: u32,
    pub queued_seq: u32,
    pub presented_seq: u32,
    pub displayed_slot: u32,
    pub pending_slot: u32,
    pub frames_queued: u32,
    pub frames_presented: u32,
    pub frames_dropped: u32,
    pub last_error: u32,
    pub last_vsync_ns: u64,
}

#[derive(Debug)]
struct MmapMapping {
    addr: usize,
    len: usize,
}

#[derive(Debug)]
struct SramSlotPublisher {
    _device: File,
    mapping: MmapMapping,
    offset: usize,
    dwell_shift_limit: u32,
}

#[derive(Debug)]
enum Rp1Hub75FrameLoader {
    Direct { frame_bytes: u32 },
}

impl Rp1Hub75Backend {
    pub(crate) fn new(config: &MatrixConfigNative) -> Result<Self, String> {
        let mapping = rp1h_mapping_for_wiring(config.wiring);
        let external_sram_slot_offset = parse_optional_usize(EXTERNAL_SRAM_SLOT_OFFSET_ENV)?;
        if config.chain_length != 1
            && external_sram_slot_offset.is_none()
            && config.wiring != WiringProfile::ThreePortActive
        {
            return Err(
                "RP1 HUB75 packer currently requires chain_length=1; use parallel panels instead."
                    .to_string(),
            );
        }

        let frame_loader = Rp1Hub75FrameLoader::for_config(config, external_sram_slot_offset)?;
        let frame_bytes = frame_loader.queue_frame_bytes();
        let pwm_bits = runtime_tuning().rp1_hub75_pwm_bits.min(11).max(1);
        let dwell_shift_limit = runtime_tuning().rp1_hub75_dwell_shift_limit;

        let (cols, rows, panel_count, lane_count, chain_length) = if external_sram_slot_offset
            .is_some()
            && config.wiring != WiringProfile::ThreePortActive
        {
            (
                u16::try_from(config.width()?)
                    .map_err(|_| "RP1 HUB75 external SRAM width exceeds u16.".to_string())?,
                u16::try_from(config.height()?)
                    .map_err(|_| "RP1 HUB75 external SRAM height exceeds u16.".to_string())?,
                1,
                1,
                1,
            )
        } else {
            rp1h_geometry_for_config(config)?
        };

        let mut rp1_config = Rp1hConfig {
            size: std::mem::size_of::<Rp1hConfig>() as u32,
            cols,
            rows,
            pwm_bits,
            mapping,
            format: RP1H_FORMAT_RGB888,
            flags: if rows >= 64 { RP1H_F_E_LINE_PRESENT } else { 0 },
            stream_format: RP1H_STREAM_STATE32,
            panel_count,
            lane_count,
            chain_length,
            slot_count: RP1H_SLOT_COUNT,
            dwell_shift_limit,
            ..Rp1hConfig::default()
        };

        let device = OpenOptions::new()
            .read(true)
            .write(true)
            .custom_flags(libc::O_CLOEXEC)
            .open(RP1H_DEVICE_PATH)
            .map_err(|error| format!("open {RP1H_DEVICE_PATH}: {error}"))?;

        xioctl(
            device.as_raw_fd(),
            RP1H_CONFIG,
            &mut rp1_config,
            "RP1H_CONFIG",
        )?;
        if rp1_config.frame_bytes != frame_bytes {
            return Err(format!(
                "RP1 HUB75 configured frame_bytes={} but runtime prepared {frame_bytes} bytes.",
                rp1_config.frame_bytes
            ));
        }
        if rp1_config.slot_count != RP1H_SLOT_COUNT {
            return Err(format!(
                "RP1 HUB75 configured slot_count={} but runtime requested {RP1H_SLOT_COUNT}.",
                rp1_config.slot_count
            ));
        }

        let mapping = MmapMapping::new(
            device.as_raw_fd(),
            usize::try_from(rp1_config.mmap_size)
                .map_err(|_| "RP1 HUB75 mmap size exceeds host usize.".to_string())?,
            libc::PROT_READ,
            0,
            RP1H_DEVICE_PATH,
        )?;
        let external_sram_slot = external_sram_slot_offset
            .map(|offset| SramSlotPublisher::new(offset, rp1_config.dwell_shift_limit))
            .transpose()?;
        let wait_timeout_ns = std::env::var("HEART_RP1_HUB75_WAIT_PRESENT_TIMEOUT_NS")
            .ok()
            .and_then(|value| value.parse::<i64>().ok());
        let signal_vsync_after_queue = std::env::var("HEART_RP1_HUB75_SIGNAL_VSYNC_AFTER_QUEUE")
            .map(|value| value != "0")
            .unwrap_or(false);
        let worker_status_timeout_ms = std::env::var("HEART_RP1_HUB75_WORKER_STATUS_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u32>().ok())
            .unwrap_or(0);
        let require_progress_after_queued_frames =
            runtime_tuning().rp1_hub75_require_progress_after_queued_frames;
        let worker_started = external_sram_slot.is_none();
        if worker_started {
            start_worker(device.as_raw_fd(), worker_status_timeout_ms)?;
        }

        Ok(Self {
            device,
            config: rp1_config,
            mapping,
            external_sram_slot,
            frame_loader,
            worker_started,
            wait_timeout_ns,
            signal_vsync_after_queue,
            require_progress_after_queued_frames,
        })
    }
}

pub fn read_pack_stats() -> Result<Rp1Hub75Stats, String> {
    read_pack_stats_from(RP1H_DEVICE_PATH)
}

pub fn read_pack_stats_from(device_path: &str) -> Result<Rp1Hub75Stats, String> {
    let device = OpenOptions::new()
        .read(true)
        .write(true)
        .custom_flags(libc::O_CLOEXEC)
        .open(device_path)
        .map_err(|error| format!("open {device_path}: {error}"))?;
    let mut stats = Rp1hStats {
        size: std::mem::size_of::<Rp1hStats>() as u32,
        ..Rp1hStats::default()
    };
    xioctl(
        device.as_raw_fd(),
        RP1H_GET_STATS,
        &mut stats,
        "RP1H_GET_STATS",
    )?;
    Ok(Rp1Hub75Stats {
        frames_packed: stats.frames_packed,
        bytes_packed: stats.bytes_packed,
        last_error: stats.last_error,
        words_per_frame: stats.words_per_frame,
    })
}

pub fn read_present_stats() -> Result<Rp1Hub75PresentStats, String> {
    read_present_stats_from(RP1H_DEVICE_PATH)
}

pub fn read_present_stats_from(device_path: &str) -> Result<Rp1Hub75PresentStats, String> {
    let device = OpenOptions::new()
        .read(true)
        .write(true)
        .custom_flags(libc::O_CLOEXEC)
        .open(device_path)
        .map_err(|error| format!("open {device_path}: {error}"))?;
    let mut stats = Rp1hPresentStats {
        size: std::mem::size_of::<Rp1hPresentStats>() as u32,
        ..Rp1hPresentStats::default()
    };
    xioctl(
        device.as_raw_fd(),
        RP1H_GET_PRESENT_STATS,
        &mut stats,
        "RP1H_GET_PRESENT_STATS",
    )?;
    Ok(Rp1Hub75PresentStats {
        frames_queued: stats.frames_queued,
        frames_presented: stats.frames_presented,
        frames_dropped: stats.frames_dropped,
        vsync_count: stats.vsync_count,
        queued_seq: stats.queued_seq,
        presented_seq: stats.presented_seq,
        displayed_slot: stats.displayed_slot,
        pending_slot: stats.pending_slot,
    })
}

pub fn read_worker_status() -> Result<Rp1Hub75WorkerStatus, String> {
    read_worker_status_from(RP1H_DEVICE_PATH)
}

pub fn read_worker_status_from(device_path: &str) -> Result<Rp1Hub75WorkerStatus, String> {
    let device = OpenOptions::new()
        .read(true)
        .write(true)
        .custom_flags(libc::O_CLOEXEC)
        .open(device_path)
        .map_err(|error| format!("open {device_path}: {error}"))?;
    read_worker_status_fd(device.as_raw_fd())
}

impl MatrixBackend for Rp1Hub75Backend {
    fn refresh_interval(&self) -> Duration {
        Duration::ZERO
    }

    fn owns_refresh_loop(&self) -> bool {
        true
    }

    fn render(&mut self, frame: &FrameBuffer) -> Result<(), String> {
        let (frame_data, frame_len) = self.frame_loader.prepare(frame.as_slice())?;
        let mut request = Rp1hQueueFrame {
            size: std::mem::size_of::<Rp1hQueueFrame>() as u32,
            length: u32::try_from(frame_len)
                .map_err(|_| "RP1 HUB75 frame length exceeds 32-bit UAPI length.".to_string())?,
            flags: RP1H_QUEUE_F_REPLACE_PENDING,
            slot_index: 0,
            data: frame_data as u64,
            seq: 0,
            reserved0: 0,
        };
        if request.length != self.config.frame_bytes {
            return Err(format!(
                "RP1 HUB75 expected {} RGB888 bytes but received {}.",
                self.config.frame_bytes, request.length
            ));
        }
        xioctl(
            self.device.as_raw_fd(),
            RP1H_QUEUE_FRAME,
            &mut request,
            "RP1H_QUEUE_FRAME",
        )?;
        if let Some(external_sram_slot) = &self.external_sram_slot {
            let slot_dma = self.slot_dma_addr(request.slot_index)?;
            external_sram_slot.publish(slot_dma)?;
        }
        if self.signal_vsync_after_queue {
            let _ = self.signal_vsync()?;
        }
        if self.external_sram_slot.is_none() {
            self.require_worker_progress()?;
        }
        if let Some(timeout_ns) = self.wait_timeout_ns {
            self.wait_present(request.seq, timeout_ns)?;
        }
        if std::env::var_os("HEART_RP1_HUB75_LOG_STATS").is_some() {
            let stats = self.read_present_stats()?;
            eprintln!(
                "[heart_rgb_matrix_driver::rp1_hub75] queued={} presented={} dropped={} vsync={} queued_seq={} presented_seq={} displayed_slot={} pending_slot={}",
                stats.frames_queued,
                stats.frames_presented,
                stats.frames_dropped,
                stats.vsync_count,
                stats.queued_seq,
                stats.presented_seq,
                stats.displayed_slot,
                stats.pending_slot
            );
        }
        Ok(())
    }
}

impl Rp1Hub75Backend {
    #[allow(dead_code)]
    fn signal_vsync(&self) -> Result<Rp1hVsync, String> {
        let mut vsync = Rp1hVsync {
            size: std::mem::size_of::<Rp1hVsync>() as u32,
            flags: 0,
            presented_seq: 0,
            displayed_slot: 0,
            reserved0: [0; 2],
        };
        xioctl(
            self.device.as_raw_fd(),
            RP1H_SIGNAL_VSYNC,
            &mut vsync,
            "RP1H_SIGNAL_VSYNC",
        )?;
        Ok(vsync)
    }

    fn wait_present(&self, seq: u32, timeout_ns: i64) -> Result<(), String> {
        let mut wait = Rp1hWaitPresent {
            size: std::mem::size_of::<Rp1hWaitPresent>() as u32,
            seq,
            timeout_ns,
            presented_seq: 0,
            reserved0: 0,
        };
        xioctl(
            self.device.as_raw_fd(),
            RP1H_WAIT_PRESENT,
            &mut wait,
            "RP1H_WAIT_PRESENT",
        )?;
        Ok(())
    }

    fn read_present_stats(&self) -> Result<Rp1hPresentStats, String> {
        let mut stats = Rp1hPresentStats {
            size: std::mem::size_of::<Rp1hPresentStats>() as u32,
            ..Rp1hPresentStats::default()
        };
        xioctl(
            self.device.as_raw_fd(),
            RP1H_GET_PRESENT_STATS,
            &mut stats,
            "RP1H_GET_PRESENT_STATS",
        )?;
        Ok(stats)
    }

    fn slot_dma_addr(&self, slot_index: u32) -> Result<u64, String> {
        let header = self.mapping.header()?;
        if slot_index >= header.slot_count || slot_index as usize >= header.slot_dma_addr_lo.len() {
            return Err(format!(
                "RP1 HUB75 queued slot {slot_index} outside slot_count {}.",
                header.slot_count
            ));
        }
        let index = slot_index as usize;
        let slot_dma = u64::from(header.slot_dma_addr_lo[index])
            | (u64::from(header.slot_dma_addr_hi[index]) << 32);
        if slot_dma == 0 {
            return Err(format!(
                "RP1 HUB75 queued slot {slot_index} has no DMA address; update/reload rp1-hub75.ko before external SRAM scanner use."
            ));
        }
        Ok(slot_dma)
    }

    fn require_worker_progress(&self) -> Result<(), String> {
        let threshold = self.require_progress_after_queued_frames;
        if self.signal_vsync_after_queue || threshold == 0 {
            return Ok(());
        }

        let status = read_worker_status_fd(self.device.as_raw_fd())?;
        if worker_progress_missing(&status, threshold) {
            return Err(format!(
                "RP1 HUB75 queued {} frames without any presented-frame or vsync progress. \
This backend only packs into /dev/rp1-hub75; start a real RP1 display worker or set \
HEART_RP1_HUB75_SIGNAL_VSYNC_AFTER_QUEUE=1 only for explicit software-vsync bring-up.",
                status.frames_queued
            ));
        }
        Ok(())
    }

    fn stop_worker(&self) -> Result<(), String> {
        let mut control = Rp1hWorkerControl {
            size: std::mem::size_of::<Rp1hWorkerControl>() as u32,
            flags: 0,
            status_timeout_ms: 0,
            reserved0: [0; 5],
        };
        xioctl(
            self.device.as_raw_fd(),
            RP1H_STOP_WORKER,
            &mut control,
            "RP1H_STOP_WORKER",
        )?;
        Ok(())
    }
}

impl Drop for Rp1Hub75Backend {
    fn drop(&mut self) {
        if self.worker_started {
            let _ = self.stop_worker();
        }
    }
}

fn start_worker(fd: RawFd, status_timeout_ms: u32) -> Result<(), String> {
    let mut control = Rp1hWorkerControl {
        size: std::mem::size_of::<Rp1hWorkerControl>() as u32,
        flags: RP1H_WORKER_F_EXTERNAL_VSYNC,
        status_timeout_ms,
        reserved0: [0; 5],
    };
    xioctl(fd, RP1H_START_WORKER, &mut control, "RP1H_START_WORKER")?;
    Ok(())
}

fn read_worker_status_fd(fd: RawFd) -> Result<Rp1Hub75WorkerStatus, String> {
    let mut status = Rp1hWorkerStatus {
        size: std::mem::size_of::<Rp1hWorkerStatus>() as u32,
        ..Rp1hWorkerStatus::default()
    };
    xioctl(
        fd,
        RP1H_GET_WORKER_STATUS,
        &mut status,
        "RP1H_GET_WORKER_STATUS",
    )?;
    Ok(Rp1Hub75WorkerStatus {
        state: status.state,
        flags: status.flags,
        status_timeout_ms: status.status_timeout_ms,
        worker_seq: status.worker_seq,
        vsync_count: status.vsync_count,
        queued_seq: status.queued_seq,
        presented_seq: status.presented_seq,
        displayed_slot: status.displayed_slot,
        pending_slot: status.pending_slot,
        frames_queued: status.frames_queued,
        frames_presented: status.frames_presented,
        frames_dropped: status.frames_dropped,
        last_error: status.last_error,
        last_vsync_ns: status.last_vsync_ns,
    })
}

fn worker_progress_missing(status: &Rp1Hub75WorkerStatus, threshold: u32) -> bool {
    status.frames_queued >= threshold && status.frames_presented == 0 && status.vsync_count == 0
}

fn rp1h_mapping_for_wiring(wiring: WiringProfile) -> u8 {
    match wiring {
        WiringProfile::AdafruitHatPwm => RP1H_MAPPING_ADAFRUIT_HAT_PWM,
        WiringProfile::ElectroDragonP0 => RP1H_MAPPING_ELECTRODRAGON_P0,
        WiringProfile::ThreePortActive => RP1H_MAPPING_REGULAR,
    }
}

fn rp1h_geometry_for_config(
    config: &MatrixConfigNative,
) -> Result<(u16, u16, u32, u32, u32), String> {
    if config.wiring == WiringProfile::ThreePortActive {
        if config.chain_length != 4 || config.parallel != 1 {
            return Err(
                "RP1 HUB75 three-port active profile expects a horizontal 4-panel RGB888 strip: chain_length=4 parallel=1.".to_string(),
            );
        }
        return Ok((config.panel_cols, config.panel_rows, 4, 2, 2));
    }

    let panel_count = config.panel_count()?;
    Ok((
        config.panel_cols,
        config.panel_rows,
        panel_count,
        panel_count,
        1,
    ))
}

impl Rp1Hub75FrameLoader {
    fn for_config(
        config: &MatrixConfigNative,
        _external_sram_slot_offset: Option<usize>,
    ) -> Result<Self, String> {
        let input_frame_bytes = config.frame_len()?;
        if config.wiring != WiringProfile::ThreePortActive {
            let frame_bytes = u32::try_from(input_frame_bytes)
                .map_err(|_| "RP1 HUB75 frame size exceeds 32-bit UAPI length.".to_string())?;
            return Ok(Self::Direct { frame_bytes });
        }
        let input_width = usize::try_from(config.width()?).map_err(|_| {
            "RP1 HUB75 three-port active input width exceeds host usize.".to_string()
        })?;
        let input_height = usize::try_from(config.height()?).map_err(|_| {
            "RP1 HUB75 three-port active input height exceeds host usize.".to_string()
        })?;
        let output_width = usize::from(config.panel_cols) * 2;
        if config.chain_length == 4 && config.parallel == 1 {
            let expected_width = output_width * 2;
            if input_width != expected_width || input_height != usize::from(config.panel_rows) {
                return Err(format!(
                    "RP1 HUB75 three-port active horizontal loader expected {}x{} input, received {input_width}x{input_height}.",
                    expected_width,
                    config.panel_rows
                ));
            }
            return Ok(Self::Direct {
                frame_bytes: u32::try_from(input_frame_bytes).map_err(|_| {
                    "RP1 HUB75 three-port active horizontal frame size exceeds 32-bit UAPI length."
                        .to_string()
                })?,
            });
        }
        Err(
            "RP1 HUB75 three-port active profile expects a horizontal 4-panel RGB888 strip: chain_length=4 parallel=1."
                .to_string(),
        )
    }

    fn queue_frame_bytes(&self) -> u32 {
        match self {
            Self::Direct { frame_bytes } => *frame_bytes,
        }
    }

    fn prepare(&mut self, frame: &[u8]) -> Result<(*const u8, usize), String> {
        match self {
            Self::Direct { frame_bytes } => {
                let expected = usize::try_from(*frame_bytes)
                    .map_err(|_| "RP1 HUB75 direct frame size exceeds host usize.".to_string())?;
                if frame.len() != expected {
                    return Err(format!(
                        "RP1 HUB75 expected {expected} RGB888 bytes but received {}.",
                        frame.len()
                    ));
                }
                Ok((frame.as_ptr(), frame.len()))
            }
        }
    }
}

impl MmapMapping {
    fn new(
        fd: RawFd,
        len: usize,
        prot: i32,
        offset: libc::off_t,
        label: &str,
    ) -> Result<Self, String> {
        let addr = unsafe {
            libc::mmap(
                std::ptr::null_mut(),
                len,
                prot,
                libc::MAP_SHARED,
                fd,
                offset,
            )
        };
        if addr == libc::MAP_FAILED {
            return Err(format!("mmap {label}: {}", std::io::Error::last_os_error()));
        }
        Ok(Self {
            addr: addr as usize,
            len,
        })
    }

    fn header(&self) -> Result<Rp1hMmapHeader, String> {
        if self.len < std::mem::size_of::<Rp1hMmapHeader>() {
            return Err(format!(
                "RP1 HUB75 mmap is too small for header: len={} header={}.",
                self.len,
                std::mem::size_of::<Rp1hMmapHeader>()
            ));
        }
        Ok(unsafe { std::ptr::read_volatile(self.addr as *const Rp1hMmapHeader) })
    }

    fn write32(&self, offset: usize, value: u32) -> Result<(), String> {
        if offset
            .checked_add(std::mem::size_of::<u32>())
            .filter(|end| *end <= self.len)
            .is_none()
        {
            return Err(format!(
                "RP1 SRAM write offset 0x{offset:x} exceeds mapped size 0x{:x}.",
                self.len
            ));
        }
        unsafe {
            std::ptr::write_volatile((self.addr as *mut u8).add(offset).cast::<u32>(), value);
        }
        Ok(())
    }
}

impl Drop for MmapMapping {
    fn drop(&mut self) {
        if self.addr != 0 && self.len != 0 {
            let _ = unsafe { libc::munmap(self.addr as *mut libc::c_void, self.len) };
        }
    }
}

const fn ioc<T>(dir: libc::c_ulong, ioctl_type: u8, nr: u8) -> libc::c_ulong {
    const IOC_NRBITS: libc::c_ulong = 8;
    const IOC_TYPEBITS: libc::c_ulong = 8;
    const IOC_SIZEBITS: libc::c_ulong = 14;
    const IOC_NRSHIFT: libc::c_ulong = 0;
    const IOC_TYPESHIFT: libc::c_ulong = IOC_NRSHIFT + IOC_NRBITS;
    const IOC_SIZESHIFT: libc::c_ulong = IOC_TYPESHIFT + IOC_TYPEBITS;
    const IOC_DIRSHIFT: libc::c_ulong = IOC_SIZESHIFT + IOC_SIZEBITS;

    (dir << IOC_DIRSHIFT)
        | ((ioctl_type as libc::c_ulong) << IOC_TYPESHIFT)
        | ((nr as libc::c_ulong) << IOC_NRSHIFT)
        | ((std::mem::size_of::<T>() as libc::c_ulong) << IOC_SIZESHIFT)
}

const fn ior<T>(ioctl_type: u8, nr: u8) -> libc::c_ulong {
    ioc::<T>(2, ioctl_type, nr)
}

const fn iow<T>(ioctl_type: u8, nr: u8) -> libc::c_ulong {
    ioc::<T>(1, ioctl_type, nr)
}

const fn iowr<T>(ioctl_type: u8, nr: u8) -> libc::c_ulong {
    ioc::<T>(3, ioctl_type, nr)
}

fn xioctl<T>(fd: RawFd, request: libc::c_ulong, arg: &mut T, label: &str) -> Result<i32, String> {
    let ret = unsafe { libc::ioctl(fd, request, arg as *mut T) };
    if ret < 0 {
        return Err(format!("{label}: {}", std::io::Error::last_os_error()));
    }
    Ok(ret)
}

impl SramSlotPublisher {
    fn new(offset: usize, dwell_shift_limit: u32) -> Result<Self, String> {
        if offset
            .checked_add(16)
            .filter(|end| *end <= RP1_SRAM_MAP_SIZE)
            .is_none()
        {
            return Err(format!(
                "{EXTERNAL_SRAM_SLOT_OFFSET_ENV}=0x{offset:x} leaves no room for the 16-byte slot control block."
            ));
        }
        let device = OpenOptions::new()
            .read(true)
            .write(true)
            .custom_flags(libc::O_CLOEXEC | libc::O_SYNC)
            .open("/dev/mem")
            .map_err(|error| format!("open /dev/mem for RP1 HUB75 external SRAM slot: {error}"))?;
        let mapping = MmapMapping::new(
            device.as_raw_fd(),
            RP1_SRAM_MAP_SIZE,
            libc::PROT_READ | libc::PROT_WRITE,
            RP1_SRAM_HOST_BASE,
            "RP1 SRAM host window",
        )?;
        Ok(Self {
            _device: device,
            mapping,
            offset,
            dwell_shift_limit,
        })
    }

    fn publish(&self, slot_dma: u64) -> Result<(), String> {
        self.mapping.write32(self.offset, slot_dma as u32)?;
        self.mapping
            .write32(self.offset + 4, (slot_dma >> 32) as u32)?;
        self.mapping.write32(self.offset + 8, 0)?;
        self.mapping
            .write32(self.offset + 12, self.dwell_shift_limit)?;
        fence(Ordering::SeqCst);
        Ok(())
    }
}

fn parse_optional_usize(key: &str) -> Result<Option<usize>, String> {
    let Some(raw) = std::env::var_os(key) else {
        return Ok(None);
    };
    let value = raw
        .to_str()
        .ok_or_else(|| format!("{key} must be valid UTF-8."))?
        .trim();
    if value.is_empty() {
        return Ok(None);
    }
    parse_usize(value)
        .map(Some)
        .ok_or_else(|| format!("{key} must be an integer or hex value, got {value:?}."))
}

fn parse_usize(value: &str) -> Option<usize> {
    if let Some(hex) = value
        .strip_prefix("0x")
        .or_else(|| value.strip_prefix("0X"))
    {
        usize::from_str_radix(hex, 16).ok()
    } else {
        value.parse::<usize>().ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rp1_hub75_uapi_layout_matches_kernel_header() {
        assert_eq!(std::mem::size_of::<Rp1hConfig>(), 88);
        assert_eq!(std::mem::size_of::<Rp1hPackFrame>(), 16);
        assert_eq!(std::mem::size_of::<Rp1hStats>(), 24);
        assert_eq!(std::mem::size_of::<Rp1hQueueFrame>(), 32);
        assert_eq!(std::mem::size_of::<Rp1hWaitPresent>(), 24);
        assert_eq!(std::mem::size_of::<Rp1hVsync>(), 24);
        assert_eq!(std::mem::size_of::<Rp1hPresentStats>(), 36);
        assert_eq!(std::mem::size_of::<Rp1hWorkerControl>(), 32);
        assert_eq!(std::mem::size_of::<Rp1hWorkerStatus>(), 80);
        assert_eq!(std::mem::size_of::<Rp1hMmapHeader>(), 220);
        assert_eq!(RP1H_CONFIG, 0xc058_4840);
        assert_eq!(RP1H_PACK_FRAME, 0x4010_4841);
        assert_eq!(RP1H_GET_STATS, 0x8018_4842);
        assert_eq!(RP1H_QUEUE_FRAME, 0xc020_4843);
        assert_eq!(RP1H_WAIT_PRESENT, 0xc018_4844);
        assert_eq!(RP1H_SIGNAL_VSYNC, 0xc018_4845);
        assert_eq!(RP1H_GET_PRESENT_STATS, 0x8024_4846);
        assert_eq!(RP1H_START_WORKER, 0x4020_4847);
        assert_eq!(RP1H_STOP_WORKER, 0x4020_4848);
        assert_eq!(RP1H_GET_WORKER_STATUS, 0x8050_4849);
    }

    #[test]
    fn rp1_hub75_runtime_defaults_to_state32_queued_swap() {
        assert_eq!(RP1H_STREAM_RIO32, 0);
        assert_eq!(RP1H_STREAM_RGB6_PACKED, 1);
        assert_eq!(RP1H_STREAM_RGB6_BYTE, 2);
        assert_eq!(RP1H_STREAM_STATE32, 3);
        assert_eq!(RP1H_SLOT_COUNT, 2);
        assert_eq!(RP1H_QUEUE_F_NONBLOCK, 1);
        assert_eq!(RP1H_QUEUE_F_REPLACE_PENDING, 2);
        assert_eq!(RP1H_WORKER_F_EXTERNAL_VSYNC, 1);
    }

    #[test]
    fn worker_progress_check_requires_real_presentation() {
        let status = Rp1Hub75WorkerStatus {
            frames_queued: 8,
            frames_presented: 0,
            vsync_count: 0,
            ..Rp1Hub75WorkerStatus::default()
        };

        assert!(worker_progress_missing(&status, 8));
        assert!(!worker_progress_missing(&status, 9));
    }

    #[test]
    fn worker_progress_check_allows_any_vsync_or_presented_frame() {
        let mut status = Rp1Hub75WorkerStatus {
            frames_queued: 64,
            frames_presented: 0,
            vsync_count: 1,
            ..Rp1Hub75WorkerStatus::default()
        };
        assert!(!worker_progress_missing(&status, 8));

        status.vsync_count = 0;
        status.frames_presented = 1;
        assert!(!worker_progress_missing(&status, 8));
    }

    #[test]
    fn three_port_active_rejects_three_parallel_lanes() {
        let config = MatrixConfigNative::new(
            WiringProfile::ThreePortActive,
            2,
            2,
            2,
            3,
            super::super::config::ColorOrder::Rgb,
        )
        .unwrap();

        let err = Rp1Hub75FrameLoader::for_config(&config, None).unwrap_err();
        assert!(err.contains("chain_length=4 parallel=1"));
    }

    #[test]
    fn three_port_active_rejects_stacked_2x2_input() {
        let config = MatrixConfigNative::new(
            WiringProfile::ThreePortActive,
            2,
            2,
            2,
            2,
            super::super::config::ColorOrder::Rgb,
        )
        .unwrap();

        let err = Rp1Hub75FrameLoader::for_config(&config, None).unwrap_err();
        assert!(err.contains("chain_length=4 parallel=1"));
    }

    #[test]
    fn three_port_active_geometry_uses_two_active_lanes_for_horizontal_chain4() {
        let config = MatrixConfigNative::new(
            WiringProfile::ThreePortActive,
            64,
            64,
            4,
            1,
            super::super::config::ColorOrder::Rgb,
        )
        .unwrap();

        assert_eq!(
            rp1h_geometry_for_config(&config).unwrap(),
            (64, 64, 4, 2, 2)
        );
    }

    #[test]
    fn three_port_active_horizontal_loader_keeps_256x64_regular_strip() {
        let config = MatrixConfigNative::new(
            WiringProfile::ThreePortActive,
            2,
            2,
            4,
            1,
            super::super::config::ColorOrder::Rgb,
        )
        .unwrap();
        let mut loader = Rp1Hub75FrameLoader::for_config(&config, None).unwrap();
        let mut input = vec![0; 48];

        set_rgb(&mut input, 8, 0, 0, [10, 0, 0]);
        set_rgb(&mut input, 8, 0, 1, [11, 0, 0]);
        set_rgb(&mut input, 8, 2, 0, [0, 20, 0]);
        set_rgb(&mut input, 8, 2, 1, [0, 21, 0]);
        set_rgb(&mut input, 8, 4, 0, [0, 0, 30]);
        set_rgb(&mut input, 8, 4, 1, [0, 0, 31]);
        set_rgb(&mut input, 8, 6, 0, [40, 40, 40]);
        set_rgb(&mut input, 8, 6, 1, [41, 41, 41]);

        let (ptr, len) = loader.prepare(&input).unwrap();
        let copied = unsafe { std::slice::from_raw_parts(ptr, len) };

        assert_eq!(len, 48);
        assert_eq!(copied, input.as_slice());
        assert_eq!(rgb_at(copied, 8, 0, 0), [10, 0, 0]);
        assert_eq!(rgb_at(copied, 8, 2, 0), [0, 20, 0]);
        assert_eq!(rgb_at(copied, 8, 4, 0), [0, 0, 30]);
        assert_eq!(rgb_at(copied, 8, 6, 0), [40, 40, 40]);
        assert_eq!(
            regular_chain2_strip_sources(copied, 8, 2, 0),
            [[10, 0, 0], [11, 0, 0], [0, 0, 30], [0, 0, 31]]
        );
        assert_eq!(
            regular_chain2_strip_sources(copied, 8, 2, 2),
            [[0, 20, 0], [0, 21, 0], [40, 40, 40], [41, 41, 41]]
        );
    }

    fn set_rgb(frame: &mut [u8], width: usize, x: usize, y: usize, rgb: [u8; 3]) {
        let offset = pixel_offset(width, x, y);
        frame[offset..offset + 3].copy_from_slice(&rgb);
    }

    fn rgb_at(frame: &[u8], width: usize, x: usize, y: usize) -> [u8; 3] {
        let offset = pixel_offset(width, x, y);
        [frame[offset], frame[offset + 1], frame[offset + 2]]
    }

    fn regular_chain2_strip_sources(
        frame: &[u8],
        width: usize,
        panel_rows: usize,
        x: usize,
    ) -> [[u8; 3]; 4] {
        let row_pairs = panel_rows / 2;
        let active_cols = width / 2;
        [
            rgb_at(frame, width, x, 0),
            rgb_at(frame, width, x, row_pairs),
            rgb_at(frame, width, active_cols + x, 0),
            rgb_at(frame, width, active_cols + x, row_pairs),
        ]
    }

    fn pixel_offset(width: usize, x: usize, y: usize) -> usize {
        (y * width + x) * 3
    }
}
