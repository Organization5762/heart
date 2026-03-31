#![allow(dead_code)]

use std::ffi::c_char;
use std::slice;
use std::time::{Duration, Instant};

use rayon::prelude::*;

use super::config::{expected_rgba_size, WiringProfile};
use super::frame::FrameBuffer;

const COMMAND_DATA: u32 = 1_u32 << 31;
const COMMAND_DELAY: u32 = 0;
const DEFAULT_CLOCK_DIVIDER: f32 = 1.0;
const DEFAULT_DMA_BUFFER_COUNT: u32 = 2;
const DEFAULT_LATCH_TICKS: u32 = 1;
const DEFAULT_POST_ADDR_TICKS: u32 = 5;
const DEFAULT_POST_LATCH_TICKS: u32 = 1;
const DEFAULT_PWM_BITS: u8 = 11;
const OE_ACTIVE_LOW: bool = true;
const PACK_PARALLEL_THRESHOLD_WORDS: usize = 8_192;
const PIO_ERROR_BUFFER_BYTES: usize = 256;
const PI5_SCAN_UNSUPPORTED_MESSAGE: &str =
    "Pi 5 scan transport is only supported on Linux aarch64 builds.";
const PI5_SCAN_MAX_DMA_BUFFER_BYTES: usize = 22_880;
const WORDS_PER_GROUP_OVERHEAD: usize = 11;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct Pi5ScanConfig {
    pub(crate) panel_rows: u16,
    pub(crate) panel_cols: u16,
    pub(crate) chain_length: u16,
    pub(crate) parallel: u8,
    pub(crate) pwm_bits: u8,
    pub(crate) lsb_dwell_ticks: u32,
    pinout: Pi5ScanPinout,
}

impl Pi5ScanConfig {
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
            pwm_bits: DEFAULT_PWM_BITS,
            lsb_dwell_ticks: pinout.default_lsb_dwell_ticks(),
            pinout,
        };
        config.validate()?;
        Ok(config)
    }

    pub(crate) fn width(&self) -> Result<u32, String> {
        u32::from(self.panel_cols)
            .checked_mul(u32::from(self.chain_length))
            .ok_or_else(|| "Pi 5 scan width exceeds supported dimensions.".to_string())
    }

    pub(crate) fn height(&self) -> Result<u32, String> {
        u32::from(self.panel_rows)
            .checked_mul(u32::from(self.parallel))
            .ok_or_else(|| "Pi 5 scan height exceeds supported dimensions.".to_string())
    }

    pub(crate) fn row_pairs(&self) -> Result<usize, String> {
        let height = usize::try_from(self.height()?)
            .map_err(|_| "Pi 5 scan height exceeds host usize.".to_string())?;
        Ok(height / 2)
    }

    pub(crate) fn pinout(&self) -> Pi5ScanPinout {
        self.pinout
    }

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
    pub(crate) word_count: usize,
    pub(crate) pack_duration: Duration,
}

#[derive(Clone, Debug)]
pub(crate) struct PackedScanFrame {
    words: Vec<u32>,
}

impl PackedScanFrame {
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
        let pack_start = Instant::now();
        let groups: Vec<(usize, usize)> = (0..group_count)
            .map(|group_index| {
                (
                    group_index / usize::from(config.pwm_bits),
                    group_index % usize::from(config.pwm_bits),
                )
            })
            .collect();

        let segments: Vec<Vec<u32>> =
            if config.estimated_word_count_for_width(width)? >= PACK_PARALLEL_THRESHOLD_WORDS {
                groups
                    .par_iter()
                    .map(|&(row_pair, plane_index)| {
                        build_scan_segment(config, rgba, width, row_pair, plane_index)
                    })
                    .collect::<Result<Vec<_>, _>>()?
            } else {
                groups
                    .iter()
                    .map(|&(row_pair, plane_index)| {
                        build_scan_segment(config, rgba, width, row_pair, plane_index)
                    })
                    .collect::<Result<Vec<_>, _>>()?
            };

        let total_words = segments.iter().map(Vec::len).sum();
        let mut words = Vec::with_capacity(total_words);
        for segment in segments {
            words.extend(segment);
        }
        let pack_duration = pack_start.elapsed();
        Ok((
            Self { words },
            PackedScanFrameStats {
                word_count: total_words,
                pack_duration,
            },
        ))
    }

    pub(crate) fn pack_frame(
        config: &Pi5ScanConfig,
        frame: &FrameBuffer,
    ) -> Result<(Self, PackedScanFrameStats), String> {
        Self::pack_rgba(config, frame.as_slice())
    }

    pub(crate) fn as_words(&self) -> &[u32] {
        &self.words
    }

    pub(crate) fn as_bytes(&self) -> &[u8] {
        unsafe {
            slice::from_raw_parts(
                self.words.as_ptr().cast::<u8>(),
                self.words.len() * std::mem::size_of::<u32>(),
            )
        }
    }

    pub(crate) fn word_count(&self) -> usize {
        self.words.len()
    }
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct Pi5ScanBenchmarkSample {
    pub(crate) word_count: usize,
    pub(crate) pack_duration: Duration,
    pub(crate) stream_duration: Duration,
}

