#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use heart_pio_sim::simulate_program;
use runtime::{
    gpio_is_high, piomatter_row_compact_engine_parity_program_info,
    piomatter_row_compact_tight_engine_parity_program_info,
    piomatter_row_counted_engine_parity_program_info,
    piomatter_row_hybrid_engine_parity_program_info,
    piomatter_row_repeat_engine_parity_program_info,
    piomatter_row_runs_engine_parity_program_info,
    piomatter_row_split_engine_parity_program_info,
    piomatter_row_window_engine_parity_program_info, Pi5ScanConfig, Pi5ScanFormat,
    WiringProfile,
};
use std::env;
use std::process::ExitCode;

const DEFAULT_PATTERN: &str = "all";
const DEFAULT_PANEL_ROWS: u16 = 64;
const DEFAULT_PANEL_COLS: u16 = 64;
const DEFAULT_CHAIN_LENGTH: u16 = 1;
const DEFAULT_PARALLEL: u8 = 1;
const DEFAULT_MAX_STEPS: usize = 4096;

const R1_GPIO: u32 = 5;
const G1_GPIO: u32 = 13;
const B1_GPIO: u32 = 6;
const R2_GPIO: u32 = 12;
const G2_GPIO: u32 = 16;
const B2_GPIO: u32 = 23;
const CLK_GPIO: u32 = 17;
const OE_GPIO: u32 = 18;

const PIOMATTER_ROW_COMPACT_COMMAND_LITERAL_BASE: u32 = 0;
const PIOMATTER_ROW_COMPACT_COMMAND_REPEAT_BASE: u32 = 1_u32 << 31;
const PIOMATTER_ROW_COMPACT_COMMAND_ACTIVE_HOLD_SHIFT: u32 = 8;
const PIOMATTER_ROW_COMPACT_COMMAND_WIDTH_MASK: u32 = (1_u32 << 8) - 1;
const PIOMATTER_ROW_COMPACT_COMMAND_ACTIVE_HOLD_LIMIT: u32 =
    (1_u32 << (31 - PIOMATTER_ROW_COMPACT_COMMAND_ACTIVE_HOLD_SHIFT)) - 1;
const PIOMATTER_ROW_COUNTED_COMMAND_LITERAL_BASE: u32 = 0;
const PIOMATTER_ROW_COUNTED_COMMAND_REPEAT_BASE: u32 = 1_u32 << 31;
const PIOMATTER_ROW_HYBRID_COMMAND_KIND_SHIFT: u32 = 30;
const PIOMATTER_ROW_HYBRID_COMMAND_LITERAL_BASE: u32 = 0;
const PIOMATTER_ROW_HYBRID_COMMAND_REPEAT_BASE: u32 = 1_u32 << PIOMATTER_ROW_HYBRID_COMMAND_KIND_SHIFT;
const PIOMATTER_ROW_HYBRID_COMMAND_SPLIT_BASE: u32 = 2_u32 << PIOMATTER_ROW_HYBRID_COMMAND_KIND_SHIFT;
const PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_SHIFT: u32 = 8;
const PIOMATTER_ROW_HYBRID_COMMAND_WIDTH_MASK: u32 = (1_u32 << 8) - 1;
const PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_LIMIT: u32 =
    (1_u32 << (PIOMATTER_ROW_HYBRID_COMMAND_KIND_SHIFT - PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_SHIFT)) - 1;
const PIOMATTER_ROW_RUNS_COMMAND_EXTRA_RUNS_SHIFT: u32 = 30;
const PIOMATTER_ROW_RUNS_COMMAND_FIRST_WIDTH_SHIFT: u32 = 22;
const PIOMATTER_ROW_RUNS_COMMAND_FIRST_WIDTH_MASK: u32 = (1_u32 << 8) - 1;
const PIOMATTER_ROW_RUNS_COMMAND_ACTIVE_HOLD_LIMIT: u32 =
    (1_u32 << PIOMATTER_ROW_RUNS_COMMAND_FIRST_WIDTH_SHIFT) - 1;
const PIOMATTER_ROW_WINDOW_COMMAND_KIND_SHIFT: u32 = 30;
const PIOMATTER_ROW_WINDOW_COMMAND_LITERAL_BASE: u32 = 0;
const PIOMATTER_ROW_WINDOW_COMMAND_REPEAT_BASE: u32 =
    1_u32 << PIOMATTER_ROW_WINDOW_COMMAND_KIND_SHIFT;
const PIOMATTER_ROW_WINDOW_COMMAND_SPLIT_BASE: u32 =
    2_u32 << PIOMATTER_ROW_WINDOW_COMMAND_KIND_SHIFT;
const PIOMATTER_ROW_WINDOW_COMMAND_WINDOW_BASE: u32 =
    3_u32 << PIOMATTER_ROW_WINDOW_COMMAND_KIND_SHIFT;
