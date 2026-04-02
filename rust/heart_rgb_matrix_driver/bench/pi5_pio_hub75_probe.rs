#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{
    build_simple_group_words_for_rgba, build_simple_smoke_group_words,
    estimate_simple_hub75_frame_timing, PackedScanFrame, Pi5PioScanTransport, Pi5ScanConfig,
    Pi5ScanFormat, WiringProfile,
};
use std::env;
use std::process::ExitCode;
use std::time::{Duration, Instant};

const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_HOLD_SECONDS: f32 = 8.0;
const DEFAULT_FRAME_SECONDS: f32 = 0.05;
const DEFAULT_PWM_BITS: u8 = 1;
const DEFAULT_SYS_CLOCK_HZ: f64 = 200_000_000.0;
const DEFAULT_HARDWARE_MAPPING: WiringProfile = WiringProfile::AdafruitHatPwm;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ProbePattern {
    BlueFill,
    Gradient,
    Checker,
    RowBars,
    RowAddress,
    Solid,
}

#[derive(Clone, Copy, Debug)]
struct ProbeOptions {
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    wiring: WiringProfile,
    pwm_bits: u8,
    hold_seconds: f32,
    frame_seconds: f32,
    pattern: ProbePattern,
    fixed_row_pair: Option<usize>,
    sys_clock_hz: f64,
    clock_divider: Option<f32>,
    lsb_dwell_ticks: Option<u32>,
    post_addr_ticks: Option<u32>,
    latch_ticks: Option<u32>,
    post_latch_ticks: Option<u32>,
    simple_clock_hold_ticks: Option<u32>,
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
    let mut config = Pi5ScanConfig::from_matrix_config(
        options.wiring,
        options.panel_rows,
        options.panel_cols,
        options.chain_length,
        options.parallel,
    )?
    .with_format(Pi5ScanFormat::Simple)?
    .with_pwm_bits(options.pwm_bits)?;
    if let Some(lsb_dwell_ticks) = options.lsb_dwell_ticks {
        config = config.with_lsb_dwell_ticks(lsb_dwell_ticks)?;
    }
    let mut timing = config.timing();
    if let Some(clock_divider) = options.clock_divider {
        timing.clock_divider = clock_divider;
    }
    if let Some(post_addr_ticks) = options.post_addr_ticks {
        timing.post_addr_ticks = post_addr_ticks;
    }
    if let Some(latch_ticks) = options.latch_ticks {
        timing.latch_ticks = latch_ticks;
    }
    if let Some(post_latch_ticks) = options.post_latch_ticks {
        timing.post_latch_ticks = post_latch_ticks;
    }
    if let Some(simple_clock_hold_ticks) = options.simple_clock_hold_ticks {
        timing.simple_clock_hold_ticks = simple_clock_hold_ticks;
    }
    config = config.with_timing(timing)?;
    let width = config.width()? as usize;
    let height = config.height()? as usize;
    let row_pairs = config.row_pairs()?;
    let mut rgba = vec![0_u8; width * height * 4];
    let transport = Pi5PioScanTransport::new(
        config.estimated_word_count()?,
        config.pinout(),
        config.timing(),
        config.format(),
    )?;
    let deadline = Instant::now() + Duration::from_secs_f32(options.hold_seconds);
    let mut last_frame_update = Instant::now() - Duration::from_secs_f32(options.frame_seconds);
    let mut frame_index = 0_u64;
    let mut scan_count = 0_u64;
    let use_full_frame_replay =
        options.pattern != ProbePattern::RowAddress && options.fixed_row_pair.is_none();
    let mut submitted_frames = 0_u64;
    let mut packed_frame: Option<PackedScanFrame> = None;
    let timing_estimate =
        estimate_simple_hub75_frame_timing(&config, options.sys_clock_hz)?;

    println!(
        "pi5_pio_hub75_probe backend=row-loop-simple width={} height={} wiring={:?} pattern={:?} pwm_bits={} clock_divider={} lsb_dwell_ticks={}",
        width,
        height,
        options.wiring,
        options.pattern,
        options.pwm_bits,
        config.timing().clock_divider,
        config.lsb_dwell_ticks
    );
    println!(
        "timing_estimate tick_ns={:.1} row_pair_us={:.3} frame_hz={:.3} post_addr_ticks={} latch_ticks={} post_latch_ticks={} simple_clock_hold_ticks={}",
        timing_estimate.pio_tick_seconds * 1_000_000_000.0,
        (timing_estimate.group_cycles_by_plane[0] as f64) * timing_estimate.pio_tick_seconds * 1_000_000.0,
        timing_estimate.full_frame_hz,
        config.timing().post_addr_ticks,
        config.timing().latch_ticks,
        config.timing().post_latch_ticks,
        config.timing().simple_clock_hold_ticks
    );

