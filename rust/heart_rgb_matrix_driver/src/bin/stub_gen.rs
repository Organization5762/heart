use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    let stub = heart_rgb_matrix_driver::stub_info()?;
    stub.generate()?;
    Ok(())
}
