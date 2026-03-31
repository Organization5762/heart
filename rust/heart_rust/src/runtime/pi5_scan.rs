#![allow(dead_code)]

use std::ffi::c_char;
use std::slice;
use std::sync::Arc;
use std::time::{Duration, Instant};

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
use std::sync::{Condvar, Mutex};
#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
use std::thread::{self, JoinHandle};

use rayon::prelude::*;

use super::config::{expected_rgba_size, WiringProfile};
use super::frame::FrameBuffer;
use super::tuning::runtime_tuning;

const OE_ACTIVE_LOW: bool = true;
const PIO_ERROR_BUFFER_BYTES: usize = 256;
const PI5_SCAN_UNSUPPORTED_MESSAGE: &str =
    "Pi 5 scan transport is only supported on Linux aarch64 builds.";
// All packed GPIO words are rebased so GPIO 5 becomes bit 0. That keeps the
// transport word width at 23 bits instead of the original sparse 28-bit map.
const PIN_WORD_SHIFT: u32 = 5;
// Packed group format, in transport-word order:
//   0: row-addressed blank word
//   repeated:
//     0, span_len              => blank span
//     span_len, packed words   => data span
//   0, 0                       => end-of-spans marker
//   latch_word
//   active_word
//   dwell_counter
//
// The paired C parsers in native/pi5_pio_scan_shim.c and
// kernel/pi5_scan_loop/heart_pi5_scan_loop.c intentionally consume this exact
// layout. Keeping the format described in one place makes it much easier to
// check protocol changes against both transports.
// A fully blank group never needs per-column payload. It collapses to:
// blank word, blank sentinel, span count, blank sentinel, blank sentinel,
// latch word, active word, dwell counter.
const BLANK_RUN_GROUP_WORDS: usize = 8;
const BLANK_RUN_SENTINEL: u32 = 0;
const PIN_WORD_BITS: usize = 23;
const PIN_WORD_MASK: u32 = (1_u32 << PIN_WORD_BITS) - 1;

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Pi5ScanConfig {
    pub(crate) panel_rows: u16,
    pub(crate) panel_cols: u16,
    pub(crate) chain_length: u16,
    pub(crate) parallel: u8,
    pub(crate) pwm_bits: u8,
    pub(crate) lsb_dwell_ticks: u32,
    timing: Pi5ScanTiming,
    pinout: Pi5ScanPinout,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Pi5ScanTiming {
    pub(crate) clock_divider: f32,
    pub(crate) post_addr_ticks: u32,
    pub(crate) latch_ticks: u32,
    pub(crate) post_latch_ticks: u32,
}

impl Default for Pi5ScanTiming {
    // Keep the default timing conservative and explicit. These values match the
    // scan program and native shims, so changing them should be treated as a
    // protocol-level tuning change rather than a cosmetic default tweak.
    fn default() -> Self {
        Self {
            clock_divider: 1.0,
            post_addr_ticks: 5,
            latch_ticks: 1,
            post_latch_ticks: 1,
        }
    }
}

impl Pi5ScanConfig {
    // Translate the public matrix configuration into the Pi 5 scan-specific
    // shape. The builder-style setters below intentionally re-run validation so
    // callers cannot construct half-valid timing or geometry combinations.
    pub(crate) fn from_matrix_config(
        wiring: WiringProfile,
        panel_rows: u16,
        panel_cols: u16,
        chain_length: u16,
        parallel: u8,
    ) -> Result<Self, String> {
        let pinout = Pi5ScanPinout::for_wiring(wiring)?;
        let config = Self {
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            pwm_bits: runtime_tuning().pi5_scan_default_pwm_bits,
            lsb_dwell_ticks: pinout.default_lsb_dwell_ticks(),
            timing: Pi5ScanTiming::default(),
            pinout,
        };
        config.validate()?;
        Ok(config)
    }

    // Update the least-significant-bit dwell and immediately revalidate, since
    // dwell feeds directly into both visible PWM timing and packed group size.
    pub(crate) fn with_lsb_dwell_ticks(mut self, lsb_dwell_ticks: u32) -> Result<Self, String> {
        self.lsb_dwell_ticks = lsb_dwell_ticks;
        self.validate()?;
        Ok(self)
    }

    // Override PWM depth while preserving the "validated config" invariant for
    // every returned value.
    pub(crate) fn with_pwm_bits(mut self, pwm_bits: u8) -> Result<Self, String> {
        self.pwm_bits = pwm_bits;
        self.validate()?;
        Ok(self)
    }

    // Override the control-path timing as one unit so the caller can tune the
    // scan program without mutating fields behind validation's back.
    pub(crate) fn with_timing(mut self, timing: Pi5ScanTiming) -> Result<Self, String> {
        self.timing = timing;
        self.validate()?;
        Ok(self)
    }

    // Width is the logical chained width, not one physical panel width. The
    // packer and transport allocate one scan stream over this full span.
    pub(crate) fn width(&self) -> Result<u32, String> {
        u32::from(self.panel_cols)
            .checked_mul(u32::from(self.chain_length))
            .ok_or_else(|| "Pi 5 scan width exceeds supported dimensions.".to_string())
    }

    // Height is the logical output height after parallel fan-out. v1 only
    // supports parallel=1, but keeping this helper explicit makes that
    // limitation obvious at the call sites.
    pub(crate) fn height(&self) -> Result<u32, String> {
        u32::from(self.panel_rows)
            .checked_mul(u32::from(self.parallel))
            .ok_or_else(|| "Pi 5 scan height exceeds supported dimensions.".to_string())
    }

    // HUB75 scanout operates on row pairs, so this is the fundamental vertical
    // unit used by the packer and by the PIO control program.
    pub(crate) fn row_pairs(&self) -> Result<usize, String> {
        let height = usize::try_from(self.height()?)
            .map_err(|_| "Pi 5 scan height exceeds host usize.".to_string())?;
        Ok(height / 2)
    }

    // Expose the resolved pinout as a copy so callers can derive packed pin
    // words without reaching back into matrix-level configuration.
    pub(crate) fn pinout(&self) -> Pi5ScanPinout {
        self.pinout
    }

    // Return the validated timing bundle that both transports must honor.
    pub(crate) fn timing(&self) -> Pi5ScanTiming {
        self.timing
    }

    // Keep all geometry, timing, and transport assumptions in one place. This
    // function is intentionally strict because the native parsers and PIO
    // program assume these invariants hold.
    fn validate(&self) -> Result<(), String> {
        if self.parallel != 1 {
            return Err(format!(
                "Pi 5 scanout v1 currently supports parallel=1, received {}.",
                self.parallel
            ));
        }
        if !matches!(self.panel_rows, 16 | 32 | 64) {
            return Err(format!(
                "Unsupported panel_rows {}. Expected one of 16, 32, or 64.",
                self.panel_rows
            ));
        }
        if !matches!(self.panel_cols, 32 | 64) {
            return Err(format!(
                "Unsupported panel_cols {}. Expected 32 or 64.",
                self.panel_cols
            ));
        }
        if self.chain_length == 0 {
            return Err("chain_length must be at least 1 for Pi 5 scanout.".to_string());
        }
        if self.pwm_bits == 0 || self.pwm_bits > 16 {
            return Err(format!(
                "Unsupported pwm_bits {}. Expected 1 through 16.",
                self.pwm_bits
            ));
        }
        if self.lsb_dwell_ticks == 0 {
            return Err("lsb_dwell_ticks must be at least 1.".to_string());
        }
        if !self.timing.clock_divider.is_finite() || self.timing.clock_divider <= 0.0 {
            return Err("clock_divider must be a positive finite value.".to_string());
        }
        if self.timing.post_addr_ticks == 0 {
            return Err("post_addr_ticks must be at least 1.".to_string());
        }
        if self.timing.latch_ticks == 0 {
            return Err("latch_ticks must be at least 1.".to_string());
        }
        if self.timing.post_latch_ticks == 0 {
            return Err("post_latch_ticks must be at least 1.".to_string());
        }
        if self.panel_rows % 2 != 0 {
            return Err(format!(
                "Pi 5 scanout requires an even panel_rows value, received {}.",
                self.panel_rows
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct PackedScanFrameStats {
    pub(crate) compressed_blank_groups: usize,
    pub(crate) merged_identical_groups: usize,
    pub(crate) word_count: usize,
    pub(crate) pack_duration: Duration,
}

#[derive(Clone, Debug)]
pub(crate) struct PackedScanFrame {
    words: Vec<u32>,
}

impl PackedScanFrame {
    // Pack a logical RGBA frame into the compact transport stream consumed by
    // both the userspace rp1-pio path and the resident-loop kernel transport.
    // The returned stats exist so tuning and benchmarks can reason about what
    // the packer emitted without decoding the stream again.
    pub(crate) fn pack_rgba(
        config: &Pi5ScanConfig,
        rgba: &[u8],
    ) -> Result<(Self, PackedScanFrameStats), String> {
        let width = usize::try_from(config.width()?)
            .map_err(|_| "Pi 5 scan width exceeds host usize.".to_string())?;
        let height = usize::try_from(config.height()?)
            .map_err(|_| "Pi 5 scan height exceeds host usize.".to_string())?;
        let expected_size = expected_rgba_size(width as u32, height as u32)
            .ok_or_else(|| "Pi 5 scan geometry exceeds supported RGBA size.".to_string())?;
        if rgba.len() != expected_size {
            return Err(format!(
                "Pi 5 scan expected {expected_size} RGBA bytes but received {}.",
                rgba.len()
            ));
        }

        let row_pairs = config.row_pairs()?;
        let group_count = row_pairs * usize::from(config.pwm_bits);
        let words_per_group = max_group_word_count(width);
        let total_words = config.estimated_word_count_for_width(width)?;
        let pack_start = Instant::now();
        let mut words = vec![0_u32; total_words];
        let mut group_lengths = vec![0_usize; group_count];

        if total_words >= runtime_tuning().pi5_scan_pack_parallel_threshold_words {
            words
                .par_chunks_mut(words_per_group)
                .zip(group_lengths.par_iter_mut())
                .enumerate()
                .try_for_each(|(group_index, (segment, group_length))| {
                    *group_length = write_scan_segment(
                        segment,
                        config,
                        rgba,
                        width,
                        row_pairs,
                        group_index / usize::from(config.pwm_bits),
                        group_index % usize::from(config.pwm_bits),
                    )?;
                    Ok::<(), String>(())
                })?;
        } else {
            for (group_index, (segment, group_length)) in words
                .chunks_mut(words_per_group)
                .zip(group_lengths.iter_mut())
                .enumerate()
            {
                *group_length = write_scan_segment(
                    segment,
                    config,
                    rgba,
                    width,
                    row_pairs,
                    group_index / usize::from(config.pwm_bits),
                    group_index % usize::from(config.pwm_bits),
                )?;
            }
        }
        let merged_identical_groups = merge_identical_plane_groups(
            &mut words,
            &mut group_lengths,
            row_pairs,
            usize::from(config.pwm_bits),
            words_per_group,
        )?;
        let compressed_blank_groups = group_lengths
            .iter()
            .filter(|&&group_length| group_length == BLANK_RUN_GROUP_WORDS)
            .count();
        let words = compact_group_words(words, &group_lengths, words_per_group)?;
        let word_count = words.len();
        let pack_duration = pack_start.elapsed();
        Ok((
            Self { words },
            PackedScanFrameStats {
                compressed_blank_groups,
                merged_identical_groups,
                word_count,
                pack_duration,
            },
        ))
    }

    // Pack from the reusable runtime frame buffer without forcing callers to
    // peel the raw RGBA slice out at every submission site.
    pub(crate) fn pack_frame(
        config: &Pi5ScanConfig,
        frame: &FrameBuffer,
    ) -> Result<(Self, PackedScanFrameStats), String> {
        Self::pack_rgba(config, frame.as_slice())
    }

    // Expose the transport words for benchmarks and any code that needs to
    // reason about packed-frame size without reinterpreting bytes.
    pub(crate) fn as_words(&self) -> &[u32] {
        &self.words
    }

    // Reinterpret the packed transport words as bytes for the native FFI
    // boundary. The packed frame owns the backing storage, so this view is
    // valid for the lifetime of `self`.
    pub(crate) fn as_bytes(&self) -> &[u8] {
        unsafe {
            slice::from_raw_parts(
                self.words.as_ptr().cast::<u8>(),
                self.words.len() * std::mem::size_of::<u32>(),
            )
        }
    }

    // Return the compact transport word count, not the logical pixel count.
    pub(crate) fn word_count(&self) -> usize {
        self.words.len()
    }
}

#[derive(Debug)]
pub(crate) struct Pi5KernelResidentLoop {
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    handle: Pi5KernelResidentLoopHandle,
}

impl Pi5KernelResidentLoop {
    // Open the kernel-owned resident replay path with enough backing storage to
    // hold one packed frame. The kernel module owns continuous refresh after
    // load/start succeeds; userspace only replaces the resident buffer.
    pub(crate) fn new(frame_bytes: usize) -> Result<Self, String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
            let mut handle: *mut ffi::HeartPi5KernelResidentLoopHandle = std::ptr::null_mut();
            let frame_bytes = u32::try_from(frame_bytes)
                .map_err(|_| "Resident scan loop frame exceeds 32-bit size limits.".to_string())?;
            let result = unsafe {
                heart_pi5_scan_loop_open(
                    frame_bytes,
                    &mut handle,
                    error_buffer.as_mut_ptr(),
                    error_buffer.len(),
                )
            };
            if result != 0 || handle.is_null() {
                return Err(read_error_buffer(&error_buffer).unwrap_or_else(|| {
                    format!("Resident scan loop initialization failed with code {result}.")
                }));
            }
            return Ok(Self {
                handle: Pi5KernelResidentLoopHandle(handle),
            });
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = frame_bytes;
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    // Copy one packed frame into the resident kernel buffer. This is the
    // changed-frame cost for the resident loop path.
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    pub(crate) fn load_frame(&self, frame: &PackedScanFrame) -> Result<(), String> {
        let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
        let data_bytes = u32::try_from(frame.as_bytes().len())
            .map_err(|_| "Resident scan loop frame exceeds 32-bit size limits.".to_string())?;
        let result = unsafe {
            heart_pi5_scan_loop_load(
                self.handle.0,
                frame.as_bytes().as_ptr(),
                data_bytes,
                error_buffer.as_mut_ptr(),
                error_buffer.len(),
            )
        };
        if result != 0 {
            return Err(read_error_buffer(&error_buffer).unwrap_or_else(|| {
                format!("Resident scan loop frame load failed with code {result}.")
            }));
        }
        Ok(())
    }

    // Non-Linux or non-aarch64 builds expose the same API but fail fast so the
    // higher layers can report "unsupported" uniformly.
    #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
    pub(crate) fn load_frame(&self, frame: &PackedScanFrame) -> Result<(), String> {
        let _ = frame;
        Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
    }

    // Begin replay of the resident packed frame. The kernel module will keep
    // cycling that frame until userspace stops it or replaces it.
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    pub(crate) fn start(&self) -> Result<(), String> {
        let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
        let result = unsafe {
            heart_pi5_scan_loop_start(self.handle.0, error_buffer.as_mut_ptr(), error_buffer.len())
        };
        if result != 0 {
            return Err(read_error_buffer(&error_buffer).unwrap_or_else(|| {
                format!("Resident scan loop start failed with code {result}.")
            }));
        }
        Ok(())
    }

    // Unsupported-platform stub matching the Linux entrypoint above.
    #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
    pub(crate) fn start(&self) -> Result<(), String> {
        Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
    }

    // Stop resident replay so the caller can safely load a new frame or shut
    // the transport down without the kernel continuing to touch the old buffer.
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    pub(crate) fn stop(&self) -> Result<(), String> {
        let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
        let result = unsafe {
            heart_pi5_scan_loop_stop(self.handle.0, error_buffer.as_mut_ptr(), error_buffer.len())
        };
        if result != 0 {
            return Err(read_error_buffer(&error_buffer)
                .unwrap_or_else(|| format!("Resident scan loop stop failed with code {result}.")));
        }
        Ok(())
    }

    // Unsupported-platform stub matching the Linux entrypoint above.
    #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
    pub(crate) fn stop(&self) -> Result<(), String> {
        Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
    }

    // Block until the kernel module reports at least the requested presentation
    // count. This is the primitive needed for true "wait for next full frame"
    // semantics on the resident path.
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    pub(crate) fn wait_presentations(&self, target_presentations: u64) -> Result<u64, String> {
        let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
        let mut completed_presentations = 0_u64;
        let result = unsafe {
            heart_pi5_scan_loop_wait_presentations(
                self.handle.0,
                target_presentations,
                &mut completed_presentations,
                error_buffer.as_mut_ptr(),
                error_buffer.len(),
            )
        };
        if result != 0 {
            return Err(read_error_buffer(&error_buffer)
                .unwrap_or_else(|| format!("Resident scan loop wait failed with code {result}.")));
        }
        Ok(completed_presentations)
    }

    // Unsupported-platform stub matching the Linux entrypoint above.
    #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
    pub(crate) fn wait_presentations(&self, target_presentations: u64) -> Result<u64, String> {
        let _ = target_presentations;
        Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
    }

    // Query the current presentation counter without waiting. Benchmarks use
    // this to measure steady-state refresh over a wall-clock window.
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    pub(crate) fn presentation_count(&self) -> Result<u64, String> {
        let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
        let mut presentations = 0_u64;
        let mut last_error = 0_i32;
        let mut replay_enabled = 0_u32;
        let result = unsafe {
            heart_pi5_scan_loop_stats(
                self.handle.0,
                &mut presentations,
                &mut last_error,
                &mut replay_enabled,
                error_buffer.as_mut_ptr(),
                error_buffer.len(),
            )
        };
        if result != 0 {
            return Err(read_error_buffer(&error_buffer).unwrap_or_else(|| {
                format!("Resident scan loop stats failed with code {result}.")
            }));
        }
        let _ = last_error;
        let _ = replay_enabled;
        Ok(presentations)
    }

    // Unsupported-platform stub matching the Linux entrypoint above.
    #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
    pub(crate) fn presentation_count(&self) -> Result<u64, String> {
        Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
    }
}

impl Drop for Pi5KernelResidentLoop {
    // Always close the native handle on drop so the kernel module can release
    // its resident buffers even if higher layers forget to stop explicitly.
    fn drop(&mut self) {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        unsafe {
            if !self.handle.0.is_null() {
                heart_pi5_scan_loop_close(self.handle.0);
                self.handle.0 = std::ptr::null_mut();
            }
        }
    }
}

#[derive(Debug)]
pub(crate) struct Pi5PioScanTransport {
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    handle: Pi5PioScanHandle,
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    shared: Arc<Pi5PioScanAsyncShared>,
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    hardware_lock: Arc<Mutex<()>>,
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    worker: Option<JoinHandle<()>>,
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
unsafe impl Send for Pi5PioScanTransport {}

impl Pi5PioScanTransport {
    // Open the raw rp1-pio transport and start the worker that serializes all
    // hardware access. Callers interact with a logical async transport; the
    // worker turns that into one-at-a-time submit/wait cycles.
    pub(crate) fn new(
        max_transfer_words: usize,
        pinout: Pi5ScanPinout,
        timing: Pi5ScanTiming,
    ) -> Result<Self, String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            if max_transfer_words == 0 {
                return Err("Pi 5 scan transport requires a non-zero transfer buffer.".to_string());
            }
            if !timing.clock_divider.is_finite() || timing.clock_divider <= 0.0 {
                return Err(
                    "Pi 5 scan transport requires a positive finite clock divider.".to_string(),
                );
            }
            let tuning = runtime_tuning();
            if tuning.pi5_scan_default_dma_buffer_count == 0 {
                return Err("Pi 5 scan transport requires at least one DMA buffer.".to_string());
            }
            let max_transfer_bytes = max_transfer_words
                .checked_mul(std::mem::size_of::<u32>())
                .ok_or_else(|| {
                    "Pi 5 scan transport buffer size overflowed while converting to bytes."
                        .to_string()
                })?;
            let dma_buffer_size = u32::try_from(
                max_transfer_bytes.min(tuning.pi5_scan_max_dma_buffer_bytes),
            )
            .map_err(|_| "Pi 5 scan transport buffer exceeds 32-bit DMA limits.".to_string())?;
            let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
            let mut handle: *mut ffi::HeartPi5PioScanHandle = std::ptr::null_mut();
            let result = unsafe {
                heart_pi5_pio_scan_open(
                    pinout.oe_gpio,
                    pinout.lat_gpio,
                    pinout.clock_gpio,
                    timing.clock_divider,
                    timing.post_addr_ticks,
                    timing.latch_ticks,
                    timing.post_latch_ticks,
                    dma_buffer_size,
                    tuning.pi5_scan_default_dma_buffer_count,
                    &mut handle,
                    error_buffer.as_mut_ptr(),
                    error_buffer.len(),
                )
            };
            if result != 0 || handle.is_null() {
                return Err(read_error_buffer(&error_buffer).unwrap_or_else(|| {
                    format!("Pi 5 scan transport initialization failed with code {result}.")
                }));
            }
            let handle = Pi5PioScanHandle(handle);
            let shared = Arc::new(Pi5PioScanAsyncShared {
                state: Mutex::new(Pi5PioScanAsyncState::default()),
                signal: Condvar::new(),
            });
            let hardware_lock = Arc::new(Mutex::new(()));
            let worker = spawn_scan_transport_worker(
                handle,
                Arc::clone(&shared),
                Arc::clone(&hardware_lock),
            )?;
            return Ok(Self {
                handle,
                shared,
                hardware_lock,
                worker: Some(worker),
            });
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = max_transfer_words;
            let _ = pinout;
            let _ = timing;
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    // Queue the newest packed frame for transport without blocking on the
    // current hardware submission. The worker coalesces duplicate or superseded
    // pending frames so slow hardware does not create an unbounded queue.
    pub(crate) fn submit_async(
        &self,
        frame_identity: (usize, u64),
        frame: Arc<PackedScanFrame>,
    ) -> Result<(), String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            let mut state = self
                .shared
                .state
                .lock()
                .map_err(|_| "Pi 5 scan transport state lock poisoned.".to_string())?;
            if let Some(error) = state.error.clone() {
                return Err(error);
            }
            if state.closed {
                return Err("Pi 5 scan transport is already closed.".to_string());
            }
            if state.transfer_in_flight
                && state.active_identity == Some(frame_identity)
                && state.pending_frame.is_none()
            {
                return Ok(());
            }
            if state.pending_identity == Some(frame_identity) {
                return Ok(());
            }
            state.pending_frame = Some(frame);
            state.pending_identity = Some(frame_identity);
            self.shared.signal.notify_one();
            Ok(())
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = frame_identity;
            let _ = frame;
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    // Wait until the transport has no active submission and no queued
    // replacement frame. This is the safe point for benchmarks and shutdown.
    pub(crate) fn wait_complete(&self) -> Result<(), String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            let mut state = self
                .shared
                .state
                .lock()
                .map_err(|_| "Pi 5 scan transport state lock poisoned.".to_string())?;
            loop {
                if let Some(error) = state.error.clone() {
                    return Err(error);
                }
                if !state.transfer_in_flight && state.pending_frame.is_none() {
                    return Ok(());
                }
                state = self
                    .shared
                    .signal
                    .wait(state)
                    .map_err(|_| "Pi 5 scan transport state lock poisoned.".to_string())?;
            }
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    // Wait until the named frame has been presented the requested number of
    // times. This is the userspace transport's frame-boundary primitive for any
    // future VSync-like API.
    pub(crate) fn wait_frame_presented(
        &self,
        frame_identity: (usize, u64),
        target_presentations: u64,
    ) -> Result<(), String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            let mut state = self
                .shared
                .state
                .lock()
                .map_err(|_| "Pi 5 scan transport state lock poisoned.".to_string())?;
            loop {
                if let Some(error) = state.error.clone() {
                    return Err(error);
                }
                if state.active_identity == Some(frame_identity)
                    && state.active_presentation_count >= target_presentations
                {
                    return Ok(());
                }
                state = self
                    .shared
                    .signal
                    .wait(state)
                    .map_err(|_| "Pi 5 scan transport state lock poisoned.".to_string())?;
            }
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = frame_identity;
            let _ = target_presentations;
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    // Read the current presentation count for the named active frame without
    // blocking, returning zero if some newer frame has already replaced it.
    pub(crate) fn active_presentation_count(
        &self,
        frame_identity: (usize, u64),
    ) -> Result<u64, String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            let state = self
                .shared
                .state
                .lock()
                .map_err(|_| "Pi 5 scan transport state lock poisoned.".to_string())?;
            if let Some(error) = state.error.clone() {
                return Err(error);
            }
            if state.active_identity == Some(frame_identity) {
                return Ok(state.active_presentation_count);
            }
            Ok(0)
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = frame_identity;
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    // Synchronous helper kept for benchmarks and bring-up. Production code uses
    // `submit_async()` so packing and application work can overlap transport.
    pub(crate) fn stream(&self, frame: &PackedScanFrame) -> Result<Duration, String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            self.wait_complete()?;
            let start = Instant::now();
            let _hardware_guard = self
                .hardware_lock
                .lock()
                .map_err(|_| "Pi 5 scan hardware lock poisoned.".to_string())?;
            submit_scan_frame(self.handle, frame)?;
            wait_for_scan_completion(self.handle)?;
            Ok(start.elapsed())
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = frame;
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

}

impl Drop for Pi5PioScanTransport {
    // Stop the worker before closing the native handle so nothing can issue one
    // final submit against a freed rp1-pio context during teardown.
    fn drop(&mut self) {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            if let Ok(mut state) = self.shared.state.lock() {
                state.closed = true;
            }
            self.shared.signal.notify_all();
            if let Some(worker) = self.worker.take() {
                let _ = worker.join();
            }
            let _ = self.wait_complete();
            unsafe {
                if !self.handle.0.is_null() {
                    heart_pi5_pio_scan_close(self.handle.0);
                    self.handle.0 = std::ptr::null_mut();
                }
            }
        }
    }
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
#[derive(Clone, Copy, Debug)]
struct Pi5PioScanHandle(*mut ffi::HeartPi5PioScanHandle);

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
unsafe impl Send for Pi5PioScanHandle {}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
#[derive(Clone, Copy, Debug)]
struct Pi5KernelResidentLoopHandle(*mut ffi::HeartPi5KernelResidentLoopHandle);

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
#[derive(Debug, Default)]
struct Pi5PioScanAsyncState {
    pending_frame: Option<Arc<PackedScanFrame>>,
    pending_identity: Option<(usize, u64)>,
    active_frame: Option<Arc<PackedScanFrame>>,
    active_identity: Option<(usize, u64)>,
    active_presentation_count: u64,
    transfer_in_flight: bool,
    closed: bool,
    error: Option<String>,
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
#[derive(Debug)]
struct Pi5PioScanAsyncShared {
    state: Mutex<Pi5PioScanAsyncState>,
    signal: Condvar,
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
fn spawn_scan_transport_worker(
    handle: Pi5PioScanHandle,
    shared: Arc<Pi5PioScanAsyncShared>,
    hardware_lock: Arc<Mutex<()>>,
) -> Result<JoinHandle<()>, String> {
    // Name the thread because this transport frequently shows up in profiles,
    // crash logs, and shutdown diagnostics when tuning scanout behavior.
    thread::Builder::new()
        .name("heart-pi5-scan-transport".to_string())
        .spawn(move || run_scan_transport_worker(handle, shared, hardware_lock))
        .map_err(|error| error.to_string())
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
fn run_scan_transport_worker(
    handle: Pi5PioScanHandle,
    shared: Arc<Pi5PioScanAsyncShared>,
    hardware_lock: Arc<Mutex<()>>,
) {
    // The caller is allowed to keep producing frames while the hardware is busy,
    // but only one transfer is ever allowed to touch the state machine at a
    // time. The worker owns that serialization point and coalesces queued work
    // down to "the newest pending frame".
    loop {
        let (frame, frame_identity, is_resident_repeat) = {
            let mut state = match shared.state.lock() {
                Ok(state) => state,
                Err(_) => return,
            };
            while !state.closed && state.pending_frame.is_none() && state.active_frame.is_none() {
                match shared.signal.wait(state) {
                    Ok(wait_state) => state = wait_state,
                    Err(_) => return,
                }
            }
            if state.closed && state.pending_frame.is_none() && state.active_frame.is_none() {
                return;
            }
            let (frame, frame_identity, is_resident_repeat) = if let Some(frame) =
                state.pending_frame.take()
            {
                let Some(frame_identity) = state.pending_identity.take() else {
                    continue;
                };
                state.active_frame = Some(Arc::clone(&frame));
                state.active_identity = Some(frame_identity);
                state.active_presentation_count = 0;
                (frame, frame_identity, false)
            } else {
                let Some(frame) = state.active_frame.as_ref().map(Arc::clone) else {
                    continue;
                };
                let Some(frame_identity) = state.active_identity else {
                    continue;
                };
                (frame, frame_identity, true)
            };
            state.transfer_in_flight = true;
            (frame, frame_identity, is_resident_repeat)
        };

        if is_resident_repeat {
            // Give the resident-loop path a short breather so repeated refreshes
            // do not starve the producer side when the displayed frame is static.
            thread::sleep(runtime_tuning().pi5_scan_resident_loop_resubmit_pause);
        }

        let transfer_result = (|| -> Result<(), String> {
            // Both the raw rp1-pio path and the kernel resident-loop path expose
            // synchronous "submit then wait" primitives at the FFI boundary. The
            // worker keeps that boundary serialized so higher-level Python and
            // Rust callers can submit asynchronously without ever overlapping
            // hardware access.
            let _hardware_guard = hardware_lock
                .lock()
                .map_err(|_| "Pi 5 scan hardware lock poisoned.".to_string())?;
            submit_scan_frame(handle, frame.as_ref())?;
            wait_for_scan_completion(handle)?;
            Ok(())
        })();

        let mut state = match shared.state.lock() {
            Ok(state) => state,
            Err(_) => return,
        };
        state.transfer_in_flight = false;
        if state.active_identity == Some(frame_identity) {
            state.active_presentation_count = state.active_presentation_count.saturating_add(1);
        }
        if let Err(error) = transfer_result {
            state.error = Some(error);
            state.closed = true;
        }
        shared.signal.notify_all();
        if state.closed {
            return;
        }
    }
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
fn submit_scan_frame(handle: Pi5PioScanHandle, frame: &PackedScanFrame) -> Result<(), String> {
    // Submit the already-packed transport bytes to rp1-pio exactly as-is. Any
    // compaction work must happen before this point because the native layer and
    // PIO parser both consume an opaque stream here.
    let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
    let data_bytes = u32::try_from(frame.as_bytes().len())
        .map_err(|_| "Pi 5 scan frame exceeds 32-bit DMA limits.".to_string())?;
    let result = unsafe {
        heart_pi5_pio_scan_submit(
            handle.0,
            frame.as_bytes().as_ptr(),
            data_bytes,
            error_buffer.as_mut_ptr(),
            error_buffer.len(),
        )
    };
    if result != 0 {
        return Err(read_error_buffer(&error_buffer)
            .unwrap_or_else(|| format!("Pi 5 scan submit failed with code {result}.")));
    }
    Ok(())
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
fn wait_for_scan_completion(handle: Pi5PioScanHandle) -> Result<(), String> {
    // Wait for the current rp1-pio submission to drain. This is the transport's
    // serialization point: no subsequent frame may touch the state machine
    // until this returns.
    let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
    let result =
        unsafe { heart_pi5_pio_scan_wait(handle.0, error_buffer.as_mut_ptr(), error_buffer.len()) };
    if result != 0 {
        return Err(read_error_buffer(&error_buffer)
            .unwrap_or_else(|| format!("Pi 5 scan wait failed with code {result}.")));
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct Pi5ScanPinout {
    rgb_gpios: [u8; 6],
    addr_gpios: [u8; 5],
    oe_gpio: u32,
    lat_gpio: u32,
    clock_gpio: u32,
}

impl Pi5ScanPinout {
    // Resolve the logical wiring profile into the exact GPIO map the packed
    // transport and PIO parser expect. Any wiring change here is a protocol
    // change because it alters packed pin-word meaning.
    fn for_wiring(wiring: WiringProfile) -> Result<Self, String> {
        match wiring {
            WiringProfile::AdafruitHatPwm => Ok(Self {
                rgb_gpios: [5, 13, 6, 12, 16, 23],
                addr_gpios: [22, 26, 27, 20, 24],
                oe_gpio: 18,
                lat_gpio: 21,
                clock_gpio: 17,
            }),
            WiringProfile::AdafruitHat => Ok(Self {
                rgb_gpios: [5, 13, 6, 12, 16, 23],
                addr_gpios: [22, 26, 27, 20, 24],
                oe_gpio: 4,
                lat_gpio: 21,
                clock_gpio: 17,
            }),
            WiringProfile::AdafruitTripleHat => {
                Err("Pi 5 scanout v1 does not yet support AdafruitTripleHat.".to_string())
            }
        }
    }

    // Encode the row-pair address into the rebased packed pin-word space used
    // by the scan stream.
    fn address_bits(&self, row_pair: usize) -> u32 {
        let mut bits = 0_u32;
        for (bit_index, gpio) in self.addr_gpios.iter().enumerate() {
            if (row_pair & (1 << bit_index)) != 0 {
                bits |= 1_u32 << (u32::from(*gpio) - PIN_WORD_SHIFT);
            }
        }
        bits
    }

    // Return the OE bit pattern that actively drives the display for this
    // hardware. The active-low quirk is kept in one place so the rest of the
    // packer can reason in terms of "active" versus "blank".
    fn oe_active_bits(&self) -> u32 {
        if OE_ACTIVE_LOW {
            0
        } else {
            1_u32 << (self.oe_gpio - PIN_WORD_SHIFT)
        }
    }

    // Return the OE bit pattern that blanks the display while shifting or
    // latching.
    fn oe_inactive_bits(&self) -> u32 {
        if OE_ACTIVE_LOW {
            1_u32 << (self.oe_gpio - PIN_WORD_SHIFT)
        } else {
            0
        }
    }

    // Return the latched-control bit used for the explicit latch phase in the
    // packed stream trailer.
    fn lat_bits(&self) -> u32 {
        1_u32 << (self.lat_gpio - PIN_WORD_SHIFT)
    }

    // Keep the default dwell policy alongside the pin mapping because the
    // supported bonnet layouts are the place where panel-level timing defaults
    // are chosen today.
    fn default_lsb_dwell_ticks(&self) -> u32 {
        2
    }
}

fn write_scan_segment(
    words: &mut [u32],
    config: &Pi5ScanConfig,
    rgba: &[u8],
    width: usize,
    row_pairs: usize,
    row_pair: usize,
    plane_index: usize,
) -> Result<usize, String> {
    // Encode one row-pair / bitplane group into the transport format described
    // at the top of this file. This is the hot path where RGBA state becomes
    // the compact span stream consumed by both native transports.
    if row_pair >= row_pairs {
        return Err(format!(
            "Row pair {row_pair} exceeds the configured row pair count {row_pairs}."
        ));
    }
    if words.len() != max_group_word_count(width) {
        return Err(format!(
            "Pi 5 scan segment expected {} words but received {}.",
            max_group_word_count(width),
            words.len()
        ));
    }
    let control = build_scan_segment_control(config, row_pair, plane_index)?;
    words[0] = control.blank_word;
    let pin_words = collect_scan_pin_words(
        config,
        rgba,
        width,
        row_pairs,
        row_pair,
        control.pinout,
        control.blank_word,
        control.msb_first_shift,
    );

    if scan_segment_is_all_blank(&pin_words, control.blank_word) {
        return write_blank_scan_segment(words, width, control);
    }

    let active_window = find_active_pin_word_window(&pin_words, control.blank_word, width)?;
    let mut word_index = emit_scan_segment_spans(
        words,
        active_window.pin_words,
        control.blank_word,
        active_window.prefix_blank_count,
        active_window.suffix_blank_count,
    )?;
    word_index = write_scan_segment_trailer(words, word_index, control);
    Ok(word_index)
}

#[derive(Clone, Copy)]
struct ScanSegmentControl {
    pinout: Pi5ScanPinout,
    blank_word: u32,
    active_word: u32,
    dwell_ticks: u32,
    msb_first_shift: usize,
}

struct ActivePinWordWindow<'a> {
    pin_words: &'a [u32],
    prefix_blank_count: usize,
    suffix_blank_count: usize,
}

#[inline]
fn build_scan_segment_control(
    config: &Pi5ScanConfig,
    row_pair: usize,
    plane_index: usize,
) -> Result<ScanSegmentControl, String> {
    // Precompute the control words and timing shared by every span emitted for
    // this group so the rest of the packer can focus on data layout.
    let pinout = config.pinout();
    let addr_bits = pinout.address_bits(row_pair);
    // PWM groups are emitted MSB first so the longest dwell lands earliest in
    // the packed stream, matching the PIO program's simple "read dwell counter,
    // count down, wrap" control flow.
    let msb_first_shift = usize::from(config.pwm_bits) - plane_index - 1;
    let dwell_ticks = config
        .lsb_dwell_ticks
        .checked_shl(msb_first_shift as u32)
        .ok_or_else(|| "Pi 5 scan dwell ticks overflowed.".to_string())?;
    Ok(ScanSegmentControl {
        pinout,
        blank_word: addr_bits | pinout.oe_inactive_bits(),
        active_word: addr_bits | pinout.oe_active_bits(),
        dwell_ticks,
        msb_first_shift,
    })
}

#[inline]
fn collect_scan_pin_words(
    config: &Pi5ScanConfig,
    rgba: &[u8],
    width: usize,
    row_pairs: usize,
    row_pair: usize,
    pinout: Pi5ScanPinout,
    blank_word: u32,
    msb_first_shift: usize,
) -> Vec<u32> {
    // Build the per-column pin words before span compression. Keeping this as a
    // flat intermediate vector makes it cheap to trim blank edges, split large
    // internal blank gaps, and compare whole groups for merge opportunities.
    let mut pin_words = Vec::with_capacity(width);
    for column in 0..width {
        pin_words.push(
            blank_word
                | scan_pixel_bits(
                    rgba,
                    pinout,
                    width,
                    row_pair,
                    row_pairs,
                    column,
                    msb_first_shift,
                    config.pwm_bits,
                ),
        );
    }
    pin_words
}

#[inline]
fn scan_segment_is_all_blank(pin_words: &[u32], blank_word: u32) -> bool {
    // Fast blank detection lets the packer collapse a group to the small
    // constant-size blank encoding without scanning for span boundaries twice.
    pin_words.iter().all(|&pin_word| pin_word == blank_word)
}

#[inline]
fn write_blank_scan_segment(
    words: &mut [u32],
    width: usize,
    control: ScanSegmentControl,
) -> Result<usize, String> {
    // Emit the fixed blank-group encoding used when no column in this group
    // lights a pixel. This is the cheapest possible resident replay payload.
    // A fully blank group is the cheapest case: no shifted pixel payload,
    // just "blank N columns" plus the fixed latch/active/dwell trailer.
    words[1] = BLANK_RUN_SENTINEL;
    words[2] = encode_span_count(width)?;
    write_scan_segment_trailer(words, 3, control);
    Ok(BLANK_RUN_GROUP_WORDS)
}

#[inline]
fn find_active_pin_word_window<'a>(
    pin_words: &'a [u32],
    blank_word: u32,
    width: usize,
) -> Result<ActivePinWordWindow<'a>, String> {
    // Trim leading and trailing blank columns so the later span writer only has
    // to look for meaningful internal gaps.
    let first_nonblank = pin_words
        .iter()
        .position(|&pin_word| pin_word != blank_word)
        .ok_or_else(|| "Pi 5 scan lost the first nonblank pixel span.".to_string())?;
    let last_nonblank = pin_words
        .iter()
        .rposition(|&pin_word| pin_word != blank_word)
        .ok_or_else(|| "Pi 5 scan lost the last nonblank pixel span.".to_string())?;
    let suffix_blank_count = width
        .checked_sub(last_nonblank + 1)
        .ok_or_else(|| "Pi 5 scan trailing blank span underflowed.".to_string())?;
    Ok(ActivePinWordWindow {
        pin_words: &pin_words[first_nonblank..last_nonblank + 1],
        prefix_blank_count: first_nonblank,
        suffix_blank_count,
    })
}

fn emit_scan_segment_spans(
    words: &mut [u32],
    active_pin_words: &[u32],
    blank_word: u32,
    prefix_blank_count: usize,
    suffix_blank_count: usize,
) -> Result<usize, String> {
    // Write the variable-length span section between the leading blank word and
    // the fixed control trailer. The important optimization here is splitting
    // large internal blank runs into their own spans instead of packing them as
    // full data runs.
    let mut word_index = 1_usize;
    if prefix_blank_count > 0 {
        emit_blank_run(words, &mut word_index, prefix_blank_count)?;
    }
    let mut data_run_start = 0_usize;
    let mut column_index = 0_usize;
    while column_index < active_pin_words.len() {
        if active_pin_words[column_index] != blank_word {
            column_index += 1;
            continue;
        }
        let blank_start = column_index;
        while column_index < active_pin_words.len() && active_pin_words[column_index] == blank_word
        {
            column_index += 1;
        }
        let blank_len = column_index - blank_start;
        if column_index == active_pin_words.len()
            || blank_len < runtime_tuning().pi5_scan_internal_blank_run_min_pixels
        {
            continue;
        }
        // Large internal blank gaps are worth splitting into their own spans so
        // the resident transport does not carry a near-full packed data run for
        // a row that only lights a few narrow islands.
        emit_data_run(words, &mut word_index, &active_pin_words[data_run_start..blank_start])?;
        emit_blank_run(words, &mut word_index, blank_len)?;
        data_run_start = column_index;
    }
    emit_data_run(words, &mut word_index, &active_pin_words[data_run_start..])?;
    if suffix_blank_count > 0 {
        emit_blank_run(words, &mut word_index, suffix_blank_count)?;
    }
    Ok(word_index)
}

#[inline]
fn write_scan_segment_trailer(
    words: &mut [u32],
    word_index: usize,
    control: ScanSegmentControl,
) -> usize {
    // Emit the fixed end-of-spans marker plus latch/active/dwell words. The C
    // parsers rely on this exact trailer shape.
    words[word_index] = BLANK_RUN_SENTINEL;
    words[word_index + 1] = BLANK_RUN_SENTINEL;
    words[word_index + 2] = control.blank_word | control.pinout.lat_bits();
    words[word_index + 3] = control.active_word;
    words[word_index + 4] = encode_dwell_counter(control.dwell_ticks);
    word_index + 5
}

pub(crate) fn packed_pin_word_count(pin_word_count: usize) -> usize {
    // Convert logical pin words into packed transport words after rebasing the
    // GPIO map to 23 bits.
    pin_word_count
        .checked_mul(PIN_WORD_BITS)
        .and_then(|bits| bits.checked_add(31))
        .map(|bits| bits / 32)
        .unwrap_or(usize::MAX)
}

pub(crate) fn max_group_word_count(width: usize) -> usize {
    // Size the per-group scratch buffer for the worst-case alternating
    // lit/blank/lit/... span pattern so packing never has to realloc.
    // Worst case is alternating one-pixel lit and blank spans across the row.
    // That produces roughly width span headers plus the packed payload words,
    // then the fixed control trailer.
    width
        .checked_mul(2)
        .and_then(|words| words.checked_add(6))
        .unwrap_or(usize::MAX)
}

fn emit_blank_run(
    words: &mut [u32],
    word_index: &mut usize,
    blank_count: usize,
) -> Result<(), String> {
    // Encode one blank span in-place in the transport buffer.
    words[*word_index] = BLANK_RUN_SENTINEL;
    words[*word_index + 1] = encode_span_count(blank_count)?;
    *word_index += 2;
    Ok(())
}

fn emit_data_run(
    words: &mut [u32],
    word_index: &mut usize,
    pin_words: &[u32],
) -> Result<(), String> {
    // Encode one nonblank span by writing its logical length followed by the
    // dense packed pin words consumed by the PIO parser's autopull stream.
    if pin_words.is_empty() {
        return Ok(());
    }
    words[*word_index] = encode_span_count(pin_words.len())?;
    *word_index += 1;
    let packed_words = packed_pin_word_count(pin_words.len());
    // The state machine autopulls 23-bit pin words from a 32-bit stream. Rust
    // does the bit-packing once up front so the kernel replay loop only pushes
    // opaque transport words into the FIFO.
    pack_pin_words(
        pin_words,
        &mut words[*word_index..*word_index + packed_words],
    )?;
    *word_index += packed_words;
    Ok(())
}

fn pack_pin_words(pin_words: &[u32], packed_words: &mut [u32]) -> Result<(), String> {
    // Pack rebased 23-bit pin words into a dense 32-bit stream once up front so
    // the replay side only does FIFO writes, not bit shuffling.
    if packed_pin_word_count(pin_words.len()) != packed_words.len() {
        return Err(format!(
            "Pi 5 scan expected {} packed transport words for {} pin words but received {}.",
            packed_pin_word_count(pin_words.len()),
            pin_words.len(),
            packed_words.len()
        ));
    }
    packed_words.fill(0);
    let mut bit_buffer = 0_u64;
    let mut buffered_bits = 0_usize;
    let mut packed_index = 0_usize;

    for &pin_word in pin_words {
        // Each logical pin word is only 23 bits wide because the Pi 5 bonnet
        // wiring lives on GPIO 5..27. Packing them densely is the transport win
        // that improved dense-frame throughput as well as sparse scenes.
        bit_buffer |= u64::from(pin_word & PIN_WORD_MASK) << buffered_bits;
        buffered_bits += PIN_WORD_BITS;
        while buffered_bits >= 32 {
            packed_words[packed_index] = bit_buffer as u32;
            packed_index += 1;
            bit_buffer >>= 32;
            buffered_bits -= 32;
        }
    }
    if buffered_bits > 0 {
        packed_words[packed_index] = bit_buffer as u32;
        packed_index += 1;
    }
    if packed_index != packed_words.len() {
        return Err(format!(
            "Pi 5 scan wrote {packed_index} packed words but expected {}.",
            packed_words.len()
        ));
    }
    Ok(())
}

fn merge_identical_plane_groups(
    words: &mut [u32],
    group_lengths: &mut [usize],
    row_pairs: usize,
    pwm_bits: usize,
    words_per_group: usize,
) -> Result<usize, String> {
    // Merge identical shifted payloads across bitplanes for the same row pair,
    // folding their dwell together. This shrinks resident replay size without
    // changing the visible waveform.
    let mut merged_group_count = 0_usize;
    for row_pair in 0..row_pairs {
        let mut retained_group_indices = Vec::with_capacity(pwm_bits);
        for plane_index in 0..pwm_bits {
            let group_index = row_pair
                .checked_mul(pwm_bits)
                .and_then(|base| base.checked_add(plane_index))
                .ok_or_else(|| "Pi 5 scan group index overflowed during merge.".to_string())?;
            if group_lengths[group_index] == 0
                || group_lengths[group_index] == BLANK_RUN_GROUP_WORDS
            {
                continue;
            }
            let mut merged = false;
            // Simple color fields often produce identical shifted payloads on
            // multiple bitplanes. Folding them together preserves the waveform
            // while shrinking the resident payload the kernel has to replay.
            for &retained_group_index in &retained_group_indices {
                if groups_are_mergeable(
                    words,
                    group_lengths,
                    retained_group_index,
                    group_index,
                    words_per_group,
                )? {
                    merge_group_dwell(
                        words,
                        group_lengths,
                        retained_group_index,
                        group_index,
                        words_per_group,
                    )?;
                    group_lengths[group_index] = 0;
                    merged_group_count += 1;
                    merged = true;
                    break;
                }
            }
            if !merged {
                retained_group_indices.push(group_index);
            }
        }
    }
    Ok(merged_group_count)
}

fn groups_are_mergeable(
    words: &[u32],
    group_lengths: &[usize],
    first_group_index: usize,
    second_group_index: usize,
    words_per_group: usize,
) -> Result<bool, String> {
    // Two groups are mergeable only if their span/data payloads match exactly
    // and only dwell differs. The final dwell word itself is excluded from the
    // bytewise comparison.
    if group_lengths[first_group_index] != group_lengths[second_group_index] {
        return Ok(false);
    }
    let group_length = group_lengths[first_group_index];
    if group_length == 0 || group_length == BLANK_RUN_GROUP_WORDS {
        return Ok(false);
    }
    let first_start = first_group_index
        .checked_mul(words_per_group)
        .ok_or_else(|| "Pi 5 scan first merge offset overflowed.".to_string())?;
    let second_start = second_group_index
        .checked_mul(words_per_group)
        .ok_or_else(|| "Pi 5 scan second merge offset overflowed.".to_string())?;
    Ok(words[first_start..first_start + group_length - 1]
        == words[second_start..second_start + group_length - 1])
}

fn merge_group_dwell(
    words: &mut [u32],
    group_lengths: &[usize],
    retained_group_index: usize,
    merged_group_index: usize,
    words_per_group: usize,
) -> Result<(), String> {
    // Accumulate the merged group's dwell into the retained group's trailer so
    // the visible on-time stays unchanged after compaction.
    let retained_group_length = group_lengths[retained_group_index];
    let merged_group_length = group_lengths[merged_group_index];
    let retained_dwell_index = retained_group_index
        .checked_mul(words_per_group)
        .and_then(|start| start.checked_add(retained_group_length - 1))
        .ok_or_else(|| "Pi 5 scan retained dwell offset overflowed.".to_string())?;
    let merged_dwell_index = merged_group_index
        .checked_mul(words_per_group)
        .and_then(|start| start.checked_add(merged_group_length - 1))
        .ok_or_else(|| "Pi 5 scan merged dwell offset overflowed.".to_string())?;
    let merged_ticks = decode_dwell_counter(words[retained_dwell_index])
        .checked_add(decode_dwell_counter(words[merged_dwell_index]))
        .ok_or_else(|| "Pi 5 scan merged dwell ticks overflowed.".to_string())?;
    words[retained_dwell_index] = encode_dwell_counter(merged_ticks);
    Ok(())
}

fn compact_group_words(
    words: Vec<u32>,
    group_lengths: &[usize],
    words_per_group: usize,
) -> Result<Vec<u32>, String> {
    // Collapse the fixed-size scratch buffer down to the exact resident replay
    // payload after blank-group removal and identical-plane merging.
    if group_lengths
        .iter()
        .all(|&group_length| group_length == words_per_group)
    {
        return Ok(words);
    }

    let retained_non_blank_group_count = group_lengths
        .iter()
        .copied()
        .filter(|&group_length| group_length != 0 && group_length != BLANK_RUN_GROUP_WORDS)
        .count();
    let actual_word_count = if retained_non_blank_group_count == 0 {
        BLANK_RUN_GROUP_WORDS
    } else {
        group_lengths
            .iter()
            .copied()
            .filter(|&group_length| group_length != 0 && group_length != BLANK_RUN_GROUP_WORDS)
            .sum()
    };
    let mut compacted = Vec::with_capacity(actual_word_count);
    for (group_index, group_length) in group_lengths.iter().copied().enumerate() {
        if group_length == 0 {
            continue;
        }
        if group_length == BLANK_RUN_GROUP_WORDS && retained_non_blank_group_count != 0 {
            continue;
        }
        let start = group_index
            .checked_mul(words_per_group)
            .ok_or_else(|| "Pi 5 scan group offset overflowed during compaction.".to_string())?;
        compacted.extend_from_slice(&words[start..start + group_length]);
        if retained_non_blank_group_count == 0 {
            break;
        }
    }
    Ok(compacted)
}

pub(crate) fn encode_span_count(pixel_count: usize) -> Result<u32, String> {
    // The transport uses zero as the blank sentinel, so data spans encode their
    // length as a positive control word.
    if pixel_count == 0 {
        return Err("Pi 5 scan spans must contain at least one pixel.".to_string());
    }
    u32::try_from(pixel_count)
        .map_err(|_| "Pi 5 scan span count exceeds 32-bit control words.".to_string())
}

pub(crate) fn encode_dwell_counter(ticks: u32) -> u32 {
    // The trailer stores dwell as "ticks - 1" so zero still represents one
    // cycle of visible output.
    ticks.saturating_sub(1)
}

pub(crate) fn decode_dwell_counter(encoded_ticks: u32) -> u32 {
    // Inverse of `encode_dwell_counter()` used when merging identical groups.
    encoded_ticks.saturating_add(1)
}

fn scan_pixel_bits(
    rgba: &[u8],
    pinout: Pi5ScanPinout,
    width: usize,
    row_pair: usize,
    row_pairs: usize,
    column: usize,
    shift: usize,
    pwm_bits: u8,
) -> u32 {
    // Convert one top/bottom pixel pair into the rebased six-RGB-bit word for
    // a single bitplane and column.
    let upper_pixel = pixel_channels(rgba, width, row_pair, column);
    let lower_pixel = pixel_channels(rgba, width, row_pair + row_pairs, column);
    let mut bits = 0_u32;
    if channel_plane_is_set(upper_pixel[0], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[0]) - PIN_WORD_SHIFT);
    }
    if channel_plane_is_set(upper_pixel[1], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[1]) - PIN_WORD_SHIFT);
    }
    if channel_plane_is_set(upper_pixel[2], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[2]) - PIN_WORD_SHIFT);
    }
    if channel_plane_is_set(lower_pixel[0], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[3]) - PIN_WORD_SHIFT);
    }
    if channel_plane_is_set(lower_pixel[1], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[4]) - PIN_WORD_SHIFT);
    }
    if channel_plane_is_set(lower_pixel[2], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[5]) - PIN_WORD_SHIFT);
    }
    bits
}

