#![allow(dead_code)]

use heart_pio_sim::{
    pio_encode_delay, simulate_program, PioSimulation, PioSimulatorConfig, PioTraceStep,
};

use super::pi5_pio_programs_generated::{
    PI5_PIO_RESIDENT_PARSER_AUTO_PULL, PI5_PIO_RESIDENT_PARSER_BASE_PROGRAM,
    PI5_PIO_RESIDENT_PARSER_DELAY_PATCH_INDICES, PI5_PIO_RESIDENT_PARSER_OUT_PIN_BASE,
    PI5_PIO_RESIDENT_PARSER_OUT_PIN_COUNT, PI5_PIO_RESIDENT_PARSER_OUT_SHIFT_RIGHT,
    PI5_PIO_RESIDENT_PARSER_PROGRAM_LENGTH, PI5_PIO_RESIDENT_PARSER_PULL_THRESHOLD,
    PI5_PIO_RESIDENT_PARSER_SIDESET_OPTIONAL, PI5_PIO_RESIDENT_PARSER_SIDESET_PIN_COUNT,
    PI5_PIO_RESIDENT_PARSER_SIDESET_TOTAL_BITS, PI5_PIO_RESIDENT_PARSER_WRAP,
    PI5_PIO_RESIDENT_PARSER_WRAP_TARGET,
    PI5_PIO_SIMPLE_HUB75_AUTO_PULL, PI5_PIO_SIMPLE_HUB75_BASE_PROGRAM,
    PI5_PIO_SIMPLE_HUB75_DELAY_PATCH_INDICES, PI5_PIO_SIMPLE_HUB75_OUT_PIN_BASE,
    PI5_PIO_SIMPLE_HUB75_OUT_PIN_COUNT, PI5_PIO_SIMPLE_HUB75_OUT_SHIFT_RIGHT,
    PI5_PIO_SIMPLE_HUB75_PROGRAM_LENGTH, PI5_PIO_SIMPLE_HUB75_PULL_THRESHOLD,
    PI5_PIO_SIMPLE_HUB75_SIDESET_OPTIONAL, PI5_PIO_SIMPLE_HUB75_SIDESET_PIN_COUNT,
    PI5_PIO_SIMPLE_HUB75_SIDESET_TOTAL_BITS, PI5_PIO_SIMPLE_HUB75_WRAP,
    PI5_PIO_SIMPLE_HUB75_WRAP_TARGET,
};
use super::pi5_scan::{
    build_simple_group_words_for_rgba, Pi5ScanConfig, Pi5ScanFormat, Pi5ScanTiming,
};

const PIO_DELAY_MASK: u16 = 0x0700;

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Pi5PioTimingEstimate {
    pub(crate) sys_clock_hz: f64,
    pub(crate) clock_divider: f64,
    pub(crate) pio_tick_seconds: f64,
    pub(crate) group_cycles_by_plane: Vec<u64>,
    pub(crate) row_pairs: usize,
    pub(crate) full_frame_cycles: u64,
    pub(crate) full_frame_seconds: f64,
    pub(crate) full_frame_hz: f64,
}

