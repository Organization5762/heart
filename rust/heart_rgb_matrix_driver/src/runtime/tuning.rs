use std::env;
use std::sync::OnceLock;

/*
 * Runtime tuning lives here instead of being scattered across backend-, queue-,
 * and packer-specific files. That keeps two invariants easy to maintain:
 *
 *   1. knobs that intentionally affect behavior are easy to audit
 *   2. every supported override uses one HEART_* environment variable
 *
 * These values are cached on first use. Changing an environment variable after
 * the runtime has already touched this module will not affect the running
 * process.
 */

const HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS_DEFAULT: u8 = 11;
const HEART_PI5_SIMPLE_SCAN_LSB_DWELL_TICKS_DEFAULT: u32 = 1;
const HEART_PI5_SIMPLE_SCAN_CLOCK_DIVIDER_DEFAULT: f32 = 200.0 / 27.0;
const HEART_PI5_SIMPLE_SCAN_POST_ADDR_TICKS_DEFAULT: u32 = 5;
const HEART_PI5_SIMPLE_SCAN_LATCH_TICKS_DEFAULT: u32 = 1;
const HEART_PI5_SIMPLE_SCAN_POST_LATCH_TICKS_DEFAULT: u32 = 1;
const HEART_PI5_SIMPLE_SCAN_CLOCK_HOLD_TICKS_DEFAULT: u32 = 1;

#[derive(Clone, Copy, Debug)]
pub(crate) struct RuntimeTuning {
    /* Default PWM bit depth used when building a Pi 5 scan config. */
    pub(crate) pi5_simple_scan_default_pwm_bits: u8,
    /* Default LSB dwell used when building a Pi 5 scan config. */
    pub(crate) pi5_simple_scan_lsb_dwell_ticks: u32,
    /* Default PIO clock divider used when building a Pi 5 scan config. */
    pub(crate) pi5_simple_scan_clock_divider: f32,
    /* Default address-settle ticks used when building a Pi 5 scan config. */
    pub(crate) pi5_simple_scan_post_addr_ticks: u32,
    /* Default latch pulse width used when building a Pi 5 scan config. */
    pub(crate) pi5_simple_scan_latch_ticks: u32,
    /* Default post-latch blanking ticks used when building a Pi 5 scan config. */
    pub(crate) pi5_simple_scan_post_latch_ticks: u32,
    /* Per-column low/high hold count for the simple explicit-word transport. */
    pub(crate) pi5_simple_scan_clock_hold_ticks: u32,
}

static HEART_RUNTIME_TUNING: OnceLock<RuntimeTuning> = OnceLock::new();

pub(crate) fn runtime_tuning() -> &'static RuntimeTuning {
    HEART_RUNTIME_TUNING.get_or_init(|| RuntimeTuning {
        pi5_simple_scan_default_pwm_bits: parse_env_u8(
            "HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS",
            HEART_PI5_SIMPLE_SCAN_DEFAULT_PWM_BITS_DEFAULT,
            |value| (1..=16).contains(&value),
        ),
        pi5_simple_scan_lsb_dwell_ticks: parse_env_u32(
            "HEART_PI5_SIMPLE_SCAN_LSB_DWELL_TICKS",
            HEART_PI5_SIMPLE_SCAN_LSB_DWELL_TICKS_DEFAULT,
            |value| value > 0,
        ),
        pi5_simple_scan_clock_divider: parse_env_f32(
            "HEART_PI5_SIMPLE_SCAN_CLOCK_DIVIDER",
            HEART_PI5_SIMPLE_SCAN_CLOCK_DIVIDER_DEFAULT,
            |value| value.is_finite() && value > 0.0,
        ),
        pi5_simple_scan_post_addr_ticks: parse_env_u32(
            "HEART_PI5_SIMPLE_SCAN_POST_ADDR_TICKS",
            HEART_PI5_SIMPLE_SCAN_POST_ADDR_TICKS_DEFAULT,
            |value| value > 0,
        ),
        pi5_simple_scan_latch_ticks: parse_env_u32(
            "HEART_PI5_SIMPLE_SCAN_LATCH_TICKS",
            HEART_PI5_SIMPLE_SCAN_LATCH_TICKS_DEFAULT,
            |value| value > 0,
        ),
        pi5_simple_scan_post_latch_ticks: parse_env_u32(
            "HEART_PI5_SIMPLE_SCAN_POST_LATCH_TICKS",
            HEART_PI5_SIMPLE_SCAN_POST_LATCH_TICKS_DEFAULT,
            |value| value > 0,
        ),
        pi5_simple_scan_clock_hold_ticks: parse_env_u32(
            "HEART_PI5_SIMPLE_SCAN_CLOCK_HOLD_TICKS",
            HEART_PI5_SIMPLE_SCAN_CLOCK_HOLD_TICKS_DEFAULT,
            |value| value > 0,
        ),
    })
}

fn parse_env_u32(key: &str, default: u32, validator: impl Fn(u32) -> bool) -> u32 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .filter(|value| validator(*value))
        .unwrap_or(default)
}

fn parse_env_u8(key: &str, default: u8, validator: impl Fn(u8) -> bool) -> u8 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse::<u8>().ok())
        .filter(|value| validator(*value))
        .unwrap_or(default)
}

fn parse_env_f32(key: &str, default: f32, validator: impl Fn(f32) -> bool) -> f32 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse::<f32>().ok())
        .filter(|value| validator(*value))
        .unwrap_or(default)
}