#[derive(Debug)]
pub(crate) struct Pi5PioScanTransport {
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    handle: *mut ffi::HeartPi5PioScanHandle,
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
unsafe impl Send for Pi5PioScanTransport {}

impl Pi5PioScanTransport {
    pub(crate) fn new(max_transfer_words: usize, pinout: Pi5ScanPinout) -> Result<Self, String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            if max_transfer_words == 0 {
                return Err("Pi 5 scan transport requires a non-zero transfer buffer.".to_string());
            }
            if !DEFAULT_CLOCK_DIVIDER.is_finite() || DEFAULT_CLOCK_DIVIDER <= 0.0 {
                return Err(
                    "Pi 5 scan transport requires a positive finite clock divider.".to_string(),
                );
            }
            if DEFAULT_DMA_BUFFER_COUNT == 0 {
                return Err("Pi 5 scan transport requires at least one DMA buffer.".to_string());
            }
            let max_transfer_bytes = max_transfer_words
                .checked_mul(std::mem::size_of::<u32>())
                .ok_or_else(|| {
                    "Pi 5 scan transport buffer size overflowed while converting to bytes."
                        .to_string()
                })?;
            let dma_buffer_size = u32::try_from(
                max_transfer_bytes.min(PI5_SCAN_MAX_DMA_BUFFER_BYTES),
            )
            .map_err(|_| "Pi 5 scan transport buffer exceeds 32-bit DMA limits.".to_string())?;
            let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
            let mut handle: *mut ffi::HeartPi5PioScanHandle = std::ptr::null_mut();
            let result = unsafe {
                heart_pi5_pio_scan_open(
                    pinout.oe_gpio,
                    pinout.lat_gpio,
                    pinout.clock_gpio,
                    DEFAULT_CLOCK_DIVIDER,
                    dma_buffer_size,
                    DEFAULT_DMA_BUFFER_COUNT,
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
            return Ok(Self { handle });
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = max_transfer_words;
            let _ = pinout;
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    pub(crate) fn stream(&mut self, frame: &PackedScanFrame) -> Result<Duration, String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
            let data_bytes = u32::try_from(frame.as_bytes().len())
                .map_err(|_| "Pi 5 scan frame exceeds 32-bit DMA limits.".to_string())?;
            let start = Instant::now();
            let result = unsafe {
                heart_pi5_pio_scan_stream(
                    self.handle,
                    frame.as_bytes().as_ptr(),
                    data_bytes,
                    error_buffer.as_mut_ptr(),
                    error_buffer.len(),
                )
            };
            if result != 0 {
                return Err(read_error_buffer(&error_buffer)
                    .unwrap_or_else(|| format!("Pi 5 scan transport failed with code {result}.")));
            }
            Ok(start.elapsed())
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = frame;
            Err(PI5_SCAN_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    pub(crate) fn benchmark_rgba(
        &mut self,
        config: &Pi5ScanConfig,
        rgba: &[u8],
    ) -> Result<Pi5ScanBenchmarkSample, String> {
        let (packed, stats) = PackedScanFrame::pack_rgba(config, rgba)?;
        let stream_duration = self.stream(&packed)?;
        Ok(Pi5ScanBenchmarkSample {
            word_count: stats.word_count,
            pack_duration: stats.pack_duration,
            stream_duration,
        })
    }
}

impl Drop for Pi5PioScanTransport {
    fn drop(&mut self) {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        unsafe {
            if !self.handle.is_null() {
                heart_pi5_pio_scan_close(self.handle);
                self.handle = std::ptr::null_mut();
            }
        }
    }
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

    fn address_bits(&self, row_pair: usize) -> u32 {
        let mut bits = 0_u32;
        for (bit_index, gpio) in self.addr_gpios.iter().enumerate() {
            if (row_pair & (1 << bit_index)) != 0 {
                bits |= 1_u32 << u32::from(*gpio);
            }
        }
        bits
    }

    fn oe_active_bits(&self) -> u32 {
        if OE_ACTIVE_LOW {
            0
        } else {
            1_u32 << self.oe_gpio
        }
    }

    fn oe_inactive_bits(&self) -> u32 {
        if OE_ACTIVE_LOW {
            1_u32 << self.oe_gpio
        } else {
            0
        }
    }

    fn lat_bits(&self) -> u32 {
        1_u32 << self.lat_gpio
    }

    fn default_lsb_dwell_ticks(&self) -> u32 {
        2
    }
}

fn build_scan_segment(
    config: &Pi5ScanConfig,
    rgba: &[u8],
    width: usize,
    row_pair: usize,
    plane_index: usize,
) -> Result<Vec<u32>, String> {
    let row_pairs = config.row_pairs()?;
    if row_pair >= row_pairs {
        return Err(format!(
            "Row pair {row_pair} exceeds the configured row pair count {row_pairs}."
        ));
    }
    let pinout = config.pinout();
    let addr_bits = pinout.address_bits(row_pair);
    let blank_word = addr_bits | pinout.oe_inactive_bits();
    let active_word = addr_bits | pinout.oe_active_bits();
    let msb_first_shift = usize::from(config.pwm_bits) - plane_index - 1;
    let dwell_ticks = config
        .lsb_dwell_ticks
        .checked_shl(msb_first_shift as u32)
        .ok_or_else(|| "Pi 5 scan dwell ticks overflowed.".to_string())?;

    let mut words = Vec::with_capacity(width + WORDS_PER_GROUP_OVERHEAD);
    append_delay(&mut words, DEFAULT_POST_ADDR_TICKS, blank_word);
    append_data_run_header(&mut words, width as u32)?;
    for x in 0..width {
        words.push(
            blank_word
                | scan_pixel_bits(
                    rgba,
                    pinout,
                    width,
                    row_pair,
                    row_pairs,
                    x,
                    msb_first_shift,
                    config.pwm_bits,
                ),
        );
    }
    append_delay(
        &mut words,
        DEFAULT_LATCH_TICKS,
        blank_word | pinout.lat_bits(),
    );
    append_delay(&mut words, DEFAULT_POST_LATCH_TICKS, blank_word);
    append_delay(&mut words, dwell_ticks, active_word);
    append_delay(&mut words, 1, blank_word);
    Ok(words)
}

fn append_data_run_header(words: &mut Vec<u32>, pixel_count: u32) -> Result<(), String> {
    if pixel_count == 0 {
        return Err("Pi 5 scan data runs must contain at least one pixel.".to_string());
    }
    words.push(COMMAND_DATA | (pixel_count - 1));
    Ok(())
}

fn append_delay(words: &mut Vec<u32>, ticks: u32, pin_word: u32) {
    words.push(COMMAND_DELAY | ticks.saturating_sub(1));
    words.push(pin_word);
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
    let upper_pixel = pixel_channels(rgba, width, row_pair, column);
    let lower_pixel = pixel_channels(rgba, width, row_pair + row_pairs, column);
    let mut bits = 0_u32;
    if channel_plane_is_set(upper_pixel[0], shift, pwm_bits) {
        bits |= 1_u32 << u32::from(pinout.rgb_gpios[0]);
    }
    if channel_plane_is_set(upper_pixel[1], shift, pwm_bits) {
        bits |= 1_u32 << u32::from(pinout.rgb_gpios[1]);
    }
    if channel_plane_is_set(upper_pixel[2], shift, pwm_bits) {
        bits |= 1_u32 << u32::from(pinout.rgb_gpios[2]);
    }
    if channel_plane_is_set(lower_pixel[0], shift, pwm_bits) {
        bits |= 1_u32 << u32::from(pinout.rgb_gpios[3]);
    }
    if channel_plane_is_set(lower_pixel[1], shift, pwm_bits) {
        bits |= 1_u32 << u32::from(pinout.rgb_gpios[4]);
    }
    if channel_plane_is_set(lower_pixel[2], shift, pwm_bits) {
        bits |= 1_u32 << u32::from(pinout.rgb_gpios[5]);
    }
    bits
}

fn pixel_channels(rgba: &[u8], width: usize, row: usize, column: usize) -> [u8; 3] {
    let offset = ((row * width) + column) * 4;
    [rgba[offset], rgba[offset + 1], rgba[offset + 2]]
}

fn channel_plane_is_set(value: u8, shift: usize, pwm_bits: u8) -> bool {
    let expanded = expand_channel_to_pwm_bits(value, pwm_bits);
    (expanded & (1_u16 << shift)) != 0
}

fn expand_channel_to_pwm_bits(value: u8, pwm_bits: u8) -> u16 {
    if pwm_bits <= 8 {
        u16::from(value >> (8 - pwm_bits))
    } else {
        u16::from(value) << (pwm_bits - 8).min(8)
    }
}

fn read_error_buffer(buffer: &[c_char]) -> Option<String> {
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
    pub(crate) fn estimated_word_count_for_width(&self, width: usize) -> Result<usize, String> {
        let row_pairs = self.row_pairs()?;
        row_pairs
            .checked_mul(usize::from(self.pwm_bits))
            .and_then(|group_count| group_count.checked_mul(width + WORDS_PER_GROUP_OVERHEAD))
            .ok_or_else(|| "Pi 5 scan word count overflowed.".to_string())
    }

    pub(crate) fn estimated_word_count(&self) -> Result<usize, String> {
        let width = usize::try_from(self.width()?)
            .map_err(|_| "Pi 5 scan width exceeds host usize.".to_string())?;
        self.estimated_word_count_for_width(width)
    }
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
#[link(name = "heart_pi5_pio_scan_shim", kind = "static")]
unsafe extern "C" {
    fn heart_pi5_pio_scan_open(
        oe_gpio: u32,
        lat_gpio: u32,
        clock_gpio: u32,
        clock_divider: f32,
        dma_buffer_size: u32,
        dma_buffer_count: u32,
        out_handle: *mut *mut ffi::HeartPi5PioScanHandle,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_pio_scan_stream(
        handle: *mut ffi::HeartPi5PioScanHandle,
        data: *const u8,
        data_bytes: u32,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_pio_scan_close(handle: *mut ffi::HeartPi5PioScanHandle);
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
}
