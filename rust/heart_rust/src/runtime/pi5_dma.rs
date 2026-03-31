#![allow(dead_code)]

use std::ffi::c_char;
use std::time::{Duration, Instant};

use rayon::prelude::*;

use super::config::expected_rgba_size;

const CONTROL_WORD_BYTES_PER_ROW_GROUP: usize = 1;
const DEFAULT_CLOCK_DIVIDER: f32 = 1.0;
const DEFAULT_DMA_BUFFER_COUNT: u32 = 2;
const DEFAULT_OUTPUT_BASE_GPIO: u32 = 20;
const DEFAULT_OUTPUT_PIN_COUNT: u32 = 8;
const DEFAULT_PWM_BITS: u8 = 11;
const DEFAULT_TRANSPORT_CLOCK_GPIO: u32 = 17;
const LAT_BIT: u8 = 1 << 6;
const MAX_ROW_ADDRESS: usize = 32;
const OE_BIT: u8 = 1 << 7;
const PACK_PARALLEL_THRESHOLD_BYTES: usize = 32_768;
const PI5_DMA_UNSUPPORTED_MESSAGE: &str =
    "Pi 5 DMA/PIO transport is only supported on Linux aarch64 builds.";
const PIO_ERROR_BUFFER_BYTES: usize = 256;
const RGB_EXPANSION_SHIFT: u8 = 3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct Pi5TransportConfig {
    pub(crate) panel_rows: u16,
    pub(crate) panel_cols: u16,
    pub(crate) chain_length: u16,
    pub(crate) parallel: u8,
    pub(crate) pwm_bits: u8,
}

impl Pi5TransportConfig {
    pub(crate) fn new(
        panel_rows: u16,
        panel_cols: u16,
        chain_length: u16,
        parallel: u8,
        pwm_bits: u8,
    ) -> Result<Self, String> {
        let config = Self {
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            pwm_bits,
        };
        config.validate()?;
        Ok(config)
    }

    pub(crate) fn width(&self) -> Result<u32, String> {
        u32::from(self.panel_cols)
            .checked_mul(u32::from(self.chain_length))
            .ok_or_else(|| "Pi 5 DMA transport width exceeds supported dimensions.".to_string())
    }

    pub(crate) fn height(&self) -> Result<u32, String> {
        u32::from(self.panel_rows)
            .checked_mul(u32::from(self.parallel))
            .ok_or_else(|| "Pi 5 DMA transport height exceeds supported dimensions.".to_string())
    }

    pub(crate) fn row_pairs(&self) -> Result<usize, String> {
        let height = usize::try_from(self.height()?)
            .map_err(|_| "Pi 5 DMA transport height exceeds host usize.".to_string())?;
        Ok(height / 2)
    }

    pub(crate) fn packed_frame_len(&self) -> Result<usize, String> {
        let width = usize::try_from(self.width()?)
            .map_err(|_| "Pi 5 DMA transport width exceeds host usize.".to_string())?;
        let row_pairs = self.row_pairs()?;
        row_pairs
            .checked_mul(self.pwm_bits as usize)
            .and_then(|groups| groups.checked_mul(width + CONTROL_WORD_BYTES_PER_ROW_GROUP))
            .ok_or_else(|| "Pi 5 DMA transport packed frame length overflowed.".to_string())
    }

