#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 - <<'PY'
import tomllib
from pathlib import Path
for path in sorted(Path('.').rglob('*.toml')):
    with path.open('rb') as handle:
        tomllib.load(handle)
    print(f'TOML OK: {path}')
PY

bash -n scripts/bootstrap-local-ca.sh
bash -n scripts/generate-message-signing-keys.sh

python3 - <<'PY'
from pathlib import Path
source = Path('proto/pdk/v1/pdk.proto').read_text()
assert source.count('{') == source.count('}'), 'unbalanced protobuf braces'
assert 'service ControlPlane' in source
assert 'service NodeAgent' in source
print('PROTO STRUCTURE OK')
PY

if grep -RInE 'Command::new\("(sh|bash|zsh|dash)"\)|/bin/(sh|bash)' crates --include='*.rs'; then
    echo 'ERROR: shell invocation detected in Rust sources' >&2
    exit 1
fi

if grep -RInE '\b(unwrap|expect|panic!)\b' crates --include='*.rs'; then
    echo 'ERROR: panic-prone call detected in Rust sources' >&2
    exit 1
fi

printf 'Rust source lines: '
find crates -name '*.rs' -print0 | xargs -0 cat | wc -l
printf 'Repository files: '
find . -type f | wc -l

echo 'STATIC VALIDATION PASSED'
