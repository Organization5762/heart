use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    let stub = heart_rust::stub_info()?;
    stub.generate()?;
    Ok(())
}
