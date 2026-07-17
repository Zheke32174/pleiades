fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("cargo:rerun-if-changed=../../proto/pdk/v1/pdk.proto");
    tonic_prost_build::configure().compile_protos(
        &["../../proto/pdk/v1/pdk.proto"],
        &["../../proto"],
    )?;
    Ok(())
}
