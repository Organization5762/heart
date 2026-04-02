use std::sync::atomic::{AtomicUsize, Ordering};

use rayon::prelude::*;

use super::config::ColorOrder;
use super::tuning::runtime_tuning;

static NEXT_FRAME_BUFFER_ID: AtomicUsize = AtomicUsize::new(1);

#[derive(Debug)]
pub(crate) struct FrameBuffer {
    data: Vec<u8>,
    buffer_id: usize,
    revision: u64,
}

impl FrameBuffer {
    pub(crate) fn new(frame_len: usize) -> Self {
        Self {
            data: vec![0_u8; frame_len],
            buffer_id: NEXT_FRAME_BUFFER_ID.fetch_add(1, Ordering::Relaxed),
            revision: 0,
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
        self.revision = self.revision.wrapping_add(1);
    }

    pub(crate) fn write_rgba(&mut self, source: &[u8], color_order: ColorOrder) {
        debug_assert_eq!(self.data.len(), source.len());
        match color_order {
            ColorOrder::Rgb => self.data.copy_from_slice(source),
            ColorOrder::Gbr => copy_with_gbr_remap(&mut self.data, source),
        }
        self.revision = self.revision.wrapping_add(1);
    }

    pub(crate) fn identity(&self) -> (usize, u64) {
        (self.buffer_id, self.revision)
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
    pub(crate) fn available(&self) -> usize {
        self.recycled.len()
    }
}

fn copy_with_gbr_remap(destination: &mut [u8], source: &[u8]) {
    if source.len() >= runtime_tuning().parallel_color_remap_threshold_bytes {
        destination
            .par_chunks_exact_mut(4)
            .zip(source.par_chunks_exact(4))
            .for_each(|(destination_chunk, source_chunk)| {
                destination_chunk[0] = source_chunk[0];
                destination_chunk[1] = source_chunk[2];
                destination_chunk[2] = source_chunk[1];
                destination_chunk[3] = source_chunk[3];
            });
        return;
    }

    for (destination_chunk, source_chunk) in
        destination.chunks_exact_mut(4).zip(source.chunks_exact(4))
    {
        destination_chunk[0] = source_chunk[0];
        destination_chunk[1] = source_chunk[2];
        destination_chunk[2] = source_chunk[1];
        destination_chunk[3] = source_chunk[3];
    }
}
