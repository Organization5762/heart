#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{PackedScanFrame, Pi5PioScanTransport, Pi5ScanConfig, Pi5ScanFormat, WiringProfile};
use std::env;
use std::process::ExitCode;
use std::thread;
use std::time::{Duration, Instant};

const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_ROW_INDEX: usize = 0;
const DEFAULT_HOLD_SECONDS: f32 = 8.0;
const DEFAULT_REPEAT_COUNT: usize = 10_000;

#[derive(Clone, Copy, Debug)]
struct SmokeOptions {
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    row_index: usize,
    red: u8,
    green: u8,
    blue: u8,
    hold_seconds: f32,
    repeat_count: usize,
    static_word: Option<u32>,
    static_word_repeat_count: usize,
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
    .with_format(Pi5ScanFormat::Simple)?
    .with_pwm_bits(1)?;
    let width = config.width()?;
    let height = config.height()?;
    if options.row_index >= height as usize {
        return Err(format!(
            "Row index {} is outside height {}.",
            options.row_index, height
        ));
    }
    let row_pair = options.row_index / 2;
    let group_words = if let Some(static_word) = options.static_word {
        vec![static_word; options.static_word_repeat_count]
    } else {
        let top_is_lit = options.row_index % 2 == 0;
        let color = (options.red > 0, options.green > 0, options.blue > 0);
        runtime::build_simple_smoke_group_words(
            &config,
            row_pair,
            if top_is_lit {
                color
            } else {
                (false, false, false)
            },
            if top_is_lit {
                (false, false, false)
            } else {
                color
            },
            config.lsb_dwell_ticks,
        )?
    };
    let word_count = group_words.len();
    let packed = PackedScanFrame::from_words(group_words);
    let transport = Pi5PioScanTransport::new(
        config.estimated_word_count()?,
        config.pinout(),
        config.timing(),
        config.format(),
    )?;

    println!(
        "pi5_pio_smoke backend=synchronous-simple width={} height={} row={} rgb=({}, {}, {}) word_count={}",
        width,
        height,
        options.row_index,
        options.red,
        options.green,
        options.blue,
        word_count
    );

    let deadline = Instant::now() + Duration::from_secs_f32(options.hold_seconds);
    let mut submits = 0_usize;
    while submits < options.repeat_count && Instant::now() < deadline {
        transport.submit_blocking(&packed)?;
        submits += 1;
    }
    println!("completed_submits={submits}");
    thread::sleep(Duration::from_millis(50));
    Ok(())
}

fn parse_args(args: Vec<String>) -> Result<SmokeOptions, String> {
    let mut options = SmokeOptions {
        panel_rows: DEFAULT_PANEL_ROWS,
        panel_cols: DEFAULT_PANEL_COLS,
        chain_length: DEFAULT_CHAIN_LENGTH,
        parallel: DEFAULT_PARALLEL,
        row_index: DEFAULT_ROW_INDEX,
        red: 255,
        green: 255,
        blue: 255,
        hold_seconds: DEFAULT_HOLD_SECONDS,
        repeat_count: DEFAULT_REPEAT_COUNT,
        static_word: None,
        static_word_repeat_count: 4096,
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
            "--row-index" => {
                options.row_index = parse_value(&next(&mut args, "--row-index")?, "--row-index")?
            }
            "--red" => options.red = parse_value(&next(&mut args, "--red")?, "--red")?,
            "--green" => options.green = parse_value(&next(&mut args, "--green")?, "--green")?,
            "--blue" => options.blue = parse_value(&next(&mut args, "--blue")?, "--blue")?,
            "--hold-seconds" => {
                options.hold_seconds =
                    parse_value(&next(&mut args, "--hold-seconds")?, "--hold-seconds")?
            }
            "--repeat-count" => {
                options.repeat_count =
                    parse_value(&next(&mut args, "--repeat-count")?, "--repeat-count")?
            }
            "--static-word" => {
                options.static_word = Some(parse_hex_value(
                    &next(&mut args, "--static-word")?,
                    "--static-word",
                )?)
            }
            "--static-word-repeat-count" => {
                options.static_word_repeat_count = parse_value(
                    &next(&mut args, "--static-word-repeat-count")?,
                    "--static-word-repeat-count",
                )?
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

fn parse_value<T: std::str::FromStr>(value: &str, flag: &str) -> Result<T, String> {
    value
        .parse::<T>()
        .map_err(|_| format!("Invalid value {value:?} for {flag}."))
}

fn parse_hex_value(value: &str, flag: &str) -> Result<u32, String> {
    let trimmed = value
        .strip_prefix("0x")
        .or_else(|| value.strip_prefix("0X"))
        .unwrap_or(value);
    u32::from_str_radix(trimmed, 16).map_err(|_| format!("Invalid hex value {value:?} for {flag}."))
}

fn print_help() {
    println!("Usage: pi5_pio_smoke [options]");
    println!("  --panel-rows <u16>       default 64");
    println!("  --panel-cols <u16>       default 64");
    println!("  --chain-length <u16>     default 1");
    println!("  --parallel <u8>          default 1");
    println!("  --row-index <usize>      default 0");
    println!("  --red <u8>               default 255");
    println!("  --green <u8>             default 255");
    println!("  --blue <u8>              default 255");
    println!("  --hold-seconds <f32>     default 8");
    println!("  --repeat-count <usize>   default 10000");
    println!("  --static-word <hex>      repeatedly write one rebased GPIO word (currently 24-bit simple bus)");
    println!("  --static-word-repeat-count <usize>   default 4096");
}
