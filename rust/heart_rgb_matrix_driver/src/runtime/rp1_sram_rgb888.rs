use std::fs::{File, OpenOptions};
use std::os::fd::AsRawFd;
use std::os::unix::fs::OpenOptionsExt;
use std::sync::atomic::{fence, Ordering};
use std::time::Duration;

use super::backend::MatrixBackend;
use super::config::{MatrixConfigNative, WiringProfile};
use super::frame::FrameBuffer;

const RP1_SRAM_HOST_BASE: libc::off_t = 0x1f00400000;
const RP1_SRAM_MAP_SIZE: usize = 0x10000;
const DEFAULT_SOURCE_OFFSET: usize = 0xc000;
const SUPPORTED_WIDTH: usize = 64;
const SUPPORTED_HEIGHT: usize = 64;
const ROWPAIRS: usize = SUPPORTED_HEIGHT / 2;
const COLS: usize = SUPPORTED_WIDTH;
const FRAME_WORDS: usize = ROWPAIRS * COLS * 2;
const FRAME_BYTES: usize = FRAME_WORDS * std::mem::size_of::<u32>();
const DEFAULT_COLOR_PROFILE: ColorProfile = ColorProfile::HzellerCie1931;
const DEFAULT_HZELLER_BRIGHTNESS_PERCENT: u8 = 100;
const DEFAULT_LEGACY_BRIGHTNESS: f32 = 0.72;
const DEFAULT_LEGACY_CONTRAST: f32 = 1.35;
const DEFAULT_LEGACY_SATURATION: f32 = 1.40;
const DEFAULT_LEGACY_GAMMA: f32 = 1.30;

#[derive(Debug)]
pub(crate) struct Rp1SramRgb888Backend {
    _device: File,
    mapping: MmapMapping,
    source_offset: usize,
    frame_words: Vec<u32>,
    adjustment: ColorAdjustment,
}

impl Rp1SramRgb888Backend {
    pub(crate) fn new(config: &MatrixConfigNative) -> Result<Self, String> {
        if config.wiring != WiringProfile::AdafruitHatPwm {
            return Err(
                "RP1 SRAM RGB888 backend only supports the Adafruit HAT PWM mapping.".to_string(),
            );
        }
        let width = usize::try_from(config.width()?)
            .map_err(|_| "RP1 SRAM RGB888 width exceeds host usize.".to_string())?;
        let height = usize::try_from(config.height()?)
            .map_err(|_| "RP1 SRAM RGB888 height exceeds host usize.".to_string())?;
        if width != SUPPORTED_WIDTH || height != SUPPORTED_HEIGHT {
            return Err(format!(
                "RP1 SRAM RGB888 backend currently requires {SUPPORTED_WIDTH}x{SUPPORTED_HEIGHT}, received {width}x{height}."
            ));
        }

        let source_offset = parse_env_usize("HEART_PI5_SRAM_RGB888_OFFSET", DEFAULT_SOURCE_OFFSET);
        if source_offset >= RP1_SRAM_MAP_SIZE || source_offset + FRAME_BYTES > RP1_SRAM_MAP_SIZE {
            return Err(format!(
                "RP1 SRAM RGB888 offset 0x{source_offset:x} plus frame bytes {FRAME_BYTES} exceeds mapped SRAM size 0x{RP1_SRAM_MAP_SIZE:x}."
            ));
        }

        let device = OpenOptions::new()
            .read(true)
            .write(true)
            .custom_flags(libc::O_CLOEXEC | libc::O_SYNC)
            .open("/dev/mem")
            .map_err(|error| format!("open /dev/mem for RP1 SRAM RGB888 backend: {error}"))?;
        let mapping = MmapMapping::new(device.as_raw_fd(), RP1_SRAM_MAP_SIZE)?;
        Ok(Self {
            _device: device,
            mapping,
            source_offset,
            frame_words: vec![0; FRAME_WORDS],
            adjustment: ColorAdjustment::from_env(),
        })
    }
}

impl MatrixBackend for Rp1SramRgb888Backend {
    fn refresh_interval(&self) -> Duration {
        Duration::ZERO
    }

