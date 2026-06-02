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
echo "=== Setup Complete ==="
