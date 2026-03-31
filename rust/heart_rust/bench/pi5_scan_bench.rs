#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{PackedScanFrame, Pi5PioScanTransport, Pi5ScanConfig, WiringProfile};
use std::env;
use std::process::ExitCode;
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_FRAME_COUNT: usize = 32;
const DEFAULT_ITERATIONS: usize = 3;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_PIPELINE_DEPTH: usize = 2;

#[derive(Clone, Copy, Debug)]
struct BenchOptions {
    frame_count: usize,
    iterations: usize,
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    pipeline_depth: usize,
}

#[derive(Clone, Copy, Debug)]
struct CycleStats {
    total_duration: Duration,
    mean_duration: Duration,
    frames_per_second: f64,
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
    )?;
    let width = config.width()?;
    let height = config.height()?;
    let frames = build_frames(width, height, options.frame_count);
    let mut transport = Pi5PioScanTransport::new(config.estimated_word_count()?, config.pinout())?;

    let mut pack_samples = Vec::with_capacity(options.iterations);
    let mut stream_samples = Vec::with_capacity(options.iterations);
    let mut word_count = 0_usize;

    for iteration in 0..options.iterations {
        let mut frame = frame_bytes(width, height, 31);
        frame[0] = frame[0].wrapping_add(iteration as u8);
        let sample = transport.benchmark_rgba(&config, &frame)?;
        word_count = sample.word_count;
        pack_samples.push(sample.pack_duration);
        stream_samples.push(sample.stream_duration);
    }

    let sequential = run_sequential_cycle(&mut transport, &config, &frames)?;
    drop(transport);
    let pipelined = run_pipelined_cycle(&config, &frames, options.pipeline_depth)?;

    println!(
        concat!(
            "{{",
            "\"panel_rows\":{panel_rows},",
            "\"panel_cols\":{panel_cols},",
            "\"chain_length\":{chain_length},",
            "\"parallel\":{parallel},",
            "\"pwm_bits\":11,",
            "\"width\":{width},",
            "\"height\":{height},",
            "\"iterations\":{iterations},",
            "\"frame_count\":{frame_count},",
            "\"word_count\":{word_count},",
            "\"pack_mean_ns\":{pack_mean_ns},",
            "\"stream_mean_ns\":{stream_mean_ns},",
            "\"sequential_cycle_mean_ns\":{sequential_cycle_mean_ns},",
            "\"sequential_cycle_hz\":{sequential_cycle_hz:.3},",
            "\"pipelined_cycle_mean_ns\":{pipelined_cycle_mean_ns},",
            "\"pipelined_cycle_hz\":{pipelined_cycle_hz:.3},",
            "\"pipeline_speedup\":{pipeline_speedup:.3}",
            "}}"
        ),
        panel_rows = options.panel_rows,
        panel_cols = options.panel_cols,
        chain_length = options.chain_length,
        parallel = options.parallel,
        width = width,
        height = height,
        iterations = options.iterations,
        frame_count = options.frame_count,
        word_count = word_count,
        pack_mean_ns = mean_ns(&pack_samples),
        stream_mean_ns = mean_ns(&stream_samples),
        sequential_cycle_mean_ns = sequential.mean_duration.as_nanos(),
        sequential_cycle_hz = sequential.frames_per_second,
        pipelined_cycle_mean_ns = pipelined.mean_duration.as_nanos(),
        pipelined_cycle_hz = pipelined.frames_per_second,
        pipeline_speedup = pipelined.frames_per_second / sequential.frames_per_second,
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
        pipeline_depth: DEFAULT_PIPELINE_DEPTH,
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
            "--pipeline-depth" => options.pipeline_depth = parse_value(next, flag)?,
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

fn frame_bytes(width: u32, height: u32, seed: u8) -> Vec<u8> {
    let byte_count = (width as usize) * (height as usize) * 4;
    (0..byte_count)
        .map(|index| seed.wrapping_add(index as u8))
        .collect()
}

fn build_frames(width: u32, height: u32, frame_count: usize) -> Vec<Vec<u8>> {
    (0..frame_count)
        .map(|index| frame_bytes(width, height, (index as u8).wrapping_mul(19)))
        .collect()
}

fn run_sequential_cycle(
    transport: &mut Pi5PioScanTransport,
    config: &Pi5ScanConfig,
    frames: &[Vec<u8>],
) -> Result<CycleStats, String> {
    let start = std::time::Instant::now();
    for frame in frames {
        let (packed, _) = PackedScanFrame::pack_rgba(config, frame)?;
        transport.stream(&packed)?;
    }
    Ok(cycle_stats(start.elapsed(), frames.len()))
}

fn run_pipelined_cycle(
    config: &Pi5ScanConfig,
    frames: &[Vec<u8>],
    pipeline_depth: usize,
) -> Result<CycleStats, String> {
    let bounded_depth = pipeline_depth.max(1);
    let (sender, receiver) = mpsc::sync_channel::<Result<PackedScanFrame, String>>(bounded_depth);
    let producer_frames = frames.to_vec();
    let producer_config = *config;

    let producer = thread::Builder::new()
        .name("heart-pi5-scan-pack".to_string())
        .spawn(move || {
            for frame in producer_frames {
                let result =
                    PackedScanFrame::pack_rgba(&producer_config, &frame).map(|(packed, _)| packed);
                if sender.send(result).is_err() {
                    return;
                }
            }
        })
        .map_err(|error| error.to_string())?;

    let start = std::time::Instant::now();
    let mut transport = Pi5PioScanTransport::new(config.estimated_word_count()?, config.pinout())?;
    for _ in 0..frames.len() {
        let packed = receiver.recv().map_err(|_| {
            "Pi 5 scan pipeline closed before all frames were packed.".to_string()
        })??;
        transport.stream(&packed)?;
    }
    producer
        .join()
        .map_err(|_| "Pi 5 scan producer thread panicked.".to_string())?;
    Ok(cycle_stats(start.elapsed(), frames.len()))
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
