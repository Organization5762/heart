use std::sync::Arc;
use std::thread;
use std::time::Duration;

use super::config::{ColorOrder, WiringProfile};
use super::driver::{MatrixDriverCore, MatrixDriverError};
use super::pi5_pio_programs_generated::PI5_PIO_SIMPLE_HUB75_SIDESET_TOTAL_BITS;
use super::{
    build_simple_group_words_for_rgba, estimate_simple_hub75_frame_timing,
    gpio_is_high, piomatter_row_compact_engine_parity_program_info,
    piomatter_row_compact_tight_engine_parity_program_info,
    piomatter_row_counted_engine_parity_program_info,
    piomatter_row_hybrid_engine_parity_program_info,
    piomatter_row_runs_engine_parity_program_info,
    piomatter_row_repeat_engine_parity_program_info,
    piomatter_row_split_engine_parity_program_info,
    piomatter_row_window_engine_parity_program_info,
    piomatter_symbol_command_parity_program_info, pio_program_info_for_format,
    simulate_simple_hub75_group, FrameBufferPool, PackedScanFrame, Pi5ScanConfig, Pi5ScanFormat,
    Pi5ScanTiming,
};
use crate::runtime::pi5_scan::{
    decode_dwell_counter, decode_symbol_command, encode_raw_span_word,
    encode_repeat_span_word, encode_symbol_delay_command, encode_symbol_literal_command,
    encode_symbol_repeat_command, pack_control_prefixed_rgb_lane_symbols, pack_rgb_lane_symbols,
    SymbolCommandKind,
    SIMPLE_COMMAND_COUNT_MASK, SIMPLE_COMMAND_DATA_BIT,
};
use crate::runtime::queue::WorkerState;
use heart_pio_sim::simulate_program;

const R1_GPIO: u32 = 5;
const G1_GPIO: u32 = 13;
const B1_GPIO: u32 = 6;
const R2_GPIO: u32 = 12;
const G2_GPIO: u32 = 16;
const B2_GPIO: u32 = 23;
const A_GPIO: u32 = 22;
const B_GPIO: u32 = 26;
const C_GPIO: u32 = 27;
const D_GPIO: u32 = 20;
const E_GPIO: u32 = 24;
const CLK_GPIO: u32 = 17;
const LAT_GPIO: u32 = 21;
const OE_GPIO: u32 = 18;
const LEGACY_OE_GPIO: u32 = 4;
const PIOMATTER_COMMAND_DATA: u32 = 1_u32 << 31;
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
const SEMANTIC_R1_BIT: u32 = 1 << 0;
const SEMANTIC_G1_BIT: u32 = 1 << 1;
const SEMANTIC_B1_BIT: u32 = 1 << 2;
const SEMANTIC_R2_BIT: u32 = 1 << 3;
const SEMANTIC_G2_BIT: u32 = 1 << 4;
const SEMANTIC_B2_BIT: u32 = 1 << 5;
const SEMANTIC_A_BIT: u32 = 1 << 6;
const SEMANTIC_B_BIT: u32 = 1 << 7;
const SEMANTIC_C_BIT: u32 = 1 << 8;
const SEMANTIC_D_BIT: u32 = 1 << 9;
const SEMANTIC_E_BIT: u32 = 1 << 10;
const SEMANTIC_OE_BIT: u32 = 1 << 11;
const SEMANTIC_LAT_BIT: u32 = 1 << 12;
const SEMANTIC_CLK_GPIO: u32 = 13;
const USED_SIMPLE_GPIOS: [u32; 12] = [
    R1_GPIO, G1_GPIO, B1_GPIO, R2_GPIO, G2_GPIO, B2_GPIO, A_GPIO, B_GPIO, C_GPIO, D_GPIO, E_GPIO,
    OE_GPIO,
];
const PIN_WORD_BASE_GPIO: u32 = 0;
const SIMPLE_PIN_WORD_MASK: u32 = (1_u32 << 28) - 1;
const SIMPLE_BLANK_COMMAND_INDEX: usize = 0;
const SIMPLE_BLANK_WORD_INDEX: usize = 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum TestSimpleCommandKind {
    Delay,
    Data,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct ParsedSimpleCommand {
    kind: TestSimpleCommandKind,
    command_word: u32,
    logical_count: usize,
    payload_words: Vec<u32>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct ParsedSimpleGroup {
    blank_command: u32,
    blank_word: u32,
    shift_commands: Vec<ParsedSimpleCommand>,
    shift_words: Vec<u32>,
    latch_command: u32,
    latch_word: u32,
    post_latch_command: u32,
    post_latch_word: u32,
    active_command: u32,
    active_word: u32,
}

impl ParsedSimpleGroup {
    fn word_count(&self) -> usize {
        2 + self
            .shift_commands
            .iter()
            .map(|command| 1 + command.payload_words.len())
            .sum::<usize>()
            + 6
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct ObservablePulseTrace {
    low_words: Vec<u32>,
    high_words: Vec<u32>,
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
            && (mov_src == 1 || mov_src == 6 || mov_src == 7);
        if !(is_out_pins || is_mov_pins) {
            continue;
        }
        low_words.push(step.pins);

        if let Some(next) = simulation.steps.get(index + 1) {
            let base_without_clock = step.pins & !(1_u32 << CLK_GPIO);
            let next_without_clock = next.pins & !(1_u32 << CLK_GPIO);
            if next_without_clock == base_without_clock
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

fn extract_pin_transition_sequence(simulation: &heart_pio_sim::PioSimulation) -> Vec<u32> {
    let mut transitions = Vec::new();
    let mut previous = None;
    for step in &simulation.steps {
        if previous == Some(step.pins) {
            continue;
        }
        transitions.push(step.pins);
        previous = Some(step.pins);
    }
    transitions
}

fn semantic_symbol(bits: u32) -> u8 {
    (bits & 0x3f) as u8
}

fn semantic_control_word(bits: u32) -> u32 {
    bits & ((1_u32 << 13) - 1)
}

fn map_semantic_pins_to_actual_gpio(pins: u32) -> u32 {
    let mut actual = 0_u32;
    for (semantic_bit, gpio) in [
        (SEMANTIC_R1_BIT, R1_GPIO),
        (SEMANTIC_G1_BIT, G1_GPIO),
        (SEMANTIC_B1_BIT, B1_GPIO),
        (SEMANTIC_R2_BIT, R2_GPIO),
        (SEMANTIC_G2_BIT, G2_GPIO),
        (SEMANTIC_B2_BIT, B2_GPIO),
        (SEMANTIC_A_BIT, A_GPIO),
        (SEMANTIC_B_BIT, B_GPIO),
        (SEMANTIC_C_BIT, C_GPIO),
        (SEMANTIC_D_BIT, D_GPIO),
        (SEMANTIC_E_BIT, E_GPIO),
        (SEMANTIC_OE_BIT, OE_GPIO),
        (SEMANTIC_LAT_BIT, LAT_GPIO),
    ] {
        if (pins & semantic_bit) != 0 {
            actual |= 1_u32 << gpio;
        }
    }
    if gpio_is_high(pins, SEMANTIC_CLK_GPIO) {
        actual |= 1_u32 << CLK_GPIO;
    }
    actual
}

fn extract_mapped_gpio_observable_trace(
    simulation: &heart_pio_sim::PioSimulation,
) -> ObservablePulseTrace {
    let trace = extract_gpio_observable_trace(simulation);
    ObservablePulseTrace {
        low_words: trace
            .low_words
            .into_iter()
            .map(map_semantic_pins_to_actual_gpio)
            .collect(),
        high_words: trace
            .high_words
            .into_iter()
            .map(map_semantic_pins_to_actual_gpio)
            .collect(),
    }
}

fn extract_mapped_out_pins_count_observable_trace(
    simulation: &heart_pio_sim::PioSimulation,
    out_count: u8,
) -> ObservablePulseTrace {
    let mut low_words = Vec::new();
    let mut high_words = Vec::new();

    for (index, step) in simulation.steps.iter().enumerate() {
        let opcode_class = step.instruction >> 13;
        let is_out_pins = opcode_class == 3
            && ((step.instruction >> 5) & 0x7) == 0
            && ((step.instruction & 0x1f) as u8 == out_count
                || (out_count == 32 && (step.instruction & 0x1f) == 0));
        if !is_out_pins {
            continue;
        }
        let mapped_low = map_semantic_pins_to_actual_gpio(step.pins);
        low_words.push(mapped_low);

        if let Some(next) = simulation.steps.get(index + 1) {
            let mapped_next = map_semantic_pins_to_actual_gpio(next.pins);
            let base_without_clock = mapped_low & !(1_u32 << CLK_GPIO);
            let next_without_clock = mapped_next & !(1_u32 << CLK_GPIO);
            if next_without_clock == base_without_clock
                && next.sideset_value != 0
                && gpio_is_high(mapped_next, CLK_GPIO)
            {
                high_words.push(mapped_next);
            }
        }
    }

    ObservablePulseTrace {
        low_words,
        high_words,
    }
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
            | encode_row_engine_count(logical_count, "counted literal row count")?,
    )
}

fn encode_row_counted_repeat_command(logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_COUNTED_COMMAND_REPEAT_BASE
            | encode_row_engine_count(logical_count, "counted repeat row count")?,
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
            | encode_row_engine_count(logical_count, "split repeat row count")?,
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
            | encode_row_engine_count(first_logical_count, "split first span count")?,
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
    let encoded_count = encode_row_engine_count(first_logical_count, "hybrid split first span count")?;
    if encoded_count > PIOMATTER_ROW_HYBRID_COMMAND_WIDTH_MASK {
        return Err("hybrid split first span count exceeds inline width bits".to_string());
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

fn split_row_if_two_runs_for_test(row_words: &[u32]) -> Option<(usize, u32, usize, u32)> {
    if row_words.is_empty() {
        return None;
    }

    let first_word = row_words[0];
    let mut split_index = 0_usize;
    while split_index < row_words.len() && row_words[split_index] == first_word {
        split_index += 1;
    }

    if split_index == row_words.len() {
        return Some((row_words.len(), first_word, 0, first_word));
    }

    let second_word = row_words[split_index];
    if row_words[split_index..]
        .iter()
        .any(|word| *word != second_word)
    {
        return None;
    }

    Some((
        split_index,
        first_word,
        row_words.len() - split_index,
        second_word,
    ))
}

fn split_row_if_window_for_test(row_words: &[u32]) -> Option<(usize, u32, usize, u32, usize)> {
    if row_words.is_empty() {
        return None;
    }

    let edge_word = row_words[0];
    let mut first_count = 0_usize;
    while first_count < row_words.len() && row_words[first_count] == edge_word {
        first_count += 1;
    }

    if first_count == row_words.len() {
        return Some((row_words.len(), edge_word, 0, edge_word, 0));
    }

    let mut tail_start = row_words.len();
    while tail_start > first_count && row_words[tail_start - 1] == edge_word {
        tail_start -= 1;
    }
    let tail_count = row_words.len() - tail_start;
    if tail_count == 0 {
        return None;
    }

    let middle_word = row_words[first_count];
    if row_words[first_count..tail_start]
        .iter()
        .any(|word| *word != middle_word)
    {
        return None;
    }

    Some((
        first_count,
        edge_word,
        tail_start - first_count,
        middle_word,
        tail_count,
    ))
}

fn split_row_into_runs_for_test(row_words: &[u32], max_runs: usize) -> Option<Vec<(usize, u32)>> {
    if row_words.is_empty() {
        return None;
    }

    let mut runs = Vec::with_capacity(max_runs);
    let mut current_word = row_words[0];
    let mut current_count = 0_usize;
    for word in row_words {
        if *word == current_word {
            current_count += 1;
            continue;
        }
        runs.push((current_count, current_word));
        if runs.len() > max_runs {
            return None;
        }
        current_word = *word;
        current_count = 1;
    }
    runs.push((current_count, current_word));
    if runs.len() > max_runs {
        return None;
    }
    Some(runs)
}

fn extend_row_repeat_row_words(
    destination: &mut Vec<u32>,
    row_words: &[u32],
    active_hold_count: u32,
    active_hold_word: u32,
    inactive_hold_word: u32,
    next_addr_word: u32,
) {
    if row_words.iter().all(|word| *word == row_words[0]) {
        destination.push(
            PIOMATTER_ROW_REPEAT_COMMAND_REPEAT
                | encode_row_engine_count(row_words.len() as u32, "row-repeat count")
                    .expect("row-repeat count should encode"),
        );
        destination.push(row_words[0]);
    } else {
        destination.push(
            PIOMATTER_ROW_REPEAT_COMMAND_LITERAL
                | encode_row_engine_count(row_words.len() as u32, "row-repeat count")
                    .expect("row-repeat count should encode"),
        );
        destination.extend_from_slice(row_words);
    }
    destination.push(active_hold_count);
    destination.push(active_hold_word);
    destination.push(encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"));
    destination.push(inactive_hold_word);
    destination.push(encode_row_engine_count(4, "latch hold").expect("latch hold should encode"));
    destination.push(encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"));
    destination.push(next_addr_word);
}

fn extend_row_hybrid_row_words(
    destination: &mut Vec<u32>,
    row_words: &[u32],
    active_hold_count: u32,
    active_hold_word: u32,
    inactive_hold_word: u32,
    next_addr_word: u32,
) {
    if row_words.iter().all(|word| *word == row_words[0]) {
        destination.push(
            encode_row_hybrid_repeat_command(row_words.len() as u32, active_hold_count)
                .expect("hybrid repeat row should encode"),
        );
        destination.push(row_words[0]);
    } else if let Some((first_count, first_word, second_count, second_word)) =
        split_row_if_two_runs_for_test(row_words)
    {
        if second_count == 0 {
            destination.push(
                encode_row_hybrid_repeat_command(row_words.len() as u32, active_hold_count)
                    .expect("hybrid repeat row should encode"),
            );
            destination.push(first_word);
        } else {
            destination.push(
                encode_row_hybrid_split_command(first_count as u32, active_hold_count)
                    .expect("hybrid split row should encode"),
            );
            destination.push(first_word);
            destination.push(
                encode_row_engine_count(second_count as u32, "hybrid second span count")
                    .expect("hybrid second span count should encode"),
            );
            destination.push(second_word);
        }
    } else {
        destination.push(
            encode_row_hybrid_literal_command(row_words.len() as u32, active_hold_count)
                .expect("hybrid literal row should encode"),
        );
        destination.extend_from_slice(row_words);
    }

    destination.push(active_hold_word);
    destination.push(inactive_hold_word);
    destination.push(next_addr_word);
}

fn extend_row_split_row_words(
    destination: &mut Vec<u32>,
    row_words: &[u32],
    active_hold_count: u32,
    active_hold_word: u32,
    inactive_hold_word: u32,
    next_addr_word: u32,
) {
    if let Some((first_count, first_word, second_count, second_word)) =
        split_row_if_two_runs_for_test(row_words)
    {
        let counted_trailer = active_hold_count != 0;
        if second_count == 0 {
            destination.push(
                encode_row_split_repeat_command(first_count as u32, counted_trailer)
                    .expect("split repeat row should encode"),
            );
            destination.push(first_word);
        } else {
            destination.push(
                encode_row_split_two_span_command(first_count as u32, counted_trailer)
                    .expect("split two-span row should encode"),
            );
            destination.push(first_word);
            destination.push(
                encode_row_engine_count(second_count as u32, "split second span count")
                    .expect("split second span count should encode"),
            );
            destination.push(second_word);
        }
        if counted_trailer {
            destination.push(active_hold_count);
        }
        destination.push(active_hold_word);
        destination.push(inactive_hold_word);
        destination.push(next_addr_word);
        return;
    }

    panic!("row-split only supports one-run or two-run rows in these parity tests");
}

fn extend_row_runs_row_words(
    destination: &mut Vec<u32>,
    row_words: &[u32],
    active_hold_count: u32,
    active_hold_word: u32,
    inactive_hold_word: u32,
    next_addr_word: u32,
) {
    let runs = split_row_into_runs_for_test(row_words, 4).expect("row-runs should support up to four runs");
    destination.push(
        encode_row_runs_command(
            runs[0].0 as u32,
            (runs.len() - 1) as u32,
            active_hold_count,
        )
        .expect("row-runs command should encode"),
    );
    destination.push(runs[0].1);
    for (count, word) in runs.iter().skip(1) {
        destination.push(
            encode_row_engine_count(*count as u32, "row-runs span count")
                .expect("row-runs span count should encode"),
        );
        destination.push(*word);
    }
    destination.push(active_hold_word);
    destination.push(inactive_hold_word);
    destination.push(next_addr_word);
}

fn encode_row_runs_command(
    first_logical_count: u32,
    extra_run_count: u32,
    active_hold_count: u32,
) -> Result<u32, String> {
    let encoded_count = encode_row_engine_count(first_logical_count, "runs first span count")?;
    if encoded_count > PIOMATTER_ROW_RUNS_COMMAND_FIRST_WIDTH_MASK {
        return Err("runs first span count exceeds inline width bits".to_string());
    }
    if extra_run_count > 3 {
        return Err("runs command supports at most four runs".to_string());
    }
    if active_hold_count > PIOMATTER_ROW_RUNS_COMMAND_ACTIVE_HOLD_LIMIT {
        return Err("runs active hold count exceeds inline bits".to_string());
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
            | encode_row_engine_count(logical_count, "window literal row count")?,
    )
}

fn encode_row_window_repeat_command(logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_WINDOW_COMMAND_REPEAT_BASE
            | encode_row_engine_count(logical_count, "window repeat row count")?,
    )
}

fn encode_row_window_split_command(first_logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_WINDOW_COMMAND_SPLIT_BASE
            | encode_row_engine_count(first_logical_count, "window first split span count")?,
    )
}

fn encode_row_window_window_command(first_logical_count: u32) -> Result<u32, String> {
    Ok(
        PIOMATTER_ROW_WINDOW_COMMAND_WINDOW_BASE
            | encode_row_engine_count(first_logical_count, "window first edge span count")?,
    )
}

fn extend_row_window_row_words(
    destination: &mut Vec<u32>,
    row_words: &[u32],
    active_hold_count: u32,
    active_hold_word: u32,
    inactive_hold_word: u32,
    next_addr_word: u32,
) {
    if row_words.iter().all(|word| *word == row_words[0]) {
        destination.push(
            encode_row_window_repeat_command(row_words.len() as u32)
                .expect("window repeat row should encode"),
        );
        destination.push(row_words[0]);
    } else if let Some((first_count, first_word, second_count, second_word)) =
        split_row_if_two_runs_for_test(row_words)
    {
        destination.push(
            encode_row_window_split_command(first_count as u32)
                .expect("window first split span should encode"),
        );
        destination.push(first_word);
        destination.push(
            encode_row_engine_count(second_count as u32, "window second span count")
                .expect("window second span count should encode"),
        );
        destination.push(second_word);
    } else if let Some((first_count, edge_word, middle_count, middle_word, tail_count)) =
        split_row_if_window_for_test(row_words)
    {
        destination.push(
            encode_row_window_window_command(first_count as u32)
                .expect("window first edge span should encode"),
        );
        destination.push(edge_word);
        destination.push(
            encode_row_engine_count(middle_count as u32, "window middle span count")
                .expect("window middle span count should encode"),
        );
        destination.push(middle_word);
        destination.push(
            encode_row_engine_count(tail_count as u32, "window tail span count")
                .expect("window tail span count should encode"),
        );
    } else {
        destination.push(
            encode_row_window_literal_command(row_words.len() as u32)
                .expect("window literal row should encode"),
        );
        destination.extend_from_slice(row_words);
    }

    destination.push(active_hold_count);
    destination.push(active_hold_word);
    destination.push(inactive_hold_word);
    destination.push(next_addr_word);
}

fn decode_test_simple_command(command_word: u32) -> (TestSimpleCommandKind, usize) {
    let logical_count = ((command_word & SIMPLE_COMMAND_COUNT_MASK) as usize) + 1;
    let kind = if (command_word & SIMPLE_COMMAND_DATA_BIT) != 0 {
        TestSimpleCommandKind::Data
    } else {
        TestSimpleCommandKind::Delay
    };
    (kind, logical_count)
}

fn parse_simple_group(words: &[u32], width: usize) -> ParsedSimpleGroup {
    let blank_command = words[SIMPLE_BLANK_COMMAND_INDEX];
    let blank_word = words[SIMPLE_BLANK_WORD_INDEX];
    let mut shift_commands = Vec::new();
    let mut shift_words = Vec::with_capacity(width);
    let mut index = 2_usize;

    while shift_words.len() < width {
        let command_word = words[index];
        index += 1;
        let (kind, logical_count) = decode_test_simple_command(command_word);
        match kind {
            TestSimpleCommandKind::Data => {
                let payload_words = words[index..index + logical_count].to_vec();
                shift_words.extend_from_slice(&payload_words);
                shift_commands.push(ParsedSimpleCommand {
                    kind,
                    command_word,
                    logical_count,
                    payload_words,
                });
                index += logical_count;
            }
            TestSimpleCommandKind::Delay => {
                panic!("unexpected delay command in simple shift section");
            }
        }
    }

    assert_eq!(
        shift_words.len(),
        width,
        "parsed simple group should reconstruct the exact requested row width"
    );
    let latch_command = words[index];
    let latch_word = words[index + 1];
    let post_latch_command = words[index + 2];
    let post_latch_word = words[index + 3];
    let active_command = words[index + 4];
    let active_word = words[index + 5];

    ParsedSimpleGroup {
        blank_command,
        blank_word,
        shift_commands,
        shift_words,
        latch_command,
        latch_word,
        post_latch_command,
        post_latch_word,
        active_command,
        active_word,
    }
}

fn simple_command_kind_steps(
    simulated: &super::pi5_pio_sim::Pi5PioSimulation,
) -> Vec<&super::pi5_pio_sim::Pi5PioTraceStep> {
    simulated.steps.iter().filter(|step| step.pc == 1).collect()
}

fn simple_command_count_steps(
    simulated: &super::pi5_pio_sim::Pi5PioSimulation,
) -> Vec<&super::pi5_pio_sim::Pi5PioTraceStep> {
    simulated.steps.iter().filter(|step| step.pc == 2).collect()
}

fn simple_delay_output_steps(
    simulated: &super::pi5_pio_sim::Pi5PioSimulation,
) -> Vec<&super::pi5_pio_sim::Pi5PioTraceStep> {
    simulated.steps.iter().filter(|step| step.pc == 5).collect()
}

fn simple_shift_low_steps(
    simulated: &super::pi5_pio_sim::Pi5PioSimulation,
) -> Vec<&super::pi5_pio_sim::Pi5PioTraceStep> {
    simulated.steps.iter().filter(|step| step.pc == 3).collect()
}

fn simple_shift_high_steps(
    simulated: &super::pi5_pio_sim::Pi5PioSimulation,
) -> Vec<&super::pi5_pio_sim::Pi5PioTraceStep> {
    simulated.steps.iter().filter(|step| step.pc == 4).collect()
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct SimulatedColumn {
    top_rgb: [bool; 3],
    bottom_rgb: [bool; 3],
}

#[derive(Clone, Debug, Eq, PartialEq)]
struct SimulatedGroupOutput {
    row_pair: usize,
    columns: Vec<SimulatedColumn>,
    oe_active_during_dwell: bool,
}

fn frame_bytes(width: u32, height: u32, seed: u8) -> Vec<u8> {
    let byte_count = (width as usize) * (height as usize) * 4;
    (0..byte_count)
        .map(|index| seed.wrapping_add(index as u8))
        .collect()
}

#[test]
fn frame_buffer_pool_reuses_recycled_frames() {
    let mut pool = FrameBufferPool::new(32, 1);

    let frame = pool.acquire();
    assert_eq!(pool.available(), 0);

    pool.recycle(frame);
    assert_eq!(pool.available(), 1);

    let reused = pool.acquire();
    assert_eq!(reused.len(), 32);
    assert_eq!(pool.available(), 0);
}

#[test]
fn frame_buffer_write_rgba_leaves_rgb_frames_unchanged() {
    let input = vec![1, 2, 3, 4, 5, 6, 7, 8];
    let mut frame = FrameBufferPool::new(input.len(), 1).acquire();

    frame.write_rgba(&input, ColorOrder::Rgb);

    assert_eq!(frame.as_slice(), input.as_slice());
}

#[test]
fn frame_buffer_write_rgba_swaps_green_and_blue_for_gbr() {
    let input = vec![10, 20, 30, 255, 40, 50, 60, 128];
    let mut frame = FrameBufferPool::new(input.len(), 1).acquire();

    frame.write_rgba(&input, ColorOrder::Gbr);

    assert_eq!(frame.as_slice(), &[10, 30, 20, 255, 40, 60, 50, 128]);
}

#[test]
fn worker_state_drops_oldest_when_queue_is_full() {
    let mut state = WorkerState::new(4);

    for seed in [1_u8, 2_u8, 3_u8] {
        let mut frame = state.acquire_frame();
        frame.write_rgba(&[seed, seed, seed, 255], ColorOrder::Rgb);
        state.submit_frame(frame);
    }

    assert_eq!(state.pending_len(), 2);
    assert_eq!(state.dropped_frames(), 1);
    assert_eq!(state.available_buffers(), 1);
}

#[test]
fn matrix_driver_submit_rgba_records_queue_pressure_stats() {
    let driver =
        MatrixDriverCore::new(WiringProfile::AdafruitHatPwm, 16, 32, 1, 1, ColorOrder::Rgb)
            .expect("simulated matrix driver should initialize");
    let width = driver.width();
    let height = driver.height();

    for seed in 0..6 {
        driver
            .submit_rgba(frame_bytes(width, height, seed), width, height)
            .expect("frame submission should succeed");
    }

    let stats = driver.stats().expect("stats should be readable");

    assert!(stats.dropped_frames >= 1);
    driver.close().expect("driver should close cleanly");
}

#[test]
fn matrix_driver_submit_rgba_rejects_wrong_frame_size() {
    let driver =
        MatrixDriverCore::new(WiringProfile::AdafruitHatPwm, 16, 32, 1, 1, ColorOrder::Rgb)
            .expect("simulated matrix driver should initialize");

    let error = driver
        .submit_rgba(vec![0; 8], 32, 16)
        .expect_err("short frame should be rejected");

    match error {
        MatrixDriverError::Validation(message) => {
            assert!(message.contains("expected 2048 bytes"));
        }
        MatrixDriverError::Runtime(message) => {
            panic!("expected validation error, received runtime error: {message}");
        }
    }

    driver.close().expect("driver should close cleanly");
}

#[test]
fn matrix_driver_worker_updates_rendered_frame_stats() {
    let driver =
        MatrixDriverCore::new(WiringProfile::AdafruitHatPwm, 16, 32, 1, 1, ColorOrder::Rgb)
            .expect("simulated matrix driver should initialize");
    let width = driver.width();
    let height = driver.height();

    driver
        .submit_rgba(frame_bytes(width, height, 1), width, height)
        .expect("frame submission should succeed");
    thread::sleep(Duration::from_millis(40));

    let stats = driver.stats().expect("stats should be readable");

    assert!(stats.rendered_frames >= 1);
    driver.close().expect("driver should close cleanly");
}

#[test]
fn matrix_driver_accepts_concurrent_submissions() {
    let driver = Arc::new(
        MatrixDriverCore::new(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1, ColorOrder::Rgb)
            .expect("simulated matrix driver should initialize"),
    );
    let width = driver.width();
    let height = driver.height();

    thread::scope(|scope| {
        for seed in 0..4 {
            let driver = Arc::clone(&driver);
            scope.spawn(move || {
                for offset in 0..8 {
                    let frame = frame_bytes(width, height, seed * 16 + offset);
                    driver
                        .submit_rgba(frame, width, height)
                        .expect("concurrent submission should succeed");
                }
            });
        }
    });
    thread::sleep(Duration::from_millis(40));

    let stats = driver.stats().expect("stats should be readable");

    assert!(stats.rendered_frames >= 1);
    driver.close().expect("driver should close cleanly");
}

#[test]
fn pi5_scan_pack_rgba_produces_expected_word_count_for_single_panel() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Optimized))
        .expect("single-panel Pi 5 scan config should be valid");
    let frame = vec![255_u8; (config.width().unwrap() * config.height().unwrap() * 4) as usize];

    let (packed, stats) =
        PackedScanFrame::pack_rgba(&config, &frame).expect("scan packing should succeed");

    assert_eq!(stats.compressed_blank_groups, 32 * 3);
    assert_eq!(stats.merged_identical_groups, 32 * 7);
    assert_eq!(packed.word_count(), 32 * 5);
    assert_eq!(stats.word_count, packed.word_count());
}

#[test]
fn pi5_scan_pack_rgba_emits_compact_group_headers_and_control_words() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Optimized))
        .expect("single-panel Pi 5 scan config should be valid");
    let frame = vec![0_u8; (config.width().unwrap() * config.height().unwrap() * 4) as usize];

    let (packed, stats) =
        PackedScanFrame::pack_rgba(&config, &frame).expect("scan packing should succeed");
    let words = packed.as_words();

    assert_eq!(words[0], 1 << 13);
    assert_eq!(
        words[1],
        encode_repeat_span_word(64, 1 << 13).expect("repeat span word should encode")
    );
    assert_eq!(words[2], 0);
    assert_eq!(words[3], 0);
    assert_eq!(words[4], 2047);
    assert_eq!(stats.compressed_blank_groups, 32 * 11);
    assert_eq!(stats.merged_identical_groups, 0);
    assert_eq!(stats.word_count, 5);
}

#[test]
fn pi5_scan_raw_span_control_word_embeds_the_first_pin_word() {
    let control = encode_raw_span_word(2, 1 << 13).expect("raw span word should encode");

    assert_eq!(control, (1 << 22) | (1 << 1));
    assert!(
        encode_raw_span_word(257, 1 << 13).is_err(),
        "raw spans longer than 256 pixels should be rejected"
    );
}

#[test]
fn pi5_scan_pack_rgba_merges_nonadjacent_identical_plane_payloads() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Optimized))
        .expect("single-panel Pi 5 scan config should be valid");
    let mut frame = vec![0_u8; (config.width().unwrap() * config.height().unwrap() * 4) as usize];

    for pixel in frame.chunks_exact_mut(4) {
        pixel[0] = 0b1010_0000;
        pixel[3] = 255;
    }

    let (packed, stats) =
        PackedScanFrame::pack_rgba(&config, &frame).expect("scan packing should succeed");

    assert_eq!(stats.compressed_blank_groups, 32 * 9);
    assert_eq!(stats.merged_identical_groups, 32);
    assert_eq!(packed.word_count(), 32 * 5);
}

