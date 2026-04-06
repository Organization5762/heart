#![allow(dead_code)]

pub(crate) const PI5_PIO_RAW_BYTE_PULL_PROGRAM_LENGTH: usize = 2;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_WRAP_TARGET: u8 = 0;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_WRAP: u8 = 1;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_SIDESET_PIN_COUNT: u8 = 0;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_SIDESET_OPTIONAL: bool = false;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_OUT_PIN_BASE: u8 = 0;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_OUT_PIN_COUNT: u8 = 28;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_OUT_SHIFT_RIGHT: bool = false;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_AUTO_PULL: bool = false;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_PULL_THRESHOLD: u8 = 28;
pub(crate) const PI5_PIO_RAW_BYTE_PULL_DELAY_PATCH_INDICES: [usize; 0] = [];
pub(crate) const PI5_PIO_RAW_BYTE_PULL_BASE_PROGRAM: [u16; 2] = [0x80a0, 0x601c];

pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_PROGRAM_LENGTH: usize = 11;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_WRAP_TARGET: u8 = 0;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_WRAP: u8 = 10;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_SIDESET_PIN_COUNT: u8 = 0;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_SIDESET_OPTIONAL: bool = false;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_OUT_PIN_BASE: u8 = 0;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_OUT_PIN_COUNT: u8 = 31;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_OUT_SHIFT_RIGHT: bool = false;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_AUTO_PULL: bool = true;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_PULL_THRESHOLD: u8 = 32;
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_DELAY_PATCH_INDICES: [usize; 0] = [];
pub(crate) const PI5_PIO_ROUND_ROBIN_OUT_BASE_PROGRAM: [u16; 11] = [0x20d0, 0x6021, 0x0024, 0x0009, 0x601f, 0xa042, 0xa042, 0xa042, 0x0001, 0xc050, 0xc011];
