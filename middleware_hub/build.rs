fn main() -> Result<(), Box<dyn std::error::Error>> {
    std::env::set_var("PROTOC", protoc_bin_vendored::protoc_bin_path()?);
    prost_build::compile_protos(&["../proto/skhy_telemetry.proto"], &["../proto/"])?;
    Ok(())
}