#[test]
fn pi5_scan_pack_rgba_uses_inlined_raw_headers_for_dense_frames() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(11))
        .and_then(|config| config.with_format(Pi5ScanFormat::Optimized))
        .expect("single-panel Pi 5 scan config should be valid");
    let frame = frame_bytes(config.width().unwrap(), config.height().unwrap(), 31);

    let (packed, stats) =
        PackedScanFrame::pack_rgba(&config, &frame).expect("scan packing should succeed");

    assert_eq!(stats.compressed_blank_groups, 96);
    assert_eq!(stats.merged_identical_groups, 0);
    assert_eq!(packed.word_count(), 6464);
    assert_eq!(stats.word_count, packed.word_count());
}

#[test]
fn pi5_scan_packed_frame_repetition_duplicates_transport_words_in_order() {
    let original = PackedScanFrame::from_words(vec![1, 2, 3, 4]);

    let repeated = original
        .repeated(3)
        .expect("packed frame repetition should succeed");

    assert_eq!(repeated.as_words(), &[1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4]);
}

#[test]
fn pi5_scan_packed_frame_repetition_rejects_zero_copies() {
    let original = PackedScanFrame::from_words(vec![1, 2, 3, 4]);

    let error = original
        .repeated(0)
        .expect_err("zero-copy repetition should be rejected");

    assert!(error.contains("at least one copy"));
}

#[test]
fn pi5_scan_config_accepts_adafruit_hat_for_simple_mode() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHat, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("Pi 5 simple scan transport should accept the non-PWM Adafruit HAT wiring");

    assert_eq!(config.pinout().oe_gpio(), LEGACY_OE_GPIO);
}

#[test]
fn pi5_scan_pack_rgba_splits_large_internal_blank_spans() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Optimized))
        .expect("single-panel Pi 5 scan config should be valid");
    let width = config.width().unwrap() as usize;
    let height = config.height().unwrap() as usize;
    let mut frame = vec![0_u8; width * height * 4];

    for row in 0..height {
        for column in 0..width {
            if (column / 16) % 2 != 0 {
                continue;
            }
            let base = ((row * width) + column) * 4;
            frame[base] = 255;
            frame[base + 1] = 255;
            frame[base + 2] = 255;
            frame[base + 3] = 255;
        }
    }

    let (packed, stats) =
        PackedScanFrame::pack_rgba(&config, &frame).expect("scan packing should succeed");

    assert_eq!(stats.compressed_blank_groups, 32 * 3);
    assert_eq!(stats.merged_identical_groups, 32 * 7);
    assert_eq!(packed.word_count(), 32 * 8);
}

#[test]
fn pi5_scan_trace_decoder_matches_expected_simple_group_trace() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(11))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 scan config should be valid");
    let frame = frame_bytes(config.width().unwrap(), config.height().unwrap(), 31);

    let (packed, _stats) =
        PackedScanFrame::pack_rgba(&config, &frame).expect("scan packing should succeed");
    let expected = config
        .debug_expected_group_trace(&frame, 0, 0)
        .expect("expected group trace should build");
    let decoded = packed
        .debug_decode_group_trace(&config, 0, 0)
        .expect("packed group trace should decode");

    assert_eq!(decoded, expected);
}

#[test]
fn pi5_simple_group_simulation_matches_reference_for_full_blue_fill() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = solid_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0, 0, 255);

    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let simulated = simulate_simple_group_output(&config, &words)
        .expect("simple group simulation should succeed");

    assert_eq!(simulated.row_pair, 0);
    assert!(simulated.oe_active_during_dwell);
    assert_eq!(simulated.columns.len(), 64);
    assert!(simulated.columns.iter().all(|column| {
        column.top_rgb == [false, false, true] && column.bottom_rgb == [false, false, true]
    }));
}

#[test]
fn pi5_simple_group_simulation_matches_reference_for_fixed_row_bars() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = row_bars_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0);

    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple row-bar group words should build");
    let simulated = simulate_simple_group_output(&config, &words)
        .expect("simple row-bar simulation should succeed");
    let expected = expected_group_output_from_rgba(&config, &frame, 0);

    assert_eq!(simulated, expected);
}

#[test]
fn pi5_simple_full_frame_simulation_reconstructs_uniform_blue_panel() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = solid_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0, 0, 255);
    let simulated = simulate_simple_full_frame(&config, &frame)
        .expect("simple full-frame simulation should succeed");
    let expected = expected_frame_output_from_rgba(&config, &frame)
        .expect("expected frame output should build");

    assert_eq!(simulated, expected);
}

#[test]
fn pi5_simple_pio_emulator_reconstructs_full_frame_position_by_position() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = position_pattern_rgba_frame(config.width().unwrap(), config.height().unwrap());
    let simulated = simulate_simple_full_frame_via_pio_emulator(&config, &frame)
        .expect("opcode-level simple PIO emulator should reconstruct the full frame");
    let expected = expected_frame_output_from_rgba(&config, &frame)
        .expect("expected frame output should build");

    assert_eq!(simulated, expected);
}

