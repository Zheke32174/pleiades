#!/usr/bin/env bash
set -uo pipefail

SOPHIA_DIR="/var/lib/.sophia"
mkdir -p "$SOPHIA_DIR"

# Get GitHub token — check saved file, env var, or gh CLI
TOKEN=""
if [[ -f "${SOPHIA_DIR}/github_token" ]]; then
    TOKEN=$(cat "${SOPHIA_DIR}/github_token")
elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
    TOKEN="$GITHUB_TOKEN"
    echo "$TOKEN" > "${SOPHIA_DIR}/github_token"
elif command -v gh &>/dev/null; then
    TOKEN=$(gh auth token 2>/dev/null) && echo "$TOKEN" > "${SOPHIA_DIR}/github_token" || true
fi

if [[ -z "$TOKEN" ]]; then
    echo "[init-drop] ERROR: No GitHub token. Set GITHUB_TOKEN env var or save to ${SOPHIA_DIR}/github_token"
    exit 1
fi

# Get the authenticated username
USERNAME=$(curl -sf -H "Authorization: token $TOKEN" https://api.github.com/user 2>/dev/null | python3 -c "
import sys,json
try:
    print(json.load(sys.stdin)[\"login\"])
except Exception:
    sys.exit(1)
" 2>/dev/null) || {
    echo "[init-drop] ERROR: Cannot determine GitHub user — token may be invalid"
    exit 1
}
echo "[init-drop] Authenticated as: $USERNAME"

# Generate random repo name (pd-<8 random hex chars>)
RAND_SUFFIX=$(openssl rand -hex 4)
REPO_NAME="pd-${RAND_SUFFIX}"

# Check if repo already exists
EXISTS=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: token $TOKEN" "https://api.github.com/repos/${USERNAME}/${REPO_NAME}" 2>/dev/null)

if [ "$EXISTS" = "200" ]; then
    echo "[init-drop] Repo ${USERNAME}/${REPO_NAME} already exists — reusing"
else
    echo "[init-drop] Creating private repo: ${USERNAME}/${REPO_NAME}"
    CREATE_RESP=$(curl -s -X POST -H "Authorization: token $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"${REPO_NAME}\",\"private\":true,\"auto_init\":true,\"description\":\"Purple Team ephemeral dead drop\"}" \
        https://api.github.com/user/repos 2>/dev/null)
    
    # Verify creation
    if echo "$CREATE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get(\"id\") else 1)" 2>/dev/null; then
        echo "[init-drop] Repo created successfully"
    else
        echo "[init-drop] ERROR: Failed to create repo"
        echo "$CREATE_RESP"
        exit 1
    fi
fi

# Wait for repo to be ready (auto_init takes a moment)
sleep 2

# Create signal.json with DORMANT state
TIMESTAMP=$(date +%s)
echo -n "DORMANT" | base64 2>/dev/null > /tmp/_drop_msg_b64 || echo -n "DORMANT" | base64 -w0 2>/dev/null > /tmp/_drop_msg_b64
MSG=$(cat /tmp/_drop_msg_b64)
SIGNATURE="DORMANT"
cat > /tmp/signal.json << JSONEOF
{
  "message": "${MSG}",
  "sig": "${SIGNATURE}",
  "ts": ${TIMESTAMP}
}
JSONEOF

# Push signal.json to repo via GitHub Contents API
B64_CONTENT=$(base64 -w0 /tmp/signal.json 2>/dev/null || base64 /tmp/signal.json | tr -d '\n')
PUT_RESP=$(curl -s -X PUT -H "Authorization: token $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"message\":\"Dead drop signal [init]\",\"content\":\"${B64_CONTENT}\",\"branch\":\"main\"}" \
    "https://api.github.com/repos/${USERNAME}/${REPO_NAME}/contents/signal.json" 2>/dev/null)

# Verify push
PUSH_OK=$(echo "$PUT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get(\"content\") else 1)" 2>/dev/null; echo $?)
if [ "$PUSH_OK" = "0" ]; then
    echo "[init-drop] signal.json pushed to repo"
else
    echo "[init-drop] WARN: push returned: $(echo $PUT_RESP | head -c 200)"
fi

# Store config
echo "${USERNAME}/${REPO_NAME}" > "${SOPHIA_DIR}/github_drop_repo"
echo "https://raw.githubusercontent.com/${USERNAME}/${REPO_NAME}/main/signal.json" > "${SOPHIA_DIR}/github_drop_url"

echo "[init-drop] Active dead drop: ${USERNAME}/${REPO_NAME}"
echo "[init-drop] Signal URL: $(cat ${SOPHIA_DIR}/github_drop_url)"

# Cleanup temp files
rm -rf /tmp/_gh_drop_* /tmp/_drop_msg_b64 /tmp/signal.json 2>/dev/null || true
