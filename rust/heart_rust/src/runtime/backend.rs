use std::fs::OpenOptions;
use std::io::ErrorKind;
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;

#[cfg(not(test))]
use std::fs;

use super::config::{MatrixConfigNative, WiringProfile};
use super::device::describe_device_permissions;
use super::frame::FrameBuffer;
use super::pi5_scan::{PackedScanFrame, Pi5PioScanTransport, Pi5ScanConfig};
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

#[derive(Debug)]
struct Pi5PioBackend {
    scan_config: Pi5ScanConfig,
    transport: Pi5PioScanTransport,
    packed_frame: Option<Arc<PackedScanFrame>>,
    last_frame_identity: Option<(usize, u64)>,
}

impl Pi5PioBackend {
    fn new(scan_config: Pi5ScanConfig) -> Result<Self, String> {
        let transport = Pi5PioScanTransport::new(
            scan_config.estimated_word_count()?,
            scan_config.pinout(),
            scan_config.timing(),
        )?;
        Ok(Self {
            scan_config,
            transport,
            packed_frame: None,
            last_frame_identity: None,
        })
    }

    fn ensure_packed_frame(&mut self, frame: &FrameBuffer) -> Result<(), String> {
        let frame_identity = frame.identity();
        if self.last_frame_identity == Some(frame_identity) && self.packed_frame.is_some() {
            return Ok(());
        }
        let (packed_frame, _stats) = PackedScanFrame::pack_frame(&self.scan_config, frame)?;
        self.packed_frame = Some(Arc::new(packed_frame));
        self.last_frame_identity = Some(frame_identity);
        Ok(())
    }
}

impl MatrixBackend for Pi5PioBackend {
    fn refresh_interval(&self) -> Duration {
        Duration::ZERO
    }

    fn owns_refresh_loop(&self) -> bool {
        true
    }

    fn render(&mut self, frame: &FrameBuffer) -> Result<(), String> {
        self.ensure_packed_frame(frame)?;
        let frame_identity = frame.identity();
        let packed_frame = self
            .packed_frame
            .as_ref()
            .ok_or_else(|| "Pi 5 backend has no packed scan buffer.".to_string())?;
        self.transport
            .submit_async(frame_identity, Arc::clone(packed_frame))?;
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
    config: &MatrixConfigNative,
) -> Result<(Box<dyn MatrixBackend>, String), String> {
    if config.wiring == WiringProfile::AdafruitHat {
        return Err(
            "Pi 5 backend does not support AdafruitHat because the packed GPIO words rebase GPIO 5..27 and require OE within that window."
                .to_string(),
        );
    }
    let scan_config = Pi5ScanConfig::from_matrix_config(
        config.wiring,
        config.panel_rows,
        config.panel_cols,
        config.chain_length,
        config.parallel,
    )?;
    if config.wiring == WiringProfile::AdafruitTripleHat {
        return Err("Pi 5 backend does not support AdafruitTripleHat in v1.".to_string());
    }

    let pio_path = Path::new("/dev/pio0");
    if let Err(error) = OpenOptions::new().read(true).write(true).open(pio_path) {
        if error.kind() == ErrorKind::NotFound {
            return Err(
                "Pi 5 backend requires /dev/pio0. Update Raspberry Pi firmware and kernel until the PIO device is present."
                    .to_string(),
            );
        }
        let details = describe_device_permissions(pio_path);
        return Err(format!(
            "Pi 5 backend requires read/write access to /dev/pio0: {error}. {details} Configure the documented udev rule and ensure the runtime user is in the gpio group."
        ));
    }

    Ok((
        Box::new(Pi5PioBackend::new(scan_config)?) as Box<dyn MatrixBackend>,
        match config.wiring {
            WiringProfile::AdafruitHatPwm => "pi5-adafruit-hat-pwm",
            WiringProfile::AdafruitHat => "pi5-adafruit-hat",
            WiringProfile::AdafruitTripleHat => unreachable!(),
        }
        .to_string(),
    ))
}
