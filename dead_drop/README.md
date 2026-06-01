# Dead Drop Signal

This directory contains the resurrection signal for the Purple Team Ouroboros system.

## How it works

The `sophia_crypto probe` binary periodically fetches this file from the raw GitHub URL
and verifies the Ed25519 signature. If the signature is valid and the message decodes to
a recognized command (e.g. "RESURRECT" or "PURGE|AUTHORIZED_PURGE"), the system acts on it.

## To sign a new signal

```bash
# Create the message
echo -n "RESURRECT" | base64 > /tmp/message.b64

# Create the JSON payload
cat > /tmp/signal.json << JSONEOF
{
  "message": "$(cat /tmp/message.b64)",
  "sig": "MUST_BE_SIGNED",
  "ts": $(date +%s)
}
JSONEOF

# Sign the JSON (using sophia_crypto from the container)
echo '{"message":"'"$(cat /tmp/message.b64)"'","sig":"MUST_BE_SIGNED","ts":'$(date +%s)'}' > /tmp/to_sign.json
sophia_crypto sign /tmp/to_sign.json > /tmp/signature.hex

# Update signal.json with real signature
python3 -c "
import json, sys
with open('/tmp/to_sign.json') as f: d = json.load(f)
with open('/tmp/signature.hex') as f: d['sig'] = f.read().strip()
with open('/tmp/signal.json', 'w') as f: json.dump(d, f, indent=2)
"
```

Then commit and push `dead_drop/signal.json` to the `main` branch.
The probe reads `https://raw.githubusercontent.com/Zheke32174/pleiades/main/dead_drop/signal.json`.

## Commands

| Message (base64 decoded) | Action |
|--------------------------|--------|
| `RESURRECT`              | Re-deploy from GitHub |
| `PURGE\|AUTHORIZED_PURGE` | Self-destruct (requires signal file) |
