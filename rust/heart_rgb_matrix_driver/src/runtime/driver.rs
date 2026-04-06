use std::env;
use std::sync::{Arc, Condvar, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use super::backend::{build_backend, MatrixBackend};
use super::config::{expected_rgba_size, ColorOrder, MatrixConfigNative, WiringProfile};
use super::queue::WorkerState;
use super::stats::MatrixStatsCore;

const MATRIX_DRIVER_CLOSED_ERROR: &str = "Matrix driver is already closed.";

fn driver_log(message: impl AsRef<str>) {
    if env::var_os("HEART_MATRIX_DRIVER_LOG").is_some() {
        eprintln!("[heart_rgb_matrix_driver::driver] {}", message.as_ref());
    }
}

#[derive(Debug)]
struct MatrixRuntime {
    width: u32,
    height: u32,
    backend_name: String,
    color_order: ColorOrder,
    state: Mutex<WorkerState>,
    signal: Condvar,
}

#[derive(Debug)]
pub enum MatrixDriverError {
    Runtime(String),
    Validation(String),
}

impl MatrixDriverError {
    pub(crate) fn runtime(message: impl Into<String>) -> Self {
        Self::Runtime(message.into())
    }

    pub(crate) fn validation(message: impl Into<String>) -> Self {
        Self::Validation(message.into())
    }
}

#[derive(Debug)]
pub struct MatrixDriverCore {
    runtime: Arc<MatrixRuntime>,
    worker: Mutex<Option<JoinHandle<()>>>,
}

impl MatrixDriverCore {
    pub fn new(
        wiring: WiringProfile,
        panel_rows: u16,
        panel_cols: u16,
        chain_length: u16,
        parallel: u8,
        color_order: ColorOrder,
    ) -> Result<Self, MatrixDriverError> {
        driver_log(format!(
            "new wiring={wiring:?} panel_rows={panel_rows} panel_cols={panel_cols} chain_length={chain_length} parallel={parallel} color_order={color_order:?}"
        ));
        let config = MatrixConfigNative::new(
            wiring,
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            color_order,
        )
        .map_err(|error| {
            driver_log(format!("new validation failed: {error}"));
            MatrixDriverError::validation(error)
        })?;
        let width = config.width().map_err(|error| {
            driver_log(format!("width validation failed: {error}"));
            MatrixDriverError::validation(error)
        })?;
        let height = config.height().map_err(|error| {
            driver_log(format!("height validation failed: {error}"));
            MatrixDriverError::validation(error)
        })?;
        let frame_len = config.frame_len().map_err(|error| {
            driver_log(format!("frame_len validation failed: {error}"));
            MatrixDriverError::validation(error)
        })?;
        let (backend, backend_name) = build_backend(&config).map_err(|error| {
            driver_log(format!("backend construction failed: {error}"));
            MatrixDriverError::runtime(error)
        })?;
        let refresh_interval = backend.refresh_interval();
        driver_log(format!(
            "backend selected name={backend_name} width={width} height={height} frame_len={frame_len} refresh_interval_ms={}",
            refresh_interval.as_millis()
        ));

        let runtime = Arc::new(MatrixRuntime {
            width,
            height,
            backend_name,
            color_order: config.color_order,
            state: Mutex::new(WorkerState::new(frame_len)),
            signal: Condvar::new(),
        });
        let worker_runtime = Arc::clone(&runtime);
        let worker = thread::Builder::new()
            .name("heart-rgb-matrix-driver-matrix-runtime".to_string())
            .spawn(move || run_matrix_worker(worker_runtime, backend, refresh_interval))
            .map_err(|error| {
                driver_log(format!("worker spawn failed: {error}"));
                MatrixDriverError::runtime(error.to_string())
            })?;
        driver_log("worker thread spawned");
        Ok(Self {
            runtime,
            worker: Mutex::new(Some(worker)),
        })
    }

    pub fn width(&self) -> u32 {
        self.runtime.width
    }

    pub fn height(&self) -> u32 {
        self.runtime.height
    }

    pub fn submit_rgba(
        &self,
        data: Vec<u8>,
        width: u32,
        height: u32,
    ) -> Result<(), MatrixDriverError> {
        driver_log(format!(
            "submit_rgba width={width} height={height} bytes={}",
            data.len()
        ));
        if width != self.runtime.width || height != self.runtime.height {
            driver_log(format!(
                "submit_rgba rejected geometry expected={}x{} received={}x{}",
                self.runtime.width, self.runtime.height, width, height
            ));
            return Err(MatrixDriverError::validation(format!(
                "submit_rgba expected {expected_width}x{expected_height} but received {width}x{height}.",
                expected_width = self.runtime.width,
                expected_height = self.runtime.height,
            )));
        }
        let expected_size = expected_rgba_size(width, height).ok_or_else(|| {
            driver_log("submit_rgba geometry exceeded supported dimensions");
            MatrixDriverError::validation("Matrix geometry exceeds supported dimensions.")
        })?;
        if data.len() != expected_size {
            driver_log(format!(
                "submit_rgba rejected byte count expected={expected_size} received={}",
                data.len()
            ));
            return Err(MatrixDriverError::validation(format!(
                "submit_rgba expected {expected_size} bytes but received {}.",
                data.len()
            )));
        }

        let mut state = self
            .runtime
            .state
            .lock()
            .map_err(|_| {
                driver_log("submit_rgba failed: runtime lock poisoned");
                MatrixDriverError::runtime("Matrix runtime lock poisoned.")
            })?;
        if state.is_closed() {
            driver_log("submit_rgba rejected: driver already closed");
            return Err(MatrixDriverError::runtime(MATRIX_DRIVER_CLOSED_ERROR));
        }

        let mut frame = state.acquire_frame();
        frame.write_rgba(&data, self.runtime.color_order);
        state.submit_frame(frame);
        let stats = state.stats_snapshot(
            self.runtime.width,
            self.runtime.height,
            &self.runtime.backend_name,
        );
        driver_log(format!(
            "submit_rgba queued dropped_frames={} rendered_frames={}",
            stats.dropped_frames, stats.rendered_frames
        ));
        self.runtime.signal.notify_one();
        Ok(())
    }

    pub fn clear(&self) -> Result<(), MatrixDriverError> {
        driver_log("clear requested");
        let mut state = self
            .runtime
            .state
            .lock()
            .map_err(|_| {
                driver_log("clear failed: runtime lock poisoned");
                MatrixDriverError::runtime("Matrix runtime lock poisoned.")
            })?;
        if state.is_closed() {
            driver_log("clear rejected: driver already closed");
            return Err(MatrixDriverError::runtime(MATRIX_DRIVER_CLOSED_ERROR));
        }
        state.clear_display();
        driver_log("clear queued");
        self.runtime.signal.notify_one();
        Ok(())
    }

    pub fn stats(&self) -> Result<MatrixStatsCore, MatrixDriverError> {
        driver_log("stats requested");
        let state = self
            .runtime
            .state
            .lock()
            .map_err(|_| {
                driver_log("stats failed: runtime lock poisoned");
                MatrixDriverError::runtime("Matrix runtime lock poisoned.")
            })?;
        let snapshot = state.stats_snapshot(
            self.runtime.width,
            self.runtime.height,
            &self.runtime.backend_name,
        );
        driver_log(format!(
            "stats snapshot rendered_frames={} dropped_frames={} refresh_hz_estimate={:.2}",
            snapshot.rendered_frames, snapshot.dropped_frames, snapshot.refresh_hz_estimate
        ));
        Ok(snapshot)
    }

    pub fn close(&self) -> Result<(), MatrixDriverError> {
        self.shutdown_inner()
    }

    fn shutdown_inner(&self) -> Result<(), MatrixDriverError> {
        driver_log("shutdown requested");
        {
            let mut state = self
                .runtime
                .state
                .lock()
                .map_err(|_| {
                    driver_log("shutdown failed: runtime lock poisoned");
                    MatrixDriverError::runtime("Matrix runtime lock poisoned.")
                })?;
            if state.is_closed() {
                driver_log("shutdown skipped: already closed");
                return Ok(());
            }
            state.mark_closed();
            driver_log("runtime marked closed");
            self.runtime.signal.notify_all();
        }

        let mut worker = self
            .worker
            .lock()
            .map_err(|_| {
                driver_log("shutdown failed: worker handle lock poisoned");
                MatrixDriverError::runtime("Matrix worker handle lock poisoned.")
            })?;
        if let Some(join_handle) = worker.take() {
            driver_log("joining worker thread");
            join_handle
                .join()
                .map_err(|_| {
                    driver_log("worker thread panicked during shutdown");
                    MatrixDriverError::runtime("Matrix worker thread panicked.")
                })?;
            driver_log("worker thread joined");
        }
        Ok(())
    }
}

impl Drop for MatrixDriverCore {
    fn drop(&mut self) {
        let _ = self.shutdown_inner();
    }
}

fn run_matrix_worker(
    runtime: Arc<MatrixRuntime>,
    mut backend: Box<dyn MatrixBackend>,
    refresh_interval: Duration,
) {
    let backend_owns_refresh_loop = backend.owns_refresh_loop();
    driver_log(format!(
        "worker starting backend_name={} refresh_interval_ms={} owns_refresh_loop={}",
        runtime.backend_name,
        refresh_interval.as_millis(),
        backend_owns_refresh_loop
    ));
    loop {
        let frame = {
            let mut state = match runtime.state.lock() {
                Ok(state) => state,
                Err(_) => {
                    driver_log("worker exiting: runtime lock poisoned");
                    return;
                }
            };
            while !state.is_closed() && !state.has_displayable_frame() {
                if refresh_interval.is_zero() {
                    // A zero refresh interval means "wait for explicit work",
                    // not "spin on an immediate timeout". The Pi 5 resident
                    // transport owns steady-state refresh once a frame is
                    // submitted, so the generic worker should sleep until a
                    // caller enqueues a replacement frame or a clear request.
                    match runtime.signal.wait(state) {
                        Ok(guard) => state = guard,
                        Err(_) => {
                            driver_log("worker exiting: condvar wait poisoned");
                            return;
                        }
                    }
                } else {
                    match runtime.signal.wait_timeout(state, refresh_interval) {
                        Ok((guard, _)) => state = guard,
                        Err(_) => {
                            driver_log("worker exiting: timed condvar wait poisoned");
                            return;
                        }
                    }
                }
            }
            if state.is_closed() {
                driver_log("worker observed closed state before render");
                return;
            }
            state.promote_pending_frame();
            match state.take_active_frame() {
                Some(frame) => frame,
                None => {
                    driver_log("worker woke without an active frame after promotion");
                    continue;
                }
            }
        };

        driver_log(format!("worker rendering frame bytes={}", frame.as_slice().len()));
        if let Err(error) = backend.render(&frame) {
            driver_log(format!("worker exiting: backend render failed: {error}"));
            return;
        }
        driver_log("worker render completed");
        if !backend_owns_refresh_loop && !refresh_interval.is_zero() {
            driver_log(format!(
                "worker sleeping for refresh_interval_ms={}",
                refresh_interval.as_millis()
            ));
            thread::sleep(refresh_interval);
        }

        let mut state = match runtime.state.lock() {
            Ok(state) => state,
            Err(_) => {
                driver_log("worker exiting after render: runtime lock poisoned");
                return;
            }
        };
        if state.is_closed() {
            state.recycle_frame(frame);
            driver_log("worker recycled frame and exited because runtime closed");
            return;
        }
        state.record_render();
        if backend_owns_refresh_loop {
            // Resident-refresh backends keep the submitted frame alive in
            // hardware, so retaining a second copy in the runtime only
            // creates redundant submissions and cache churn.
            state.recycle_frame(frame);
            driver_log("worker recycled rendered frame because backend owns refresh loop");
        } else {
            state.restore_active_frame(frame);
            driver_log("worker restored rendered frame as active");
        }
    }
}