fn pixel_channels(rgba: &[u8], width: usize, row: usize, column: usize) -> [u8; 3] {
    // Read RGB bytes from the packed RGBA frame without allocating or reshaping
    // the source image first.
    let offset = ((row * width) + column) * 4;
    [rgba[offset], rgba[offset + 1], rgba[offset + 2]]
}

fn channel_plane_is_set(value: u8, shift: usize, pwm_bits: u8) -> bool {
    // Test the requested PWM bit after the 8-bit source channel has been
    // expanded or truncated to the configured PWM depth.
    let expanded = expand_channel_to_pwm_bits(value, pwm_bits);
    (expanded & (1_u16 << shift)) != 0
}

fn expand_channel_to_pwm_bits(value: u8, pwm_bits: u8) -> u16 {
    // Normalize 8-bit image channels into the configured PWM width so the rest
    // of the packer can treat every bitplane uniformly.
    if pwm_bits <= 8 {
        u16::from(value >> (8 - pwm_bits))
    } else {
        u16::from(value) << (pwm_bits - 8).min(8)
    }
}

fn read_error_buffer(buffer: &[c_char]) -> Option<String> {
    // Native shims report errors through fixed C buffers. Convert that into the
    // normal Rust `String` path while tolerating empty buffers.
    let length = buffer
        .iter()
        .position(|&byte| byte == 0)
        .unwrap_or(buffer.len());
    if length == 0 {
        return None;
    }
    let bytes: Vec<u8> = buffer[..length].iter().map(|byte| *byte as u8).collect();
    Some(String::from_utf8_lossy(&bytes).into_owned())
}

