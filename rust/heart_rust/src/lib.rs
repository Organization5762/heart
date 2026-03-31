mod runtime;

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use pyo3_stub_gen::define_stub_info_gatherer;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};

use crate::runtime::{
    MatrixDriverCore, MatrixDriverError, MatrixStatsCore, SceneManagerCore, SceneSnapshotCore,
};

#[gen_stub_pyclass]
#[pyclass(module = "heart_rust", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct NativeMatrixStats {
    #[pyo3(get)]
    width: u32,
    #[pyo3(get)]
    height: u32,
    #[pyo3(get)]
    dropped_frames: u64,
    #[pyo3(get)]
    rendered_frames: u64,
    #[pyo3(get)]
    refresh_hz_estimate: f32,
    #[pyo3(get)]
    backend_name: String,
}

impl From<MatrixStatsCore> for NativeMatrixStats {
    fn from(value: MatrixStatsCore) -> Self {
        Self {
            width: value.width,
            height: value.height,
            dropped_frames: value.dropped_frames,
            rendered_frames: value.rendered_frames,
            refresh_hz_estimate: value.refresh_hz_estimate,
            backend_name: value.backend_name,
        }
    }
}

fn map_matrix_runtime_error(error: MatrixDriverError) -> PyErr {
    match error {
        MatrixDriverError::Runtime(message) => PyRuntimeError::new_err(message),
        MatrixDriverError::Validation(message) => PyValueError::new_err(message),
    }
}

#[gen_stub_pyclass]
#[pyclass(module = "heart_rust", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct SceneSnapshot {
    #[pyo3(get)]
    active_scene_index: usize,
    #[pyo3(get)]
    active_scene_name: String,
    #[pyo3(get)]
    current_button_value: i64,
    #[pyo3(get)]
    offset_button_value: Option<i64>,
    #[pyo3(get)]
    scene_count: usize,
}

impl From<SceneSnapshotCore> for SceneSnapshot {
    fn from(value: SceneSnapshotCore) -> Self {
        Self {
            active_scene_index: value.active_scene_index,
            active_scene_name: value.active_scene_name,
            current_button_value: value.current_button_value,
            offset_button_value: value.offset_button_value,
            scene_count: value.scene_count,
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(module = "heart_rust", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct SceneManagerBridge {
    core: SceneManagerCore,
}

#[gen_stub_pymethods]
#[pymethods]
impl SceneManagerBridge {
    #[new]
    fn new(scene_names: Vec<String>) -> PyResult<Self> {
        let core = SceneManagerCore::new(scene_names).map_err(PyValueError::new_err)?;
        Ok(Self { core })
    }

    fn active_scene_index(&self, current_button_value: i64) -> PyResult<usize> {
        self.core
            .active_scene_index(current_button_value)
            .map_err(PyValueError::new_err)
    }

    fn register_scene(&mut self, scene_name: String) {
        self.core.register_scene(scene_name);
    }

    fn reset_button_offset(&mut self, current_button_value: i64) {
        self.core.reset_button_offset(current_button_value);
    }

    fn scene_count(&self) -> usize {
        self.core.scene_count()
    }

    fn scene_names(&self) -> Vec<String> {
        self.core.scene_names()
    }

    fn snapshot(&self, current_button_value: i64) -> PyResult<SceneSnapshot> {
        self.core
            .snapshot(current_button_value)
            .map(SceneSnapshot::from)
            .map_err(PyValueError::new_err)
    }
}

#[pyclass(module = "heart_rust", skip_from_py_object)]
pub struct NativeMatrixDriver {
    core: MatrixDriverCore,
}

#[pymethods]
impl NativeMatrixDriver {
    #[new]
    fn new(
        py: Python<'_>,
        wiring: String,
        panel_rows: u16,
        panel_cols: u16,
        chain_length: u16,
        parallel: u8,
        color_order: String,
    ) -> PyResult<Self> {
        let core = py
            .detach(move || {
                MatrixDriverCore::new(
                    wiring,
                    panel_rows,
                    panel_cols,
                    chain_length,
                    parallel,
                    color_order,
                )
            })
            .map_err(map_matrix_runtime_error)?;
        Ok(Self { core })
    }

    #[getter]
    fn width(&self) -> u32 {
        self.core.width()
    }

    #[getter]
    fn height(&self) -> u32 {
        self.core.height()
    }

    fn submit_rgba(&self, py: Python<'_>, data: Vec<u8>, width: u32, height: u32) -> PyResult<()> {
        py.detach(move || self.core.submit_rgba(data, width, height))
            .map_err(map_matrix_runtime_error)
    }

    fn clear(&self, py: Python<'_>) -> PyResult<()> {
        py.detach(|| self.core.clear())
            .map_err(map_matrix_runtime_error)
    }

    fn stats(&self, py: Python<'_>) -> PyResult<NativeMatrixStats> {
        py.detach(|| self.core.stats())
            .map(NativeMatrixStats::from)
            .map_err(map_matrix_runtime_error)
    }

    fn close(&self, py: Python<'_>) -> PyResult<()> {
        py.detach(|| self.core.close())
            .map_err(map_matrix_runtime_error)
    }
}

#[gen_stub_pyfunction]
#[pyfunction]
fn bridge_version() -> &'static str {
    runtime::MATRIX_RUNTIME_VERSION
}

#[pymodule]
#[pyo3(name = "_heart_rust")]
fn heart_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<NativeMatrixDriver>()?;
    module.add_class::<NativeMatrixStats>()?;
    module.add_class::<SceneManagerBridge>()?;
    module.add_class::<SceneSnapshot>()?;
    module.add_function(wrap_pyfunction!(bridge_version, module)?)?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