#[test]
fn pi5_simple_group_words_only_touch_rgb_address_and_oe_bits() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple scan config should be valid");
    let width = config.width().expect("width should be available");
    let height = config.height().expect("height should be available");
    let frame = solid_rgba_frame(width, height, 0, 0, 255);
    let width = width as usize;
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let parsed = parse_simple_group(&words, width);
    let allowed_mask = USED_SIMPLE_GPIOS
        .into_iter()
        .chain([LAT_GPIO])
        .fold(0_u32, |mask, gpio| {
            mask | (1_u32 << (gpio - PIN_WORD_BASE_GPIO))
        });

    for &word in &[words[SIMPLE_BLANK_WORD_INDEX]] {
        assert_eq!(
            word & !allowed_mask,
            0,
            "blank word touched an unexpected GPIO bit"
        );
    }
    for &word in &parsed.shift_words {
        assert_eq!(
            word & !allowed_mask,
            0,
            "shift word touched an unexpected GPIO bit"
        );
    }
    assert_eq!(
        parsed.latch_word & !allowed_mask,
        0,
        "latch word touched an unexpected GPIO bit"
    );
    assert_eq!(
        parsed.post_latch_word & !allowed_mask,
        0,
        "post-latch word touched an unexpected GPIO bit"
    );
    assert_eq!(
        parsed.active_word & !allowed_mask,
        0,
        "active word touched an unexpected GPIO bit"
    );
}

#[test]
fn pi5_simple_group_words_keep_gpio4_in_sync_with_oe_for_adafruit_hat_pwm() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple scan config should be valid");
    let frame = solid_rgba_frame(
        config.width().expect("width should be available"),
        config.height().expect("height should be available"),
        0,
        0,
        255,
    );
    let width = config.width().expect("width should be available") as usize;
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let parsed = parse_simple_group(&words, width);
    let gpio4_mask = 1_u32 << (LEGACY_OE_GPIO - PIN_WORD_BASE_GPIO);

    assert_eq!(
        words[SIMPLE_BLANK_WORD_INDEX] & gpio4_mask,
        gpio4_mask,
        "blank word should drive GPIO4 high so it mirrors GPIO18's inactive OE state"
    );
    for &word in &parsed.shift_words {
        assert_eq!(
            word & gpio4_mask,
            gpio4_mask,
            "shift words should keep GPIO4 high while GPIO18 keeps OE inactive"
        );
    }
    assert_eq!(
        parsed.latch_word & gpio4_mask,
        gpio4_mask,
        "latch word should keep GPIO4 high while OE remains inactive"
    );
    assert_eq!(
        parsed.post_latch_word & gpio4_mask,
        gpio4_mask,
        "post-latch word should keep GPIO4 high while OE remains inactive"
    );
    assert_eq!(
        parsed.active_word & gpio4_mask,
        0,
        "active word should drive GPIO4 low so it mirrors GPIO18's active-low OE state"
    );
}

#[test]
fn pi5_simple_group_words_drive_gpio4_as_oe_for_adafruit_hat() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHat, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple scan config should be valid");
    let frame = solid_rgba_frame(
        config.width().expect("width should be available"),
        config.height().expect("height should be available"),
        0,
        0,
        255,
    );
    let width = config.width().expect("width should be available") as usize;
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let parsed = parse_simple_group(&words, width);
    let gpio4_mask = 1_u32 << (LEGACY_OE_GPIO - PIN_WORD_BASE_GPIO);

    assert_ne!(
        words[SIMPLE_BLANK_WORD_INDEX] & gpio4_mask,
        0,
        "blank word should drive GPIO4 high so the AdafruitHat panel stays blank"
    );
    for &word in &parsed.shift_words {
        assert_ne!(
            word & gpio4_mask,
            0,
            "shift words should keep GPIO4 high so the AdafruitHat panel stays blank while shifting"
        );
    }
    assert_eq!(
        parsed.latch_word & gpio4_mask,
        gpio4_mask,
        "latch word should keep GPIO4 high while the panel remains blank"
    );
    assert_eq!(
        parsed.post_latch_word & gpio4_mask,
        gpio4_mask,
        "post-latch word should keep GPIO4 high before the panel becomes visible"
    );
    assert_eq!(
        parsed.active_word & gpio4_mask,
        0,
        "active word should drive GPIO4 low so the AdafruitHat panel becomes visible"
    );
}

#[test]
fn pi5_simple_group_words_keep_clk_low_and_only_raise_lat_for_the_latch_word() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple scan config should be valid");
    let frame = solid_rgba_frame(
        config.width().expect("width should be available"),
        config.height().expect("height should be available"),
        0,
        0,
        255,
    );
    let width = config.width().expect("width should be available") as usize;
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let parsed = parse_simple_group(&words, width);
    let clock_mask = 1_u32 << (CLK_GPIO - PIN_WORD_BASE_GPIO);
    let lat_mask = 1_u32 << (LAT_GPIO - PIN_WORD_BASE_GPIO);

    for &word in &[words[SIMPLE_BLANK_WORD_INDEX]] {
        assert_eq!(
            word & clock_mask,
            0,
            "blank word should keep CLK low so side-set owns that pin"
        );
        assert_eq!(word & lat_mask, 0, "blank word should keep LAT low");
    }
    for &word in &parsed.shift_words {
        assert_eq!(
            word & clock_mask,
            0,
            "shift word should keep CLK low so side-set owns that pin"
        );
        assert_eq!(word & lat_mask, 0, "shift word should keep LAT low");
    }
    assert_eq!(
        parsed.latch_word & clock_mask,
        0,
        "latch word should keep CLK low while LAT is asserted in-band"
    );
    assert_eq!(
        parsed.latch_word & lat_mask,
        lat_mask,
        "latch word should be the only literal GPIO word that raises LAT"
    );
    assert_eq!(
        parsed.post_latch_word & lat_mask,
        0,
        "post-latch word should return LAT low"
    );
    assert_eq!(
        parsed.active_word & ((1_u32 << (CLK_GPIO - PIN_WORD_BASE_GPIO)) | lat_mask),
        0,
        "active word should keep both CLK and LAT low"
    );
}

#[test]
fn pi5_simple_group_words_encode_the_requested_row_address_for_every_row_pair() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple scan config should be valid");
    let pinout = config.pinout();
    let width = config.width().expect("width should be available") as usize;
    let row_pairs = config.row_pairs().expect("row pairs should resolve");
    let frame = solid_rgba_frame(
        config.width().expect("width should be available"),
        config.height().expect("height should be available"),
        0,
        0,
        255,
    );
    let address_mask = pinout.addr_gpios().into_iter().fold(0_u32, |mask, gpio| {
        mask | (1_u32 << (u32::from(gpio) - PIN_WORD_BASE_GPIO))
    });

    for row_pair in 0..row_pairs {
        let expected_address_bits =
            pinout
                .addr_gpios()
                .into_iter()
                .enumerate()
                .fold(0_u32, |bits, (bit_index, gpio)| {
                    if (row_pair & (1 << bit_index)) != 0 {
                        bits | (1_u32 << (u32::from(gpio) - PIN_WORD_BASE_GPIO))
                    } else {
                        bits
                    }
                });
        let words = build_simple_group_words_for_rgba(&config, &frame, row_pair, 0)
            .expect("simple group words should build");
        let parsed = parse_simple_group(&words, width);

        assert_eq!(
            words[SIMPLE_BLANK_WORD_INDEX] & address_mask,
            expected_address_bits,
            "blank word should carry the requested row-pair address"
        );
        for &word in &parsed.shift_words {
            assert_eq!(
                word & address_mask,
                expected_address_bits,
                "every shift word should hold the selected row-pair address stable"
            );
        }
        assert_eq!(
            parsed.latch_word & address_mask,
            expected_address_bits,
            "latch word should keep the selected row-pair address stable"
        );
        assert_eq!(
            parsed.post_latch_word & address_mask,
            expected_address_bits,
            "post-latch word should keep the selected row-pair address stable"
        );
        assert_eq!(
            parsed.active_word & address_mask,
            expected_address_bits,
            "active word should keep the selected row-pair address during dwell"
        );
    }
}

#[test]
fn pi5_simple_pio_emulator_consumes_compact_group_words_in_row_engine_order() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = solid_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0, 0, 255);
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let parsed = parse_simple_group(&words, config.width().expect("width should resolve") as usize);
    let simulated = simulate_simple_hub75_group(&config, &words)
        .expect("simple PIO emulator should execute the group");
    let command_kind_steps = simple_command_kind_steps(&simulated);
    let command_count_steps = simple_command_count_steps(&simulated);
    let delay_output_steps = simple_delay_output_steps(&simulated);
    let blank_output = delay_output_steps
        .first()
        .expect("program should apply the blank word in the delay path");
    let active_output = delay_output_steps
        .last()
        .expect("program should apply the active row word in the final delay phase");

    assert!(
        simulated.stalled_on_pull,
        "program should block waiting for the next group once FIFO words are exhausted"
    );
    assert!(
        gpio_is_high(blank_output.pins, OE_GPIO),
        "blank phase should keep OE inactive"
    );
    assert!(
        !gpio_is_high(active_output.pins, OE_GPIO),
        "active phase should drive OE active-low"
    );
    assert_eq!(
        command_kind_steps.first().expect("first command kind step should exist").x,
        0,
        "the first command should be a delay command for blank/address settle"
    );
    assert_eq!(
        command_count_steps.first().expect("first command count step should exist").y,
        parsed.blank_command & SIMPLE_COMMAND_COUNT_MASK,
        "the blank/address delay command should load its encoded count into Y"
    );
    assert_eq!(
        command_kind_steps
            .get(1)
            .expect("second command kind step should exist")
            .x,
        1,
        "the blue-fill row should use the literal data path in the rollback simple transport"
    );
    assert_eq!(
        command_count_steps
            .get(1)
            .expect("second command count step should exist")
            .y,
        parsed.shift_commands[0].command_word & SIMPLE_COMMAND_COUNT_MASK,
        "the shift command should load its encoded logical count into Y"
    );
    assert_eq!(
        parsed.shift_commands.len(),
        1,
        "the blue-fill row should use a single compact shift command"
    );
    assert_eq!(
        parsed.shift_commands[0].kind,
        TestSimpleCommandKind::Data,
        "the rollback simple transport should emit a literal data command for the row"
    );
    assert_eq!(
        parsed.shift_commands[0].logical_count,
        config.width().expect("width should resolve") as usize,
        "the literal shift command should still decode back to the full logical row width"
    );
    assert_eq!(
        command_kind_steps
            .last()
            .expect("final command kind step should exist")
            .x,
        0,
        "the final command should be a delay command for visible dwell"
    );
    assert_eq!(
        command_count_steps
            .last()
            .expect("final command count step should exist")
            .y,
        parsed.active_command & SIMPLE_COMMAND_COUNT_MASK,
        "the dwell command should load its encoded count into Y"
    );
    assert_eq!(
        (parsed.active_command & SIMPLE_COMMAND_COUNT_MASK) + 1,
        config.lsb_dwell_ticks,
        "encoded dwell command should still decode back to the logical dwell interval"
    );
}

#[test]
fn pi5_simple_mixed_rows_stay_literal_until_repeat_boundaries_are_hardware_safe() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = row_bars_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0);
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let parsed = parse_simple_group(&words, config.width().expect("width should resolve") as usize);

    assert_eq!(
        parsed.shift_commands.len(),
        1,
        "mixed rows should ride a single literal data command so every column sees the same shift cadence"
    );
    assert_eq!(
        parsed.shift_commands[0].kind,
        TestSimpleCommandKind::Data,
        "row-bars should not use repeat segments until hardware repeat boundaries are validated"
    );
    assert_eq!(
        parsed.shift_commands[0].logical_count,
        config.width().expect("width should resolve") as usize,
        "the fallback literal command should still cover the full row width"
    );
}

#[test]
fn pi5_simple_timing_estimate_accounts_for_clock_divider() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_lsb_dwell_ticks(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .and_then(|config| {
            config.with_timing(Pi5ScanTiming {
                clock_divider: 20.0,
                post_addr_ticks: 5,
                latch_ticks: 1,
                post_latch_ticks: 1,
                simple_clock_hold_ticks: 1,
            })
        })
        .expect("single-panel Pi 5 simple config should be valid");
    let estimate = estimate_simple_hub75_frame_timing(&config, 200_000_000.0)
        .expect("simple timing estimate should resolve");

    assert_eq!(
        estimate.row_pairs, 32,
        "a 64x64 1/32-scan panel should expose 32 row pairs"
    );
    assert!(
        (estimate.pio_tick_seconds - 100e-9).abs() < 1e-15,
        "divider 20 on a 200 MHz clock should yield 100 ns PIO ticks"
    );
    assert_eq!(
        estimate.group_cycles_by_plane.len(),
        1,
        "pwm_bits=1 should produce one per-plane cycle estimate"
    );
    assert!(
        estimate.group_cycles_by_plane[0] > 0,
        "the simple command stream should consume a non-zero number of PIO cycles per row pair"
    );
    assert_eq!(
        estimate.full_frame_cycles,
        estimate.group_cycles_by_plane[0] * 32,
        "full-frame timing should multiply the one-plane row-pair budget across all 32 row pairs"
    );
    assert!(
        estimate.full_frame_seconds > 0.0,
        "the cycle budget should convert into a positive full-frame wall-clock time"
    );
    assert!(
        (estimate.full_frame_hz - (1.0 / estimate.full_frame_seconds)).abs() < 1e-6,
        "the timing helper should keep the reported frame rate consistent with the computed frame time"
    );
    assert!(
        estimate.full_frame_hz > 0.0,
        "the timing helper should report a positive frame rate"
    );
}

#[test]
fn pi5_pio_program_summaries_track_generated_program_shapes() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let simple_info = pio_program_info_for_format(&config, Pi5ScanFormat::Simple);
    let optimized_info = pio_program_info_for_format(&config, Pi5ScanFormat::Optimized);

    assert_eq!(
        simple_info.instructions.len(),
        simple_info.program.len(),
        "simple program summaries should cover every generated opcode"
    );
    assert_eq!(
        simple_info.simulator_config.out_pin_base,
        0,
        "the simple simulator should match the native shim's real GPIO0..27 output window"
    );
    assert_eq!(
        simple_info.simulator_config.out_pin_count,
        28,
        "the simple simulator should drive the full GPIO0..27 window like the native shim"
    );
    assert_eq!(
        simple_info.simulator_config.sideset_total_bits,
        PI5_PIO_SIMPLE_HUB75_SIDESET_TOTAL_BITS,
        "the simple simulator should model the generated simple-program side-set field width"
    );
    assert_eq!(
        optimized_info.instructions.len(),
        optimized_info.program.len(),
        "resident parser summaries should cover every generated opcode"
    );
    assert_eq!(
        simple_info
            .instructions
            .iter()
            .filter(|instruction| instruction.out_writes_window)
            .count(),
        2,
        "the simple Piomatter-parity program should only write the OUT window for the data and delay GPIO words"
    );
    assert_eq!(
        simple_info
            .instructions
            .iter()
            .filter(|instruction| instruction.set_writes_pins)
            .count(),
        0,
        "the simple command interpreter should not use SET PINS because LAT now lives in-band"
    );
    assert_eq!(
        optimized_info
            .instructions
            .iter()
            .filter(|instruction| instruction.out_writes_window)
            .count(),
        4,
        "the resident parser should only touch the OUT window on the blank, repeat, raw, and active write instructions"
    );
    assert!(
        optimized_info
            .instructions
            .iter()
            .any(|instruction| instruction.mnemonic == "mov pins, x"),
        "the resident parser summary should reflect the generated repeat-path MOV PINS instruction"
    );
}

#[test]
fn piomatter_parity_program_emits_expected_gpio_trace() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let program_info = pio_program_info_for_format(&config, Pi5ScanFormat::Simple);
    let data_word_a = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let data_word_b = (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO);
    let delay_word = 1_u32 << LAT_GPIO;
    let fifo_words = [
        PIOMATTER_COMMAND_DATA | 1,
        data_word_a,
        data_word_b,
        0,
        delay_word,
    ];
    let simulated = simulate_program(
        &program_info.program,
        program_info.simulator_config,
        &fifo_words,
        64,
    )
    .expect("Piomatter parity command stream should simulate");

    assert!(
        simulated.stalled_on_pull,
        "the simulator should stop by stalling on the next pull once the scripted parity command stream is consumed"
    );

    let trace = simulated
        .steps
        .iter()
        .map(|step| (step.pc, step.pins))
        .collect::<Vec<_>>();
    let expected_trace = vec![
        (0, 0),
        (1, 0),
        (2, 0),
        (3, data_word_a),
        (4, data_word_a | (1_u32 << CLK_GPIO)),
        (3, data_word_b),
        (4, data_word_b | (1_u32 << CLK_GPIO)),
        (0, data_word_b | (1_u32 << CLK_GPIO)),
        (1, data_word_b | (1_u32 << CLK_GPIO)),
        (2, data_word_b | (1_u32 << CLK_GPIO)),
        (5, delay_word),
        (6, delay_word),
        (7, delay_word),
    ];

    assert_eq!(
        trace, expected_trace,
        "the Piomatter-parity program should keep the exact GPIO sequence for one two-word data command followed by one delay command"
    );
}