    fn owns_refresh_loop(&self) -> bool {
        true
    }

    fn render(&mut self, frame: &FrameBuffer) -> Result<(), String> {
        pack_rgb888_rowpair_words(
            &mut self.frame_words,
            frame.as_slice(),
            SUPPORTED_WIDTH,
            SUPPORTED_HEIGHT,
            self.adjustment,
        )?;
        unsafe {
            std::ptr::copy_nonoverlapping(
                self.frame_words.as_ptr().cast::<u8>(),
                self.mapping.as_mut_ptr().add(self.source_offset),
                FRAME_BYTES,
            );
        }
        fence(Ordering::SeqCst);
        Ok(())
    }
}

#[derive(Clone, Copy, Debug)]
struct ColorAdjustment {
    profile: ColorProfile,
    brightness_percent: u8,
    legacy_brightness: f32,
    legacy_contrast: f32,
    legacy_saturation: f32,
    legacy_gamma: f32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ColorProfile {
    HzellerCie1931,
    HzellerDirect,
    Legacy,
}

impl ColorAdjustment {
    fn from_env() -> Self {
        let profile = parse_color_profile("HEART_PI5_SRAM_RGB888_COLOR_PROFILE");
        Self {
            profile,
            brightness_percent: parse_env_brightness_percent(
                "HEART_PI5_SRAM_RGB888_BRIGHTNESS",
                DEFAULT_HZELLER_BRIGHTNESS_PERCENT,
            ),
            legacy_brightness: parse_env_f32(
                "HEART_PI5_SRAM_RGB888_BRIGHTNESS",
                DEFAULT_LEGACY_BRIGHTNESS,
            ),
            legacy_contrast: parse_env_f32(
                "HEART_PI5_SRAM_RGB888_CONTRAST",
                DEFAULT_LEGACY_CONTRAST,
            ),
            legacy_saturation: parse_env_f32(
                "HEART_PI5_SRAM_RGB888_SATURATION",
                DEFAULT_LEGACY_SATURATION,
            ),
            legacy_gamma: parse_env_f32("HEART_PI5_SRAM_RGB888_GAMMA", DEFAULT_LEGACY_GAMMA),
        }
    }

    fn apply(self, r: u8, g: u8, b: u8) -> (u8, u8, u8) {
        match self.profile {
            ColorProfile::HzellerCie1931 => (
                cie1931_map_color(self.brightness_percent, r),
                cie1931_map_color(self.brightness_percent, g),
                cie1931_map_color(self.brightness_percent, b),
            ),
            ColorProfile::HzellerDirect => (
                direct_map_color(self.brightness_percent, r),
                direct_map_color(self.brightness_percent, g),
                direct_map_color(self.brightness_percent, b),
            ),
            ColorProfile::Legacy => legacy_adjust(
                r,
                g,
                b,
                self.legacy_brightness,
                self.legacy_contrast,
                self.legacy_saturation,
                self.legacy_gamma,
            ),
        }
    }
}

#[derive(Debug)]
struct MmapMapping {
    addr: *mut u8,
    len: usize,
}

unsafe impl Send for MmapMapping {}

impl MmapMapping {
    fn new(fd: i32, len: usize) -> Result<Self, String> {
        let addr = unsafe {
            libc::mmap(
                std::ptr::null_mut(),
                len,
                libc::PROT_READ | libc::PROT_WRITE,
                libc::MAP_SHARED,
                fd,
                RP1_SRAM_HOST_BASE,
            )
        };
        if addr == libc::MAP_FAILED {
            return Err(format!(
                "mmap RP1 SRAM host window: {}",
                std::io::Error::last_os_error()
            ));
        }
        Ok(Self {
            addr: addr.cast::<u8>(),
            len,
        })
    }

