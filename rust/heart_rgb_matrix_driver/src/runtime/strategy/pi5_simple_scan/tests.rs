use heart_pio_sim::{pio_encode_out, simulate_program, PioOutDest, PioSimulatorConfig};

use super::{PackedScanFrame, Pi5ScanConfig};
use crate::runtime::config::WiringProfile;
use crate::runtime::pi5_pinout::Pi5ScanPinout;
use crate::runtime::pi5_pio_programs_generated::{
    PI5_PIO_RAW_BYTE_PULL_BASE_PROGRAM, PI5_PIO_RAW_BYTE_PULL_OUT_PIN_BASE,
    PI5_PIO_RAW_BYTE_PULL_OUT_PIN_COUNT, PI5_PIO_RAW_BYTE_PULL_OUT_SHIFT_RIGHT,
    PI5_PIO_RAW_BYTE_PULL_WRAP, PI5_PIO_RAW_BYTE_PULL_WRAP_TARGET,
};

fn red_frame_rgba(config: &Pi5ScanConfig) -> Vec<u8> {
    let width = config.width().expect("width should resolve") as usize;
    let height = config.height().expect("height should resolve") as usize;
    let mut rgba = vec![0_u8; width * height * 4];
    for pixel in rgba.chunks_exact_mut(4) {
        pixel[0] = 0xff;
        pixel[3] = 0xff;
    }
    rgba
}

fn raw_frame_words(config: &Pi5ScanConfig) -> Vec<u32> {
    let rgba = red_frame_rgba(config);
    let (frame, _) = PackedScanFrame::pack_rgba(config, &rgba).expect("raw frame should pack");
    frame.as_words().to_vec()
}

fn raw_byte_pull_sim_config() -> PioSimulatorConfig {
    PioSimulatorConfig {
        wrap_target: PI5_PIO_RAW_BYTE_PULL_WRAP_TARGET,
        wrap: PI5_PIO_RAW_BYTE_PULL_WRAP,
        out_pin_base: PI5_PIO_RAW_BYTE_PULL_OUT_PIN_BASE,
        out_pin_count: PI5_PIO_RAW_BYTE_PULL_OUT_PIN_COUNT,
        set_pin_base: 0,
        set_pin_count: 0,
        sideset_pin_base: 0,
        sideset_count: 0,
        sideset_total_bits: 0,
        sideset_optional: false,
        out_shift_right: PI5_PIO_RAW_BYTE_PULL_OUT_SHIFT_RIGHT,
        auto_pull: false,
        pull_threshold: 32,
    }
}

fn raw_byte_pull_config() -> Pi5ScanConfig {
    Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .expect("config should build")
        .with_pwm_bits(5)
        .expect("pwm bits should apply")
        .with_clock_divider(1.0)
        .expect("clock divider should apply")
}

#[test]
fn raw_byte_pull_matches_equivalent_autopull_out_stream() {
    let config = raw_byte_pull_config();
    let words = raw_frame_words(&config);
    let sample_len = 256.min(words.len());
    let fifo_words = &words[..sample_len];

    let explicit = simulate_program(
        &PI5_PIO_RAW_BYTE_PULL_BASE_PROGRAM,
        raw_byte_pull_sim_config(),
        fifo_words,
        sample_len * 2 + 4,
    )
    .expect("explicit pull program should simulate");
    let explicit_pins: Vec<u32> = explicit
        .steps
        .iter()
        .filter(|step| (step.instruction >> 13) == 3)
        .map(|step| step.pins)
        .collect();

    let autopull_program = [pio_encode_out(PioOutDest::Pins as u8, 28)];
    let autopull = simulate_program(
        &autopull_program,
        PioSimulatorConfig {
            wrap_target: 0,
            wrap: 0,
            out_pin_base: PI5_PIO_RAW_BYTE_PULL_OUT_PIN_BASE,
            out_pin_count: PI5_PIO_RAW_BYTE_PULL_OUT_PIN_COUNT,
            set_pin_base: 0,
            set_pin_count: 0,
            sideset_pin_base: 0,
            sideset_count: 0,
            sideset_total_bits: 0,
            sideset_optional: false,
            out_shift_right: PI5_PIO_RAW_BYTE_PULL_OUT_SHIFT_RIGHT,
            auto_pull: true,
            pull_threshold: 28,
        },
        fifo_words,
        sample_len + 2,
    )
    .expect("autopull program should simulate");
    let autopull_pins: Vec<u32> = autopull
        .steps
        .iter()
        .filter(|step| (step.instruction >> 13) == 3)
        .map(|step| step.pins)
        .collect();

    assert_eq!(
        explicit_pins, autopull_pins,
        "explicit pull transport should emit the same raw pin stream as an equivalent autopull-only loop"
    );
}

#[test]
fn raw_byte_pull_holds_every_output_word_for_constant_duration() {
    let config = raw_byte_pull_config();
    let words = raw_frame_words(&config);
    let sample_len = 512.min(words.len());
    let simulation = simulate_program(
        &PI5_PIO_RAW_BYTE_PULL_BASE_PROGRAM,
        raw_byte_pull_sim_config(),
        &words[..sample_len],
        sample_len * 2 + 4,
    )
    .expect("raw byte pull program should simulate");

    let out_steps: Vec<_> = simulation
        .steps
        .iter()
        .filter(|step| (step.instruction >> 13) == 3)
        .collect();
    assert!(
        out_steps.len() >= 2,
        "expected at least two OUT steps to compare hold duration"
    );

    let deltas: Vec<u64> = out_steps
        .windows(2)
        .map(|window| window[1].cycle_start - window[0].cycle_start)
        .collect();
    let expected_delta = deltas[0];
    assert!(
        deltas
            .iter()
            .all(|delta| *delta >= expected_delta.saturating_sub(1)
                && *delta <= expected_delta + 1),
        "raw byte pull should hold every emitted word for the same number of instructions; got deltas {deltas:?}"
    );

    let pinout = Pi5ScanPinout::for_wiring(WiringProfile::AdafruitHatPwm)
        .expect("pinout should resolve");
    let active_groups_per_plane = usize::from(config.pwm_bits()) * config.row_pairs().expect("row pairs");
    let active_deltas: Vec<u64> = out_steps
        .iter()
        .map(|step| step.pins)
        .filter(|pins| (*pins & pinout.oe_inactive_bits(0)) == 0)
        .take(active_groups_per_plane)
        .zip(out_steps.iter().skip(1).map(|step| step.cycle_start))
        .enumerate()
        .map(|(index, (_, next_cycle_start))| next_cycle_start - out_steps[index].cycle_start)
        .collect();
    assert!(
        active_deltas
            .iter()
            .all(|delta| *delta >= expected_delta.saturating_sub(1)
                && *delta <= expected_delta + 1),
        "active row writes should be held uniformly before changing or blanking; got active deltas {active_deltas:?}"
    );
}
