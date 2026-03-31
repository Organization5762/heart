#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{
    PackedScanFrame, Pi5KernelResidentLoop, Pi5ScanConfig, Pi5ScanTiming, WiringProfile,
};
use std::env;
use std::process::ExitCode;
use std::time::Duration;

const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_FRAME_COUNT: usize = 32;
const DEFAULT_ITERATIONS: usize = 3;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_PIPELINE_DEPTH: usize = 2;
const DEFAULT_RESIDENT_LOOP_MS: u64 = 100;
const PI5_SCAN_SHARED_PROGRAM_LENGTH: u64 = 24;
const DEFAULT_SCAN_TIMING: Pi5ScanTiming = Pi5ScanTiming {
    clock_divider: 1.0,
    post_addr_ticks: 5,
    latch_ticks: 1,
    post_latch_ticks: 1,
};

#[derive(Clone, Copy, Debug)]
struct BenchOptions {
    frame_count: usize,
    iterations: usize,
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    pwm_bits: u8,
    pipeline_depth: usize,
    resident_loop_ms: u64,
    lsb_dwell_ticks: u32,
    clock_divider: f32,
    frame_pattern: FramePattern,
}

#[derive(Clone, Copy, Debug)]
enum FramePattern {
    Dense,
    Black,
    Sparse,
    Solid,
    Striped,
}

impl FramePattern {
    fn as_str(self) -> &'static str {
        match self {
            Self::Dense => "dense",
            Self::Black => "black",
            Self::Sparse => "sparse",
            Self::Solid => "solid",
            Self::Striped => "striped",
        }
    }
}

#[derive(Clone, Copy, Debug)]
struct CycleStats {
    total_duration: Duration,
    mean_duration: Duration,
    frames_per_second: f64,
}

#[derive(Clone, Copy, Debug)]
struct ResidentLoopBenchmarkSample {
    compressed_blank_groups: usize,
    merged_identical_groups: usize,
    word_count: usize,
    pack_duration: Duration,
    first_render_duration: Duration,
    steady_window_duration: Duration,
    refresh_count: u64,
    refresh_hz: f64,
    batches_submitted: u64,
    words_written: u64,
    drain_failures: u64,
    stop_requests_seen_during_batch: u64,
    mmio_write_ns: u64,
    drain_ns: u64,
    max_batch_replays: u32,
    worker_cpu: u32,
    worker_priority: u32,
    worker_runnable: bool,
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
    let config = Pi5ScanConfig::from_matrix_config(
        WiringProfile::AdafruitHatPwm,
        options.panel_rows,
        options.panel_cols,
        options.chain_length,
        options.parallel,
    )?
    .with_pwm_bits(options.pwm_bits)?
    .with_lsb_dwell_ticks(options.lsb_dwell_ticks)?
    .with_timing(Pi5ScanTiming {
        clock_divider: options.clock_divider,
        ..DEFAULT_SCAN_TIMING
    })?;
    let width = config.width()?;
    let height = config.height()?;
    let scan_metrics = estimate_scan_metrics(&config)?;
    let frames = build_frames(width, height, options.frame_count, options.frame_pattern);
    let transport = Pi5KernelResidentLoop::new(
        config
            .estimated_word_count()?
            .checked_mul(std::mem::size_of::<u32>())
            .ok_or_else(|| {
                "Pi 5 scan frame size overflowed while opening kernel loop.".to_string()
            })?,
    )?;

    let mut pack_samples = Vec::with_capacity(options.iterations);
    let mut stream_samples = Vec::with_capacity(options.iterations);
    let mut word_count = 0_usize;

    for iteration in 0..options.iterations {
        let mut frame = frame_bytes(width, height, 31, options.frame_pattern);
        if matches!(options.frame_pattern, FramePattern::Dense) {
            frame[0] = frame[0].wrapping_add(iteration as u8);
        }
        let (packed, stats) = PackedScanFrame::pack_rgba(&config, &frame)?;
        word_count = stats.word_count;
        pack_samples.push(stats.pack_duration);
        let stream_start = std::time::Instant::now();
        transport.load_frame(&packed)?;
        transport.start()?;
        transport.wait_presentations(1)?;
        transport.stop()?;
        stream_samples.push(stream_start.elapsed());
    }