#[test]
fn piomatter_row_repeat_engine_preserves_observable_gpio_waveform_for_repeated_rows() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let literal_program = pio_program_info_for_format(&config, Pi5ScanFormat::Simple);
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);

    let repeated_blue = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let active_word = 1_u32 << OE_GPIO;
    let inactive_word = 0;

    let literal_fifo_words = [
        PIOMATTER_COMMAND_DATA | 3,
        repeated_blue,
        repeated_blue,
        repeated_blue,
        repeated_blue,
        2,
        active_word,
        1,
        inactive_word,
        3,
        inactive_word | (1_u32 << LAT_GPIO),
        1,
        inactive_word,
    ];
    let row_repeat_fifo_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 3,
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        active_word,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        inactive_word,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        inactive_word,
    ];

    let literal_simulation = simulate_program(
        &literal_program.program,
        literal_program.simulator_config,
        &literal_fifo_words,
        256,
    )
    .expect("literal Piomatter-style command stream should simulate");
    let row_repeat_simulation = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_fifo_words,
        256,
    )
    .expect("row-repeat command stream should simulate");

    let literal_observable = extract_gpio_observable_trace(&literal_simulation);
    let row_repeat_observable = extract_gpio_observable_trace(&row_repeat_simulation);

    assert_eq!(
        literal_observable.low_words[..4],
        row_repeat_observable.low_words[..4],
        "the row-repeat engine should preserve the same shifted low GPIO words as the literal Piomatter stream for repeated rows"
    );
    assert_eq!(
        literal_observable.high_words,
        row_repeat_observable.high_words,
        "the row-repeat engine should preserve the same clock-high GPIO words as the literal Piomatter stream for repeated rows"
    );
}

#[test]
fn piomatter_row_repeat_engine_preserves_gpio_transition_shape_for_one_nonuniform_row() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let literal_program = pio_program_info_for_format(&config, Pi5ScanFormat::Simple);
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);

    let data_word_a = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO) | (1_u32 << A_GPIO);
    let data_word_b = (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO) | (1_u32 << A_GPIO);
    let active_word = (1_u32 << OE_GPIO) | (1_u32 << A_GPIO);
    let inactive_word = 1_u32 << A_GPIO;
    let latch_word = inactive_word | (1_u32 << LAT_GPIO);
    let next_addr_word = 1_u32 << B_GPIO;

    let literal_fifo_words = [
        PIOMATTER_COMMAND_DATA | 1,
        data_word_a,
        data_word_b,
        2,
        active_word,
        1,
        inactive_word,
        3,
        latch_word,
        1,
        next_addr_word,
    ];
    let row_repeat_fifo_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 1,
        data_word_a,
        data_word_b,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        active_word,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        inactive_word,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        next_addr_word,
    ];

    let literal_simulation = simulate_program(
        &literal_program.program,
        literal_program.simulator_config,
        &literal_fifo_words,
        256,
    )
    .expect("literal Piomatter-style command stream should simulate");
    let row_repeat_simulation = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_fifo_words,
        256,
    )
    .expect("row-repeat command stream should simulate");

    let literal_observable = extract_gpio_observable_trace(&literal_simulation);
    let row_repeat_observable = extract_gpio_observable_trace(&row_repeat_simulation);
    assert_eq!(
        literal_observable.low_words[..2],
        row_repeat_observable.low_words[..2],
        "the row-repeat engine should preserve the same shifted low GPIO words as the literal Piomatter stream for nonuniform rows"
    );
    assert_eq!(
        literal_observable.high_words,
        row_repeat_observable.high_words,
        "the row-repeat engine should preserve the same clock-high GPIO words as the literal Piomatter stream for nonuniform rows"
    );

    assert_eq!(
        extract_pin_transition_sequence(&literal_simulation),
        extract_pin_transition_sequence(&row_repeat_simulation),
        "the row-repeat engine should preserve the externally visible GPIO transition sequence for one nonuniform row"
    );
}

#[test]
fn piomatter_row_repeat_engine_preserves_quadrant_scene_row_waveform() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let literal_program = pio_program_info_for_format(&config, Pi5ScanFormat::Simple);
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let frame = quadrant_rgba_frame(64, 64);

    assert_eq!(&frame[0..4], &[255, 0, 0, 255]);
    assert_eq!(&frame[((31 * 64 + 63) * 4) as usize..((31 * 64 + 63) * 4 + 4) as usize], &[0, 255, 0, 255]);
    assert_eq!(&frame[((63 * 64) * 4) as usize..((63 * 64) * 4 + 4) as usize], &[0, 0, 255, 255]);
    assert_eq!(
        &frame[((63 * 64 + 63) * 4) as usize..((63 * 64 + 63) * 4 + 4) as usize],
        &[255, 255, 255, 255]
    );

    let left_word = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_word =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let active_word = 1_u32 << OE_GPIO;
    let inactive_word = 0;
    let latch_word = 1_u32 << LAT_GPIO;

    let literal_fifo_words = std::iter::once(PIOMATTER_COMMAND_DATA | 63)
        .chain(std::iter::repeat_n(left_word, 32))
        .chain(std::iter::repeat_n(right_word, 32))
        .chain([2, active_word, 1, inactive_word, 3, latch_word, 1, inactive_word])
        .collect::<Vec<_>>();
    let row_repeat_fifo_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
        .chain(std::iter::repeat_n(left_word, 32))
        .chain(std::iter::repeat_n(right_word, 32))
        .chain([
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
            active_word,
            encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
            inactive_word,
            encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
            encode_row_engine_count(2, "next-address hold")
                .expect("next-address hold should encode"),
            inactive_word,
        ])
        .collect::<Vec<_>>();

    let literal_simulation = simulate_program(
        &literal_program.program,
        literal_program.simulator_config,
        &literal_fifo_words,
        1024,
    )
    .expect("literal Piomatter quadrant row should simulate");
    let row_repeat_simulation = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_fifo_words,
        1024,
    )
    .expect("row-repeat quadrant row should simulate");

    let literal_observable = extract_gpio_observable_trace(&literal_simulation);
    let row_repeat_observable = extract_gpio_observable_trace(&row_repeat_simulation);
    assert_eq!(
        literal_observable.low_words[..64],
        row_repeat_observable.low_words[..64],
        "the row-repeat engine should preserve the shifted low GPIO words for a quadrant scene row"
    );
    assert_eq!(
        literal_observable.high_words[..64],
        row_repeat_observable.high_words[..64],
        "the row-repeat engine should preserve the clock-high GPIO words for a quadrant scene row"
    );

    let half_width = 32;
    assert!(
        literal_observable.low_words[..half_width]
            .iter()
            .all(|&word| word == left_word),
        "the left half of the quadrant row should stay on the red/blue mixed word"
    );
    assert!(
        literal_observable.low_words[half_width..64]
            .iter()
            .all(|&word| word == right_word),
        "the right half of the quadrant row should stay on the green/white mixed word"
    );
}

#[test]
fn piomatter_row_compact_engine_preserves_repeated_nonuniform_quadrant_and_center_box_rows() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_compact_program = piomatter_row_compact_engine_parity_program_info(&config);

    let repeated_blue = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let repeated_active = 1_u32 << OE_GPIO;
    let repeated_inactive = 0;
    let row_repeat_repeated_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 3,
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        repeated_inactive,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        repeated_inactive,
    ];
    let row_compact_repeated_words = [
        encode_row_compact_repeat_command(
            4,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("repeat row count should encode"),
        repeated_blue,
        repeated_active,
        repeated_inactive,
        repeated_inactive,
    ];

    let data_word_a = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO) | (1_u32 << A_GPIO);
    let data_word_b = (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO) | (1_u32 << A_GPIO);
    let active_word = (1_u32 << OE_GPIO) | (1_u32 << A_GPIO);
    let inactive_word = 1_u32 << A_GPIO;
    let next_addr_word = 1_u32 << B_GPIO;
    let row_repeat_nonuniform_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 1,
        data_word_a,
        data_word_b,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        (1_u32 << OE_GPIO) | (1_u32 << A_GPIO),
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        inactive_word,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        next_addr_word,
    ];
    let row_compact_nonuniform_words = [
        encode_row_compact_literal_command(
            2,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("literal row count should encode"),
        data_word_a,
        data_word_b,
        active_word,
        inactive_word,
        next_addr_word,
    ];

    let alternating_left = (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO);
    let alternating_right = (1_u32 << G1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let row_repeat_alternating_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
        .chain((0..64).map(|index| {
            if index % 2 == 0 {
                alternating_left
            } else {
                alternating_right
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
    let row_compact_alternating_words = std::iter::once(
        encode_row_compact_literal_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("literal row count should encode"),
    )
    .chain((0..64).map(|index| {
        if index % 2 == 0 {
            alternating_left
        } else {
            alternating_right
        }
    }))
    .chain([
        1_u32 << OE_GPIO,
        0,
        0,
    ])
    .collect::<Vec<_>>();

    let left_word = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_word =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let row_repeat_quadrant_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
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
    let row_compact_quadrant_words = std::iter::once(
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
    let center_box_dark_word = 1_u32 << OE_GPIO;
    let center_box_white_word = (1_u32 << R1_GPIO)
        | (1_u32 << G1_GPIO)
        | (1_u32 << B1_GPIO)
        | (1_u32 << R2_GPIO)
        | (1_u32 << G2_GPIO)
        | (1_u32 << B2_GPIO)
        | (1_u32 << OE_GPIO);
    let row_repeat_center_box_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
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
    let row_compact_center_box_words = std::iter::once(
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

    let row_repeat_repeated_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_repeated_words,
        256,
    )
    .expect("row-repeat repeated row should simulate");
    let row_compact_repeated_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &row_compact_repeated_words,
        512,
    )
    .expect("row-compact repeated row should simulate");
    let row_repeat_repeated_observable = extract_gpio_observable_trace(&row_repeat_repeated_sim);
    let row_compact_repeated_observable = extract_gpio_observable_trace(&row_compact_repeated_sim);
    assert_eq!(
        row_repeat_repeated_observable.low_words[..4],
        row_compact_repeated_observable.low_words[..4],
        "the row-compact engine should preserve the shifted low GPIO words for repeated rows"
    );
    assert_eq!(
        row_repeat_repeated_observable.high_words[..4],
        row_compact_repeated_observable.high_words[..4],
        "the row-compact engine should preserve the shifted clock-high GPIO words for repeated rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_repeated_sim),
        extract_pin_transition_sequence(&row_compact_repeated_sim),
        "the row-compact engine should preserve the externally visible GPIO transitions for repeated rows"
    );

    let row_repeat_nonuniform_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_nonuniform_words,
        256,
    )
    .expect("row-repeat nonuniform row should simulate");
    let row_compact_nonuniform_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &row_compact_nonuniform_words,
        512,
    )
    .expect("row-compact nonuniform row should simulate");
    let row_repeat_nonuniform_observable =
        extract_gpio_observable_trace(&row_repeat_nonuniform_sim);
    let row_compact_nonuniform_observable =
        extract_gpio_observable_trace(&row_compact_nonuniform_sim);
    assert_eq!(
        row_repeat_nonuniform_observable.low_words[..2],
        row_compact_nonuniform_observable.low_words[..2],
        "the row-compact engine should preserve the shifted low GPIO words for nonuniform rows"
    );
    assert_eq!(
        row_repeat_nonuniform_observable.high_words[..2],
        row_compact_nonuniform_observable.high_words[..2],
        "the row-compact engine should preserve the shifted clock-high GPIO words for nonuniform rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_nonuniform_sim),
        extract_pin_transition_sequence(&row_compact_nonuniform_sim),
        "the row-compact engine should preserve the externally visible GPIO transitions for nonuniform rows"
    );
    assert!(
        row_compact_nonuniform_words.len() < row_repeat_nonuniform_words.len(),
        "the row-compact literal-row encoding should shrink dense nonuniform rows without changing their waveform"
    );

    let row_repeat_alternating_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_alternating_words,
        2048,
    )
    .expect("row-repeat alternating row should simulate");
    let row_compact_alternating_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &row_compact_alternating_words,
        2048,
    )
    .expect("row-compact alternating row should simulate");
    let row_repeat_alternating_observable =
        extract_gpio_observable_trace(&row_repeat_alternating_sim);
    let row_compact_alternating_observable =
        extract_gpio_observable_trace(&row_compact_alternating_sim);
    assert_eq!(
        row_repeat_alternating_observable.low_words[..64],
        row_compact_alternating_observable.low_words[..64],
        "the row-compact engine should preserve the shifted low GPIO words for dense alternating rows"
    );
    assert_eq!(
        row_repeat_alternating_observable.high_words[..64],
        row_compact_alternating_observable.high_words[..64],
        "the row-compact engine should preserve the shifted clock-high GPIO words for dense alternating rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_alternating_sim),
        extract_pin_transition_sequence(&row_compact_alternating_sim),
        "the row-compact engine should preserve the externally visible GPIO transitions for dense alternating rows"
    );
    assert!(
        row_compact_alternating_words.len() < row_repeat_alternating_words.len(),
        "the row-compact literal-row encoding should shrink dense alternating rows without changing their waveform"
    );

    let row_repeat_quadrant_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_quadrant_words,
        1024,
    )
    .expect("row-repeat quadrant row should simulate");
    let row_compact_quadrant_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &row_compact_quadrant_words,
        2048,
    )
    .expect("row-compact quadrant row should simulate");
    let row_repeat_quadrant_observable = extract_gpio_observable_trace(&row_repeat_quadrant_sim);
    let row_compact_quadrant_observable =
        extract_gpio_observable_trace(&row_compact_quadrant_sim);
    assert_eq!(
        row_repeat_quadrant_observable.low_words[..64],
        row_compact_quadrant_observable.low_words[..64],
        "the row-compact engine should preserve the shifted low GPIO words for a quadrant row"
    );
    assert_eq!(
        row_repeat_quadrant_observable.high_words[..64],
        row_compact_quadrant_observable.high_words[..64],
        "the row-compact engine should preserve the shifted clock-high GPIO words for a quadrant row"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_quadrant_sim),
        extract_pin_transition_sequence(&row_compact_quadrant_sim),
        "the row-compact engine should preserve the externally visible GPIO transitions for a quadrant row"
    );
    assert!(
        row_compact_quadrant_words.len() < row_repeat_quadrant_words.len(),
        "the row-compact quadrant encoding should shrink the payload by keeping the compact trailer while preserving the same shifted waveform"
    );

    let row_repeat_center_box_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_center_box_words,
        1024,
    )
    .expect("row-repeat center-box row should simulate");
    let row_compact_center_box_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &row_compact_center_box_words,
        2048,
    )
    .expect("row-compact center-box row should simulate");
    let row_repeat_center_box_observable =
        extract_gpio_observable_trace(&row_repeat_center_box_sim);
    let row_compact_center_box_observable =
        extract_gpio_observable_trace(&row_compact_center_box_sim);
    assert_eq!(
        row_repeat_center_box_observable.low_words[..64],
        row_compact_center_box_observable.low_words[..64],
        "the row-compact engine should preserve the shifted low GPIO words for a center-box row"
    );
    assert_eq!(
        row_repeat_center_box_observable.high_words[..64],
        row_compact_center_box_observable.high_words[..64],
        "the row-compact engine should preserve the shifted clock-high GPIO words for a center-box row"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_center_box_sim),
        extract_pin_transition_sequence(&row_compact_center_box_sim),
        "the row-compact engine should preserve the externally visible GPIO transitions for a center-box row"
    );
    assert!(
        row_compact_center_box_words.len() < row_repeat_center_box_words.len(),
        "the row-compact center-box encoding should shrink the payload by keeping the compact trailer while preserving the same shifted waveform"
    );
}

#[test]
fn piomatter_row_compact_engine_preserves_dark_rows_with_a_shorter_trailer() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_compact_program = piomatter_row_compact_engine_parity_program_info(&config);

    let dark_word = 0;
    let row_repeat_dark_words = [
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
    let row_compact_dark_words = [
        encode_row_compact_repeat_command(64, 0).expect("repeat row count should encode"),
        dark_word,
        0,
        0,
        0,
    ];

    let row_repeat_dark_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_dark_words,
        512,
    )
    .expect("row-repeat dark row should simulate");
    let row_compact_dark_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &row_compact_dark_words,
        512,
    )
    .expect("row-compact dark row should simulate");

    let row_repeat_dark_observable = extract_gpio_observable_trace(&row_repeat_dark_sim);
    let row_compact_dark_observable = extract_gpio_observable_trace(&row_compact_dark_sim);
    assert_eq!(
        row_repeat_dark_observable.low_words[..64],
        row_compact_dark_observable.low_words[..64],
        "the row-compact engine should preserve the shifted low GPIO words for dark rows"
    );
    assert_eq!(
        row_repeat_dark_observable.high_words[..64],
        row_compact_dark_observable.high_words[..64],
        "the row-compact engine should preserve the shifted clock-high GPIO words for dark rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_dark_sim),
        extract_pin_transition_sequence(&row_compact_dark_sim),
        "the row-compact engine should preserve the externally visible GPIO transitions for dark rows"
    );
    assert!(
        row_compact_dark_words.len() < row_repeat_dark_words.len(),
        "the row-compact dark-row encoding should still shrink the payload while preserving parity"
    );
    assert!(
        row_compact_dark_sim.steps.len() < row_repeat_dark_sim.steps.len(),
        "the row-compact dark-row path should still reduce simulated PIO work by keeping the compact trailer"
    );
}

