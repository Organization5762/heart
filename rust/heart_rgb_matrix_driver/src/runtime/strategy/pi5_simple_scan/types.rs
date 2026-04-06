use std::time::{Duration, Instant};

use super::experimental::{build_raw_group_words_for_rgba, raw_group_word_count};
use crate::runtime::config::{expected_rgba_size, WiringProfile};
use crate::runtime::pi5_pinout::Pi5ScanPinout;
use crate::runtime::tuning::runtime_tuning;

fn probe_log(message: impl AsRef<str>) {
    if std::env::var("HEART_PI5_SIMPLE_PROBE_LOG")
        .map(|value| value != "0")
        .unwrap_or(true)
    {
        eprintln!("[pi5_simple_probe::scan] {}", message.as_ref());
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Pi5SimpleProbeMode {
    RawBytePull,
}

impl Pi5SimpleProbeMode {
    pub fn pack_rgba_frame(
        self,
        config: &Pi5ScanConfig,
        rgba: &[u8],
    ) -> Result<(PackedScanFrame, PackedScanFrameStats), String> {
        let _ = self;
        PackedScanFrame::pack_rgba(config, rgba)
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Pi5ScanTiming {
    pub(crate) clock_divider: f32,
    pub(crate) post_addr_ticks: u32,
    pub(crate) latch_ticks: u32,
    pub(crate) post_latch_ticks: u32,
    pub(crate) simple_clock_hold_ticks: u32,
}

impl Default for Pi5ScanTiming {
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

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Pi5ScanConfig {
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    pwm_bits: u8,
    lsb_dwell_ticks: u32,
    timing: Pi5ScanTiming,
    pinout: Pi5ScanPinout,
}

impl Pi5ScanConfig {
    pub fn from_matrix_config(
        wiring: WiringProfile,
        panel_rows: u16,
        panel_cols: u16,
        chain_length: u16,
        parallel: u8,
    ) -> Result<Self, String> {
        let tuning = runtime_tuning();
        let config = Self {
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            pwm_bits: tuning.pi5_simple_scan_default_pwm_bits,
            lsb_dwell_ticks: tuning.pi5_simple_scan_lsb_dwell_ticks,
            timing: Pi5ScanTiming {
                clock_divider: tuning.pi5_simple_scan_clock_divider,
                post_addr_ticks: tuning.pi5_simple_scan_post_addr_ticks,
                latch_ticks: tuning.pi5_simple_scan_latch_ticks,
                post_latch_ticks: tuning.pi5_simple_scan_post_latch_ticks,
                simple_clock_hold_ticks: tuning.pi5_simple_scan_clock_hold_ticks,
            },
            pinout: Pi5ScanPinout::for_wiring(wiring)?,
        };
        config.validate()?;
        Ok(config)
    }

    pub fn with_pwm_bits(mut self, pwm_bits: u8) -> Result<Self, String> {
        probe_log(format!("with_pwm_bits old={} new={}", self.pwm_bits, pwm_bits));
        self.pwm_bits = pwm_bits;
        self.validate()?;
        Ok(self)
    }

    pub fn with_clock_divider(mut self, clock_divider: f32) -> Result<Self, String> {
        probe_log(format!("with_clock_divider old={} new={}", self.timing.clock_divider, clock_divider));
        self.timing.clock_divider = clock_divider;
        self.validate()?;
        Ok(self)
    }

    pub fn width(&self) -> Result<u32, String> {
        u32::from(self.panel_cols)
            .checked_mul(u32::from(self.chain_length))
            .ok_or_else(|| "Pi 5 simple scan width exceeds supported dimensions.".to_string())
    }

    pub fn height(&self) -> Result<u32, String> {
        u32::from(self.panel_rows)
            .checked_mul(u32::from(self.parallel))
            .ok_or_else(|| "Pi 5 simple scan height exceeds supported dimensions.".to_string())
    }

    pub fn row_pairs(&self) -> Result<usize, String> {
        let height = usize::try_from(self.height()?)
            .map_err(|_| "Pi 5 simple scan height exceeds host usize.".to_string())?;
        Ok(height / 2)
    }

    pub(crate) fn pinout(&self) -> Pi5ScanPinout {
        self.pinout
    }

    pub fn timing(&self) -> Pi5ScanTiming {
        self.timing
    }

    pub(crate) fn pwm_bits(&self) -> u8 {
        self.pwm_bits
    }

    pub(crate) fn lsb_dwell_ticks(&self) -> u32 {
        self.lsb_dwell_ticks
    }

    fn validate(&self) -> Result<(), String> {
        if self.parallel != 1 {
            return Err(format!("Pi 5 simple scan supports parallel=1, received {}.", self.parallel));
        }
        if !matches!(self.panel_rows, 16 | 32 | 64) {
            return Err(format!("Unsupported panel_rows {}. Expected 16, 32, or 64.", self.panel_rows));
        }
        if !matches!(self.panel_cols, 32 | 64) {
            return Err(format!("Unsupported panel_cols {}. Expected 32 or 64.", self.panel_cols));
        }
        if self.chain_length == 0 {
            return Err("chain_length must be at least 1.".to_string());
        }
        if self.pwm_bits == 0 || self.pwm_bits > 16 {
            return Err(format!("Unsupported pwm_bits {}. Expected 1 through 16.", self.pwm_bits));
        }
        if self.lsb_dwell_ticks == 0 {
            return Err("lsb_dwell_ticks must be at least 1.".to_string());
        }
        if !self.timing.clock_divider.is_finite() || self.timing.clock_divider <= 0.0 {
            return Err("clock_divider must be a positive finite value.".to_string());
        }
        if self.timing.post_addr_ticks == 0
            || self.timing.latch_ticks == 0
            || self.timing.post_latch_ticks == 0
            || self.timing.simple_clock_hold_ticks == 0
        {
            return Err("All timing ticks must be at least 1.".to_string());
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PackedScanFrameStats {
    pub word_count: usize,
    pub pack_duration: Duration,
}

#[derive(Clone, Debug)]
pub struct PackedScanFrame {
    words: Vec<u32>,
}

impl PackedScanFrame {
    pub fn pack_rgba(config: &Pi5ScanConfig, rgba: &[u8]) -> Result<(Self, PackedScanFrameStats), String> {
        let width = usize::try_from(config.width()?)
            .map_err(|_| "Pi 5 simple scan width exceeds host usize.".to_string())?;
        let height = usize::try_from(config.height()?)
            .map_err(|_| "Pi 5 simple scan height exceeds host usize.".to_string())?;
        let expected_size = expected_rgba_size(width as u32, height as u32)
            .ok_or_else(|| "Pi 5 simple scan geometry exceeds supported RGBA size.".to_string())?;
        if rgba.len() != expected_size {
            return Err(format!("Pi 5 simple scan expected {expected_size} RGBA bytes but received {}.", rgba.len()));
        }

        let row_pairs = config.row_pairs()?;
        let started = Instant::now();
        let mut words =
            Vec::with_capacity(row_pairs * usize::from(config.pwm_bits()) * raw_group_word_count(config, width, 0)?);
        for row_pair in 0..row_pairs {
            for plane_index in 0..usize::from(config.pwm_bits()) {
                words.extend(build_raw_group_words_for_rgba(config, rgba, row_pair, plane_index)?);
            }
        }

        Ok((
            Self { words: words.clone() },
            PackedScanFrameStats {
                word_count: words.len(),
                pack_duration: started.elapsed(),
            },
        ))
    }

    pub fn as_bytes(&self) -> &[u8] {
        unsafe {
            std::slice::from_raw_parts(
                self.words.as_ptr().cast::<u8>(),
                self.words.len() * std::mem::size_of::<u32>(),
            )
        }
    }

    pub fn as_words(&self) -> &[u32] {
        &self.words
    }

    pub fn word_count(&self) -> usize {
        self.words.len()
    }

    pub fn repeated(&self, copies: usize) -> Result<Self, String> {
        if copies <= 1 {
            return Ok(self.clone());
        }
        let total_words = self
            .words
            .len()
            .checked_mul(copies)
            .ok_or_else(|| "Pi 5 packed frame repeat overflowed.".to_string())?;
        let mut words = Vec::with_capacity(total_words);
        for _ in 0..copies {
            words.extend_from_slice(&self.words);
        }
        Ok(Self { words })
    }
}
