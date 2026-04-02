#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PioOutDest {
    Pins = 0,
    X = 1,
    Y = 2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PioSetDest {
    Pins = 0,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PioMovDest {
    Pins = 0,
    X = 1,
    Y = 2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PioMovSrc {
    Pins = 0,
    X = 1,
    Y = 2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PioSimulatorConfig {
    pub wrap_target: u8,
    pub wrap: u8,
    pub out_pin_base: u8,
    pub out_pin_count: u8,
    pub set_pin_base: u8,
    pub set_pin_count: u8,
    pub sideset_pin_base: u8,
    pub sideset_count: u8,
    pub sideset_total_bits: u8,
    pub sideset_optional: bool,
    pub out_shift_right: bool,
    pub auto_pull: bool,
    pub pull_threshold: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PioTraceStep {
    pub cycle_start: u64,
    pub cycle_end: u64,
    pub pc: u8,
    pub instruction: u16,
    pub delay_cycles: u8,
    pub sideset_value: u8,
    pub x: u32,
    pub y: u32,
    pub osr: u32,
    pub osr_bits_available: u8,
    pub pins: u32,
    pub tx_fifo_remaining: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PioSimulation {
    pub program: Vec<u16>,
    pub steps: Vec<PioTraceStep>,
    pub stalled_on_pull: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct DecodedSideSet {
    value: u8,
    pin_count: u8,
    delay_cycles: u8,
    enabled: bool,
}

const PIO_INSTR_BITS_JMP: u16 = 0x0000;
const PIO_INSTR_BITS_OUT: u16 = 0x6000;
const PIO_INSTR_BITS_PULL: u16 = 0x8080;
const PIO_INSTR_BITS_MOV: u16 = 0xa000;
const PIO_INSTR_BITS_SET: u16 = 0xe000;

pub fn simulate_program(
    program: &[u16],
    config: PioSimulatorConfig,
    fifo_words: &[u32],
    max_steps: usize,
) -> Result<PioSimulation, String> {
    let mut pins = 0_u32;
    let mut pc = 0_u8;
    let mut x = 0_u32;
    let mut y = 0_u32;
    let mut osr = 0_u32;
    let mut osr_bits_available = 0_u8;
    let mut tx_index = 0_usize;
    let mut cycle = 0_u64;
    let mut steps = Vec::new();

    for _ in 0..max_steps {
        let instruction = *program.get(pc as usize).ok_or_else(|| {
            format!(
                "PIO simulation PC {pc} ran past program length {}.",
                program.len()
            )
        })?;
        let decoded_sideset = decode_sideset(instruction, config);
        let mut next_pc = pc.wrapping_add(1);
        let opcode = instruction >> 13;

        match opcode {
            0 => {
                let condition = ((instruction >> 5) & 0x7) as u8;
                let address = (instruction & 0x1f) as u8;
                let should_jump = match condition {
                    0 => true,
                    1 => x == 0,
                    2 => {
                        let initial = x;
                        x = x.wrapping_sub(1);
                        initial != 0
                    }
                    4 => {
                        let initial = y;
                        y = y.wrapping_sub(1);
                        initial != 0
                    }
                    _ => {
                        return Err(format!(
                            "PIO simulation does not support JMP condition {condition} in opcode 0x{instruction:04x}."
                        ))
                    }
                };
                if should_jump {
                    next_pc = address;
                }
            }
            3 => {
                let dest = ((instruction >> 5) & 0x7) as u8;
                let count = decode_out_count(instruction);
                if config.auto_pull && should_autopull(config.pull_threshold, osr_bits_available) {
                    match pull_from_fifo(&mut osr, &mut osr_bits_available, fifo_words, &mut tx_index) {
                        Ok(()) => {}
                        Err(()) => {
                            return Ok(PioSimulation {
                                program: program.to_vec(),
                                steps,
                                stalled_on_pull: true,
                            });
                        }
                    }
                }
                let value = shift_out(
                    &mut osr,
                    &mut osr_bits_available,
                    count,
                    config.out_shift_right,
                );
                match dest {
                    out_dest if out_dest == PioOutDest::Pins as u8 => write_consecutive_pins(
                        &mut pins,
                        config.out_pin_base,
                        config.out_pin_count,
                        value,
                    ),
                    out_dest if out_dest == PioOutDest::X as u8 => x = value,
                    out_dest if out_dest == PioOutDest::Y as u8 => y = value,
                    _ => {
                        return Err(format!(
                            "PIO simulation does not support OUT destination {dest} in opcode 0x{instruction:04x}."
                        ))
                    }
                }
            }
            4 => {
                let is_pull = ((instruction >> 7) & 0x1) != 0;
                let if_empty = ((instruction >> 6) & 0x1) != 0;
                let block = ((instruction >> 5) & 0x1) != 0;
                if !is_pull {
                    return Err(format!(
                        "PIO simulation does not support PUSH/RX-FIFO opcodes (0x{instruction:04x})."
                    ));
                }
                if if_empty && osr_bits_available != 0 {
                    // The OSR still contains data, so an ifempty pull becomes a no-op.
                } else if tx_index >= fifo_words.len() {
                    if block {
                        return Ok(PioSimulation {
                            program: program.to_vec(),
                            steps,
                            stalled_on_pull: true,
                        });
                    }
                    osr = 0;
                    osr_bits_available = 32;
                } else {
                    let _ = pull_from_fifo(&mut osr, &mut osr_bits_available, fifo_words, &mut tx_index);
                }
            }
            5 => {
                let dest = ((instruction >> 5) & 0x7) as u8;
                let op = ((instruction >> 3) & 0x3) as u8;
                let src = (instruction & 0x7) as u8;
                if op != 0 {
                    return Err(format!(
                        "PIO simulation only supports plain MOV instructions, but saw opcode 0x{instruction:04x}."
                    ));
                }
                match (dest, src) {
                    (d, s) if d == PioMovDest::Y as u8 && s == PioMovSrc::Y as u8 => {}
                    (d, s) if d == PioMovDest::Pins as u8 && s == PioMovSrc::X as u8 => {
                        write_consecutive_pins(
                            &mut pins,
                            config.out_pin_base,
                            config.out_pin_count,
                            x,
                        );
                    }
                    _ => {
                        return Err(format!(
                            "PIO simulation does not support MOV dest={dest} src={src} in opcode 0x{instruction:04x}."
                        ));
                    }
                }
            }
            7 => {
                let dest = ((instruction >> 5) & 0x7) as u8;
                let value = (instruction & 0x1f) as u8;
                if dest != PioSetDest::Pins as u8 {
                    return Err(format!(
                        "PIO simulation does not support SET destination {dest} in opcode 0x{instruction:04x}."
                    ));
                }
                write_consecutive_pins(
                    &mut pins,
                    config.set_pin_base,
                    config.set_pin_count,
                    u32::from(value),
                );
            }
            _ => {
                return Err(format!(
                    "PIO simulation does not support opcode class {opcode} in instruction 0x{instruction:04x}."
                ))
            }
        }

        if decoded_sideset.enabled && config.sideset_count != 0 {
            write_consecutive_pins(
                &mut pins,
                config.sideset_pin_base,
                decoded_sideset.pin_count,
                u32::from(decoded_sideset.value),
            );
        }

        let cycle_end = cycle
            .checked_add(1 + u64::from(decoded_sideset.delay_cycles))
            .ok_or_else(|| "PIO simulation cycle counter overflowed.".to_string())?;
        steps.push(PioTraceStep {
            cycle_start: cycle,
            cycle_end,
            pc,
            instruction,
            delay_cycles: decoded_sideset.delay_cycles,
            sideset_value: decoded_sideset.value,
            x,
            y,
            osr,
            osr_bits_available,
            pins,
            tx_fifo_remaining: fifo_words.len().saturating_sub(tx_index),
        });
        cycle = cycle_end;

        if pc == config.wrap && next_pc == pc.wrapping_add(1) {
            next_pc = config.wrap_target;
        }
        pc = next_pc;
    }

    Err("PIO simulation exceeded the maximum instruction budget before stalling.".to_string())
}

pub fn gpio_is_high(pins: u32, gpio: u32) -> bool {
    (pins & (1_u32 << gpio)) != 0
}

pub fn pio_encode_jmp(address: u8) -> u16 {
    pio_encode_instr_and_args(PIO_INSTR_BITS_JMP, 0, address)
}

pub fn pio_encode_jmp_x_dec(address: u8) -> u16 {
    pio_encode_instr_and_args(PIO_INSTR_BITS_JMP, 2, address)
}

pub fn pio_encode_jmp_y_dec(address: u8) -> u16 {
    pio_encode_instr_and_args(PIO_INSTR_BITS_JMP, 4, address)
}

pub fn pio_encode_out(dest: u8, count: u8) -> u16 {
    pio_encode_instr_and_args(PIO_INSTR_BITS_OUT, dest, count & 0x1f)
}

pub fn pio_encode_pull(if_empty: bool, block: bool) -> u16 {
    PIO_INSTR_BITS_PULL | (u16::from(if_empty) << 6) | (u16::from(block) << 5)
}

pub fn pio_encode_set(dest: u8, value: u8) -> u16 {
    pio_encode_instr_and_args(PIO_INSTR_BITS_SET, dest, value & 0x1f)
}

pub fn pio_encode_nop() -> u16 {
    pio_encode_instr_and_args(PIO_INSTR_BITS_MOV, PioMovDest::Y as u8, PioMovSrc::Y as u8)
}

pub fn pio_encode_delay(cycles: u32) -> u16 {
    ((cycles & 0x1f) as u16) << 8
}

pub fn pio_encode_sideset_opt(sideset_bit_count: u8, value: u8) -> u16 {
    let delay_bits = 4_u8.saturating_sub(sideset_bit_count);
    (1_u16 << 12) | (u16::from(value) << (8 + delay_bits))
}

fn shift_out(osr: &mut u32, osr_bits_available: &mut u8, count: u8, shift_right: bool) -> u32 {
    let value = shift_out_value(osr, count, shift_right);
    *osr_bits_available = osr_bits_available.saturating_sub(count);
    value
}

fn shift_out_value(osr: &mut u32, count: u8, shift_right: bool) -> u32 {
    if count == 0 {
        return 0;
    }
    let mask = if count == 32 {
        u32::MAX
    } else {
        (1_u32 << count) - 1
    };
    if shift_right {
        let value = *osr & mask;
        *osr = if count == 32 { 0 } else { *osr >> count };
        value
    } else {
        let value = if count == 32 {
            *osr
        } else {
            (*osr >> (32 - count)) & mask
        };
        *osr = if count == 32 { 0 } else { *osr << count };
        value
    }
}

fn should_autopull(pull_threshold: u8, osr_bits_available: u8) -> bool {
    let threshold = pull_threshold.clamp(1, 32);
    osr_bits_available <= 32_u8.saturating_sub(threshold)
}

fn pull_from_fifo(
    osr: &mut u32,
    osr_bits_available: &mut u8,
    fifo_words: &[u32],
    tx_index: &mut usize,
) -> Result<(), ()> {
    let Some(&word) = fifo_words.get(*tx_index) else {
        return Err(());
    };
    *osr = word;
    *osr_bits_available = 32;
    *tx_index += 1;
    Ok(())
}

fn decode_out_count(instruction: u16) -> u8 {
    let encoded = (instruction & 0x1f) as u8;
    if encoded == 0 {
        32
    } else {
        encoded
    }
}

fn decode_sideset(instruction: u16, config: PioSimulatorConfig) -> DecodedSideSet {
    if config.sideset_count == 0 {
        return DecodedSideSet {
            value: 0,
            pin_count: 0,
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
        pin_count: active_sideset_count,
        delay_cycles,
        enabled,
    }
}

fn write_consecutive_pins(pins: &mut u32, base: u8, count: u8, value: u32) {
    for offset in 0..count {
        let raw_pin = u32::from(base + offset);
        let bit = 1_u32 << raw_pin;
        if ((value >> offset) & 1) != 0 {
            *pins |= bit;
        } else {
            *pins &= !bit;
        }
    }
}

fn pio_encode_instr_and_args(instruction_bits: u16, arg1: u8, arg2: u8) -> u16 {
    instruction_bits | (u16::from(arg1) << 5) | u16::from(arg2)
}