    while Instant::now() < deadline {
        let frame_due =
            packed_frame.is_none()
                || last_frame_update.elapsed() >= Duration::from_secs_f32(options.frame_seconds);
        if frame_due {
            fill_probe_frame(
                &mut rgba,
                width,
                height,
                options.pattern,
                frame_index,
                options.fixed_row_pair,
            );
            if use_full_frame_replay {
                let (packed, _stats) = PackedScanFrame::pack_rgba(&config, &rgba)?;
                packed_frame = Some(packed);
                submitted_frames = submitted_frames.saturating_add(1);
                last_frame_update = Instant::now();
                frame_index = frame_index.saturating_add(1);
            } else {
                last_frame_update = Instant::now();
                frame_index = frame_index.saturating_add(1);
                let row_pair_range = options
                    .fixed_row_pair
                    .map(|row_pair| row_pair..row_pair.saturating_add(1))
                    .unwrap_or(0..row_pairs);

                for row_pair in row_pair_range {
                    let words = if options.pattern == ProbePattern::RowAddress {
                        build_row_address_group_words(
                            &config,
                            row_pair,
                            frame_index.saturating_sub(1),
                            options.fixed_row_pair,
                        )?
                    } else {
                        build_simple_group_words_for_rgba(&config, &rgba, row_pair, 0)?
                    };
                    let packed = PackedScanFrame::from_words(words);
                    transport.submit_blocking(&packed)?;
                    scan_count = scan_count.saturating_add(1);
                    if Instant::now() >= deadline {
                        break;
                    }
                }
            }
        }

        if use_full_frame_replay {
            let Some(frame) = packed_frame.as_ref() else {
                continue;
            };
            transport.submit_blocking(frame)?;
            scan_count = scan_count.saturating_add(
                row_pairs.saturating_mul(usize::from(config.pwm_bits)) as u64,
            );
        }
    }

    if use_full_frame_replay {
        println!(
            "completed_row_pair_scans={scan_count} submitted_frames={submitted_frames}"
        );
    } else {
        println!("completed_row_pair_scans={scan_count}");
    }
    Ok(())
}

fn fill_probe_frame(
    rgba: &mut [u8],
    width: usize,
    height: usize,
    pattern: ProbePattern,
    frame_index: u64,
    fixed_row_pair: Option<usize>,
) {
    match pattern {
        ProbePattern::BlueFill => fill_blue_frame(rgba, width, height),
        ProbePattern::Gradient => fill_gradient_frame(rgba, width, height, frame_index),
        ProbePattern::Checker => fill_checker_frame(rgba, width, height, frame_index),
        ProbePattern::RowBars => {
            fill_row_bars_frame(rgba, width, height, frame_index, fixed_row_pair)
        }
        ProbePattern::RowAddress => fill_solid_frame(rgba, width, height, frame_index),
        ProbePattern::Solid => fill_solid_frame(rgba, width, height, frame_index),
    }
}

fn fill_blue_frame(rgba: &mut [u8], width: usize, height: usize) {
    for pixel in rgba.chunks_exact_mut(4).take(width * height) {
        pixel[0] = 0;
        pixel[1] = 0;
        pixel[2] = 255;
        pixel[3] = 255;
    }
}

fn build_row_address_group_words(
    config: &Pi5ScanConfig,
    row_pair: usize,
    frame_index: u64,
    fixed_row_pair: Option<usize>,
) -> Result<Vec<u32>, String> {
    let active_row_pair = fixed_row_pair.unwrap_or((frame_index as usize) % config.row_pairs()?);
    if row_pair == active_row_pair {
        build_simple_smoke_group_words(
            config,
            row_pair,
            (true, false, false),
            (false, true, false),
            config.lsb_dwell_ticks,
        )
    } else {
        build_simple_smoke_group_words(
            config,
            row_pair,
            (false, false, false),
            (false, false, false),
            config.lsb_dwell_ticks,
        )
    }
}

