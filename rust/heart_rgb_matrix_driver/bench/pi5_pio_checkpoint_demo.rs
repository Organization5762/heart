#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{
    estimate_simple_hub75_frame_timing, PackedScanFrame, PackedScanFrameStats,
    Pi5KernelResidentLoop, Pi5PioScanTransport, Pi5ScanConfig, Pi5ScanFormat, Pi5ScanTiming,
    WiringProfile,
};
use std::env;
use std::process::ExitCode;
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

const DEFAULT_BURST_COPIES: usize = 8;
const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_CLOCK_DIVIDER: f32 = 20.0;
const DEFAULT_COLOR_INTERVAL_MS: u64 = 200;
const DEFAULT_HARDWARE_MAPPING: WiringProfile = WiringProfile::AdafruitHatPwm;
const DEFAULT_HOLD_SECONDS_PER_CHECKPOINT: f32 = 3.0;
const DEFAULT_LATCH_TICKS: u32 = 1;
const DEFAULT_LSB_DWELL_TICKS: u32 = 64;
const DEFAULT_OPTIMIZED_HARDWARE_MAPPING: WiringProfile = WiringProfile::AdafruitHatPwm;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_POST_ADDR_TICKS: u32 = 5;
const DEFAULT_POST_LATCH_TICKS: u32 = 1;
const DEFAULT_PWM_BITS: u8 = 1;
const DEFAULT_SIMPLE_CLOCK_HOLD_TICKS: u32 = 1;
const DEFAULT_SYS_CLOCK_HZ: f64 = 200_000_000.0;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum DemoCheckpoint {
    All,
    OptimizedResident,
    SimpleBurst,
    SimpleSingle,
}

