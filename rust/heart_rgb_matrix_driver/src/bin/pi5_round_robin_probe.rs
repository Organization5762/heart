use std::env;
use std::fs::OpenOptions;
use std::mem::size_of;
use std::os::fd::{AsRawFd, RawFd};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::thread;
use std::time::{Duration, Instant};

use heart_rgb_matrix_driver::{PackedScanFrame, Pi5ScanConfig, ProbeWiringProfile as WiringProfile};

#[path = "../runtime/pi5_pio_programs_generated.rs"]
mod generated;

const RP1_GPIO_FUNC_PIO: u16 = 7;
const RP1_PIO_ORIGIN_ANY: u16 = u16::MAX;
const RP1_PIO_DIR_TO_SM: u16 = 0;
const PIO_INSTR_BITS_IRQ: u16 = 0xc000;
const PROC_PIO_SM0_PINCTRL_OUT_BASE_LSB: u32 = 0;
const PROC_PIO_SM0_PINCTRL_SIDESET_BASE_LSB: u32 = 10;
const PROC_PIO_SM0_PINCTRL_OUT_COUNT_LSB: u32 = 20;
const PROC_PIO_SM0_PINCTRL_SIDESET_COUNT_LSB: u32 = 29;
const PROC_PIO_SM0_EXECCTRL_SIDE_EN_LSB: u32 = 30;
const PROC_PIO_SM0_EXECCTRL_WRAP_TOP_LSB: u32 = 12;
const PROC_PIO_SM0_EXECCTRL_WRAP_BOTTOM_LSB: u32 = 7;
const PROC_PIO_SM0_EXECCTRL_STATUS_SEL_LSB: u32 = 5;
const PROC_PIO_SM0_EXECCTRL_STATUS_N_LSB: u32 = 0;
const PROC_PIO_SM0_CLKDIV_INT_LSB: u32 = 16;
const PROC_PIO_SM0_CLKDIV_FRAC_LSB: u32 = 8;
const PROC_PIO_SM0_SHIFTCTRL_AUTOPULL_LSB: u32 = 17;
const PROC_PIO_SM0_SHIFTCTRL_OUT_SHIFTDIR_LSB: u32 = 19;
const PROC_PIO_SM0_SHIFTCTRL_PULL_THRESH_LSB: u32 = 25;
const PROC_PIO_SM0_SHIFTCTRL_FJOIN_TX_LSB: u32 = 30;
const IOC_NRBITS: u32 = 8;
const IOC_TYPEBITS: u32 = 8;
const IOC_SIZEBITS: u32 = 14;
const IOC_NRSHIFT: u32 = 0;
const IOC_TYPESHIFT: u32 = IOC_NRSHIFT + IOC_NRBITS;
const IOC_SIZESHIFT: u32 = IOC_TYPESHIFT + IOC_TYPEBITS;
const IOC_DIRSHIFT: u32 = IOC_SIZESHIFT + IOC_SIZEBITS;
const IOC_WRITE: u32 = 1;

use generated::{
    PI5_PIO_ROUND_ROBIN_OUT_AUTO_PULL, PI5_PIO_ROUND_ROBIN_OUT_BASE_PROGRAM,
    PI5_PIO_ROUND_ROBIN_OUT_OUT_PIN_BASE, PI5_PIO_ROUND_ROBIN_OUT_OUT_PIN_COUNT,
    PI5_PIO_ROUND_ROBIN_OUT_OUT_SHIFT_RIGHT, PI5_PIO_ROUND_ROBIN_OUT_PROGRAM_LENGTH,
    PI5_PIO_ROUND_ROBIN_OUT_PULL_THRESHOLD, PI5_PIO_ROUND_ROBIN_OUT_SIDESET_OPTIONAL,
    PI5_PIO_ROUND_ROBIN_OUT_SIDESET_PIN_COUNT, PI5_PIO_ROUND_ROBIN_OUT_WRAP,
    PI5_PIO_ROUND_ROBIN_OUT_WRAP_TARGET,
};

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmConfig {
    clkdiv: u32,
    execctrl: u32,
    shiftctrl: u32,
    pinctrl: u32,
}

#[repr(C)]
#[derive(Clone, Copy)]
struct Rp1PioAddProgram {
    num_instrs: u16,
    origin: u16,
    instrs: [u16; 32],
}

