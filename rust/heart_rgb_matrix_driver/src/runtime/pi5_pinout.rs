use std::collections::BTreeSet;

use super::config::WiringProfile;

const LEGACY_OE_SYNC_GPIO: u32 = 4;

fn probe_log(message: impl AsRef<str>) {
    if std::env::var("HEART_PI5_SIMPLE_PROBE_LOG")
        .map(|value| value != "0")
        .unwrap_or(true)
    {
        eprintln!("[pi5_simple_probe::pinout] {}", message.as_ref());
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) struct Pi5ScanPinout {
    rgb_gpios: [u8; 6],
    addr_gpios: [u8; 5],
    oe_gpio: u32,
    lat_gpio: u32,
    clock_gpio: u32,
}

impl Pi5ScanPinout {
    pub(crate) fn for_wiring(wiring: WiringProfile) -> Result<Self, String> {
        probe_log(format!("resolving pinout for wiring={wiring:?}"));
        match wiring {
            WiringProfile::AdafruitHatPwm => Ok(Self {
                rgb_gpios: [5, 13, 6, 12, 16, 23],
                addr_gpios: [22, 26, 27, 20, 24],
                oe_gpio: 18,
                lat_gpio: 21,
                clock_gpio: 17,
            }),
        }
    }

    pub(crate) fn used_panel_gpios(&self) -> Vec<u16> {
        let mut gpios = BTreeSet::new();
        for gpio in self.rgb_gpios {
            gpios.insert(u16::from(gpio));
        }
        for gpio in self.addr_gpios {
            gpios.insert(u16::from(gpio));
        }
        gpios.insert(self.oe_gpio as u16);
        gpios.insert(self.lat_gpio as u16);
        gpios.insert(self.clock_gpio as u16);
        if self.oe_gpio == 18 {
            gpios.insert(LEGACY_OE_SYNC_GPIO as u16);
        }
        let gpios: Vec<u16> = gpios.into_iter().collect();
        probe_log(format!("used_panel_gpios={gpios:?}"));
        gpios
    }

    pub(crate) fn address_bits(&self, row_pair: usize, pin_word_shift: u32) -> u32 {
        let mut bits = 0_u32;
        for (bit_index, gpio) in self.addr_gpios.iter().enumerate() {
            if (row_pair & (1 << bit_index)) != 0 {
                bits |= 1_u32 << (u32::from(*gpio) - pin_word_shift);
            }
        }
        bits
    }

    pub(crate) fn oe_inactive_bits(&self, pin_word_shift: u32) -> u32 {
        let mut bits = 0_u32;
        bits |= 1_u32 << (self.oe_gpio - pin_word_shift);
        if self.oe_gpio == 18_u32 && LEGACY_OE_SYNC_GPIO >= pin_word_shift {
            bits |= 1_u32 << (LEGACY_OE_SYNC_GPIO - pin_word_shift);
        }
        bits
    }

    pub(crate) fn oe_active_bits(&self, _pin_word_shift: u32) -> u32 {
        0
    }

    pub(crate) fn lat_bits(&self, pin_word_shift: u32) -> u32 {
        1_u32 << (self.lat_gpio - pin_word_shift)
    }

    pub(crate) fn rgb_gpios(&self) -> [u8; 6] {
        self.rgb_gpios
    }

    pub(crate) fn clock_gpio(&self) -> u32 {
        self.clock_gpio
    }
}