    fn as_mut_ptr(&self) -> *mut u8 {
        self.addr
    }
}

impl Drop for MmapMapping {
    fn drop(&mut self) {
        if !self.addr.is_null() && self.len != 0 {
            let _ = unsafe { libc::munmap(self.addr.cast::<libc::c_void>(), self.len) };
        }
    }
}

fn pack_rgb888_rowpair_words(
    destination: &mut [u32],
    frame: &[u8],
    width: usize,
    height: usize,
    adjustment: ColorAdjustment,
) -> Result<(), String> {
    let expected_frame_bytes = width
        .checked_mul(height)
        .and_then(|pixels| pixels.checked_mul(3))
        .ok_or_else(|| "RP1 SRAM RGB888 geometry overflowed.".to_string())?;
    if frame.len() != expected_frame_bytes {
        return Err(format!(
            "RP1 SRAM RGB888 expected {expected_frame_bytes} RGB888 bytes but received {}.",
            frame.len()
        ));
    }
    if width != SUPPORTED_WIDTH || height != SUPPORTED_HEIGHT {
        return Err(format!(
            "RP1 SRAM RGB888 packer requires {SUPPORTED_WIDTH}x{SUPPORTED_HEIGHT}, received {width}x{height}."
        ));
    }
    if destination.len() != FRAME_WORDS {
        return Err(format!(
            "RP1 SRAM RGB888 destination expected {FRAME_WORDS} words but received {}.",
            destination.len()
        ));
    }

    let mut word_index = 0;
    for row in 0..ROWPAIRS {
        for col in 0..COLS {
            for y in [row, row + ROWPAIRS] {
                let pixel_offset = ((y * width) + col) * 3;
                let (r, g, b) = adjustment.apply(
                    frame[pixel_offset],
                    frame[pixel_offset + 1],
                    frame[pixel_offset + 2],
                );
                destination[word_index] = pack_rgb888(r, g, b);
                word_index += 1;
            }
        }
    }
    Ok(())
}

fn pack_rgb888(r: u8, g: u8, b: u8) -> u32 {
    u32::from(r) | (u32::from(g) << 8) | (u32::from(b) << 16)
}

fn cie1931_map_color(brightness_percent: u8, color: u8) -> u8 {
    let value = f32::from(color) * f32::from(brightness_percent) / 255.0;
    let luminance = if value <= 8.0 {
        value / 902.3
    } else {
        ((value + 16.0) / 116.0).powi(3)
    };
    (255.0 * luminance).round().clamp(0.0, 255.0) as u8
}

fn direct_map_color(brightness_percent: u8, color: u8) -> u8 {
    ((u16::from(color) * u16::from(brightness_percent)) / 100) as u8
}

fn legacy_adjust(
    r: u8,
    g: u8,
    b: u8,
    brightness: f32,
    contrast: f32,
    saturation: f32,
    gamma: f32,
) -> (u8, u8, u8) {
    let mut r = adjust_contrast(f32::from(r), contrast);
    let mut g = adjust_contrast(f32::from(g), contrast);
    let mut b = adjust_contrast(f32::from(b), contrast);
    let luminance = (0.299 * r) + (0.587 * g) + (0.114 * b);
    r = luminance + ((r - luminance) * saturation);
    g = luminance + ((g - luminance) * saturation);
    b = luminance + ((b - luminance) * saturation);
    (
        apply_gamma_and_brightness(r, gamma, brightness),
        apply_gamma_and_brightness(g, gamma, brightness),
        apply_gamma_and_brightness(b, gamma, brightness),
    )
}

fn adjust_contrast(value: f32, contrast: f32) -> f32 {
    ((value - 128.0) * contrast) + 128.0
}

fn apply_gamma_and_brightness(value: f32, gamma: f32, brightness: f32) -> u8 {
    let normalized = (value / 255.0).clamp(0.0, 1.0);
    let adjusted = normalized.powf(gamma.max(0.001)) * 255.0 * brightness;
    adjusted.round().clamp(0.0, 255.0) as u8
}

fn parse_env_f32(key: &str, default: f32) -> f32 {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse::<f32>().ok())
        .filter(|value| value.is_finite() && *value >= 0.0)
        .unwrap_or(default)
}

fn parse_color_profile(key: &str) -> ColorProfile {
    match std::env::var(key)
        .unwrap_or_else(|_| "hzeller-cie1931".to_string())
        .trim()
        .to_ascii_lowercase()
        .as_str()
    {
        "" | "hzeller-cie1931" | "cie1931" | "cie" | "hzeller" => ColorProfile::HzellerCie1931,
        "hzeller-direct" | "direct" | "linear" => ColorProfile::HzellerDirect,
        "legacy" => ColorProfile::Legacy,
        _ => DEFAULT_COLOR_PROFILE,
    }
}