    fn validate(&self) -> Result<(), String> {
        if self.parallel != 1 {
            return Err(format!(
                "Pi 5 DMA transport probe currently supports parallel=1, received {}.",
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
            return Err("chain_length must be at least 1 for Pi 5 DMA transport.".to_string());
        }
        if self.pwm_bits == 0 || self.pwm_bits > 16 {
            return Err(format!(
                "Unsupported pwm_bits {}. Expected 1 through 16.",
                self.pwm_bits
            ));
        }
        if self.panel_rows % 2 != 0 {
            return Err(format!(
                "Pi 5 DMA transport requires an even panel_rows value, received {}.",
                self.panel_rows
            ));
        }
        let row_pairs = usize::from(self.panel_rows / 2);
        if row_pairs > MAX_ROW_ADDRESS {
            return Err(format!(
                "Pi 5 DMA transport supports up to {MAX_ROW_ADDRESS} row pairs, received {row_pairs}."
            ));
        }
        Ok(())
    }
}

#[derive(Clone, Debug)]
pub(crate) struct PackedTransportFrame {
    data: Vec<u8>,
}

impl PackedTransportFrame {
    pub(crate) fn pack_rgba(
        config: &Pi5TransportConfig,
        rgba: &[u8],
    ) -> Result<(Self, Duration), String> {
        let width = usize::try_from(config.width()?)
            .map_err(|_| "Pi 5 DMA transport width exceeds host usize.".to_string())?;
        let height = usize::try_from(config.height()?)
            .map_err(|_| "Pi 5 DMA transport height exceeds host usize.".to_string())?;
        let expected_size = expected_rgba_size(width as u32, height as u32).ok_or_else(|| {
            "Pi 5 DMA transport geometry exceeds supported RGBA size.".to_string()
        })?;
        if rgba.len() != expected_size {
            return Err(format!(
                "Pi 5 DMA transport expected {expected_size} RGBA bytes but received {}.",
                rgba.len()
            ));
        }

        let row_pairs = config.row_pairs()?;
        let bytes_per_group = width + CONTROL_WORD_BYTES_PER_ROW_GROUP;
        let total_groups = row_pairs * usize::from(config.pwm_bits);
        let mut data = vec![0_u8; total_groups * bytes_per_group];
        let pack_start = Instant::now();

        if data.len() >= PACK_PARALLEL_THRESHOLD_BYTES {
            data.par_chunks_mut(bytes_per_group)
                .enumerate()
                .for_each(|(group_index, group)| {
                    write_transport_group(
                        group,
                        rgba,
                        width,
                        row_pairs,
                        group_index / usize::from(config.pwm_bits),
                        group_index % usize::from(config.pwm_bits),
                        config.pwm_bits,
                    );
                });
        } else {
            for (group_index, group) in data.chunks_mut(bytes_per_group).enumerate() {
                write_transport_group(
                    group,
                    rgba,
                    width,
                    row_pairs,
                    group_index / usize::from(config.pwm_bits),
                    group_index % usize::from(config.pwm_bits),
                    config.pwm_bits,
                );
            }
        }

        Ok((Self { data }, pack_start.elapsed()))
    }

    pub(crate) fn as_slice(&self) -> &[u8] {
        &self.data
    }

    pub(crate) fn len(&self) -> usize {
        self.data.len()
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub(crate) struct Pi5DmaBenchmarkSample {
    pub(crate) packed_bytes: usize,
    pub(crate) pack_duration: Duration,
    pub(crate) dma_duration: Duration,
}

pub(crate) struct Pi5PioDmaTransport {
    #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
    handle: *mut ffi::HeartPi5PioTxHandle,
}

impl Pi5PioDmaTransport {
    pub(crate) fn new(max_transfer_bytes: usize) -> Result<Self, String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            if max_transfer_bytes == 0 {
                return Err("Pi 5 DMA transport requires a non-zero transfer buffer.".to_string());
            }
            let dma_buffer_size = u32::try_from(max_transfer_bytes)
                .map_err(|_| "Pi 5 DMA transport buffer exceeds 32-bit DMA limits.".to_string())?;
            let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
            let mut handle = std::ptr::null_mut();
            let result = unsafe {
                ffi::heart_pi5_pio_tx_open(
                    DEFAULT_OUTPUT_BASE_GPIO,
                    DEFAULT_OUTPUT_PIN_COUNT,
                    DEFAULT_TRANSPORT_CLOCK_GPIO,
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
                    format!("Pi 5 DMA transport initialization failed with code {result}.")
                }));
            }
            return Ok(Self { handle });
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = max_transfer_bytes;
            Err(PI5_DMA_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    pub(crate) fn stream(&mut self, frame: &PackedTransportFrame) -> Result<Duration, String> {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        {
            let mut error_buffer = [0 as c_char; PIO_ERROR_BUFFER_BYTES];
            let data_bytes = u32::try_from(frame.len())
                .map_err(|_| "Pi 5 DMA transport frame exceeds 32-bit DMA limits.".to_string())?;
            let start = Instant::now();
            let result = unsafe {
                ffi::heart_pi5_pio_tx_stream(
                    self.handle,
                    frame.as_slice().as_ptr(),
                    data_bytes,
                    error_buffer.as_mut_ptr(),
                    error_buffer.len(),
                )
            };
            if result != 0 {
                return Err(read_error_buffer(&error_buffer).unwrap_or_else(|| {
                    format!("Pi 5 DMA transport submission failed with code {result}.")
                }));
            }
            return Ok(start.elapsed());
        }

        #[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
        {
            let _ = frame;
            Err(PI5_DMA_UNSUPPORTED_MESSAGE.to_string())
        }
    }

    pub(crate) fn benchmark_rgba(
        &mut self,
        config: &Pi5TransportConfig,
        rgba: &[u8],
    ) -> Result<Pi5DmaBenchmarkSample, String> {
        let (packed, pack_duration) = PackedTransportFrame::pack_rgba(config, rgba)?;
        let dma_duration = self.stream(&packed)?;
        Ok(Pi5DmaBenchmarkSample {
            packed_bytes: packed.len(),
            pack_duration,
            dma_duration,
        })
    }
}

impl Drop for Pi5PioDmaTransport {
    fn drop(&mut self) {
        #[cfg(all(target_arch = "aarch64", target_os = "linux"))]
        unsafe {
            ffi::heart_pi5_pio_tx_close(self.handle);
        }
    }
}

fn write_transport_group(
    destination: &mut [u8],
    rgba: &[u8],
    width: usize,
    row_pairs: usize,
    row_pair_index: usize,
    plane_index: usize,
    pwm_bits: u8,
) {
    let lower_row_index = row_pair_index + row_pairs;
    for column in 0..width {
        let upper_offset = rgba_offset(width, row_pair_index, column);
        let lower_offset = rgba_offset(width, lower_row_index, column);
        destination[column] = pack_data_byte(
            rgba[upper_offset],
            rgba[upper_offset + 1],
            rgba[upper_offset + 2],
            rgba[lower_offset],
            rgba[lower_offset + 1],
            rgba[lower_offset + 2],
            plane_index,
            pwm_bits,
        );
    }
    destination[width] = pack_control_byte(row_pair_index);
}

fn rgba_offset(width: usize, row_index: usize, column: usize) -> usize {
    ((row_index * width) + column) * 4
}

fn pack_control_byte(row_pair_index: usize) -> u8 {
    ((row_pair_index as u8) & 0x1f) | LAT_BIT | OE_BIT
}

fn pack_data_byte(
    upper_red: u8,
    upper_green: u8,
    upper_blue: u8,
    lower_red: u8,
    lower_green: u8,
    lower_blue: u8,
    plane_index: usize,
    pwm_bits: u8,
) -> u8 {
    let mut packed = 0_u8;
    if channel_plane_is_set(upper_red, plane_index, pwm_bits) {
        packed |= 1 << 0;
    }
    if channel_plane_is_set(upper_green, plane_index, pwm_bits) {
        packed |= 1 << 1;
    }
    if channel_plane_is_set(upper_blue, plane_index, pwm_bits) {
        packed |= 1 << 2;
    }
    if channel_plane_is_set(lower_red, plane_index, pwm_bits) {
        packed |= 1 << 3;
    }
    if channel_plane_is_set(lower_green, plane_index, pwm_bits) {
        packed |= 1 << 4;
    }
    if channel_plane_is_set(lower_blue, plane_index, pwm_bits) {
        packed |= 1 << 5;
    }
    packed
}

fn channel_plane_is_set(value: u8, plane_index: usize, pwm_bits: u8) -> bool {
    let expanded = expand_channel_to_pwm_bits(value, pwm_bits);
    ((expanded >> plane_index) & 1) != 0
}

fn expand_channel_to_pwm_bits(value: u8, pwm_bits: u8) -> u16 {
    if pwm_bits <= 8 {
        u16::from(value >> (8 - pwm_bits))
    } else {
        u16::from(value) << (pwm_bits - 8).min(RGB_EXPANSION_SHIFT)
    }
}

fn read_error_buffer(buffer: &[c_char; PIO_ERROR_BUFFER_BYTES]) -> Option<String> {
    let bytes: Vec<u8> = buffer
        .iter()
        .copied()
        .take_while(|value| *value != 0)
        .map(|value| value as u8)
        .collect();
    if bytes.is_empty() {
        return None;
    }
    String::from_utf8(bytes).ok()
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
mod ffi {
    use std::ffi::c_char;

    #[repr(C)]
    pub(crate) struct HeartPi5PioTxHandle {
        _private: [u8; 0],
    }

    #[link(name = "heart_pi5_pio_shim", kind = "static")]
    unsafe extern "C" {
        pub(crate) fn heart_pi5_pio_tx_open(
            out_base_gpio: u32,
            out_pin_count: u32,
            clock_gpio: u32,
            clock_divider: f32,
            dma_buffer_size: u32,
            dma_buffer_count: u32,
            out_handle: *mut *mut HeartPi5PioTxHandle,
            error_buf: *mut c_char,
            error_buf_len: usize,
        ) -> i32;
        pub(crate) fn heart_pi5_pio_tx_stream(
            handle: *mut HeartPi5PioTxHandle,
            data: *const u8,
            data_bytes: u32,
            error_buf: *mut c_char,
            error_buf_len: usize,
        ) -> i32;
        pub(crate) fn heart_pi5_pio_tx_close(handle: *mut HeartPi5PioTxHandle);
    }

    #[link(name = "pio")]
    unsafe extern "C" {}
}

#[cfg(test)]
pub(crate) fn default_benchmark_config(chain_length: u16) -> Pi5TransportConfig {
    Pi5TransportConfig::new(64, 64, chain_length, 1, DEFAULT_PWM_BITS)
        .expect("default Pi 5 transport benchmark config should be valid")
}
