#!/bin/bash
source "${PLEIADES_TERMUX_LIB:-}" 2>/dev/null || true
# Launch the pleiades-team QEMU test VM.
# Serial console only (nographic). Ctrl+A X to exit QEMU.
set -euo pipefail

# Termux: QEMU VM runner (requires x86_64 host)
[[ "${PLEIADES_ENV:-}" == "termux" ]] && echo "[run-vm] Termux: QEMU VM requires x86_64 host, skipping" && exit 0

PLEIADES_ROOT="${PLEIADES_ROOT:-${HOME}/pleiades}"
QCOW_IMG="${PLEIADES_ROOT}/pleiades-test.qcow2"
VMLINUZ=$(ls /boot/vmlinuz-* 2>/dev/null | sort -V | tail -1)
INITRD=$(ls /boot/initrd.img-* 2>/dev/null | sort -V | tail -1)

[[ ! -f "$QCOW_IMG" ]] && { echo "ERROR: No image. Run: sudo bash ${PLEIADES_ROOT}/build-pleiades-vm.sh"; exit 1; }
[[ -z "$VMLINUZ" ]] && { echo "ERROR: No kernel in /boot"; exit 1; }

echo "[*] Booting $QCOW_IMG"
echo "[*] Kernel: $VMLINUZ"
echo "[*] To exit: Ctrl+A then X"
echo ""

exec qemu-system-x86_64 \
  -m 2048 -smp 2 \
  -kernel "$VMLINUZ" \
  -initrd "$INITRD" \
  -append "root=/dev/vda rw console=ttyS0 quiet systemd.log_level=err" \
  -drive file="$QCOW_IMG",format=qcow2,if=virtio \
  -net nic -net user,hostfwd=tcp::2222-:22 \
  -nographic
