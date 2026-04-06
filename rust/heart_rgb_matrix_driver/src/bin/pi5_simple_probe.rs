use std::env;
use std::time::{Duration, Instant};

use heart_rgb_matrix_driver::{Pi5ScanConfig, Pi5SimpleProbeMode, Pi5SimpleProbeSession};
use heart_rgb_matrix_driver::ProbeWiringProfile as WiringProfile;

fn probe_log(message: impl AsRef<str>) {
    if env::var("HEART_PI5_SIMPLE_PROBE_LOG")
        .map(|value| value != "0")
        .unwrap_or(true)
    {
        eprintln!("[pi5_simple_probe] {}", message.as_ref());
    }
}

fn wiring() -> Result<WiringProfile, String> {
    match env::var("HEART_PI5_SIMPLE_PROBE_WIRING")
        .unwrap_or_else(|_| "adafruit_hat_pwm".to_string())
        .to_ascii_lowercase()
        .as_str()
    {
        "adafruit_hat_pwm" | "pwm" => Ok(WiringProfile::AdafruitHatPwm),
        other => Err(format!("Unsupported HEART_PI5_SIMPLE_PROBE_WIRING={other}")),
    }
}

fn main() -> Result<(), String> {
    let seconds = env::var("HEART_PI5_SIMPLE_PROBE_SECONDS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(10);
    let frame_copies = env::var("HEART_PI5_SIMPLE_PROBE_FRAME_COPIES")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .filter(|value| *value >= 1)
        .unwrap_or(1);
    let wiring = wiring()?;
    let mode = Pi5SimpleProbeMode::RawBytePull;
    probe_log(format!(
        "starting mode={mode:?} wiring={wiring:?} seconds={seconds} frame_copies={frame_copies} panel=64x64 chain_length=1 parallel=1 pwm_bits=5"
    ));
    let config = Pi5ScanConfig::from_matrix_config(wiring, 64, 64, 1, 1)?
        .with_pwm_bits(5)?
        .with_clock_divider(1.0)?;
    probe_log(format!(
        "resolved config width={} height={} row_pairs={} timing={:?}",
        config.width()?,
        config.height()?,
        config.row_pairs()?,
        config.timing()
    ));
    let mut rgba = vec![0_u8; (config.width()? * config.height()? * 4) as usize];
    for pixel in rgba.chunks_exact_mut(4) {
        pixel[0] = 0xff;
        pixel[3] = 0xff;
    }
    probe_log(format!("built solid-red rgba bytes={}", rgba.len()));
    let (packed_frame, stats) = mode.pack_rgba_frame(&config, &rgba)?;
    let frame = packed_frame.repeated(frame_copies)?;
    probe_log(format!(
        "packed frame words={} bytes={} pack_us={}",
        frame.word_count(),
        frame.as_bytes().len(),
        stats.pack_duration.as_micros()
    ));
    let mut session = Pi5SimpleProbeSession::new(&config, frame.as_bytes().len())?;
    probe_log("session initialized");
    let deadline = Instant::now() + Duration::from_secs(seconds);
    let start = Instant::now();
    let mut submits = 0_u64;
    while Instant::now() < deadline {
        session.present(&frame)?;
        submits += 1;
        if submits == 1 || submits % 256 == 0 {
            probe_log(format!("presented_submits={submits}"));
        }
    }
    let frames = submits
        .checked_mul(frame_copies as u64)
        .ok_or_else(|| "Presented frame count overflowed.".to_string())?;
    println!(
        "frames={} submits={} elapsed_s={:.3} hz={:.2} words={} pack_us={}",
        frames,
        submits,
        start.elapsed().as_secs_f64(),
        frames as f64 / start.elapsed().as_secs_f64(),
        frame.word_count(),
        stats.pack_duration.as_micros()
    );
    Ok(())
}
