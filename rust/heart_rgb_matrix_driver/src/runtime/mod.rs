mod backend;
mod config;
mod driver;
mod frame;
mod pi5_pio_programs_generated;
mod pi5_pio_sim;
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
pub(crate) use pi5_pio_sim::{
    build_piomatter_row_compact_engine_parity_program_opcodes,
    build_piomatter_row_compact_tight_engine_parity_program_opcodes,
    build_piomatter_row_counted_engine_parity_program_opcodes,
    build_piomatter_row_hybrid_engine_parity_program_opcodes,
    build_piomatter_row_runs_engine_parity_program_opcodes,
    build_piomatter_row_window_engine_parity_program_opcodes,
    build_piomatter_row_split_engine_parity_program_opcodes,
    build_piomatter_row_repeat_engine_parity_program_opcodes,
    build_piomatter_symbol_command_parity_program_opcodes, build_simple_hub75_program_opcodes,
    estimate_simple_hub75_frame_timing, gpio_is_high,
    piomatter_row_compact_engine_parity_program_info,
    piomatter_row_compact_tight_engine_parity_program_info,
    piomatter_row_counted_engine_parity_program_info,
    piomatter_row_hybrid_engine_parity_program_info,
    piomatter_row_runs_engine_parity_program_info,
    piomatter_row_window_engine_parity_program_info,
    piomatter_row_split_engine_parity_program_info,
    piomatter_symbol_command_parity_program_info,
    piomatter_row_repeat_engine_parity_program_info, pio_program_info_for_format,
    simulate_simple_hub75_group, Pi5PioInstructionSummary, Pi5PioProgramInfo, Pi5PioProgramKind,
    Pi5PioSimulation, Pi5PioTimingEstimate, Pi5PioTraceStep,
};
#[allow(unused_imports)]
pub(crate) use pi5_scan::{
    build_simple_group_words_for_rgba, build_simple_smoke_group_words, PackedScanFrame,
    PackedScanFrameStats, Pi5PioScanTransport, Pi5ScanConfig, Pi5ScanFormat, Pi5ScanGroupTrace,
    Pi5ScanTiming,
};
#[allow(unused_imports)]
pub use scene::{SceneManagerCore, SceneSnapshotCore};
#[allow(unused_imports)]
pub use stats::MatrixStatsCore;

pub const MATRIX_RUNTIME_VERSION: &str = env!("CARGO_PKG_VERSION");
