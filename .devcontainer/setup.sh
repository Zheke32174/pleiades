#!/usr/bin/env bash
# Pleiades devcontainer setup — bootstrap the purple team dev environment
#
# Third-party tools installed by this script (not vendored — installed from upstream):
#   gosec    securego (securego org)  Apache-2.0  https://github.com/securego/gosec
#   amass    owasp-amass (OWASP)      Apache-2.0  https://github.com/owasp-amass/amass
set -euo pipefail

echo "=== Pleiades DevContainer Setup ==="

# Install system deps
sudo apt-get update -qq
sudo apt-get install -y -qq shellcheck jq yamllint git curl 2>/dev/null

# Install Go tools
go install github.com/securego/gosec/v2/cmd/gosec@latest 2>/dev/null &
go install github.com/owasp-amass/amass/v4/...@master 2>/dev/null &

# Install Python tools
pip3 install --quiet --user ansible-lint yamllint 2>/dev/null &

wait

# Install opencode (AI fallback via opencode-go/deepseek-v4-pro)
if ! command -v opencode &>/dev/null; then
    npm install -g opencode-ai 2>/dev/null || true
fi

# Install oc-deepseek fallback wrapper
mkdir -p "$HOME/bin"
cat > "$HOME/bin/oc-deepseek" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# oc-deepseek — fallback to opencode-go/deepseek-v4-pro on rate-limit/quota errors
# Trigger: primary model (Claude/Gemini) returns 429 or quota-exceeded
set -uo pipefail
KEYS_ENV="${HOME}/.config/opencode/keys.env"
[[ -f "$KEYS_ENV" ]] && source "$KEYS_ENV"
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "ERROR: DEEPSEEK_API_KEY not set. See https://platform.deepseek.com/api_keys" >&2; exit 1
fi
exec timeout "${OC_DEEPSEEK_TIMEOUT:-300}" opencode run -m opencode-go/deepseek-v4-pro "$@"
WRAPPER_EOF
chmod +x "$HOME/bin/oc-deepseek"

echo "=== Setup Complete ==="
