use std::sync::Arc;
use std::thread;
use std::time::Duration;
use std::{fs, path::PathBuf};

use super::config::{ColorOrder, WiringProfile};
use super::driver::{MatrixDriverCore, MatrixDriverError};
use super::pi5_pio_programs_generated::PI5_PIO_SIMPLE_HUB75_SIDESET_TOTAL_BITS;
use super::{
    build_simple_group_words_for_rgba, estimate_simple_hub75_frame_timing,
    gpio_is_high, pio_program_info_for_format, simulate_simple_hub75_group, FrameBufferPool,
    PackedScanFrame, Pi5ScanConfig, Pi5ScanFormat, Pi5ScanTiming,
};
use crate::runtime::pi5_scan::{
    decode_dwell_counter, encode_raw_span_word, encode_repeat_span_word, Pi5KernelResidentLoopStats,
    SIMPLE_COMMAND_COUNT_MASK, SIMPLE_COMMAND_DATA_BIT,
};
use crate::runtime::queue::WorkerState;

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
fn frame_buffer_identity_advances_when_contents_change() {
    let mut frame = FrameBufferPool::new(8, 1).acquire();
    let initial_identity = frame.identity();

    frame.write_rgba(&[1, 2, 3, 4, 5, 6, 7, 8], ColorOrder::Rgb);
    let updated_identity = frame.identity();
    frame.clear();
    let cleared_identity = frame.identity();

    assert_ne!(initial_identity, updated_identity);
    assert_ne!(updated_identity, cleared_identity);
    assert_eq!(initial_identity.0, updated_identity.0);
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
fn pi5_kernel_stats_surface_worker_errors_in_presentation_counts() {
    let stats = Pi5KernelResidentLoopStats {
        presentations: 7,
        last_error: -5,
        ..Default::default()
    };

    let error = stats
        .presentation_count_result()
        .expect_err("worker failures should not be hidden behind a presentation count");

    assert!(error.contains("-5"));
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
fn pi5_native_pwm_bonnet_keeps_gpio4_out_of_the_pio_output_window() {
    let source_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("native")
        .join("pi5_pio_scan_shim.c");
    let source = fs::read_to_string(&source_path)
        .unwrap_or_else(|error| panic!("failed to read {}: {error}", source_path.display()));

    assert!(
        source.contains(
            "oe_gpio == 18u && pin == HEART_PI5_PIO_SCAN_ADAFRUIT_PWM_TRANSITION_GPIO"
        ),
        "the native shim should special-case the PWM bonnet's bridged GPIO4 pin"
    );
    assert!(
        source.contains("heart_pi5_pio_scan_output_window_init(pio, (uint)sm, oe_gpio);"),
        "the native shim should decide output-window ownership from the active OE mapping"
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
        3,
        "the simple command interpreter should only write the OUT window for delay, data, and repeat GPIO words"
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
