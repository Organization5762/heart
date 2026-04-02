#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{PackedScanFrame, Pi5ScanConfig, Pi5ScanFormat, Pi5ScanGroupTrace, WiringProfile};
use std::env;
use std::process::ExitCode;

const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_PWM_BITS: u8 = 11;
const DEFAULT_ROW_PAIR: usize = 0;
const DEFAULT_PLANE_INDEX: usize = 0;
const DEFAULT_SEED: u8 = 255;

#[derive(Clone, Copy, Debug)]
enum FramePattern {
    Black,
    Blue,
    Dense,
    Solid,
    Striped,
}

impl FramePattern {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "black" => Ok(Self::Black),
            "blue" => Ok(Self::Blue),
            "dense" => Ok(Self::Dense),
            "solid" => Ok(Self::Solid),
            "striped" => Ok(Self::Striped),
            _ => Err(format!(
                "Unsupported frame pattern '{value}'. Expected one of: black, blue, dense, solid, striped."
            )),
        }
    }
}

#[derive(Clone, Debug)]
struct TraceOptions {
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    pwm_bits: u8,
    row_pair: usize,
    plane_index: usize,
    frame_pattern: FramePattern,
    seed: u8,
    format: Pi5ScanFormat,
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
    .with_format(options.format)?;
    let width = config.width()?;
    let height = config.height()?;
    let rgba = frame_bytes(width, height, options.seed, options.frame_pattern);
    let expected =
        config.debug_expected_group_trace(&rgba, options.row_pair, options.plane_index)?;
    let (packed, _stats) = PackedScanFrame::pack_rgba(&config, &rgba)?;
    let decoded =
        packed.debug_decode_group_trace(&config, options.row_pair, options.plane_index)?;

    print_trace("expected", &expected);
    print_trace("decoded", &decoded);
    print_diff(&expected, &decoded);
    Ok(())
}

fn print_trace(label: &str, trace: &Pi5ScanGroupTrace) {
    println!("{label}:");
    println!("  blank_word:  0x{:08x}", trace.blank_word);
    println!("  active_word: 0x{:08x}", trace.active_word);
    println!("  dwell_ticks: {}", trace.dwell_ticks);
    println!("  shift_count: {}", trace.shift_words.len());
    for (index, word) in trace.shift_words.iter().take(16).enumerate() {
        println!("  shift[{index:02}]: 0x{word:08x}");
    }
    if trace.shift_words.len() > 16 {
        println!("  ... {} more shift words", trace.shift_words.len() - 16);
    }
}

fn print_diff(expected: &Pi5ScanGroupTrace, decoded: &Pi5ScanGroupTrace) {
    println!("diff:");
    if expected == decoded {
        println!("  traces match");
        return;
    }
    if expected.blank_word != decoded.blank_word {
        println!(
            "  blank_word mismatch: expected=0x{:08x} decoded=0x{:08x}",
            expected.blank_word, decoded.blank_word
        );
    }
    if expected.active_word != decoded.active_word {
        println!(
            "  active_word mismatch: expected=0x{:08x} decoded=0x{:08x}",
            expected.active_word, decoded.active_word
        );
    }
    if expected.dwell_ticks != decoded.dwell_ticks {
        println!(
            "  dwell_ticks mismatch: expected={} decoded={}",
            expected.dwell_ticks, decoded.dwell_ticks
        );
    }
    if expected.shift_words.len() != decoded.shift_words.len() {
        println!(
            "  shift_count mismatch: expected={} decoded={}",
            expected.shift_words.len(),
            decoded.shift_words.len()
        );
    }
    for index in 0..expected.shift_words.len().min(decoded.shift_words.len()) {
        if expected.shift_words[index] != decoded.shift_words[index] {
            println!(
                "  shift[{index}] mismatch: expected=0x{:08x} decoded=0x{:08x}",
                expected.shift_words[index], decoded.shift_words[index]
            );
            break;
        }
    }
}

