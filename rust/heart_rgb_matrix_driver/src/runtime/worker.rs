use std::fs::OpenOptions;
use std::mem::size_of;
use std::os::fd::{AsRawFd, RawFd};
use std::time::{Duration, Instant};

use super::pi5_pio_programs_generated::{
    PI5_PIO_RAW_BYTE_PULL_BASE_PROGRAM,
    PI5_PIO_RAW_BYTE_PULL_DELAY_PATCH_INDICES,
    PI5_PIO_RAW_BYTE_PULL_OUT_PIN_BASE,
    PI5_PIO_RAW_BYTE_PULL_OUT_PIN_COUNT,
    PI5_PIO_RAW_BYTE_PULL_OUT_SHIFT_RIGHT,
    PI5_PIO_RAW_BYTE_PULL_PROGRAM_LENGTH,
    PI5_PIO_RAW_BYTE_PULL_SIDESET_OPTIONAL,
    PI5_PIO_RAW_BYTE_PULL_SIDESET_PIN_COUNT,
    PI5_PIO_RAW_BYTE_PULL_WRAP,
    PI5_PIO_RAW_BYTE_PULL_WRAP_TARGET,
};
use super::pi5_pinout::Pi5ScanPinout;
use super::strategy::pi5_simple_scan::{PackedScanFrame, Pi5ScanConfig, Pi5ScanTiming};

fn probe_log(message: impl AsRef<str>) {
    if std::env::var("HEART_PI5_SIMPLE_PROBE_LOG")
        .map(|value| value != "0")
        .unwrap_or(true)
    {
        eprintln!("[pi5_simple_probe::worker] {}", message.as_ref());
    }
}
const RP1_PIO_INSTRUCTION_COUNT: usize = 32;
const RP1_GPIO_FUNC_PIO: u16 = 7;
const RP1_PIO_ORIGIN_ANY: u16 = u16::MAX;
const RP1_PIO_DIR_TO_SM: u16 = 0;
const PROC_PIO_SM0_PINCTRL_OUT_BASE_LSB: u32 = 0;
const PROC_PIO_SM0_PINCTRL_SET_BASE_LSB: u32 = 5;
const PROC_PIO_SM0_PINCTRL_SIDESET_BASE_LSB: u32 = 10;
const PROC_PIO_SM0_PINCTRL_OUT_COUNT_LSB: u32 = 20;
const PROC_PIO_SM0_PINCTRL_SET_COUNT_LSB: u32 = 26;
const PROC_PIO_SM0_PINCTRL_SIDESET_COUNT_LSB: u32 = 29;
const PROC_PIO_SM0_EXECCTRL_SIDE_EN_LSB: u32 = 30;
const PROC_PIO_SM0_EXECCTRL_WRAP_TOP_LSB: u32 = 12;
const PROC_PIO_SM0_EXECCTRL_WRAP_BOTTOM_LSB: u32 = 7;
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
const PIO_DELAY_MASK: u16 = 0x0700;

const fn ioc(dir: u32, type_: u32, nr: u32, size: u32) -> libc::c_ulong {
    ((dir << IOC_DIRSHIFT)
        | (type_ << IOC_TYPESHIFT)
        | (nr << IOC_NRSHIFT)
        | (size << IOC_SIZESHIFT)) as libc::c_ulong
}

const fn iow<T>(type_: u32, nr: u32) -> libc::c_ulong {
    ioc(IOC_WRITE, type_, nr, size_of::<T>() as u32)
}

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
    instrs: [u16; RP1_PIO_INSTRUCTION_COUNT],
}