#[test]
fn piomatter_row_compact_tight_engine_preserves_compact_waveforms_and_reduces_short_rows() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_compact_program = piomatter_row_compact_engine_parity_program_info(&config);
    let row_compact_tight_program = piomatter_row_compact_tight_engine_parity_program_info(&config);

    let repeated_blue_word = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let short_repeat_words = [
        encode_row_compact_repeat_command(64, 0).expect("repeat row count should encode"),
        repeated_blue_word,
        1_u32 << OE_GPIO,
        0,
        0,
    ];
    let alternating_left = (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO);
    let alternating_right = (1_u32 << G1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let long_literal_words = std::iter::once(
        encode_row_compact_literal_command(
            64,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("literal row count should encode"),
    )
    .chain((0..64).map(|index| {
        if index % 2 == 0 {
            alternating_left
        } else {
            alternating_right
        }
    }))
    .chain([
        1_u32 << OE_GPIO,
        0,
        0,
    ])
    .collect::<Vec<_>>();
    let mixed_frame_words = short_repeat_words
        .into_iter()
        .chain(long_literal_words.iter().copied())
        .collect::<Vec<_>>();

    let row_compact_short_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &short_repeat_words,
        1024,
    )
    .expect("row-compact short repeat row should simulate");
    let row_compact_tight_short_sim = simulate_program(
        &row_compact_tight_program.program,
        row_compact_tight_program.simulator_config,
        &short_repeat_words,
        1024,
    )
    .expect("row-compact-tight short repeat row should simulate");
    let row_compact_short_observable = extract_gpio_observable_trace(&row_compact_short_sim);
    let row_compact_tight_short_observable =
        extract_gpio_observable_trace(&row_compact_tight_short_sim);
    assert_eq!(
        row_compact_short_observable.low_words,
        row_compact_tight_short_observable.low_words,
        "the tight compact engine should preserve the shifted low GPIO words on short repeated rows",
    );
    assert_eq!(
        row_compact_short_observable.high_words,
        row_compact_tight_short_observable.high_words,
        "the tight compact engine should preserve the shifted clock-high GPIO words on short repeated rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_compact_short_sim),
        extract_pin_transition_sequence(&row_compact_tight_short_sim),
        "the tight compact engine should preserve the GPIO transition ordering on short repeated rows",
    );
    assert!(
        row_compact_tight_short_sim.steps.len() < row_compact_short_sim.steps.len(),
        "the tight compact engine should spend fewer instructions on short repeated rows",
    );
    assert!(
        row_compact_tight_short_sim
            .steps
            .last()
            .map(|step| step.cycle_end)
            .unwrap_or(0)
            < row_compact_short_sim
                .steps
                .last()
                .map(|step| step.cycle_end)
                .unwrap_or(0),
        "the tight compact engine should reduce total PIO cycles on short repeated rows",
    );

    let row_compact_long_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &long_literal_words,
        4096,
    )
    .expect("row-compact long literal row should simulate");
    let row_compact_tight_long_sim = simulate_program(
        &row_compact_tight_program.program,
        row_compact_tight_program.simulator_config,
        &long_literal_words,
        4096,
    )
    .expect("row-compact-tight long literal row should simulate");
    let row_compact_long_observable = extract_gpio_observable_trace(&row_compact_long_sim);
    let row_compact_tight_long_observable =
        extract_gpio_observable_trace(&row_compact_tight_long_sim);
    assert_eq!(
        row_compact_long_observable.low_words,
        row_compact_tight_long_observable.low_words,
        "the tight compact engine should preserve the shifted low GPIO words on long literal rows",
    );
    assert_eq!(
        row_compact_long_observable.high_words,
        row_compact_tight_long_observable.high_words,
        "the tight compact engine should preserve the shifted clock-high GPIO words on long literal rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_compact_long_sim),
        extract_pin_transition_sequence(&row_compact_tight_long_sim),
        "the tight compact engine should preserve GPIO transition ordering on long literal rows",
    );
    assert!(
        row_compact_tight_long_sim
            .steps
            .last()
            .map(|step| step.cycle_end)
            .unwrap_or(0)
            < row_compact_long_sim
                .steps
                .last()
                .map(|step| step.cycle_end)
                .unwrap_or(0),
        "the tight compact engine should reduce total PIO cycles on long literal rows",
    );

    let row_compact_frame_sim = simulate_program(
        &row_compact_program.program,
        row_compact_program.simulator_config,
        &mixed_frame_words,
        4096,
    )
    .expect("row-compact mixed frame should simulate");
    let row_compact_tight_frame_sim = simulate_program(
        &row_compact_tight_program.program,
        row_compact_tight_program.simulator_config,
        &mixed_frame_words,
        4096,
    )
    .expect("row-compact-tight mixed frame should simulate");
    let row_compact_frame_observable = extract_gpio_observable_trace(&row_compact_frame_sim);
    let row_compact_tight_frame_observable =
        extract_gpio_observable_trace(&row_compact_tight_frame_sim);
    assert_eq!(
        row_compact_frame_observable.low_words,
        row_compact_tight_frame_observable.low_words,
        "the tight compact engine should preserve low GPIO words across mixed short and long rows",
    );
    assert_eq!(
        row_compact_frame_observable.high_words,
        row_compact_tight_frame_observable.high_words,
        "the tight compact engine should preserve clock-high GPIO words across mixed short and long rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_compact_frame_sim),
        extract_pin_transition_sequence(&row_compact_tight_frame_sim),
        "the tight compact engine should preserve the GPIO transition ordering across mixed short and long rows",
    );
}

#[test]
fn piomatter_row_counted_engine_preserves_repeated_nonuniform_quadrant_and_center_box_rows() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_counted_program = piomatter_row_counted_engine_parity_program_info(&config);

    let repeated_blue = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let repeated_inactive = 0;
    let row_repeat_repeated_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 3,
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        repeated_inactive,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        repeated_inactive,
    ];
    let row_counted_repeated_words = [
        encode_row_counted_repeat_command(4).expect("repeat row count should encode"),
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        repeated_inactive,
        repeated_inactive,
    ];

    let data_word_a = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO) | (1_u32 << A_GPIO);
    let data_word_b = (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO) | (1_u32 << A_GPIO);
    let inactive_word = 1_u32 << A_GPIO;
    let next_addr_word = 1_u32 << B_GPIO;
    let row_repeat_nonuniform_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 1,
        data_word_a,
        data_word_b,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        (1_u32 << OE_GPIO) | (1_u32 << A_GPIO),
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        inactive_word,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        next_addr_word,
    ];
    let row_counted_nonuniform_words = [
        encode_row_counted_literal_command(2).expect("literal row count should encode"),
        data_word_a,
        data_word_b,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        (1_u32 << OE_GPIO) | (1_u32 << A_GPIO),
        inactive_word,
        next_addr_word,
    ];

    let left_word = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_word =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let row_repeat_quadrant_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
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
    let row_counted_quadrant_words = std::iter::once(
        encode_row_counted_literal_command(64).expect("literal row count should encode"),
    )
    .chain(std::iter::repeat_n(left_word, 32))
    .chain(std::iter::repeat_n(right_word, 32))
    .chain([
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        0,
    ])
    .collect::<Vec<_>>();

    let center_box_dark_word = 1_u32 << OE_GPIO;
    let center_box_white_word = (1_u32 << R1_GPIO)
        | (1_u32 << G1_GPIO)
        | (1_u32 << B1_GPIO)
        | (1_u32 << R2_GPIO)
        | (1_u32 << G2_GPIO)
        | (1_u32 << B2_GPIO)
        | (1_u32 << OE_GPIO);
    let row_repeat_center_box_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
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
    let row_counted_center_box_words = std::iter::once(
        encode_row_counted_literal_command(64).expect("literal row count should encode"),
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
    .collect::<Vec<_>>();

    let row_repeat_repeated_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_repeated_words,
        256,
    )
    .expect("row-repeat repeated row should simulate");
    let row_counted_repeated_sim = simulate_program(
        &row_counted_program.program,
        row_counted_program.simulator_config,
        &row_counted_repeated_words,
        512,
    )
    .expect("row-counted repeated row should simulate");
    let row_repeat_repeated_observable = extract_gpio_observable_trace(&row_repeat_repeated_sim);
    let row_counted_repeated_observable = extract_gpio_observable_trace(&row_counted_repeated_sim);
    assert_eq!(
        row_repeat_repeated_observable.low_words[..4],
        row_counted_repeated_observable.low_words[..4],
        "the row-counted engine should preserve the shifted low GPIO words for repeated rows",
    );
    assert_eq!(
        row_repeat_repeated_observable.high_words[..4],
        row_counted_repeated_observable.high_words[..4],
        "the row-counted engine should preserve the shifted clock-high GPIO words for repeated rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_repeated_sim),
        extract_pin_transition_sequence(&row_counted_repeated_sim),
        "the row-counted engine should preserve the externally visible GPIO transitions for repeated rows",
    );

    let row_repeat_nonuniform_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_nonuniform_words,
        256,
    )
    .expect("row-repeat nonuniform row should simulate");
    let row_counted_nonuniform_sim = simulate_program(
        &row_counted_program.program,
        row_counted_program.simulator_config,
        &row_counted_nonuniform_words,
        512,
    )
    .expect("row-counted nonuniform row should simulate");
    let row_repeat_nonuniform_observable =
        extract_gpio_observable_trace(&row_repeat_nonuniform_sim);
    let row_counted_nonuniform_observable =
        extract_gpio_observable_trace(&row_counted_nonuniform_sim);
    assert_eq!(
        row_repeat_nonuniform_observable.low_words[..2],
        row_counted_nonuniform_observable.low_words[..2],
        "the row-counted engine should preserve the shifted low GPIO words for nonuniform rows",
    );
    assert_eq!(
        row_repeat_nonuniform_observable.high_words[..2],
        row_counted_nonuniform_observable.high_words[..2],
        "the row-counted engine should preserve the shifted clock-high GPIO words for nonuniform rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_nonuniform_sim),
        extract_pin_transition_sequence(&row_counted_nonuniform_sim),
        "the row-counted engine should preserve the externally visible GPIO transitions for nonuniform rows",
    );

    let row_repeat_quadrant_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_quadrant_words,
        1024,
    )
    .expect("row-repeat quadrant row should simulate");
    let row_counted_quadrant_sim = simulate_program(
        &row_counted_program.program,
        row_counted_program.simulator_config,
        &row_counted_quadrant_words,
        2048,
    )
    .expect("row-counted quadrant row should simulate");
    let row_repeat_quadrant_observable = extract_gpio_observable_trace(&row_repeat_quadrant_sim);
    let row_counted_quadrant_observable =
        extract_gpio_observable_trace(&row_counted_quadrant_sim);
    assert_eq!(
        row_repeat_quadrant_observable.low_words[..64],
        row_counted_quadrant_observable.low_words[..64],
        "the row-counted engine should preserve the shifted low GPIO words for a quadrant row",
    );
    assert_eq!(
        row_repeat_quadrant_observable.high_words[..64],
        row_counted_quadrant_observable.high_words[..64],
        "the row-counted engine should preserve the shifted clock-high GPIO words for a quadrant row",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_quadrant_sim),
        extract_pin_transition_sequence(&row_counted_quadrant_sim),
        "the row-counted engine should preserve the externally visible GPIO transitions for a quadrant row",
    );

    let row_repeat_center_box_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_center_box_words,
        1024,
    )
    .expect("row-repeat center-box row should simulate");
    let row_counted_center_box_sim = simulate_program(
        &row_counted_program.program,
        row_counted_program.simulator_config,
        &row_counted_center_box_words,
        2048,
    )
    .expect("row-counted center-box row should simulate");
    let row_repeat_center_box_observable =
        extract_gpio_observable_trace(&row_repeat_center_box_sim);
    let row_counted_center_box_observable =
        extract_gpio_observable_trace(&row_counted_center_box_sim);
    assert_eq!(
        row_repeat_center_box_observable.low_words[..64],
        row_counted_center_box_observable.low_words[..64],
        "the row-counted engine should preserve the shifted low GPIO words for a center-box row",
    );
    assert_eq!(
        row_repeat_center_box_observable.high_words[..64],
        row_counted_center_box_observable.high_words[..64],
        "the row-counted engine should preserve the shifted clock-high GPIO words for a center-box row",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_center_box_sim),
        extract_pin_transition_sequence(&row_counted_center_box_sim),
        "the row-counted engine should preserve the externally visible GPIO transitions for a center-box row",
    );

    assert!(
        row_counted_repeated_words.len() < row_repeat_repeated_words.len(),
        "the row-counted repeated-row encoding should shrink the payload while preserving parity",
    );
    assert!(
        row_counted_nonuniform_words.len() < row_repeat_nonuniform_words.len(),
        "the row-counted literal-row encoding should shrink dense nonuniform rows while preserving parity",
    );
    assert!(
        row_counted_quadrant_words.len() < row_repeat_quadrant_words.len(),
        "the row-counted quadrant encoding should shrink the payload while preserving parity",
    );
    assert!(
        row_counted_center_box_words.len() < row_repeat_center_box_words.len(),
        "the row-counted center-box encoding should shrink the payload while preserving parity",
    );
}

#[test]
fn piomatter_row_counted_engine_preserves_full_width_center_box_frame_waveform() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_counted_program = piomatter_row_counted_engine_parity_program_info(&config);

    let repeated_row_words = vec![(1_u32 << B1_GPIO) | (1_u32 << OE_GPIO); 64];
    let center_box_dark_word = 1_u32 << OE_GPIO;
    let center_box_white_word = (1_u32 << R1_GPIO)
        | (1_u32 << G1_GPIO)
        | (1_u32 << B1_GPIO)
        | (1_u32 << R2_GPIO)
        | (1_u32 << G2_GPIO)
        | (1_u32 << B2_GPIO)
        | (1_u32 << OE_GPIO);
    let center_box_row_words = std::iter::repeat_n(center_box_dark_word, 24)
        .chain(std::iter::repeat_n(center_box_white_word, 16))
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .collect::<Vec<_>>();

    let mut row_repeat_frame_words = Vec::new();
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &center_box_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        1_u32 << B_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        0,
    );

    let mut row_counted_frame_words = Vec::new();
    row_counted_frame_words.extend([
        encode_row_counted_repeat_command(64).expect("repeat row count should encode"),
        repeated_row_words[0],
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    ]);
    row_counted_frame_words.push(
        encode_row_counted_literal_command(64).expect("literal row count should encode"),
    );
    row_counted_frame_words.extend(center_box_row_words.iter().copied());
    row_counted_frame_words.extend([
        0,
        1_u32 << OE_GPIO,
        0,
        1_u32 << B_GPIO,
    ]);
    row_counted_frame_words.extend([
        encode_row_counted_repeat_command(64).expect("repeat row count should encode"),
        repeated_row_words[0],
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        0,
    ]);

    let row_repeat_frame_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_frame_words,
        8_192,
    )
    .expect("row-repeat frame should simulate");
    let row_counted_frame_sim = simulate_program(
        &row_counted_program.program,
        row_counted_program.simulator_config,
        &row_counted_frame_words,
        8_192,
    )
    .expect("row-counted frame should simulate");

    let row_repeat_frame_observable = extract_gpio_observable_trace(&row_repeat_frame_sim);
    let row_counted_frame_observable = extract_gpio_observable_trace(&row_counted_frame_sim);
    assert_eq!(
        row_repeat_frame_observable.low_words,
        row_counted_frame_observable.low_words,
        "the row-counted engine should preserve every shifted and trailer low GPIO word for full-width center-box rows",
    );
    assert_eq!(
        row_repeat_frame_observable.high_words,
        row_counted_frame_observable.high_words,
        "the row-counted engine should preserve every shifted clock-high GPIO word for full-width center-box rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_frame_sim),
        extract_pin_transition_sequence(&row_counted_frame_sim),
        "the row-counted engine should preserve the externally visible GPIO transitions for full-width center-box rows",
    );
    assert!(
        row_counted_frame_words.len() < row_repeat_frame_words.len(),
        "the row-counted frame encoding should still shrink the payload for full-width center-box rows",
    );
}

