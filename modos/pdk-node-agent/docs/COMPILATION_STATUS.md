# Compilation Status

The workspace was structurally assembled and statically inspected in an environment that did not contain `rustc`, `cargo`, or `protoc`, and that had no outbound DNS access for installing them.

Therefore:

- TOML and repository structure can be checked locally;
- the Rust code has **not** been compiled in the drafting environment;
- generated Tonic bindings have **not** been emitted here;
- systemd D-Bus behavior has **not** been exercised against a live PID 1;
- no claim of passing `cargo test` is made.

The first authoritative validation is the command sequence in `BUILD_AND_BOOTSTRAP.md`. Any compiler/API corrections found there should be committed as the first implementation ADR rather than silently patched outside the canonical repository.