const PIOMATTER_ROW_SPLIT_COMMAND_REPEAT_BASE: u32 = 0;
const PIOMATTER_ROW_SPLIT_COMMAND_SPLIT_BASE: u32 = 1_u32 << 31;
const PIOMATTER_ROW_SPLIT_COMMAND_COUNTED_TRAILER: u32 = 1_u32 << 30;
const PIOMATTER_ROW_REPEAT_COMMAND_LITERAL: u32 = 0b10_u32 << 30;
const PIOMATTER_ROW_REPEAT_COMMAND_REPEAT: u32 = 0b11_u32 << 30;

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
    .with_format(Pi5ScanFormat::Simple)?;
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_compact_program = piomatter_row_compact_engine_parity_program_info(&config);
    let row_compact_tight_program = piomatter_row_compact_tight_engine_parity_program_info(&config);
    let row_counted_program = piomatter_row_counted_engine_parity_program_info(&config);
    let row_hybrid_program = piomatter_row_hybrid_engine_parity_program_info(&config);
    let row_runs_program = piomatter_row_runs_engine_parity_program_info(&config);
    let row_split_program = piomatter_row_split_engine_parity_program_info(&config);
    let row_window_program = piomatter_row_window_engine_parity_program_info(&config);

    let scenarios = match options.pattern.as_str() {
        "all" => vec![
            dark_row_scenario(),
            repeated_blue_scenario(),
            alternating_scenario(),
            quadrant_scenario(),
            center_box_scenario(),
        ],
        "dark-row" => vec![dark_row_scenario()],
        "repeated-blue" => vec![repeated_blue_scenario()],
        "alternating" => vec![alternating_scenario()],
        "quadrants" => vec![quadrant_scenario()],
        "center-box" => vec![center_box_scenario()],
        other => {
            return Err(format!(
                "Unsupported pattern {other:?}. Expected one of: all, dark-row, repeated-blue, alternating, quadrants, center-box."
            ))
        }
    };

    println!(
        "row-pattern cost benchmark panel={}x{} chain_length={} parallel={}",
        options.panel_cols, options.panel_rows, options.chain_length, options.parallel
    );
    println!();

    for scenario in scenarios {
        let row_repeat_sim = simulate_program(
            &row_repeat_program.program,
            row_repeat_program.simulator_config,
            &scenario.row_repeat_words,
            options.max_steps,
        )
        .map_err(|error| format!("row-repeat {} failed: {error}", scenario.name))?;
        let row_compact_sim = simulate_program(
            &row_compact_program.program,
            row_compact_program.simulator_config,
            &scenario.row_compact_words,
            options.max_steps,
        )
        .map_err(|error| format!("row-compact {} failed: {error}", scenario.name))?;

        let row_repeat_trace = extract_gpio_observable_trace(&row_repeat_sim);
        let row_compact_trace = extract_gpio_observable_trace(&row_compact_sim);
        if row_repeat_trace.low_words[..scenario.shift_word_count]
            != row_compact_trace.low_words[..scenario.shift_word_count]
        {
            return Err(format!(
                "row-compact low GPIO waveform drifted for {}",
                scenario.name
            ));
        }
        if row_repeat_trace.high_words[..scenario.shift_word_count]
            != row_compact_trace.high_words[..scenario.shift_word_count]
        {
            return Err(format!(
                "row-compact high GPIO waveform drifted for {}",
                scenario.name
            ));
        }

        let row_repeat_cycles = row_repeat_sim
            .steps
            .last()
            .map(|step| step.cycle_end)
            .unwrap_or(0);
        let row_compact_cycles = row_compact_sim
            .steps
            .last()
            .map(|step| step.cycle_end)
            .unwrap_or(0);
        let row_compact_tight_sim = simulate_program(
            &row_compact_tight_program.program,
            row_compact_tight_program.simulator_config,
            &scenario.row_compact_words,
            options.max_steps,
        )
        .map_err(|error| format!("row-compact-tight {} failed: {error}", scenario.name))?;
        let row_compact_tight_trace = extract_gpio_observable_trace(&row_compact_tight_sim);
        if row_repeat_trace.low_words[..scenario.shift_word_count]
            != row_compact_tight_trace.low_words[..scenario.shift_word_count]
        {
            return Err(format!(
                "row-compact-tight low GPIO waveform drifted for {}",
                scenario.name
            ));
        }
        if row_repeat_trace.high_words[..scenario.shift_word_count]
            != row_compact_tight_trace.high_words[..scenario.shift_word_count]
        {
            return Err(format!(
                "row-compact-tight high GPIO waveform drifted for {}",
                scenario.name
            ));
        }
        let row_compact_tight_cycles = row_compact_tight_sim
            .steps
            .last()
            .map(|step| step.cycle_end)
            .unwrap_or(0);
        let row_hybrid_sim = simulate_program(
            &row_hybrid_program.program,
            row_hybrid_program.simulator_config,
            &scenario.row_hybrid_words,
            options.max_steps,
        )
        .map_err(|error| format!("row-hybrid {} failed: {error}", scenario.name))?;
        let row_hybrid_trace = extract_gpio_observable_trace(&row_hybrid_sim);
        if row_repeat_trace.low_words[..scenario.shift_word_count]
            != row_hybrid_trace.low_words[..scenario.shift_word_count]
        {
            return Err(format!(
                "row-hybrid low GPIO waveform drifted for {}",
                scenario.name
            ));
        }
        if row_repeat_trace.high_words[..scenario.shift_word_count]
            != row_hybrid_trace.high_words[..scenario.shift_word_count]
        {
            return Err(format!(
                "row-hybrid high GPIO waveform drifted for {}",
                scenario.name
            ));
        }
        let row_hybrid_cycles = row_hybrid_sim
            .steps
            .last()
            .map(|step| step.cycle_end)
            .unwrap_or(0);
        let row_counted_sim = simulate_program(
            &row_counted_program.program,
            row_counted_program.simulator_config,
            &scenario.row_counted_words,
            options.max_steps,
        )
        .map_err(|error| format!("row-counted {} failed: {error}", scenario.name))?;
        let row_counted_trace = extract_gpio_observable_trace(&row_counted_sim);
        if row_repeat_trace.low_words[..scenario.shift_word_count]
            != row_counted_trace.low_words[..scenario.shift_word_count]
        {
            return Err(format!(
                "row-counted low GPIO waveform drifted for {}",
                scenario.name
            ));
        }
        if row_repeat_trace.high_words[..scenario.shift_word_count]
            != row_counted_trace.high_words[..scenario.shift_word_count]
        {
            return Err(format!(
                "row-counted high GPIO waveform drifted for {}",
                scenario.name
            ));
        }
        let row_counted_cycles = row_counted_sim
            .steps
            .last()
            .map(|step| step.cycle_end)
            .unwrap_or(0);

        let row_runs_metrics = if let Some(row_runs_words) = &scenario.row_runs_words {
            let row_runs_sim = simulate_program(
                &row_runs_program.program,
                row_runs_program.simulator_config,
                row_runs_words,
                options.max_steps,
            )
            .map_err(|error| format!("row-runs {} failed: {error}", scenario.name))?;
            let row_runs_trace = extract_gpio_observable_trace(&row_runs_sim);
            if row_repeat_trace.low_words[..scenario.shift_word_count]
                != row_runs_trace.low_words[..scenario.shift_word_count]
            {
                return Err(format!(
                    "row-runs low GPIO waveform drifted for {}",
                    scenario.name
                ));
            }
            if row_repeat_trace.high_words[..scenario.shift_word_count]
                != row_runs_trace.high_words[..scenario.shift_word_count]
            {
                return Err(format!(
                    "row-runs high GPIO waveform drifted for {}",
                    scenario.name
                ));
            }
            let row_runs_cycles = row_runs_sim
                .steps
                .last()
                .map(|step| step.cycle_end)
                .unwrap_or(0);
            Some((row_runs_words.len(), row_runs_sim.steps.len(), row_runs_cycles))
        } else {
            None
        };
        let row_split_metrics = if let Some(row_split_words) = &scenario.row_split_words {
            let row_split_sim = simulate_program(
                &row_split_program.program,
                row_split_program.simulator_config,
                row_split_words,
                options.max_steps,
            )
            .map_err(|error| format!("row-split {} failed: {error}", scenario.name))?;
            let row_split_trace = extract_gpio_observable_trace(&row_split_sim);
            if row_repeat_trace.low_words[..scenario.shift_word_count]
                != row_split_trace.low_words[..scenario.shift_word_count]
            {
                return Err(format!(
                    "row-split low GPIO waveform drifted for {}",
                    scenario.name
                ));
            }
            if row_repeat_trace.high_words[..scenario.shift_word_count]
                != row_split_trace.high_words[..scenario.shift_word_count]
            {
                return Err(format!(
                    "row-split high GPIO waveform drifted for {}",
                    scenario.name
                ));
            }
            let row_split_cycles = row_split_sim
                .steps
                .last()
                .map(|step| step.cycle_end)
                .unwrap_or(0);
            Some((row_split_words.len(), row_split_sim.steps.len(), row_split_cycles))
        } else {
            None
        };
        let row_window_metrics = if let Some(row_window_words) = &scenario.row_window_words {
            let row_window_sim = simulate_program(
                &row_window_program.program,
                row_window_program.simulator_config,
                row_window_words,
                options.max_steps,
            )
            .map_err(|error| format!("row-window {} failed: {error}", scenario.name))?;
            let row_window_trace = extract_gpio_observable_trace(&row_window_sim);
            if row_repeat_trace.low_words[..scenario.shift_word_count]
                != row_window_trace.low_words[..scenario.shift_word_count]
            {
                return Err(format!(
                    "row-window low GPIO waveform drifted for {}",
                    scenario.name
                ));
            }
            if row_repeat_trace.high_words[..scenario.shift_word_count]
                != row_window_trace.high_words[..scenario.shift_word_count]
            {
                return Err(format!(
                    "row-window high GPIO waveform drifted for {}",
                    scenario.name
                ));
            }
            let row_window_cycles = row_window_sim
                .steps
                .last()
                .map(|step| step.cycle_end)
                .unwrap_or(0);
            Some((row_window_words.len(), row_window_sim.steps.len(), row_window_cycles))
        } else {
            None
        };

        println!("scenario={}", scenario.name);
        println!(
            "  shift_words={} row_repeat_words={} row_compact_words={} savings={:.1}% row_counted_words={} savings={:.1}% row_hybrid_words={} savings={:.1}%",
            scenario.shift_word_count,
            scenario.row_repeat_words.len(),
            scenario.row_compact_words.len(),
            percent_savings(scenario.row_repeat_words.len(), scenario.row_compact_words.len()),
            scenario.row_counted_words.len(),
            percent_savings(scenario.row_repeat_words.len(), scenario.row_counted_words.len()),
            scenario.row_hybrid_words.len(),
            percent_savings(scenario.row_repeat_words.len(), scenario.row_hybrid_words.len()),
        );
        println!(
            "  row_repeat steps={} cycles={} compact steps={} cycles={} compact_tight steps={} cycles={} counted steps={} cycles={} hybrid steps={} cycles={}",
            row_repeat_sim.steps.len(),
            row_repeat_cycles,
            row_compact_sim.steps.len(),
            row_compact_cycles,
            row_compact_tight_sim.steps.len(),
            row_compact_tight_cycles,
            row_counted_sim.steps.len(),
            row_counted_cycles,
            row_hybrid_sim.steps.len(),
            row_hybrid_cycles,
        );
        if let Some((row_runs_word_count, row_runs_steps, row_runs_cycles)) = row_runs_metrics {
            println!(
                "  row_runs_words={} savings={:.1}% row_runs steps={} cycles={}",
                row_runs_word_count,
                percent_savings(scenario.row_repeat_words.len(), row_runs_word_count),
                row_runs_steps,
                row_runs_cycles
            );
        }
        if let Some((row_split_word_count, row_split_steps, row_split_cycles)) = row_split_metrics {
            println!(
                "  row_split_words={} savings={:.1}% row_split steps={} cycles={}",
                row_split_word_count,
                percent_savings(scenario.row_repeat_words.len(), row_split_word_count),
                row_split_steps,
                row_split_cycles
            );
        }
        if let Some((row_window_word_count, row_window_steps, row_window_cycles)) = row_window_metrics
        {
            println!(
                "  row_window_words={} savings={:.1}% row_window steps={} cycles={}",
                row_window_word_count,
                percent_savings(scenario.row_repeat_words.len(), row_window_word_count),
                row_window_steps,
                row_window_cycles
            );
        }
        println!();
    }

    Ok(())
}

