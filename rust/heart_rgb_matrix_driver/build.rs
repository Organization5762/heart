use std::env;

fn main() {
    println!("cargo:rerun-if-changed=pio/pi5_simple_hub75.pio");
    println!("cargo:rerun-if-changed=pio/pi5_resident_parser.pio");
    println!("cargo:rerun-if-changed=pio/piomatter_row_compact_tight_engine_parity.pio");
    println!("cargo:rerun-if-changed=pio/piomatter_row_counted_engine_parity.pio");
    println!("cargo:rerun-if-changed=pio/piomatter_row_hybrid_engine_parity.pio");
    println!("cargo:rerun-if-changed=pio/piomatter_row_window_engine_parity.pio");
    let _ = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
    let _ = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
}