fn fill_gradient_frame(rgba: &mut [u8], width: usize, height: usize, frame_index: u64) {
    let phase = ((frame_index % 120) as f32) / 119.0;
    for y in 0..height {
        for x in 0..width {
            let pixel_index = ((y * width) + x) * 4;
            let horizontal = if width > 1 {
                x as f32 / (width - 1) as f32
            } else {
                0.0
            };
            let vertical = if height > 1 {
                y as f32 / (height - 1) as f32
            } else {
                0.0
            };
            let red = (48.0 + 160.0 * phase + 24.0 * horizontal).clamp(0.0, 255.0) as u8;
            let green = (72.0 + 40.0 * (1.0 - vertical)).clamp(0.0, 255.0) as u8;
            let blue = (208.0 - 160.0 * phase + 32.0 * vertical).clamp(0.0, 255.0) as u8;
            rgba[pixel_index] = red;
            rgba[pixel_index + 1] = green;
            rgba[pixel_index + 2] = blue;
            rgba[pixel_index + 3] = 255;
        }
    }
}

fn fill_checker_frame(rgba: &mut [u8], width: usize, height: usize, frame_index: u64) {
    let invert = (frame_index / 10) % 2 == 1;
    for y in 0..height {
        for x in 0..width {
            let pixel_index = ((y * width) + x) * 4;
            let is_lit = ((x + y) % 2 == 0) ^ invert;
            let value = if is_lit { 255 } else { 0 };
            rgba[pixel_index] = value;
            rgba[pixel_index + 1] = value;
            rgba[pixel_index + 2] = value;
            rgba[pixel_index + 3] = 255;
        }
    }
}

fn fill_row_bars_frame(
    rgba: &mut [u8],
    width: usize,
    height: usize,
    frame_index: u64,
    fixed_row_pair: Option<usize>,
) {
    for pixel in rgba.chunks_exact_mut(4).take(width * height) {
        pixel[0] = 0;
        pixel[1] = 0;
        pixel[2] = 0;
        pixel[3] = 255;
    }

    let row_pairs = height / 2;
    let active_row_pair = fixed_row_pair.unwrap_or((frame_index as usize) % row_pairs);
    let top_row = active_row_pair;
    let bottom_row = active_row_pair + row_pairs;

    for x in 0..width {
        let bar_index = x / 8;
        let top_on = bar_index % 2 == 0;
        let bottom_on = bar_index % 2 == 1;
        let top_offset = ((top_row * width) + x) * 4;
        let bottom_offset = ((bottom_row * width) + x) * 4;

        rgba[top_offset] = if top_on { 255 } else { 0 };
        rgba[top_offset + 1] = 0;
        rgba[top_offset + 2] = if top_on { 64 } else { 0 };
        rgba[top_offset + 3] = 255;

        rgba[bottom_offset] = 0;
        rgba[bottom_offset + 1] = if bottom_on { 255 } else { 0 };
        rgba[bottom_offset + 2] = if bottom_on { 64 } else { 0 };
        rgba[bottom_offset + 3] = 255;
    }
}

fn fill_solid_frame(rgba: &mut [u8], width: usize, height: usize, frame_index: u64) {
    let phase = (frame_index / 20) % 3;
    let (red, green, blue) = match phase {
        0 => (255, 96, 96),
        1 => (96, 255, 160),
        _ => (96, 160, 255),
    };
    for pixel in rgba.chunks_exact_mut(4).take(width * height) {
        pixel[0] = red;
        pixel[1] = green;
        pixel[2] = blue;
        pixel[3] = 255;
    }
}