fn parse_args(arguments: Vec<String>) -> Result<TraceOptions, String> {
    let mut options = TraceOptions {
        panel_rows: DEFAULT_PANEL_ROWS,
        panel_cols: DEFAULT_PANEL_COLS,
        chain_length: DEFAULT_CHAIN_LENGTH,
        parallel: DEFAULT_PARALLEL,
        pwm_bits: DEFAULT_PWM_BITS,
        row_pair: DEFAULT_ROW_PAIR,
        plane_index: DEFAULT_PLANE_INDEX,
        frame_pattern: FramePattern::Solid,
        seed: DEFAULT_SEED,
        format: Pi5ScanFormat::Simple,
    };

    let mut arguments = arguments.into_iter();
    while let Some(argument) = arguments.next() {
        let value = match argument.as_str() {
            "--panel-rows" => arguments
                .next()
                .ok_or_else(|| "Missing value for --panel-rows".to_string())?,
            "--panel-cols" => arguments
                .next()
                .ok_or_else(|| "Missing value for --panel-cols".to_string())?,
            "--chain-length" => arguments
                .next()
                .ok_or_else(|| "Missing value for --chain-length".to_string())?,
            "--parallel" => arguments
                .next()
                .ok_or_else(|| "Missing value for --parallel".to_string())?,
            "--pwm-bits" => arguments
                .next()
                .ok_or_else(|| "Missing value for --pwm-bits".to_string())?,
            "--row-pair" => arguments
                .next()
                .ok_or_else(|| "Missing value for --row-pair".to_string())?,
            "--plane-index" => arguments
                .next()
                .ok_or_else(|| "Missing value for --plane-index".to_string())?,
            "--frame-pattern" => arguments
                .next()
                .ok_or_else(|| "Missing value for --frame-pattern".to_string())?,
            "--seed" => arguments
                .next()
                .ok_or_else(|| "Missing value for --seed".to_string())?,
            "--format" => arguments
                .next()
                .ok_or_else(|| "Missing value for --format".to_string())?,
            _ => return Err(format!("Unknown argument '{argument}'.")),
        };
        match argument.as_str() {
            "--panel-rows" => {
                options.panel_rows = value
                    .parse()
                    .map_err(|_| format!("Invalid panel rows '{value}'."))?
            }
            "--panel-cols" => {
                options.panel_cols = value
                    .parse()
                    .map_err(|_| format!("Invalid panel cols '{value}'."))?
            }
            "--chain-length" => {
                options.chain_length = value
                    .parse()
                    .map_err(|_| format!("Invalid chain length '{value}'."))?
            }
            "--parallel" => {
                options.parallel = value
                    .parse()
                    .map_err(|_| format!("Invalid parallel '{value}'."))?
            }
            "--pwm-bits" => {
                options.pwm_bits = value
                    .parse()
                    .map_err(|_| format!("Invalid pwm bits '{value}'."))?
            }
            "--row-pair" => {
                options.row_pair = value
                    .parse()
                    .map_err(|_| format!("Invalid row pair '{value}'."))?
            }
            "--plane-index" => {
                options.plane_index = value
                    .parse()
                    .map_err(|_| format!("Invalid plane index '{value}'."))?
            }
            "--frame-pattern" => options.frame_pattern = FramePattern::parse(&value)?,
            "--seed" => {
                options.seed = value
                    .parse()
                    .map_err(|_| format!("Invalid seed '{value}'."))?
            }
            "--format" => {
                options.format = match value.as_str() {
                    "simple" => Pi5ScanFormat::Simple,
                    "optimized" => Pi5ScanFormat::Optimized,
                    _ => {
                        return Err(format!(
                            "Unsupported format '{value}'. Expected 'simple' or 'optimized'."
                        ))
                    }
                };
            }
            _ => unreachable!(),
        }
    }
    Ok(options)
}

fn frame_bytes(width: u32, height: u32, seed: u8, pattern: FramePattern) -> Vec<u8> {
    let byte_count = (width as usize) * (height as usize) * 4;
    match pattern {
        FramePattern::Black => vec![0; byte_count],
        FramePattern::Blue => {
            let mut frame = vec![0; byte_count];
            for pixel in frame.chunks_exact_mut(4) {
                pixel[0] = 0;
                pixel[1] = 0;
                pixel[2] = u8::MAX;
                pixel[3] = u8::MAX;
            }
            frame
        }
        FramePattern::Dense => (0..byte_count)
            .map(|index| seed.wrapping_add(index as u8))
            .collect(),
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
                    if (column / 16) % 2 != 0 {
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
