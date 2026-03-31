use std::env;
use std::sync::OnceLock;
use std::time::Duration;

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

const HEART_MATRIX_PI4_REFRESH_INTERVAL_MS_DEFAULT: u64 = 16;
const HEART_MATRIX_SIMULATED_REFRESH_INTERVAL_MS_DEFAULT: u64 = 16;
const HEART_MATRIX_MAX_PENDING_FRAMES_DEFAULT: usize = 2;
const HEART_PARALLEL_COLOR_REMAP_THRESHOLD_BYTES_DEFAULT: usize = 16_384;
const HEART_PI5_SCAN_DEFAULT_DMA_BUFFER_COUNT_DEFAULT: u32 = 2;
const HEART_PI5_SCAN_DEFAULT_PWM_BITS_DEFAULT: u8 = 11;
const HEART_PI5_SCAN_INTERNAL_BLANK_RUN_MIN_PIXELS_DEFAULT: usize = 5;
const HEART_PI5_SCAN_PACK_PARALLEL_THRESHOLD_WORDS_DEFAULT: usize = 8_192;
const HEART_PI5_SCAN_MAX_DMA_BUFFER_BYTES_DEFAULT: usize = 22_880;
const HEART_PI5_SCAN_RESIDENT_LOOP_RESUBMIT_PAUSE_US_DEFAULT: u64 = 100;

#[allow(dead_code)]
#[derive(Clone, Copy, Debug)]
pub(crate) struct RuntimeTuning {
    /* Software refresh cadence for the placeholder Pi 4 backend. */
    pub(crate) matrix_pi4_refresh_interval_ms: u64,
    /* Software refresh cadence for the simulated non-Pi backend. */
    pub(crate) matrix_simulated_refresh_interval_ms: u64,
    /* Queue depth before the oldest pending frame is dropped. */
    pub(crate) matrix_max_pending_frames: usize,
    /* Minimum RGBA byte count before channel remap work uses Rayon. */
    pub(crate) parallel_color_remap_threshold_bytes: usize,
    /* rp1-pio DMA buffer count for the raw userspace Pi 5 transport. */
    pub(crate) pi5_scan_default_dma_buffer_count: u32,
    /* Default PWM bit depth used when building a Pi 5 scan config. */
    pub(crate) pi5_scan_default_pwm_bits: u8,
    /* Small blank gaps stay inline; larger ones become explicit blank spans. */
    pub(crate) pi5_scan_internal_blank_run_min_pixels: usize,
    /* Minimum packed word count before scan packing parallelizes with Rayon. */
    pub(crate) pi5_scan_pack_parallel_threshold_words: usize,
    /* Cap for the rp1-pio transfer buffer used by the raw userspace transport. */
    pub(crate) pi5_scan_max_dma_buffer_bytes: usize,
    /* Pause between resident-frame replays in the async userspace transport. */
    pub(crate) pi5_scan_resident_loop_resubmit_pause: Duration,
}

static HEART_RUNTIME_TUNING: OnceLock<RuntimeTuning> = OnceLock::new();

pub(crate) fn runtime_tuning() -> &'static RuntimeTuning {
    HEART_RUNTIME_TUNING.get_or_init(|| RuntimeTuning {
        matrix_pi4_refresh_interval_ms: parse_env_u64(
            "HEART_MATRIX_PI4_REFRESH_INTERVAL_MS",
            HEART_MATRIX_PI4_REFRESH_INTERVAL_MS_DEFAULT,
            |value| value > 0,
        ),
        matrix_simulated_refresh_interval_ms: parse_env_u64(
            "HEART_MATRIX_SIMULATED_REFRESH_INTERVAL_MS",
            HEART_MATRIX_SIMULATED_REFRESH_INTERVAL_MS_DEFAULT,
            |value| value > 0,
        ),
        matrix_max_pending_frames: parse_env_usize(
            "HEART_MATRIX_MAX_PENDING_FRAMES",
            HEART_MATRIX_MAX_PENDING_FRAMES_DEFAULT,
            |value| value > 0,
        ),
        parallel_color_remap_threshold_bytes: parse_env_usize(
            "HEART_PARALLEL_COLOR_REMAP_THRESHOLD_BYTES",
            HEART_PARALLEL_COLOR_REMAP_THRESHOLD_BYTES_DEFAULT,
            |value| value > 0,
        ),
        pi5_scan_default_dma_buffer_count: parse_env_u32(
            "HEART_PI5_SCAN_DEFAULT_DMA_BUFFER_COUNT",
            HEART_PI5_SCAN_DEFAULT_DMA_BUFFER_COUNT_DEFAULT,
            |value| value > 0,
        ),
        pi5_scan_default_pwm_bits: parse_env_u8(
            "HEART_PI5_SCAN_DEFAULT_PWM_BITS",
            HEART_PI5_SCAN_DEFAULT_PWM_BITS_DEFAULT,
            |value| (1..=16).contains(&value),
        ),
        pi5_scan_internal_blank_run_min_pixels: parse_env_usize(
            "HEART_PI5_SCAN_INTERNAL_BLANK_RUN_MIN_PIXELS",
            HEART_PI5_SCAN_INTERNAL_BLANK_RUN_MIN_PIXELS_DEFAULT,
            |value| value > 0,
        ),
        pi5_scan_pack_parallel_threshold_words: parse_env_usize(
            "HEART_PI5_SCAN_PACK_PARALLEL_THRESHOLD_WORDS",
            HEART_PI5_SCAN_PACK_PARALLEL_THRESHOLD_WORDS_DEFAULT,
            |value| value > 0,
        ),
        pi5_scan_max_dma_buffer_bytes: parse_env_usize(
            "HEART_PI5_SCAN_MAX_DMA_BUFFER_BYTES",
            HEART_PI5_SCAN_MAX_DMA_BUFFER_BYTES_DEFAULT,
            |value| value > 0,
        ),
        pi5_scan_resident_loop_resubmit_pause: Duration::from_micros(parse_env_u64(
            "HEART_PI5_SCAN_RESIDENT_LOOP_RESUBMIT_PAUSE_US",
            HEART_PI5_SCAN_RESIDENT_LOOP_RESUBMIT_PAUSE_US_DEFAULT,
            |_| true,
        )),
    })
}

pub(crate) fn frame_pool_size() -> usize {
    runtime_tuning()
        .matrix_max_pending_frames
        .saturating_add(1)
}

fn parse_env_u64(
    key: &str,
    default: u64,
    validator: impl Fn(u64) -> bool,
) -> u64 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .filter(|value| validator(*value))
        .unwrap_or(default)
}

fn parse_env_u32(
    key: &str,
    default: u32,
    validator: impl Fn(u32) -> bool,
) -> u32 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .filter(|value| validator(*value))
        .unwrap_or(default)
}

fn parse_env_u8(
    key: &str,
    default: u8,
    validator: impl Fn(u8) -> bool,
) -> u8 {
    env::var(key)
        .ok()
        .and_then(|value| value.parse::<u8>().ok())
        .filter(|value| validator(*value))
        .unwrap_or(default)
}

fn parse_env_usize(
    key: &str,
    default: usize,
    validator: impl Fn(usize) -> bool,
) -> usize {
    env::var(key)
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .filter(|value| validator(*value))
        .unwrap_or(default)
}
