#!/usr/bin/env bash
# Extracts Go/Rust/JS heredocs from pleiades scripts and syntax-checks each one.
# Exit 1 if any block fails; 0 if all pass.
#
# Heredoc naming convention detected:
#   GO_*   → gofmt -e (parse check, no module needed)
#   RUST_* → rustc --edition 2021 --crate-type lib (parse + type check)
#   BUN_*  → node --check (JS parse check)
set -euo pipefail

SCRIPTS_DIR="${1:-root.x86_64/scripts}"
fail=0
total_go=0; total_rust=0; total_js=0

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

check_go() {
    local file="$1" label="$2"
    total_go=$(( total_go + 1 ))
    if ! gofmt -e "$file" > /dev/null 2>&1; then
        echo "FAIL [Go]   $label"
        gofmt -e "$file" 2>&1 | sed 's/^/       /'
        return 1
    fi
    echo "PASS [Go]   $label"
}

check_rust() {
    local file="$1" label="$2"
    total_rust=$(( total_rust + 1 ))
    if ! command -v rustc &>/dev/null; then
        echo "SKIP [Rust] $label (rustc not in PATH)"
        return 0
    fi
    local errors
    errors=$(rustc --edition 2021 --crate-type lib --emit=metadata \
                   -o /dev/null "$file" 2>&1 | grep '^error' || true)
    if [[ -n "$errors" ]]; then
        echo "FAIL [Rust] $label"
        echo "$errors" | sed 's/^/       /'
        return 1
    fi
    echo "PASS [Rust] $label"
}

check_js() {
    local file="$1" label="$2"
    total_js=$(( total_js + 1 ))
    if ! node --check "$file" 2>/dev/null; then
        echo "FAIL [JS]   $label"
        node --check "$file" 2>&1 | sed 's/^/       /'
        return 1
    fi
    echo "PASS [JS]   $label"
}

while IFS= read -r script; do
    [[ "$script" == *.bak.* ]] && continue

    script_base=$(basename "$script")
    marker=""
    lang=""
    outfile=""
    block_idx=0

    while IFS= read -r line; do
        if [[ -z "$marker" ]]; then
            if [[ "$line" =~ \<\<[[:space:]]*\'?(GO_[A-Za-z0-9_]+)\'?[[:space:]]*$ ]]; then
                marker="${BASH_REMATCH[1]}"
                lang="go"
                block_idx=$(( block_idx + 1 ))
                outfile="$tmpdir/${script_base%.sh}_${marker}.go"
                : > "$outfile"
            elif [[ "$line" =~ \<\<[[:space:]]*\'?(RUST_[A-Za-z0-9_]+)\'?[[:space:]]*$ ]]; then
                marker="${BASH_REMATCH[1]}"
                lang="rust"
                block_idx=$(( block_idx + 1 ))
                outfile="$tmpdir/${script_base%.sh}_${marker}.rs"
                : > "$outfile"
            elif [[ "$line" =~ \<\<[[:space:]]*\'?(BUN_[A-Za-z0-9_]+)\'?[[:space:]]*$ ]]; then
                marker="${BASH_REMATCH[1]}"
                lang="js"
                block_idx=$(( block_idx + 1 ))
                outfile="$tmpdir/${script_base%.sh}_${marker}.js"
                : > "$outfile"
            fi
        else
            if [[ "$line" == "$marker" ]]; then
                label="${script_base}::${marker}"
                case "$lang" in
                    go)   check_go   "$outfile" "$label" || fail=1 ;;
                    rust) check_rust "$outfile" "$label" || fail=1 ;;
                    js)   check_js   "$outfile" "$label" || fail=1 ;;
                esac
                marker=""; lang=""; outfile=""
            else
                printf '%s\n' "$line" >> "$outfile"
            fi
        fi
    done < "$script"
done < <(find "$SCRIPTS_DIR" -maxdepth 1 -name '*.sh' | sort)

echo ""
echo "Polyglot syntax check complete — Go:${total_go} Rust:${total_rust} JS:${total_js} blocks checked"
exit $fail