    let display = run_display_cycle(&transport, &config, &frames)?;
    drop(transport);
    let resident = run_resident_loop_cycle(
        &config,
        &frame_bytes(width, height, 77, options.frame_pattern),
        Duration::from_millis(options.resident_loop_ms),
    )?;

    println!(
        concat!(
            "{{",
            "\"panel_rows\":{panel_rows},",
            "\"panel_cols\":{panel_cols},",
            "\"chain_length\":{chain_length},",
            "\"parallel\":{parallel},",
            "\"pwm_bits\":{pwm_bits},",
            "\"frame_pattern\":\"{frame_pattern}\",",
            "\"lsb_dwell_ticks\":{lsb_dwell_ticks},",
            "\"clock_divider\":{clock_divider:.3},",
            "\"width\":{width},",
            "\"height\":{height},",
            "\"scan_row_pairs\":{scan_row_pairs},",
            "\"scan_group_count\":{scan_group_count},",
            "\"scan_shift_words\":{scan_shift_words},",
            "\"scan_dwell_ticks_total\":{scan_dwell_ticks_total},",
            "\"scan_fixed_delay_ticks_total\":{scan_fixed_delay_ticks_total},",
            "\"scan_estimated_cycles\":{scan_estimated_cycles},",
            "\"iterations\":{iterations},",
            "\"frame_count\":{frame_count},",
            "\"word_count\":{word_count},",
            "\"compressed_blank_groups\":{compressed_blank_groups},",
            "\"merged_identical_groups\":{merged_identical_groups},",
            "\"pack_mean_ns\":{pack_mean_ns},",
            "\"stream_mean_ns\":{stream_mean_ns},",
            "\"resident_backend\":\"{resident_backend}\",",
            "\"resident_loop_ms\":{resident_loop_ms},",
            "\"resident_first_render_ns\":{resident_first_render_ns},",
            "\"resident_steady_window_ns\":{resident_steady_window_ns},",
            "\"resident_refresh_count\":{resident_refresh_count},",
            "\"resident_refresh_hz\":{resident_refresh_hz:.3},",
            "\"resident_batches_submitted\":{resident_batches_submitted},",
            "\"resident_words_written\":{resident_words_written},",
            "\"resident_drain_failures\":{resident_drain_failures},",
            "\"resident_stop_requests_seen_during_batch\":{resident_stop_requests_seen_during_batch},",
            "\"resident_mmio_write_ns\":{resident_mmio_write_ns},",
            "\"resident_drain_ns\":{resident_drain_ns},",
            "\"resident_max_batch_replays\":{resident_max_batch_replays},",
            "\"resident_worker_cpu\":{resident_worker_cpu},",
            "\"resident_worker_priority\":{resident_worker_priority},",
            "\"resident_worker_runnable\":{resident_worker_runnable},",
            "\"distinct_frame_update_cycle_mean_ns\":{distinct_frame_update_cycle_mean_ns},",
            "\"distinct_frame_update_hz\":{distinct_frame_update_hz:.3},",
            "\"sequential_cycle_mean_ns\":{sequential_cycle_mean_ns},",
            "\"sequential_cycle_hz\":{sequential_cycle_hz:.3}",
            "}}"
        ),
        panel_rows = options.panel_rows,
        panel_cols = options.panel_cols,
        chain_length = options.chain_length,
        parallel = options.parallel,
        pwm_bits = options.pwm_bits,
        frame_pattern = options.frame_pattern.as_str(),
        lsb_dwell_ticks = options.lsb_dwell_ticks,
        clock_divider = options.clock_divider,
        width = width,
        height = height,
        scan_row_pairs = scan_metrics.row_pairs,
        scan_group_count = scan_metrics.group_count,
        scan_shift_words = scan_metrics.shift_words,
        scan_dwell_ticks_total = scan_metrics.dwell_ticks_total,
        scan_fixed_delay_ticks_total = scan_metrics.fixed_delay_ticks_total,
        scan_estimated_cycles = scan_metrics.estimated_cycles,
        iterations = options.iterations,
        frame_count = options.frame_count,
        word_count = word_count,
        compressed_blank_groups = resident.compressed_blank_groups,
        merged_identical_groups = resident.merged_identical_groups,
        pack_mean_ns = mean_ns(&pack_samples),
        stream_mean_ns = mean_ns(&stream_samples),
        resident_backend = "kernel_loop",
        resident_loop_ms = options.resident_loop_ms,
        resident_first_render_ns = resident.first_render_duration.as_nanos(),
        resident_steady_window_ns = resident.steady_window_duration.as_nanos(),
        resident_refresh_count = resident.refresh_count,
        resident_refresh_hz = resident.refresh_hz,
        resident_batches_submitted = resident.batches_submitted,
        resident_words_written = resident.words_written,
        resident_drain_failures = resident.drain_failures,
        resident_stop_requests_seen_during_batch =
            resident.stop_requests_seen_during_batch,
        resident_mmio_write_ns = resident.mmio_write_ns,
        resident_drain_ns = resident.drain_ns,
        resident_max_batch_replays = resident.max_batch_replays,
        resident_worker_cpu = resident.worker_cpu,
        resident_worker_priority = resident.worker_priority,
        resident_worker_runnable = if resident.worker_runnable { 1 } else { 0 },
        distinct_frame_update_cycle_mean_ns = display.mean_duration.as_nanos(),
        distinct_frame_update_hz = display.frames_per_second,
        sequential_cycle_mean_ns = display.mean_duration.as_nanos(),
        sequential_cycle_hz = display.frames_per_second,
    );

