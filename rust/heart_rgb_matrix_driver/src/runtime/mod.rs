mod backend;
mod config;
mod driver;
mod frame;
mod pi5_pinout;
mod pi5_pio_programs_generated;
mod queue;
mod rp1_hub75;
mod rp1_sram_rgb888;
mod stats;
pub mod strategy;
mod tuning;
mod worker;

pub use config::{ColorOrder, WiringProfile};
pub use driver::{MatrixDriverCore, MatrixDriverError};
pub use rp1_hub75::{
    read_pack_stats, read_pack_stats_from, read_present_stats, read_present_stats_from,
    read_worker_status, read_worker_status_from, Rp1Hub75PresentStats, Rp1Hub75Stats,
    Rp1Hub75WorkerStatus,
};
pub use stats::MatrixStatsCore;
pub use strategy::pi5_simple_scan::{
    PackedScanFrame, PackedScanFrameStats, Pi5ScanConfig, Pi5ScanTiming, Pi5SimpleProbeMode,
};
pub use worker::Pi5SimpleProbeSession;

pub const MATRIX_RUNTIME_VERSION: &str = env!("CARGO_PKG_VERSION");