pub(crate) type Pi5PioSimulation = PioSimulation;
pub(crate) type Pi5PioTraceStep = PioTraceStep;
pub(crate) use heart_pio_sim::gpio_is_high;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum Pi5PioProgramKind {
    SimpleHub75,
    ResidentParser,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct Pi5PioInstructionSummary {
    pub(crate) index: u8,
    pub(crate) instruction: u16,
    pub(crate) mnemonic: String,
    pub(crate) delay_cycles: u8,
    pub(crate) sideset_clock: Option<bool>,
    pub(crate) out_writes_window: bool,
    pub(crate) set_writes_pins: bool,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub(crate) struct Pi5PioProgramInfo {
    pub(crate) kind: Pi5PioProgramKind,
    pub(crate) wrap_target: u8,
    pub(crate) wrap: u8,
    pub(crate) simulator_config: PioSimulatorConfig,
    pub(crate) program: Vec<u16>,
    pub(crate) instructions: Vec<Pi5PioInstructionSummary>,
}

fn with_delay_bits(opcode: u16, delay_ticks: u32) -> u16 {
    (opcode & !PIO_DELAY_MASK) | pio_encode_delay(delay_ticks.saturating_sub(1))
}

pub(crate) fn build_simple_hub75_program_opcodes(
    timing: Pi5ScanTiming,
) -> [u16; PI5_PIO_SIMPLE_HUB75_PROGRAM_LENGTH] {
    let mut program = PI5_PIO_SIMPLE_HUB75_BASE_PROGRAM;
    let _ = timing.post_addr_ticks;
    let _ = timing.latch_ticks;
    let _ = timing.post_latch_ticks;
    for &index in &PI5_PIO_SIMPLE_HUB75_DELAY_PATCH_INDICES {
        program[index] = with_delay_bits(program[index], timing.simple_clock_hold_ticks);
    }
    program
}

pub(crate) fn build_resident_parser_program_opcodes(
    timing: Pi5ScanTiming,
) -> [u16; PI5_PIO_RESIDENT_PARSER_PROGRAM_LENGTH] {
    let mut program = PI5_PIO_RESIDENT_PARSER_BASE_PROGRAM;
    let [post_addr_index, latch_index, post_latch_index] =
        PI5_PIO_RESIDENT_PARSER_DELAY_PATCH_INDICES;
    program[post_addr_index] = with_delay_bits(program[post_addr_index], timing.post_addr_ticks);
    program[latch_index] = with_delay_bits(program[latch_index], timing.latch_ticks);
    program[post_latch_index] =
        with_delay_bits(program[post_latch_index], timing.post_latch_ticks);
    program
}

fn scan_program_simulator_config(
    config: &Pi5ScanConfig,
    format: Pi5ScanFormat,
    wrap_target: u8,
    wrap: u8,
) -> PioSimulatorConfig {
    let pinout = config.pinout();
    let (
        out_pin_base,
        out_pin_count,
        out_shift_right,
        auto_pull,
        pull_threshold,
        sideset_count,
        sideset_total_bits,
        sideset_optional,
    ) = match format {
        Pi5ScanFormat::Simple => (
            PI5_PIO_SIMPLE_HUB75_OUT_PIN_BASE,
            PI5_PIO_SIMPLE_HUB75_OUT_PIN_COUNT,
            PI5_PIO_SIMPLE_HUB75_OUT_SHIFT_RIGHT,
            PI5_PIO_SIMPLE_HUB75_AUTO_PULL,
            PI5_PIO_SIMPLE_HUB75_PULL_THRESHOLD,
            PI5_PIO_SIMPLE_HUB75_SIDESET_PIN_COUNT,
            PI5_PIO_SIMPLE_HUB75_SIDESET_TOTAL_BITS,
            PI5_PIO_SIMPLE_HUB75_SIDESET_OPTIONAL,
        ),
        Pi5ScanFormat::Optimized => (
            PI5_PIO_RESIDENT_PARSER_OUT_PIN_BASE,
            PI5_PIO_RESIDENT_PARSER_OUT_PIN_COUNT,
            PI5_PIO_RESIDENT_PARSER_OUT_SHIFT_RIGHT,
            PI5_PIO_RESIDENT_PARSER_AUTO_PULL,
            PI5_PIO_RESIDENT_PARSER_PULL_THRESHOLD,
            PI5_PIO_RESIDENT_PARSER_SIDESET_PIN_COUNT,
            PI5_PIO_RESIDENT_PARSER_SIDESET_TOTAL_BITS,
            PI5_PIO_RESIDENT_PARSER_SIDESET_OPTIONAL,
        ),
    };
    PioSimulatorConfig {
        wrap_target,
        wrap,
        out_pin_base,
        out_pin_count,
        set_pin_base: 0,
        set_pin_count: 0,
        sideset_pin_base: pinout.clock_gpio() as u8,
        sideset_count,
        sideset_total_bits,
        sideset_optional,
        out_shift_right,
        auto_pull,
        pull_threshold,
    }
}

pub(crate) fn simulate_simple_hub75_group(
    config: &Pi5ScanConfig,
    words: &[u32],
) -> Result<Pi5PioSimulation, String> {
    let sim_config = scan_program_simulator_config(
        config,
        Pi5ScanFormat::Simple,
        PI5_PIO_SIMPLE_HUB75_WRAP_TARGET,
        PI5_PIO_SIMPLE_HUB75_WRAP,
    );
    let program = build_simple_hub75_program_opcodes(config.timing()).to_vec();
    simulate_program(&program, sim_config, words, 1_000_000)
}

pub(crate) fn pio_program_info_for_format(
    config: &Pi5ScanConfig,
    format: Pi5ScanFormat,
) -> Pi5PioProgramInfo {
    match format {
        Pi5ScanFormat::Simple => build_program_info(
            Pi5PioProgramKind::SimpleHub75,
            build_simple_hub75_program_opcodes(config.timing()).to_vec(),
            scan_program_simulator_config(
                config,
                Pi5ScanFormat::Simple,
                PI5_PIO_SIMPLE_HUB75_WRAP_TARGET,
                PI5_PIO_SIMPLE_HUB75_WRAP,
            ),
        ),
        Pi5ScanFormat::Optimized => build_program_info(
            Pi5PioProgramKind::ResidentParser,
            build_resident_parser_program_opcodes(config.timing()).to_vec(),
            scan_program_simulator_config(
                config,
                Pi5ScanFormat::Optimized,
                PI5_PIO_RESIDENT_PARSER_WRAP_TARGET,
                PI5_PIO_RESIDENT_PARSER_WRAP,
            ),
        ),
    }
}

fn build_program_info(
    kind: Pi5PioProgramKind,
    program: Vec<u16>,
    simulator_config: PioSimulatorConfig,
) -> Pi5PioProgramInfo {
    let instructions = summarize_program(&program, simulator_config);
    Pi5PioProgramInfo {
        kind,
        wrap_target: simulator_config.wrap_target,
        wrap: simulator_config.wrap,
        simulator_config,
        program,
        instructions,
    }
}

fn summarize_program(
    program: &[u16],
    simulator_config: PioSimulatorConfig,
) -> Vec<Pi5PioInstructionSummary> {
    program
        .iter()
        .enumerate()
        .map(|(index, instruction)| {
            let decoded_sideset = decode_sideset(*instruction, simulator_config);
            let class = instruction >> 13;
            let arg1 = ((*instruction >> 5) & 0x7) as u8;
            let arg2 = (*instruction & 0x1f) as u8;
            let mnemonic = match class {
                0 => format!("jmp {} {}", decode_jmp_condition(arg1), arg2),
                3 => format!(
                    "out {}, {}",
                    decode_out_dest(arg1),
                    decode_out_count(*instruction)
                ),
                4 => decode_pull_mnemonic(*instruction),
                5 => decode_mov_mnemonic(
                    arg1,
                    ((*instruction >> 3) & 0x3) as u8,
                    (*instruction & 0x7) as u8,
                ),
                7 => format!("set {}, {}", decode_set_dest(arg1), arg2),
                _ => format!("unknown class={} arg1={} arg2={}", class, arg1, arg2),
            };
            let out_writes_window = match class {
                3 => arg1 == 0,
                5 => arg1 == 0,
                _ => false,
            };
            let set_writes_pins = class == 7 && arg1 == 0;
            let sideset_clock = if decoded_sideset.enabled {
                Some(decoded_sideset.value != 0)
            } else {
                None
            };
            Pi5PioInstructionSummary {
                index: index as u8,
                instruction: *instruction,
                mnemonic,
                delay_cycles: decoded_sideset.delay_cycles,
                sideset_clock,
                out_writes_window,
                set_writes_pins,
            }
        })
        .collect()
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct DecodedSideSet {
    value: u8,
    delay_cycles: u8,
    enabled: bool,
}

fn decode_sideset(instruction: u16, config: PioSimulatorConfig) -> DecodedSideSet {
    if config.sideset_count == 0 {
        return DecodedSideSet {
            value: 0,
            delay_cycles: ((instruction >> 8) & 0x1f) as u8,
            enabled: false,
        };
    }
    let field = ((instruction >> 8) & 0x1f) as u8;
    let total_non_delay_bits = config.sideset_total_bits;
    let active_sideset_count = config
        .sideset_count
        .min(total_non_delay_bits.saturating_sub(u8::from(config.sideset_optional)));
    let delay_bits = 5_u8.saturating_sub(total_non_delay_bits);
    let delay_mask = if delay_bits == 0 {
        0
    } else {
        (1_u8 << delay_bits) - 1
    };
    let delay_cycles = field & delay_mask;
    let value_mask = if active_sideset_count == 0 {
        0
    } else {
        (1_u8 << active_sideset_count) - 1
    };
    let value = (field >> delay_bits) & value_mask;
    let enabled = if config.sideset_optional {
        ((field >> (delay_bits + active_sideset_count)) & 0x1) != 0
    } else {
        true
    };
    DecodedSideSet {
        value,
        delay_cycles,
        enabled,
    }
}

fn decode_out_count(instruction: u16) -> u8 {
    let encoded = (instruction & 0x1f) as u8;
    if encoded == 0 {
        32
    } else {
        encoded
    }
}

fn decode_jmp_condition(condition: u8) -> &'static str {
    match condition {
        0 => "always",
        1 => "!x",
        2 => "x--",
        3 => "!y",
        4 => "y--",
        5 => "x!=y",
        6 => "pin",
        7 => "!osre",
        _ => "unknown",
    }
}

fn decode_out_dest(dest: u8) -> &'static str {
    match dest {
        0 => "pins",
        1 => "x",
        2 => "y",
        3 => "null",
        4 => "pindirs",
        5 => "pc",
        6 => "isr",
        7 => "exec",
        _ => "unknown",
    }
}

fn decode_pull_mnemonic(instruction: u16) -> String {
    let if_empty = ((instruction >> 6) & 0x1) != 0;
    let block = ((instruction >> 5) & 0x1) != 0;
    match (if_empty, block) {
        (false, true) => "pull block".to_string(),
        (true, true) => "pull ifempty block".to_string(),
        (false, false) => "pull".to_string(),
        (true, false) => "pull ifempty".to_string(),
    }
}

fn decode_mov_mnemonic(dest: u8, op: u8, src: u8) -> String {
    if dest == 2 && op == 0 && src == 2 {
        return "nop".to_string();
    }
    let operator = match op {
        0 => "",
        1 => "!",
        2 => "::",
        3 => "reserved:",
        _ => "unknown:",
    };
    format!(
        "mov {}, {}{}",
        decode_mov_dest(dest),
        operator,
        decode_mov_src(src)
    )
}

fn decode_mov_dest(dest: u8) -> &'static str {
    match dest {
        0 => "pins",
        1 => "x",
        2 => "y",
        3 => "reserved",
        4 => "exec",
        5 => "pc",
        6 => "isr",
        7 => "osr",
        _ => "unknown",
    }
}

