# Build and Bootstrap

## 1. Prerequisites

On Ubuntu Server:

```bash
sudo apt update
sudo apt install -y build-essential pkg-config libssl-dev protobuf-compiler openssl
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"
rustup update stable
```

The workspace declares Rust 1.95 because its current dependency set includes sysinfo 0.39.x. Adjust only after dependency/MSRV verification.

## 2. Validate and build

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
cargo build --release --workspace
```

Install binaries:

```bash
sudo install -d -m 0755 /usr/local/libexec/pleiades
sudo install -m 0755 target/release/pdk-controller /usr/local/libexec/pleiades/
sudo install -m 0755 target/release/pdk-node-agent /usr/local/libexec/pleiades/
sudo install -m 0755 target/release/pdk-admin /usr/local/libexec/pleiades/
sudo install -m 0755 target/release/pdk-keygen /usr/local/libexec/pleiades/
```

## 3. Create TLS identities

Run on an offline or carefully controlled bootstrap host:

```bash
./scripts/bootstrap-local-ca.sh ./local-pki
```

Copy:

- controller certificate/key + CA to Alienware controller;
- Alienware node certificate/key + CA to Alienware node agent;
- Lenovo node certificate/key + CA to Lenovo;
- controller certificate/key + CA to the host running `pdk-admin`.

After enrollment, move `ca.key.pem` offline. Populate the certificate fingerprints in the TOML files from `fingerprints.txt`.

Name resolution for the templates:

```text
controller.pdk.local        -> Alienware control-plane address
alienware-node.pdk.local    -> Alienware node-agent address
lenovo-node.pdk.local       -> Lenovo node-agent address
```

Use local DNS or temporary `/etc/hosts` entries during the laboratory phase.

## 4. Create Ed25519 protocol keys

```bash
cargo build --release -p pdk-keygen
./scripts/generate-message-signing-keys.sh ./message-signing-keys
```

Copy each JSON private key only to its owning principal. Insert each printed public key into the corresponding trust list.

## 5. Install configuration and units

```bash
sudo install -d -m 0700 /etc/pleiades/keys /etc/pleiades/pki
sudo install -d -m 0750 /var/lib/pleiades/node-agent
sudo install -m 0644 systemd/pleiades-workloads.slice /etc/systemd/system/
sudo install -m 0644 systemd/pdk-controller.service /etc/systemd/system/
sudo install -m 0644 systemd/pdk-node-agent.service /etc/systemd/system/
```

Place the correct node-specific TOML at `/etc/pleiades/pdk-node-agent.toml`. Place the controller TOML only on Alienware. Keep all private key files mode `0600`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pleiades-workloads.slice
sudo systemctl enable --now pdk-controller.service      # Alienware only
sudo systemctl enable --now pdk-node-agent.service      # both nodes
```

## 6. First bounded workload

From the administrative control surface:

```bash
pdk-admin --config /etc/pleiades/pdk-admin.toml run \
  --node node://pleiades/lenovo \
  --workload-id epoch2-proof-of-life \
  --executable /usr/bin/sleep \
  --arg 30 \
  --network-denied true
```

Then inspect or stop it:

```bash
pdk-admin --config /etc/pleiades/pdk-admin.toml status \
  --node node://pleiades/lenovo \
  --workload-id epoch2-proof-of-life

pdk-admin --config /etc/pleiades/pdk-admin.toml stop \
  --node node://pleiades/lenovo \
  --workload-id epoch2-proof-of-life \
  --reason "Epoch 2 validation complete"
```

This still names a node. Host-neutral placement belongs to the next scheduler slice.

## 7. Partition test

1. Confirm Lenovo is `Connected`.
2. Interrupt only its path to the controller.
3. Wait past the 15-second threshold.
4. Confirm state changes to `DegradedAutonomous` without process death or audit loss.
5. Confirm a new grant is rejected.
6. Restore connectivity.
7. Confirm signed heartbeat ACK returns the node to `Connected`.
8. Confirm buffered events drain in order and disappear locally only after signed ACKs.
