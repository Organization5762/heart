use std::convert::TryFrom;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ColorOrder {
    Rgb,
    Gbr,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
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
        wiring: WiringProfile,
        panel_rows: u16,
        panel_cols: u16,
        chain_length: u16,
        parallel: u8,
        color_order: ColorOrder,
    ) -> Result<Self, String> {
        let config = Self {
            wiring,
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            color_order,
        };
        config.validate()?;
        Ok(config)
    }

    pub(crate) fn width(&self) -> Result<u32, String> {
        u32::from(self.panel_cols)
            .checked_mul(u32::from(self.chain_length))
            .ok_or_else(|| "Matrix width exceeds supported dimensions.".to_string())
    }

    pub(crate) fn height(&self) -> Result<u32, String> {
        u32::from(self.panel_rows)
            .checked_mul(u32::from(self.parallel))
            .ok_or_else(|| "Matrix height exceeds supported dimensions.".to_string())
    }

    pub(crate) fn frame_len(&self) -> Result<usize, String> {
        expected_rgb888_size(self.width()?, self.height()?)
            .ok_or_else(|| "Matrix RGB888 frame size exceeds supported dimensions.".to_string())
    }

    pub(crate) fn panel_count(&self) -> Result<u32, String> {
        u32::from(self.chain_length)
            .checked_mul(u32::from(self.parallel))
            .ok_or_else(|| "Matrix panel count exceeds supported dimensions.".to_string())
    }

    fn validate(&self) -> Result<(), String> {
        if self.panel_rows == 0 || self.panel_cols == 0 {
            return Err("panel_rows and panel_cols must be non-zero.".to_string());
        }
        if self.chain_length == 0 {
            return Err("chain_length must be at least 1.".to_string());
        }
        if self.parallel == 0 {
            return Err("parallel must be at least 1.".to_string());
        }
        let _ = self.width()?;
        let _ = self.height()?;
        let _ = self.frame_len()?;
        let _ = self.panel_count()?;
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WiringProfile {
    AdafruitHatPwm,
    ElectroDragonP0,
    Regular,
}

impl TryFrom<&str> for WiringProfile {
    type Error = String;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        match value {
            "adafruit_hat_pwm" => Ok(Self::AdafruitHatPwm),
            "electrodragon" | "electrodragon_p0" => Ok(Self::ElectroDragonP0),
            "regular" => Ok(Self::Regular),
            _ => Err(format!("Unsupported wiring profile '{value}'.")),
        }
    }
}

pub(crate) fn expected_rgba_size(width: u32, height: u32) -> Option<usize> {
    let pixels = width.checked_mul(height)?;
    let bytes = pixels.checked_mul(4)?;
    usize::try_from(bytes).ok()
}

pub(crate) fn expected_rgb888_size(width: u32, height: u32) -> Option<usize> {
    let pixels = width.checked_mul(height)?;
    let bytes = pixels.checked_mul(3)?;
    usize::try_from(bytes).ok()
}
