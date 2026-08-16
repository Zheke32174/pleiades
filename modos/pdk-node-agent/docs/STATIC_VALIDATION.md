# Static Validation Record

**Draft artifact:** `pleiades-pdk-node-agent-v0.2`  
**Validation environment:** Debian 13 container without a Rust toolchain, `protoc`, systemd PID 1, or outbound package access.

The following checks were completed against the assembled workspace:

- every workspace, crate, and example configuration TOML file parsed successfully;
- both shell bootstrap scripts passed `bash -n`;
- the canonical Protobuf file has balanced message/service braces and contains both required services;
- the Rust runtime path contains no invocation of `sh`, `bash`, `zsh`, or `dash`;
- the Rust sources contain no `unwrap`, `expect`, or `panic!` calls;
- private-key loaders enforce owner-only permissions on Unix;
- capability acceptance rolls back the in-memory cache if durable audit persistence fails;
- workload start is fail-closed if immediate status observation or post-start audit persistence fails;
- controller event acceptance verifies protocol, domain, mTLS source identity, Ed25519 signature, required IDs, and future timestamp skew;
- all example files and documents required for first-node bootstrap are present.

Repository size at validation time:

```text
Rust source lines: 3,386
Repository files: 84
```

## Not yet authoritative

These checks do **not** replace:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace
cargo build --release --workspace
```

Nor do they replace live tests against:

- Tonic/rustls mTLS;
- a real systemd D-Bus manager;
- SQLite crash recovery;
- network partitions between Alienware and Lenovo;
- lease expiry while a transient unit is active.

The absence of a local compiler is recorded explicitly so static drafting confidence is not mistaken for a passing build.
