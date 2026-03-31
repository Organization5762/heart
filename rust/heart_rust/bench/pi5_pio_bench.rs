#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{Pi5PioDmaTransport, Pi5TransportConfig};
use std::env;
use std::process::ExitCode;
use std::sync::mpsc;
use std::thread;
use std::time::Duration;

const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_FRAME_COUNT: usize = 64;
const DEFAULT_ITERATIONS: usize = 5;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_PIPELINE_DEPTH: usize = 2;
const DEFAULT_PWM_BITS: u8 = 11;

#[derive(Clone, Copy, Debug)]
struct BenchOptions {
    frame_count: usize,
    iterations: usize,
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    pipeline_depth: usize,
    pwm_bits: u8,
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
    let config = Pi5TransportConfig::new(
        options.panel_rows,
        options.panel_cols,
        options.chain_length,
        options.parallel,
        options.pwm_bits,
    )?;
    let width = config.width()?;
    let height = config.height()?;
    let mut transport = Pi5PioDmaTransport::new(config.packed_frame_len()?)?;
    let frame = frame_bytes(width, height, 19);

    let mut pack_samples = Vec::with_capacity(options.iterations);
    let mut dma_samples = Vec::with_capacity(options.iterations);
    let mut packed_bytes = 0_usize;
    let frames = build_frames(width, height, options.frame_count);

