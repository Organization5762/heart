use std::time::Duration;

#[cfg(not(test))]
use std::fs;
use std::path::Path;

use super::config::MatrixConfigNative;
use super::frame::FrameBuffer;
use super::rp1_hub75::Rp1Hub75Backend;
use super::rp1_sram_rgb888::Rp1SramRgb888Backend;
use super::tuning::runtime_tuning;

const PI5_BACKEND_ENV_VAR: &str = "HEART_PI5_MATRIX_BACKEND";
const PI5_BACKEND_AUTO: &str = "auto";
const PI5_BACKEND_RP1_HUB75: &str = "rp1-hub75";
const PI5_BACKEND_RP1_SRAM_RGB888: &str = "rp1-sram-rgb888";
const RP1_HUB75_DEVICE_PATH: &str = "/dev/rp1-hub75";

pub(crate) trait MatrixBackend: Send {
    fn refresh_interval(&self) -> Duration;
    // Backends with a resident hardware loop keep scanning after a single
    // submit, so the generic runtime worker should wait for new work instead of
    // re-rendering the same active frame in software.
    fn owns_refresh_loop(&self) -> bool {
        false
    }
    fn render(&mut self, frame: &FrameBuffer) -> Result<(), String>;
}

pub(crate) fn build_backend(
    config: &MatrixConfigNative,
) -> Result<(Box<dyn MatrixBackend>, String), String> {
    match detect_pi_model() {
        Some(5) => build_pi5_backend(config),
        Some(4) => build_pi4_backend(config),
        Some(version) => Err(format!("Unsupported Pi model {version} for HUB75 runtime.")),
        None => Ok((
            Box::new(SimulatedBackend) as Box<dyn MatrixBackend>,
            "simulated".to_string(),
        )),
    }
}

#[derive(Debug)]
struct SimulatedBackend;

impl MatrixBackend for SimulatedBackend {
    fn refresh_interval(&self) -> Duration {
        Duration::from_millis(runtime_tuning().matrix_simulated_refresh_interval_ms)
    }

    fn render(&mut self, _frame: &FrameBuffer) -> Result<(), String> {
        Ok(())
    }
}

#[derive(Debug)]
struct Pi4GpioBackend;

impl MatrixBackend for Pi4GpioBackend {
    fn refresh_interval(&self) -> Duration {
        Duration::from_millis(runtime_tuning().matrix_pi4_refresh_interval_ms)
    }

    fn render(&mut self, _frame: &FrameBuffer) -> Result<(), String> {
        Ok(())
    }
}

#[cfg(test)]
fn detect_pi_model() -> Option<u8> {
    None
}

#[cfg(not(test))]
fn detect_pi_model() -> Option<u8> {
    let model_path = Path::new("/proc/device-tree/model");
    let model = fs::read_to_string(model_path).ok()?;
    if let Some(version_text) = model.split("Raspberry Pi ").nth(1) {
        let version_string: String = version_text
            .chars()
            .take_while(|character| character.is_ascii_digit())
            .collect();
        return version_string.parse::<u8>().ok();
    }
    None
}

fn build_pi4_backend(
    config: &MatrixConfigNative,
) -> Result<(Box<dyn MatrixBackend>, String), String> {
    if config.parallel > 3 {
        return Err(format!(
            "Pi 4 backend supports parallel values up to 3, received {}.",
            config.parallel
        ));
    }
    Ok((
        Box::new(Pi4GpioBackend) as Box<dyn MatrixBackend>,
        "pi4-adafruit-hat-pwm".to_string(),
    ))
}

fn build_pi5_backend(
    config: &MatrixConfigNative,
) -> Result<(Box<dyn MatrixBackend>, String), String> {
    let requested_backend = std::env::var(PI5_BACKEND_ENV_VAR)
        .unwrap_or_else(|_| PI5_BACKEND_AUTO.to_string())
        .trim()
        .to_ascii_lowercase();
    match requested_backend.as_str() {
        "" | PI5_BACKEND_AUTO => {
            if Path::new(RP1_HUB75_DEVICE_PATH).exists() {
                build_pi5_rp1_hub75_backend(config)
            } else {
                Err(format!(
                    "{RP1_HUB75_DEVICE_PATH} is not present. Set {PI5_BACKEND_ENV_VAR}={PI5_BACKEND_RP1_SRAM_RGB888} to write Heart frames into the external RP1 SRAM RGB888 scanner buffer."
                ))
            }
        }
        PI5_BACKEND_RP1_HUB75 => build_pi5_rp1_hub75_backend(config),
        PI5_BACKEND_RP1_SRAM_RGB888 | "sram-rgb888" => {
            Ok((
                Box::new(Rp1SramRgb888Backend::new(config)?) as Box<dyn MatrixBackend>,
                "pi5-rp1-sram-rgb888".to_string(),
            ))
        }
        other => Err(format!(
            "Unsupported {PI5_BACKEND_ENV_VAR}={other:?}. Use {PI5_BACKEND_AUTO:?}, {PI5_BACKEND_RP1_HUB75:?}, or {PI5_BACKEND_RP1_SRAM_RGB888:?}."
        )),
    }
}

fn build_pi5_rp1_hub75_backend(
    config: &MatrixConfigNative,
) -> Result<(Box<dyn MatrixBackend>, String), String> {
    Ok((
        Box::new(Rp1Hub75Backend::new(config)?) as Box<dyn MatrixBackend>,
        "pi5-rp1-hub75-packer".to_string(),
    ))
}
