use super::types::Pi5ScanConfig;

pub(crate) const SIMPLE_PIN_WORD_SHIFT: u32 = 0;
const SIMPLE_COMMAND_DATA_BIT: u32 = 1_u32 << 31;
const SIMPLE_COMMAND_COUNT_MASK: u32 = !SIMPLE_COMMAND_DATA_BIT;
const PIOMATTER_CLOCKS_PER_DATA: i32 = 2;
const PIOMATTER_DELAY_OVERHEAD: i32 = 5;
const PIOMATTER_CLOCKS_PER_DELAY: i32 = 1;

#[derive(Clone, Copy, Debug)]
struct PiomatterScheduleEntry {
    shift: usize,
    active_time: u32,
}

pub(crate) fn build_simple_group_words_for_rgba(
    config: &Pi5ScanConfig,
    rgba: &[u8],
    row_pair: usize,
    plane_index: usize,
) -> Result<Vec<u32>, String> {
    let width = usize::try_from(config.width()?).map_err(|_| "Pi 5 simple scan width exceeds host usize.".to_string())?;
    let height = usize::try_from(config.height()?).map_err(|_| "Pi 5 simple scan height exceeds host usize.".to_string())?;
    let row_pairs = config.row_pairs()?;
    let pinout = config.pinout();
    let rgb10 = convert_rgba_to_rgb10(rgba, width, height);
    let schedule = make_piomatter_simple_schedule(config.pwm_bits(), width)?;
    let entry = schedule.get(plane_index).ok_or_else(|| format!("Plane index {plane_index} exceeds schedule length {}.", schedule.len()))?;
    let mut active_time = if plane_index == 0 {
        schedule.last().ok_or_else(|| "Piomatter simple schedule is unexpectedly empty.".to_string())?.active_time as i32
    } else {
        schedule[plane_index - 1].active_time as i32
    };
    let mut addr_bits = if plane_index == 0 {
        pinout.address_bits(if row_pair == 0 { row_pairs - 1 } else { row_pair - 1 }, SIMPLE_PIN_WORD_SHIFT)
    } else {
        pinout.address_bits(row_pair, SIMPLE_PIN_WORD_SHIFT)
    };

    let mut words = Vec::with_capacity(width + 8);
    words.push(encode_simple_data_command(width)?);
    for column in 0..width {
        let data_bits = scan_rgb10_pixel_bits(&rgb10, config, width, row_pair, row_pairs, column, entry.shift);
        let mut word = addr_bits | data_bits;
        word |= if active_time > 0 {
            pinout.oe_active_bits(SIMPLE_PIN_WORD_SHIFT)
        } else {
            pinout.oe_inactive_bits(SIMPLE_PIN_WORD_SHIFT)
        };
        active_time -= 1;
        words.push(word);
    }
    words.push(encode_piomatter_delay(active_time * PIOMATTER_CLOCKS_PER_DATA - PIOMATTER_DELAY_OVERHEAD)?);
    words.push(addr_bits | pinout.oe_active_bits(SIMPLE_PIN_WORD_SHIFT));
    words.push(encode_piomatter_delay(pinout.post_oe_delay() as i32)?);
    words.push(addr_bits | pinout.oe_inactive_bits(SIMPLE_PIN_WORD_SHIFT));
    words.push(encode_piomatter_delay(pinout.post_latch_delay() as i32)?);
    addr_bits = pinout.address_bits(row_pair, SIMPLE_PIN_WORD_SHIFT);
    words.push(encode_piomatter_delay(pinout.post_addr_delay() as i32)?);
    words.push(addr_bits | pinout.oe_inactive_bits(SIMPLE_PIN_WORD_SHIFT));
    Ok(words)
}

pub(crate) fn piomatter_simple_frame_words(config: &Pi5ScanConfig, rgba: &[u8]) -> Result<Vec<u32>, String> {
    let width = usize::try_from(config.width()?).map_err(|_| "Pi 5 simple scan width exceeds host usize.".to_string())?;
    let height = usize::try_from(config.height()?).map_err(|_| "Pi 5 simple scan height exceeds host usize.".to_string())?;
    let row_pairs = config.row_pairs()?;
    let pinout = config.pinout();
    let rgb10 = convert_rgba_to_rgb10(rgba, width, height);
    let schedule = make_piomatter_simple_schedule(config.pwm_bits(), width)?;
    let mut old_active_time = schedule.last().ok_or_else(|| "Piomatter simple schedule is unexpectedly empty.".to_string())?.active_time as i32;
    let mut addr_bits = pinout.address_bits(
        row_pairs.checked_sub(1).ok_or_else(|| "Pi 5 simple scan row pair count must be at least 1.".to_string())?,
        SIMPLE_PIN_WORD_SHIFT,
    );
    let mut words = Vec::with_capacity(row_pairs * schedule.len() * (width + 8));

    for row_pair in 0..row_pairs {
        for schedule_entry in &schedule {
            let mut active_time = old_active_time;
            words.push(encode_simple_data_command(width)?);
            for column in 0..width {
                let data_bits = scan_rgb10_pixel_bits(&rgb10, config, width, row_pair, row_pairs, column, schedule_entry.shift);
                let mut word = addr_bits | data_bits;
                word |= if active_time > 0 {
                    pinout.oe_active_bits(SIMPLE_PIN_WORD_SHIFT)
                } else {
                    pinout.oe_inactive_bits(SIMPLE_PIN_WORD_SHIFT)
                };
                active_time -= 1;
                words.push(word);
            }
            words.push(encode_piomatter_delay(active_time * PIOMATTER_CLOCKS_PER_DATA - PIOMATTER_DELAY_OVERHEAD)?);
            words.push(addr_bits | pinout.oe_active_bits(SIMPLE_PIN_WORD_SHIFT));
            words.push(encode_piomatter_delay(pinout.post_oe_delay() as i32)?);
            words.push(addr_bits | pinout.oe_inactive_bits(SIMPLE_PIN_WORD_SHIFT));
            words.push(encode_piomatter_delay(pinout.post_latch_delay() as i32)?);
            old_active_time = schedule_entry.active_time as i32;
            addr_bits = pinout.address_bits(row_pair, SIMPLE_PIN_WORD_SHIFT);
            words.push(encode_piomatter_delay(pinout.post_addr_delay() as i32)?);
            words.push(addr_bits | pinout.oe_inactive_bits(SIMPLE_PIN_WORD_SHIFT));
        }
    }
    Ok(words)
}