    for iteration in 0..options.iterations {
        let mut frame = frame.clone();
        frame[0] = frame[0].wrapping_add(iteration as u8);
        let sample = transport.benchmark_rgba(&config, &frame)?;
        packed_bytes = sample.packed_bytes;
        pack_samples.push(sample.pack_duration);
        dma_samples.push(sample.dma_duration);
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
            "\"pwm_bits\":{pwm_bits},",
            "\"width\":{width},",
            "\"height\":{height},",
            "\"iterations\":{iterations},",
            "\"frame_count\":{frame_count},",
            "\"packed_bytes\":{packed_bytes},",
            "\"pack_mean_ns\":{pack_mean_ns},",
            "\"pack_min_ns\":{pack_min_ns},",
            "\"pack_max_ns\":{pack_max_ns},",
            "\"dma_mean_ns\":{dma_mean_ns},",
            "\"dma_min_ns\":{dma_min_ns},",
            "\"dma_max_ns\":{dma_max_ns},",
            "\"sequential_cycle_total_ns\":{sequential_cycle_total_ns},",
            "\"sequential_cycle_mean_ns\":{sequential_cycle_mean_ns},",
            "\"sequential_cycle_hz\":{sequential_cycle_hz:.3},",
            "\"pipelined_cycle_total_ns\":{pipelined_cycle_total_ns},",
            "\"pipelined_cycle_mean_ns\":{pipelined_cycle_mean_ns},",
            "\"pipelined_cycle_hz\":{pipelined_cycle_hz:.3},",
            "\"pipeline_speedup\":{pipeline_speedup:.3},",
            "\"transport_only_hz\":{transport_only_hz:.3},",
            "\"transport_only_mib_per_sec\":{transport_only_mib_per_sec:.3}",
            "}}"
        ),
        panel_rows = options.panel_rows,
        panel_cols = options.panel_cols,
        chain_length = options.chain_length,
        parallel = options.parallel,
        pwm_bits = options.pwm_bits,
        width = width,
        height = height,
        iterations = options.iterations,
        frame_count = options.frame_count,
        packed_bytes = packed_bytes,
        pack_mean_ns = mean_ns(&pack_samples),
        pack_min_ns = min_ns(&pack_samples),
        pack_max_ns = max_ns(&pack_samples),
        dma_mean_ns = mean_ns(&dma_samples),
        dma_min_ns = min_ns(&dma_samples),
        dma_max_ns = max_ns(&dma_samples),
        sequential_cycle_total_ns = sequential.total_duration.as_nanos(),
        sequential_cycle_mean_ns = sequential.mean_duration.as_nanos(),
        sequential_cycle_hz = sequential.frames_per_second,
        pipelined_cycle_total_ns = pipelined.total_duration.as_nanos(),
        pipelined_cycle_mean_ns = pipelined.mean_duration.as_nanos(),
        pipelined_cycle_hz = pipelined.frames_per_second,
        pipeline_speedup = pipelined.frames_per_second / sequential.frames_per_second,
        transport_only_hz = 1_000_000_000_f64 / (mean_ns(&dma_samples) as f64),
        transport_only_mib_per_sec = ((packed_bytes as f64) / (1024.0 * 1024.0))
            / ((mean_ns(&dma_samples) as f64) / 1_000_000_000.0),
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
        pwm_bits: DEFAULT_PWM_BITS,
    };
    let mut index = 0;
    while index < arguments.len() {
        let value = arguments[index].as_str();
        if value == "--help" {
            return Err(
                "Usage: cargo run --bin pi5_pio_bench -- --panel-rows 64 --panel-cols 64 --chain-length 1 --parallel 1 --pwm-bits 11 --iterations 5".to_string(),
            );
        }
        let next = arguments
            .get(index + 1)
            .ok_or_else(|| format!("Expected a value after {value}."))?;
        match value {
            "--frame-count" => options.frame_count = parse_value(next, value)?,
            "--iterations" => options.iterations = parse_value(next, value)?,
            "--panel-rows" => options.panel_rows = parse_value(next, value)?,
            "--panel-cols" => options.panel_cols = parse_value(next, value)?,
            "--chain-length" => options.chain_length = parse_value(next, value)?,
            "--parallel" => options.parallel = parse_value(next, value)?,
            "--pipeline-depth" => options.pipeline_depth = parse_value(next, value)?,
            "--pwm-bits" => options.pwm_bits = parse_value(next, value)?,
            _ => return Err(format!("Unknown argument {value}.")),
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
        .map(|index| frame_bytes(width, height, (index as u8).wrapping_mul(17)))
        .collect()
}

#[derive(Clone, Copy, Debug)]
struct CycleStats {
    total_duration: Duration,
    mean_duration: Duration,
    frames_per_second: f64,
}

fn run_sequential_cycle(
    transport: &mut Pi5PioDmaTransport,
    config: &Pi5TransportConfig,
    frames: &[Vec<u8>],
) -> Result<CycleStats, String> {
    let start = std::time::Instant::now();
    for frame in frames {
        let (packed, _) = runtime::PackedTransportFrame::pack_rgba(config, frame)?;
        transport.stream(&packed)?;
    }
    Ok(cycle_stats(start.elapsed(), frames.len()))
}

fn run_pipelined_cycle(
    config: &Pi5TransportConfig,
    frames: &[Vec<u8>],
    pipeline_depth: usize,
) -> Result<CycleStats, String> {
    let bounded_depth = pipeline_depth.max(1);
    let (sender, receiver) =
        mpsc::sync_channel::<Result<runtime::PackedTransportFrame, String>>(bounded_depth);
    let producer_frames = frames.to_vec();
    let producer_config = *config;
    let producer = thread::Builder::new()
        .name("heart-pi5-pack-pipeline".to_string())
        .spawn(move || {
            for frame in producer_frames {
                if sender
                    .send(
                        runtime::PackedTransportFrame::pack_rgba(&producer_config, &frame)
                            .map(|(packed, _)| packed),
                    )
                    .is_err()
                {
                    return;
                }
            }
        })
        .map_err(|error| error.to_string())?;

    let start = std::time::Instant::now();
    let mut transport = Pi5PioDmaTransport::new(config.packed_frame_len()?)?;
    for _ in 0..frames.len() {
        let packed = receiver.recv().map_err(|_| {
            "Pi 5 pack pipeline closed before all frames were produced.".to_string()
        })??;
        transport.stream(&packed)?;
    }
    producer
        .join()
        .map_err(|_| "Pi 5 pack pipeline thread panicked.".to_string())?;
    Ok(cycle_stats(start.elapsed(), frames.len()))
}

fn cycle_stats(total_duration: Duration, frame_count: usize) -> CycleStats {
    let mean_nanos = total_duration.as_nanos() / frame_count.max(1) as u128;
    CycleStats {
        total_duration,
        mean_duration: Duration::from_nanos(mean_nanos.min(u128::from(u64::MAX)) as u64),
        frames_per_second: frame_count as f64 / total_duration.as_secs_f64(),
    }
}

fn max_ns(samples: &[Duration]) -> u128 {
    samples
        .iter()
        .map(Duration::as_nanos)
        .max()
        .unwrap_or_default()
}

fn mean_ns(samples: &[Duration]) -> u128 {
    if samples.is_empty() {
        return 0;
    }
    samples.iter().map(Duration::as_nanos).sum::<u128>() / samples.len() as u128
}

fn min_ns(samples: &[Duration]) -> u128 {
    samples
        .iter()
        .map(Duration::as_nanos)
        .min()
        .unwrap_or_default()
}
