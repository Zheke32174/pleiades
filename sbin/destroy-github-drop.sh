#!/usr/bin/env bash
set -uo pipefail

MAIA_DIR="/var/lib/.maia"
REPO_FILE="${MAIA_DIR}/github_drop_repo"
TOKEN_FILE="${MAIA_DIR}/github_token"

[ ! -f "$REPO_FILE" ] && { echo "[destroy-drop] No drop repo configured"; exit 0; }

REPO=$(cat "$REPO_FILE")
TOKEN=""
if [[ -f "$TOKEN_FILE" ]]; then
    TOKEN=$(cat "$TOKEN_FILE")
elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
    TOKEN="$GITHUB_TOKEN"
fi

echo "[destroy-drop] Deleting dead drop repo: ${REPO}"

if [[ -n "$TOKEN" ]]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE -H "Authorization: token $TOKEN" "https://api.github.com/repos/${REPO}" 2>/dev/null)
    if [ "$HTTP_CODE" = "204" ]; then
        echo "[destroy-drop] Repo deleted successfully (204)"
    elif [ "$HTTP_CODE" = "404" ]; then
        echo "[destroy-drop] Repo not found — already deleted"
    else
        echo "[destroy-drop] Delete returned HTTP $HTTP_CODE"
    fi
else
    echo "[destroy-drop] WARN: No token available, skipping deletion"
fi

rm -f "$REPO_FILE" "${MAIA_DIR}/github_drop_url" 2>/dev/null || true
echo "[destroy-drop] Local state cleaned"