fn decode_mov_src(src: u8) -> &'static str {
    match src {
        0 => "pins",
        1 => "x",
        2 => "y",
        3 => "null",
        4 => "status",
        5 => "reserved",
        6 => "isr",
        7 => "osr",
        _ => "unknown",
    }
}

fn decode_set_dest(dest: u8) -> &'static str {
    match dest {
        0 => "pins",
        1 => "x",
        2 => "y",
        4 => "pindirs",
        _ => "unknown",
    }
}

pub(crate) fn estimate_simple_hub75_frame_timing(
    config: &Pi5ScanConfig,
    sys_clock_hz: f64,
) -> Result<Pi5PioTimingEstimate, String> {
    if config.format() != Pi5ScanFormat::Simple {
        return Err("simple timing estimates require Pi5ScanFormat::Simple.".to_string());
    }
    if !sys_clock_hz.is_finite() || sys_clock_hz <= 0.0 {
        return Err("sys_clock_hz must be a positive finite value.".to_string());
    }

    let width = config.width()? as usize;
    let height = config.height()? as usize;
    let row_pairs = config.row_pairs()?;
    let zero_frame = vec![0_u8; width * height * 4];
    let mut group_cycles_by_plane = Vec::with_capacity(usize::from(config.pwm_bits));

    for plane_index in 0..usize::from(config.pwm_bits) {
        let words = build_simple_group_words_for_rgba(config, &zero_frame, 0, plane_index)?;
        let simulated = simulate_simple_hub75_group(config, &words)?;
        let group_cycles = simulated
            .steps
            .last()
            .map(|step| step.cycle_end)
            .ok_or_else(|| "simple PIO simulation produced no trace steps.".to_string())?;
        group_cycles_by_plane.push(group_cycles);
    }

    let row_pair_cycle_sum = group_cycles_by_plane.iter().copied().sum::<u64>();
    let full_frame_cycles = row_pair_cycle_sum
        .checked_mul(row_pairs as u64)
        .ok_or_else(|| {
            "simple PIO timing estimate overflowed the full-frame cycle count.".to_string()
        })?;
    let pio_tick_seconds = f64::from(config.timing().clock_divider) / sys_clock_hz;
    let full_frame_seconds = (full_frame_cycles as f64) * pio_tick_seconds;
    let full_frame_hz = 1.0 / full_frame_seconds;

    Ok(Pi5PioTimingEstimate {
        sys_clock_hz,
        clock_divider: f64::from(config.timing().clock_divider),
        pio_tick_seconds,
        group_cycles_by_plane,
        row_pairs,
        full_frame_cycles,
        full_frame_seconds,
        full_frame_hz,
    })
}
