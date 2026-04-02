#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use runtime::{
    pio_program_info_for_format, PackedScanFrame, Pi5PioProgramInfo, Pi5ScanConfig, Pi5ScanFormat,
    Pi5ScanGroupTrace, WiringProfile,
};
use std::collections::BTreeSet;
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
struct AuditOptions {
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
    let program_info = pio_program_info_for_format(&config, options.format);

    println!("PIO ownership audit");
    print_pin_ownership(&program_info);
    println!();
    println!("Concrete group trace");
    print_trace("expected", &expected, &config);
    print_trace("decoded", &decoded, &config);
    println!();
    print_control_word_decode("blank_word", expected.blank_word, &config);
    print_control_word_decode("active_word", expected.active_word, &config);
    if let Some(first_shift_word) = expected.shift_words.first().copied() {
        print_control_word_decode("shift_word[0]", first_shift_word, &config);
    }
    println!();
    println!("Program semantics");
    println!(
        "  kind={:?} wrap_target={} wrap={}",
        program_info.kind, program_info.wrap_target, program_info.wrap
    );
    for step in &program_info.instructions {
        let mut notes = Vec::new();
        if step.out_writes_window {
            notes.push("OUT window".to_string());
        }
        if step.set_writes_pins {
            notes.push("SET LAT".to_string());
        }
        if let Some(level) = step.sideset_clock {
            notes.push(if level {
                "CLK high".to_string()
            } else {
                "CLK low".to_string()
            });
        }
        if step.delay_cycles != 0 {
            notes.push(format!("delay={}", step.delay_cycles));
        }
        println!(
            "  {:02}: {} (0x{:04x}) [{}]",
            step.index,
            step.mnemonic,
            step.instruction,
            notes.join(", ")
        );
    }
    println!();
    println!("Checks");
    print_checks(&program_info, &config);
    Ok(())
}

fn print_pin_ownership(program_info: &Pi5PioProgramInfo) {
    let out_pins: BTreeSet<u32> = (u32::from(program_info.simulator_config.out_pin_base)
        ..(u32::from(program_info.simulator_config.out_pin_base)
            + u32::from(program_info.simulator_config.out_pin_count)))
        .collect();
    let set_pins = pin_set(
        program_info.simulator_config.set_pin_base,
        program_info.simulator_config.set_pin_count,
    );
    let sideset_pins = pin_set(
        program_info.simulator_config.sideset_pin_base,
        program_info.simulator_config.sideset_count,
    );
    let out_set_overlap: Vec<u32> = out_pins.intersection(&set_pins).copied().collect();
    let out_sideset_overlap: Vec<u32> = out_pins.intersection(&sideset_pins).copied().collect();
    let set_sideset_overlap: Vec<u32> = set_pins.intersection(&sideset_pins).copied().collect();

    println!(
        "  OUT pins:      {}..={}",
        program_info.simulator_config.out_pin_base,
        program_info.simulator_config.out_pin_base + program_info.simulator_config.out_pin_count
            - 1
    );
    println!("  SET pins:      {:?}", set_pins);
    println!("  side-set pins: {:?}", sideset_pins);
    println!("  OUT ∩ SET:     {:?}", out_set_overlap);
    println!("  OUT ∩ side-set:{:?}", out_sideset_overlap);
    println!("  SET ∩ side-set:{:?}", set_sideset_overlap);
}

fn print_control_word_decode(label: &str, word: u32, config: &Pi5ScanConfig) {
    let pinout = config.pinout();
    let rgb_gpios = pinout.rgb_gpios().map(u32::from);
    let addr_gpios = pinout.addr_gpios().map(u32::from);
    println!("{label}: 0x{word:08x}");
    println!("  RGB pins:  {}", format_named_pins(word, &rgb_gpios));
    println!("  ADDR pins: {}", format_named_pins(word, &addr_gpios));
    println!(
        "  control:   OE={} LAT(bit in OUT window)={} CLK(bit in OUT window)={}",
        bit_is_set(word, pinout.oe_gpio()),
        bit_is_set(word, pinout.lat_gpio()),
        bit_is_set(word, pinout.clock_gpio())
    );
}

fn print_checks(program_info: &Pi5PioProgramInfo, config: &Pi5ScanConfig) {
    let pinout = config.pinout();
    let out_pins: BTreeSet<u32> = (u32::from(program_info.simulator_config.out_pin_base)
        ..(u32::from(program_info.simulator_config.out_pin_base)
            + u32::from(program_info.simulator_config.out_pin_count)))
        .collect();
    let lat_overlap = out_pins.contains(&pinout.lat_gpio());
    let clk_overlap = out_pins.contains(&pinout.clock_gpio());
    println!(
        "  OUT window overlaps LAT ownership: {}",
        if lat_overlap { "YES" } else { "no" }
    );
    println!(
        "  OUT window overlaps CLK ownership: {}",
        if clk_overlap { "YES" } else { "no" }
    );
    println!(
        "  OE is owned by OUT window only: {}",
        if out_pins.contains(&pinout.oe_gpio()) {
            "yes"
        } else {
            "NO"
        }
    );
    println!("  Risk summary: if OUT/SET or OUT/side-set overlap semantics differ from our assumptions on RP1, the panel can stay fully blank even when the packed trace is correct.");
}

fn print_trace(label: &str, trace: &Pi5ScanGroupTrace, config: &Pi5ScanConfig) {
    let program_info = pio_program_info_for_format(config, config.format());
    println!(
        "{label}: blank=0x{:08x} active=0x{:08x} dwell={} shifts={} wrap={}->{}",
        trace.blank_word,
        trace.active_word,
        trace.dwell_ticks,
        trace.shift_words.len(),
        program_info.wrap_target,
        program_info.wrap
    );
}

fn format_named_pins(word: u32, gpios: &[u32]) -> String {
    gpios
        .iter()
        .map(|gpio| format!("{gpio}={}", if bit_is_set(word, *gpio) { 1 } else { 0 }))
        .collect::<Vec<_>>()
        .join(" ")
}

fn bit_is_set(word: u32, gpio: u32) -> bool {
    const OUT_BASE_GPIO: u32 = 5;
    const OUT_PIN_COUNT: u32 = 23;
    if gpio < OUT_BASE_GPIO || gpio >= OUT_BASE_GPIO + OUT_PIN_COUNT {
        return false;
    }
    let bit = gpio - OUT_BASE_GPIO;
    (word & (1_u32 << bit)) != 0
}

fn pin_set(base: u8, count: u8) -> BTreeSet<u32> {
    (u32::from(base)..(u32::from(base) + u32::from(count))).collect()
}

fn parse_args(arguments: Vec<String>) -> Result<AuditOptions, String> {
    let mut options = AuditOptions {
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
        let value = arguments
            .next()
            .ok_or_else(|| format!("Missing value for {argument}"))?;
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
                    _ => return Err(format!("Unsupported format '{value}'.")),
                }
            }
            _ => return Err(format!("Unknown argument '{argument}'.")),
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