impl Default for Rp1PioAddProgram {
    fn default() -> Self {
        Self {
            num_instrs: 0,
            origin: 0,
            instrs: [0; RP1_PIO_INSTRUCTION_COUNT],
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
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
struct Rp1PioSmClearFifosArgs {
    sm: u16,
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
struct Rp1PioSmSetPindirsArgs {
    sm: u16,
    rsvd: u16,
    dirs: u32,
    mask: u32,
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

#[derive(Clone, Copy)]
struct ProgramSpec {
    base_program: &'static [u16],
    delay_patch_indices: &'static [usize],
    out_pin_base: u8,
    out_pin_count: u8,
    set_pin_base: u8,
    set_pin_count: u8,
    out_shift_right: bool,
    auto_pull: bool,
    pull_threshold: u8,
    sideset_pin_count: u8,
    sideset_optional: bool,
    wrap_target: u8,
    wrap: u8,
    program_length: usize,
}

const PIO_IOC_ADD_PROGRAM: libc::c_ulong = iow::<Rp1PioAddProgram>(102, 11);
const PIO_IOC_REMOVE_PROGRAM: libc::c_ulong = iow::<Rp1PioRemoveProgram>(102, 12);
const PIO_IOC_SM_CLAIM: libc::c_ulong = iow::<Rp1PioSmClaimArgs>(102, 20);
const PIO_IOC_SM_UNCLAIM: libc::c_ulong = iow::<Rp1PioSmClaimArgs>(102, 21);
const PIO_IOC_SM_INIT: libc::c_ulong = iow::<Rp1PioSmInitArgs>(102, 30);
const PIO_IOC_SM_CLEAR_FIFOS: libc::c_ulong = iow::<Rp1PioSmClearFifosArgs>(102, 33);
const PIO_IOC_SM_SET_PINDIRS: libc::c_ulong = iow::<Rp1PioSmSetPindirsArgs>(102, 36);
const PIO_IOC_SM_SET_ENABLED: libc::c_ulong = iow::<Rp1PioSmSetEnabledArgs>(102, 37);
const PIO_IOC_SM_CONFIG_XFER32: libc::c_ulong = iow::<Rp1PioSmConfigXfer32Args>(102, 3);
const PIO_IOC_SM_XFER_DATA32: libc::c_ulong = iow::<Rp1PioSmXferData32Args>(102, 2);
const PIO_IOC_GPIO_INIT: libc::c_ulong = iow::<Rp1GpioInitArgs>(102, 50);
const PIO_IOC_GPIO_SET_FUNCTION: libc::c_ulong = iow::<Rp1GpioSetFunctionArgs>(102, 51);

fn raw_byte_pull_program_spec() -> ProgramSpec {
    ProgramSpec {
        base_program: &PI5_PIO_RAW_BYTE_PULL_BASE_PROGRAM,
        delay_patch_indices: &PI5_PIO_RAW_BYTE_PULL_DELAY_PATCH_INDICES,
        out_pin_base: PI5_PIO_RAW_BYTE_PULL_OUT_PIN_BASE,
        out_pin_count: PI5_PIO_RAW_BYTE_PULL_OUT_PIN_COUNT,
        set_pin_base: 0,
        set_pin_count: 0,
        out_shift_right: PI5_PIO_RAW_BYTE_PULL_OUT_SHIFT_RIGHT,
        auto_pull: false,
        pull_threshold: 32,
        sideset_pin_count: PI5_PIO_RAW_BYTE_PULL_SIDESET_PIN_COUNT,
        sideset_optional: PI5_PIO_RAW_BYTE_PULL_SIDESET_OPTIONAL,
        wrap_target: PI5_PIO_RAW_BYTE_PULL_WRAP_TARGET,
        wrap: PI5_PIO_RAW_BYTE_PULL_WRAP,
        program_length: PI5_PIO_RAW_BYTE_PULL_PROGRAM_LENGTH,
    }
}

#[derive(Debug)]
pub struct Pi5SimpleProbeSession {
    file: std::fs::File,
    claimed_mask: u16,
    enabled_mask: u16,
    loaded_programs: Vec<Rp1PioRemoveProgram>,
    configured_buf_size: u32,
    configured_buf_count: u32,
    panel_pindir_mask: u32,
}

impl Pi5SimpleProbeSession {
    pub fn new(
        config: &Pi5ScanConfig,
        frame_bytes: usize,
    ) -> Result<Self, String> {
        probe_log("opening /dev/pio0");
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .open("/dev/pio0")
            .map_err(|error| format!("Open /dev/pio0: {error}"))?;
        let fd = file.as_raw_fd();
        probe_log(format!("opened /dev/pio0 fd={fd}"));
        probe_log("initializing panel GPIOs");
        init_panel_gpios(fd, config.pinout())?;
        let claimed_mask = 0b1;
        probe_log(format!("claiming SM mask=0x{claimed_mask:x}"));
        xioctl(
            fd,
            PIO_IOC_SM_CLAIM,
            &mut Rp1PioSmClaimArgs { mask: claimed_mask },
            "PIO_IOC_SM_CLAIM",
        )?;
        probe_log("SM claim succeeded");
        probe_log("adding probe program mode=RawBytePull");
        let (loaded_programs, panel_pindir_mask) =
            add_probe_programs(fd, config.timing(), config.pinout())?;
        for (index, program) in loaded_programs.iter().enumerate() {
            probe_log(format!(
                "program loaded sm={} origin={} instructions={}",
                index, program.origin, program.num_instrs
            ));
        }
        let requested_buf_size = std::env::var("HEART_PI5_SIMPLE_PROBE_BUF_SIZE")
            .ok()
            .and_then(|value| value.parse::<u32>().ok())
            .filter(|value| *value >= 1024)
            .unwrap_or(262_140);
        let configured_buf_size = aligned_buf_size(frame_bytes, requested_buf_size)?;
        let configured_buf_count = std::env::var("HEART_PI5_SIMPLE_PROBE_BUF_COUNT")
            .ok()
            .and_then(|value| value.parse::<u32>().ok())
            .filter(|value| *value >= 1)
            .unwrap_or(3);
        let configured_capacity = configured_buf_size as usize * configured_buf_count as usize;
        if frame_bytes > configured_capacity {
            return Err(format!(
                "Packed frame size {} exceeds configured DMA pool capacity {} (buf_size={} * buf_count={}).",
                frame_bytes, configured_capacity, configured_buf_size, configured_buf_count
            ));
        }
        xioctl(
            fd,
            PIO_IOC_SM_CONFIG_XFER32,
            &mut Rp1PioSmConfigXfer32Args {
                sm: 0,
                dir: RP1_PIO_DIR_TO_SM,
                buf_size: configured_buf_size,
                buf_count: configured_buf_count,
            },
            "PIO_IOC_SM_CONFIG_XFER32(sm=0)",
        )?;
        probe_log(format!(
            "configured xfer once sms={} dir={} buf_size={} buf_count={} frame_bytes={} requested_buf_size={}",
            1,
            RP1_PIO_DIR_TO_SM, configured_buf_size, configured_buf_count, frame_bytes, requested_buf_size
        ));
        xioctl(
            fd,
            PIO_IOC_SM_SET_ENABLED,
            &mut Rp1PioSmSetEnabledArgs {
                mask: claimed_mask,
                enable: 1,
                rsvd: 0,
            },
            "PIO_IOC_SM_SET_ENABLED(enable)",
        )?;
        probe_log(format!("enabled mask=0x{claimed_mask:x} once"));
        Ok(Self {
            file,
            claimed_mask,
            enabled_mask: claimed_mask,
            loaded_programs,
            configured_buf_size,
            configured_buf_count,
            panel_pindir_mask,
        })
    }

    pub fn present(&mut self, frame: &PackedScanFrame) -> Result<Duration, String> {
        let fd = self.file.as_raw_fd();
        probe_log(format!(
            "present start bytes={} words={}",
            frame.as_bytes().len(),
            frame.word_count()
        ));
        let configured_capacity = self.configured_buf_size as usize * self.configured_buf_count as usize;
        if frame.as_bytes().len() > configured_capacity {
            return Err(format!(
                "Packed frame size {} exceeds configured DMA pool capacity {} (buf_size={} * buf_count={}).",
                frame.as_bytes().len(),
                configured_capacity,
                self.configured_buf_size,
                self.configured_buf_count
            ));
        }

        let started = Instant::now();
        xioctl(
            fd,
            PIO_IOC_SM_XFER_DATA32,
            &mut Rp1PioSmXferData32Args {
                sm: 0,
                dir: RP1_PIO_DIR_TO_SM,
                data_bytes: frame.as_bytes().len() as u32,
                data: frame.as_bytes().as_ptr() as *mut libc::c_void,
            },
            "PIO_IOC_SM_XFER_DATA32(sm=0)",
        )?;
        let elapsed = started.elapsed();
        probe_log(format!("present complete xfer_us={}", elapsed.as_micros()));
        Ok(elapsed)
    }
}

impl Drop for Pi5SimpleProbeSession {
    fn drop(&mut self) {
        let fd = self.file.as_raw_fd();
        probe_log(format!(
            "drop begin enabled_mask=0x{:x} claimed_mask=0x{:x} loaded_programs={}",
            self.enabled_mask,
            self.claimed_mask,
            self.loaded_programs.len()
        ));
        if self.enabled_mask != 0 {
            probe_log(format!("disabling SM mask=0x{:x}", self.enabled_mask));
            let _ = unsafe {
                libc::ioctl(
                    fd,
                    PIO_IOC_SM_SET_ENABLED,
                    &mut Rp1PioSmSetEnabledArgs {
                        mask: self.enabled_mask,
                        enable: 0,
                        rsvd: 0,
                    } as *mut Rp1PioSmSetEnabledArgs,
                )
            };
        }
        if self.claimed_mask != 0 {
            let pindir_mask = self.panel_pindir_mask;
            probe_log(format!("restoring pindirs to input mask=0x{pindir_mask:08x}"));
            let _ = unsafe {
                libc::ioctl(
                    fd,
                    PIO_IOC_SM_SET_PINDIRS,
                    &mut Rp1PioSmSetPindirsArgs {
                        sm: 0,
                        rsvd: 0,
                        dirs: 0,
                        mask: pindir_mask,
                    } as *mut Rp1PioSmSetPindirsArgs,
                )
            };
            probe_log("clearing SM0 FIFOs");
            let _ = unsafe {
                libc::ioctl(
                    fd,
                    PIO_IOC_SM_CLEAR_FIFOS,
                    &mut Rp1PioSmClearFifosArgs { sm: 0 } as *mut Rp1PioSmClearFifosArgs,
                )
            };
        }
        for program in self.loaded_programs.iter_mut().rev() {
            probe_log(format!(
                "removing program origin={} instructions={}",
                program.origin, program.num_instrs
            ));
            let _ = unsafe { libc::ioctl(fd, PIO_IOC_REMOVE_PROGRAM, program as *mut Rp1PioRemoveProgram) };
        }
        if self.claimed_mask != 0 {
            probe_log(format!("unclaiming SM mask=0x{:x}", self.claimed_mask));
            let _ = unsafe {
                libc::ioctl(
                    fd,
                    PIO_IOC_SM_UNCLAIM,
                    &mut Rp1PioSmClaimArgs {
                        mask: self.claimed_mask,
                    } as *mut Rp1PioSmClaimArgs,
                )
            };
        }
        probe_log("drop complete");
    }
}

fn init_panel_gpios(fd: RawFd, pinout: Pi5ScanPinout) -> Result<(), String> {
    for gpio in pinout.used_panel_gpios() {
        probe_log(format!("gpio init gpio={gpio}"));
        xioctl(
            fd,
            PIO_IOC_GPIO_INIT,
            &mut Rp1GpioInitArgs { gpio },
            "PIO_IOC_GPIO_INIT",
        )?;
        probe_log(format!("gpio set function gpio={gpio} fn={RP1_GPIO_FUNC_PIO}"));
        xioctl(
            fd,
            PIO_IOC_GPIO_SET_FUNCTION,
            &mut Rp1GpioSetFunctionArgs {
                gpio,
                fn_: RP1_GPIO_FUNC_PIO,
            },
            "PIO_IOC_GPIO_SET_FUNCTION",
        )?;
    }
    Ok(())
}

fn add_probe_programs(
    fd: RawFd,
    timing: Pi5ScanTiming,
    pinout: Pi5ScanPinout,
) -> Result<(Vec<Rp1PioRemoveProgram>, u32), String> {
    let program_specs = vec![(raw_byte_pull_program_spec(), None)];
    let disable_mask = 0b1;
    xioctl(
        fd,
        PIO_IOC_SM_SET_ENABLED,
        &mut Rp1PioSmSetEnabledArgs {
            mask: disable_mask,
            enable: 0,
            rsvd: 0,
        },
        "PIO_IOC_SM_SET_ENABLED(disable)",
    )?;

    let mut loaded_programs = Vec::with_capacity(program_specs.len());
    for (sm_index, (spec, requested_origin)) in program_specs.into_iter().enumerate() {
        probe_log(format!(
            "patching program mode=RawBytePull sm={} simple_clock_hold_ticks={} requested_origin={requested_origin:?}",
            sm_index, timing.simple_clock_hold_ticks
        ));
        let mut program = spec.base_program.to_vec();
        for &index in spec.delay_patch_indices {
            program[index] = with_delay_bits(program[index], timing.simple_clock_hold_ticks);
        }
        validate_program_uses_sideset(
            &program,
            spec.sideset_pin_count,
            spec.sideset_optional,
        )?;
        validate_program_uses_out_pins(&program, spec.out_pin_count)?;
        if spec.program_length > RP1_PIO_INSTRUCTION_COUNT || program.len() > RP1_PIO_INSTRUCTION_COUNT {
            return Err(format!(
                "PIO program for sm={} is too long: program_length={} actual_len={} max={}.",
                sm_index,
                spec.program_length,
                program.len(),
                RP1_PIO_INSTRUCTION_COUNT
            ));
        }

        let mut add = Rp1PioAddProgram {
            num_instrs: spec.program_length as u16,
            origin: requested_origin.unwrap_or(RP1_PIO_ORIGIN_ANY),
            ..Default::default()
        };
        for (index, instruction) in program.iter().copied().enumerate() {
            add.instrs[index] = instruction;
        }
        let add_label = format!("PIO_IOC_ADD_PROGRAM(sm={sm_index})");
        let origin = xioctl(fd, PIO_IOC_ADD_PROGRAM, &mut add, &add_label)? as u16;
        probe_log(format!("PIO_IOC_ADD_PROGRAM sm={} origin={origin}", sm_index));

        let clear_label = format!("PIO_IOC_SM_CLEAR_FIFOS(sm={sm_index})");
        xioctl(
            fd,
            PIO_IOC_SM_CLEAR_FIFOS,
            &mut Rp1PioSmClearFifosArgs { sm: sm_index as u16 },
            &clear_label,
        )?;
        let sm_config = build_sm_config(origin, pinout, timing, spec);
        probe_log(format!(
            "sm={} config clkdiv=0x{:08x} execctrl=0x{:08x} shiftctrl=0x{:08x} pinctrl=0x{:08x}",
            sm_index, sm_config.clkdiv, sm_config.execctrl, sm_config.shiftctrl, sm_config.pinctrl
        ));
        let init_label = format!("PIO_IOC_SM_INIT(sm={sm_index})");
        xioctl(
            fd,
            PIO_IOC_SM_INIT,
            &mut Rp1PioSmInitArgs {
                sm: sm_index as u16,
                initial_pc: origin,
                config: sm_config,
            },
            &init_label,
        )?;
        loaded_programs.push(Rp1PioRemoveProgram {
            num_instrs: spec.program_length as u16,
            origin,
        });
    }

    let pindir_mask = panel_pindir_mask(pinout);
    for sm in 0..loaded_programs.len() {
        probe_log(format!(
            "setting SM{} panel pindirs to output mask=0x{pindir_mask:08x}",
            sm
        ));
        let label = format!("PIO_IOC_SM_SET_PINDIRS(sm={sm})");
        xioctl(
            fd,
            PIO_IOC_SM_SET_PINDIRS,
            &mut Rp1PioSmSetPindirsArgs {
                sm: sm as u16,
                rsvd: 0,
                dirs: pindir_mask,
                mask: pindir_mask,
            },
            &label,
        )?;
    }

    Ok((loaded_programs, pindir_mask))
}

fn build_sm_config(
    origin: u16,
    pinout: Pi5ScanPinout,
    timing: Pi5ScanTiming,
    spec: ProgramSpec,
) -> Rp1PioSmConfig {
    let mut config = Rp1PioSmConfig::default();
    let (clkdiv_int, clkdiv_frac) = encode_clkdiv(timing.clock_divider);
    config.clkdiv =
        (u32::from(clkdiv_int) << PROC_PIO_SM0_CLKDIV_INT_LSB)
        | (u32::from(clkdiv_frac) << PROC_PIO_SM0_CLKDIV_FRAC_LSB);
    config.execctrl = (u32::from(spec.wrap_target + origin as u8)
        << PROC_PIO_SM0_EXECCTRL_WRAP_BOTTOM_LSB)
        | (u32::from(spec.wrap + origin as u8) << PROC_PIO_SM0_EXECCTRL_WRAP_TOP_LSB)
        | (u32::from(spec.sideset_optional as u8) << PROC_PIO_SM0_EXECCTRL_SIDE_EN_LSB);
    config.shiftctrl = (u32::from(spec.auto_pull as u8)
        << PROC_PIO_SM0_SHIFTCTRL_AUTOPULL_LSB)
        | (u32::from(spec.out_shift_right as u8)
            << PROC_PIO_SM0_SHIFTCTRL_OUT_SHIFTDIR_LSB)
        | (u32::from(spec.pull_threshold & 0x1f)
            << PROC_PIO_SM0_SHIFTCTRL_PULL_THRESH_LSB)
        | (1_u32 << PROC_PIO_SM0_SHIFTCTRL_FJOIN_TX_LSB);
    config.pinctrl = (u32::from(spec.out_pin_base) << PROC_PIO_SM0_PINCTRL_OUT_BASE_LSB)
        | (u32::from(spec.out_pin_count) << PROC_PIO_SM0_PINCTRL_OUT_COUNT_LSB)
        | (u32::from(pinout.clock_gpio() as u8) << PROC_PIO_SM0_PINCTRL_SIDESET_BASE_LSB)
        | (u32::from(spec.sideset_pin_count) << PROC_PIO_SM0_PINCTRL_SIDESET_COUNT_LSB)
        | (u32::from(spec.set_pin_base) << PROC_PIO_SM0_PINCTRL_SET_BASE_LSB)
        | (u32::from(spec.set_pin_count) << PROC_PIO_SM0_PINCTRL_SET_COUNT_LSB)
        | (u32::from(0_u8) << PROC_PIO_SM0_CLKDIV_FRAC_LSB);
    config
}

fn encode_clkdiv(clkdiv: f32) -> (u16, u8) {
    let scaled = (clkdiv * 256.0).round().clamp(256.0, (u16::MAX as f32) * 256.0);
    let scaled = scaled as u32;
    ((scaled >> 8) as u16, (scaled & 0xff) as u8)
}

fn panel_pindir_mask(pinout: Pi5ScanPinout) -> u32 {
    let mask = pinout
        .used_panel_gpios()
        .into_iter()
        .fold(0_u32, |mask, gpio| mask | (1_u32 << u32::from(gpio)));
    mask
}

fn aligned_buf_size(frame_bytes: usize, requested_buf_size: u32) -> Result<u32, String> {
    let frame_bytes =
        u32::try_from(frame_bytes).map_err(|_| "RawBytePull frame size exceeds 32-bit DMA configuration.".to_string())?;
    Ok(requested_buf_size.max(frame_bytes))
}

fn with_delay_bits(opcode: u16, delay_ticks: u32) -> u16 {
    (opcode & !PIO_DELAY_MASK) | ((((delay_ticks.saturating_sub(1)) & 0x7) as u16) << 8)
}

pub(crate) fn validate_program_uses_sideset(
    program: &[u16],
    sideset_count: u8,
    sideset_optional: bool,
) -> Result<(), String> {
    if sideset_count == 0 {
        return Ok(());
    }
    if program
        .iter()
        .any(|&instruction| decoded_sideset_value(instruction, sideset_count, sideset_optional) != 0)
    {
        return Ok(());
    }
    Err(format!(
        "PIO program declares {} side-set pin(s) but never drives a non-zero side-set value.",
        sideset_count
    ))
}

pub(crate) fn validate_program_uses_out_pins(program: &[u16], out_pin_count: u8) -> Result<(), String> {
    if out_pin_count == 0 {
        return Ok(());
    }
    if program.iter().any(|&instruction| instruction_writes_out_pins(instruction)) {
        return Ok(());
    }
    Err(format!(
        "PIO program declares {} out pin(s) but never issues an OUT PINS instruction.",
        out_pin_count
    ))
}

fn decoded_sideset_value(instruction: u16, sideset_count: u8, sideset_optional: bool) -> u8 {
    let total_non_delay_bits = sideset_count.saturating_add(u8::from(sideset_optional));
    let active_sideset_count = sideset_count.min(total_non_delay_bits.saturating_sub(u8::from(sideset_optional)));
    let delay_bits = 5_u8.saturating_sub(total_non_delay_bits);
    let field = ((instruction >> 8) & 0x1f) as u8;
    let value_mask = if active_sideset_count == 0 {
        0
    } else {
        (1_u8 << active_sideset_count) - 1
    };
    let value = (field >> delay_bits) & value_mask;
    let enabled = if sideset_optional {
        ((field >> (delay_bits + active_sideset_count)) & 0x1) != 0
    } else {
        true
    };
    if enabled { value } else { 0 }
}

fn instruction_writes_out_pins(instruction: u16) -> bool {
    const PIO_INSTR_BITS_OUT: u16 = 0x6000;
    const PIO_OUT_DEST_PINS: u16 = 0;
    (instruction & 0xe000) == PIO_INSTR_BITS_OUT && ((instruction >> 5) & 0x7) == PIO_OUT_DEST_PINS
}

fn xioctl<T>(fd: RawFd, request: libc::c_ulong, arg: &mut T, label: &str) -> Result<i32, String> {
    probe_log(format!("ioctl begin label={label} request=0x{request:x}"));
    let ret = unsafe { libc::ioctl(fd, request, arg as *mut T) };
    if ret < 0 {
        probe_log(format!(
            "ioctl error label={label} error={}",
            std::io::Error::last_os_error()
        ));
        return Err(format!("{label}: {}", std::io::Error::last_os_error()));
    }
    probe_log(format!("ioctl ok label={label} ret={ret}"));
    Ok(ret)
}
