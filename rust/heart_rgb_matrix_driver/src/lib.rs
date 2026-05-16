mod runtime;

use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3::wrap_pyfunction;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::define_stub_info_gatherer;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};
use std::sync::Mutex;

use crate::runtime::{
    ColorOrder, MatrixDriverCore, MatrixDriverError, MatrixStatsCore, WiringProfile,
};

pub use crate::runtime::{
    read_pack_stats as rp1_hub75_read_pack_stats,
    read_pack_stats_from as rp1_hub75_read_pack_stats_from,
    read_present_stats as rp1_hub75_read_present_stats,
    read_present_stats_from as rp1_hub75_read_present_stats_from,
    read_worker_status as rp1_hub75_read_worker_status,
    read_worker_status_from as rp1_hub75_read_worker_status_from, PackedScanFrame,
    PackedScanFrameStats, Pi5ScanConfig, Pi5ScanTiming, Pi5SimpleProbeMode, Pi5SimpleProbeSession,
    Rp1Hub75PresentStats, Rp1Hub75Stats, Rp1Hub75WorkerStatus, WiringProfile as ProbeWiringProfile,
};
pub use crate::runtime::{
    ColorOrder as RuntimeColorOrder, MatrixDriverCore as RuntimeMatrixDriver,
    MatrixDriverError as RuntimeMatrixDriverError,
};