fn parse_args(args: Vec<String>) -> Result<ProbeOptions, String> {
    let mut options = ProbeOptions {
        panel_rows: DEFAULT_PANEL_ROWS,
        panel_cols: DEFAULT_PANEL_COLS,
        chain_length: DEFAULT_CHAIN_LENGTH,
        parallel: DEFAULT_PARALLEL,
        wiring: DEFAULT_HARDWARE_MAPPING,
        pwm_bits: DEFAULT_PWM_BITS,
        hold_seconds: DEFAULT_HOLD_SECONDS,
        frame_seconds: DEFAULT_FRAME_SECONDS,
        pattern: ProbePattern::Gradient,
        fixed_row_pair: None,
        sys_clock_hz: DEFAULT_SYS_CLOCK_HZ,
        clock_divider: None,
        lsb_dwell_ticks: None,
        post_addr_ticks: None,
        latch_ticks: None,
        post_latch_ticks: None,
        simple_clock_hold_ticks: None,
    };
    let mut args = args.into_iter();
    while let Some(arg) = args.next() {
        let next = |args: &mut std::vec::IntoIter<String>, flag: &str| {
            args.next()
                .ok_or_else(|| format!("Missing value for {flag}."))
        };
        match arg.as_str() {
            "--panel-rows" => {
                options.panel_rows = parse_value(&next(&mut args, "--panel-rows")?, "--panel-rows")?
            }
            "--panel-cols" => {
                options.panel_cols = parse_value(&next(&mut args, "--panel-cols")?, "--panel-cols")?
            }
            "--chain-length" => {
                options.chain_length =
                    parse_value(&next(&mut args, "--chain-length")?, "--chain-length")?
            }
            "--parallel" => {
                options.parallel = parse_value(&next(&mut args, "--parallel")?, "--parallel")?
            }
            "--hardware-mapping" => {
                options.wiring = parse_wiring_profile(&next(&mut args, "--hardware-mapping")?)?;
            }
            "--pwm-bits" => {
                options.pwm_bits = parse_value(&next(&mut args, "--pwm-bits")?, "--pwm-bits")?
            }
            "--hold-seconds" => {
                options.hold_seconds =
                    parse_value(&next(&mut args, "--hold-seconds")?, "--hold-seconds")?
            }
            "--frame-seconds" => {
                options.frame_seconds =
                    parse_value(&next(&mut args, "--frame-seconds")?, "--frame-seconds")?
            }
            "--pattern" => {
                options.pattern = parse_pattern(&next(&mut args, "--pattern")?)?;
            }
            "--fixed-row-pair" => {
                options.fixed_row_pair = Some(parse_value(
                    &next(&mut args, "--fixed-row-pair")?,
                    "--fixed-row-pair",
                )?);
            }
            "--sys-clock-hz" => {
                options.sys_clock_hz =
                    parse_value(&next(&mut args, "--sys-clock-hz")?, "--sys-clock-hz")?
            }
            "--clock-divider" => {
                options.clock_divider =
                    Some(parse_value(&next(&mut args, "--clock-divider")?, "--clock-divider")?)
            }
            "--lsb-dwell-ticks" => {
                options.lsb_dwell_ticks = Some(parse_value(
                    &next(&mut args, "--lsb-dwell-ticks")?,
                    "--lsb-dwell-ticks",
                )?)
            }
            "--post-addr-ticks" => {
                options.post_addr_ticks = Some(parse_value(
                    &next(&mut args, "--post-addr-ticks")?,
                    "--post-addr-ticks",
                )?)
            }
            "--latch-ticks" => {
                options.latch_ticks =
                    Some(parse_value(&next(&mut args, "--latch-ticks")?, "--latch-ticks")?)
            }
            "--post-latch-ticks" => {
                options.post_latch_ticks = Some(parse_value(
                    &next(&mut args, "--post-latch-ticks")?,
                    "--post-latch-ticks",
                )?)
            }
            "--simple-clock-hold-ticks" => {
                options.simple_clock_hold_ticks = Some(parse_value(
                    &next(&mut args, "--simple-clock-hold-ticks")?,
                    "--simple-clock-hold-ticks",
                )?)
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

fn parse_pattern(value: &str) -> Result<ProbePattern, String> {
    match value {
        "blue-fill" => Ok(ProbePattern::BlueFill),
        "gradient" => Ok(ProbePattern::Gradient),
        "checker" => Ok(ProbePattern::Checker),
        "row-bars" => Ok(ProbePattern::RowBars),
        "row-address" => Ok(ProbePattern::RowAddress),
        "solid" => Ok(ProbePattern::Solid),
        _ => Err(format!(
            "Invalid pattern {value:?}. Expected one of: blue-fill, gradient, checker, row-bars, row-address, solid."
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
    println!("Usage: pi5_pio_hub75_probe [options]");
    println!("  --panel-rows <u16>       default 64");
    println!("  --panel-cols <u16>       default 64");
    println!("  --chain-length <u16>     default 1");
    println!("  --parallel <u8>          default 1");
    println!("  --hardware-mapping <name> adafruit-hat|adafruit-hat-pwm");
    println!("  --pwm-bits <u8>          default 1");
    println!("  --hold-seconds <f32>     default 8");
    println!("  --frame-seconds <f32>    default 0.05");
    println!("  --pattern <name>         blue-fill|gradient|checker|row-bars|row-address|solid");
    println!("  --fixed-row-pair <usize> optional fixed row pair for row-bars/row-address");
    println!("  --clock-divider <f32>    override PIO clock divider");
    println!("  --lsb-dwell-ticks <u32>  override visible dwell ticks for pwm bit 0");
    println!("  --post-addr-ticks <u32>  override blanked settle ticks after row address");
    println!("  --latch-ticks <u32>      override LAT pulse width");
    println!("  --post-latch-ticks <u32> override blanked hold after LAT");
    println!("  --simple-clock-hold-ticks <u32> override per-phase low/high clock hold");
    println!("  --sys-clock-hz <f64>     default 200000000, used only for timing estimates");
}
