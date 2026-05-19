use rayon::prelude::*;

use super::config::ColorOrder;
use super::tuning::runtime_tuning;

#[derive(Debug)]
pub(crate) struct FrameBuffer {
    data: Vec<u8>,
}

impl FrameBuffer {
    pub(crate) fn new(frame_len: usize) -> Self {
        Self {
            data: vec![0_u8; frame_len],
        }
    }

    pub(crate) fn as_slice(&self) -> &[u8] {
        &self.data
    }

    pub(crate) fn len(&self) -> usize {
        self.data.len()
    }

    pub(crate) fn clear(&mut self) {
        self.data.fill(0);
    }

    pub(crate) fn write_rgba(&mut self, source: &[u8], color_order: ColorOrder) {
        debug_assert_eq!(self.data.len(), source.len() / 4 * 3);
        let tuning = runtime_tuning();
        let brightness = tuning.matrix_effective_brightness();
        let gamma = tuning.matrix_gamma;
        match color_order {
            ColorOrder::Rgb => copy_rgb888(&mut self.data, source, brightness, gamma),
            ColorOrder::Gbr => copy_rgb888_with_gbr_remap(&mut self.data, source, brightness, gamma),
        }
    }
}

#[derive(Debug)]
pub(crate) struct FrameBufferPool {
    recycled: Vec<FrameBuffer>,
    frame_len: usize,
}

impl FrameBufferPool {
    pub(crate) fn new(frame_len: usize, initial_capacity: usize) -> Self {
        let mut recycled = Vec::with_capacity(initial_capacity);
        for _ in 0..initial_capacity {
            recycled.push(FrameBuffer::new(frame_len));
        }
        Self {
            recycled,
            frame_len,
        }
    }

    pub(crate) fn acquire(&mut self) -> FrameBuffer {
        self.recycled
            .pop()
            .unwrap_or_else(|| FrameBuffer::new(self.frame_len))
    }

    pub(crate) fn recycle(&mut self, frame: FrameBuffer) {
        if frame.len() == self.frame_len {
            self.recycled.push(frame);
        }
    }

    #[cfg(test)]
    #[allow(dead_code)]
    pub(crate) fn available(&self) -> usize {
        self.recycled.len()
    }
}

fn copy_rgb888(destination: &mut [u8], source: &[u8], brightness: f32, gamma: f32) {
    if source.len() >= runtime_tuning().parallel_color_remap_threshold_bytes {
        destination
            .par_chunks_exact_mut(3)
            .zip(source.par_chunks_exact(4))
            .for_each(|(destination_chunk, source_chunk)| {
                destination_chunk[0] = scale_channel(source_chunk[0], brightness, gamma);
                destination_chunk[1] = scale_channel(source_chunk[1], brightness, gamma);
                destination_chunk[2] = scale_channel(source_chunk[2], brightness, gamma);
            });
        return;
    }

    for (destination_chunk, source_chunk) in
        destination.chunks_exact_mut(3).zip(source.chunks_exact(4))
    {
        destination_chunk[0] = scale_channel(source_chunk[0], brightness, gamma);
        destination_chunk[1] = scale_channel(source_chunk[1], brightness, gamma);
        destination_chunk[2] = scale_channel(source_chunk[2], brightness, gamma);
    }
}

fn copy_rgb888_with_gbr_remap(destination: &mut [u8], source: &[u8], brightness: f32, gamma: f32) {
    if source.len() >= runtime_tuning().parallel_color_remap_threshold_bytes {
        destination
            .par_chunks_exact_mut(3)
            .zip(source.par_chunks_exact(4))
            .for_each(|(destination_chunk, source_chunk)| {
                destination_chunk[0] = scale_channel(source_chunk[0], brightness, gamma);
                destination_chunk[1] = scale_channel(source_chunk[2], brightness, gamma);
                destination_chunk[2] = scale_channel(source_chunk[1], brightness, gamma);
            });
        return;
    }

    for (destination_chunk, source_chunk) in
        destination.chunks_exact_mut(3).zip(source.chunks_exact(4))
    {
        destination_chunk[0] = scale_channel(source_chunk[0], brightness, gamma);
        destination_chunk[1] = scale_channel(source_chunk[2], brightness, gamma);
        destination_chunk[2] = scale_channel(source_chunk[1], brightness, gamma);
    }
}

fn scale_channel(value: u8, brightness: f32, gamma: f32) -> u8 {
    let normalized = f32::from(value) / 255.0;
    let adjusted = normalized.powf(gamma) * 255.0 * brightness;

    adjusted.round().clamp(0.0, 255.0) as u8
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn write_rgba_drops_alpha_and_preserves_rgb_order_for_kernel_rgb888() {
        let rgba = [
            1, 2, 3, 255, //
            4, 5, 6, 128,
        ];
        let mut frame = FrameBuffer::new(6);

        frame.write_rgba(&rgba, ColorOrder::Rgb);

        assert_eq!(frame.as_slice(), &[1, 2, 3, 4, 5, 6]);
    }

    #[test]
    fn write_rgba_drops_alpha_and_applies_gbr_panel_remap_before_kernel_submit() {
        let rgba = [
            1, 2, 3, 255, //
            4, 5, 6, 128,
        ];
        let mut frame = FrameBuffer::new(6);

        frame.write_rgba(&rgba, ColorOrder::Gbr);

        assert_eq!(frame.as_slice(), &[1, 3, 2, 4, 6, 5]);
    }

    #[test]
    fn scale_channel_applies_normalized_brightness() {
        assert_eq!(scale_channel(255, 1.0, 1.0), 255);
        assert_eq!(scale_channel(255, 0.8, 1.0), 204);
        assert_eq!(scale_channel(10, 0.5, 1.0), 5);
        assert_eq!(scale_channel(255, 0.0, 1.0), 0);
    }

    #[test]
    fn scale_channel_applies_output_gamma() {
        assert_eq!(scale_channel(255, 1.0, 1.2), 255);
        assert!(scale_channel(128, 1.0, 1.2) < scale_channel(128, 1.0, 1.0));
        assert!(scale_channel(128, 1.0, 0.8) > scale_channel(128, 1.0, 1.0));
    }
}