#[test]
fn piomatter_row_hybrid_engine_preserves_multi_row_frame_waveform() {
    // Keep the hybrid experiment honest by checking repeat, literal, and split
    // rows in one consecutive frame so row-to-row address and latch transitions
    // stay aligned with the Piomatter row-repeat baseline.
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_hybrid_program = piomatter_row_hybrid_engine_parity_program_info(&config);

    let repeated_row_words = [
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
    ];
    let alternating_row_words = [
        (1_u32 << A_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
    ];
    let split_row_words = [
        (1_u32 << B_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
    ];

    let mut row_repeat_frame_words = Vec::new();
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &alternating_row_words,
        0,
        (1_u32 << A_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << A_GPIO,
        1_u32 << B_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &split_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << B_GPIO,
        0,
    );

    let mut row_hybrid_frame_words = Vec::new();
    extend_row_hybrid_row_words(
        &mut row_hybrid_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_hybrid_row_words(
        &mut row_hybrid_frame_words,
        &alternating_row_words,
        0,
        (1_u32 << A_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << A_GPIO,
        1_u32 << B_GPIO,
    );
    extend_row_hybrid_row_words(
        &mut row_hybrid_frame_words,
        &split_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << B_GPIO,
        0,
    );

    let row_repeat_frame_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_frame_words,
        2_048,
    )
    .expect("row-repeat frame should simulate");
    let row_hybrid_frame_sim = simulate_program(
        &row_hybrid_program.program,
        row_hybrid_program.simulator_config,
        &row_hybrid_frame_words,
        2_048,
    )
    .expect("row-hybrid frame should simulate");

    let row_repeat_frame_observable = extract_gpio_observable_trace(&row_repeat_frame_sim);
    let row_hybrid_frame_observable = extract_gpio_observable_trace(&row_hybrid_frame_sim);
    assert_eq!(
        row_repeat_frame_observable.low_words,
        row_hybrid_frame_observable.low_words,
        "the row-hybrid engine should preserve every shifted and trailer low GPIO word across consecutive rows"
    );
    assert_eq!(
        row_repeat_frame_observable.high_words,
        row_hybrid_frame_observable.high_words,
        "the row-hybrid engine should preserve every shifted clock-high GPIO word across consecutive rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_frame_sim),
        extract_pin_transition_sequence(&row_hybrid_frame_sim),
        "the row-hybrid engine should preserve the externally visible GPIO transitions across consecutive rows"
    );
    assert!(
        row_hybrid_frame_words.len() < row_repeat_frame_words.len(),
        "the row-hybrid frame encoding should shrink the payload while preserving full-frame parity"
    );
}

#[test]
fn piomatter_row_hybrid_engine_preserves_full_width_quadrant_frame_waveform() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_hybrid_program = piomatter_row_hybrid_engine_parity_program_info(&config);

    let repeated_row_words = vec![(1_u32 << B1_GPIO) | (1_u32 << OE_GPIO); 64];
    let left_quadrant_word = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_quadrant_word =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let quadrant_row_words = std::iter::repeat_n(left_quadrant_word, 32)
        .chain(std::iter::repeat_n(right_quadrant_word, 32))
        .collect::<Vec<_>>();

    let mut row_repeat_frame_words = Vec::new();
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &quadrant_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << B_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        0,
    );

    let mut row_hybrid_frame_words = Vec::new();
    extend_row_hybrid_row_words(
        &mut row_hybrid_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_hybrid_row_words(
        &mut row_hybrid_frame_words,
        &quadrant_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << B_GPIO,
    );
    extend_row_hybrid_row_words(
        &mut row_hybrid_frame_words,
        &repeated_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        0,
    );

    let row_repeat_frame_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_frame_words,
        8_192,
    )
    .expect("row-repeat frame should simulate");
    let row_hybrid_frame_sim = simulate_program(
        &row_hybrid_program.program,
        row_hybrid_program.simulator_config,
        &row_hybrid_frame_words,
        8_192,
    )
    .expect("row-hybrid frame should simulate");

    let row_repeat_frame_observable = extract_gpio_observable_trace(&row_repeat_frame_sim);
    let row_hybrid_frame_observable = extract_gpio_observable_trace(&row_hybrid_frame_sim);
    assert_eq!(
        row_repeat_frame_observable.low_words,
        row_hybrid_frame_observable.low_words,
        "the row-hybrid engine should preserve every shifted and trailer low GPIO word for full-width quadrant rows",
    );
    assert_eq!(
        row_repeat_frame_observable.high_words,
        row_hybrid_frame_observable.high_words,
        "the row-hybrid engine should preserve every shifted clock-high GPIO word for full-width quadrant rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_frame_sim),
        extract_pin_transition_sequence(&row_hybrid_frame_sim),
        "the row-hybrid engine should preserve the externally visible GPIO transitions for full-width quadrant rows",
    );
    assert!(
        row_hybrid_frame_words.len() < row_repeat_frame_words.len(),
        "the row-hybrid frame encoding should still shrink the payload for full-width quadrant rows",
    );
}

#[test]
fn piomatter_row_split_engine_preserves_repeated_and_quadrant_rows() {
    // Keep the split-row experiment honest by matching Piomatter's visible GPIO
    // waveform for both full-row repeats and the two-span quadrant case.
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_split_program = piomatter_row_split_engine_parity_program_info(&config);

    let repeated_blue = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let repeated_active = 1_u32 << OE_GPIO;
    let repeated_inactive = 0;
    let row_repeat_repeated_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 3,
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        repeated_active,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        repeated_inactive,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        repeated_inactive,
    ];
    let row_split_repeated_words = [
        encode_row_split_repeat_command(4, true).expect("repeat row count should encode"),
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        repeated_active,
        repeated_inactive,
        repeated_inactive,
    ];
    let repeated_blue_inactive = 1_u32 << B1_GPIO;
    let row_repeat_cutoff_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 3,
        repeated_blue,
        repeated_blue,
        repeated_blue,
        repeated_blue_inactive,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        repeated_active,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        repeated_inactive,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        repeated_inactive,
    ];
    let row_split_cutoff_words = [
        encode_row_split_two_span_command(3, true).expect("split row count should encode"),
        repeated_blue,
        encode_row_engine_count(1, "cutoff second span").expect("second span should encode"),
        repeated_blue_inactive,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        repeated_active,
        repeated_inactive,
        repeated_inactive,
    ];

    let left_word = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_word =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let row_repeat_quadrant_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
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
    let row_split_quadrant_words = [
        encode_row_split_two_span_command(32, true).expect("split row count should encode"),
        left_word,
        encode_row_engine_count(32, "quadrant second span").expect("second span should encode"),
        right_word,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        0,
    ];

    let row_repeat_repeated_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_repeated_words,
        256,
    )
    .expect("row-repeat repeated row should simulate");
    let row_split_repeated_sim = simulate_program(
        &row_split_program.program,
        row_split_program.simulator_config,
        &row_split_repeated_words,
        512,
    )
    .expect("row-split repeated row should simulate");
    let row_repeat_repeated_observable = extract_gpio_observable_trace(&row_repeat_repeated_sim);
    let row_split_repeated_observable = extract_gpio_observable_trace(&row_split_repeated_sim);
    assert_eq!(
        row_repeat_repeated_observable.low_words[..4],
        row_split_repeated_observable.low_words[..4],
        "the row-split engine should preserve the shifted low GPIO words for repeated rows"
    );
    assert_eq!(
        row_repeat_repeated_observable.high_words[..4],
        row_split_repeated_observable.high_words[..4],
        "the row-split engine should preserve the shifted clock-high GPIO words for repeated rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_repeated_sim),
        extract_pin_transition_sequence(&row_split_repeated_sim),
        "the row-split engine should preserve the externally visible GPIO transitions for repeated rows"
    );
    assert!(
        row_split_repeated_words.len() < row_repeat_repeated_words.len(),
        "the row-split repeated-row encoding should shrink the payload while preserving parity"
    );

    let row_repeat_cutoff_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_cutoff_words,
        512,
    )
    .expect("row-repeat cutoff row should simulate");
    let row_split_cutoff_sim = simulate_program(
        &row_split_program.program,
        row_split_program.simulator_config,
        &row_split_cutoff_words,
        512,
    )
    .expect("row-split cutoff row should simulate");
    let row_repeat_cutoff_observable = extract_gpio_observable_trace(&row_repeat_cutoff_sim);
    let row_split_cutoff_observable = extract_gpio_observable_trace(&row_split_cutoff_sim);
    assert_eq!(
        row_repeat_cutoff_observable.low_words[..4],
        row_split_cutoff_observable.low_words[..4],
        "the row-split engine should preserve the shifted low GPIO words when OE changes inside the row"
    );
    assert_eq!(
        row_repeat_cutoff_observable.high_words[..4],
        row_split_cutoff_observable.high_words[..4],
        "the row-split engine should preserve the shifted clock-high GPIO words when OE changes inside the row"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_cutoff_sim),
        extract_pin_transition_sequence(&row_split_cutoff_sim),
        "the row-split engine should preserve the externally visible GPIO transitions when OE changes inside the row"
    );
    assert!(
        row_split_cutoff_words.len() < row_repeat_cutoff_words.len(),
        "the row-split cutoff encoding should shrink the payload while preserving parity"
    );

    let row_repeat_quadrant_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_quadrant_words,
        1024,
    )
    .expect("row-repeat quadrant row should simulate");
    let row_split_quadrant_sim = simulate_program(
        &row_split_program.program,
        row_split_program.simulator_config,
        &row_split_quadrant_words,
        1024,
    )
    .expect("row-split quadrant row should simulate");
    let row_repeat_quadrant_observable = extract_gpio_observable_trace(&row_repeat_quadrant_sim);
    let row_split_quadrant_observable = extract_gpio_observable_trace(&row_split_quadrant_sim);
    assert_eq!(
        row_repeat_quadrant_observable.low_words[..64],
        row_split_quadrant_observable.low_words[..64],
        "the row-split engine should preserve the shifted low GPIO words for a quadrant row"
    );
    assert_eq!(
        row_repeat_quadrant_observable.high_words[..64],
        row_split_quadrant_observable.high_words[..64],
        "the row-split engine should preserve the shifted clock-high GPIO words for a quadrant row"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_quadrant_sim),
        extract_pin_transition_sequence(&row_split_quadrant_sim),
        "the row-split engine should preserve the externally visible GPIO transitions for a quadrant row"
    );
    assert!(
        row_split_quadrant_words.len() < row_repeat_quadrant_words.len(),
        "the row-split quadrant encoding should shrink the payload while preserving the same waveform"
    );
    assert!(
        row_split_quadrant_sim.steps.len() < row_repeat_quadrant_sim.steps.len(),
        "the row-split quadrant path should reduce simulated PIO work by reusing two repeated spans"
    );
}

#[test]
fn piomatter_row_split_engine_preserves_multi_row_frame_waveform() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_split_program = piomatter_row_split_engine_parity_program_info(&config);

    let repeated_row_words = [
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
    ];
    let split_row_words = [
        (1_u32 << B_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
    ];
    let second_repeated_row_words = [
        (1_u32 << A_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << OE_GPIO),
    ];

    let mut row_repeat_frame_words = Vec::new();
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &split_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << B_GPIO,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &second_repeated_row_words,
        0,
        (1_u32 << A_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << A_GPIO,
        0,
    );

    let mut row_split_frame_words = Vec::new();
    extend_row_split_row_words(
        &mut row_split_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_split_row_words(
        &mut row_split_frame_words,
        &split_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << B_GPIO,
        1_u32 << A_GPIO,
    );
    extend_row_split_row_words(
        &mut row_split_frame_words,
        &second_repeated_row_words,
        0,
        (1_u32 << A_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << A_GPIO,
        0,
    );

    let row_repeat_frame_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_frame_words,
        2_048,
    )
    .expect("row-repeat frame should simulate");
    let row_split_frame_sim = simulate_program(
        &row_split_program.program,
        row_split_program.simulator_config,
        &row_split_frame_words,
        2_048,
    )
    .expect("row-split frame should simulate");

    let row_repeat_frame_observable = extract_gpio_observable_trace(&row_repeat_frame_sim);
    let row_split_frame_observable = extract_gpio_observable_trace(&row_split_frame_sim);
    assert_eq!(
        row_repeat_frame_observable.low_words,
        row_split_frame_observable.low_words,
        "the row-split engine should preserve every shifted and trailer low GPIO word across consecutive rows",
    );
    assert_eq!(
        row_repeat_frame_observable.high_words,
        row_split_frame_observable.high_words,
        "the row-split engine should preserve every shifted clock-high GPIO word across consecutive rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_frame_sim),
        extract_pin_transition_sequence(&row_split_frame_sim),
        "the row-split engine should preserve the externally visible GPIO transitions across consecutive rows",
    );
    assert!(
        row_split_frame_words.len() < row_repeat_frame_words.len(),
        "the row-split frame encoding should shrink the payload while preserving full-frame parity",
    );
}

#[test]
fn piomatter_row_split_engine_preserves_full_width_quadrant_frame_waveform() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_split_program = piomatter_row_split_engine_parity_program_info(&config);

    let repeated_row_words = vec![(1_u32 << B1_GPIO) | (1_u32 << OE_GPIO); 64];
    let left_quadrant_word = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_quadrant_word =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let quadrant_row_words = std::iter::repeat_n(left_quadrant_word, 32)
        .chain(std::iter::repeat_n(right_quadrant_word, 32))
        .collect::<Vec<_>>();

    let mut row_repeat_frame_words = Vec::new();
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &quadrant_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << B_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        0,
    );

    let mut row_split_frame_words = Vec::new();
    extend_row_split_row_words(
        &mut row_split_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_split_row_words(
        &mut row_split_frame_words,
        &quadrant_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << B_GPIO,
    );
    extend_row_split_row_words(
        &mut row_split_frame_words,
        &repeated_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        0,
    );

    let row_repeat_frame_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_frame_words,
        8_192,
    )
    .expect("row-repeat frame should simulate");
    let row_split_frame_sim = simulate_program(
        &row_split_program.program,
        row_split_program.simulator_config,
        &row_split_frame_words,
        8_192,
    )
    .expect("row-split frame should simulate");

    let row_repeat_frame_observable = extract_gpio_observable_trace(&row_repeat_frame_sim);
    let row_split_frame_observable = extract_gpio_observable_trace(&row_split_frame_sim);
    assert_eq!(
        row_repeat_frame_observable.low_words,
        row_split_frame_observable.low_words,
        "the row-split engine should preserve every shifted and trailer low GPIO word for full-width quadrant rows",
    );
    assert_eq!(
        row_repeat_frame_observable.high_words,
        row_split_frame_observable.high_words,
        "the row-split engine should preserve every shifted clock-high GPIO word for full-width quadrant rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_frame_sim),
        extract_pin_transition_sequence(&row_split_frame_sim),
        "the row-split engine should preserve the externally visible GPIO transitions for full-width quadrant rows",
    );
    assert!(
        row_split_frame_words.len() < row_repeat_frame_words.len(),
        "the row-split frame encoding should still shrink the payload for full-width quadrant rows",
    );
    assert!(
        row_split_frame_sim.steps.len() < row_repeat_frame_sim.steps.len(),
        "the row-split full-width quadrant frame should reduce simulated PIO work by reusing two repeated spans",
    );
}

#[test]
fn piomatter_row_runs_engine_preserves_repeated_quadrant_and_center_box_rows() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_runs_program = piomatter_row_runs_engine_parity_program_info(&config);

    let repeated_blue = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let repeated_active = 1_u32 << OE_GPIO;
    let repeated_inactive = 0;
    let row_repeat_repeated_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 3,
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        repeated_active,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        repeated_inactive,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        repeated_inactive,
    ];
    let row_runs_repeated_words = [
        encode_row_runs_command(
            4,
            0,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("runs row count should encode"),
        repeated_blue,
        repeated_active,
        repeated_inactive,
        repeated_inactive,
    ];

    let left_word = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_word =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let row_repeat_quadrant_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
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
    let row_runs_quadrant_words = [
        encode_row_runs_command(
            32,
            1,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("runs first span count should encode"),
        left_word,
        encode_row_engine_count(32, "second span count").expect("second span count should encode"),
        right_word,
        1_u32 << OE_GPIO,
        0,
        0,
    ];

    let center_box_dark_word = 1_u32 << OE_GPIO;
    let center_box_white_word = (1_u32 << R1_GPIO)
        | (1_u32 << G1_GPIO)
        | (1_u32 << B1_GPIO)
        | (1_u32 << R2_GPIO)
        | (1_u32 << G2_GPIO)
        | (1_u32 << B2_GPIO)
        | (1_u32 << OE_GPIO);
    let row_repeat_center_box_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
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
    let row_runs_center_box_words = [
        encode_row_runs_command(
            24,
            2,
            encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        )
        .expect("runs center-box command should encode"),
        center_box_dark_word,
        encode_row_engine_count(16, "center-box second span count")
            .expect("center-box second span count should encode"),
        center_box_white_word,
        encode_row_engine_count(24, "center-box third span count")
            .expect("center-box third span count should encode"),
        center_box_dark_word,
        1_u32 << OE_GPIO,
        0,
        0,
    ];

    let row_repeat_repeated_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_repeated_words,
        256,
    )
    .expect("row-repeat repeated row should simulate");
    let row_runs_repeated_sim = simulate_program(
        &row_runs_program.program,
        row_runs_program.simulator_config,
        &row_runs_repeated_words,
        512,
    )
    .expect("row-runs repeated row should simulate");
    let row_repeat_repeated_observable = extract_gpio_observable_trace(&row_repeat_repeated_sim);
    let row_runs_repeated_observable = extract_gpio_observable_trace(&row_runs_repeated_sim);
    assert_eq!(
        row_repeat_repeated_observable.low_words[..4],
        row_runs_repeated_observable.low_words[..4],
        "the row-runs engine should preserve the shifted low GPIO words for repeated rows"
    );
    assert_eq!(
        row_repeat_repeated_observable.high_words[..4],
        row_runs_repeated_observable.high_words[..4],
        "the row-runs engine should preserve the shifted clock-high GPIO words for repeated rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_repeated_sim),
        extract_pin_transition_sequence(&row_runs_repeated_sim),
        "the row-runs engine should preserve the externally visible GPIO transitions for repeated rows"
    );

    let row_repeat_quadrant_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_quadrant_words,
        1024,
    )
    .expect("row-repeat quadrant row should simulate");
    let row_runs_quadrant_sim = simulate_program(
        &row_runs_program.program,
        row_runs_program.simulator_config,
        &row_runs_quadrant_words,
        1024,
    )
    .expect("row-runs quadrant row should simulate");
    let row_repeat_quadrant_observable = extract_gpio_observable_trace(&row_repeat_quadrant_sim);
    let row_runs_quadrant_observable = extract_gpio_observable_trace(&row_runs_quadrant_sim);
    assert_eq!(
        row_repeat_quadrant_observable.low_words[..64],
        row_runs_quadrant_observable.low_words[..64],
        "the row-runs engine should preserve the shifted low GPIO words for a quadrant row"
    );
    assert_eq!(
        row_repeat_quadrant_observable.high_words[..64],
        row_runs_quadrant_observable.high_words[..64],
        "the row-runs engine should preserve the shifted clock-high GPIO words for a quadrant row"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_quadrant_sim),
        extract_pin_transition_sequence(&row_runs_quadrant_sim),
        "the row-runs engine should preserve the externally visible GPIO transitions for a quadrant row"
    );

    let row_repeat_center_box_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_center_box_words,
        1024,
    )
    .expect("row-repeat center-box row should simulate");
    let row_runs_center_box_sim = simulate_program(
        &row_runs_program.program,
        row_runs_program.simulator_config,
        &row_runs_center_box_words,
        1024,
    )
    .expect("row-runs center-box row should simulate");
    let row_repeat_center_box_observable =
        extract_gpio_observable_trace(&row_repeat_center_box_sim);
    let row_runs_center_box_observable =
        extract_gpio_observable_trace(&row_runs_center_box_sim);
    assert_eq!(
        row_repeat_center_box_observable.low_words[..64],
        row_runs_center_box_observable.low_words[..64],
        "the row-runs engine should preserve the shifted low GPIO words for a center-box row"
    );
    assert_eq!(
        row_repeat_center_box_observable.high_words[..64],
        row_runs_center_box_observable.high_words[..64],
        "the row-runs engine should preserve the shifted clock-high GPIO words for a center-box row"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_center_box_sim),
        extract_pin_transition_sequence(&row_runs_center_box_sim),
        "the row-runs engine should preserve the externally visible GPIO transitions for a center-box row"
    );

    assert!(
        row_runs_repeated_words.len() < row_repeat_repeated_words.len(),
        "the row-runs repeated-row encoding should shrink the payload while preserving parity"
    );
    assert!(
        row_runs_quadrant_words.len() < row_repeat_quadrant_words.len(),
        "the row-runs quadrant encoding should shrink the payload while preserving parity"
    );
    assert!(
        row_runs_center_box_words.len() < row_repeat_center_box_words.len(),
        "the row-runs center-box encoding should shrink the payload while preserving parity"
    );
}