fn to_py_runtime_error(error: MatrixDriverError) -> PyErr {
    match error {
        MatrixDriverError::Runtime(message) => pyo3::exceptions::PyRuntimeError::new_err(message),
        MatrixDriverError::Validation(message) => pyo3::exceptions::PyValueError::new_err(message),
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(
    eq,
    frozen,
    from_py_object,
    module = "heart_rgb_matrix_driver",
    name = "ColorOrder"
)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NativeColorOrder {
    inner: ColorOrder,
}

impl From<NativeColorOrder> for ColorOrder {
    fn from(value: NativeColorOrder) -> Self {
        value.inner
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
#[allow(non_snake_case)]
impl NativeColorOrder {
    #[classattr]
    fn RGB() -> NativeColorOrder {
        NativeColorOrder {
            inner: ColorOrder::Rgb,
        }
    }

    #[classattr]
    fn GBR() -> NativeColorOrder {
        NativeColorOrder {
            inner: ColorOrder::Gbr,
        }
    }

    #[getter]
    fn value(&self) -> &'static str {
        match self.inner {
            ColorOrder::Rgb => "rgb",
            ColorOrder::Gbr => "gbr",
        }
    }

    fn __repr__(&self) -> String {
        match self.inner {
            ColorOrder::Rgb => "ColorOrder.RGB".to_string(),
            ColorOrder::Gbr => "ColorOrder.GBR".to_string(),
        }
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(
    eq,
    frozen,
    from_py_object,
    module = "heart_rgb_matrix_driver",
    name = "WiringProfile"
)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NativeWiringProfile {
    inner: WiringProfile,
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(
    skip_from_py_object,
    module = "heart_rgb_matrix_driver",
    name = "NativeMatrixStats"
)]
#[derive(Clone, Debug)]
pub struct NativeMatrixStats {
    inner: MatrixStatsCore,
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(
    skip_from_py_object,
    module = "heart_rgb_matrix_driver",
    name = "Rp1Hub75Stats"
)]
#[derive(Clone, Debug)]
pub struct NativeRp1Hub75Stats {
    inner: Rp1Hub75Stats,
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(
    skip_from_py_object,
    module = "heart_rgb_matrix_driver",
    name = "Rp1Hub75PresentStats"
)]
#[derive(Clone, Debug)]
pub struct NativeRp1Hub75PresentStats {
    inner: Rp1Hub75PresentStats,
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(
    skip_from_py_object,
    module = "heart_rgb_matrix_driver",
    name = "Rp1Hub75WorkerStatus"
)]
#[derive(Clone, Debug)]
pub struct NativeRp1Hub75WorkerStatus {
    inner: Rp1Hub75WorkerStatus,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl NativeMatrixStats {
    #[getter]
    fn width(&self) -> u32 {
        self.inner.width
    }

    #[getter]
    fn height(&self) -> u32 {
        self.inner.height
    }

    #[getter]
    fn dropped_frames(&self) -> u64 {
        self.inner.dropped_frames
    }

    #[getter]
    fn rendered_frames(&self) -> u64 {
        self.inner.rendered_frames
    }

    #[getter]
    fn refresh_hz_estimate(&self) -> f32 {
        self.inner.refresh_hz_estimate
    }

    #[getter]
    fn backend_name(&self) -> &str {
        &self.inner.backend_name
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl NativeRp1Hub75Stats {
    #[getter]
    fn frames_packed(&self) -> u32 {
        self.inner.frames_packed
    }

    #[getter]
    fn bytes_packed(&self) -> u64 {
        self.inner.bytes_packed
    }

    #[getter]
    fn last_error(&self) -> u32 {
        self.inner.last_error
    }

    #[getter]
    fn words_per_frame(&self) -> u32 {
        self.inner.words_per_frame
    }

    fn __repr__(&self) -> String {
        format!(
            "Rp1Hub75Stats(frames_packed={}, bytes_packed={}, last_error={}, words_per_frame={})",
            self.inner.frames_packed,
            self.inner.bytes_packed,
            self.inner.last_error,
            self.inner.words_per_frame
        )
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl NativeRp1Hub75PresentStats {
    #[getter]
    fn frames_queued(&self) -> u32 {
        self.inner.frames_queued
    }

    #[getter]
    fn frames_presented(&self) -> u32 {
        self.inner.frames_presented
    }

    #[getter]
    fn frames_dropped(&self) -> u32 {
        self.inner.frames_dropped
    }

    #[getter]
    fn vsync_count(&self) -> u32 {
        self.inner.vsync_count
    }

    #[getter]
    fn queued_seq(&self) -> u32 {
        self.inner.queued_seq
    }

    #[getter]
    fn presented_seq(&self) -> u32 {
        self.inner.presented_seq
    }

    #[getter]
    fn displayed_slot(&self) -> u32 {
        self.inner.displayed_slot
    }

    #[getter]
    fn pending_slot(&self) -> u32 {
        self.inner.pending_slot
    }

    fn __repr__(&self) -> String {
        format!(
            "Rp1Hub75PresentStats(frames_queued={}, frames_presented={}, frames_dropped={}, vsync_count={}, queued_seq={}, presented_seq={}, displayed_slot={}, pending_slot={})",
            self.inner.frames_queued,
            self.inner.frames_presented,
            self.inner.frames_dropped,
            self.inner.vsync_count,
            self.inner.queued_seq,
            self.inner.presented_seq,
            self.inner.displayed_slot,
            self.inner.pending_slot
        )
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl NativeRp1Hub75WorkerStatus {
    #[getter]
    fn state(&self) -> u32 {
        self.inner.state
    }

    #[getter]
    fn flags(&self) -> u32 {
        self.inner.flags
    }

    #[getter]
    fn status_timeout_ms(&self) -> u32 {
        self.inner.status_timeout_ms
    }

    #[getter]
    fn worker_seq(&self) -> u32 {
        self.inner.worker_seq
    }

    #[getter]
    fn vsync_count(&self) -> u32 {
        self.inner.vsync_count
    }

    #[getter]
    fn queued_seq(&self) -> u32 {
        self.inner.queued_seq
    }

    #[getter]
    fn presented_seq(&self) -> u32 {
        self.inner.presented_seq
    }

    #[getter]
    fn displayed_slot(&self) -> u32 {
        self.inner.displayed_slot
    }

    #[getter]
    fn pending_slot(&self) -> u32 {
        self.inner.pending_slot
    }

    #[getter]
    fn frames_queued(&self) -> u32 {
        self.inner.frames_queued
    }

    #[getter]
    fn frames_presented(&self) -> u32 {
        self.inner.frames_presented
    }

    #[getter]
    fn frames_dropped(&self) -> u32 {
        self.inner.frames_dropped
    }

    #[getter]
    fn last_error(&self) -> u32 {
        self.inner.last_error
    }

    #[getter]
    fn last_vsync_ns(&self) -> u64 {
        self.inner.last_vsync_ns
    }

    fn __repr__(&self) -> String {
        format!(
            "Rp1Hub75WorkerStatus(state={}, flags={}, status_timeout_ms={}, worker_seq={}, vsync_count={}, queued_seq={}, presented_seq={}, displayed_slot={}, pending_slot={}, frames_queued={}, frames_presented={}, frames_dropped={}, last_error={}, last_vsync_ns={})",
            self.inner.state,
            self.inner.flags,
            self.inner.status_timeout_ms,
            self.inner.worker_seq,
            self.inner.vsync_count,
            self.inner.queued_seq,
            self.inner.presented_seq,
            self.inner.displayed_slot,
            self.inner.pending_slot,
            self.inner.frames_queued,
            self.inner.frames_presented,
            self.inner.frames_dropped,
            self.inner.last_error,
            self.inner.last_vsync_ns
        )
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(module = "heart_rgb_matrix_driver", name = "NativeMatrixDriver")]
#[derive(Debug)]
pub struct NativeMatrixDriver {
    inner: Mutex<Option<MatrixDriverCore>>,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl NativeMatrixDriver {
    #[new]
    fn new(
        wiring: NativeWiringProfile,
        panel_rows: u16,
        panel_cols: u16,
        chain_length: u16,
        parallel: u8,
        color_order: NativeColorOrder,
    ) -> PyResult<Self> {
        let driver = MatrixDriverCore::new(
            wiring.into(),
            panel_rows,
            panel_cols,
            chain_length,
            parallel,
            color_order.into(),
        )
        .map_err(to_py_runtime_error)?;
        Ok(Self {
            inner: Mutex::new(Some(driver)),
        })
    }

    #[getter]
    fn width(&self) -> PyResult<u32> {
        self.with_driver(|driver| Ok(driver.width()))
    }

    #[getter]
    fn height(&self) -> PyResult<u32> {
        self.with_driver(|driver| Ok(driver.height()))
    }

    fn submit_rgba(&self, data: &Bound<'_, PyBytes>, width: u32, height: u32) -> PyResult<()> {
        self.with_driver(|driver| {
            driver
                .submit_rgba(data.as_bytes().to_vec(), width, height)
                .map_err(to_py_runtime_error)
        })
    }

    fn clear(&self) -> PyResult<()> {
        self.with_driver(|driver| driver.clear().map_err(to_py_runtime_error))
    }

    fn stats(&self) -> PyResult<NativeMatrixStats> {
        self.with_driver(|driver| {
            driver
                .stats()
                .map(|inner| NativeMatrixStats { inner })
                .map_err(to_py_runtime_error)
        })
    }

    fn close(&self) -> PyResult<()> {
        let mut guard = self.inner.lock().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("Native matrix driver lock poisoned.")
        })?;
        if let Some(driver) = guard.take() {
            driver.close().map_err(to_py_runtime_error)?;
        }
        Ok(())
    }
}

impl NativeMatrixDriver {
    fn with_driver<T>(
        &self,
        callback: impl FnOnce(&MatrixDriverCore) -> PyResult<T>,
    ) -> PyResult<T> {
        let guard = self.inner.lock().map_err(|_| {
            pyo3::exceptions::PyRuntimeError::new_err("Native matrix driver lock poisoned.")
        })?;
        let driver = guard.as_ref().ok_or_else(|| {
            pyo3::exceptions::PyRuntimeError::new_err("Native matrix driver is already closed.")
        })?;
        callback(driver)
    }
}

impl From<NativeWiringProfile> for WiringProfile {
    fn from(value: NativeWiringProfile) -> Self {
        value.inner
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
#[allow(non_snake_case)]
impl NativeWiringProfile {
    #[classattr]
    fn AdafruitHatPwm() -> NativeWiringProfile {
        NativeWiringProfile {
            inner: WiringProfile::AdafruitHatPwm,
        }
    }

    #[getter]
    fn value(&self) -> &'static str {
        match self.inner {
            WiringProfile::AdafruitHatPwm => "adafruit_hat_pwm",
        }
    }

    fn __repr__(&self) -> String {
        match self.inner {
            WiringProfile::AdafruitHatPwm => "WiringProfile.AdafruitHatPwm".to_string(),
        }
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn bridge_version() -> &'static str {
    runtime::MATRIX_RUNTIME_VERSION
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (device_path=None))]
fn rp1_hub75_get_stats(device_path: Option<&str>) -> PyResult<NativeRp1Hub75Stats> {
    let inner = match device_path {
        Some(path) => rp1_hub75_read_pack_stats_from(path),
        None => rp1_hub75_read_pack_stats(),
    }
    .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
    Ok(NativeRp1Hub75Stats { inner })
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (device_path=None))]
fn rp1_hub75_get_present_stats(device_path: Option<&str>) -> PyResult<NativeRp1Hub75PresentStats> {
    let inner = match device_path {
        Some(path) => rp1_hub75_read_present_stats_from(path),
        None => rp1_hub75_read_present_stats(),
    }
    .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
    Ok(NativeRp1Hub75PresentStats { inner })
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (device_path=None))]
fn rp1_hub75_get_worker_status(device_path: Option<&str>) -> PyResult<NativeRp1Hub75WorkerStatus> {
    let inner = match device_path {
        Some(path) => rp1_hub75_read_worker_status_from(path),
        None => rp1_hub75_read_worker_status(),
    }
    .map_err(pyo3::exceptions::PyRuntimeError::new_err)?;
    Ok(NativeRp1Hub75WorkerStatus { inner })
}

#[pymodule]
#[pyo3(name = "_heart_rgb_matrix_driver")]
fn heart_rgb_matrix_driver(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<NativeColorOrder>()?;
    module.add_class::<NativeWiringProfile>()?;
    module.add_class::<NativeMatrixStats>()?;
    module.add_class::<NativeRp1Hub75Stats>()?;
    module.add_class::<NativeRp1Hub75PresentStats>()?;
    module.add_class::<NativeRp1Hub75WorkerStatus>()?;
    module.add_class::<NativeMatrixDriver>()?;
    module.add_function(wrap_pyfunction!(bridge_version, module)?)?;
    module.add_function(wrap_pyfunction!(rp1_hub75_get_stats, module)?)?;
    module.add_function(wrap_pyfunction!(rp1_hub75_get_present_stats, module)?)?;
    module.add_function(wrap_pyfunction!(rp1_hub75_get_worker_status, module)?)?;
    Ok(())
}

#[cfg(feature = "stubgen")]
define_stub_info_gatherer!(stub_info);
