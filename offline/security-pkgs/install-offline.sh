#!/usr/bin/env bash
# install-offline.sh — air-gapped purple team security baseline installer
# Task #21
set -euo pipefail
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
CONTAINER="${CONTAINER_ROOT:-${PLEIADES_ROOT:-${HOME}/pleiades}/rootfs}"
BINPKG_DIR="$CONTAINER/var/cache/binpkgs"
log() { printf '[offline-install] %s\n' "$*" >&2; }

[[ -f "$SCRIPT_DIR/MANIFEST.json" ]] || { log "MANIFEST.json not found"; exit 1; }
mkdir -p "$BINPKG_DIR"

python3 - "$SCRIPT_DIR/MANIFEST.json" "$BINPKG_DIR" << 'PYEOF'
import json, shutil, hashlib, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text())
binpkg_dir = Path(sys.argv[2])
errors = 0
for pkg in manifest.get("packages", []):
    src = Path(sys.argv[1]).parent / pkg["file"]
    if not src.exists():
        print(f"  MISSING: {pkg['file']}")
        errors += 1
        continue
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    if sha != pkg.get("sha256", sha):
        print(f"  CHECKSUM FAIL: {pkg['file']}")
        errors += 1
        continue
    shutil.copy2(src, binpkg_dir / src.name)
    print(f"  OK: {pkg['file']}")
sys.exit(errors)
PYEOF

log "Installing packages via emerge --usepkgonly"
ATOMS=$(python3 -c "import json; d=json.load(open('$SCRIPT_DIR/MANIFEST.json')); print(' '.join(p['atom'] for p in d.get('packages',[])))" 2>/dev/null || true)
if [[ -n "$ATOMS" ]] && command -v emerge &>/dev/null; then
    emerge --usepkgonly --root="$CONTAINER" $ATOMS 2>/dev/null || log "WARN: some packages failed"
else
    log "emerge not available or no atoms — copy to $BINPKG_DIR complete"
fi
log "Offline install done"
