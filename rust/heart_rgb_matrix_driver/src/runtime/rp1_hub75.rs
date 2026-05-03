use std::fs::{File, OpenOptions};
use std::os::fd::{AsRawFd, RawFd};
use std::os::unix::fs::OpenOptionsExt;
use std::time::Duration;

use super::backend::MatrixBackend;
use super::config::{MatrixConfigNative, WiringProfile};
use super::frame::FrameBuffer;
use super::tuning::runtime_tuning;

const RP1H_DEVICE_PATH: &str = "/dev/rp1-hub75";
const RP1H_MAPPING_ADAFRUIT_HAT_PWM: u8 = 0;
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
    reserved1: [u32; 2],
}

#[derive(Debug)]
pub(crate) struct Rp1Hub75Backend {
    device: File,
    config: Rp1hConfig,
    _mapping: MmapMapping,
    wait_timeout_ns: Option<i64>,
    signal_vsync_after_queue: bool,
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

impl Rp1Hub75Backend {
    pub(crate) fn new(config: &MatrixConfigNative) -> Result<Self, String> {
        if config.wiring != WiringProfile::AdafruitHatPwm {
            return Err(
                "RP1 HUB75 backend only supports the Adafruit HAT PWM mapping.".to_string(),
            );
        }
        if config.chain_length != 1 {
            return Err(
                "RP1 HUB75 packer currently requires chain_length=1; use parallel panels instead."
                    .to_string(),
            );
        }

        let panel_count = config.panel_count()?;
        let frame_len = config.frame_len()?;
        let frame_bytes = u32::try_from(frame_len)
            .map_err(|_| "RP1 HUB75 frame size exceeds 32-bit UAPI length.".to_string())?;
        let pwm_bits = runtime_tuning()
            .pi5_simple_scan_default_pwm_bits
            .min(11)
            .max(1);

        let mut rp1_config = Rp1hConfig {
            size: std::mem::size_of::<Rp1hConfig>() as u32,
            cols: config.panel_cols,
            rows: config.panel_rows,
            pwm_bits,
            mapping: RP1H_MAPPING_ADAFRUIT_HAT_PWM,
            format: RP1H_FORMAT_RGB888,
            flags: if config.panel_rows >= 64 {
                RP1H_F_E_LINE_PRESENT
            } else {
                0
            },
            stream_format: RP1H_STREAM_STATE32,
            panel_count,
            lane_count: panel_count,
            chain_length: 1,
            slot_count: RP1H_SLOT_COUNT,
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

        let mapping = MmapMapping::new(device.as_raw_fd(), rp1_config.mmap_size)?;
        let wait_timeout_ns = std::env::var("HEART_RP1_HUB75_WAIT_PRESENT_TIMEOUT_NS")
            .ok()
            .and_then(|value| value.parse::<i64>().ok());
        let signal_vsync_after_queue = std::env::var("HEART_RP1_HUB75_SIGNAL_VSYNC_AFTER_QUEUE")
            .map(|value| value != "0")
            .unwrap_or(true);
        let worker_status_timeout_ms = std::env::var("HEART_RP1_HUB75_WORKER_STATUS_TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u32>().ok())
            .unwrap_or(0);
        start_worker(device.as_raw_fd(), worker_status_timeout_ms)?;

        Ok(Self {
            device,
            config: rp1_config,
            _mapping: mapping,
            wait_timeout_ns,
            signal_vsync_after_queue,
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
        let mut request = Rp1hQueueFrame {
            size: std::mem::size_of::<Rp1hQueueFrame>() as u32,
            length: u32::try_from(frame.as_slice().len())
                .map_err(|_| "RP1 HUB75 frame length exceeds 32-bit UAPI length.".to_string())?,
            flags: RP1H_QUEUE_F_REPLACE_PENDING,
            slot_index: 0,
            data: frame.as_slice().as_ptr() as u64,
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
        if self.signal_vsync_after_queue {
            let _ = self.signal_vsync()?;
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
        let _ = self.stop_worker();
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

impl MmapMapping {
    fn new(fd: RawFd, mmap_size: u32) -> Result<Self, String> {
        let len = usize::try_from(mmap_size)
            .map_err(|_| "RP1 HUB75 mmap size exceeds host usize.".to_string())?;
        let addr = unsafe {
            libc::mmap(
                std::ptr::null_mut(),
                len,
                libc::PROT_READ,
                libc::MAP_SHARED,
                fd,
                0,
            )
        };
        if addr == libc::MAP_FAILED {
            return Err(format!(
                "mmap {RP1H_DEVICE_PATH}: {}",
                std::io::Error::last_os_error()
            ));
        }
        Ok(Self {
            addr: addr as usize,
            len,
        })
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
}