impl Default for Rp1PioAddProgram {
    fn default() -> Self {
        Self {
            num_instrs: 0,
            origin: 0,
            instrs: [0; 32],
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioRemoveProgram {
    num_instrs: u16,
    origin: u16,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmClaimArgs {
    mask: u16,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmInitArgs {
    sm: u16,
    initial_pc: u16,
    config: Rp1PioSmConfig,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmConfigXfer32Args {
    sm: u16,
    dir: u16,
    buf_size: u32,
    buf_count: u32,
}

#[repr(C)]
#[derive(Clone, Copy)]
struct Rp1PioSmXferData32Args {
    sm: u16,
    dir: u16,
    data_bytes: u32,
    data: *mut libc::c_void,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmExecArgs {
    sm: u16,
    instr: u16,
    blocking: u8,
    rsvd: u8,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmClearFifosArgs {
    sm: u16,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmSetPindirsArgs {
    sm: u16,
    rsvd: u16,
    dirs: u32,
    mask: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmSetEnabledArgs {
    mask: u16,
    enable: u8,
    rsvd: u8,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmRestartArgs {
    mask: u16,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1PioSmEnableSyncArgs {
    mask: u16,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1GpioInitArgs {
    gpio: u16,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct Rp1GpioSetFunctionArgs {
    gpio: u16,
    fn_: u16,
}

const fn ioc(dir: u32, type_: u32, nr: u32, size: u32) -> libc::c_ulong {
    ((dir << IOC_DIRSHIFT)
        | (type_ << IOC_TYPESHIFT)
        | (nr << IOC_NRSHIFT)
        | (size << IOC_SIZESHIFT)) as libc::c_ulong
}

const fn iow<T>(type_: u32, nr: u32) -> libc::c_ulong {
    ioc(IOC_WRITE, type_, nr, size_of::<T>() as u32)
}

const PIO_IOC_ADD_PROGRAM: libc::c_ulong = iow::<Rp1PioAddProgram>(102, 11);
const PIO_IOC_REMOVE_PROGRAM: libc::c_ulong = iow::<Rp1PioRemoveProgram>(102, 12);
const PIO_IOC_SM_CLAIM: libc::c_ulong = iow::<Rp1PioSmClaimArgs>(102, 20);
const PIO_IOC_SM_UNCLAIM: libc::c_ulong = iow::<Rp1PioSmClaimArgs>(102, 21);
const PIO_IOC_SM_INIT: libc::c_ulong = iow::<Rp1PioSmInitArgs>(102, 30);
const PIO_IOC_SM_EXEC: libc::c_ulong = iow::<Rp1PioSmExecArgs>(102, 32);
const PIO_IOC_SM_CLEAR_FIFOS: libc::c_ulong = iow::<Rp1PioSmClearFifosArgs>(102, 33);
const PIO_IOC_SM_SET_PINDIRS: libc::c_ulong = iow::<Rp1PioSmSetPindirsArgs>(102, 36);
const PIO_IOC_SM_SET_ENABLED: libc::c_ulong = iow::<Rp1PioSmSetEnabledArgs>(102, 37);
const PIO_IOC_SM_CONFIG_XFER32: libc::c_ulong = iow::<Rp1PioSmConfigXfer32Args>(102, 3);
const PIO_IOC_SM_XFER_DATA32: libc::c_ulong = iow::<Rp1PioSmXferData32Args>(102, 2);
const PIO_IOC_SM_RESTART: libc::c_ulong = iow::<Rp1PioSmRestartArgs>(102, 38);
const PIO_IOC_SM_CLKDIV_RESTART: libc::c_ulong = iow::<Rp1PioSmRestartArgs>(102, 39);
const PIO_IOC_SM_ENABLE_SYNC: libc::c_ulong = iow::<Rp1PioSmEnableSyncArgs>(102, 40);
const PIO_IOC_GPIO_INIT: libc::c_ulong = iow::<Rp1GpioInitArgs>(102, 50);
const PIO_IOC_GPIO_SET_FUNCTION: libc::c_ulong = iow::<Rp1GpioSetFunctionArgs>(102, 51);

fn log(message: impl AsRef<str>) {
    if env::var("HEART_PI5_SIMPLE_PROBE_LOG").map(|value| value != "0").unwrap_or(true) {
        eprintln!("[pi5_round_robin_probe] {}", message.as_ref());
    }
}

fn xioctl<T>(fd: RawFd, request: libc::c_ulong, arg: &mut T, label: &str) -> Result<i32, String> {
    let ret = unsafe { libc::ioctl(fd, request, arg as *mut T) };
    if ret < 0 {
        return Err(format!("{label}: {}", std::io::Error::last_os_error()));
    }
    Ok(ret)
}

fn encode_clkdiv(clkdiv: f32) -> (u16, u8) {
    let scaled = (clkdiv * 256.0).round().clamp(256.0, (u16::MAX as f32) * 256.0) as u32;
    ((scaled >> 8) as u16, (scaled & 0xff) as u8)
}

fn pio_encode_irq_set(relative: bool, irq: u8) -> u16 {
    PIO_INSTR_BITS_IRQ | (((relative as u16) << 4) | u16::from(irq & 0x7))
}

fn pio_encode_irq_clear(relative: bool, irq: u8) -> u16 {
    PIO_INSTR_BITS_IRQ | (2 << 5) | (((relative as u16) << 4) | u16::from(irq & 0x7))
}

fn solid_rgba(config: &Pi5ScanConfig, rgb: [u8; 3]) -> Vec<u8> {
    let mut rgba = vec![0_u8; (config.width().unwrap() * config.height().unwrap() * 4) as usize];
    for pixel in rgba.chunks_exact_mut(4) {
        pixel[0] = rgb[0];
        pixel[1] = rgb[1];
        pixel[2] = rgb[2];
        pixel[3] = 0xff;
    }
    rgba
}

fn round_robin_words(frame: &PackedScanFrame) -> Vec<u32> {
    frame
        .as_words()
        .iter()
        .map(|word| (word >> 4) & 0x7fff_ffff)
        .collect()
}

fn round_robin_turn_words(frame: &PackedScanFrame, frames_per_turn: usize) -> Vec<u32> {
    let base = round_robin_words(frame);
    let repeat = frames_per_turn.max(1);
    let mut words = Vec::with_capacity(
        base.len()
            .checked_mul(repeat)
            .and_then(|n| n.checked_add(1))
            .unwrap_or(base.len() + 1),
    );
    for _ in 0..repeat {
        words.extend_from_slice(&base);
    }
    words.push(0x8000_0000);
    words
}

fn panel_gpios() -> [u16; 15] {
    [4, 5, 6, 12, 13, 16, 17, 18, 20, 21, 22, 23, 24, 26, 27]
}

fn main() -> Result<(), String> {
    let frame_submits = env::var("HEART_PI5_ROUND_ROBIN_FRAME_COPIES")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .filter(|value| *value >= 1)
        .unwrap_or(32);
    let clock_divider = env::var("HEART_PI5_SIMPLE_SCAN_CLOCK_DIVIDER")
        .ok()
        .and_then(|value| value.parse::<f32>().ok())
        .filter(|value| value.is_finite() && *value > 0.0)
        .unwrap_or(1.0);
    let dma_buf_size_cap = env::var("HEART_PI5_ROUND_ROBIN_BUF_SIZE")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .filter(|value| *value >= 4096)
        .unwrap_or(50_000);
    let dma_buf_count = env::var("HEART_PI5_ROUND_ROBIN_BUF_COUNT")
        .ok()
        .and_then(|value| value.parse::<u32>().ok())
        .filter(|value| *value >= 1)
        .unwrap_or(3);
    let turn_weights = [
        env::var("HEART_PI5_ROUND_ROBIN_SM0_FRAMES_PER_TURN")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .filter(|value| *value >= 1)
            .unwrap_or(4),
        env::var("HEART_PI5_ROUND_ROBIN_SM1_FRAMES_PER_TURN")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .filter(|value| *value >= 1)
            .unwrap_or(4),
        env::var("HEART_PI5_ROUND_ROBIN_SM2_FRAMES_PER_TURN")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .filter(|value| *value >= 1)
            .unwrap_or(1),
        env::var("HEART_PI5_ROUND_ROBIN_SM3_FRAMES_PER_TURN")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .filter(|value| *value >= 1)
            .unwrap_or(1),
    ];
    let run_seconds = env::var("HEART_PI5_ROUND_ROBIN_SECONDS")
        .ok()
        .and_then(|value| value.parse::<f64>().ok())
        .filter(|value| value.is_finite() && *value > 0.0);
    let config = Pi5ScanConfig::from_matrix_config(WiringProfile::AdafruitHatPwm, 64, 64, 1, 1)?
        .with_pwm_bits(11)?
        .with_clock_divider(clock_divider)?;
    let colors = [
        ("sm0", [0xff, 0x00, 0x00]),
        ("sm1", [0xff, 0x00, 0x00]),
        ("sm2", [0xff, 0x00, 0x00]),
        ("sm3", [0xff, 0x00, 0x00]),
    ];
    let frames: Vec<Vec<u32>> = colors
        .iter()
        .enumerate()
        .map(|(sm, (_, rgb))| {
            let (frame, _) = PackedScanFrame::pack_rgba(&config, &solid_rgba(&config, *rgb)).unwrap();
            round_robin_turn_words(&frame, turn_weights[sm])
        })
        .collect();
    let frame_bytes_by_sm: Vec<usize> = frames
        .iter()
        .map(|frame| {
            frame
                .len()
                .checked_mul(size_of::<u32>())
                .ok_or_else(|| "round robin frame size overflowed".to_string())
        })
        .collect::<Result<_, _>>()?;
    let max_frame_bytes = frame_bytes_by_sm
        .iter()
        .copied()
        .max()
        .ok_or_else(|| "round robin requires at least one frame".to_string())?;
    let dma_buf_size_by_sm: Vec<usize> = frame_bytes_by_sm
        .iter()
        .map(|frame_bytes| (*frame_bytes).min(dma_buf_size_cap))
        .collect();
    log(format!(
        "starting round robin frame_bytes_by_sm={frame_bytes_by_sm:?} dma_buf_size_by_sm={dma_buf_size_by_sm:?} dma_buf_count={dma_buf_count} frame_submits={frame_submits} clock_divider={clock_divider} run_seconds={run_seconds:?} turn_weights={turn_weights:?}"
    ));

    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .open("/dev/pio0")
        .map_err(|error| format!("open /dev/pio0: {error}"))?;
    let fd = file.as_raw_fd();
    for gpio in panel_gpios() {
        xioctl(fd, PIO_IOC_GPIO_INIT, &mut Rp1GpioInitArgs { gpio }, "PIO_IOC_GPIO_INIT")?;
        xioctl(
            fd,
            PIO_IOC_GPIO_SET_FUNCTION,
            &mut Rp1GpioSetFunctionArgs { gpio, fn_: RP1_GPIO_FUNC_PIO },
            "PIO_IOC_GPIO_SET_FUNCTION",
        )?;
    }

    let claim_mask = 0x0f;
    xioctl(fd, PIO_IOC_SM_CLAIM, &mut Rp1PioSmClaimArgs { mask: claim_mask }, "PIO_IOC_SM_CLAIM")?;
    xioctl(
        fd,
        PIO_IOC_SM_SET_ENABLED,
        &mut Rp1PioSmSetEnabledArgs { mask: claim_mask, enable: 0, rsvd: 0 },
        "PIO_IOC_SM_SET_ENABLED(disable)",
    )?;

    let mut add = Rp1PioAddProgram {
        num_instrs: PI5_PIO_ROUND_ROBIN_OUT_PROGRAM_LENGTH as u16,
        origin: RP1_PIO_ORIGIN_ANY,
        ..Default::default()
    };
    for (index, instruction) in PI5_PIO_ROUND_ROBIN_OUT_BASE_PROGRAM.iter().copied().enumerate() {
        add.instrs[index] = instruction;
    }
    let origin = xioctl(fd, PIO_IOC_ADD_PROGRAM, &mut add, "PIO_IOC_ADD_PROGRAM(round_robin)")? as u16;
    log(format!("round_robin program loaded at origin={origin}"));

    let (clkdiv_int, clkdiv_frac) = encode_clkdiv(clock_divider);
    let sm_config = Rp1PioSmConfig {
        clkdiv: (u32::from(clkdiv_int) << PROC_PIO_SM0_CLKDIV_INT_LSB)
            | (u32::from(clkdiv_frac) << PROC_PIO_SM0_CLKDIV_FRAC_LSB),
        execctrl: (u32::from(PI5_PIO_ROUND_ROBIN_OUT_WRAP_TARGET + origin as u8)
            << PROC_PIO_SM0_EXECCTRL_WRAP_BOTTOM_LSB)
            | (u32::from(PI5_PIO_ROUND_ROBIN_OUT_WRAP + origin as u8) << PROC_PIO_SM0_EXECCTRL_WRAP_TOP_LSB)
            | (u32::from(PI5_PIO_ROUND_ROBIN_OUT_SIDESET_OPTIONAL as u8) << PROC_PIO_SM0_EXECCTRL_SIDE_EN_LSB)
            | (0_u32 << PROC_PIO_SM0_EXECCTRL_STATUS_SEL_LSB)
            | (1_u32 << PROC_PIO_SM0_EXECCTRL_STATUS_N_LSB),
        shiftctrl: (u32::from(PI5_PIO_ROUND_ROBIN_OUT_AUTO_PULL as u8) << PROC_PIO_SM0_SHIFTCTRL_AUTOPULL_LSB)
            | (u32::from(PI5_PIO_ROUND_ROBIN_OUT_OUT_SHIFT_RIGHT as u8) << PROC_PIO_SM0_SHIFTCTRL_OUT_SHIFTDIR_LSB)
            | (u32::from(PI5_PIO_ROUND_ROBIN_OUT_PULL_THRESHOLD & 0x1f) << PROC_PIO_SM0_SHIFTCTRL_PULL_THRESH_LSB)
            | (1_u32 << PROC_PIO_SM0_SHIFTCTRL_FJOIN_TX_LSB),
        pinctrl: (u32::from(PI5_PIO_ROUND_ROBIN_OUT_OUT_PIN_BASE) << PROC_PIO_SM0_PINCTRL_OUT_BASE_LSB)
            | (u32::from(PI5_PIO_ROUND_ROBIN_OUT_OUT_PIN_COUNT) << PROC_PIO_SM0_PINCTRL_OUT_COUNT_LSB)
            | (u32::from(17_u8) << PROC_PIO_SM0_PINCTRL_SIDESET_BASE_LSB)
            | (u32::from(PI5_PIO_ROUND_ROBIN_OUT_SIDESET_PIN_COUNT) << PROC_PIO_SM0_PINCTRL_SIDESET_COUNT_LSB),
    };

    let pindir_mask = panel_gpios()
        .iter()
        .fold(0_u32, |mask, gpio| mask | (1_u32 << u32::from(*gpio)));
    for sm in 0..4_u16 {
        let frame_bytes = frame_bytes_by_sm[sm as usize];
        let dma_buf_size = dma_buf_size_by_sm[sm as usize];
        xioctl(fd, PIO_IOC_SM_CLEAR_FIFOS, &mut Rp1PioSmClearFifosArgs { sm }, "PIO_IOC_SM_CLEAR_FIFOS")?;
        xioctl(
            fd,
            PIO_IOC_SM_INIT,
            &mut Rp1PioSmInitArgs { sm, initial_pc: origin, config: sm_config },
            "PIO_IOC_SM_INIT",
        )?;
        xioctl(
            fd,
            PIO_IOC_SM_SET_PINDIRS,
            &mut Rp1PioSmSetPindirsArgs { sm, rsvd: 0, dirs: pindir_mask, mask: pindir_mask },
            "PIO_IOC_SM_SET_PINDIRS",
        )?;
        xioctl(
            fd,
            PIO_IOC_SM_CONFIG_XFER32,
            &mut Rp1PioSmConfigXfer32Args {
                sm,
                dir: RP1_PIO_DIR_TO_SM,
                buf_size: dma_buf_size as u32,
                buf_count: dma_buf_count,
            },
            "PIO_IOC_SM_CONFIG_XFER32",
        )?;
        log(format!(
            "configured sm={sm} frame_bytes={frame_bytes} dma_buf_size={dma_buf_size} dma_buf_count={dma_buf_count}"
        ));
    }

    xioctl(fd, PIO_IOC_SM_RESTART, &mut Rp1PioSmRestartArgs { mask: claim_mask }, "PIO_IOC_SM_RESTART")?;
    xioctl(fd, PIO_IOC_SM_CLKDIV_RESTART, &mut Rp1PioSmRestartArgs { mask: claim_mask }, "PIO_IOC_SM_CLKDIV_RESTART")?;
    for irq in 0..4_u8 {
        xioctl(
            fd,
            PIO_IOC_SM_EXEC,
            &mut Rp1PioSmExecArgs { sm: 0, instr: pio_encode_irq_clear(false, irq), blocking: 1, rsvd: 0 },
            "PIO_IOC_SM_EXEC(irq_clear)",
        )?;
    }
    xioctl(
        fd,
        PIO_IOC_SM_EXEC,
        &mut Rp1PioSmExecArgs { sm: 0, instr: pio_encode_irq_set(false, 0), blocking: 1, rsvd: 0 },
        "PIO_IOC_SM_EXEC(seed_irq0)",
    )?;
    xioctl(fd, PIO_IOC_SM_ENABLE_SYNC, &mut Rp1PioSmEnableSyncArgs { mask: claim_mask }, "PIO_IOC_SM_ENABLE_SYNC")?;

    let started = Instant::now();
    let deadline = run_seconds.map(|seconds| started + Duration::from_secs_f64(seconds));
    let completed_submits = [
        AtomicUsize::new(0),
        AtomicUsize::new(0),
        AtomicUsize::new(0),
        AtomicUsize::new(0),
    ];
    thread::scope(|scope| -> Result<(), String> {
        let mut handles = Vec::new();
        for (sm, frame) in frames.iter().enumerate() {
            let label = colors[sm].0.to_string();
            let counter = &completed_submits[sm];
            let weight = turn_weights[sm];
            handles.push(scope.spawn(move || -> Result<(), String> {
                for submit_index in 0..frame_submits {
                    if deadline.is_some_and(|end| Instant::now() >= end) {
                        break;
                    }
                    let mut args = Rp1PioSmXferData32Args {
                        sm: sm as u16,
                        dir: RP1_PIO_DIR_TO_SM,
                        data_bytes: (frame.len() * size_of::<u32>()) as u32,
                        data: frame.as_ptr() as *mut libc::c_void,
                    };
                    xioctl(
                        fd,
                        PIO_IOC_SM_XFER_DATA32,
                        &mut args,
                        &format!("PIO_IOC_SM_XFER_DATA32({label},submit={submit_index})"),
                    )?;
                    counter.fetch_add(weight, Ordering::Relaxed);
                }
                Ok(())
            }));
        }
        for handle in handles {
            handle
                .join()
                .map_err(|_| "round robin xfer thread panicked".to_string())??;
        }
        Ok(())
    })?;

    xioctl(
        fd,
        PIO_IOC_SM_SET_ENABLED,
        &mut Rp1PioSmSetEnabledArgs { mask: claim_mask, enable: 0, rsvd: 0 },
        "PIO_IOC_SM_SET_ENABLED(disable)",
    )?;
    for sm in 0..4_u16 {
        let _ = xioctl(fd, PIO_IOC_SM_CLEAR_FIFOS, &mut Rp1PioSmClearFifosArgs { sm }, "PIO_IOC_SM_CLEAR_FIFOS");
    }
    let mut remove = Rp1PioRemoveProgram {
        num_instrs: PI5_PIO_ROUND_ROBIN_OUT_PROGRAM_LENGTH as u16,
        origin,
    };
    let _ = xioctl(fd, PIO_IOC_REMOVE_PROGRAM, &mut remove, "PIO_IOC_REMOVE_PROGRAM");
    let _ = xioctl(fd, PIO_IOC_SM_UNCLAIM, &mut Rp1PioSmClaimArgs { mask: claim_mask }, "PIO_IOC_SM_UNCLAIM");
    let elapsed_s = started.elapsed().as_secs_f64();
    let completed_per_sm = [
        completed_submits[0].load(Ordering::Relaxed),
        completed_submits[1].load(Ordering::Relaxed),
        completed_submits[2].load(Ordering::Relaxed),
        completed_submits[3].load(Ordering::Relaxed),
    ];
    let total_completed: usize = completed_per_sm.iter().sum();
    let avg_completed_per_sm = total_completed as f64 / 4.0;
    let per_sm_hz = avg_completed_per_sm / elapsed_s;
    let ring_hz = total_completed as f64 / elapsed_s;
    println!(
        "round_robin_elapsed_s={elapsed_s:.3} per_sm_hz={per_sm_hz:.2} ring_hz={ring_hz:.2} max_frame_bytes={max_frame_bytes} frame_bytes_by_sm={frame_bytes_by_sm:?} completed_frames_per_sm={completed_per_sm:?}"
    );
    Ok(())
}
