#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONHASHSEED=0
export PYTHONDONTWRITEBYTECODE=1
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export PIP_NO_INDEX=1

python - <<'PY'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"CPython 3.12 is required; found {sys.version.split()[0]}")
try:
    import jsonschema
    import yaml
except ImportError as exc:
    raise SystemExit(
        "Pinned validation dependencies are not installed. Provision them from an approved offline wheelhouse matching requirements-modos.txt before running validation."
    ) from exc
print(f"runtime ready: Python {sys.version.split()[0]}, jsonschema {jsonschema.__version__}, PyYAML {yaml.__version__}")
PY

mkdir -p artifacts
python ci/run-modos-convergence.py --continue-on-failure
python modos/convergence/synthetic_rehearsal.py
python modos/convergence/intervention_frontier.py \
  --bundle modos/convergence/repository-ready-intervention.fixture.json \
  --report artifacts/intervention-frontier.json
python ci/scan-public-history.py \
  --mode current \
  --report artifacts/current-tree-sensitivity-receipt.json
python ci/build-modos-validation-package.py

printf '%s\n' "offline MODOS validation completed"