#[derive(Clone, Debug)]
struct Options {
    panel_rows: u16,
    panel_cols: u16,
    chain_length: u16,
    parallel: u8,
    max_steps: usize,
    pattern: String,
}

#[derive(Clone, Debug)]
struct Scenario {
    name: &'static str,
    shift_word_count: usize,
    row_repeat_words: Vec<u32>,
    row_compact_words: Vec<u32>,
    row_counted_words: Vec<u32>,
    row_hybrid_words: Vec<u32>,
    row_runs_words: Option<Vec<u32>>,
    row_split_words: Option<Vec<u32>>,
    row_window_words: Option<Vec<u32>>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct ObservablePulseTrace {
    low_words: Vec<u32>,
    high_words: Vec<u32>,
}

fn parse_args(args: Vec<String>) -> Result<Options, String> {
    let mut options = Options {
        panel_rows: DEFAULT_PANEL_ROWS,
        panel_cols: DEFAULT_PANEL_COLS,
        chain_length: DEFAULT_CHAIN_LENGTH,
        parallel: DEFAULT_PARALLEL,
        max_steps: DEFAULT_MAX_STEPS,
        pattern: DEFAULT_PATTERN.to_string(),
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
            "--steps" => options.max_steps = parse_value(&next(&mut args, "--steps")?, "--steps")?,
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
    println!("Usage: cargo run --bin piomatter_row_pattern_cost -- [options]");
    println!("  --pattern <name>       all|dark-row|repeated-blue|alternating|quadrants|center-box");
    println!("  --steps <usize>        max simulated instructions before declaring failure");
}

fn parse_value<T: std::str::FromStr>(value: &str, flag: &str) -> Result<T, String>
where
    <T as std::str::FromStr>::Err: std::fmt::Display,
{
    value
        .parse::<T>()
        .map_err(|error| format!("Invalid value for {flag}: {error}"))
}

fn encode_row_engine_count(logical_count: u32, label: &str) -> Result<u32, String> {
    logical_count
        .checked_sub(1)
        .ok_or_else(|| format!("row-engine {label} count must be at least 1"))
}

fn encode_row_compact_literal_command(
    logical_count: u32,
    active_hold_count: u32,
) -> Result<u32, String> {
    let encoded_count = encode_row_engine_count(logical_count, "literal row count")?;
    if encoded_count > PIOMATTER_ROW_COMPACT_COMMAND_WIDTH_MASK {
        return Err("literal row count exceeds compact command width bits".to_string());
    }
    if active_hold_count > PIOMATTER_ROW_COMPACT_COMMAND_ACTIVE_HOLD_LIMIT {
        return Err("active hold count exceeds compact command inline bits".to_string());
    }
    Ok(
        PIOMATTER_ROW_COMPACT_COMMAND_LITERAL_BASE
            | (active_hold_count << PIOMATTER_ROW_COMPACT_COMMAND_ACTIVE_HOLD_SHIFT)
            | encoded_count,
    )
}

fn encode_row_compact_repeat_command(
    logical_count: u32,
    active_hold_count: u32,
) -> Result<u32, String> {
    let encoded_count = encode_row_engine_count(logical_count, "repeat row count")?;
    if encoded_count > PIOMATTER_ROW_COMPACT_COMMAND_WIDTH_MASK {
        return Err("repeat row count exceeds compact command width bits".to_string());
    }
    if active_hold_count > PIOMATTER_ROW_COMPACT_COMMAND_ACTIVE_HOLD_LIMIT {
        return Err("active hold count exceeds compact command inline bits".to_string());
    }
    Ok(
        PIOMATTER_ROW_COMPACT_COMMAND_REPEAT_BASE
            | (active_hold_count << PIOMATTER_ROW_COMPACT_COMMAND_ACTIVE_HOLD_SHIFT)
            | encoded_count,
    )
}

fn encode_row_counted_literal_command(logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_COUNTED_COMMAND_LITERAL_BASE
            | encode_row_engine_count(logical_count, "row-counted literal row count")?,
    )
}

fn encode_row_counted_repeat_command(logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_COUNTED_COMMAND_REPEAT_BASE
            | encode_row_engine_count(logical_count, "row-counted repeat row count")?,
    )
}

