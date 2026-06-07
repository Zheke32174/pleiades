#!/usr/bin/env bash
# Shared backup helper for Pleiades project scripts and CLI harnesses.
# Usage: source this file, then call pleiades_backup_file /path/to/file [reason]

pleiades_backup_agent() {
    local agent="${PLEIADES_BACKUP_AGENT:-${PURPLE_BACKUP_AGENT:-${CODEX_AGENT_NAME:-${CLAUDE_AGENT_NAME:-agent}}}}"
    agent="${agent//[^A-Za-z0-9_.-]/_}"
    [[ -n "$agent" ]] || agent="agent"
    printf '%s' "$agent"
}

pleiades_backup_manifest_dir() {
    printf '%s' "${PLEIADES_BACKUP_MANIFEST_DIR:-${PURPLE_BACKUP_MANIFEST_DIR:-/workspaces/gentoo/.pleiades-backups}}"
}

pleiades_backup_file() {
    local file="$1"
    local reason="${2:-manual-change}"
    local agent ts base candidate i manifest_dir manifest tmp

    [[ -e "$file" ]] || return 0
    [[ -f "$file" || -L "$file" ]] || {
        printf 'pleiades-backup: refusing non-file path: %s\n' "$file" >&2
        return 2
    }

    agent="$(pleiades_backup_agent)"
    ts="$(date +%s)"
    base="${file}.bak.${ts}"
    candidate="${base}.${agent}.$$"
    i=0
    while [[ -e "$candidate" ]]; do
        i=$((i + 1))
        candidate="${base}.${agent}.$$.$i"
    done

    cp -a -- "$file" "$candidate"

    manifest_dir="$(pleiades_backup_manifest_dir)"
    mkdir -p "$manifest_dir"
    manifest="${manifest_dir}/manifest.jsonl"
    tmp="${manifest_dir}/.manifest.$$.tmp"
    printf '{"timestamp":"%s","agent":"%s","pid":%s,"source":"%s","backup":"%s","reason":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$agent" \
        "$$" \
        "$file" \
        "$candidate" \
        "${reason//\"/\\\"}" > "$tmp"
    cat "$tmp" >> "$manifest"
    rm -f "$tmp"

    printf '%s\n' "$candidate"

    # Rotate old backups
    pleiades_backup_purge_old >/dev/null 2>&1 || true
}

pleiades_backup_purge_old() {
    local manifest_dir max_retention purged_count
    local manifest_file tmp_sorted

    manifest_dir="$(pleiades_backup_manifest_dir)"
    max_retention="${PLEIADES_BACKUP_RETENTION_MAX:-30}"
    manifest_file="$manifest_dir/manifest.jsonl"

    [[ -f "$manifest_file" ]] || { printf '0\n'; return 0; }

    # Use Python to parse JSONL, group by source, purge oldest backups
    purged_count=$(python3 - "$manifest_file" "$max_retention" <<'PYEOF'
import json, os, sys

manifest_file = sys.argv[1]
max_retention = int(sys.argv[2])

entries = []
with open(manifest_file) as f:
    for line in f:
        line = line.strip()
        if line:
            entries.append(json.loads(line))

# Group by source path
by_source = {}
for e in entries:
    src = e.get("source", "")
    by_source.setdefault(src, []).append(e)

purged = 0
to_keep = []
for src, src_entries in by_source.items():
    # Sort ascending by timestamp (oldest first)
    src_entries.sort(key=lambda x: x.get("timestamp", ""))
    if len(src_entries) > max_retention:
        excess = len(src_entries) - max_retention
        for i in range(excess):
            bp = src_entries[i].get("backup", "")
            if bp and os.path.isfile(bp):
                os.remove(bp)
            purged += 1
        to_keep.extend(src_entries[excess:])
    else:
        to_keep.extend(src_entries)

# Rewrite manifest without purged entries
with open(manifest_file, "w") as f:
    for e in to_keep:
        f.write(json.dumps(e, separators=(",", ":")) + "\n")

print(purged)
PYEOF
    )

    printf '%d\n' "$purged_count"
}

pleiades_backup_archive_glob() {
    printf '%s' "${PLEIADES_BACKUP_ARCHIVE_GLOB:-/workspaces/gentoo/rootfs-backup-*.tar.gz}"
}

pleiades_backup_dry_run() {
    local pattern latest latest_size

    pattern="$(pleiades_backup_archive_glob)"
    shopt -s nullglob
    local matches=( $pattern )
    shopt -u nullglob

    if (( ${#matches[@]} == 0 )); then
        echo "valid_archive=no"
        echo "archive_glob=$pattern"
        return 1
    fi

    latest="$(printf '%s\n' "${matches[@]}" | sort | tail -1)"
    latest_size="$(stat -c%s "$latest" 2>/dev/null | tr -d '[:space:]')"
    latest_size="${latest_size:-0}"

    if [[ ! -s "$latest" ]]; then
        echo "valid_archive=no"
        echo "archive_path=$latest"
        echo "archive_bytes=$latest_size"
        return 1
    fi

    if ! python3 - "$latest" <<'PY'
import gzip
import sys

path = sys.argv[1]

try:
    with open(path, "rb") as raw:
        magic = raw.read(2)
        raw.seek(0)
        if magic == b"\x1f\x8b":
            reader = gzip.GzipFile(fileobj=raw)
            header = reader.read(512)
        else:
            header = raw.read(512)
except OSError:
    sys.exit(1)

if len(header) < 512:
    sys.exit(1)

ustar = header[257:262]
name = header[0:100].rstrip(b"\0")
sys.exit(0 if name and ustar == b"ustar" else 1)
PY
    then
        echo "valid_archive=no"
        echo "archive_path=$latest"
        echo "archive_bytes=$latest_size"
        return 1
    fi

    echo "valid_archive=yes"
    echo "archive_path=$latest"
    echo "archive_bytes=$latest_size"
    return 0
}

pleiades_backup_usage() {
    cat <<'USAGE'
usage:
  source pleiades-backup.sh && pleiades_backup_file /path/to/file [reason]
  bash pleiades-backup.sh --dry-run
USAGE
}

pleiades_backup_main() {
    case "${1:-}" in
        --dry-run)
            pleiades_backup_dry_run
            ;;
        --help|-h|"")
            pleiades_backup_usage
            ;;
        *)
            pleiades_backup_usage >&2
            return 2
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    pleiades_backup_main "$@"
fi
