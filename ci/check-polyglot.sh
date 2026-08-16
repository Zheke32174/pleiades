#!/usr/bin/env bash
# Extracts Go/Rust/JS heredocs from pleiades scripts and syntax-checks each one.
# Exit 1 if any block fails; 0 if all pass.
#
# Heredoc naming convention detected:
#   GO_*   → gofmt -e (parse check, no module needed)
#   RUST_* → rustfmt parse/emit (syntax check without resolving dependencies)
#   BUN_*  → node --check (JS parse check)
set -euo pipefail

SCRIPTS_DIR="${1:-root.x86_64/scripts}"
fail=0
total_go=0; total_rust=0; total_js=0

if [[ ! -d "$SCRIPTS_DIR" ]]; then
    echo "ERROR: scripts directory does not exist: $SCRIPTS_DIR" >&2
    exit 1
fi

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
    if ! command -v rustfmt &>/dev/null; then
        echo "SKIP [Rust] $label (rustfmt not in PATH)"
        return 0
    fi

    # rustc performs name/type resolution and therefore rejects otherwise-valid
    # standalone fragments that depend on crates supplied by their generated
    # Cargo project. rustfmt parses the Rust grammar without manufacturing that
    # false dependency failure. Emit to stdout so formatting differences do not
    # make this syntax-only check fail.
    local error_file="$tmpdir/rustfmt-$total_rust.err"
    if ! rustfmt --edition 2021 --emit stdout "$file" > /dev/null 2>"$error_file"; then
        echo "FAIL [Rust] $label"
        sed 's/^/       /' "$error_file"
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

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ -z "$marker" ]]; then
            if [[ "$line" =~ \<\<[[:space:]]*\'?(GO_[A-Za-z0-9_]+)\'?[[:space:]]*$ ]]; then
                marker="${BASH_REMATCH[1]}"
                lang="go"
                outfile="$tmpdir/${script_base%.sh}_${marker}.go"
                : > "$outfile"
            elif [[ "$line" =~ \<\<[[:space:]]*\'?(RUST_[A-Za-z0-9_]+)\'?[[:space:]]*$ ]]; then
                marker="${BASH_REMATCH[1]}"
                lang="rust"
                outfile="$tmpdir/${script_base%.sh}_${marker}.rs"
                : > "$outfile"
            elif [[ "$line" =~ \<\<[[:space:]]*\'?(BUN_[A-Za-z0-9_]+)\'?[[:space:]]*$ ]]; then
                marker="${BASH_REMATCH[1]}"
                lang="js"
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

    if [[ -n "$marker" ]]; then
        echo "FAIL [${lang}] ${script_base}::${marker} (unterminated heredoc)"
        fail=1
    fi
done < <(find "$SCRIPTS_DIR" -maxdepth 1 -type f -name '*.sh' | sort)

echo ""
echo "Polyglot syntax check complete — Go:${total_go} Rust:${total_rust} JS:${total_js} blocks checked"
exit $fail
