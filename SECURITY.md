# Security Policy

## Scope

Pleiades is intended for authorized defensive research, local lab testing, decoy-service telemetry, and owner-authorized system administration.

**Do not use this project on systems you do not own or administer without explicit permission.**

## Reporting Security Issues

Please report security issues privately through [GitHub Security Advisories](https://github.com/Zheke32174/pleiades/security/advisories).

Do not open public issues containing:
- real credentials or tokens
- private logs or evidence archives
- working exploit chains
- third-party host details
- personal identifying information

## Secret Handling

Never commit:
- `.env` files or environment variable files
- API keys (OpenAI, Anthropic, cloud provider)
- OAuth tokens or GitHub PATs
- SSH private keys
- Certificates or signing keys
- Private evidence archives or forensic bundles

## Defensive-Use Boundary

This project does not authorize:
- Stealth deployment on systems without explicit owner consent
- Credential theft or unauthorized access
- Lateral movement between systems
- Unauthorized reconnaissance
- Anti-forensic log wiping to conceal unauthorized activity
- Evasion of a system owner or administrator

## Dependency Security

Third-party tools in `pleiades-factory-stack` are cloned from their upstream repositories at install time. Review each tool's own security posture before use in sensitive environments.
