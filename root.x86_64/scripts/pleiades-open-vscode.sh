#!/bin/bash
# Launch VS Code Insiders with pleiades workspace from WSL
# Run this from WSL to open the pleiades ecosystem workspace in VS Code Insiders

WORKSPACE="/mnt/c/Users/Fixxia/AppData/Roaming/pleiades-workspace/pleiades-ecosystem.code-workspace"
VSCODE="/mnt/c/Users/Fixxia/AppData/Local/Programs/Microsoft VS Code Insiders/bin/code-insiders"

if [[ -f "$VSCODE" ]]; then
    if [[ -f "$WORKSPACE" ]]; then
        echo "Opening $WORKSPACE in VS Code Insiders..."
        "$VSCODE" "$WORKSPACE" --new-window
        echo "VS Code launched. Close this terminal or press Ctrl+C to return."
    else
        echo "Error: Workspace not found at $WORKSPACE"
        echo "Run pleiades-vscode-bridge.sh setup first to generate it."
        exit 1
    fi
else
    echo "Error: VS Code Insiders not found at $VSCODE"
    echo "Install VS Code Insiders or update the path in this script."
    exit 1
fi
