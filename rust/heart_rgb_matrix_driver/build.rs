use std::env;

fn main() {
    println!("cargo:rerun-if-changed=pio/pi5_raw_byte_pull.pio");
    println!("cargo:rerun-if-changed=pio/round_robin.pio");
    println!("cargo:rerun-if-changed=tools/generate_pi5_pio_programs.py");
    let _ = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
    let _ = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
}