    Ok(())
}

fn parse_args(arguments: Vec<String>) -> Result<BenchOptions, String> {
    let mut options = BenchOptions {
        frame_count: DEFAULT_FRAME_COUNT,
        iterations: DEFAULT_ITERATIONS,
        panel_rows: DEFAULT_PANEL_ROWS,
        panel_cols: DEFAULT_PANEL_COLS,
        chain_length: DEFAULT_CHAIN_LENGTH,
        parallel: DEFAULT_PARALLEL,
        pwm_bits: 11,
        pipeline_depth: DEFAULT_PIPELINE_DEPTH,
        resident_loop_ms: DEFAULT_RESIDENT_LOOP_MS,
        lsb_dwell_ticks: 2,
        clock_divider: DEFAULT_SCAN_TIMING.clock_divider,
        frame_pattern: FramePattern::Dense,
    };
    let mut index = 0;
    while index < arguments.len() {
        let flag = arguments[index].as_str();
        let next = arguments
            .get(index + 1)
            .ok_or_else(|| format!("Expected a value after {flag}."))?;
        match flag {
            "--frame-count" => options.frame_count = parse_value(next, flag)?,
            "--iterations" => options.iterations = parse_value(next, flag)?,
            "--panel-rows" => options.panel_rows = parse_value(next, flag)?,
            "--panel-cols" => options.panel_cols = parse_value(next, flag)?,
            "--chain-length" => options.chain_length = parse_value(next, flag)?,
            "--parallel" => options.parallel = parse_value(next, flag)?,
            "--pwm-bits" => options.pwm_bits = parse_value(next, flag)?,
            "--pipeline-depth" => options.pipeline_depth = parse_value(next, flag)?,
            "--resident-loop-ms" => options.resident_loop_ms = parse_value(next, flag)?,
            "--lsb-dwell-ticks" => options.lsb_dwell_ticks = parse_value(next, flag)?,
            "--clock-divider" => options.clock_divider = parse_value(next, flag)?,
            "--frame-pattern" => options.frame_pattern = parse_frame_pattern(next)?,
            _ => return Err(format!("Unknown argument {flag}.")),
        }
        index += 2;
    }
    Ok(options)
}

fn parse_value<T>(value: &str, flag: &str) -> Result<T, String>
where
    T: std::str::FromStr,
{
    value
        .parse::<T>()
        .map_err(|_| format!("Unable to parse {flag} value {value:?}."))
}