impl DemoCheckpoint {
    fn as_str(self) -> &'static str {
        match self {
            Self::All => "all",
            Self::OptimizedResident => "optimized-resident",
            Self::SimpleBurst => "simple-burst",
            Self::SimpleSingle => "simple-single",
        }
    }

    fn checkpoints(self) -> &'static [Self] {
        match self {
            Self::All => &[
                Self::SimpleSingle,
                Self::SimpleBurst,
                Self::OptimizedResident,
            ],
            Self::OptimizedResident => &[Self::OptimizedResident],
            Self::SimpleBurst => &[Self::SimpleBurst],
            Self::SimpleSingle => &[Self::SimpleSingle],
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum DemoColor {
    Blue,
    Green,
    Red,
}

impl DemoColor {
    fn as_rgb(self) -> (u8, u8, u8) {
        match self {
            Self::Blue => (0, 0, 255),
            Self::Green => (0, 255, 0),
            Self::Red => (255, 0, 0),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Blue => "blue",
            Self::Green => "green",
            Self::Red => "red",
        }
    }
}

const RGB_SEQUENCE: [DemoColor; 3] = [DemoColor::Red, DemoColor::Green, DemoColor::Blue];

#[derive(Clone, Copy, Debug)]
struct DemoOptions {
    burst_copies: usize,
    chain_length: u16,
    checkpoint: DemoCheckpoint,
    clock_divider: f32,
    color_interval_ms: u64,
    hardware_mapping: WiringProfile,
    hold_seconds_per_checkpoint: f32,
    latch_ticks: u32,
    lsb_dwell_ticks: u32,
    optimized_hardware_mapping: WiringProfile,
    panel_cols: u16,
    panel_rows: u16,
    parallel: u8,
    post_addr_ticks: u32,
    post_latch_ticks: u32,
    pwm_bits: u8,
    simple_clock_hold_ticks: u32,
    sys_clock_hz: f64,
}

#[derive(Clone, Copy, Debug, Default)]
struct CheckpointSummary {
    frame_builds: u64,
    frame_bytes: usize,
    pack_word_count: usize,
    render_cycles: u64,
    reused_blocks: u64,
    submit_calls: u64,
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let options = parse_args(env::args().skip(1).collect())?;
    for checkpoint in options.checkpoint.checkpoints() {
        match checkpoint {
            DemoCheckpoint::SimpleSingle => run_simple_single_checkpoint(&options)?,
            DemoCheckpoint::SimpleBurst => run_simple_burst_checkpoint(&options)?,
            DemoCheckpoint::OptimizedResident => {
                if let Err(error) = run_optimized_resident_checkpoint(&options) {
                    if options.checkpoint == DemoCheckpoint::All {
                        println!(
                            "checkpoint={} status=skipped error={:?}",
                            checkpoint.as_str(),
                            error
                        );
                    } else {
                        return Err(error);
                    }
                }
            }
            DemoCheckpoint::All => {}
        }
    }
    Ok(())
}

fn run_simple_single_checkpoint(options: &DemoOptions) -> Result<(), String> {
    let config = build_simple_config(options, options.hardware_mapping)?;
    let timing = estimate_simple_hub75_frame_timing(&config, options.sys_clock_hz)?;
    let width = usize::try_from(config.width()?)
        .map_err(|_| "Simple checkpoint width exceeded host usize.".to_string())?;
    let height = usize::try_from(config.height()?)
        .map_err(|_| "Simple checkpoint height exceeded host usize.".to_string())?;
    let transport = Pi5PioScanTransport::new(
        config.estimated_word_count()?,
        config.pinout(),
        config.timing(),
        config.format(),
    )?;
    let checkpoint_start = Instant::now();
    let deadline =
        checkpoint_start + Duration::from_secs_f32(options.hold_seconds_per_checkpoint);
    let color_interval = Duration::from_millis(options.color_interval_ms);
    let mut summary = CheckpointSummary::default();
    let mut last_identity = None;

    println!(
        "checkpoint=simple-single wiring={:?} tick_ns={:.1} frame_hz={:.3} interval_ms={} hold_s={:.2}",
        options.hardware_mapping,
        timing.pio_tick_seconds * 1_000_000_000.0,
        timing.full_frame_hz,
        options.color_interval_ms,
        options.hold_seconds_per_checkpoint
    );

    for interval_index in 0_u64.. {
        let interval_start = checkpoint_start
            .checked_add(color_interval.saturating_mul(interval_index as u32))
            .ok_or_else(|| "Simple single interval start overflowed.".to_string())?;
        if interval_start >= deadline {
            break;
        }
        let interval_end = interval_start
            .checked_add(color_interval)
            .map(|time| time.min(deadline))
            .ok_or_else(|| "Simple single interval end overflowed.".to_string())?;
        let color = RGB_SEQUENCE[(interval_index as usize) % RGB_SEQUENCE.len()];
        let (frame, stats) = pack_solid_frame(&config, width, height, color)?;
        let identity = (0_usize, interval_index);
        let frame = Arc::new(frame);
        transport.submit_async(identity, Arc::clone(&frame))?;
        transport.wait_frame_presented(identity, 1)?;
        summary.frame_builds = summary.frame_builds.saturating_add(1);
        summary.submit_calls = summary.submit_calls.saturating_add(1);
        summary.frame_bytes = frame.as_bytes().len();
        summary.pack_word_count = stats.word_count;
        println!(
            "checkpoint=simple-single color={} rebuild={} frame_words={} frame_bytes={}",
            color.as_str(),
            summary.frame_builds,
            stats.word_count,
            summary.frame_bytes
        );
        if let Some(previous_identity) = last_identity {
            summary.reused_blocks = summary.reused_blocks.saturating_add(
                transport.active_presentation_count(previous_identity).unwrap_or(0),
            );
        }
        last_identity = Some(identity);
        if interval_end > Instant::now() {
            thread::sleep(interval_end - Instant::now());
        }
    }

    if let Some(identity) = last_identity {
        summary.render_cycles = transport.active_presentation_count(identity)?;
        transport.wait_complete()?;
    } else {
        transport.wait_complete()?;
    }

    println!(
        "checkpoint=simple-single status=ok frame_builds={} submit_calls={} retained_presentations={} frame_words={} frame_bytes={}",
        summary.frame_builds,
        summary.submit_calls,
        summary.reused_blocks,
        summary.pack_word_count,
        summary.frame_bytes
    );
    Ok(())
}

fn run_simple_burst_checkpoint(options: &DemoOptions) -> Result<(), String> {
    let config = build_simple_config(options, options.hardware_mapping)?;
    let timing = estimate_simple_hub75_frame_timing(&config, options.sys_clock_hz)?;
    let width = usize::try_from(config.width()?)
        .map_err(|_| "Simple burst checkpoint width exceeded host usize.".to_string())?;
    let height = usize::try_from(config.height()?)
        .map_err(|_| "Simple burst checkpoint height exceeded host usize.".to_string())?;
    let max_words = config
        .estimated_word_count()?
        .checked_mul(options.burst_copies)
        .ok_or_else(|| "Simple burst transport size overflowed.".to_string())?;
    let transport = Pi5PioScanTransport::new(
        max_words,
        config.pinout(),
        config.timing(),
        config.format(),
    )?;
    let checkpoint_start = Instant::now();
    let deadline =
        checkpoint_start + Duration::from_secs_f32(options.hold_seconds_per_checkpoint);
    let color_interval = Duration::from_millis(options.color_interval_ms);
    let mut summary = CheckpointSummary::default();
    let mut last_identity = None;

    println!(
        "checkpoint=simple-burst wiring={:?} burst_copies={} tick_ns={:.1} frame_hz={:.3} interval_ms={} hold_s={:.2}",
        options.hardware_mapping,
        options.burst_copies,
        timing.pio_tick_seconds * 1_000_000_000.0,
        timing.full_frame_hz,
        options.color_interval_ms,
        options.hold_seconds_per_checkpoint
    );

    for interval_index in 0_u64.. {
        let interval_start = checkpoint_start
            .checked_add(color_interval.saturating_mul(interval_index as u32))
            .ok_or_else(|| "Simple burst interval start overflowed.".to_string())?;
        if interval_start >= deadline {
            break;
        }
        let interval_end = interval_start
            .checked_add(color_interval)
            .map(|time| time.min(deadline))
            .ok_or_else(|| "Simple burst interval end overflowed.".to_string())?;
        let color = RGB_SEQUENCE[(interval_index as usize) % RGB_SEQUENCE.len()];
        let (frame, stats) = pack_solid_frame(&config, width, height, color)?;
        let burst = Arc::new(frame.repeated(options.burst_copies)?);
        let identity = (0_usize, interval_index);
        transport.submit_async(identity, Arc::clone(&burst))?;
        transport.wait_frame_presented(identity, 1)?;
        summary.frame_builds = summary.frame_builds.saturating_add(1);
        summary.submit_calls = summary.submit_calls.saturating_add(1);
        summary.pack_word_count = burst.word_count();
        summary.frame_bytes = burst.as_bytes().len();
        println!(
            "checkpoint=simple-burst color={} rebuild={} base_words={} burst_words={} burst_bytes={}",
            color.as_str(),
            summary.frame_builds,
            stats.word_count,
            summary.pack_word_count,
            summary.frame_bytes
        );
        if let Some(previous_identity) = last_identity {
            summary.reused_blocks = summary.reused_blocks.saturating_add(
                transport.active_presentation_count(previous_identity).unwrap_or(0),
            );
        }
        last_identity = Some(identity);
        if interval_end > Instant::now() {
            thread::sleep(interval_end - Instant::now());
        }
    }

    if let Some(identity) = last_identity {
        summary.render_cycles = transport
            .active_presentation_count(identity)?
            .saturating_mul(options.burst_copies as u64);
        transport.wait_complete()?;
    } else {
        transport.wait_complete()?;
    }

    println!(
        "checkpoint=simple-burst status=ok frame_builds={} submit_calls={} retained_presentations={} logical_frame_copies={} burst_words={} burst_bytes={}",
        summary.frame_builds,
        summary.submit_calls,
        summary.reused_blocks,
        summary.render_cycles,
        summary.pack_word_count,
        summary.frame_bytes
    );
    Ok(())
}

fn run_optimized_resident_checkpoint(options: &DemoOptions) -> Result<(), String> {
    let config = build_optimized_config(options, options.optimized_hardware_mapping)?;
    let width = usize::try_from(config.width()?)
        .map_err(|_| "Optimized checkpoint width exceeded host usize.".to_string())?;
    let height = usize::try_from(config.height()?)
        .map_err(|_| "Optimized checkpoint height exceeded host usize.".to_string())?;
    let resident_bytes = config
        .estimated_word_count()?
        .checked_mul(std::mem::size_of::<u32>())
        .ok_or_else(|| "Optimized resident buffer size overflowed.".to_string())?;
    let transport = Pi5KernelResidentLoop::new(resident_bytes)?;
    let start = Instant::now();
    let deadline = start + Duration::from_secs_f32(options.hold_seconds_per_checkpoint);
    let color_interval = Duration::from_millis(options.color_interval_ms);
    let mut frame_builds = 0_u64;
    let mut steady_presentations = 0_u64;
    let mut pack_word_count = 0_usize;
    let mut frame_bytes = 0_usize;

    println!(
        "checkpoint=optimized-resident wiring={:?} interval_ms={} hold_s={:.2}",
        options.optimized_hardware_mapping,
        options.color_interval_ms,
        options.hold_seconds_per_checkpoint
    );

    for interval_index in 0_u64.. {
        let interval_start = start
            .checked_add(color_interval.saturating_mul(interval_index as u32))
            .ok_or_else(|| "Optimized checkpoint interval start overflowed.".to_string())?;
        if interval_start >= deadline {
            break;
        }
        let interval_end = interval_start
            .checked_add(color_interval)
            .map(|time| time.min(deadline))
            .ok_or_else(|| "Optimized checkpoint interval end overflowed.".to_string())?;
        let color = RGB_SEQUENCE[(interval_index as usize) % RGB_SEQUENCE.len()];
        let (frame, stats) = pack_solid_frame(&config, width, height, color)?;
        pack_word_count = stats.word_count;
        frame_bytes = frame.as_bytes().len();
        frame_builds = frame_builds.saturating_add(1);
        println!(
            "checkpoint=optimized-resident color={} rebuild={} frame_words={} frame_bytes={} compressed_blank_groups={} merged_identical_groups={}",
            color.as_str(),
            frame_builds,
            stats.word_count,
            frame_bytes,
            stats.compressed_blank_groups,
            stats.merged_identical_groups
        );

        transport.load_frame(&frame)?;
        transport.start()?;
        transport.wait_presentations(1)?;
        if interval_end > Instant::now() {
            thread::sleep(interval_end - Instant::now());
        }
        let stats = transport.stats()?;
        steady_presentations = steady_presentations
            .saturating_add(stats.presentations.saturating_sub(1));
        transport.stop()?;
    }

    println!(
        "checkpoint=optimized-resident status=ok frame_builds={} steady_presentations={} frame_words={} frame_bytes={}",
        frame_builds,
        steady_presentations,
        pack_word_count,
        frame_bytes
    );
    Ok(())
}

fn build_simple_config(
    options: &DemoOptions,
    wiring: WiringProfile,
) -> Result<Pi5ScanConfig, String> {
    Pi5ScanConfig::from_matrix_config(
        wiring,
        options.panel_rows,
        options.panel_cols,
        options.chain_length,
        options.parallel,
    )?
    .with_format(Pi5ScanFormat::Simple)?
    .with_pwm_bits(options.pwm_bits)?
    .with_lsb_dwell_ticks(options.lsb_dwell_ticks)?
    .with_timing(Pi5ScanTiming {
        clock_divider: options.clock_divider,
        post_addr_ticks: options.post_addr_ticks,
        latch_ticks: options.latch_ticks,
        post_latch_ticks: options.post_latch_ticks,
        simple_clock_hold_ticks: options.simple_clock_hold_ticks,
    })
}

fn build_optimized_config(
    options: &DemoOptions,
    wiring: WiringProfile,
) -> Result<Pi5ScanConfig, String> {
    Pi5ScanConfig::from_matrix_config(
        wiring,
        options.panel_rows,
        options.panel_cols,
        options.chain_length,
        options.parallel,
    )?
    .with_format(Pi5ScanFormat::Optimized)?
    .with_pwm_bits(options.pwm_bits)?
    .with_lsb_dwell_ticks(options.lsb_dwell_ticks)
}

fn pack_solid_frame(
    config: &Pi5ScanConfig,
    width: usize,
    height: usize,
    color: DemoColor,
) -> Result<(PackedScanFrame, PackedScanFrameStats), String> {
    let mut rgba = vec![0_u8; width * height * 4];
    fill_solid_frame(&mut rgba, color);
    PackedScanFrame::pack_rgba(config, &rgba)
}

fn fill_solid_frame(rgba: &mut [u8], color: DemoColor) {
    let (red, green, blue) = color.as_rgb();
    for pixel in rgba.chunks_exact_mut(4) {
        pixel[0] = red;
        pixel[1] = green;
        pixel[2] = blue;
        pixel[3] = 255;
    }
}

fn parse_args(args: Vec<String>) -> Result<DemoOptions, String> {
    let mut options = DemoOptions {
        burst_copies: DEFAULT_BURST_COPIES,
        chain_length: DEFAULT_CHAIN_LENGTH,
        checkpoint: DemoCheckpoint::All,
        clock_divider: DEFAULT_CLOCK_DIVIDER,
        color_interval_ms: DEFAULT_COLOR_INTERVAL_MS,
        hardware_mapping: DEFAULT_HARDWARE_MAPPING,
        hold_seconds_per_checkpoint: DEFAULT_HOLD_SECONDS_PER_CHECKPOINT,
        latch_ticks: DEFAULT_LATCH_TICKS,
        lsb_dwell_ticks: DEFAULT_LSB_DWELL_TICKS,
        optimized_hardware_mapping: DEFAULT_OPTIMIZED_HARDWARE_MAPPING,
        panel_cols: DEFAULT_PANEL_COLS,
        panel_rows: DEFAULT_PANEL_ROWS,
        parallel: DEFAULT_PARALLEL,
        post_addr_ticks: DEFAULT_POST_ADDR_TICKS,
        post_latch_ticks: DEFAULT_POST_LATCH_TICKS,
        pwm_bits: DEFAULT_PWM_BITS,
        simple_clock_hold_ticks: DEFAULT_SIMPLE_CLOCK_HOLD_TICKS,
        sys_clock_hz: DEFAULT_SYS_CLOCK_HZ,
    };
    let mut args = args.into_iter();
    while let Some(arg) = args.next() {
        let next = |args: &mut std::vec::IntoIter<String>, flag: &str| {
            args.next()
                .ok_or_else(|| format!("Missing value for {flag}."))
        };
        match arg.as_str() {
            "--burst-copies" => {
                options.burst_copies =
                    parse_value(&next(&mut args, "--burst-copies")?, "--burst-copies")?
            }
            "--chain-length" => {
                options.chain_length =
                    parse_value(&next(&mut args, "--chain-length")?, "--chain-length")?
            }
            "--checkpoint" => {
                options.checkpoint = parse_checkpoint(&next(&mut args, "--checkpoint")?)?;
            }
            "--clock-divider" => {
                options.clock_divider =
                    parse_value(&next(&mut args, "--clock-divider")?, "--clock-divider")?
            }
            "--color-interval-ms" => {
                options.color_interval_ms = parse_value(
                    &next(&mut args, "--color-interval-ms")?,
                    "--color-interval-ms",
                )?
            }
            "--hardware-mapping" => {
                options.hardware_mapping =
                    parse_wiring_profile(&next(&mut args, "--hardware-mapping")?)?;
            }
            "--hold-seconds-per-checkpoint" => {
                options.hold_seconds_per_checkpoint = parse_value(
                    &next(&mut args, "--hold-seconds-per-checkpoint")?,
                    "--hold-seconds-per-checkpoint",
                )?
            }
            "--latch-ticks" => {
                options.latch_ticks =
                    parse_value(&next(&mut args, "--latch-ticks")?, "--latch-ticks")?
            }
            "--lsb-dwell-ticks" => {
                options.lsb_dwell_ticks = parse_value(
                    &next(&mut args, "--lsb-dwell-ticks")?,
                    "--lsb-dwell-ticks",
                )?
            }
            "--optimized-hardware-mapping" => {
                options.optimized_hardware_mapping =
                    parse_wiring_profile(&next(&mut args, "--optimized-hardware-mapping")?)?;
            }
            "--panel-cols" => {
                options.panel_cols = parse_value(&next(&mut args, "--panel-cols")?, "--panel-cols")?
            }
            "--panel-rows" => {
                options.panel_rows = parse_value(&next(&mut args, "--panel-rows")?, "--panel-rows")?
            }
            "--parallel" => {
                options.parallel = parse_value(&next(&mut args, "--parallel")?, "--parallel")?
            }
            "--post-addr-ticks" => {
                options.post_addr_ticks = parse_value(
                    &next(&mut args, "--post-addr-ticks")?,
                    "--post-addr-ticks",
                )?
            }
            "--post-latch-ticks" => {
                options.post_latch_ticks = parse_value(
                    &next(&mut args, "--post-latch-ticks")?,
                    "--post-latch-ticks",
                )?
            }
            "--pwm-bits" => {
                options.pwm_bits = parse_value(&next(&mut args, "--pwm-bits")?, "--pwm-bits")?
            }
            "--simple-clock-hold-ticks" => {
                options.simple_clock_hold_ticks = parse_value(
                    &next(&mut args, "--simple-clock-hold-ticks")?,
                    "--simple-clock-hold-ticks",
                )?
            }
            "--sys-clock-hz" => {
                options.sys_clock_hz =
                    parse_value(&next(&mut args, "--sys-clock-hz")?, "--sys-clock-hz")?
            }
            "--help" => {
                print_help();
                std::process::exit(0);
            }
            other => return Err(format!("Unknown argument {other:?}. Use --help for usage.")),
        }
    }
    Ok(options)
}

fn parse_checkpoint(value: &str) -> Result<DemoCheckpoint, String> {
    match value {
        "all" => Ok(DemoCheckpoint::All),
        "optimized-resident" => Ok(DemoCheckpoint::OptimizedResident),
        "simple-burst" => Ok(DemoCheckpoint::SimpleBurst),
        "simple-single" => Ok(DemoCheckpoint::SimpleSingle),
        _ => Err(format!(
            "Invalid checkpoint {value:?}. Expected all, optimized-resident, simple-burst, or simple-single."
        )),
    }
}

fn parse_wiring_profile(value: &str) -> Result<WiringProfile, String> {
    match value {
        "adafruit-hat" => Ok(WiringProfile::AdafruitHat),
        "adafruit-hat-pwm" => Ok(WiringProfile::AdafruitHatPwm),
        _ => Err(format!(
            "Invalid hardware mapping {value:?}. Expected adafruit-hat or adafruit-hat-pwm."
        )),
    }
}

fn parse_value<T: std::str::FromStr>(value: &str, flag: &str) -> Result<T, String> {
    value
        .parse::<T>()
        .map_err(|_| format!("Invalid value {value:?} for {flag}."))
}

fn print_help() {
    println!("Usage: pi5_pio_checkpoint_demo [options]");
    println!("  --checkpoint <name>                   all|simple-single|simple-burst|optimized-resident");
    println!("  --panel-rows <u16>                    default 64");
    println!("  --panel-cols <u16>                    default 64");
    println!("  --chain-length <u16>                  default 1");
    println!("  --parallel <u8>                       default 1");
    println!("  --hardware-mapping <name>             adafruit-hat|adafruit-hat-pwm");
    println!("  --optimized-hardware-mapping <name>   adafruit-hat|adafruit-hat-pwm");
    println!("  --pwm-bits <u8>                       default 1");
    println!("  --hold-seconds-per-checkpoint <f32>   default 3");
    println!("  --color-interval-ms <u64>             default 200");
    println!("  --burst-copies <usize>                default 8");
    println!("  --clock-divider <f32>                 default 20");
    println!("  --lsb-dwell-ticks <u32>               default 64");
    println!("  --post-addr-ticks <u32>               default 5");
    println!("  --latch-ticks <u32>                   default 1");
    println!("  --post-latch-ticks <u32>              default 1");
    println!("  --simple-clock-hold-ticks <u32>       default 1");
    println!("  --sys-clock-hz <f64>                  default 200000000, used for timing estimates");
}
