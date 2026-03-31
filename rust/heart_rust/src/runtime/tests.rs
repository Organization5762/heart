use std::sync::Arc;
use std::thread;
use std::time::Duration;

use super::config::{ColorOrder, WiringProfile};
use super::driver::{MatrixDriverCore, MatrixDriverError};
use super::{FrameBufferPool, PackedScanFrame, Pi5ScanConfig};
use crate::runtime::pi5_scan::{encode_raw_span_word, encode_repeat_span_word};
use crate::runtime::queue::WorkerState;

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
    let driver = MatrixDriverCore::new(
        WiringProfile::AdafruitHatPwm,
        16,
        32,
        1,
        1,
        ColorOrder::Rgb,
    )
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
    let driver = MatrixDriverCore::new(
        WiringProfile::AdafruitHatPwm,
        16,
        32,
        1,
        1,
        ColorOrder::Rgb,
    )
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
    let driver = MatrixDriverCore::new(
        WiringProfile::AdafruitHatPwm,
        16,
        32,
        1,
        1,
        ColorOrder::Rgb,
    )
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
        MatrixDriverCore::new(
            WiringProfile::AdafruitHatPwm,
            64,
            64,
            1,
            1,
            ColorOrder::Rgb,
        )
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
        .expect("single-panel Pi 5 scan config should be valid");
    let frame = vec![255_u8; (config.width().unwrap() * config.height().unwrap() * 4) as usize];

    let (packed, stats) =
        PackedScanFrame::pack_rgba(&config, &frame).expect("scan packing should succeed");

    assert_eq!(stats.compressed_blank_groups, 32 * 3);
    assert_eq!(stats.merged_identical_groups, 32 * 7);
    assert_eq!(packed.word_count(), 32 * 4);
    assert_eq!(stats.word_count, packed.word_count());
}

#[test]
fn pi5_scan_pack_rgba_emits_compact_group_headers_and_control_words() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
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
    assert_eq!(words[3], 2047);
    assert_eq!(stats.compressed_blank_groups, 32 * 11);
    assert_eq!(stats.merged_identical_groups, 0);
    assert_eq!(stats.word_count, 4);
}

#[test]
fn pi5_scan_raw_span_control_word_embeds_the_first_pin_word() {
    let control =
        encode_raw_span_word(2, 1 << 13).expect("raw span word should encode");

    assert_eq!(control, (1 << 22) | (1 << 1));
    assert!(
        encode_raw_span_word(257, 1 << 13).is_err(),
        "raw spans longer than 256 pixels should be rejected"
    );
}

#[test]
fn pi5_scan_pack_rgba_merges_nonadjacent_identical_plane_payloads() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
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
    assert_eq!(packed.word_count(), 32 * 4);
}

#[test]
fn pi5_scan_pack_rgba_uses_inlined_raw_headers_for_dense_frames() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
        .and_then(|config| config.with_pwm_bits(11))
        .expect("single-panel Pi 5 scan config should be valid");
    let frame = frame_bytes(config.width().unwrap(), config.height().unwrap(), 31);

    let (packed, stats) =
        PackedScanFrame::pack_rgba(&config, &frame).expect("scan packing should succeed");

    assert_eq!(stats.compressed_blank_groups, 96);
    assert_eq!(stats.merged_identical_groups, 0);
    assert_eq!(packed.word_count(), 6208);
    assert_eq!(stats.word_count, packed.word_count());
}

#[test]
fn pi5_scan_pack_rgba_splits_large_internal_blank_spans() {
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)
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
    assert_eq!(packed.word_count(), 32 * 7);
}
