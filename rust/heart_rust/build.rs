use std::env;

fn main() {
    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();

    println!("cargo:rerun-if-changed=native/pi5_pio_scan_shim.c");
    println!("cargo:rerun-if-changed=native/pi5_pio_shim.c");

    if target_arch == "aarch64" && target_os == "linux" {
        let out_dir = env::var("OUT_DIR").expect("OUT_DIR should be available during build");
        cc::Build::new()
            .file("native/pi5_pio_shim.c")
            .include("/usr/include/piolib")
            .compile("heart_pi5_pio_shim");
        cc::Build::new()
            .file("native/pi5_pio_scan_shim.c")
            .include("/usr/include/piolib")
            .compile("heart_pi5_pio_scan_shim");
        println!("cargo:rustc-link-search=native={out_dir}");
        println!("cargo:rustc-link-lib=static=heart_pi5_pio_shim");
        println!("cargo:rustc-link-lib=static=heart_pi5_pio_scan_shim");
        println!("cargo:rustc-link-lib=pio");
    }
}
