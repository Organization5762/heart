use std::time::Instant;

#[derive(Clone, Debug)]
pub struct MatrixStatsCore {
    pub width: u32,
    pub height: u32,
    pub dropped_frames: u64,
    pub rendered_frames: u64,
    pub refresh_hz_estimate: f32,
    pub backend_name: String,
}

#[derive(Debug)]
pub(crate) struct WorkerStats {
    dropped_frames: u64,
    rendered_frames: u64,
    refresh_hz_estimate: f32,
    last_render_at: Option<Instant>,
}

impl WorkerStats {
    pub(crate) fn new() -> Self {
        Self {
            dropped_frames: 0,
            rendered_frames: 0,
            refresh_hz_estimate: 0.0,
            last_render_at: None,
        }
    }

    pub(crate) fn record_drop(&mut self) {
        self.dropped_frames = self.dropped_frames.saturating_add(1);
    }

    pub(crate) fn record_render(&mut self) {
        let now = Instant::now();
        if let Some(previous_render_at) = self.last_render_at {
            let elapsed = now.duration_since(previous_render_at).as_secs_f32();
            if elapsed > 0.0 {
                self.refresh_hz_estimate = 1.0 / elapsed;
            }
        }
        self.last_render_at = Some(now);
        self.rendered_frames = self.rendered_frames.saturating_add(1);
    }

    pub(crate) fn snapshot(&self, width: u32, height: u32, backend_name: &str) -> MatrixStatsCore {
        MatrixStatsCore {
            width,
            height,
            dropped_frames: self.dropped_frames,
            rendered_frames: self.rendered_frames,
            refresh_hz_estimate: self.refresh_hz_estimate,
            backend_name: backend_name.to_string(),
        }
    }

    #[cfg(test)]
    pub(crate) fn dropped_frames(&self) -> u64 {
        self.dropped_frames
    }
}
