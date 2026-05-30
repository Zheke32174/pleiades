#!/usr/bin/env bash
# PreToolUse hook — scan inbound tool-call content for credential-shaped strings.
#
# Inspired by `parry` (https://github.com/vaporif/parry). Reads the tool call's
# JSON input from stdin (PreToolUse hook payload) and exits non-zero if it
# detects high-confidence credential patterns. The harness blocks the tool
# call and surfaces the message.
#
# Patterns matched (high confidence — low false-positive rate intended):
#   - sk-ant-* / sk-* (Anthropic/OpenAI API key shape)
#   - Bearer tokens that look like JWT (eyJ... three dot-separated parts)
#   - Google OAuth refresh tokens (1//... ya29.*)
#   - GitHub PATs (ghp_*, ghs_*, gho_*, ghu_*, ghr_*)
#   - AWS access keys (AKIA[0-9A-Z]{16})
#
# What it does NOT do:
#   - block arbitrary "looks suspicious" strings (would block too many
#     legitimate inputs)
#   - scan tool *output* (output truncation is separate; this only gates
#     the call itself)
#
# Wired in .claude/settings.json under hooks.PreToolUse.

set -uo pipefail

# Read the hook payload from stdin
PAYLOAD=$(cat)

# Patterns. Each line: name:regex
PATTERNS=$(cat <<'EOF'
anthropic_key:sk-ant-[A-Za-z0-9_-]{32,}
openai_key:sk-(proj-)?[A-Za-z0-9_-]{20,}
google_refresh:1//[A-Za-z0-9_-]{50,}
google_access:ya29\.[A-Za-z0-9_-]{20,}
github_pat:gh[psorlu]_[A-Za-z0-9_]{36,}
aws_access:AKIA[0-9A-Z]{16}
jwt_token:eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}
EOF
)

HITS=()
while IFS= read -r line; do
  name="${line%%:*}"
  pattern="${line#*:}"
  if echo "$PAYLOAD" | grep -qE "$pattern"; then
    HITS+=("$name")
  fi
done <<<"$PATTERNS"

if [ "${#HITS[@]}" -gt 0 ]; then
  # Don't echo the pattern match — that would print the credential.
  # Just list which categories tripped.
  echo "BLOCKED: pre-tool credential scan flagged: ${HITS[*]}" >&2
  echo "  If this is a false positive (e.g., reading a config file in a sandbox)," >&2
  echo "  run the tool call manually outside the agent or refactor the call to" >&2
  echo "  consume the secret via a file rather than embedding it in the command." >&2
  exit 2  # non-zero exit blocks the tool call per PreToolUse hook contract
fi

exit 0
