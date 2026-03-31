#![allow(dead_code)]

#[path = "../src/runtime/mod.rs"]
mod runtime;

use criterion::{criterion_group, criterion_main, BatchSize, BenchmarkId, Criterion, Throughput};
use runtime::{ColorOrder, FrameBufferPool, MatrixDriverCore};
#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
use runtime::{PackedTransportFrame, Pi5PioDmaTransport, Pi5TransportConfig};
use std::cell::RefCell;
use std::hint::black_box;
use std::sync::Arc;
use std::thread;
use std::time::Instant;

fn frame_bytes(width: u32, height: u32, seed: u8) -> Vec<u8> {
    let byte_count = (width as usize) * (height as usize) * 4;
    (0..byte_count)
        .map(|index| seed.wrapping_add(index as u8))
        .collect()
}

fn bench_submit_rgba(c: &mut Criterion) {
    let mut group = c.benchmark_group("matrix_submit_rgba");

    for (label, panel_rows, panel_cols, chain_length, parallel, color_order) in [
        ("32x16_rgb", 16_u16, 32_u16, 1_u16, 1_u8, "rgb"),
        ("64x64_rgb", 64_u16, 64_u16, 1_u16, 1_u8, "rgb"),
        ("128x64_rgb", 64_u16, 64_u16, 2_u16, 1_u8, "rgb"),
        ("128x64_gbr", 64_u16, 64_u16, 2_u16, 1_u8, "gbr"),
    ] {
        let driver = MatrixDriverCore::new(
            "adafruit_hat_pwm".to_string(),
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            color_order.to_string(),
        )
        .expect("benchmark driver should initialize");
        let width = driver.width();
        let height = driver.height();
        let template = frame_bytes(width, height, 7);
        group.throughput(Throughput::Bytes(template.len() as u64));

        group.bench_with_input(BenchmarkId::from_parameter(label), &label, |b, _| {
            b.iter_batched(
                || template.clone(),
                |frame| {
                    driver
                        .submit_rgba(black_box(frame), black_box(width), black_box(height))
                        .expect("benchmark submission should succeed");
                },
                BatchSize::SmallInput,
            );
        });

        driver.close().expect("benchmark driver should close");
    }

    group.finish();
}

fn bench_frame_write_rgba(c: &mut Criterion) {
    let mut group = c.benchmark_group("frame_write_rgba");

    for (label, width, height, color_order) in [
        ("64x64_rgb", 64_u32, 64_u32, ColorOrder::Rgb),
        ("64x64_gbr", 64_u32, 64_u32, ColorOrder::Gbr),
        ("128x64_gbr", 128_u32, 64_u32, ColorOrder::Gbr),
    ] {
        let template = frame_bytes(width, height, 11);
        let pool = RefCell::new(FrameBufferPool::new(template.len(), 1));
        group.throughput(Throughput::Bytes(template.len() as u64));

        group.bench_with_input(BenchmarkId::from_parameter(label), &label, |b, _| {
            b.iter(|| {
                let mut pool = pool.borrow_mut();
                let mut frame = pool.acquire();
                frame.write_rgba(black_box(template.as_slice()), color_order);
                black_box(frame.as_slice());
                pool.recycle(frame);
            });
        });
    }

    group.finish();
}

fn bench_submit_rgba_contention(c: &mut Criterion) {
    let mut group = c.benchmark_group("matrix_submit_rgba_contention");

    for producers in [1_usize, 2_usize, 4_usize] {
        let driver = Arc::new(
            MatrixDriverCore::new(
                "adafruit_hat_pwm".to_string(),
                64,
                64,
                1,
                1,
                "rgb".to_string(),
            )
            .expect("benchmark driver should initialize"),
        );
        let width = driver.width();
        let height = driver.height();
        let templates: Vec<Vec<u8>> = (0..producers)
            .map(|seed| frame_bytes(width, height, (seed * 17) as u8))
            .collect();

        group.bench_with_input(
            BenchmarkId::from_parameter(format!("64x64_rgb_{producers}p")),
            &producers,
            |b, &producer_count| {
                b.iter_custom(|iters| {
                    let start = Instant::now();
                    thread::scope(|scope| {
                        for worker_index in 0..producer_count {
                            let driver = Arc::clone(&driver);
                            let template = templates[worker_index].clone();
                            let iterations_for_worker = (iters as usize) / producer_count
                                + usize::from(worker_index < (iters as usize) % producer_count);
                            scope.spawn(move || {
                                for iteration in 0..iterations_for_worker {
                                    let mut frame = template.clone();
                                    frame[0] = frame[0].wrapping_add(iteration as u8);
                                    driver
                                        .submit_rgba(frame, width, height)
                                        .expect("contention submission should succeed");
                                }
                            });
                        }
                    });
                    start.elapsed()
                });
            },
        );

        driver.close().expect("benchmark driver should close");
    }

    group.finish();
}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
fn bench_pi5_pack_transport(c: &mut Criterion) {
    let mut group = c.benchmark_group("pi5_pack_transport_rgba");

    for (label, chain_length) in [("64x64_chain1_pwm11", 1_u16), ("64x64_chain4_pwm11", 4_u16)] {
        let config =
            Pi5TransportConfig::new(64, 64, chain_length, 1, 11).expect("config should be valid");
        let frame = frame_bytes(config.width().unwrap(), config.height().unwrap(), 29);
        group.throughput(Throughput::Bytes(frame.len() as u64));
        group.bench_with_input(BenchmarkId::from_parameter(label), &label, |b, _| {
            b.iter(|| {
                let (packed, pack_duration) = PackedTransportFrame::pack_rgba(
                    black_box(&config),
                    black_box(frame.as_slice()),
                )
                .expect("packing should succeed");
                black_box(packed.as_slice());
                black_box(pack_duration);
            });
        });
    }

    group.finish();
}

#[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
fn bench_pi5_pack_transport(_: &mut Criterion) {}

#[cfg(all(target_arch = "aarch64", target_os = "linux"))]
fn bench_pi5_dma_transport(c: &mut Criterion) {
    let mut group = c.benchmark_group("pi5_dma_transport");

    for (label, chain_length) in [("64x64_chain1_pwm11", 1_u16), ("64x64_chain4_pwm11", 4_u16)] {
        let config =
            Pi5TransportConfig::new(64, 64, chain_length, 1, 11).expect("config should be valid");
        let width = config.width().expect("width should be valid");
        let height = config.height().expect("height should be valid");
        let frame = frame_bytes(width, height, 41);
        let (packed, _) =
            PackedTransportFrame::pack_rgba(&config, &frame).expect("packing should succeed");
        let mut transport =
            Pi5PioDmaTransport::new(packed.len()).expect("Pi 5 DMA transport should initialize");
        group.throughput(Throughput::Bytes(packed.len() as u64));
        group.bench_with_input(BenchmarkId::from_parameter(label), &label, |b, _| {
            b.iter_custom(|iters| {
                let start = Instant::now();
                for _ in 0..iters {
                    transport
                        .stream(black_box(&packed))
                        .expect("DMA transport should succeed");
                }
                start.elapsed()
            });
        });
    }

    group.finish();
}

#[cfg(not(all(target_arch = "aarch64", target_os = "linux")))]
fn bench_pi5_dma_transport(_: &mut Criterion) {}

criterion_group!(
    benches,
    bench_frame_write_rgba,
    bench_submit_rgba,
    bench_submit_rgba_contention,
    bench_pi5_pack_transport,
    bench_pi5_dma_transport
);
criterion_main!(benches);
