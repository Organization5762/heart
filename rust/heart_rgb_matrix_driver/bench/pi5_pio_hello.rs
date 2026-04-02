use std::env;
use std::ffi::{c_char, CStr};
use std::process::ExitCode;
use std::thread;
use std::time::{Duration, Instant};

const DEFAULT_GPIO: u32 = 17;
const DEFAULT_CLOCK_DIVIDER: f32 = 1.0;
const DEFAULT_HOLD_SECONDS: f32 = 8.0;
const DEFAULT_TOGGLE_PERIOD_MS: u64 = 500;
const ERROR_BUFFER_BYTES: usize = 256;
const HELLO_MODE_FIFO: u32 = 0;
const HELLO_MODE_AUTOBLINK: u32 = 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum HelloMode {
    Fifo,
    Autoblink,
}

#[derive(Clone, Copy, Debug)]
struct HelloOptions {
    gpio: u32,
    clock_divider: f32,
    hold_seconds: f32,
    toggle_period_ms: u64,
    initial_value: u32,
    mode: HelloMode,
}

#[repr(C)]
struct Pi5PioHelloHandle {
    _private: [u8; 0],
}

#[link(name = "heart_pi5_pio_hello_shim", kind = "static")]
#[link(name = "pio")]
unsafe extern "C" {
    fn heart_pi5_pio_hello_open(
        gpio: u32,
        clock_divider: f32,
        mode: u32,
        out_handle: *mut *mut Pi5PioHelloHandle,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_pio_hello_put(
        handle: *mut Pi5PioHelloHandle,
        value: u32,
        error_buf: *mut c_char,
        error_buf_len: usize,
    ) -> i32;
    fn heart_pi5_pio_hello_close(handle: *mut Pi5PioHelloHandle);
}

struct HelloTransport {
    handle: *mut Pi5PioHelloHandle,
}

impl HelloTransport {
    fn open(gpio: u32, clock_divider: f32, mode: HelloMode) -> Result<Self, String> {
        let mut handle = std::ptr::null_mut();
        let mut error_buf = vec![0_u8; ERROR_BUFFER_BYTES];
        let result = unsafe {
            heart_pi5_pio_hello_open(
                gpio,
                clock_divider,
                match mode {
                    HelloMode::Fifo => HELLO_MODE_FIFO,
                    HelloMode::Autoblink => HELLO_MODE_AUTOBLINK,
                },
                &mut handle,
                error_buf.as_mut_ptr().cast::<c_char>(),
                error_buf.len(),
            )
        };
        if result != 0 {
            return Err(error_from_buf(
                &error_buf,
                "Failed to open Pi 5 hello PIO transport",
            ));
        }
        Ok(Self { handle })
    }

    fn put(&self, value: u32) -> Result<(), String> {
        let mut error_buf = vec![0_u8; ERROR_BUFFER_BYTES];
        let result = unsafe {
            heart_pi5_pio_hello_put(
                self.handle,
                value,
                error_buf.as_mut_ptr().cast::<c_char>(),
                error_buf.len(),
            )
        };
        if result != 0 {
            return Err(error_from_buf(
                &error_buf,
                "Failed to submit Pi 5 hello PIO value",
            ));
        }
        Ok(())
    }
}

impl Drop for HelloTransport {
    fn drop(&mut self) {
        if !self.handle.is_null() {
            unsafe { heart_pi5_pio_hello_close(self.handle) };
        }
    }
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let options = parse_args(env::args().skip(1).collect())?;
    let transport = HelloTransport::open(options.gpio, options.clock_divider, options.mode)?;
    let deadline = Instant::now() + Duration::from_secs_f32(options.hold_seconds);
    let mut value = options.initial_value & 1;
    let period = Duration::from_millis(options.toggle_period_ms);

    println!(
        "pi5_pio_hello gpio={} clock_divider={} hold_seconds={} toggle_period_ms={} initial_value={}",
        options.gpio,
        options.clock_divider,
        options.hold_seconds,
        options.toggle_period_ms,
        value,
    );

    if options.mode == HelloMode::Autoblink {
        while Instant::now() < deadline {
            thread::sleep(period);
        }
    } else {
        while Instant::now() < deadline {
            transport.put(value)?;
            thread::sleep(period);
            value ^= 1;
        }
    }
    Ok(())
}

fn parse_args(args: Vec<String>) -> Result<HelloOptions, String> {
    let mut options = HelloOptions {
        gpio: DEFAULT_GPIO,
        clock_divider: DEFAULT_CLOCK_DIVIDER,
        hold_seconds: DEFAULT_HOLD_SECONDS,
        toggle_period_ms: DEFAULT_TOGGLE_PERIOD_MS,
        initial_value: 1,
        mode: HelloMode::Fifo,
    };
    let mut args = args.into_iter();
    while let Some(arg) = args.next() {
        let next = |args: &mut std::vec::IntoIter<String>, flag: &str| {
            args.next()
                .ok_or_else(|| format!("Missing value for {flag}."))
        };
        match arg.as_str() {
            "--gpio" => options.gpio = parse_value(&next(&mut args, "--gpio")?, "--gpio")?,
            "--clock-divider" => {
                options.clock_divider =
                    parse_value(&next(&mut args, "--clock-divider")?, "--clock-divider")?
            }
            "--hold-seconds" => {
                options.hold_seconds =
                    parse_value(&next(&mut args, "--hold-seconds")?, "--hold-seconds")?
            }
            "--toggle-period-ms" => {
                options.toggle_period_ms = parse_value(
                    &next(&mut args, "--toggle-period-ms")?,
                    "--toggle-period-ms",
                )?
            }
            "--initial-value" => {
                options.initial_value =
                    parse_value(&next(&mut args, "--initial-value")?, "--initial-value")?
            }
            "--mode" => {
                options.mode = parse_mode(&next(&mut args, "--mode")?)?;
            }
            "--help" => {
                print_help();
                std::process::exit(0);
            }
            other => return Err(format!("Unknown argument {other:?}. Use --help for usage.")),
        }
    }
    Ok(options)
}

fn parse_mode(value: &str) -> Result<HelloMode, String> {
    match value {
        "fifo" => Ok(HelloMode::Fifo),
        "autoblink" => Ok(HelloMode::Autoblink),
        _ => Err(format!(
            "Invalid value {value:?} for --mode. Expected fifo or autoblink."
        )),
    }
}

fn parse_value<T: std::str::FromStr>(value: &str, flag: &str) -> Result<T, String> {
    value
        .parse::<T>()
        .map_err(|_| format!("Invalid value {value:?} for {flag}."))
}

fn error_from_buf(error_buf: &[u8], fallback: &str) -> String {
    let cstr = CStr::from_bytes_until_nul(error_buf)
        .ok()
        .and_then(|value| value.to_str().ok())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or(fallback);
    cstr.to_string()
}

fn print_help() {
    println!("Usage: pi5_pio_hello [options]");
    println!("  --gpio <u32>             default 17");
    println!("  --clock-divider <f32>    default 1.0");
    println!("  --hold-seconds <f32>     default 8");
    println!("  --toggle-period-ms <u64> default 500");
    println!("  --initial-value <u32>    default 1");
    println!("  --mode <fifo|autoblink>  default fifo");
}
