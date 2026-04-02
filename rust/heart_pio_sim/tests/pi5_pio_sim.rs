use heart_pio_sim::{
    pio_encode_delay, pio_encode_jmp_x_dec, pio_encode_jmp_y_dec, pio_encode_nop, pio_encode_out,
    pio_encode_pull, pio_encode_sideset_opt, simulate_program, PioOutDest, PioSimulation,
    PioSimulatorConfig,
};

const LOW_23_BITS_MASK: u32 = (1_u32 << 23) - 1;

fn default_config() -> PioSimulatorConfig {
    PioSimulatorConfig {
        wrap_target: 0,
        wrap: 0,
        out_pin_base: 0,
        out_pin_count: 23,
        set_pin_base: 0,
        set_pin_count: 0,
        sideset_pin_base: 0,
        sideset_count: 0,
        sideset_total_bits: 0,
        sideset_optional: false,
        out_shift_right: true,
        auto_pull: false,
        pull_threshold: 32,
    }
}

fn simulate(program: &[u16], config: PioSimulatorConfig, fifo_words: &[u32]) -> PioSimulation {
    simulate_program(program, config, fifo_words, 64).expect("program should simulate cleanly")
}

#[test]
fn explicit_pull_overwrites_unused_osr_bits_before_the_next_out() {
    let mut config = default_config();
    config.wrap = 4;
    let program = vec![
        pio_encode_pull(false, true),
        pio_encode_out(PioOutDest::Pins as u8, 23),
        pio_encode_pull(false, true),
        pio_encode_out(PioOutDest::Pins as u8, 23),
        pio_encode_pull(false, true),
    ];
    let fifo_words = [0xA555_4321, 0x5AAA_1357];
    let simulated = simulate(&program, config, &fifo_words);
    let emitted = simulated
        .steps
        .iter()
        .filter(|step| step.pc == 1 || step.pc == 3)
        .map(|step| step.pins)
        .collect::<Vec<_>>();

    assert_eq!(
        emitted,
        vec![fifo_words[0] & LOW_23_BITS_MASK, fifo_words[1] & LOW_23_BITS_MASK],
        "an explicit pull should replace OSR completely so unused high bits from a partial out cannot drift into the next value"
    );
    assert!(
        simulated.stalled_on_pull,
        "the sentinel blocking pull should stop the simulation after the second out"
    );
}

#[test]
fn jmp_x_dec_decrements_after_testing_the_current_value() {
    let mut config = default_config();
    config.wrap = 3;
    let program = vec![
        pio_encode_pull(false, true),
        pio_encode_out(PioOutDest::X as u8, 32),
        pio_encode_jmp_x_dec(2),
        pio_encode_pull(false, true),
    ];
    let simulated = simulate(&program, config, &[2]);
    let x_values = simulated
        .steps
        .iter()
        .filter(|step| step.pc == 2)
        .map(|step| step.x)
        .collect::<Vec<_>>();

    assert_eq!(
        x_values,
        vec![1, 0, u32::MAX],
        "jmp x-- should jump while X was non-zero, then decrement X after each test"
    );
}

#[test]
fn jmp_y_dec_decrements_after_testing_the_current_value() {
    let mut config = default_config();
    config.wrap = 3;
    let program = vec![
        pio_encode_pull(false, true),
        pio_encode_out(PioOutDest::Y as u8, 32),
        pio_encode_jmp_y_dec(2),
        pio_encode_pull(false, true),
    ];
    let simulated = simulate(&program, config, &[2]);
    let y_values = simulated
        .steps
        .iter()
        .filter(|step| step.pc == 2)
        .map(|step| step.y)
        .collect::<Vec<_>>();

    assert_eq!(
        y_values,
        vec![1, 0, u32::MAX],
        "jmp y-- should jump while Y was non-zero, then decrement Y after each test"
    );
}

#[test]
fn optional_sideset_only_touches_the_sideset_pin_and_extends_the_cycle_count() {
    let mut config = default_config();
    config.wrap = 1;
    config.sideset_pin_base = 10;
    config.sideset_count = 1;
    config.sideset_total_bits = 2;
    config.sideset_optional = true;
    let program = vec![
        pio_encode_nop() | pio_encode_delay(3) | pio_encode_sideset_opt(1, 1),
        pio_encode_pull(false, true),
    ];
    let simulated = simulate(&program, config, &[]);
    let first_step = simulated
        .steps
        .first()
        .expect("the sided-set nop should execute before the blocking pull");

    assert_eq!(
        first_step.pins,
        1_u32 << 10,
        "optional sideset should only modify the configured sideset pin when no out/set pins are active"
    );
    assert_eq!(
        first_step.cycle_end - first_step.cycle_start,
        4,
        "a delay of 3 should stretch the instruction to 4 total cycles"
    );
}

#[test]
fn autopull_refills_the_osr_after_the_threshold_is_consumed() {
    let mut config = default_config();
    config.wrap = 4;
    config.out_pin_count = 32;
    config.out_shift_right = false;
    config.auto_pull = true;
    config.pull_threshold = 32;
    let program = vec![
        pio_encode_out(PioOutDest::X as u8, 1),
        pio_encode_out(PioOutDest::Y as u8, 31),
        pio_encode_out(PioOutDest::Pins as u8, 32),
        pio_encode_out(PioOutDest::Pins as u8, 32),
        pio_encode_pull(false, true),
    ];
    let fifo_words = [0x8000_0003, 0x0123_4567, 0x89ab_cdef];
    let simulated = simulate(&program, config, &fifo_words);

    assert_eq!(
        simulated.steps[0].x, 1,
        "the first OUT should consume the command MSB from the autopulled word"
    );
    assert_eq!(
        simulated.steps[1].y, 3,
        "the second OUT should consume the remaining 31 command bits before the next autopull"
    );
    assert_eq!(
        simulated.steps[2].pins, fifo_words[1],
        "after the command word is exhausted, the next OUT should autopull the first payload word"
    );
    assert_eq!(
        simulated.steps[3].pins, fifo_words[2],
        "the following OUT should autopull the next payload word"
    );
}