impl Pi5ScanConfig {
    // Estimate the worst-case packed word count for one logical width. The
    // transports use this to size DMA buffers and resident storage up front.
    pub(crate) fn estimated_word_count_for_width(&self, width: usize) -> Result<usize, String> {
        let row_pairs = self.row_pairs()?;
        row_pairs
            .checked_mul(usize::from(self.pwm_bits))
            .and_then(|group_count| group_count.checked_mul(max_group_word_count(width)))
            .ok_or_else(|| "Pi 5 scan word count overflowed.".to_string())
    }

    // Convenience wrapper over `estimated_word_count_for_width()` using the
    // config's validated logical width.
    pub(crate) fn estimated_word_count(&self) -> Result<usize, String> {
        let width = usize::try_from(self.width()?)
            .map_err(|_| "Pi 5 scan width exceeds host usize.".to_string())?;
        self.estimated_word_count_for_width(width)
    }
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
#[link(name = "heart_pi5_pio_scan_shim", kind = "static")]
unsafe extern "C" {
    // Raw rp1-pio userspace transport entrypoints. These operate on one
    // synchronous submit/wait cycle at a time; the Rust worker above provides
    // the higher-level async semantics.
    fn heart_pi5_pio_scan_open(
        oe_gpio: u32,
        lat_gpio: u32,
        clock_gpio: u32,
        clock_divider: f32,
        post_addr_ticks: u32,
        latch_ticks: u32,
        post_latch_ticks: u32,
        dma_buffer_size: u32,
        dma_buffer_count: u32,
        out_handle: *mut *mut ffi::HeartPi5PioScanHandle,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_pio_scan_submit(
        handle: *mut ffi::HeartPi5PioScanHandle,
        data: *const u8,
        data_bytes: u32,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_pio_scan_wait(
        handle: *mut ffi::HeartPi5PioScanHandle,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_pio_scan_close(handle: *mut ffi::HeartPi5PioScanHandle);
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
#[link(name = "heart_pi5_scan_loop_shim", kind = "static")]
unsafe extern "C" {
    // Resident-loop transport entrypoints backed by the kernel module. The
    // kernel owns continuous replay once `start` succeeds; userspace mostly
    // loads frames, waits, and samples counters.
    fn heart_pi5_scan_loop_open(
        frame_bytes: u32,
        out_handle: *mut *mut ffi::HeartPi5KernelResidentLoopHandle,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_scan_loop_load(
        handle: *mut ffi::HeartPi5KernelResidentLoopHandle,
        data: *const u8,
        data_bytes: u32,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_scan_loop_start(
        handle: *mut ffi::HeartPi5KernelResidentLoopHandle,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_scan_loop_stop(
        handle: *mut ffi::HeartPi5KernelResidentLoopHandle,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_scan_loop_wait_presentations(
        handle: *mut ffi::HeartPi5KernelResidentLoopHandle,
        target_presentations: u64,
        completed_presentations: *mut u64,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_scan_loop_stats(
        handle: *mut ffi::HeartPi5KernelResidentLoopHandle,
        presentations: *mut u64,
        last_error: *mut i32,
        replay_enabled: *mut u32,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_scan_loop_close(handle: *mut ffi::HeartPi5KernelResidentLoopHandle);
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
#[link(name = "pio")]
unsafe extern "C" {}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
mod ffi {
    #[repr(C)]
    pub(crate) struct HeartPi5PioScanHandle {
        _private: [u8; 0],
    }

    #[repr(C)]
    pub(crate) struct HeartPi5KernelResidentLoopHandle {
        _private: [u8; 0],
    }
}
