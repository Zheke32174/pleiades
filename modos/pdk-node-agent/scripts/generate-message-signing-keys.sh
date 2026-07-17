#!/usr/bin/env bash
set -euo pipefail

OUT=${1:-./message-signing-keys}
PDK_KEYGEN=${PDK_KEYGEN:-target/release/pdk-keygen}

if [[ -e "$OUT" ]]; then
  echo "Refusing to overwrite existing key directory: $OUT" >&2
  exit 1
fi
if [[ ! -x "$PDK_KEYGEN" ]]; then
  echo "Build pdk-keygen first: cargo build --release -p pdk-keygen" >&2
  exit 1
fi

umask 077
mkdir -p "$OUT"
"$PDK_KEYGEN" --key-id controller-alienware-ed25519-v1 --out "$OUT/controller-signing.json" \
  | tee "$OUT/controller-public.txt"
"$PDK_KEYGEN" --key-id node-alienware-ed25519-v1 --out "$OUT/node-alienware-signing.json" \
  | tee "$OUT/node-alienware-public.txt"
"$PDK_KEYGEN" --key-id node-lenovo-ed25519-v1 --out "$OUT/node-lenovo-signing.json" \
  | tee "$OUT/node-lenovo-public.txt"
chmod 0600 "$OUT"/*.json
