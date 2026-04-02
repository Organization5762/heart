use std::sync::{Arc, Condvar, Mutex};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use super::backend::{build_backend, MatrixBackend};
use super::config::{expected_rgba_size, ColorOrder, MatrixConfigNative, WiringProfile};
use super::queue::WorkerState;
use super::stats::MatrixStatsCore;

const MATRIX_DRIVER_CLOSED_ERROR: &str = "Matrix driver is already closed.";

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
        let config = MatrixConfigNative::new(
            wiring,
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            color_order,
        )
        .map_err(MatrixDriverError::validation)?;
        let width = config.width().map_err(MatrixDriverError::validation)?;
        let height = config.height().map_err(MatrixDriverError::validation)?;
        let frame_len = config.frame_len().map_err(MatrixDriverError::validation)?;
        let (backend, backend_name) = build_backend(&config).map_err(MatrixDriverError::runtime)?;
        let refresh_interval = backend.refresh_interval();

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
            .map_err(|error| MatrixDriverError::runtime(error.to_string()))?;
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
        if width != self.runtime.width || height != self.runtime.height {
            return Err(MatrixDriverError::validation(format!(
                "submit_rgba expected {expected_width}x{expected_height} but received {width}x{height}.",
                expected_width = self.runtime.width,
                expected_height = self.runtime.height,
            )));
        }
        let expected_size = expected_rgba_size(width, height).ok_or_else(|| {
            MatrixDriverError::validation("Matrix geometry exceeds supported dimensions.")
        })?;
        if data.len() != expected_size {
            return Err(MatrixDriverError::validation(format!(
                "submit_rgba expected {expected_size} bytes but received {}.",
                data.len()
            )));
        }

        let mut state = self
            .runtime
            .state
            .lock()
            .map_err(|_| MatrixDriverError::runtime("Matrix runtime lock poisoned."))?;
        if state.is_closed() {
            return Err(MatrixDriverError::runtime(MATRIX_DRIVER_CLOSED_ERROR));
        }

        let mut frame = state.acquire_frame();
        frame.write_rgba(&data, self.runtime.color_order);
        state.submit_frame(frame);
        self.runtime.signal.notify_one();
        Ok(())
    }

    pub fn clear(&self) -> Result<(), MatrixDriverError> {
        let mut state = self
            .runtime
            .state
            .lock()
            .map_err(|_| MatrixDriverError::runtime("Matrix runtime lock poisoned."))?;
        if state.is_closed() {
            return Err(MatrixDriverError::runtime(MATRIX_DRIVER_CLOSED_ERROR));
        }
        state.clear_display();
        self.runtime.signal.notify_one();
        Ok(())
    }

    pub fn stats(&self) -> Result<MatrixStatsCore, MatrixDriverError> {
        let state = self
            .runtime
            .state
            .lock()
            .map_err(|_| MatrixDriverError::runtime("Matrix runtime lock poisoned."))?;
        Ok(state.stats_snapshot(
            self.runtime.width,
            self.runtime.height,
            &self.runtime.backend_name,
        ))
    }

    pub fn close(&self) -> Result<(), MatrixDriverError> {
        self.shutdown_inner()
    }

    fn shutdown_inner(&self) -> Result<(), MatrixDriverError> {
        {
            let mut state = self
                .runtime
                .state
                .lock()
                .map_err(|_| MatrixDriverError::runtime("Matrix runtime lock poisoned."))?;
            if state.is_closed() {
                return Ok(());
            }
            state.mark_closed();
            self.runtime.signal.notify_all();
        }

        let mut worker = self
            .worker
            .lock()
            .map_err(|_| MatrixDriverError::runtime("Matrix worker handle lock poisoned."))?;
        if let Some(join_handle) = worker.take() {
            join_handle
                .join()
                .map_err(|_| MatrixDriverError::runtime("Matrix worker thread panicked."))?;
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
    loop {
        let frame = {
            let mut state = match runtime.state.lock() {
                Ok(state) => state,
                Err(_) => return,
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
                        Err(_) => return,
                    }
                } else {
                    match runtime.signal.wait_timeout(state, refresh_interval) {
                        Ok((guard, _)) => state = guard,
                        Err(_) => return,
                    }
                }
            }
            if state.is_closed() {
                return;
            }
            state.promote_pending_frame();
            match state.take_active_frame() {
                Some(frame) => frame,
                None => continue,
            }
        };

        if backend.render(&frame).is_err() {
            return;
        }
        if !backend_owns_refresh_loop && !refresh_interval.is_zero() {
            thread::sleep(refresh_interval);
        }

        let mut state = match runtime.state.lock() {
            Ok(state) => state,
            Err(_) => return,
        };
        if state.is_closed() {
            state.recycle_frame(frame);
            return;
        }
        state.record_render();
        if backend_owns_refresh_loop {
            // Resident-refresh backends keep the submitted frame alive in
            // hardware, so retaining a second copy in the runtime only
            // creates redundant submissions and cache churn.
            state.recycle_frame(frame);
        } else {
            state.restore_active_frame(frame);
        }
    }
}