fn encode_row_hybrid_literal_command(
    logical_count: u32,
    active_hold_count: u32,
) -> Result<u32, String> {
    let encoded_count = encode_row_engine_count(logical_count, "hybrid literal row count")?;
    if encoded_count > PIOMATTER_ROW_HYBRID_COMMAND_WIDTH_MASK {
        return Err("hybrid literal row count exceeds inline width bits".to_string());
    }
    if active_hold_count > PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_LIMIT {
        return Err("hybrid active hold count exceeds inline bits".to_string());
    }
    Ok(
        PIOMATTER_ROW_HYBRID_COMMAND_LITERAL_BASE
            | (active_hold_count << PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_SHIFT)
            | encoded_count,
    )
}

fn encode_row_hybrid_repeat_command(
    logical_count: u32,
    active_hold_count: u32,
) -> Result<u32, String> {
    let encoded_count = encode_row_engine_count(logical_count, "hybrid repeat row count")?;
    if encoded_count > PIOMATTER_ROW_HYBRID_COMMAND_WIDTH_MASK {
        return Err("hybrid repeat row count exceeds inline width bits".to_string());
    }
    if active_hold_count > PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_LIMIT {
        return Err("hybrid active hold count exceeds inline bits".to_string());
    }
    Ok(
        PIOMATTER_ROW_HYBRID_COMMAND_REPEAT_BASE
            | (active_hold_count << PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_SHIFT)
            | encoded_count,
    )
}