fn encode_simple_data_command(logical_count: usize) -> Result<u32, String> {
    encode_simple_count(
        u32::try_from(logical_count).map_err(|_| "Pi 5 simple scan width exceeds 32-bit transport words.".to_string())?,
        true,
    )
}

fn encode_simple_count(logical_count: u32, is_data: bool) -> Result<u32, String> {
    let encoded = logical_count.checked_sub(1).ok_or_else(|| "Pi 5 simple count must be at least 1.".to_string())?;
    if encoded > SIMPLE_COMMAND_COUNT_MASK {
        return Err("Pi 5 simple count exceeds the 31-bit command payload.".to_string());
    }
    Ok(if is_data { SIMPLE_COMMAND_DATA_BIT | encoded } else { encoded })
}

fn encode_piomatter_delay(delay: i32) -> Result<u32, String> {
    let normalized = ((delay / PIOMATTER_CLOCKS_PER_DELAY) - PIOMATTER_DELAY_OVERHEAD).max(1);
    encode_simple_count(
        u32::try_from(normalized).map_err(|_| "Pi 5 simple delay normalization underflowed.".to_string())?,
        false,
    )
}

fn make_piomatter_simple_schedule(pwm_bits: u8, pixels_across: usize) -> Result<Vec<PiomatterScheduleEntry>, String> {
    if !(1..=10).contains(&pwm_bits) {
        return Err(format!("Piomatter pwm_bits {} out of range.", pwm_bits));
    }
    let mut schedule = Vec::with_capacity(usize::from(pwm_bits));
    let mut max_active_time = 0_u32;
    for i in 0..usize::from(pwm_bits) {
        let active_time = 1_u32
            .checked_shl((usize::from(pwm_bits) - i - 1) as u32)
            .ok_or_else(|| "Piomatter active_time overflowed.".to_string())?;
        max_active_time = max_active_time.max(active_time);
        schedule.push(PiomatterScheduleEntry { shift: 9 - i, active_time });
    }
    if max_active_time != 0 && usize::try_from(max_active_time).unwrap_or(usize::MAX) < pixels_across {
        let scale = ((pixels_across as u32) + max_active_time - 1) / max_active_time;
        for entry in &mut schedule {
            entry.active_time = entry.active_time.checked_mul(scale).ok_or_else(|| "Piomatter schedule rescale overflowed.".to_string())?;
        }
    }
    Ok(schedule)
}

fn convert_rgba_to_rgb10(rgba: &[u8], width: usize, height: usize) -> Vec<u32> {
    let mut result = Vec::with_capacity(width * height);
    for pixel in rgba.chunks_exact(4) {
        result.push((gamma_convert(pixel[0]) << 20) | (gamma_convert(pixel[1]) << 10) | gamma_convert(pixel[2]));
    }
    result
}

fn gamma_convert(channel: u8) -> u32 {
    let normalized = f64::from(channel) / 255.0;
    let scaled = (1023.0 * normalized.powf(2.2)).round() as i32;
    u32::try_from(scaled.max(i32::from(channel))).unwrap_or(1023).min(1023)
}

fn scan_rgb10_pixel_bits(
    rgb10: &[u32],
    config: &Pi5ScanConfig,
    width: usize,
    row_pair: usize,
    row_pairs: usize,
    column: usize,
    shift: usize,
) -> u32 {
    let upper = rgb10[(row_pair * width) + column];
    let lower = rgb10[((row_pair + row_pairs) * width) + column];
    let rgb_gpios = config.pinout().rgb_gpios();
    let masks = [1_u32 << (20 + shift), 1_u32 << (10 + shift), 1_u32 << shift];
    let mut bits = 0_u32;
    for (index, mask) in masks.into_iter().enumerate() {
        if (upper & mask) != 0 {
            bits |= 1_u32 << u32::from(rgb_gpios[index]);
        }
        if (lower & mask) != 0 {
            bits |= 1_u32 << u32::from(rgb_gpios[index + 3]);
        }
    }
    bits
}