#[test]
fn piomatter_row_runs_engine_preserves_multi_row_frame_waveform() {
    // Keep the row-runs experiment honest by checking consecutive repeated,
    // two-span, and three-span rows so row-to-row control phases stay aligned
    // with the Piomatter row-repeat baseline.
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_runs_program = piomatter_row_runs_engine_parity_program_info(&config);

    let repeated_row_words = [
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
    ];
    let split_row_words = [
        (1_u32 << A_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
    ];
    let center_box_row_words = [
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
    ];

    let mut row_repeat_frame_words = Vec::new();
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &split_row_words,
        0,
        (1_u32 << A_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << A_GPIO,
        1_u32 << B_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &center_box_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << B_GPIO,
        0,
    );

    let mut row_runs_frame_words = Vec::new();
    extend_row_runs_row_words(
        &mut row_runs_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_runs_row_words(
        &mut row_runs_frame_words,
        &split_row_words,
        0,
        (1_u32 << A_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << A_GPIO,
        1_u32 << B_GPIO,
    );
    extend_row_runs_row_words(
        &mut row_runs_frame_words,
        &center_box_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << B_GPIO,
        0,
    );

    let row_repeat_frame_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_frame_words,
        2_048,
    )
    .expect("row-repeat frame should simulate");
    let row_runs_frame_sim = simulate_program(
        &row_runs_program.program,
        row_runs_program.simulator_config,
        &row_runs_frame_words,
        2_048,
    )
    .expect("row-runs frame should simulate");

    let row_repeat_frame_observable = extract_gpio_observable_trace(&row_repeat_frame_sim);
    let row_runs_frame_observable = extract_gpio_observable_trace(&row_runs_frame_sim);
    assert_eq!(
        row_repeat_frame_observable.low_words,
        row_runs_frame_observable.low_words,
        "the row-runs engine should preserve every shifted and trailer low GPIO word across consecutive rows"
    );
    assert_eq!(
        row_repeat_frame_observable.high_words,
        row_runs_frame_observable.high_words,
        "the row-runs engine should preserve every shifted clock-high GPIO word across consecutive rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_frame_sim),
        extract_pin_transition_sequence(&row_runs_frame_sim),
        "the row-runs engine should preserve the externally visible GPIO transitions across consecutive rows"
    );
    assert!(
        row_runs_frame_words.len() < row_repeat_frame_words.len(),
        "the row-runs frame encoding should shrink the payload while preserving full-frame parity"
    );
}

#[test]
fn piomatter_row_window_engine_preserves_repeated_and_center_box_rows() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_window_program = piomatter_row_window_engine_parity_program_info(&config);

    let repeated_blue = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let repeated_active = 1_u32 << OE_GPIO;
    let repeated_inactive = 0;
    let row_repeat_repeated_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 3,
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        repeated_active,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        repeated_inactive,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        repeated_inactive,
    ];
    let row_window_repeated_words = [
        encode_row_window_repeat_command(4).expect("window repeat row should encode"),
        repeated_blue,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        repeated_active,
        repeated_inactive,
        repeated_inactive,
    ];

    let center_box_dark_word = 1_u32 << OE_GPIO;
    let center_box_white_word = (1_u32 << R1_GPIO)
        | (1_u32 << G1_GPIO)
        | (1_u32 << B1_GPIO)
        | (1_u32 << R2_GPIO)
        | (1_u32 << G2_GPIO)
        | (1_u32 << B2_GPIO)
        | (1_u32 << OE_GPIO);
    let row_repeat_center_box_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
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
    let row_window_center_box_words = [
        encode_row_window_window_command(24).expect("window first edge span should encode"),
        center_box_dark_word,
        encode_row_engine_count(16, "window middle span count")
            .expect("window middle span count should encode"),
        center_box_white_word,
        encode_row_engine_count(24, "window tail span count")
            .expect("window tail span count should encode"),
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        0,
    ];

    let row_repeat_repeated_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_repeated_words,
        256,
    )
    .expect("row-repeat repeated row should simulate");
    let row_window_repeated_sim = simulate_program(
        &row_window_program.program,
        row_window_program.simulator_config,
        &row_window_repeated_words,
        512,
    )
    .expect("row-window repeated row should simulate");
    let row_repeat_repeated_observable = extract_gpio_observable_trace(&row_repeat_repeated_sim);
    let row_window_repeated_observable = extract_gpio_observable_trace(&row_window_repeated_sim);
    assert_eq!(
        row_repeat_repeated_observable.low_words[..4],
        row_window_repeated_observable.low_words[..4],
        "the row-window engine should preserve the shifted low GPIO words for repeated rows"
    );
    assert_eq!(
        row_repeat_repeated_observable.high_words[..4],
        row_window_repeated_observable.high_words[..4],
        "the row-window engine should preserve the shifted clock-high GPIO words for repeated rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_repeated_sim),
        extract_pin_transition_sequence(&row_window_repeated_sim),
        "the row-window engine should preserve the externally visible GPIO transitions for repeated rows"
    );

    let row_repeat_center_box_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_center_box_words,
        1024,
    )
    .expect("row-repeat center-box row should simulate");
    let row_window_center_box_sim = simulate_program(
        &row_window_program.program,
        row_window_program.simulator_config,
        &row_window_center_box_words,
        1024,
    )
    .expect("row-window center-box row should simulate");
    let row_repeat_center_box_observable =
        extract_gpio_observable_trace(&row_repeat_center_box_sim);
    let row_window_center_box_observable =
        extract_gpio_observable_trace(&row_window_center_box_sim);
    assert_eq!(
        row_repeat_center_box_observable.low_words[..64],
        row_window_center_box_observable.low_words[..64],
        "the row-window engine should preserve the shifted low GPIO words for a center-box row"
    );
    assert_eq!(
        row_repeat_center_box_observable.high_words[..64],
        row_window_center_box_observable.high_words[..64],
        "the row-window engine should preserve the shifted clock-high GPIO words for a center-box row"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_center_box_sim),
        extract_pin_transition_sequence(&row_window_center_box_sim),
        "the row-window engine should preserve the externally visible GPIO transitions for a center-box row"
    );

    assert!(
        row_window_repeated_words.len() < row_repeat_repeated_words.len(),
        "the row-window repeated-row encoding should shrink the payload while preserving parity"
    );
    assert!(
        row_window_center_box_words.len() < row_repeat_center_box_words.len(),
        "the row-window center-box encoding should shrink the payload while preserving parity"
    );
}

#[test]
fn piomatter_row_window_engine_preserves_multi_row_frame_waveform() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_window_program = piomatter_row_window_engine_parity_program_info(&config);

    let repeated_row_words = [
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO),
    ];
    let center_box_row_words = [
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
    ];
    let literal_row_words = [
        (1_u32 << A_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << R1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
        (1_u32 << A_GPIO) | (1_u32 << G1_GPIO) | (1_u32 << OE_GPIO),
    ];

    let mut row_repeat_frame_words = Vec::new();
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &center_box_row_words,
        0,
        (1_u32 << A_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << A_GPIO,
        1_u32 << B_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &literal_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << B_GPIO,
        0,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );

    let mut row_window_frame_words = Vec::new();
    extend_row_window_row_words(
        &mut row_window_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_window_row_words(
        &mut row_window_frame_words,
        &center_box_row_words,
        0,
        (1_u32 << A_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << A_GPIO,
        1_u32 << B_GPIO,
    );
    extend_row_window_row_words(
        &mut row_window_frame_words,
        &literal_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        (1_u32 << B_GPIO) | (1_u32 << OE_GPIO),
        1_u32 << B_GPIO,
        0,
    );
    extend_row_window_row_words(
        &mut row_window_frame_words,
        &repeated_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );

    let row_repeat_frame_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_frame_words,
        2_048,
    )
    .expect("row-repeat frame should simulate");
    let row_window_frame_sim = simulate_program(
        &row_window_program.program,
        row_window_program.simulator_config,
        &row_window_frame_words,
        2_048,
    )
    .expect("row-window frame should simulate");

    let row_repeat_frame_observable = extract_gpio_observable_trace(&row_repeat_frame_sim);
    let row_window_frame_observable = extract_gpio_observable_trace(&row_window_frame_sim);
    assert_eq!(
        row_repeat_frame_observable.low_words,
        row_window_frame_observable.low_words,
        "the row-window engine should preserve every shifted and trailer low GPIO word across consecutive rows"
    );
    assert_eq!(
        row_repeat_frame_observable.high_words,
        row_window_frame_observable.high_words,
        "the row-window engine should preserve every shifted clock-high GPIO word across consecutive rows"
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_frame_sim),
        extract_pin_transition_sequence(&row_window_frame_sim),
        "the row-window engine should preserve the externally visible GPIO transitions across consecutive rows"
    );
    assert!(
        row_window_frame_words.len() < row_repeat_frame_words.len(),
        "the row-window frame encoding should shrink the payload while preserving full-frame parity"
    );
}

#[test]
fn piomatter_row_window_engine_preserves_full_width_center_box_frame_waveform() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let row_window_program = piomatter_row_window_engine_parity_program_info(&config);

    let repeated_row_words = vec![(1_u32 << B1_GPIO) | (1_u32 << OE_GPIO); 64];
    let center_box_dark_word = 1_u32 << OE_GPIO;
    let center_box_white_word = (1_u32 << R1_GPIO)
        | (1_u32 << G1_GPIO)
        | (1_u32 << B1_GPIO)
        | (1_u32 << R2_GPIO)
        | (1_u32 << G2_GPIO)
        | (1_u32 << B2_GPIO)
        | (1_u32 << OE_GPIO);
    let center_box_row_words = std::iter::repeat_n(center_box_dark_word, 24)
        .chain(std::iter::repeat_n(center_box_white_word, 16))
        .chain(std::iter::repeat_n(center_box_dark_word, 24))
        .collect::<Vec<_>>();

    let mut row_repeat_frame_words = Vec::new();
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &center_box_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        1_u32 << B_GPIO,
    );
    extend_row_repeat_row_words(
        &mut row_repeat_frame_words,
        &repeated_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        0,
    );

    let mut row_window_frame_words = Vec::new();
    extend_row_window_row_words(
        &mut row_window_frame_words,
        &repeated_row_words,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        1_u32 << A_GPIO,
    );
    extend_row_window_row_words(
        &mut row_window_frame_words,
        &center_box_row_words,
        0,
        1_u32 << OE_GPIO,
        0,
        1_u32 << B_GPIO,
    );
    extend_row_window_row_words(
        &mut row_window_frame_words,
        &repeated_row_words,
        encode_row_engine_count(2, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        0,
        0,
    );

    let row_repeat_frame_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_frame_words,
        8_192,
    )
    .expect("row-repeat frame should simulate");
    let row_window_frame_sim = simulate_program(
        &row_window_program.program,
        row_window_program.simulator_config,
        &row_window_frame_words,
        8_192,
    )
    .expect("row-window frame should simulate");

    let row_repeat_frame_observable = extract_gpio_observable_trace(&row_repeat_frame_sim);
    let row_window_frame_observable = extract_gpio_observable_trace(&row_window_frame_sim);
    assert_eq!(
        row_repeat_frame_observable.low_words,
        row_window_frame_observable.low_words,
        "the row-window engine should preserve every shifted and trailer low GPIO word for full-width center-box rows",
    );
    assert_eq!(
        row_repeat_frame_observable.high_words,
        row_window_frame_observable.high_words,
        "the row-window engine should preserve every shifted clock-high GPIO word for full-width center-box rows",
    );
    assert_eq!(
        extract_pin_transition_sequence(&row_repeat_frame_sim),
        extract_pin_transition_sequence(&row_window_frame_sim),
        "the row-window engine should preserve the externally visible GPIO transitions for full-width center-box rows",
    );
    assert!(
        row_window_frame_words.len() < row_repeat_frame_words.len(),
        "the row-window frame encoding should still shrink the payload for full-width center-box rows",
    );
}

#[test]
fn piomatter_symbol_command_engine_preserves_repeated_and_quadrant_row_waveforms() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 config should be valid");
    let row_repeat_program = piomatter_row_repeat_engine_parity_program_info(&config);
    let symbol_program = piomatter_symbol_command_parity_program_info(&config);

    let repeated_blue_word = (1_u32 << B1_GPIO) | (1_u32 << OE_GPIO);
    let repeated_blue_symbol = semantic_symbol(SEMANTIC_B1_BIT);
    let repeated_shift_control = semantic_control_word(SEMANTIC_OE_BIT);
    let repeated_active_control = semantic_control_word(SEMANTIC_OE_BIT);
    let repeated_inactive_control = semantic_control_word(0);
    let repeated_latch_control = semantic_control_word(SEMANTIC_LAT_BIT);
    let repeated_next_control = semantic_control_word(0);

    let row_repeat_repeated_words = [
        PIOMATTER_ROW_REPEAT_COMMAND_REPEAT | 3,
        repeated_blue_word,
        encode_row_engine_count(3, "active hold").expect("active hold should encode"),
        1_u32 << OE_GPIO,
        encode_row_engine_count(2, "inactive hold").expect("inactive hold should encode"),
        0,
        encode_row_engine_count(4, "latch hold").expect("latch hold should encode"),
        encode_row_engine_count(2, "next-address hold").expect("next-address hold should encode"),
        0,
    ];
    let symbol_repeated_words = [
        encode_symbol_repeat_command(4).expect("symbol repeat command should encode"),
        pack_control_prefixed_rgb_lane_symbols(repeated_shift_control, &[repeated_blue_symbol])[0],
        encode_symbol_delay_command(3).expect("active hold should encode"),
        repeated_active_control,
        encode_symbol_delay_command(2).expect("inactive hold should encode"),
        repeated_inactive_control,
        encode_symbol_delay_command(4).expect("latch hold should encode"),
        repeated_latch_control,
        encode_symbol_delay_command(2).expect("next hold should encode"),
        repeated_next_control,
    ];

    let left_actual = (1_u32 << R1_GPIO) | (1_u32 << B2_GPIO) | (1_u32 << OE_GPIO);
    let right_actual =
        (1_u32 << G1_GPIO) | (1_u32 << R2_GPIO) | (1_u32 << G2_GPIO) | (1_u32 << B2_GPIO)
            | (1_u32 << OE_GPIO);
    let left_symbol = semantic_symbol(SEMANTIC_R1_BIT | SEMANTIC_B2_BIT);
    let right_symbol = semantic_symbol(
        SEMANTIC_G1_BIT | SEMANTIC_R2_BIT | SEMANTIC_G2_BIT | SEMANTIC_B2_BIT,
    );
    let quadrant_shift_control = semantic_control_word(SEMANTIC_OE_BIT);
    let quadrant_active_control = semantic_control_word(SEMANTIC_OE_BIT);
    let quadrant_inactive_control = semantic_control_word(0);
    let quadrant_latch_control = semantic_control_word(SEMANTIC_LAT_BIT);
    let quadrant_next_control = semantic_control_word(0);

    let row_repeat_quadrant_words = std::iter::once(PIOMATTER_ROW_REPEAT_COMMAND_LITERAL | 63)
        .chain(std::iter::repeat_n(left_actual, 32))
        .chain(std::iter::repeat_n(right_actual, 32))
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
    let mut symbol_quadrant_words = vec![
        encode_symbol_literal_command(64).expect("symbol literal command should encode"),
    ];
    let quadrant_symbols = std::iter::repeat_n(left_symbol, 32)
        .chain(std::iter::repeat_n(right_symbol, 32))
        .collect::<Vec<_>>();
    symbol_quadrant_words.extend(pack_control_prefixed_rgb_lane_symbols(
        quadrant_shift_control,
        &quadrant_symbols,
    ));
    symbol_quadrant_words.extend_from_slice(&[
        encode_symbol_delay_command(3).expect("active hold should encode"),
        quadrant_active_control,
        encode_symbol_delay_command(2).expect("inactive hold should encode"),
        quadrant_inactive_control,
        encode_symbol_delay_command(4).expect("latch hold should encode"),
        quadrant_latch_control,
        encode_symbol_delay_command(2).expect("next hold should encode"),
        quadrant_next_control,
    ]);

    let row_repeat_repeated_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_repeated_words,
        256,
    )
    .expect("row-repeat repeated row should simulate");
    let symbol_repeated_sim = simulate_program(
        &symbol_program.program,
        symbol_program.simulator_config,
        &symbol_repeated_words,
        256,
    )
    .expect("symbol repeated row should simulate");
    assert_eq!(
        decode_symbol_command(symbol_repeated_words[0]).expect("symbol command should decode"),
        (SymbolCommandKind::Repeat, 4),
        "the symbol prototype should exercise the repeat command path"
    );
    let row_repeat_repeated_observable = extract_gpio_observable_trace(&row_repeat_repeated_sim);
    let symbol_repeated_shift_observable =
        extract_mapped_out_pins_count_observable_trace(&symbol_repeated_sim, 6);
    assert_eq!(
        row_repeat_repeated_observable.low_words[..4],
        symbol_repeated_shift_observable.low_words,
        "the symbol-command prototype should preserve the shifted low GPIO words for repeated rows"
    );
    assert_eq!(
        row_repeat_repeated_observable.high_words,
        symbol_repeated_shift_observable.high_words,
        "the symbol-command prototype should preserve the shifted clock-high GPIO words for repeated rows"
    );

    let row_repeat_quadrant_sim = simulate_program(
        &row_repeat_program.program,
        row_repeat_program.simulator_config,
        &row_repeat_quadrant_words,
        1024,
    )
    .expect("row-repeat quadrant row should simulate");
    let symbol_quadrant_sim = simulate_program(
        &symbol_program.program,
        symbol_program.simulator_config,
        &symbol_quadrant_words,
        1024,
    )
    .expect("symbol quadrant row should simulate");
    assert_eq!(
        decode_symbol_command(symbol_quadrant_words[0]).expect("symbol command should decode"),
        (SymbolCommandKind::Literal, 64),
        "the symbol prototype should exercise the packed literal path"
    );
    let row_repeat_quadrant_observable = extract_gpio_observable_trace(&row_repeat_quadrant_sim);
    let symbol_quadrant_shift_observable =
        extract_mapped_out_pins_count_observable_trace(&symbol_quadrant_sim, 6);
    assert_eq!(
        row_repeat_quadrant_observable.low_words[..64],
        symbol_quadrant_shift_observable.low_words[..64],
        "the symbol-command prototype should preserve the shifted low GPIO words for a quadrant row"
    );
    assert_eq!(
        row_repeat_quadrant_observable.high_words[..64],
        symbol_quadrant_shift_observable.high_words[..64],
        "the symbol-command prototype should preserve the shifted clock-high GPIO words for a quadrant row"
    );
}

