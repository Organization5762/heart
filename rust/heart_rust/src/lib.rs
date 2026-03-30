use numpy::ndarray::Array3;
use numpy::{IntoPyArray, PyArray3, PyReadonlyArray3};
use numpy::PyUntypedArrayMethods;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3::wrap_pyfunction;
use pyo3_stub_gen::define_stub_info_gatherer;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};
use safetensors::tensor::{Dtype, TensorView};
use safetensors::SafeTensors;

const EMPTY_SCENE_MANAGER_ERROR: &str = "Scene manager bridge requires at least one scene name.";
const INVALID_SCENE_BUFFER_DIMENSIONS_ERROR: &str =
    "SoftwareSceneBuffer requires positive width and height.";
const INVALID_SCENE_BUFFER_SHAPE_ERROR: &str =
    "blit_array expects a pygame-style array shaped as (width, height, 3|4).";
const INVALID_SCENE_BUFFER_TENSOR_ERROR: &str =
    "Scene safetensor payload must contain a uint8 rgba tensor.";
const SCENE_BRIDGE_VERSION: &str = env!("CARGO_PKG_VERSION");
const SCENE_BUFFER_CHANNELS: usize = 4;
const SCENE_BUFFER_TENSOR_NAME: &str = "rgba";

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

#[gen_stub_pyclass]
#[pyclass(module = "heart_rust", skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct SoftwareSceneBuffer {
    #[pyo3(get)]
    width: usize,
    #[pyo3(get)]
    height: usize,
    pixels: Vec<u8>,
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

#[gen_stub_pymethods]
#[pymethods]
impl SoftwareSceneBuffer {
    #[new]
    fn new(width: usize, height: usize) -> PyResult<Self> {
        Self::validate_dimensions(width, height)?;
        let pixel_count = Self::pixel_count(width, height)?;
        Ok(Self {
            width,
            height,
            pixels: vec![0; pixel_count],
        })
    }

    fn channels(&self) -> usize {
        SCENE_BUFFER_CHANNELS
    }

    fn get_size(&self) -> (usize, usize) {
        (self.width, self.height)
    }

    fn get_width(&self) -> usize {
        self.width
    }

    fn get_height(&self) -> usize {
        self.height
    }

    #[pyo3(signature=(red, green, blue, alpha=255))]
    fn fill_rgba(&mut self, red: u8, green: u8, blue: u8, alpha: u8) {
        self.fill_region(red, green, blue, alpha, None);
    }

    #[pyo3(signature=(red, green, blue, alpha=255, rect=None))]
    fn fill_rect_rgba(
        &mut self,
        red: u8,
        green: u8,
        blue: u8,
        alpha: u8,
        rect: Option<(usize, usize, usize, usize)>,
    ) {
        self.fill_region(red, green, blue, alpha, rect);
    }

    #[pyo3(signature=(source, dest=(0, 0), area=None))]
    fn blit(
        &mut self,
        source: PyRef<'_, SoftwareSceneBuffer>,
        dest: (usize, usize),
        area: Option<(usize, usize, usize, usize)>,
    ) {
        self.blit_from(&source, dest, area);
    }

    #[pyo3(signature=(array, dest=(0, 0)))]
    fn blit_array(
        &mut self,
        array: PyReadonlyArray3<'_, u8>,
        dest: (usize, usize),
    ) -> PyResult<()> {
        let shape = array.shape();
        if shape.len() != 3 || !(shape[2] == 3 || shape[2] == SCENE_BUFFER_CHANNELS) {
            return Err(PyValueError::new_err(INVALID_SCENE_BUFFER_SHAPE_ERROR));
        }

        let width = shape[0];
        let height = shape[1];
        let channels = shape[2];
        let view = array.as_array();

        for x in 0..width {
            let Some(dest_x) = dest.0.checked_add(x) else {
                break;
            };
            if dest_x >= self.width {
                continue;
            }

            for y in 0..height {
                let Some(dest_y) = dest.1.checked_add(y) else {
                    break;
                };
                if dest_y >= self.height {
                    continue;
                }

                let target_offset = self.pixel_offset(dest_x, dest_y);
                self.pixels[target_offset] = view[[x, y, 0]];
                self.pixels[target_offset + 1] = view[[x, y, 1]];
                self.pixels[target_offset + 2] = view[[x, y, 2]];
                self.pixels[target_offset + 3] = if channels == SCENE_BUFFER_CHANNELS {
                    view[[x, y, 3]]
                } else {
                    u8::MAX
                };
            }
        }

        Ok(())
    }