fn parse_env_brightness_percent(key: &str, default: u8) -> u8 {
    std::env::var(key)
        .ok()
        .and_then(|value| value.parse::<f32>().ok())
        .filter(|value| value.is_finite() && *value >= 0.0)
        .map(normalize_brightness_percent)
        .unwrap_or(default)
}

fn normalize_brightness_percent(value: f32) -> u8 {
    let percent = if value <= 1.0 { value * 100.0 } else { value };
    percent.round().clamp(1.0, 100.0) as u8
}

fn parse_env_usize(key: &str, default: usize) -> usize {
    std::env::var(key)
        .ok()
        .and_then(|value| parse_usize(&value))
        .unwrap_or(default)
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

    const IDENTITY_ADJUSTMENT: ColorAdjustment = ColorAdjustment {
        profile: ColorProfile::Legacy,
        brightness_percent: 100,
        legacy_brightness: 1.0,
        legacy_contrast: 1.0,
        legacy_saturation: 1.0,
        legacy_gamma: 1.0,
    };

    #[test]
    fn packs_upper_and_lower_row_pair_words_as_rgb888() {
        let mut frame = vec![0; SUPPORTED_WIDTH * SUPPORTED_HEIGHT * 3];
        write_pixel(&mut frame, 0, 0, [1, 2, 3]);
        write_pixel(&mut frame, 32, 0, [4, 5, 6]);
        write_pixel(&mut frame, 0, 1, [7, 8, 9]);
        write_pixel(&mut frame, 32, 1, [10, 11, 12]);
        let mut words = vec![0; FRAME_WORDS];

        pack_rgb888_rowpair_words(
            &mut words,
            &frame,
            SUPPORTED_WIDTH,
            SUPPORTED_HEIGHT,
            IDENTITY_ADJUSTMENT,
        )
        .expect("pack row-pair words");

        assert_eq!(words[0], 0x0003_0201);
        assert_eq!(words[1], 0x0006_0504);
        assert_eq!(words[2], 0x0009_0807);
        assert_eq!(words[3], 0x000c_0b0a);
    }

    #[test]
    fn parses_hex_offsets() {
        assert_eq!(parse_usize("0xc000"), Some(0xc000));
        assert_eq!(parse_usize("49152"), Some(0xc000));
    }

    #[test]
    fn hzeller_cie1931_profile_maps_to_rgb888_luminance_curve() {
        let adjustment = ColorAdjustment {
            profile: ColorProfile::HzellerCie1931,
            brightness_percent: 100,
            legacy_brightness: 1.0,
            legacy_contrast: 1.0,
            legacy_saturation: 1.0,
            legacy_gamma: 1.0,
        };

        assert_eq!(adjustment.apply(0, 128, 255), (0, 47, 255));
    }

    #[test]
    fn hzeller_direct_profile_scales_rgb888_channels_linearly() {
        let adjustment = ColorAdjustment {
            profile: ColorProfile::HzellerDirect,
            brightness_percent: 50,
            legacy_brightness: 1.0,
            legacy_contrast: 1.0,
            legacy_saturation: 1.0,
            legacy_gamma: 1.0,
        };

        assert_eq!(adjustment.apply(10, 128, 255), (5, 64, 127));
    }

    #[test]
    fn fractional_brightness_env_is_treated_as_percent_fraction() {
        assert_eq!(normalize_brightness_percent(0.72), 72);
        assert_eq!(normalize_brightness_percent(72.0), 72);
        assert_eq!(normalize_brightness_percent(0.0), 1);
        assert_eq!(normalize_brightness_percent(150.0), 100);
    }

    fn write_pixel(frame: &mut [u8], row: usize, col: usize, rgb: [u8; 3]) {
        let offset = ((row * SUPPORTED_WIDTH) + col) * 3;
        frame[offset..offset + 3].copy_from_slice(&rgb);
    }
}