fn encode_row_hybrid_split_command(
    first_logical_count: u32,
    active_hold_count: u32,
) -> Result<u32, String> {
    let encoded_count = encode_row_engine_count(first_logical_count, "hybrid first span count")?;
    if encoded_count > PIOMATTER_ROW_HYBRID_COMMAND_WIDTH_MASK {
        return Err("hybrid first span count exceeds inline width bits".to_string());
    }
    if active_hold_count > PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_LIMIT {
        return Err("hybrid active hold count exceeds inline bits".to_string());
    }
    Ok(
        PIOMATTER_ROW_HYBRID_COMMAND_SPLIT_BASE
            | (active_hold_count << PIOMATTER_ROW_HYBRID_COMMAND_ACTIVE_HOLD_SHIFT)
            | encoded_count,
    )
}

fn encode_row_runs_command(
    first_logical_count: u32,
    extra_run_count: u32,
    active_hold_count: u32,
) -> Result<u32, String> {
    let encoded_count = encode_row_engine_count(first_logical_count, "row-runs first row count")?;
    if encoded_count > PIOMATTER_ROW_RUNS_COMMAND_FIRST_WIDTH_MASK {
        return Err("row-runs first row count exceeds inline width bits".to_string());
    }
    if active_hold_count > PIOMATTER_ROW_RUNS_COMMAND_ACTIVE_HOLD_LIMIT {
        return Err("row-runs active hold count exceeds inline bits".to_string());
    }
    Ok(
        (extra_run_count << PIOMATTER_ROW_RUNS_COMMAND_EXTRA_RUNS_SHIFT)
            | (encoded_count << PIOMATTER_ROW_RUNS_COMMAND_FIRST_WIDTH_SHIFT)
            | active_hold_count,
    )
}

