mod backend;
mod config;
mod device;
mod driver;
mod frame;
mod pi5_scan;
mod queue;
mod scene;
mod stats;
mod tuning;

#[cfg(test)]
#[allow(dead_code, unused_imports)]
mod tests;

#[allow(unused_imports)]
pub(crate) use config::{ColorOrder, WiringProfile};
#[allow(unused_imports)]
pub use driver::{MatrixDriverCore, MatrixDriverError};
#[allow(unused_imports)]
pub(crate) use frame::{FrameBuffer, FrameBufferPool};
#[allow(unused_imports)]
pub(crate) use pi5_scan::{
    PackedScanFrame, PackedScanFrameStats, Pi5KernelResidentLoop, Pi5PioScanTransport,
    Pi5ScanConfig, Pi5ScanTiming,
};
#[allow(unused_imports)]
pub use scene::{SceneManagerCore, SceneSnapshotCore};
#[allow(unused_imports)]
pub use stats::MatrixStatsCore;

pub const MATRIX_RUNTIME_VERSION: &str = env!("CARGO_PKG_VERSION");
