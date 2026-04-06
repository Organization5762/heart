mod config;
mod pi5_pinout;
mod pi5_pio_programs_generated;
pub mod strategy;
mod tuning;
mod worker;

pub use config::WiringProfile;
pub use strategy::pi5_simple_scan::{
    PackedScanFrame, PackedScanFrameStats, Pi5ScanConfig, Pi5ScanTiming, Pi5SimpleProbeMode,
};
pub use worker::Pi5SimpleProbeSession;

pub const MATRIX_RUNTIME_VERSION: &str = env!("CARGO_PKG_VERSION");