fn parse_frame_pattern(value: &str) -> Result<FramePattern, String> {
    match value {
        "dense" => Ok(FramePattern::Dense),
        "black" => Ok(FramePattern::Black),
        "sparse" => Ok(FramePattern::Sparse),
        "solid" => Ok(FramePattern::Solid),
        "striped" => Ok(FramePattern::Striped),
        _ => Err(format!(
            "Unknown --frame-pattern value {value:?}. Expected dense, black, sparse, solid, or striped."
        )),
    }
}

fn frame_bytes(width: u32, height: u32, seed: u8, pattern: FramePattern) -> Vec<u8> {
    let byte_count = (width as usize) * (height as usize) * 4;
    match pattern {
        FramePattern::Dense => (0..byte_count)
            .map(|index| seed.wrapping_add(index as u8))
            .collect(),
        FramePattern::Black => vec![0; byte_count],
        FramePattern::Sparse => {
            let mut frame = vec![0; byte_count];
            let pixels = (width as usize) * (height as usize);
            for offset in [0_usize, pixels / 3, (2 * pixels) / 3] {
                let pixel_index = offset.min(pixels.saturating_sub(1));
                let base = pixel_index * 4;
                frame[base] = seed.max(1);
                frame[base + 1] = seed.wrapping_mul(3).max(1);
                frame[base + 2] = seed.wrapping_mul(7).max(1);
                frame[base + 3] = 255;
            }
            frame
        }
        FramePattern::Solid => {
            let mut frame = vec![0; byte_count];
            for pixel in frame.chunks_exact_mut(4) {
                pixel[0] = seed.max(1);
                pixel[1] = seed.wrapping_mul(3).max(1);
                pixel[2] = seed.wrapping_mul(7).max(1);
                pixel[3] = u8::MAX;
            }
            frame
        }
        FramePattern::Striped => {
            let mut frame = vec![0; byte_count];
            let width = width as usize;
            let height = height as usize;
            for row in 0..height {
                for column in 0..width {
                    let lit = (column / 16) % 2 == 0;
                    if !lit {
                        continue;
                    }
                    let base = ((row * width) + column) * 4;
                    frame[base] = seed.max(1);
                    frame[base + 1] = seed.wrapping_mul(3).max(1);
                    frame[base + 2] = seed.wrapping_mul(7).max(1);
                    frame[base + 3] = u8::MAX;
                }
            }
            frame
        }
    }
}

fn build_frames(
    width: u32,
    height: u32,
    frame_count: usize,
    pattern: FramePattern,
) -> Vec<Vec<u8>> {
    (0..frame_count)
        .map(|index| frame_bytes(width, height, (index as u8).wrapping_mul(19), pattern))
        .collect()
}

fn run_display_cycle(
    transport: &Pi5KernelResidentLoop,
    config: &Pi5ScanConfig,
    frames: &[Vec<u8>],
) -> Result<CycleStats, String> {
    let start = std::time::Instant::now();
    for frame in frames {
        let (packed, _) = PackedScanFrame::pack_rgba(config, frame)?;
        transport.load_frame(&packed)?;
        transport.start()?;
        transport.wait_presentations(1)?;
        transport.stop()?;
    }
    Ok(cycle_stats(start.elapsed(), frames.len()))
}