#[test]
fn pi5_simple_native_submit_uses_literal_gpio_words_directly() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = solid_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0, 0, 255);
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let parsed = parse_simple_group(&words, config.width().expect("width should resolve") as usize);

    assert_eq!(
        parsed.blank_command,
        parsed.blank_command,
        "blank delay commands should already be native-ready"
    );
    assert_eq!(
        parsed.blank_word,
        parsed.blank_word & SIMPLE_PIN_WORD_MASK,
        "blank GPIO words should already occupy their real GPIO bit positions"
    );
    assert_eq!(
        parsed
            .shift_commands
            .iter()
            .map(|command| command.command_word)
            .collect::<Vec<_>>(),
        parsed
            .shift_commands
            .iter()
            .map(|command| command.command_word)
            .collect::<Vec<_>>(),
        "shift command words should already be native-ready"
    );
    assert_eq!(
        parsed.shift_words,
        parsed
            .shift_words
            .iter()
            .map(|word| *word & SIMPLE_PIN_WORD_MASK)
            .collect::<Vec<_>>(),
        "literal shift words should already target the real GPIO window"
    );
    assert_eq!(
        parsed.latch_word,
        parsed.latch_word & SIMPLE_PIN_WORD_MASK,
        "the latch-high GPIO word should already target the real GPIO window"
    );
    assert_eq!(
        parsed.post_latch_word,
        parsed.post_latch_word & SIMPLE_PIN_WORD_MASK,
        "the post-latch GPIO word should already target the real GPIO window"
    );
    assert_eq!(
        parsed.active_command,
        parsed.active_command,
        "the dwell command should already be native-ready"
    );
    assert_eq!(
        parsed.active_word,
        parsed.active_word & SIMPLE_PIN_WORD_MASK,
        "the active GPIO word should already target the real GPIO window"
    );
}

#[test]
fn pi5_simple_pio_emulator_pulses_clock_per_column_and_latch_once() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = row_bars_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0);
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let simulated = simulate_simple_hub75_group(&config, &words)
        .expect("simple PIO emulator should execute the group");
    let width = config.width().expect("width should resolve") as usize;
    let clock_high_steps = simple_shift_high_steps(&simulated)
        .into_iter()
        .filter(|step| gpio_is_high(step.pins, CLK_GPIO))
        .count();
    let latch_high_steps = simple_delay_output_steps(&simulated)
        .into_iter()
        .filter(|step| gpio_is_high(step.pins, LAT_GPIO))
        .count();

    assert_eq!(
        clock_high_steps, width,
        "the row engine should generate one clock-high phase per streamed column word"
    );
    assert_eq!(
        latch_high_steps, 1,
        "the row engine should generate exactly one latch pulse per group"
    );
}

#[test]
fn pi5_simple_pio_emulator_outputs_column_words_without_osr_phase_drift() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = row_bars_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0);
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let parsed = parse_simple_group(&words, config.width().expect("width should resolve") as usize);
    let simulated = simulate_simple_hub75_group(&config, &words)
        .expect("simple PIO emulator should execute the group");
    let emitted_shift_words = simple_shift_low_steps(&simulated)
        .into_iter()
        .map(|step| pins_to_pin_word(step.pins))
        .collect::<Vec<_>>();

    assert_eq!(
        emitted_shift_words, parsed.shift_words,
        "each explicit pull/out pair should emit exactly one source column word with no leftover-bit drift"
    );
}

#[test]
fn pi5_simple_pio_emulator_matches_expected_gpio_values_across_row_phases() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = row_bars_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0);
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let width = config.width().expect("width should resolve") as usize;
    let parsed = parse_simple_group(&words, width);
    let simulated = simulate_simple_hub75_group(&config, &words)
        .expect("simple PIO emulator should execute the group");
    let clock_bit = 1_u32 << (CLK_GPIO - PIN_WORD_BASE_GPIO);
    let lat_bit = 1_u32 << (LAT_GPIO - PIN_WORD_BASE_GPIO);
    let delay_output_steps = simple_delay_output_steps(&simulated);
    let shift_low_steps = simple_shift_low_steps(&simulated);
    let shift_high_steps = simple_shift_high_steps(&simulated);
    let dwell_step = simulated
        .steps
        .iter()
        .filter(|step| step.pc == 6)
        .last()
        .expect("program should execute the dwell loop");
    let blank_step = delay_output_steps
        .first()
        .expect("program should apply the blank word");
    let latch_high_step = delay_output_steps
        .get(1)
        .expect("program should apply the latch-high word");
    let post_latch_step = delay_output_steps
        .get(2)
        .expect("program should apply the post-latch word");
    let active_step = delay_output_steps
        .last()
        .expect("program should apply the active row word");

    assert_eq!(
        pins_to_pin_word(blank_step.pins),
        parsed.blank_word,
        "blank phase should drive the exact blank/address word"
    );
    assert_eq!(
        shift_low_steps.len(),
        width,
        "program should emit one clock-low shift step per column"
    );
    assert_eq!(
        shift_high_steps.len(),
        width,
        "program should emit one clock-high shift step per column"
    );

    for ((expected_word, low_step), high_step) in parsed
        .shift_words
        .iter()
        .zip(shift_low_steps.iter())
        .zip(shift_high_steps.iter())
    {
        assert_eq!(
            pins_to_pin_word(low_step.pins),
            *expected_word,
            "clock-low phase should drive the source column word verbatim"
        );
        assert_eq!(
            pins_to_pin_word(high_step.pins),
            *expected_word | clock_bit,
            "clock-high phase should only add the clock bit to the source column word"
        );
    }

    assert_eq!(
        pins_to_pin_word(latch_high_step.pins),
        parsed.latch_word,
        "latch-high phase should drive the explicit latch-high GPIO word"
    );
    assert_eq!(
        pins_to_pin_word(post_latch_step.pins),
        parsed.post_latch_word,
        "post-latch phase should restore the explicit post-latch GPIO word"
    );
    assert_eq!(
        pins_to_pin_word(active_step.pins),
        parsed.active_word,
        "active phase should drive the explicit active/address word"
    );
    assert_eq!(
        pins_to_pin_word(dwell_step.pins),
        parsed.active_word,
        "dwell loop should keep the active/address word stable"
    );
    assert_eq!(
        parsed.latch_word & lat_bit,
        lat_bit,
        "the explicit latch word should raise LAT in-band"
    );
}

#[test]
fn pi5_simple_pio_emulator_drives_each_rgb_lane_as_expected() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(1))
        .and_then(|config| config.with_format(Pi5ScanFormat::Simple))
        .expect("single-panel Pi 5 simple config should be valid");
    let frame = rgb_lane_pattern_rgba_frame(config.width().unwrap(), config.height().unwrap(), 0);
    let words = build_simple_group_words_for_rgba(&config, &frame, 0, 0)
        .expect("simple group words should build");
    let simulated = simulate_simple_hub75_group(&config, &words)
        .expect("simple PIO emulator should execute the group");
    let expected = expected_group_output_from_rgba(&config, &frame, 0);
    let shift_low_steps = simple_shift_low_steps(&simulated);
    let shift_high_steps = simple_shift_high_steps(&simulated);

    for (column, ((expected_column, low_step), high_step)) in expected
        .columns
        .iter()
        .zip(shift_low_steps.iter())
        .zip(shift_high_steps.iter())
        .enumerate()
    {
        assert_rgb_pins_match_column(low_step.pins, expected_column, "clock-low", column);
        assert_rgb_pins_match_column(high_step.pins, expected_column, "clock-high", column);
    }
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

fn position_pattern_rgba_frame(width: u32, height: u32) -> Vec<u8> {
    let width = width as usize;
    let height = height as usize;
    let mut frame = vec![0_u8; width * height * 4];

    for row in 0..height {
        for column in 0..width {
            let offset = ((row * width) + column) * 4;
            frame[offset] = if ((row ^ column) & 0x01) != 0 { 255 } else { 0 };
            frame[offset + 1] = if (((row >> 1) ^ (column >> 1)) & 0x01) != 0 {
                255
            } else {
                0
            };
            frame[offset + 2] = if (((row >> 2) ^ (column >> 2)) & 0x01) != 0 {
                255
            } else {
                0
            };
            frame[offset + 3] = 255;
        }
    }

    frame
}

fn quadrant_rgba_frame(width: u32, height: u32) -> Vec<u8> {
    let mut frame = vec![0_u8; (width * height * 4) as usize];
    let half_width = width / 2;
    let half_height = height / 2;

    for y in 0..height {
        for x in 0..width {
            let base = ((y * width + x) * 4) as usize;
            let (red, green, blue) = match (x < half_width, y < half_height) {
                (true, true) => (255, 0, 0),
                (false, true) => (0, 255, 0),
                (true, false) => (0, 0, 255),
                (false, false) => (255, 255, 255),
            };
            frame[base] = red;
            frame[base + 1] = green;
            frame[base + 2] = blue;
            frame[base + 3] = 255;
        }
    }

    frame
}

fn rgb_lane_pattern_rgba_frame(width: u32, height: u32, row_pair: usize) -> Vec<u8> {
    let width = width as usize;
    let height = height as usize;
    let row_pairs = height / 2;
    let top_row = row_pair;
    let bottom_row = row_pair + row_pairs;
    let mut frame = vec![0_u8; width * height * 4];

    for column in 0..width {
        let top_offset = ((top_row * width) + column) * 4;
        let bottom_offset = ((bottom_row * width) + column) * 4;
        if (column & 0x01) != 0 {
            frame[top_offset] = 255;
        }
        if (column & 0x02) != 0 {
            frame[top_offset + 1] = 255;
        }
        if (column & 0x04) != 0 {
            frame[top_offset + 2] = 255;
        }
        if (column & 0x08) != 0 {
            frame[bottom_offset] = 255;
        }
        if (column & 0x10) != 0 {
            frame[bottom_offset + 1] = 255;
        }
        if (column & 0x20) != 0 {
            frame[bottom_offset + 2] = 255;
        }
        frame[top_offset + 3] = 255;
        frame[bottom_offset + 3] = 255;
    }

    frame
}

fn simulate_simple_full_frame(
    config: &Pi5ScanConfig,
    rgba: &[u8],
) -> Result<Vec<Vec<[bool; 3]>>, String> {
    let height = config.height()? as usize;
    let row_pairs = config.row_pairs()?;
    let mut rows = vec![vec![[false; 3]; config.width()? as usize]; height];

    for row_pair in 0..row_pairs {
        let words = build_simple_group_words_for_rgba(config, rgba, row_pair, 0)?;
        let simulated = simulate_simple_group_output(config, &words)?;
        rows[row_pair] = simulated
            .columns
            .iter()
            .map(|column| column.top_rgb)
            .collect();
        rows[row_pair + row_pairs] = simulated
            .columns
            .iter()
            .map(|column| column.bottom_rgb)
            .collect();
    }

    Ok(rows)
}

fn simulate_simple_full_frame_via_pio_emulator(
    config: &Pi5ScanConfig,
    rgba: &[u8],
) -> Result<Vec<Vec<[bool; 3]>>, String> {
    let width = config.width()? as usize;
    let height = config.height()? as usize;
    let row_pairs = config.row_pairs()?;
    let mut rows = vec![vec![[false; 3]; width]; height];

    for row_pair in 0..row_pairs {
        let words = build_simple_group_words_for_rgba(config, rgba, row_pair, 0)?;
        let simulated = simulate_simple_hub75_group(config, &words)?;
        let shift_low_steps = simple_shift_low_steps(&simulated);
        if shift_low_steps.len() != width {
            return Err(format!(
                "simple PIO emulator emitted {} column words for row pair {row_pair}, expected {width}",
                shift_low_steps.len()
            ));
        }
        for (column, step) in shift_low_steps.iter().enumerate() {
            let decoded = decode_column(pins_to_pin_word(step.pins));
            rows[row_pair][column] = decoded.top_rgb;
            rows[row_pair + row_pairs][column] = decoded.bottom_rgb;
        }
    }

    Ok(rows)
}

fn expected_frame_output_from_rgba(
    config: &Pi5ScanConfig,
    rgba: &[u8],
) -> Result<Vec<Vec<[bool; 3]>>, String> {
    let width = config.width()? as usize;
    let height = config.height()? as usize;
    let mut rows = vec![vec![[false; 3]; width]; height];

    for row in 0..height {
        for column in 0..width {
            let offset = ((row * width) + column) * 4;
            rows[row][column] = [
                rgba[offset] >= 128,
                rgba[offset + 1] >= 128,
                rgba[offset + 2] >= 128,
            ];
        }
    }

    Ok(rows)
}

fn expected_group_output_from_rgba(
    config: &Pi5ScanConfig,
    rgba: &[u8],
    row_pair: usize,
) -> SimulatedGroupOutput {
    let width = config.width().expect("width should resolve") as usize;
    let row_pairs = config.row_pairs().expect("row_pairs should resolve");
    let mut columns = Vec::with_capacity(width);

    for column in 0..width {
        let top_offset = ((row_pair * width) + column) * 4;
        let bottom_offset = (((row_pair + row_pairs) * width) + column) * 4;
        columns.push(SimulatedColumn {
            top_rgb: [
                rgba[top_offset] >= 128,
                rgba[top_offset + 1] >= 128,
                rgba[top_offset + 2] >= 128,
            ],
            bottom_rgb: [
                rgba[bottom_offset] >= 128,
                rgba[bottom_offset + 1] >= 128,
                rgba[bottom_offset + 2] >= 128,
            ],
        });
    }

    SimulatedGroupOutput {
        row_pair,
        columns,
        oe_active_during_dwell: true,
    }
}

fn simulate_simple_group_output(
    config: &Pi5ScanConfig,
    words: &[u32],
) -> Result<SimulatedGroupOutput, String> {
    let width = config.width()? as usize;
    let parsed = parse_simple_group(words, width);
    if parsed.word_count() != words.len() {
        return Err(format!(
            "simple group simulation parsed {} words but received {}",
            parsed.word_count(),
            words.len()
        ));
    }
    let blank_word = parsed.blank_word;
    let active_word = parsed.active_word;
    let row_pair = decode_row_pair(blank_word);
    if decode_row_pair(active_word) != row_pair {
        return Err(
            "simple group simulation found mismatched row addresses between blank and active words"
                .to_string(),
        );
    }
    let columns = parsed
        .shift_words
        .iter()
        .copied()
        .map(decode_column)
        .collect::<Vec<_>>();
    let oe_active_during_dwell = decode_test_simple_command(parsed.active_command).1 > 0
        && !word_has_gpio(active_word, OE_GPIO);

    Ok(SimulatedGroupOutput {
        row_pair,
        columns,
        oe_active_during_dwell,
    })
}

fn decode_column(word: u32) -> SimulatedColumn {
    SimulatedColumn {
        top_rgb: [
            word_has_gpio(word, R1_GPIO),
            word_has_gpio(word, G1_GPIO),
            word_has_gpio(word, B1_GPIO),
        ],
        bottom_rgb: [
            word_has_gpio(word, R2_GPIO),
            word_has_gpio(word, G2_GPIO),
            word_has_gpio(word, B2_GPIO),
        ],
    }
}

fn decode_row_pair(word: u32) -> usize {
    let mut row_pair = 0_usize;
    for (bit_index, gpio) in [A_GPIO, B_GPIO, C_GPIO, D_GPIO, E_GPIO].iter().enumerate() {
        if word_has_gpio(word, *gpio) {
            row_pair |= 1 << bit_index;
        }
    }
    row_pair
}

fn word_has_gpio(word: u32, gpio: u32) -> bool {
    let bit = gpio - PIN_WORD_BASE_GPIO;
    (word & (1_u32 << bit)) != 0
}

fn pins_to_pin_word(pins: u32) -> u32 {
    (pins >> PIN_WORD_BASE_GPIO) & SIMPLE_PIN_WORD_MASK
}

fn assert_rgb_pins_match_column(
    pins: u32,
    expected_column: &SimulatedColumn,
    phase: &str,
    column: usize,
) {
    assert_eq!(
        gpio_is_high(pins, R1_GPIO),
        expected_column.top_rgb[0],
        "{phase} phase drove R1 incorrectly for column {column}"
    );
    assert_eq!(
        gpio_is_high(pins, G1_GPIO),
        expected_column.top_rgb[1],
        "{phase} phase drove G1 incorrectly for column {column}"
    );
    assert_eq!(
        gpio_is_high(pins, B1_GPIO),
        expected_column.top_rgb[2],
        "{phase} phase drove B1 incorrectly for column {column}"
    );
    assert_eq!(
        gpio_is_high(pins, R2_GPIO),
        expected_column.bottom_rgb[0],
        "{phase} phase drove R2 incorrectly for column {column}"
    );
    assert_eq!(
        gpio_is_high(pins, G2_GPIO),
        expected_column.bottom_rgb[1],
        "{phase} phase drove G2 incorrectly for column {column}"
    );
    assert_eq!(
        gpio_is_high(pins, B2_GPIO),
        expected_column.bottom_rgb[2],
        "{phase} phase drove B2 incorrectly for column {column}"
    );
}
