use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use pyo3_stub_gen::define_stub_info_gatherer;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};

const EMPTY_SCENE_MANAGER_ERROR: &str = "Scene manager bridge requires at least one scene name.";
const SCENE_BRIDGE_VERSION: &str = env!("CARGO_PKG_VERSION");

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

#[gen_stub_pyclass]
#[pyclass(module = "heart_rust", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct SceneManagerBridge {
    scene_names: Vec<String>,
    offset_button_value: Option<i64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SceneManagerBridge {
    #[new]
    fn new(scene_names: Vec<String>) -> PyResult<Self> {
        if scene_names.is_empty() {
            return Err(PyValueError::new_err(EMPTY_SCENE_MANAGER_ERROR));
        }
        Ok(Self {
            scene_names,
            offset_button_value: None,
        })
    }

    fn active_scene_index(&self, current_button_value: i64) -> PyResult<usize> {
        self.active_index(current_button_value)
    }

    fn register_scene(&mut self, scene_name: String) {
        self.scene_names.push(scene_name);
    }

    fn reset_button_offset(&mut self, current_button_value: i64) {
        self.offset_button_value = Some(current_button_value);
    }

    fn scene_count(&self) -> usize {
        self.scene_names.len()
    }

    fn scene_names(&self) -> Vec<String> {
        self.scene_names.clone()
    }

    fn snapshot(&self, current_button_value: i64) -> PyResult<SceneSnapshot> {
        let active_scene_index = self.active_index(current_button_value)?;
        Ok(SceneSnapshot {
            active_scene_index,
            active_scene_name: self.scene_names[active_scene_index].clone(),
            current_button_value,
            offset_button_value: self.offset_button_value,
            scene_count: self.scene_names.len(),
        })
    }
}

impl SceneManagerBridge {
    fn active_index(&self, current_button_value: i64) -> PyResult<usize> {
        if self.scene_names.is_empty() {
            return Err(PyValueError::new_err(EMPTY_SCENE_MANAGER_ERROR));
        }
        let offset = self.offset_button_value.unwrap_or_default();
        let count = self.scene_names.len() as i64;
        let raw_index = (current_button_value - offset).rem_euclid(count);
        Ok(raw_index as usize)
    }
}

#[gen_stub_pyfunction]
#[pyfunction]
fn bridge_version() -> &'static str {
    SCENE_BRIDGE_VERSION
}

#[pymodule]
#[pyo3(name = "_heart_rust")]
fn heart_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<SceneManagerBridge>()?;
    module.add_class::<SceneSnapshot>()?;
    module.add_function(wrap_pyfunction!(bridge_version, module)?)?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