fn encode_row_window_literal_command(logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_WINDOW_COMMAND_LITERAL_BASE
            | encode_row_engine_count(logical_count, "row-window literal row count")?,
    )
}

fn encode_row_window_repeat_command(logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_WINDOW_COMMAND_REPEAT_BASE
            | encode_row_engine_count(logical_count, "row-window repeat row count")?,
    )
}

fn encode_row_window_split_command(first_logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_WINDOW_COMMAND_SPLIT_BASE
            | encode_row_engine_count(first_logical_count, "row-window first split span count")?,
    )
}

fn encode_row_window_window_command(first_logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_WINDOW_COMMAND_WINDOW_BASE
            | encode_row_engine_count(first_logical_count, "row-window first edge span count")?,
    )
}

fn encode_row_split_repeat_command(logical_count: u32, counted_trailer: bool) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_SPLIT_COMMAND_REPEAT_BASE
            | if counted_trailer {
                PIOMATTER_ROW_SPLIT_COMMAND_COUNTED_TRAILER
            } else {
                0
            }
            | encode_row_engine_count(logical_count, "row-split repeat row count")?,
    )
}

fn encode_row_split_two_span_command(
    first_logical_count: u32,
    counted_trailer: bool,
) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_SPLIT_COMMAND_SPLIT_BASE
            | if counted_trailer {
                PIOMATTER_ROW_SPLIT_COMMAND_COUNTED_TRAILER
            } else {
                0
            }
            | encode_row_engine_count(first_logical_count, "row-split first span count")?,
    )
}

