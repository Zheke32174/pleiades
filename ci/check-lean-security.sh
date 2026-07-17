#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-lean}"
fail=0

bad() { echo "[lean-security] ERROR: $*" >&2; fail=1; }
ok()  { echo "[lean-security] OK: $*"; }

[[ -d "$ROOT/agents" && -d "$ROOT/units" ]] || {
  echo "usage: $0 [lean-root]" >&2
  exit 2
}

if grep -RInE 'journalctl[[:space:]].*--vacuum|curl[^|]*\|[[:space:]]*(sh|bash)|Restart=always' "$ROOT"; then
  bad "prohibited self-erasure, curl-pipe execution, or infinite restart policy found"
else
  ok "no journal vacuum, curl-pipe execution, or Restart=always"
fi

if grep -RInE '^[[:space:]]*while[[:space:]]+(true|:)' "$ROOT/agents"; then
  bad "in-process infinite loop found; use event activation or a timer"
else
  ok "no in-process infinite agent loops"
fi

if grep -RIn '/mnt/c' "$ROOT"; then
  bad "direct Windows drive access found in lean runtime"
else
  ok "no direct /mnt/c access"
fi

# Only the dedicated Maia bridge ingester may reference the narrow read-only
# /host/win spool during this migration phase.
host_refs=$(grep -RIl '/host/' "$ROOT/agents" || true)
for f in $host_refs; do
  [[ "$f" == "$ROOT/agents/maia/maia-overseer.sh" ]] || bad "unauthorized host reference: $f"
done
[[ -z "$host_refs" || "$host_refs" == "$ROOT/agents/maia/maia-overseer.sh" ]] && ok "host references limited to Maia bridge ingestion"

for unit in "$ROOT"/units/*.service; do
  [[ -e "$unit" ]] || continue
  for directive in 'NoNewPrivileges=yes' 'ProtectSystem=strict' 'ProtectHome=yes' 'PrivateTmp=yes' 'Slice=pleiades.slice'; do
    grep -Fxq "$directive" "$unit" || bad "$(basename "$unit") missing $directive"
  done
done

for unit in "$ROOT"/units/pleiades-taygete@.service "$ROOT"/units/pleiades-electra-http@.service "$ROOT"/units/pleiades-electra-telnet@.service; do
  for directive in 'RuntimeMaxSec=15' 'MemoryMax=32M' 'CPUQuota=10%'; do
    grep -Fxq "$directive" "$unit" || bad "$(basename "$unit") missing $directive"
  done
done

if grep -RInE '(^|[^[:alnum:]_])(exec|eval)[[:space:]]+\$|bash[[:space:]]+-c[[:space:]]+"?\$' "$ROOT/agents"; then
  bad "dynamic command execution found in a lean agent"
else
  ok "no obvious dynamic shell execution in lean agents"
fi

python3 -m json.tool "$ROOT/policy/authority-actions.v1.json" >/dev/null || bad "authority policy is invalid JSON"

if [[ "$fail" -ne 0 ]]; then
  echo "[lean-security] FAILED" >&2
  exit 1
fi

echo "[lean-security] PASSED"
