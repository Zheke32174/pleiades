use std::path::PathBuf;

use anyhow::Result;
use clap::Parser;
use pdk_crypto::{generate_key_file, write_key_file};

#[derive(Debug, Parser)]
struct Args {
    #[arg(long)]
    key_id: String,
    #[arg(long)]
    out: PathBuf,
}

fn main() -> Result<()> {
    let args = Args::parse();
    let key = generate_key_file(args.key_id);
    write_key_file(&args.out, &key)?;
    println!("key_id={}", key.key_id);
    println!("public_key_base64={}", key.public_key_base64);
    Ok(())
}
