use std::convert::TryFrom;

pub(crate) const MATRIX_DRIVER_WIDTH_OVERFLOW_ERROR: &str =
    "Matrix geometry exceeds supported dimensions.";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum WiringProfile {
    AdafruitHatPwm,
    AdafruitHat,
    AdafruitTripleHat,
}

impl TryFrom<&str> for WiringProfile {
    type Error = String;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        match value {
            "adafruit_hat_pwm" => Ok(Self::AdafruitHatPwm),
            "adafruit_hat" => Ok(Self::AdafruitHat),
            "adafruit_triple_hat" => Ok(Self::AdafruitTripleHat),
            _ => Err(format!("Unsupported wiring profile '{value}'.")),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ColorOrder {
    Rgb,
    Gbr,
}

impl TryFrom<&str> for ColorOrder {
    type Error = String;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        match value {
            "rgb" => Ok(Self::Rgb),
            "gbr" => Ok(Self::Gbr),
            _ => Err(format!("Unsupported color order '{value}'.")),
        }
    }
}

#[derive(Clone, Debug)]
pub(crate) struct MatrixConfigNative {
    pub(crate) wiring: WiringProfile,
    pub(crate) panel_rows: u16,
    pub(crate) panel_cols: u16,
    pub(crate) chain_length: u16,
    pub(crate) parallel: u8,
    pub(crate) color_order: ColorOrder,
}

impl MatrixConfigNative {
    pub(crate) fn new(
        wiring: String,
        panel_rows: u16,
        panel_cols: u16,
        chain_length: u16,
        parallel: u8,
        color_order: String,
    ) -> Result<Self, String> {
        let config = Self {
            wiring: WiringProfile::try_from(wiring.as_str())?,
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            color_order: ColorOrder::try_from(color_order.as_str())?,
        };
        config.validate()?;
        Ok(config)
    }

    pub(crate) fn width(&self) -> Result<u32, String> {
        u32::from(self.panel_cols)
            .checked_mul(u32::from(self.chain_length))
            .ok_or_else(|| MATRIX_DRIVER_WIDTH_OVERFLOW_ERROR.to_string())
    }

    pub(crate) fn height(&self) -> Result<u32, String> {
        u32::from(self.panel_rows)
            .checked_mul(u32::from(self.parallel))
            .ok_or_else(|| MATRIX_DRIVER_WIDTH_OVERFLOW_ERROR.to_string())
    }

    pub(crate) fn frame_len(&self) -> Result<usize, String> {
        expected_rgba_size(self.width()?, self.height()?)
            .ok_or_else(|| MATRIX_DRIVER_WIDTH_OVERFLOW_ERROR.to_string())
    }

    fn validate(&self) -> Result<(), String> {
        if !matches!(self.panel_rows, 16 | 32 | 64) {
            return Err(format!(
                "Unsupported panel_rows {}. Expected one of 16, 32, or 64.",
                self.panel_rows
            ));
        }
        if !matches!(self.panel_cols, 32 | 64) {
            return Err(format!(
                "Unsupported panel_cols {}. Expected 32 or 64.",
                self.panel_cols
            ));
        }
        if self.chain_length == 0 {
            return Err("chain_length must be at least 1.".to_string());
        }
        if self.parallel == 0 {
            return Err("parallel must be at least 1.".to_string());
        }
        Ok(())
    }
}

pub(crate) fn expected_rgba_size(width: u32, height: u32) -> Option<usize> {
    let pixels = width.checked_mul(height)?;
    let bytes = pixels.checked_mul(4)?;
    usize::try_from(bytes).ok()
}
