use std::convert::TryFrom;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WiringProfile {
    AdafruitHatPwm,
}

impl TryFrom<&str> for WiringProfile {
    type Error = String;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        match value {
            "adafruit_hat_pwm" => Ok(Self::AdafruitHatPwm),
            _ => Err(format!("Unsupported wiring profile '{value}'.")),
        }
    }
}

pub(crate) fn expected_rgba_size(width: u32, height: u32) -> Option<usize> {
    let pixels = width.checked_mul(height)?;
    let bytes = pixels.checked_mul(4)?;
    usize::try_from(bytes).ok()
}
