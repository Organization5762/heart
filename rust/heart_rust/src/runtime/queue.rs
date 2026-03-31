use std::collections::VecDeque;

use super::frame::{FrameBuffer, FrameBufferPool, FRAME_POOL_SIZE};
use super::stats::{MatrixStatsCore, WorkerStats};

pub(crate) const MAX_PENDING_FRAMES: usize = 2;

#[derive(Debug)]
pub(crate) struct WorkerState {
    active_frame: Option<FrameBuffer>,
    pending_frames: VecDeque<FrameBuffer>,
    stats: WorkerStats,
    frame_pool: FrameBufferPool,
    closed: bool,
}

impl WorkerState {
    pub(crate) fn new(frame_len: usize) -> Self {
        Self {
            active_frame: None,
            pending_frames: VecDeque::with_capacity(MAX_PENDING_FRAMES),
            stats: WorkerStats::new(),
            frame_pool: FrameBufferPool::new(frame_len, FRAME_POOL_SIZE),
            closed: false,
        }
    }

    pub(crate) fn acquire_frame(&mut self) -> FrameBuffer {
        self.frame_pool.acquire()
    }

    pub(crate) fn recycle_frame(&mut self, frame: FrameBuffer) {
        self.frame_pool.recycle(frame);
    }

    pub(crate) fn submit_frame(&mut self, frame: FrameBuffer) {
        if self.pending_frames.len() == MAX_PENDING_FRAMES {
            if let Some(dropped_frame) = self.pending_frames.pop_front() {
                self.recycle_frame(dropped_frame);
                self.stats.record_drop();
            }
        }
        self.pending_frames.push_back(frame);
    }

    pub(crate) fn promote_pending_frame(&mut self) {
        if let Some(next_frame) = self.pending_frames.pop_front() {
            if let Some(previous_frame) = self.active_frame.replace(next_frame) {
                self.recycle_frame(previous_frame);
            }
        }
    }

    pub(crate) fn clear_display(&mut self) {
        self.recycle_pending_frames();
        let mut blank_frame = self
            .active_frame
            .take()
            .unwrap_or_else(|| self.frame_pool.acquire());
        blank_frame.clear();
        self.active_frame = Some(blank_frame);
    }

    pub(crate) fn has_displayable_frame(&self) -> bool {
        self.active_frame.is_some() || !self.pending_frames.is_empty()
    }

    pub(crate) fn take_active_frame(&mut self) -> Option<FrameBuffer> {
        self.active_frame.take()
    }

    pub(crate) fn restore_active_frame(&mut self, frame: FrameBuffer) {
        if let Some(previous_frame) = self.active_frame.replace(frame) {
            self.recycle_frame(previous_frame);
        }
    }

    pub(crate) fn record_render(&mut self) {
        self.stats.record_render();
    }

    pub(crate) fn stats_snapshot(
        &self,
        width: u32,
        height: u32,
        backend_name: &str,
    ) -> MatrixStatsCore {
        self.stats.snapshot(width, height, backend_name)
    }

    pub(crate) fn mark_closed(&mut self) {
        self.closed = true;
    }

    pub(crate) fn is_closed(&self) -> bool {
        self.closed
    }

    #[cfg(test)]
    pub(crate) fn pending_len(&self) -> usize {
        self.pending_frames.len()
    }

    #[cfg(test)]
    pub(crate) fn available_buffers(&self) -> usize {
        self.frame_pool.available()
    }

    #[cfg(test)]
    pub(crate) fn dropped_frames(&self) -> u64 {
        self.stats.dropped_frames()
    }

    fn recycle_pending_frames(&mut self) {
        while let Some(pending_frame) = self.pending_frames.pop_front() {
            self.recycle_frame(pending_frame);
        }
    }
}
