#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{
    build_simple_group_words_for_rgba, gpio_is_high, pio_program_info_for_format,
    simulate_simple_hub75_group, Pi5ScanConfig, Pi5ScanFormat, WiringProfile,
};
use std::env;
use std::process::ExitCode;

const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_ROW_PAIR: usize = 0;
const DEFAULT_PLANE_INDEX: usize = 0;
const DEFAULT_STEP_LIMIT: usize = 160;

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
    .with_format(Pi5ScanFormat::Simple)?
    .with_pwm_bits(1)?;
    let frame = match options.pattern.as_str() {
        "blue" => solid_rgba_frame(config.width()?, config.height()?, 0, 0, 255),
        "red" => solid_rgba_frame(config.width()?, config.height()?, 255, 0, 0),
        "row-bars" => row_bars_rgba_frame(config.width()?, config.height()?, options.row_pair),
        other => {
            return Err(format!(
                "Unsupported pattern {other:?}. Expected one of: blue, red, row-bars."
            ))
        }
    };
    let words =
        build_simple_group_words_for_rgba(&config, &frame, options.row_pair, options.plane_index)?;
    let simulation = simulate_simple_hub75_group(&config, &words)?;
    let program_info = pio_program_info_for_format(&config, Pi5ScanFormat::Simple);

    println!(
        "simple-group row_pair={} plane_index={} fifo_words={} stalled_on_pull={} wrap={}->{}",
        options.row_pair,
        options.plane_index,
        words.len(),
        simulation.stalled_on_pull,
        program_info.wrap_target,
        program_info.wrap
    );
    println!("program opcodes:");
    for instruction in &program_info.instructions {
        let mut notes = Vec::new();
        if instruction.out_writes_window {
            notes.push("OUT window".to_string());
        }
        if instruction.set_writes_pins {
            notes.push("SET LAT".to_string());
        }
        if let Some(level) = instruction.sideset_clock {
            notes.push(if level {
                "CLK high".to_string()
            } else {
                "CLK low".to_string()
            });
        }
        if instruction.delay_cycles != 0 {
            notes.push(format!("delay={}", instruction.delay_cycles));
        }
        println!(
            "  {:02}: 0x{:04x} {} [{}]",
            instruction.index,
            instruction.instruction,
            instruction.mnemonic,
            notes.join(", ")
        );
    }
    println!();
    println!("trace:");
    println!("cycle      pc  instr   x          y          osr        clk lat oe  r1 g1 b1 r2 g2 b2  addr");
    for step in simulation.steps.iter().take(options.step_limit) {
        println!(
            "{:5}-{:5} {:02}  0x{:04x} {:10} {:10} 0x{:08x}  {}   {}   {}   {}  {}  {}  {}  {}  {}   {:02}",
            step.cycle_start,
            step.cycle_end,
            step.pc,
            step.instruction,
            step.x,
            step.y,
            step.osr,
            bit(step.pins, 17),
            bit(step.pins, 21),
            bit(step.pins, 18),
            bit(step.pins, 5),
            bit(step.pins, 13),
            bit(step.pins, 6),
            bit(step.pins, 12),
            bit(step.pins, 16),
            bit(step.pins, 23),
            decode_row_pair(step.pins),
        );
    }
    if simulation.steps.len() > options.step_limit {
        println!(
            "... {} additional steps omitted",
            simulation.steps.len() - options.step_limit
        );
    }
    Ok(())
}

#[derive(Clone, Debug)]
struct Options {
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    row_pair: usize,
    plane_index: usize,
    step_limit: usize,
    pattern: String,
}

fn parse_args(args: Vec<String>) -> Result<Options, String> {
    let mut options = Options {
        panel_rows: DEFAULT_PANEL_ROWS,
        panel_cols: DEFAULT_PANEL_COLS,
        chain_length: DEFAULT_CHAIN_LENGTH,
        parallel: DEFAULT_PARALLEL,
        row_pair: DEFAULT_ROW_PAIR,
        plane_index: DEFAULT_PLANE_INDEX,
        step_limit: DEFAULT_STEP_LIMIT,
        pattern: "blue".to_string(),
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
            "--row-pair" => {
                options.row_pair = parse_value(&next(&mut args, "--row-pair")?, "--row-pair")?
            }
            "--plane-index" => {
                options.plane_index =
                    parse_value(&next(&mut args, "--plane-index")?, "--plane-index")?
            }
            "--steps" => options.step_limit = parse_value(&next(&mut args, "--steps")?, "--steps")?,
            "--pattern" => options.pattern = next(&mut args, "--pattern")?,
            "--help" => {
                print_help();
                std::process::exit(0);
            }
            other => return Err(format!("Unknown argument {other:?}. Use --help for usage.")),
        }
    }
    Ok(options)
}

fn print_help() {
    println!("Usage: cargo run --bin pi5_pio_sim_trace -- [options]");
    println!("  --pattern <name>       blue|red|row-bars");
    println!("  --row-pair <usize>     default 0");
    println!("  --plane-index <usize>  default 0");
    println!("  --steps <usize>        number of trace steps to print");
}

fn parse_value<T: std::str::FromStr>(value: &str, flag: &str) -> Result<T, String>
where
    <T as std::str::FromStr>::Err: std::fmt::Display,
{
    value
        .parse::<T>()
        .map_err(|error| format!("Invalid value for {flag}: {error}"))
}

fn solid_rgba_frame(width: u32, height: u32, red: u8, green: u8, blue: u8) -> Vec<u8> {
    let mut frame = vec![0_u8; (width * height * 4) as usize];
    for pixel in frame.chunks_exact_mut(4) {
        pixel[0] = red;
        pixel[1] = green;
        pixel[2] = blue;
        pixel[3] = 255;
    }
    frame
}

fn row_bars_rgba_frame(width: u32, height: u32, row_pair: usize) -> Vec<u8> {
    let width = width as usize;
    let height = height as usize;
    let row_pairs = height / 2;
    let top_row = row_pair;
    let bottom_row = row_pair + row_pairs;
    let mut frame = vec![0_u8; width * height * 4];

    for column in 0..width {
        let bar_index = column / 8;
        let top_offset = ((top_row * width) + column) * 4;
        let bottom_offset = ((bottom_row * width) + column) * 4;
        if bar_index % 2 == 0 {
            frame[top_offset] = 255;
            frame[top_offset + 2] = 64;
        } else {
            frame[bottom_offset + 1] = 255;
            frame[bottom_offset + 2] = 64;
        }
        frame[top_offset + 3] = 255;
        frame[bottom_offset + 3] = 255;
    }
    frame
}

fn bit(pins: u32, gpio: u32) -> u8 {
    u8::from(gpio_is_high(pins, gpio))
}

fn decode_row_pair(pins: u32) -> usize {
    let mut row_pair = 0_usize;
    for (bit_index, gpio) in [22_u32, 26, 27, 20, 24].iter().enumerate() {
        if gpio_is_high(pins, *gpio) {
            row_pair |= 1 << bit_index;
        }
    }
    row_pair
}