fn dark_row_scenario() -> Scenario {
    let dark_word = 0;
    let row_repeat_words = vec![
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 63,
        dark_word,
        encode_row_engine_count(1, "active hold").expect("active hold should encode"),
        0,
        encode_row_engine_count(1, "inactive hold").expect("inactive hold should encode"),
        0,
        encode_row_engine_count(1, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(1, "next-address hold").expect("next-address hold should encode"),
        0,
    ];
    let row_compact_words = vec![
        encode_row_compact_repeat_command(64, 0).expect("repeat row count should encode"),
        dark_word,
        0,
        0,
        0,
    ];
    let row_hybrid_words = vec![
        encode_row_hybrid_repeat_command(64, 0).expect("repeat row count should encode"),
        dark_word,
        0,
        0,
        0,
    ];
    Scenario {
        name: "dark-row",
        shift_word_count: 64,
        row_repeat_words,
        row_compact_words,
        row_counted_words: vec![
            encode_row_counted_repeat_command(64).expect("repeat row count should encode"),
            dark_word,
            0,
            0,
            0,
            0,
        ],
        row_hybrid_words,
        row_runs_words: Some(vec![
            encode_row_runs_command(64, 0, 0).expect("row-runs command should encode"),
            dark_word,
            0,
            0,
            0,
        ]),
        row_split_words: Some(vec![
            encode_row_split_repeat_command(64, false).expect("row-split command should encode"),
            dark_word,
            0,
            0,
            0,
        ]),
        row_window_words: Some(vec![
            encode_row_window_repeat_command(64).expect("row-window command should encode"),
            dark_word,
            0,
            0,
            0,
        ]),
    }
}

fn repeated_blue_scenario() -> Scenario {
    let repeated_blue = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let repeated_active = 1_u32 << OE_GPIO;
    let repeated_inactive = 0;
    let row_repeat_words = vec![
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 63,
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        repeated_active,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        repeated_inactive,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        repeated_inactive,
    ];
    let row_compact_words = vec![
        encode_row_compact_repeat_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("repeat row count should encode"),
        repeated_blue,
        repeated_active,
        repeated_inactive,
        repeated_inactive,
    ];
    let row_hybrid_words = vec![
        encode_row_hybrid_repeat_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("repeat row count should encode"),
        repeated_blue,
        repeated_active,
        repeated_inactive,
        repeated_inactive,
    ];
    Scenario {
        name: "repeated-blue",
        shift_word_count: 64,
        row_repeat_words,
        row_compact_words,
        row_counted_words: vec![
            encode_row_counted_repeat_command(64).expect("repeat row count should encode"),
            repeated_blue,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            repeated_active,
            repeated_inactive,
            repeated_inactive,
        ],
        row_hybrid_words,
        row_runs_words: Some(vec![
            encode_row_runs_command(
                64,
                0,
                encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            )
            .expect("row-runs command should encode"),
            repeated_blue,
            repeated_active,
            repeated_inactive,
            repeated_inactive,
        ]),
        row_split_words: Some(vec![
            encode_row_split_repeat_command(64, true).expect("row-split command should encode"),
            repeated_blue,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            repeated_active,
            repeated_inactive,
            repeated_inactive,
        ]),
        row_window_words: Some(vec![
            encode_row_window_repeat_command(64).expect("row-window command should encode"),
            repeated_blue,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            repeated_active,
            repeated_inactive,
            repeated_inactive,
        ]),
    }
}

fn alternating_scenario() -> Scenario {
    let left_word = (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO);
    let right_word = (1_u32 << G1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let row_repeat_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
        .chain((0..64).map(|index| {
            if index % 2 == 0 {
                left_word
            } else {
                right_word
            }
        }))
        .chain([
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            1_u32 << OE_GPIO,
            encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
            0,
            encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
            encode_row_engine_count(2, "next-address hold")
                .expect("next-address hold should encode"),
            0,
        ])
        .collect::<Vec<_>>();
    let row_compact_words = std::iter::once(
        encode_row_compact_literal_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("literal row count should encode"),
    )
    .chain((0..64).map(|index| {
        if index % 2 == 0 {
            left_word
        } else {
            right_word
        }
    }))
    .chain([
        1_u32 << OE_GPIO,
        0,
        0,
    ])
    .collect::<Vec<_>>();
    let row_hybrid_words = std::iter::once(
        encode_row_hybrid_literal_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("literal row count should encode"),
    )
    .chain((0..64).map(|index| {
        if index % 2 == 0 {
            left_word
        } else {
            right_word
        }
    }))
    .chain([1_u32 << OE_GPIO, 0, 0])
    .collect::<Vec<_>>();
    Scenario {
        name: "alternating",
        shift_word_count: 64,
        row_repeat_words,
        row_compact_words,
        row_counted_words: std::iter::once(
            encode_row_counted_literal_command(64)
                .expect("literal row count should encode"),
        )
        .chain((0..64).map(|index| {
            if index % 2 == 0 {
                left_word
            } else {
                right_word
            }
        }))
        .chain([
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            1_u32 << OE_GPIO,
            0,
            0,
        ])
        .collect::<Vec<_>>(),
        row_hybrid_words,
        row_runs_words: None,
        row_split_words: None,
        row_window_words: Some(
            std::iter::once(
                encode_row_window_literal_command(64)
                    .expect("row-window literal command should encode"),
            )
            .chain((0..64).map(|index| {
                if index % 2 == 0 {
                    left_word
                } else {
                    right_word
                }
            }))
            .chain([
                encode_row_engine_count(3, "active hold").expect("active hold should encode"),
                1_u32 << OE_GPIO,
                0,
                0,
            ])
            .collect(),
        ),
    }
}

fn quadrant_scenario() -> Scenario {
    let left_word = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_word =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let row_repeat_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
        .chain(std::iter::repeat_n(left_word, 32))
        .chain(std::iter::repeat_n(right_word, 32))
        .chain([
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            1_u32 << OE_GPIO,
            encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
            0,
            encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
            encode_row_engine_count(2, "next-address hold")
                .expect("next-address hold should encode"),
            0,
        ])
        .collect::<Vec<_>>();
    let row_compact_words = std::iter::once(
        encode_row_compact_literal_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("literal row count should encode"),
    )
        .chain(std::iter::repeat_n(left_word, 32))
        .chain(std::iter::repeat_n(right_word, 32))
        .chain([
            1_u32 << OE_GPIO,
            0,
            0,
        ])
        .collect::<Vec<_>>();
    let row_hybrid_words = vec![
        encode_row_hybrid_split_command(
            32,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("split row count should encode"),
        left_word,
        31,
        right_word,
        1_u32 << OE_GPIO,
        0,
        0,
    ];
    Scenario {
        name: "quadrants",
        shift_word_count: 64,
        row_repeat_words,
        row_compact_words,
        row_counted_words: std::iter::once(
            encode_row_counted_literal_command(64)
                .expect("literal row count should encode"),
        )
        .chain(std::iter::repeat_n(left_word, 32))
        .chain(std::iter::repeat_n(right_word, 32))
        .chain([
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            1_u32 << OE_GPIO,
            0,
            0,
        ])
        .collect::<Vec<_>>(),
        row_hybrid_words,
        row_runs_words: Some(vec![
            encode_row_runs_command(
                32,
                1,
                encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            )
            .expect("row-runs command should encode"),
            left_word,
            31,
            right_word,
            1_u32 << OE_GPIO,
            0,
            0,
        ]),
        row_split_words: Some(vec![
            encode_row_split_two_span_command(32, true).expect("row-split command should encode"),
            left_word,
            31,
            right_word,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            1_u32 << OE_GPIO,
            0,
            0,
        ]),
        row_window_words: Some(
            vec![
                encode_row_window_split_command(32)
                    .expect("row-window split command should encode"),
                left_word,
                31,
                right_word,
                encode_row_engine_count(3, "active hold").expect("active hold should encode"),
                1_u32 << OE_GPIO,
                0,
                0,
            ],
        ),
    }
}

fn center_box_scenario() -> Scenario {
    let center_box_dark_word = 1_u32 << OE_GPIO;
    let center_box_white_word = (1_u32 << R1_GPIO)
        | (1_u32 << G1_GPIO)
        | (1_u32 << B1_GPIO)
        | (1_u32 << R2_GPIO)
        | (1_u32 << G2_GPIO)
        | (1_u32 << B2_GPIO)
        | (1_u32 << OE_GPIO);
    let row_repeat_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .chain(std::iter::repeat_n(center_box_white_word, 16))
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .chain([
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            1_u32 << OE_GPIO,
            encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
            0,
            encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
            encode_row_engine_count(2, "next-address hold")
                .expect("next-address hold should encode"),
            0,
        ])
        .collect::<Vec<_>>();
    let row_compact_words = std::iter::once(
        encode_row_compact_literal_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("literal row count should encode"),
    )
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .chain(std::iter::repeat_n(center_box_white_word, 16))
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .chain([
            1_u32 << OE_GPIO,
            0,
            0,
        ])
        .collect::<Vec<_>>();
    let row_hybrid_words = std::iter::once(
        encode_row_hybrid_literal_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("literal row count should encode"),
    )
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .chain(std::iter::repeat_n(center_box_white_word, 16))
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .chain([1_u32 << OE_GPIO, 0, 0])
        .collect::<Vec<_>>();
    Scenario {
        name: "center-box",
        shift_word_count: 64,
        row_repeat_words,
        row_compact_words,
        row_counted_words: std::iter::once(
            encode_row_counted_literal_command(64)
                .expect("literal row count should encode"),
        )
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .chain(std::iter::repeat_n(center_box_white_word, 16))
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .chain([
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            1_u32 << OE_GPIO,
            0,
            0,
        ])
        .collect::<Vec<_>>(),
        row_hybrid_words,
        row_runs_words: Some(vec![
            encode_row_runs_command(
                24,
                2,
                encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            )
            .expect("row-runs command should encode"),
            center_box_dark_word,
            15,
            center_box_white_word,
            23,
            center_box_dark_word,
            1_u32 << OE_GPIO,
            0,
            0,
        ]),
        row_split_words: None,
        row_window_words: Some(vec![
            encode_row_window_window_command(24).expect("row-window command should encode"),
            center_box_dark_word,
            encode_row_engine_count(16, "middle span").expect("middle span should encode"),
            center_box_white_word,
            encode_row_engine_count(24, "tail span").expect("tail span should encode"),
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            1_u32 << OE_GPIO,
            0,
            0,
        ]),
    }
}

fn extract_gpio_observable_trace(simulation: &heart_pio_sim::PioSimulation) -> ObservablePulseTrace {
    let mut low_words = Vec::new();
    let mut high_words = Vec::new();

    for (index, step) in simulation.steps.iter().enumerate() {
        let opcode_class = step.instruction >> 13;
        let is_out_pins = opcode_class == 3 && ((step.instruction >> 5) & 0x7) == 0;
        let mov_src = step.instruction & 0x7;
        let is_mov_pins = opcode_class == 5
            && ((step.instruction >> 5) & 0x7) == 0
            && ((step.instruction >> 3) & 0x3) == 0
            && (mov_src == 1 || mov_src == 6 || mov_src == 7);
        if !is_out_pins && !is_mov_pins {
            continue;
        }

        let visible_low = step.pins;
        low_words.push(visible_low);
        if let Some(next) = simulation.steps.get(index + 1) {
            let low_without_clock = visible_low & !(1_u32 << CLK_GPIO);
            let next_without_clock = next.pins & !(1_u32 << CLK_GPIO);
            if next_without_clock == low_without_clock
                && next.sideset_value != 0
                && gpio_is_high(next.pins, CLK_GPIO)
            {
                high_words.push(next.pins);
            }
        }
    }

    ObservablePulseTrace {
        low_words,
        high_words,
    }
}

fn percent_savings(baseline_words: usize, optimized_words: usize) -> f64 {
    if baseline_words == 0 {
        return 0.0;
    }
    ((baseline_words as f64 - optimized_words as f64) / baseline_words as f64) * 100.0
}
