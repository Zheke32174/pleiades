# Zheke32174 External Repos — Integration Log

Generated: 2026-06-01

## Repos Evaluated

| Repo | Purpose | Decision |
|------|---------|----------|
| alien | Fork of alien-bsd with upstream patches | Merge improvements → local alien-bsd |
| scandroid | Android app static analysis (bytecode scanning) | Stage as pleiades-team capability: domain=re |
| Tracendroid | Android execution trace analysis | Stage as pleiades-team capability: domain=forensics |
| underlode | Binary unpacker/loader utility | Stage as pleiades-team capability: domain=re |

## Merge Status: alien fork

- Cloned to: `/workspaces/gentoo/external/zheke32174/alien`
- Diff target: `/workspaces/gentoo/alien-bsd`
- Status: **pending clone** — run `install-zheke32174.sh` to fetch and diff
- Conflicts: none yet (not cloned)

## Integration Specs

### scandroid
- **Purpose**: Static analysis of Android APK bytecode for security issues
- **Integration**: Register as `pleiadesctl re android-scan <apk>`
- **Capability**: `domain=reverse_engineering, authority=policy-gated`
- **Install**: `pip install scandroid` or clone to `/workspaces/gentoo/tools/scandroid`

### Tracendroid
- **Purpose**: Dynamic execution trace analysis for Android binaries
- **Integration**: Register as `pleiadesctl forensics trace-android <trace>`
- **Capability**: `domain=forensics, authority=policy-gated`
- **Install**: Clone to `/workspaces/gentoo/tools/Tracendroid`

### underlode
- **Purpose**: Binary unpacking and loader emulation
- **Integration**: Register as `pleiadesctl re unpack <binary>`
- **Capability**: `domain=reverse_engineering, authority=policy-gated`
- **Install**: Clone to `/workspaces/gentoo/tools/underlode`
