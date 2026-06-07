#!/usr/bin/env bash
# Developing Mind — substrate-sync (AST Validated & Dynamic)
# Arxiv Anchor: 2410.02724 & 2604.24579

# Detect base directory (Dynamic)
REPRO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
GGA_PATH="${REPRO_DIR}/../scripts/gga_repo/bin/gga"
if [ ! -f "$GGA_PATH" ]; then
    GGA_PATH="./scripts/gga_repo/bin/gga"
fi

cd "$REPRO_DIR"

echo "🔍 Validating AST..."
python3 scripts/ast_validator.py src/
if [ $? -ne 0 ]; then
    echo "❌ AST Validation failed. Aborting sync."
    exit 1
fi

echo "👼 Guardian Angel: Reviewing cognitive snapshot..."
git add .
"$GGA_PATH" run
if [ $? -eq 0 ]; then
    echo "✅ Review passed. Syncing to GitHub..."
    MSG="${1:-PSS: Algorithmic Snapshot with AST Validation - Gated by GGA}"
    git commit -m "$MSG"
    git push origin master
else
    echo " Guardian Angel rejected the snapshot."
    exit 1
fi