fn run_resident_loop_cycle(
    config: &Pi5ScanConfig,
    frame: &[u8],
    steady_window: Duration,
) -> Result<ResidentLoopBenchmarkSample, String> {
    let (packed, stats) = PackedScanFrame::pack_rgba(config, frame)?;
    let transport = Pi5KernelResidentLoop::new(packed.as_bytes().len())?;
    let first_render_start = std::time::Instant::now();
    transport.load_frame(&packed)?;
    transport.start()?;

    let benchmark = (|| {
        transport.wait_presentations(1)?;
        let first_render_duration = first_render_start.elapsed();

        let baseline_stats = transport.stats()?;
        let baseline_count = baseline_stats.presentations;
        let steady_start = std::time::Instant::now();
        std::thread::sleep(steady_window);
        let steady_window_duration = steady_start.elapsed();
        let steady_end_stats = transport.stats()?;
        let steady_end_count = steady_end_stats.presentations;
        let refresh_count = steady_end_count.saturating_sub(baseline_count);
        let refresh_hz =
            refresh_count as f64 / steady_window_duration.as_secs_f64().max(f64::EPSILON);

        Ok::<ResidentLoopBenchmarkSample, String>(ResidentLoopBenchmarkSample {
            compressed_blank_groups: stats.compressed_blank_groups,
            merged_identical_groups: stats.merged_identical_groups,
            word_count: stats.word_count,
            pack_duration: stats.pack_duration,
            first_render_duration,
            steady_window_duration,
            refresh_count,
            refresh_hz,
            batches_submitted: steady_end_stats.batches_submitted,
            words_written: steady_end_stats.words_written,
            drain_failures: steady_end_stats.drain_failures,
            stop_requests_seen_during_batch: steady_end_stats.stop_requests_seen_during_batch,
            mmio_write_ns: steady_end_stats.mmio_write_ns,
            drain_ns: steady_end_stats.drain_ns,
            max_batch_replays: steady_end_stats.max_batch_replays,
            worker_cpu: steady_end_stats.worker_cpu,
            worker_priority: steady_end_stats.worker_priority,
            worker_runnable: steady_end_stats.worker_runnable,
        })
    })();

    let stop_result = transport.stop();
    match (benchmark, stop_result) {
        (Ok(sample), Ok(())) => Ok(sample),
        (Err(error), Ok(())) => Err(error),
        (Ok(_), Err(error)) => Err(error),
        (Err(error), Err(stop_error)) => Err(format!(
            "{error} Resident loop shutdown also failed: {stop_error}"
        )),
    }
}

fn cycle_stats(total_duration: Duration, frame_count: usize) -> CycleStats {
    let mean_duration = Duration::from_secs_f64(total_duration.as_secs_f64() / frame_count as f64);
    let frames_per_second = frame_count as f64 / total_duration.as_secs_f64();
    CycleStats {
        total_duration,
        mean_duration,
        frames_per_second,
    }
}

fn mean_ns(samples: &[Duration]) -> u128 {
    samples.iter().map(Duration::as_nanos).sum::<u128>() / samples.len() as u128
}

#[derive(Clone, Copy, Debug)]
struct ScanMetrics {
    row_pairs: usize,
    group_count: usize,
    shift_words: usize,
    dwell_ticks_total: u64,
    fixed_delay_ticks_total: u64,
    estimated_cycles: u64,
}

fn estimate_scan_metrics(config: &Pi5ScanConfig) -> Result<ScanMetrics, String> {
    let row_pairs = config.row_pairs()?;
    let width = usize::try_from(config.width()?)
        .map_err(|_| "Pi 5 scan width exceeds host usize.".to_string())?;
    let group_count = row_pairs * usize::from(config.pwm_bits);
    let shift_words = group_count * width;
    let fixed_delay_ticks_per_group = u64::from(
        config.timing().post_addr_ticks
            + config.timing().latch_ticks
            + config.timing().post_latch_ticks
            + 1,
    );
    let mut dwell_ticks_total = 0_u64;
    for _row_pair in 0..row_pairs {
        for plane_index in 0..usize::from(config.pwm_bits) {
            let msb_first_shift = usize::from(config.pwm_bits) - plane_index - 1;
            dwell_ticks_total += u64::from(config.lsb_dwell_ticks) << msb_first_shift;
        }
    }
    let fixed_delay_ticks_total =
        fixed_delay_ticks_per_group * u64::try_from(group_count).unwrap_or(u64::MAX);
    let estimated_cycles = u64::try_from(group_count)
        .map_err(|_| "Pi 5 scan group count exceeds 64-bit cycle estimation.".to_string())?
        .checked_mul(PI5_SCAN_SHARED_PROGRAM_LENGTH)
        .and_then(|value| value.checked_add(2 * u64::try_from(shift_words).ok()?))
        .and_then(|value| value.checked_add(2 * dwell_ticks_total))
        .and_then(|value| value.checked_add(2 * fixed_delay_ticks_total))
        .ok_or_else(|| "Pi 5 scan estimated cycle count overflowed.".to_string())?;

    Ok(ScanMetrics {
        row_pairs,
        group_count,
        shift_words,
        dwell_ticks_total,
        fixed_delay_ticks_total,
        estimated_cycles,
    })
}
