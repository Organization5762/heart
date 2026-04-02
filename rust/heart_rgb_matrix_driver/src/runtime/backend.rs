use std::time::Duration;

#[cfg(not(test))]
use std::fs;
#[cfg(not(test))]
use std::path::Path;

use super::config::{MatrixConfigNative, WiringProfile};
use super::frame::FrameBuffer;
use super::tuning::runtime_tuning;

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
        match config.wiring {
            WiringProfile::AdafruitHatPwm => "pi4-adafruit-hat-pwm",
            WiringProfile::AdafruitHat => "pi4-adafruit-hat",
            WiringProfile::AdafruitTripleHat => "pi4-adafruit-triple-hat",
        }
        .to_string(),
    ))
}

fn build_pi5_backend(
    _config: &MatrixConfigNative,
) -> Result<(Box<dyn MatrixBackend>, String), String> {
    Err(
        "The native Pi 5 HUB75 backend is not available in the runtime build. Piomatter remains bench/parity tooling only."
            .to_string(),
    )
}
