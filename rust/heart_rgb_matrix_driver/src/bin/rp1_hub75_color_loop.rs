use std::env;
use std::thread;
use std::time::{Duration, Instant};

use heart_rgb_matrix_driver::{
    rp1_hub75_read_pack_stats, rp1_hub75_read_present_stats, rp1_hub75_read_worker_status,
    ProbeWiringProfile, RuntimeColorOrder, RuntimeMatrixDriver, RuntimeMatrixDriverError,
};

const WIDTH: u32 = 64;
const HEIGHT: u32 = 64;
const COLORS: &[(u8, u8, u8)] = &[(255, 0, 0), (0, 255, 0), (0, 0, 255)];

fn main() -> Result<(), String> {
    let duration = parse_duration_ms(1, Duration::from_secs(10))?;
    let interval = parse_duration_ms(2, Duration::from_millis(1))?;
    let solid = parse_solid_color()?;
    let wiring = parse_wiring()?;
    let driver = RuntimeMatrixDriver::new(
        wiring,
        HEIGHT as u16,
        WIDTH as u16,
        1,
        1,
        RuntimeColorOrder::Rgb,
    )
    .map_err(format_driver_error)?;

    let start = Instant::now();
    let mut submitted = 0_u64;
    while start.elapsed() < duration {
        let (red, green, blue) =
            solid.unwrap_or_else(|| COLORS[(submitted as usize) % COLORS.len()]);
        let frame = solid_rgba(red, green, blue);
        driver
            .submit_rgba(&frame, WIDTH, HEIGHT)
            .map_err(format_driver_error)?;
        submitted += 1;
        if !interval.is_zero() {
            thread::sleep(interval);
        }
    }
    driver.close().map_err(format_driver_error)?;

    let elapsed = start.elapsed();
    let pack = rp1_hub75_read_pack_stats()?;
    let present = rp1_hub75_read_present_stats()?;
    let worker = rp1_hub75_read_worker_status()?;
    println!(
        "submitted={submitted} elapsed_s={:.3} submit_hz={:.2} solid={}",
        elapsed.as_secs_f64(),
        submitted as f64 / elapsed.as_secs_f64(),
        solid
            .map(|(red, green, blue)| format!("{red},{green},{blue}"))
            .unwrap_or_else(|| "cycle".to_string())
    );
    println!(
        "pack frames_packed={} bytes_packed={} last_error={} words_per_frame={}",
        pack.frames_packed, pack.bytes_packed, pack.last_error, pack.words_per_frame
    );
    println!(
        "present queued={} presented={} dropped={} vsync={} queued_seq={} presented_seq={} displayed_slot={} pending_slot={}",
        present.frames_queued,
        present.frames_presented,
        present.frames_dropped,
        present.vsync_count,
        present.queued_seq,
        present.presented_seq,
        present.displayed_slot,
        present.pending_slot
    );
    println!(
        "worker state={} flags={} seq={} vsync={} queued_seq={} presented_seq={} displayed_slot={} pending_slot={} last_error={}",
        worker.state,
        worker.flags,
        worker.worker_seq,
        worker.vsync_count,
        worker.queued_seq,
        worker.presented_seq,
        worker.displayed_slot,
        worker.pending_slot,
        worker.last_error
    );
    Ok(())
}

fn parse_wiring() -> Result<ProbeWiringProfile, String> {
    match env::var("HEART_RGB_MATRIX_WIRING")
        .unwrap_or_else(|_| "adafruit_hat_pwm".to_string())
        .to_ascii_lowercase()
        .as_str()
    {
        "adafruit_hat_pwm" | "pwm" => Ok(ProbeWiringProfile::AdafruitHatPwm),
        "electrodragon" | "electrodragon_p0" => Ok(ProbeWiringProfile::ElectroDragonP0),
        "regular" => Ok(ProbeWiringProfile::Regular),
        other => Err(format!("Unsupported HEART_RGB_MATRIX_WIRING={other}")),
    }
}

fn parse_duration_ms(index: usize, default: Duration) -> Result<Duration, String> {
    let Some(raw) = std::env::args().nth(index) else {
        return Ok(default);
    };
    raw.parse::<u64>()
        .map(Duration::from_millis)
        .map_err(|error| format!("argument {index} must be a millisecond count: {error}"))
}

fn parse_solid_color() -> Result<Option<(u8, u8, u8)>, String> {
    let Some(raw) = std::env::var_os("HEART_RP1_HUB75_COLOR_LOOP_SOLID") else {
        return Ok(None);
    };
    let value = raw
        .into_string()
        .map_err(|_| "HEART_RP1_HUB75_COLOR_LOOP_SOLID must be valid UTF-8".to_string())?;
    match value.as_str() {
        "red" => Ok(Some((255, 0, 0))),
        "green" => Ok(Some((0, 255, 0))),
        "blue" => Ok(Some((0, 0, 255))),
        "white" => Ok(Some((255, 255, 255))),
        "black" => Ok(Some((0, 0, 0))),
        _ => Err(
            "HEART_RP1_HUB75_COLOR_LOOP_SOLID must be one of red, green, blue, white, black"
                .to_string(),
        ),
    }
}

fn solid_rgba(red: u8, green: u8, blue: u8) -> Vec<u8> {
    let mut frame = Vec::with_capacity((WIDTH * HEIGHT * 4) as usize);
    for _ in 0..(WIDTH * HEIGHT) {
        frame.extend_from_slice(&[red, green, blue, 255]);
    }
    frame
}

fn format_driver_error(error: RuntimeMatrixDriverError) -> String {
    format!("{error:?}")
}
