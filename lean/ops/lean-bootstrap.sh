#!/bin/bash
set -uo pipefail
ROOT=/workspaces/gentoo/root.x86_64
MIRROR=https://distfiles.gentoo.org/releases/amd64/autobuilds

echo "=== bare-bones Gentoo nspawn substrate ==="
command -v xz >/dev/null || { echo "installing xz-utils..."; DEBIAN_FRONTEND=noninteractive apt-get install -y xz-utils >/dev/null 2>&1; }

if [ -d "$ROOT/usr/bin" ]; then echo "rootfs already present:"; du -sh "$ROOT"; exit 0; fi
mkdir -p "$ROOT"

echo "resolving latest stage3 (systemd)..."
S3=$(curl -fsSL "$MIRROR/latest-stage3-amd64-systemd.txt" | grep -oE '[A-Za-z0-9/_.+-]*stage3-amd64-systemd[A-Za-z0-9/_.+-]*\.tar\.xz' | head -1)
if [ -z "$S3" ]; then echo "FAIL: could not resolve stage3 path"; exit 1; fi
echo "downloading: $S3"
curl -fsSL "$MIRROR/$S3" -o /tmp/stage3.tar.xz || { echo "FAIL: download"; exit 1; }
echo "downloaded: $(du -h /tmp/stage3.tar.xz | cut -f1) — extracting (~1 GB)..."
tar xpf /tmp/stage3.tar.xz --xattrs-include='*.*' --numeric-owner -C "$ROOT" || { echo "FAIL: extract"; exit 1; }
rm -f /tmp/stage3.tar.xz

echo "=== DONE: $(du -sh "$ROOT" | cut -f1) at $ROOT ==="
ls "$ROOT"
