#!/usr/bin/env bash
# Shared backup helper for Purple project scripts and CLI harnesses.
# Usage: source this file, then call purple_backup_file /path/to/file [reason]

purple_backup_agent() {
    local agent="${PURPLE_BACKUP_AGENT:-${CODEX_AGENT_NAME:-${CLAUDE_AGENT_NAME:-agent}}}"
    agent="${agent//[^A-Za-z0-9_.-]/_}"
    [[ -n "$agent" ]] || agent="agent"
    printf '%s' "$agent"
}

purple_backup_manifest_dir() {
    printf '%s' "${PURPLE_BACKUP_MANIFEST_DIR:-/workspaces/gentoo/.purple-backups}"
}

purple_backup_file() {
    local file="$1"
    local reason="${2:-manual-change}"
    local agent ts base candidate i manifest_dir manifest tmp

    [[ -e "$file" ]] || return 0
    [[ -f "$file" || -L "$file" ]] || {
        printf 'purple-backup: refusing non-file path: %s\n' "$file" >&2
        return 2
    }

    agent="$(purple_backup_agent)"
    ts="$(date +%s)"
    base="${file}.bak.${ts}"
    candidate="${base}.${agent}.$$"
    i=0
    while [[ -e "$candidate" ]]; do
        i=$((i + 1))
        candidate="${base}.${agent}.$$.$i"
    done

    cp -a -- "$file" "$candidate"

    manifest_dir="$(purple_backup_manifest_dir)"
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
}