    fn rgba_array<'py>(&self, py: Python<'py>) -> Bound<'py, PyArray3<u8>> {
        Array3::from_shape_fn((self.height, self.width, SCENE_BUFFER_CHANNELS), |(y, x, c)| {
            self.pixels[self.pixel_offset(x, y) + c]
        })
        .into_pyarray(py)
    }

    fn to_safetensors<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyBytes>> {
        let tensor = TensorView::new(
            Dtype::U8,
            vec![self.height, self.width, SCENE_BUFFER_CHANNELS],
            &self.pixels,
        )
        .map_err(Self::safetensor_error)?;
        let serialized = safetensors::serialize(
            [(SCENE_BUFFER_TENSOR_NAME, tensor)],
            None,
        )
        .map_err(Self::safetensor_error)?;
        Ok(PyBytes::new(py, &serialized))
    }

    #[staticmethod]
    fn from_safetensors(buffer: Vec<u8>) -> PyResult<Self> {
        let tensors = SafeTensors::deserialize(&buffer).map_err(Self::safetensor_error)?;
        let tensor = tensors
            .tensor(SCENE_BUFFER_TENSOR_NAME)
            .map_err(Self::safetensor_error)?;

        if tensor.dtype() != Dtype::U8 {
            return Err(PyValueError::new_err(INVALID_SCENE_BUFFER_TENSOR_ERROR));
        }

        let shape = tensor.shape();
        if shape.len() != 3 || shape[2] != SCENE_BUFFER_CHANNELS {
            return Err(PyValueError::new_err(INVALID_SCENE_BUFFER_TENSOR_ERROR));
        }

        let height = shape[0];
        let width = shape[1];
        Self::validate_dimensions(width, height)?;
        let pixel_count = Self::pixel_count(width, height)?;
        if tensor.data().len() != pixel_count {
            return Err(PyValueError::new_err(INVALID_SCENE_BUFFER_TENSOR_ERROR));
        }

        Ok(Self {
            width,
            height,
            pixels: tensor.data().to_vec(),
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

impl SoftwareSceneBuffer {
    fn validate_dimensions(width: usize, height: usize) -> PyResult<()> {
        if width == 0 || height == 0 {
            return Err(PyValueError::new_err(
                INVALID_SCENE_BUFFER_DIMENSIONS_ERROR,
            ));
        }
        Ok(())
    }

    fn pixel_count(width: usize, height: usize) -> PyResult<usize> {
        width
            .checked_mul(height)
            .and_then(|count| count.checked_mul(SCENE_BUFFER_CHANNELS))
            .ok_or_else(|| PyValueError::new_err(INVALID_SCENE_BUFFER_DIMENSIONS_ERROR))
    }

    fn pixel_offset(&self, x: usize, y: usize) -> usize {
        ((y * self.width) + x) * SCENE_BUFFER_CHANNELS
    }

    fn clipped_region(
        &self,
        rect: Option<(usize, usize, usize, usize)>,
    ) -> Option<(usize, usize, usize, usize)> {
        let (x, y, width, height) = rect.unwrap_or((0, 0, self.width, self.height));
        if x >= self.width || y >= self.height || width == 0 || height == 0 {
            return None;
        }
        Some((x, y, width.min(self.width - x), height.min(self.height - y)))
    }

    fn fill_region(
        &mut self,
        red: u8,
        green: u8,
        blue: u8,
        alpha: u8,
        rect: Option<(usize, usize, usize, usize)>,
    ) {
        let Some((start_x, start_y, width, height)) = self.clipped_region(rect) else {
            return;
        };

        for y in start_y..start_y + height {
            for x in start_x..start_x + width {
                let offset = self.pixel_offset(x, y);
                self.pixels[offset] = red;
                self.pixels[offset + 1] = green;
                self.pixels[offset + 2] = blue;
                self.pixels[offset + 3] = alpha;
            }
        }
    }

    fn blit_from(
        &mut self,
        source: &SoftwareSceneBuffer,
        dest: (usize, usize),
        area: Option<(usize, usize, usize, usize)>,
    ) {
        let (source_x, source_y, source_width, source_height) =
            area.unwrap_or((0, 0, source.width, source.height));
        if source_x >= source.width
            || source_y >= source.height
            || source_width == 0
            || source_height == 0
        {
            return;
        }

        let copy_width = source_width.min(source.width - source_x);
        let copy_height = source_height.min(source.height - source_y);

        for rel_y in 0..copy_height {
            let Some(dest_y) = dest.1.checked_add(rel_y) else {
                break;
            };
            if dest_y >= self.height {
                continue;
            }

            for rel_x in 0..copy_width {
                let Some(dest_x) = dest.0.checked_add(rel_x) else {
                    break;
                };
                if dest_x >= self.width {
                    continue;
                }

                let source_offset = source.pixel_offset(source_x + rel_x, source_y + rel_y);
                let dest_offset = self.pixel_offset(dest_x, dest_y);
                self.pixels[dest_offset..dest_offset + SCENE_BUFFER_CHANNELS].copy_from_slice(
                    &source.pixels[source_offset..source_offset + SCENE_BUFFER_CHANNELS],
                );
            }
        }
    }

    fn safetensor_error(err: safetensors::SafeTensorError) -> PyErr {
        PyValueError::new_err(err.to_string())
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
    module.add_class::<SoftwareSceneBuffer>()?;
    module.add_function(wrap_pyfunction!(bridge_version, module)?)?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
