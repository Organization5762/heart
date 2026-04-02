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
const LEGACY_OE_SYNC_GPIO: u32 = 4;
const PIO_ERROR_BUFFER_BYTES: usize = 256;
const PI5_SCAN_UNSUPPORTED_MESSAGE: &str =
    "Pi 5 scan transport is only supported on Linux aarch64 builds.";
// The optimized parser still rebases GPIO 5..27 into a dense 23-bit stream.
// The simple host-driven transport now mirrors Piomatter and writes literal
// GPIO words in the real GPIO0..27 space.
const OPTIMIZED_PIN_WORD_SHIFT: u32 = 5;
const SIMPLE_PIN_WORD_SHIFT: u32 = 0;
// Optimized packed group format, in transport-word order:
//   0: row-addressed blank word with OE forced inactive
//   repeated:
//     raw control word         => one-word raw span header:
//                                  bit 0      = 0
//                                  bits 1..8  = raw_len - 1
//                                  bits 9..31 = first 23-bit pin word
//                                  remaining pin words follow in packed form
//     repeat control word      => one-word repeat span:
//                                  bit 0      = 1
//                                  bits 1..8  = repeat_len - 1
//                                  bits 9..31 = repeated 23-bit pin word
//   0                          => end-of-spans marker
//   active_display_word        => row address with OE driven active
//   dwell_counter
//
// Simple packed group format, in transport-word order:
//   0: delay command for blank/address settle
//   1: blank/address GPIO word (OE inactive, LAT low)
//   2: data command for the row's column count
//   3..: one literal GPIO word per logical column
//   n-6: delay command for the latch-high phase
//   n-5: latch-high GPIO word (OE inactive, LAT high)
//   n-4: delay command for the post-latch blank phase
//   n-3: post-latch GPIO word (OE inactive, LAT low)
//   n-2: delay command for the visible dwell phase
//   n-1: active/address GPIO word (OE active, LAT low)
//
// Commands mirror Piomatter exactly:
//   - bit 31      => data (1) vs delay (0)
//   - bits 0..30  => logical_count - 1
//
// The PIO program consumes this as a continuous 32-bit autopull stream and
// interprets only two operations: shift `N` literal GPIO words with clock
// pulses, or hold one literal GPIO word for `N` cycles.
const END_OF_SPANS_MARKER: u32 = 0;
const OPTIMIZED_PIN_WORD_BITS: usize = 23;
const OPTIMIZED_PIN_WORD_MASK: u32 = (1_u32 << OPTIMIZED_PIN_WORD_BITS) - 1;
const SPAN_LEN_BITS: usize = 8;
const RAW_SPAN_MAX_PIXELS: usize = 1 << SPAN_LEN_BITS;
const REPEAT_SPAN_MAX_PIXELS: usize = 1 << SPAN_LEN_BITS;
const SPAN_WORD_SHIFT: usize = 1 + SPAN_LEN_BITS;
const SIMPLE_GROUP_FIXED_WORDS: usize = 9;
pub(crate) const SIMPLE_COMMAND_DATA_BIT: u32 = 1_u32 << 31;
pub(crate) const SIMPLE_COMMAND_COUNT_MASK: u32 = !SIMPLE_COMMAND_DATA_BIT;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum SimpleCommandKind {
    Delay,
    Data,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Pi5ScanFormat {
    Optimized,
    Simple,
}

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
    format: Pi5ScanFormat,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Pi5ScanTiming {
    pub(crate) clock_divider: f32,
    pub(crate) post_addr_ticks: u32,
    pub(crate) latch_ticks: u32,
    pub(crate) post_latch_ticks: u32,
    pub(crate) simple_clock_hold_ticks: u32,
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
            simple_clock_hold_ticks: 1,
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
        let tuning = runtime_tuning();
        let config = Self {
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            pwm_bits: tuning.pi5_scan_default_pwm_bits,
            lsb_dwell_ticks: tuning.pi5_scan_lsb_dwell_ticks,
            timing: Pi5ScanTiming {
                clock_divider: tuning.pi5_scan_clock_divider,
                post_addr_ticks: tuning.pi5_scan_post_addr_ticks,
                latch_ticks: tuning.pi5_scan_latch_ticks,
                post_latch_ticks: tuning.pi5_scan_post_latch_ticks,
                simple_clock_hold_ticks: tuning.pi5_scan_simple_clock_hold_ticks,
            },
            pinout,
            format: Pi5ScanFormat::Optimized,
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

    // Keep the packing format explicit so hardware bring-up can select a
    // simpler, less optimized transport without mutating the higher-level
    // matrix configuration shape.
    pub(crate) fn with_format(mut self, format: Pi5ScanFormat) -> Result<Self, String> {
        self.format = format;
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

    pub(crate) fn format(&self) -> Pi5ScanFormat {
        self.format
    }

    pub(crate) fn pin_word_shift(&self) -> u32 {
        match self.format {
            Pi5ScanFormat::Optimized => OPTIMIZED_PIN_WORD_SHIFT,
            Pi5ScanFormat::Simple => SIMPLE_PIN_WORD_SHIFT,
        }
    }

    pub(crate) fn debug_expected_group_trace(
        &self,
        rgba: &[u8],
        row_pair: usize,
        plane_index: usize,
    ) -> Result<Pi5ScanGroupTrace, String> {
        let width = self.width()? as usize;
        let row_pairs = self.row_pairs()?;
        let control = build_scan_segment_control(self, row_pair, plane_index)?;
        let shift_words = collect_scan_pin_words(
            self,
            rgba,
            width,
            row_pairs,
            row_pair,
            control.pinout,
            control.blank_word,
            control.msb_first_shift,
        );
        Ok(Pi5ScanGroupTrace {
            blank_word: control.blank_word,
            shift_words,
            active_word: control.active_word,
            dwell_ticks: control.dwell_ticks,
        })
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
        if self.timing.post_addr_ticks == 0 || self.timing.post_addr_ticks > 32 {
            return Err("post_addr_ticks must be in the range 1..32.".to_string());
        }
        if self.timing.latch_ticks == 0 || self.timing.latch_ticks > 32 {
            return Err("latch_ticks must be in the range 1..32.".to_string());
        }
        if self.timing.post_latch_ticks == 0 || self.timing.post_latch_ticks > 32 {
            return Err("post_latch_ticks must be in the range 1..32.".to_string());
        }
        if self.timing.simple_clock_hold_ticks == 0 || self.timing.simple_clock_hold_ticks > 32 {
            return Err("simple_clock_hold_ticks must be in the range 1..32.".to_string());
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

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct Pi5ScanGroupTrace {
    pub(crate) blank_word: u32,
    pub(crate) shift_words: Vec<u32>,
    pub(crate) active_word: u32,
    pub(crate) dwell_ticks: u32,
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
        let words_per_group = max_group_word_count_for_config(config, width);
        let total_words = config.estimated_word_count_for_width(width)?;
        let pack_start = Instant::now();
        let mut words = vec![0_u32; total_words];
        let mut group_lengths = vec![0_usize; group_count];

        match config.format() {
            Pi5ScanFormat::Optimized => {
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
                    .enumerate()
                    .filter(|(group_index, group_length)| {
                        scan_group_is_blank_run(
                            &words,
                            words_per_group,
                            *group_index,
                            **group_length,
                        )
                    })
                    .count();
                let words = compact_group_words(words, &group_lengths, words_per_group)?;
                let word_count = words.len();
                let pack_duration = pack_start.elapsed();
                return Ok((
                    Self { words },
                    PackedScanFrameStats {
                        compressed_blank_groups,
                        merged_identical_groups,
                        word_count,
                        pack_duration,
                    },
                ));
            }
            Pi5ScanFormat::Simple => {
                for (group_index, (segment, group_length)) in words
                    .chunks_mut(words_per_group)
                    .zip(group_lengths.iter_mut())
                    .enumerate()
                {
                    let row_pair = group_index / usize::from(config.pwm_bits);
                    let plane_index = group_index % usize::from(config.pwm_bits);
                    let exact_group_words = simple_group_word_count(width);
                    *group_length = write_scan_segment_simple(
                        &mut segment[..exact_group_words],
                        config,
                        rgba,
                        width,
                        row_pairs,
                        row_pair,
                        plane_index,
                    )?;
                }
                let words = compact_group_words_simple(words, &group_lengths, words_per_group)?;
                let word_count = words.len();
                let pack_duration = pack_start.elapsed();
                return Ok((
                    Self { words },
                    PackedScanFrameStats {
                        compressed_blank_groups: 0,
                        merged_identical_groups: 0,
                        word_count,
                        pack_duration,
                    },
                ));
            }
        }
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

    // Construct a packed frame directly from already-audited transport words.
    // This is reserved for bring-up probes that want to bypass the normal RGBA
    // packer and drive the raw Pi 5 transport with a hand-built word stream.
    pub(crate) fn from_words(words: Vec<u32>) -> Self {
        Self { words }
    }

    // Duplicate one already-packed frame back-to-back in transport order.
    // This is the simplest way to build a larger FIFO burst without changing
    // the live PIO contract: the state machine just consumes the same frame
    // several times before userspace decides whether to resend or replace it.
    pub(crate) fn repeated(&self, copies: usize) -> Result<Self, String> {
        if copies == 0 {
            return Err("Packed scan frame repetition requires at least one copy.".to_string());
        }
        let total_words = self
            .words
            .len()
            .checked_mul(copies)
            .ok_or_else(|| "Packed scan frame repetition overflowed the word count.".to_string())?;
        let mut words = Vec::with_capacity(total_words);
        for _ in 0..copies {
            words.extend_from_slice(&self.words);
        }
        Ok(Self { words })
    }

    pub(crate) fn debug_decode_group_trace(
        &self,
        config: &Pi5ScanConfig,
        row_pair: usize,
        plane_index: usize,
    ) -> Result<Pi5ScanGroupTrace, String> {
        match config.format() {
            Pi5ScanFormat::Optimized => {
                let group_index = row_pair
                    .checked_mul(usize::from(config.pwm_bits))
                    .and_then(|index| index.checked_add(plane_index))
                    .ok_or_else(|| "Pi 5 trace group index overflowed.".to_string())?;
                let mut word_index = 0_usize;
                for current_group in 0..=group_index {
                    let (trace, next_index) =
                        decode_group_trace_from_optimized_words(self.as_words(), word_index)?;
                    if current_group == group_index {
                        return Ok(trace);
                    }
                    word_index = next_index;
                }
                Err(format!(
                    "Pi 5 packed frame does not contain group index {group_index}."
                ))
            }
            Pi5ScanFormat::Simple => {
                decode_group_trace_from_simple_words(self.as_words(), config, row_pair, plane_index)
            }
        }
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

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
unsafe impl Send for Pi5KernelResidentLoop {}

#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Pi5KernelResidentLoopStats {
    // Kernel-owned presentation count since the current replay epoch.
    pub(crate) presentations: u64,
    // Sticky worker failure, reported as a negative errno-style value.
    pub(crate) last_error: i32,
    // Whether replay is currently enabled for this resident session.
    pub(crate) replay_enabled: bool,
    // Number of replay batches that reached the completion primitive.
    pub(crate) batches_submitted: u64,
    // Total transport words written into the RP1 FIFO for this replay epoch.
    pub(crate) words_written: u64,
    // Number of times the worker observed a drain failure.
    pub(crate) drain_failures: u64,
    // Number of batches interrupted early by STOP/disable requests.
    pub(crate) stop_requests_seen_during_batch: u64,
    // Cumulative nanoseconds spent issuing the MMIO burst.
    pub(crate) mmio_write_ns: u64,
    // Cumulative nanoseconds spent in the drain completion primitive.
    pub(crate) drain_ns: u64,
    // Largest replay batch count the worker actually completed.
    pub(crate) max_batch_replays: u32,
    // CPU the kernel bound the replay worker to.
    pub(crate) worker_cpu: u32,
    // RT priority requested for the replay worker.
    pub(crate) worker_priority: u32,
    // Whether the worker currently has enough state to enter a replay batch.
    pub(crate) worker_runnable: bool,
}

impl Pi5KernelResidentLoopStats {
    // presentation_count() is only a meaningful health signal while the kernel
    // worker is healthy. Once the worker reports a sticky errno-style failure,
    // callers must surface that error instead of quietly treating the counter as
    // authoritative.
    pub(crate) fn presentation_count_result(&self) -> Result<u64, String> {
        if self.last_error != 0 {
            return Err(format!(
                "Resident scan loop worker failed with code {}.",
                self.last_error
            ));
        }
        Ok(self.presentations)
    }
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

    // Query the current resident-loop counters without waiting. STATS is a
    // read-only snapshot; callers that need a frame boundary still use WAIT.
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    pub(crate) fn stats(&self) -> Result<Pi5KernelResidentLoopStats, String> {
        let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
        let mut stats = Pi5KernelResidentLoopStats::default();
        let mut replay_enabled = 0_u32;
        let mut worker_runnable = 0_u32;
        let result = unsafe {
            heart_pi5_scan_loop_stats(
                self.handle.0,
                &mut stats.presentations,
                &mut stats.last_error,
                &mut replay_enabled,
                &mut stats.batches_submitted,
                &mut stats.words_written,
                &mut stats.drain_failures,
                &mut stats.stop_requests_seen_during_batch,
                &mut stats.mmio_write_ns,
                &mut stats.drain_ns,
                &mut stats.max_batch_replays,
                &mut stats.worker_cpu,
                &mut stats.worker_priority,
                &mut worker_runnable,
                error_buffer.as_mut_ptr(),
                error_buffer.len(),
            )
        };
        if result != 0 {
            return Err(read_error_buffer(&error_buffer).unwrap_or_else(|| {
                format!("Resident scan loop stats failed with code {result}.")
            }));
        }
        stats.replay_enabled = replay_enabled != 0;
        stats.worker_runnable = worker_runnable != 0;
        Ok(stats)
    }

    // Unsupported-platform stub matching the Linux entrypoint above.
    #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
    pub(crate) fn stats(&self) -> Result<Pi5KernelResidentLoopStats, String> {
        Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
    }

    // Query just the presentation counter when the caller only needs refresh
    // progress and not the rest of the kernel telemetry. This still propagates
    // the sticky kernel worker error, because a stale counter is not a valid
    // health signal once the resident loop has failed.
    pub(crate) fn presentation_count(&self) -> Result<u64, String> {
        self.stats()?.presentation_count_result()
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
        _format: Pi5ScanFormat,
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
            let dma_buffer_size =
                u32::try_from(max_transfer_bytes.min(tuning.pi5_scan_max_dma_buffer_bytes))
                    .map_err(|_| {
                        "Pi 5 scan transport buffer exceeds 32-bit DMA limits.".to_string()
                    })?;
            let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
            let mut handle: *mut ffi::HeartPi5PioScanHandle = std::ptr::null_mut();
            let result = unsafe {
                heart_pi5_pio_scan_open(
                    pinout.oe_gpio,
                    pinout.lat_gpio,
                    pinout.clock_gpio,
                    timing.clock_divider,
                    timing.simple_clock_hold_ticks,
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
            let repeat_pause = tuning.pi5_scan_resident_loop_resubmit_pause;
            let worker = spawn_scan_transport_worker(
                handle,
                Arc::clone(&shared),
                Arc::clone(&hardware_lock),
                repeat_pause,
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
            let _ = _format;
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

    // Bypass the async queue and drive one synchronous submit/wait cycle
    // directly. This is used only by bring-up smoke tools where we want to
    // test the raw RP1 PIO path without any higher-level scheduling behavior.
    pub(crate) fn submit_blocking(&self, frame: &PackedScanFrame) -> Result<(), String> {
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
            if state.closed {
                return Err("Pi 5 scan transport is already closed.".to_string());
            }
            drop(state);

            let _hardware_guard = self
                .hardware_lock
                .lock()
                .map_err(|_| "Pi 5 scan hardware lock poisoned.".to_string())?;
            submit_scan_frame(self.handle, frame)?;
            wait_for_scan_completion(self.handle)
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
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
    repeat_pause: Duration,
) -> Result<JoinHandle<()>, String> {
    // Name the thread because this transport frequently shows up in profiles,
    // crash logs, and shutdown diagnostics when tuning scanout behavior.
    thread::Builder::new()
        .name("heart-pi5-scan-transport".to_string())
        .spawn(move || run_scan_transport_worker(handle, shared, hardware_lock, repeat_pause))
        .map_err(|error| error.to_string())
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
fn run_scan_transport_worker(
    handle: Pi5PioScanHandle,
    shared: Arc<Pi5PioScanAsyncShared>,
    hardware_lock: Arc<Mutex<()>>,
    repeat_pause: Duration,
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
            let (frame, frame_identity, is_resident_repeat) =
                if let Some(frame) = state.pending_frame.take() {
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

        if is_resident_repeat && !repeat_pause.is_zero() {
            // Give the resident-loop path a short breather so repeated refreshes
            // do not starve the producer side when the displayed frame is static.
            thread::sleep(repeat_pause);
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
    fn address_bits(&self, row_pair: usize, pin_word_shift: u32) -> u32 {
        let mut bits = 0_u32;
        for (bit_index, gpio) in self.addr_gpios.iter().enumerate() {
            if (row_pair & (1 << bit_index)) != 0 {
                bits |= 1_u32 << (u32::from(*gpio) - pin_word_shift);
            }
        }
        bits
    }

    // The packed stream owns OE directly. Shift-time and latch-time words keep
    // OE inactive so the panel stays blank while row address and RGB data are
    // changing, then the final active word drops OE for the dwell phase.
    fn oe_inactive_bits(&self, pin_word_shift: u32) -> u32 {
        let mut bits = 0_u32;
        if OE_ACTIVE_LOW {
            bits |= 1_u32 << (self.oe_gpio - pin_word_shift);
            if self.oe_gpio == 18_u32 && LEGACY_OE_SYNC_GPIO >= pin_word_shift {
                bits |= 1_u32 << (LEGACY_OE_SYNC_GPIO - pin_word_shift);
            }
        }
        bits
    }

    fn oe_active_bits(&self, _pin_word_shift: u32) -> u32 {
        0
    }

    fn lat_bits(&self, pin_word_shift: u32) -> u32 {
        1_u32 << (self.lat_gpio - pin_word_shift)
    }

    // Keep the default dwell policy alongside the pin mapping because the
    // supported bonnet layouts are the place where panel-level timing defaults
    // are chosen today.
    fn default_lsb_dwell_ticks(&self) -> u32 {
        2
    }

    pub(crate) fn oe_gpio(&self) -> u32 {
        self.oe_gpio
    }

    pub(crate) fn rgb_gpios(&self) -> [u8; 6] {
        self.rgb_gpios
    }

    pub(crate) fn addr_gpios(&self) -> [u8; 5] {
        self.addr_gpios
    }

    pub(crate) fn lat_gpio(&self) -> u32 {
        self.lat_gpio
    }

    pub(crate) fn clock_gpio(&self) -> u32 {
        self.clock_gpio
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
    //
    // The hot-path shape is deliberate:
    //   1. build the one control bundle shared by the whole group
    //   2. materialize one flat per-column pin-word vector
    //   3. detect the all-blank fast path immediately
    //   4. plan the cheapest raw/repeat segmentation over that vector
    //   5. serialize the chosen spans once into the output scratch buffer
    //
    // Keeping those stages explicit makes performance tuning auditable. Each
    // stage answers one question only:
    //   - what should the per-column GPIO state be?
    //   - how should it be segmented for minimum transport words?
    //   - how should that segmentation be encoded?
    //
    // That separation matters because dense-frame throughput has been won and
    // lost here before by "small" format tweaks that changed total words more
    // than they changed CPU time.
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

    let planned_spans = plan_scan_segment_spans(&pin_words)?;
    let mut word_index = emit_planned_scan_spans(words, &pin_words, &planned_spans)?;
    word_index = write_scan_segment_trailer(words, word_index, control);
    Ok(word_index)
}

fn write_scan_segment_simple(
    words: &mut [u32],
    config: &Pi5ScanConfig,
    rgba: &[u8],
    width: usize,
    row_pairs: usize,
    row_pair: usize,
    plane_index: usize,
) -> Result<usize, String> {
    // The simple format now mirrors the working Piomatter-style contract:
    //   - delay command + blank/address word
    //   - data/repeat commands + RGB/address shift words
    //   - delay command + latch-high word
    //   - delay command + post-latch blank word
    //   - delay command + active/address word
    //
    // Literal GPIO words span the synthetic GPIO4..27 window. They keep CLK
    // low in-band, carry LAT/OE directly, and leave unused pins at zero.
    if row_pair >= row_pairs {
        return Err(format!(
            "Row pair {row_pair} exceeds the configured row pair count {row_pairs}."
        ));
    }
    let expected_words = simple_group_word_count(width);
    if words.len() != expected_words {
        return Err(format!(
            "Pi 5 scan segment expected {} words but received {}.",
            expected_words,
            words.len()
        ));
    }

    let control = build_scan_segment_control(config, row_pair, plane_index)?;
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
    let latch_high_word = control.blank_word | control.pinout.lat_bits(config.pin_word_shift());
    let post_latch_word = control.blank_word;

    let mut word_index = 0_usize;
    words[word_index] = encode_simple_delay_command(config.timing().post_addr_ticks)?;
    word_index += 1;
    words[word_index] = control.blank_word;
    word_index += 1;
    word_index = emit_simple_shift_commands(words, word_index, &pin_words)?;
    words[word_index] = encode_simple_delay_command(config.timing().latch_ticks)?;
    word_index += 1;
    words[word_index] = latch_high_word;
    word_index += 1;
    words[word_index] = encode_simple_delay_command(config.timing().post_latch_ticks)?;
    word_index += 1;
    words[word_index] = post_latch_word;
    word_index += 1;
    words[word_index] = encode_simple_delay_command(control.dwell_ticks)?;
    word_index += 1;
    words[word_index] = control.active_word;
    word_index += 1;
    Ok(word_index)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct SimpleShiftSegment {
    start: usize,
    end: usize,
}

fn plan_simple_shift_segments(pin_words: &[u32]) -> Result<Vec<SimpleShiftSegment>, String> {
    if pin_words.is_empty() {
        return Ok(Vec::new());
    }

    // Return to the last known-good simple path: one literal data command per
    // row. Repeat compression looked correct in simulation but introduced
    // visible hardware artifacts and submit instability during bring-up, so
    // disable it entirely until the live RP1 path is stable again.
    Ok(vec![SimpleShiftSegment {
        start: 0,
        end: pin_words.len(),
    }])
}

fn emit_simple_shift_commands(
    words: &mut [u32],
    mut word_index: usize,
    pin_words: &[u32],
) -> Result<usize, String> {
    let planned_segments = plan_simple_shift_segments(pin_words)?;

    for segment in planned_segments {
        let segment_words = &pin_words[segment.start..segment.end];
        words[word_index] = encode_simple_data_command(segment_words.len())?;
        word_index += 1;
        words[word_index..word_index + segment_words.len()].copy_from_slice(segment_words);
        word_index += segment_words.len();
    }

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

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum PlannedScanSpanKind {
    Raw,
    Repeat,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct PlannedScanSpan {
    start: usize,
    end: usize,
    kind: PlannedScanSpanKind,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct PinWordRun {
    start: usize,
    end: usize,
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
    let pin_word_shift = config.pin_word_shift();
    let addr_bits = pinout.address_bits(row_pair, pin_word_shift);
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
        blank_word: addr_bits | pinout.oe_inactive_bits(pin_word_shift),
        active_word: addr_bits | pinout.oe_active_bits(pin_word_shift),
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
                    config.pin_word_shift(),
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
    // lights a pixel. The parser now understands generic repeat spans, so the
    // all-blank fast path is just one repeat span of the group blank word.
    let mut word_index = 1_usize;
    emit_repeat_run(words, &mut word_index, width, control.blank_word)?;
    word_index = write_scan_segment_trailer(words, word_index, control);
    Ok(word_index)
}

fn plan_scan_segment_spans(pin_words: &[u32]) -> Result<Vec<PlannedScanSpan>, String> {
    // Choose the minimum-word span segmentation under the current parser
    // contract using run boundaries instead of per-column heuristics.
    //
    // The repeat-span opcode changes the tradeoff: long constant runs no longer
    // have to ride inside a raw packed span. Planning over exact runs gives the
    // packer the ability to decide when one repeated pin word is cheaper than a
    // raw packed payload, while still keeping pack-time work bounded by the
    // number of runs rather than the full row width squared.
    let runs = collect_pin_word_runs(pin_words);
    let run_count = runs.len();
    let mut best_suffix_words = vec![usize::MAX; run_count + 1];
    let mut planned_end_run = vec![0_usize; run_count];
    let mut planned_kind = vec![PlannedScanSpanKind::Raw; run_count];

    // Dynamic programming over runs, not pixels:
    //   best_suffix_words[i] = minimum transport words needed to encode
    //   runs[i..]
    //
    // This is the key pack-time compromise. Searching over every pixel
    // boundary would give the same optimality but is needlessly expensive for
    // wide rows. Searching over already-coalesced runs keeps the state space
    // bounded by "number of actual value changes in this group", which is the
    // quantity that matters for repeat-span opportunities.
    best_suffix_words[run_count] = 0;
    for start_run in (0..run_count).rev() {
        let mut best_words = usize::MAX;
        let mut best_end_run = start_run + 1;
        let mut best_kind = PlannedScanSpanKind::Raw;
        let repeat_len = runs[start_run].end - runs[start_run].start;

        if repeat_len >= 2 {
            let repeat_words = repeat_span_word_count(repeat_len)
                .checked_add(best_suffix_words[start_run + 1])
                .ok_or_else(|| "Pi 5 scan repeat span planning overflowed.".to_string())?;
            best_words = repeat_words;
            best_end_run = start_run + 1;
            best_kind = PlannedScanSpanKind::Repeat;
        }

        let mut raw_len = 0_usize;
        for end_run in start_run..run_count {
            raw_len = raw_len
                .checked_add(runs[end_run].end - runs[end_run].start)
                .ok_or_else(|| "Pi 5 scan raw span length overflowed.".to_string())?;
            // A raw span pays:
            //   1 control word carrying opcode/len/first pin word
            //   packed transport words for the remaining pin words
            // plus the optimal suffix after this candidate span.
            //
            // This exact word accounting is what lets the planner justify
            // seemingly counterintuitive choices such as "keep a short repeat
            // run inside a larger raw span" when the extra span header would
            // cost more than it saves.
            let raw_words = 1_usize
                .checked_add(packed_pin_word_count(raw_len))
                .and_then(|words| words.checked_add(best_suffix_words[end_run + 1]))
                .ok_or_else(|| "Pi 5 scan raw span planning overflowed.".to_string())?;
            if raw_words < best_words {
                best_words = raw_words;
                best_end_run = end_run + 1;
                best_kind = PlannedScanSpanKind::Raw;
            }
        }

        best_suffix_words[start_run] = best_words;
        planned_end_run[start_run] = best_end_run;
        planned_kind[start_run] = best_kind;
    }

    let mut spans = Vec::new();
    let mut start_run = 0_usize;
    while start_run < run_count {
        let end_run = planned_end_run[start_run];
        if end_run <= start_run || end_run > run_count {
            return Err(
                "Pi 5 scan run-span planner produced an invalid span boundary.".to_string(),
            );
        }
        spans.push(PlannedScanSpan {
            start: runs[start_run].start,
            end: runs[end_run - 1].end,
            kind: planned_kind[start_run],
        });
        start_run = end_run;
    }
    Ok(spans)
}

fn emit_planned_scan_spans(
    words: &mut [u32],
    pin_words: &[u32],
    planned_spans: &[PlannedScanSpan],
) -> Result<usize, String> {
    // The planner above decides the cheapest sequence of raw and repeat spans.
    // This helper just serializes that decision into the shared transport
    // format consumed by both native C parsers.
    let mut word_index = 1_usize;
    for span in planned_spans {
        match span.kind {
            PlannedScanSpanKind::Raw => {
                emit_safe_raw_run(words, &mut word_index, &pin_words[span.start..span.end])?;
            }
            PlannedScanSpanKind::Repeat => {
                emit_repeat_run(
                    words,
                    &mut word_index,
                    span.end - span.start,
                    pin_words[span.start],
                )?;
            }
        }
    }
    Ok(word_index)
}

fn emit_safe_raw_run(
    words: &mut [u32],
    word_index: &mut usize,
    pin_words: &[u32],
) -> Result<(), String> {
    // The parser reserves a zero first pin word as the end-of-spans marker.
    // After removing OE from the packed GPIO stream, a legitimate blank/address
    // word can now be zero for row-pair 0. Preserve the marker invariant by
    // peeling any leading zero run into an explicit repeat span before the raw
    // encoder sees it.
    if pin_words.is_empty() {
        return Ok(());
    }

    let leading_zero_count = pin_words
        .iter()
        .take_while(|&&pin_word| pin_word == 0)
        .count();
    if leading_zero_count > 0 {
        emit_repeat_run(words, word_index, leading_zero_count, 0)?;
    }
    emit_raw_run(words, word_index, &pin_words[leading_zero_count..])
}

#[inline]
fn write_scan_segment_trailer(
    words: &mut [u32],
    word_index: usize,
    control: ScanSegmentControl,
) -> usize {
    // Emit the fixed end-of-spans marker, then explicitly switch the rebased
    // GPIO window from "blanked row address" to "active row address" before
    // loading the dwell counter. This keeps the PIO waveform aligned with the
    // known-good direct GPIO loop: blank -> address -> shift -> latch ->
    // unblank -> dwell.
    words[word_index] = END_OF_SPANS_MARKER;
    words[word_index + 1] = control.active_word;
    words[word_index + 2] = encode_dwell_counter(control.dwell_ticks);
    word_index + 3
}

pub(crate) fn packed_pin_word_count(pin_word_count: usize) -> usize {
    // Convert logical pin words into packed transport words after rebasing the
    // GPIO map to 23 bits.
    pin_word_count
        .checked_mul(OPTIMIZED_PIN_WORD_BITS)
        .and_then(|bits| bits.checked_add(31))
        .map(|bits| bits / 32)
        .unwrap_or(usize::MAX)
}

pub(crate) fn max_group_word_count(width: usize) -> usize {
    // Size the per-group scratch buffer for the worst-case alternating
    // lit/blank/lit/... span pattern so packing never has to realloc.
    // Worst case is alternating one-pixel lit and blank spans across the row.
    // That produces roughly width span headers plus the packed payload words,
    // then the fixed blank-word + terminator + active-word + dwell trailer.
    width
        .checked_mul(2)
        .and_then(|words| words.checked_add(5))
        .unwrap_or(usize::MAX)
}

fn simple_group_word_count(width: usize) -> usize {
    width
        .checked_add(SIMPLE_GROUP_FIXED_WORDS)
        .unwrap_or(usize::MAX)
}

fn encode_simple_count(
    logical_count: u32,
    kind: SimpleCommandKind,
    label: &str,
) -> Result<u32, String> {
    let encoded = logical_count
        .checked_sub(1)
        .ok_or_else(|| format!("Pi 5 simple {label} count must be at least 1."))?;
    if encoded > SIMPLE_COMMAND_COUNT_MASK {
        return Err(format!(
            "Pi 5 simple {label} count exceeds the 31-bit command payload."
        ));
    }
    Ok(match kind {
        SimpleCommandKind::Delay => encoded,
        SimpleCommandKind::Data => SIMPLE_COMMAND_DATA_BIT | encoded,
    })
}

fn encode_simple_data_command(logical_count: usize) -> Result<u32, String> {
    let logical_count = u32::try_from(logical_count)
        .map_err(|_| "Pi 5 simple scan width exceeds 32-bit transport words.".to_string())?;
    encode_simple_count(logical_count, SimpleCommandKind::Data, "data")
}

fn encode_simple_delay_command(ticks: u32) -> Result<u32, String> {
    encode_simple_count(ticks, SimpleCommandKind::Delay, "delay")
}

fn decode_simple_command(command_word: u32) -> Result<(SimpleCommandKind, u32), String> {
    let logical_count = (command_word & SIMPLE_COMMAND_COUNT_MASK)
        .checked_add(1)
        .ok_or_else(|| "Pi 5 simple command count overflowed.".to_string())?;
    let kind = if (command_word & SIMPLE_COMMAND_DATA_BIT) != 0 {
        SimpleCommandKind::Data
    } else {
        SimpleCommandKind::Delay
    };
    Ok((kind, logical_count))
}

fn decode_simple_data_command(command_word: u32) -> Result<usize, String> {
    let (kind, logical_count) = decode_simple_command(command_word)?;
    if kind != SimpleCommandKind::Data {
        return Err(format!(
            "Pi 5 simple command 0x{command_word:08x} was a delay where data was expected."
        ));
    }
    usize::try_from(logical_count)
        .map_err(|_| "Pi 5 simple data command count does not fit host usize.".to_string())
}

fn decode_simple_delay_command(command_word: u32) -> Result<u32, String> {
    let (kind, logical_count) = decode_simple_command(command_word)?;
    if kind != SimpleCommandKind::Delay {
        return Err(format!(
            "Pi 5 simple command 0x{command_word:08x} was data where a delay was expected."
        ));
    }
    Ok(logical_count)
}

fn decode_simple_shift_counter(encoded_width: u32) -> Result<usize, String> {
    decode_simple_data_command(encoded_width)
}

fn max_group_word_count_for_config(config: &Pi5ScanConfig, width: usize) -> usize {
    match config.format() {
        Pi5ScanFormat::Optimized => max_group_word_count(width),
        Pi5ScanFormat::Simple => simple_group_word_count(width),
    }
}

fn repeat_span_word_count(pixel_count: usize) -> usize {
    pixel_count.div_ceil(REPEAT_SPAN_MAX_PIXELS)
}

fn emit_raw_run(
    words: &mut [u32],
    word_index: &mut usize,
    pin_words: &[u32],
) -> Result<(), String> {
    // Encode one raw span by writing its logical length followed by the dense
    // packed pin words consumed by the PIO parser's autopull stream.
    //
    // The first 23-bit pin word now rides inside the control word itself. That
    // saves one transport word for every raw span, which is exactly the dense
    // case that still matters once repeat/blank compression has already landed.
    if pin_words.is_empty() {
        return Ok(());
    }
    words[*word_index] = encode_raw_span_word(pin_words.len(), pin_words[0])?;
    *word_index += 1;
    let packed_words = packed_pin_word_count(pin_words.len() - 1);
    // The first pin word is intentionally inlined into the header. That
    // seemingly small choice matters because dense scenes still emit many raw
    // spans; saving one transport word per raw span was one of the few changes
    // that improved the dense resident-refresh ceiling instead of only helping
    // sparse content.
    // The state machine autopulls 23-bit pin words from a 32-bit stream. Rust
    // does the bit-packing once up front so the kernel replay loop only pushes
    // opaque transport words into the FIFO.
    pack_pin_words(
        &pin_words[1..],
        &mut words[*word_index..*word_index + packed_words],
    )?;
    *word_index += packed_words;
    Ok(())
}

fn emit_repeat_run(
    words: &mut [u32],
    word_index: &mut usize,
    repeat_count: usize,
    repeated_word: u32,
) -> Result<(), String> {
    // Encode one constant run using the dedicated repeat opcode. The repeat
    // control word carries both length and the repeated 23-bit GPIO state, so
    // long constant runs cost one transport word per <=256 columns.
    let mut remaining = repeat_count;
    while remaining > 0 {
        let chunk = remaining.min(REPEAT_SPAN_MAX_PIXELS);
        words[*word_index] = encode_repeat_span_word(chunk, repeated_word)?;
        *word_index += 1;
        remaining -= chunk;
    }
    Ok(())
}

fn collect_pin_word_runs(pin_words: &[u32]) -> Vec<PinWordRun> {
    // Group equal consecutive pin words so the planner can search over the real
    // repeat opportunities instead of every individual column boundary.
    let mut runs = Vec::new();
    if pin_words.is_empty() {
        return runs;
    }

    let mut run_start = 0_usize;
    for index in 1..=pin_words.len() {
        if index < pin_words.len() && pin_words[index] == pin_words[run_start] {
            continue;
        }
        runs.push(PinWordRun {
            start: run_start,
            end: index,
        });
        run_start = index;
    }
    runs
}

fn scan_group_is_blank_run(
    words: &[u32],
    words_per_group: usize,
    group_index: usize,
    group_length: usize,
) -> bool {
    // Group length alone is no longer enough to identify a blank group because
    // repeat spans are variable length and a nonblank group can also compress
    // down to a very small body. A group is blank only if every span word
    // before the terminator is a repeat span of the group's own blank word.
    if group_length < 5 {
        return false;
    }
    let start = match group_index.checked_mul(words_per_group) {
        Some(start) => start,
        None => return false,
    };
    let group_words = &words[start..start + group_length];
    if group_words[group_length - 3] != END_OF_SPANS_MARKER {
        return false;
    }
    group_words[1..group_length - 3]
        .iter()
        .all(|&word| decode_repeat_span_word(word) == Some(group_words[0]))
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
        //
        // The bit-buffer loop is intentionally scalar and branch-light:
        //   - append one 23-bit word at the current bit offset
        //   - flush complete 32-bit transport words as soon as they appear
        //
        // This keeps the packer's CPU cost predictable while preserving the
        // real win, which is fewer FIFO words for the replay side.
        bit_buffer |= u64::from(pin_word & OPTIMIZED_PIN_WORD_MASK) << buffered_bits;
        buffered_bits += OPTIMIZED_PIN_WORD_BITS;
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
                || scan_group_is_blank_run(
                    words,
                    words_per_group,
                    group_index,
                    group_lengths[group_index],
                )
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
    if group_length == 0
        || scan_group_is_blank_run(words, words_per_group, first_group_index, group_length)
    {
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
    //
    // This compaction step is performance-critical even though it is not on the
    // steady-state kernel hot path: every word removed here is a word the
    // resident loop never has to write into the RP1 FIFO again. Historically,
    // the biggest replay wins came from shrinking this final resident payload,
    // not from making the kernel worker more elaborate.
    if group_lengths
        .iter()
        .all(|&group_length| group_length == words_per_group)
    {
        return Ok(words);
    }

    let retained_non_blank_group_count = group_lengths
        .iter()
        .enumerate()
        .filter(|(group_index, group_length)| {
            **group_length != 0
                && !scan_group_is_blank_run(
                    words.as_slice(),
                    words_per_group,
                    *group_index,
                    **group_length,
                )
        })
        .count();
    let actual_word_count = if retained_non_blank_group_count == 0 {
        group_lengths
            .iter()
            .copied()
            .find(|&group_length| group_length != 0)
            .unwrap_or(0)
    } else {
        group_lengths
            .iter()
            .enumerate()
            .filter_map(|(group_index, group_length)| {
                if *group_length == 0
                    || scan_group_is_blank_run(
                        words.as_slice(),
                        words_per_group,
                        group_index,
                        *group_length,
                    )
                {
                    None
                } else {
                    Some(*group_length)
                }
            })
            .sum()
    };
    let mut compacted = Vec::with_capacity(actual_word_count);
    for (group_index, group_length) in group_lengths.iter().copied().enumerate() {
        if group_length == 0 {
            continue;
        }
        if scan_group_is_blank_run(words.as_slice(), words_per_group, group_index, group_length)
            && retained_non_blank_group_count != 0
        {
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

fn compact_group_words_simple(
    words: Vec<u32>,
    group_lengths: &[usize],
    words_per_group: usize,
) -> Result<Vec<u32>, String> {
    // The simple format preserves every logical group in order. It only trims
    // the unused scratch tail from each fixed-size group slot; it does not try
    // to remove blank groups or merge identical bitplanes.
    let actual_word_count: usize = group_lengths.iter().sum();
    let mut compacted = Vec::with_capacity(actual_word_count);
    for (group_index, group_length) in group_lengths.iter().copied().enumerate() {
        let start = group_index.checked_mul(words_per_group).ok_or_else(|| {
            "Pi 5 scan group offset overflowed during simple compaction.".to_string()
        })?;
        compacted.extend_from_slice(&words[start..start + group_length]);
    }
    Ok(compacted)
}

pub(crate) fn encode_raw_span_word(pixel_count: usize, first_word: u32) -> Result<u32, String> {
    // Raw spans use the low bit to distinguish themselves from repeat spans.
    // The low 8 count bits store (len - 1), and the remaining 23 bits carry
    // the first pin word. The all-zero word remains the end-of-spans marker,
    // so callers must never hand this encoder a raw span whose first pin word
    // is zero.
    if pixel_count == 0 {
        return Err("Pi 5 scan spans must contain at least one pixel.".to_string());
    }
    if pixel_count > RAW_SPAN_MAX_PIXELS {
        return Err(format!(
            "Pi 5 scan raw span length {pixel_count} exceeds the packed raw maximum {RAW_SPAN_MAX_PIXELS}."
        ));
    }
    if first_word == 0 {
        return Err(
            "Pi 5 scan raw span headers cannot inline a zero first pin word because 0 is reserved as the end-of-spans marker."
                .to_string(),
        );
    }

    let raw_len = u32::try_from(pixel_count - 1)
        .map_err(|_| "Pi 5 scan span count exceeds 32-bit control words.".to_string())?;
    let encoded_word = (first_word & OPTIMIZED_PIN_WORD_MASK)
        .checked_shl(SPAN_WORD_SHIFT as u32)
        .and_then(|word| word.checked_add(raw_len << 1))
        .ok_or_else(|| "Pi 5 scan raw span control word overflowed.".to_string())?;
    Ok(encoded_word)
}

pub(crate) fn encode_repeat_span_word(
    pixel_count: usize,
    repeated_word: u32,
) -> Result<u32, String> {
    // Repeat spans use one transport word:
    //   bit 0      => repeat opcode tag
    //   bits 1..8  => repeat_len - 1
    //   bits 9..31 => repeated 23-bit pin word
    if pixel_count == 0 {
        return Err("Pi 5 scan repeat spans must contain at least one pixel.".to_string());
    }
    if pixel_count > REPEAT_SPAN_MAX_PIXELS {
        return Err(format!(
            "Pi 5 scan repeat span length {pixel_count} exceeds the packed repeat maximum {REPEAT_SPAN_MAX_PIXELS}."
        ));
    }

    let repeat_len = u32::try_from(pixel_count - 1)
        .map_err(|_| "Pi 5 scan span count exceeds 32-bit control words.".to_string())?;
    let encoded_word = (repeated_word & OPTIMIZED_PIN_WORD_MASK)
        .checked_shl(SPAN_WORD_SHIFT as u32)
        .and_then(|word| {
            word.checked_add(repeat_len << 1)
                .and_then(|word| word.checked_add(1))
        })
        .ok_or_else(|| "Pi 5 scan repeat span control word overflowed.".to_string())?;
    Ok(encoded_word)
}

fn decode_repeat_span_word(word: u32) -> Option<u32> {
    if (word & 1) == 0 {
        return None;
    }
    Some((word >> SPAN_WORD_SHIFT) & OPTIMIZED_PIN_WORD_MASK)
}

fn decode_span_len(word: u32) -> usize {
    (((word >> 1) & ((1_u32 << SPAN_LEN_BITS) - 1)) as usize) + 1
}

fn decode_raw_span_word(word: u32) -> Option<(usize, u32)> {
    if word == END_OF_SPANS_MARKER || (word & 1) != 0 {
        return None;
    }
    Some((
        decode_span_len(word),
        (word >> SPAN_WORD_SHIFT) & OPTIMIZED_PIN_WORD_MASK,
    ))
}

fn unpack_pin_words(packed_words: &[u32], pin_word_count: usize) -> Result<Vec<u32>, String> {
    if packed_pin_word_count(pin_word_count) != packed_words.len() {
        return Err(format!(
            "Pi 5 scan expected {} packed transport words for {} pin words but received {}.",
            packed_pin_word_count(pin_word_count),
            pin_word_count,
            packed_words.len()
        ));
    }

    let mut pin_words = Vec::with_capacity(pin_word_count);
    let mut bit_buffer = 0_u64;
    let mut buffered_bits = 0_usize;
    let mut packed_index = 0_usize;

    while pin_words.len() < pin_word_count {
        while buffered_bits < OPTIMIZED_PIN_WORD_BITS {
            if packed_index >= packed_words.len() {
                return Err(
                    "Pi 5 scan packed pin words ended before the requested logical word count."
                        .to_string(),
                );
            }
            bit_buffer |= u64::from(packed_words[packed_index]) << buffered_bits;
            buffered_bits += 32;
            packed_index += 1;
        }
        pin_words.push((bit_buffer as u32) & OPTIMIZED_PIN_WORD_MASK);
        bit_buffer >>= OPTIMIZED_PIN_WORD_BITS;
        buffered_bits -= OPTIMIZED_PIN_WORD_BITS;
    }

    Ok(pin_words)
}

fn decode_group_trace_from_optimized_words(
    words: &[u32],
    start_index: usize,
) -> Result<(Pi5ScanGroupTrace, usize), String> {
    let blank_word = *words.get(start_index).ok_or_else(|| {
        "Pi 5 scan group trace decode ran past the packed word buffer.".to_string()
    })?;
    let mut word_index = start_index + 1;
    let mut shift_words = Vec::new();

    loop {
        let span_word = *words.get(word_index).ok_or_else(|| {
            "Pi 5 scan group trace decode hit EOF before the end-of-spans marker.".to_string()
        })?;
        if span_word == END_OF_SPANS_MARKER {
            break;
        }
        if let Some(repeated_word) = decode_repeat_span_word(span_word) {
            shift_words.extend(std::iter::repeat_n(
                repeated_word,
                decode_span_len(span_word),
            ));
            word_index += 1;
            continue;
        }
        if let Some((raw_len, first_word)) = decode_raw_span_word(span_word) {
            let packed_word_count = packed_pin_word_count(raw_len.saturating_sub(1));
            let packed_slice_start = word_index + 1;
            let packed_slice_end = packed_slice_start
                .checked_add(packed_word_count)
                .ok_or_else(|| {
                    "Pi 5 scan raw-span packed payload overflowed during decode.".to_string()
                })?;
            let packed_slice =
                words
                    .get(packed_slice_start..packed_slice_end)
                    .ok_or_else(|| {
                        "Pi 5 scan raw-span packed payload ran past EOF during decode.".to_string()
                    })?;
            shift_words.push(first_word);
            shift_words.extend(unpack_pin_words(packed_slice, raw_len.saturating_sub(1))?);
            word_index = packed_slice_end;
            continue;
        }
        return Err(format!(
            "Pi 5 scan encountered an invalid span/control word 0x{span_word:08x} during decode."
        ));
    }

    let active_word = *words.get(word_index + 1).ok_or_else(|| {
        "Pi 5 scan group trace decode hit EOF before the active-display word.".to_string()
    })?;
    let dwell_word = *words
        .get(word_index + 2)
        .ok_or_else(|| "Pi 5 scan group trace decode hit EOF before the dwell word.".to_string())?;
    Ok((
        Pi5ScanGroupTrace {
            blank_word,
            shift_words,
            active_word,
            dwell_ticks: decode_dwell_counter(dwell_word),
        },
        word_index + 3,
    ))
}

fn decode_group_trace_from_simple_words(
    words: &[u32],
    config: &Pi5ScanConfig,
    row_pair: usize,
    plane_index: usize,
) -> Result<Pi5ScanGroupTrace, String> {
    let width = config.width()? as usize;
    let group_index = row_pair
        .checked_mul(usize::from(config.pwm_bits))
        .and_then(|index| index.checked_add(plane_index))
        .ok_or_else(|| "Pi 5 simple trace group index overflowed.".to_string())?;
    let mut start = 0_usize;
    let mut group_words = None;

    for current_group in 0..=group_index {
        let group_length = decode_simple_group_length(
            words.get(start..).ok_or_else(|| {
                "Pi 5 simple trace decode ran past the packed word buffer.".to_string()
            })?,
            width,
        )?;
        let end = start
            .checked_add(group_length)
            .ok_or_else(|| "Pi 5 simple trace group end overflowed.".to_string())?;
        let current_words = words.get(start..end).ok_or_else(|| {
            "Pi 5 simple trace decode ran past the packed word buffer.".to_string()
        })?;
        if current_group == group_index {
            group_words = Some(current_words);
            break;
        }
        start = end;
    }
    let group_words =
        group_words.ok_or_else(|| "Pi 5 simple trace group lookup did not resolve.".to_string())?;
    let mut shift_words = Vec::with_capacity(width);
    let mut word_index = 2_usize;
    while shift_words.len() < width {
        let command_word = *group_words.get(word_index).ok_or_else(|| {
            "Pi 5 simple trace missing a shift command before the requested width was reconstructed."
                .to_string()
        })?;
        word_index += 1;
        match decode_simple_command(command_word)? {
            (SimpleCommandKind::Data, logical_count) => {
                let data_count = usize::try_from(logical_count)
                    .map_err(|_| "Pi 5 simple data command count does not fit host usize.".to_string())?;
                let payload_end = word_index.checked_add(data_count).ok_or_else(|| {
                    "Pi 5 simple trace data payload overflowed while reconstructing shift words."
                        .to_string()
                })?;
                let payload = group_words.get(word_index..payload_end).ok_or_else(|| {
                    "Pi 5 simple trace missing literal data payload words.".to_string()
                })?;
                shift_words.extend_from_slice(payload);
                word_index = payload_end;
            }
            (SimpleCommandKind::Delay, _) => {
                return Err(
                    "Pi 5 simple trace encountered a delay command before reconstructing the full row width."
                        .to_string(),
                );
            }
        }
    }
    if shift_words.len() != width {
        return Err(format!(
            "Pi 5 simple trace reconstructed {} columns, expected {width}.",
            shift_words.len()
        ));
    }
    let encoded_dwell = *group_words
        .get(group_words.len() - 2)
        .ok_or_else(|| "Pi 5 simple trace missing final dwell command.".to_string())?;
    let active_word = *group_words
        .get(group_words.len() - 1)
        .ok_or_else(|| "Pi 5 simple trace missing final active-display word.".to_string())?;
    Ok(Pi5ScanGroupTrace {
        blank_word: group_words[1],
        shift_words,
        active_word,
        dwell_ticks: decode_simple_delay_command(encoded_dwell)?,
    })
}

fn decode_simple_group_length(words: &[u32], width: usize) -> Result<usize, String> {
    if words.len() < SIMPLE_GROUP_FIXED_WORDS {
        return Err("Pi 5 simple trace group was shorter than the fixed trailer size.".to_string());
    }
    let mut word_index = 2_usize;
    let mut shifted_columns = 0_usize;
    while shifted_columns < width {
        let command_word = *words.get(word_index).ok_or_else(|| {
            "Pi 5 simple trace decode hit EOF before reconstructing the full row width."
                .to_string()
        })?;
        word_index += 1;
        match decode_simple_command(command_word)? {
            (SimpleCommandKind::Data, logical_count) => {
                let data_count = usize::try_from(logical_count)
                    .map_err(|_| "Pi 5 simple data command count does not fit host usize.".to_string())?;
                word_index = word_index.checked_add(data_count).ok_or_else(|| {
                    "Pi 5 simple trace data payload overflowed while measuring group length."
                        .to_string()
                })?;
                shifted_columns = shifted_columns.checked_add(data_count).ok_or_else(|| {
                    "Pi 5 simple shift-column counter overflowed while measuring group length."
                        .to_string()
                })?;
            }
            (SimpleCommandKind::Delay, _) => {
                return Err(
                    "Pi 5 simple trace encountered a delay command before reconstructing the full row width."
                        .to_string(),
                );
            }
        }
    }
    if shifted_columns != width {
        return Err(format!(
            "Pi 5 simple trace reconstructed {shifted_columns} columns while measuring group length, expected {width}."
        ));
    }
    let total_length = word_index
        .checked_add(6)
        .ok_or_else(|| "Pi 5 simple group length overflowed.".to_string())?;
    if total_length > words.len() {
        return Err("Pi 5 simple trace group trailer ran past the packed word buffer.".to_string());
    }
    Ok(total_length)
}

pub(crate) fn build_simple_smoke_group_words(
    config: &Pi5ScanConfig,
    row_pair: usize,
    top_rgb: (bool, bool, bool),
    bottom_rgb: (bool, bool, bool),
    dwell_ticks: u32,
) -> Result<Vec<u32>, String> {
    let pinout = config.pinout();
    let pin_word_shift = config.pin_word_shift();
    let addr_bits = pinout.address_bits(row_pair, pin_word_shift);
    let blank_word = addr_bits | pinout.oe_inactive_bits(pin_word_shift);
    let active_word = addr_bits;
    let width = config.width()? as usize;

    let mut data_bits = addr_bits;
    for (is_on, gpio) in [
        (top_rgb.0, pinout.rgb_gpios[0]),
        (top_rgb.1, pinout.rgb_gpios[1]),
        (top_rgb.2, pinout.rgb_gpios[2]),
        (bottom_rgb.0, pinout.rgb_gpios[3]),
        (bottom_rgb.1, pinout.rgb_gpios[4]),
        (bottom_rgb.2, pinout.rgb_gpios[5]),
    ] {
        if is_on {
            data_bits |= 1_u32 << (u32::from(gpio) - pin_word_shift);
        }
    }
    let shift_word = blank_word | data_bits;

    let latch_high_word = blank_word | pinout.lat_bits(pin_word_shift);
    let mut words = Vec::with_capacity(simple_group_word_count(width));
    words.push(encode_simple_delay_command(config.timing().post_addr_ticks)?);
    words.push(blank_word);
    words.push(encode_simple_data_command(width)?);
    words.extend(std::iter::repeat_n(shift_word, width));
    words.push(encode_simple_delay_command(config.timing().latch_ticks)?);
    words.push(latch_high_word);
    words.push(encode_simple_delay_command(config.timing().post_latch_ticks)?);
    words.push(blank_word);
    words.push(encode_simple_delay_command(dwell_ticks)?);
    words.push(active_word);
    Ok(words)
}

pub(crate) fn build_simple_group_words_for_rgba(
    config: &Pi5ScanConfig,
    rgba: &[u8],
    row_pair: usize,
    plane_index: usize,
) -> Result<Vec<u32>, String> {
    let width = config.width()? as usize;
    let row_pairs = config.row_pairs()?;
    let word_count = simple_group_word_count(width);
    let mut words = vec![0_u32; word_count];

    let actual_word_count = write_scan_segment_simple(
        &mut words,
        config,
        rgba,
        width,
        row_pairs,
        row_pair,
        plane_index,
    )?;
    words.truncate(actual_word_count);
    Ok(words)
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
    pin_word_shift: u32,
) -> u32 {
    // Convert one top/bottom pixel pair into the rebased six-RGB-bit word for
    // a single bitplane and column.
    let upper_pixel = pixel_channels(rgba, width, row_pair, column);
    let lower_pixel = pixel_channels(rgba, width, row_pair + row_pairs, column);
    let mut bits = 0_u32;
    if channel_plane_is_set(upper_pixel[0], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[0]) - pin_word_shift);
    }
    if channel_plane_is_set(upper_pixel[1], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[1]) - pin_word_shift);
    }
    if channel_plane_is_set(upper_pixel[2], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[2]) - pin_word_shift);
    }
    if channel_plane_is_set(lower_pixel[0], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[3]) - pin_word_shift);
    }
    if channel_plane_is_set(lower_pixel[1], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[4]) - pin_word_shift);
    }
    if channel_plane_is_set(lower_pixel[2], shift, pwm_bits) {
        bits |= 1_u32 << (u32::from(pinout.rgb_gpios[5]) - pin_word_shift);
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
            .and_then(|group_count| {
                group_count.checked_mul(max_group_word_count_for_config(self, width))
            })
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
        simple_clock_hold_ticks: u32,
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
        batches_submitted: *mut u64,
        words_written: *mut u64,
        drain_failures: *mut u64,
        stop_requests_seen_during_batch: *mut u64,
        mmio_write_ns: *mut u64,
        drain_ns: *mut u64,
        max_batch_replays: *mut u32,
        worker_cpu: *mut u32,
        worker_priority: *mut u32,
        worker_runnable: *mut u32,
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
