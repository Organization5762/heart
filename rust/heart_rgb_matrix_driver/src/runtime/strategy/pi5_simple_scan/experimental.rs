use super::types::Pi5ScanConfig;
const RAW_PIN_WORD_SHIFT: u32 = 0;

pub(crate) fn build_raw_group_words_for_rgba(
    config: &Pi5ScanConfig,
    rgba: &[u8],
    row_pair: usize,
    plane_index: usize,
) -> Result<Vec<u32>, String> {
    let width = usize::try_from(config.width()?).map_err(|_| "Pi 5 raw replay width exceeds host usize.".to_string())?;
    let row_pairs = config.row_pairs()?;
    let pinout = config.pinout();
    let addr_bits = pinout.address_bits(row_pair, RAW_PIN_WORD_SHIFT);
    let blank_word = addr_bits | pinout.oe_inactive_bits(RAW_PIN_WORD_SHIFT);
    let active_word = addr_bits | pinout.oe_active_bits(RAW_PIN_WORD_SHIFT);
    let latch_high_word = blank_word | pinout.lat_bits(RAW_PIN_WORD_SHIFT);
    let clock_word = 1_u32 << pinout.clock_gpio();
    let msb_first_shift = usize::from(config.pwm_bits()) - plane_index - 1;
    let timing = config.timing();
    let post_addr = usize::try_from(timing.post_addr_ticks).map_err(|_| "Pi 5 raw replay post_addr_ticks exceeds host usize.".to_string())?;
    let latch = usize::try_from(timing.latch_ticks).map_err(|_| "Pi 5 raw replay latch_ticks exceeds host usize.".to_string())?;
    let post_latch = usize::try_from(timing.post_latch_ticks).map_err(|_| "Pi 5 raw replay post_latch_ticks exceeds host usize.".to_string())?;
    let hold = usize::try_from(timing.simple_clock_hold_ticks).map_err(|_| "Pi 5 raw replay simple_clock_hold_ticks exceeds host usize.".to_string())?;
    let dwell_ticks = usize::try_from(raw_dwell_ticks(config, plane_index)?).map_err(|_| "Pi 5 raw replay dwell exceeds host usize.".to_string())?;

    let mut words = Vec::with_capacity(raw_group_word_count(config, width, plane_index)?);
    repeat_word(&mut words, blank_word, post_addr);
    for column in 0..width {
        let data_word = blank_word | scan_pixel_bits(rgba, config, width, row_pair, row_pairs, column, msb_first_shift);
        repeat_word(&mut words, data_word, hold);
        repeat_word(&mut words, data_word | clock_word, hold);
    }
    repeat_word(&mut words, latch_high_word, latch);
    repeat_word(&mut words, blank_word, post_latch);
    repeat_word(&mut words, active_word, dwell_ticks);
    Ok(words.into_iter().map(raw_word_to_out_word).collect())
}

pub(crate) fn raw_group_word_count(config: &Pi5ScanConfig, width: usize, plane_index: usize) -> Result<usize, String> {
    let timing = config.timing();
    let post_addr = usize::try_from(timing.post_addr_ticks).map_err(|_| "Pi 5 raw replay post_addr_ticks exceeds host usize.".to_string())?;
    let latch = usize::try_from(timing.latch_ticks).map_err(|_| "Pi 5 raw replay latch_ticks exceeds host usize.".to_string())?;
    let post_latch = usize::try_from(timing.post_latch_ticks).map_err(|_| "Pi 5 raw replay post_latch_ticks exceeds host usize.".to_string())?;
    let hold = usize::try_from(timing.simple_clock_hold_ticks).map_err(|_| "Pi 5 raw replay simple_clock_hold_ticks exceeds host usize.".to_string())?;
    let clocks = width.checked_mul(hold).and_then(|v| v.checked_mul(2)).ok_or_else(|| "Pi 5 raw replay clock expansion overflowed.".to_string())?;
    let dwell = usize::try_from(raw_dwell_ticks(config, plane_index)?).map_err(|_| "Pi 5 raw replay dwell exceeds host usize.".to_string())?;
    post_addr
        .checked_add(clocks)
        .and_then(|v| v.checked_add(latch))
        .and_then(|v| v.checked_add(post_latch))
        .and_then(|v| v.checked_add(dwell))
        .ok_or_else(|| "Pi 5 raw replay group word count overflowed.".to_string())
}

fn raw_dwell_ticks(config: &Pi5ScanConfig, plane_index: usize) -> Result<u32, String> {
    let msb_first_shift = usize::from(config.pwm_bits()) - plane_index - 1;
    config.lsb_dwell_ticks().checked_shl(msb_first_shift as u32).ok_or_else(|| "Pi 5 raw replay dwell ticks overflowed.".to_string())
}

fn repeat_word(words: &mut Vec<u32>, word: u32, count: usize) {
    for _ in 0..count.max(1) {
        words.push(word);
    }
}

fn raw_word_to_out_word(word: u32) -> u32 {
    (word & 0x0fff_ffff) << 4
}

fn scan_pixel_bits(
    rgba: &[u8],
    config: &Pi5ScanConfig,
    width: usize,
    row_pair: usize,
    row_pairs: usize,
    column: usize,
    shift: usize,
) -> u32 {
    let upper = pixel_channels(rgba, width, row_pair, column);
    let lower = pixel_channels(rgba, width, row_pair + row_pairs, column);
    let rgb_gpios = config.pinout().rgb_gpios();
    let mut bits = 0_u32;
    for (index, value) in [upper[0], upper[1], upper[2], lower[0], lower[1], lower[2]].into_iter().enumerate() {
        if channel_plane_is_set(value, shift, config.pwm_bits()) {
            bits |= 1_u32 << u32::from(rgb_gpios[index]);
        }
    }
    bits
}

fn pixel_channels(rgba: &[u8], width: usize, row: usize, column: usize) -> [u8; 3] {
    let offset = ((row * width) + column) * 4;
    [rgba[offset], rgba[offset + 1], rgba[offset + 2]]
}

fn channel_plane_is_set(value: u8, shift: usize, pwm_bits: u8) -> bool {
    let expanded = if pwm_bits <= 8 {
        u16::from(value >> (8 - pwm_bits))
    } else {
        u16::from(value) << (pwm_bits - 8).min(8)
    };
    (expanded & (1_u16 << shift)) != 0
}
