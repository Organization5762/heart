mod runtime;

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::define_stub_info_gatherer;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};

use crate::runtime::WiringProfile;

pub use crate::runtime::{
    PackedScanFrame, PackedScanFrameStats, Pi5ScanConfig, Pi5ScanTiming, Pi5SimpleProbeMode,
    Pi5SimpleProbeSession,
    WiringProfile as ProbeWiringProfile,
};

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

#[pymodule]
#[pyo3(name = "_heart_rgb_matrix_driver")]
fn heart_rgb_matrix_driver(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<NativeWiringProfile>()?;
    module.add_function(wrap_pyfunction!(bridge_version, module)?)?;
    Ok(())
}

#[cfg(feature = "stubgen")]
define_stub_info_gatherer!(stub_info);
