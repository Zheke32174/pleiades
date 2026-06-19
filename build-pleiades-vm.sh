#!/bin/bash
source "${PLEIADES_TERMUX_LIB:-}" 2>/dev/null || true
# Builds a bootable QEMU image from the existing Gentoo nspawn root.
# Run as root or with sudo. Takes ~5-10 min (rsync of ~5.7GB).
set -euo pipefail

cleanup() {
    if mountpoint -q "$MOUNT"; then
        echo "[*] Cleaning up: unmounting $MOUNT"
        umount -l "$MOUNT" || true
    fi
}
trap cleanup EXIT


# Termux: QEMU VM builder (requires x86_64 host kernel)
[[ "${PLEIADES_ENV:-}" == "termux" ]] && echo "[build-vm] Termux: QEMU VM builder requires x86_64 host, skipping" && exit 0

PLEIADES_ROOT="${PLEIADES_ROOT:-${HOME}/pleiades}"
NSPAWN_ROOT="${PLEIADES_ROOT}/rootfs"
RAW_IMG="${PLEIADES_ROOT}/pleiades-test.raw"
QCOW_IMG="${PLEIADES_ROOT}/pleiades-test.qcow2"
MOUNT="/tmp/pleiades-qemu-mount"
SIZE="22G"

VMLINUZ=$(ls /boot/vmlinuz-* 2>/dev/null | sort -V | tail -1)
INITRD=$(ls /boot/initrd.img-* 2>/dev/null | sort -V | tail -1)

[[ -z "$VMLINUZ" ]] && { echo "ERROR: No kernel found in /boot. Run: sudo apt-get install linux-image-generic"; exit 1; }
echo "[*] Kernel : $VMLINUZ"
echo "[*] Initrd : $INITRD"

# Create sparse raw image
echo "[*] Creating ${SIZE} raw image..."
fallocate -l "$SIZE" "$RAW_IMG" 2>/dev/null || dd if=/dev/zero bs=1M count=0 seek=22528 of="$RAW_IMG"
mkfs.ext4 -F -L pleiades-root "$RAW_IMG"

# Mount and populate
mkdir -p "$MOUNT"
mount -o loop "$RAW_IMG" "$MOUNT"

echo "[*] Rsyncing nspawn root (this takes a few minutes)..."
rsync -a --info=progress2 \
  --exclude="/proc/*" \
  --exclude="/sys/*" \
  --exclude="/dev/*" \
  --exclude="/run/*" \
  --exclude="/tmp/*" \
  --exclude="/var/db/repos/gentoo/*" \
  --exclude="/usr/share/doc/*" \
  --exclude="/usr/share/man/*" \
  --exclude="/var/cache/distfiles/*" \
  --exclude="/var/cache/binpkgs/*" \
  --exclude=".git" --exclude="*.bak.*" --exclude="*.old" \
  "$NSPAWN_ROOT/" "$MOUNT/"

# Ensure stub dirs
mkdir -p "$MOUNT"/{proc,sys,dev,run,tmp}
chmod 1777 "$MOUNT/tmp"

# fstab
cat > "$MOUNT/etc/fstab" << 'EOF'
/dev/vda  /       ext4   defaults,noatime  0 1
tmpfs     /tmp    tmpfs  defaults          0 0
proc      /proc   proc   defaults          0 0
sysfs     /sys    sysfs  defaults          0 0
devtmpfs  /dev    devtmpfs defaults        0 0
EOF

# Serial console for nographic mode
mkdir -p "$MOUNT/etc/systemd/system/getty@ttyS0.service.d"
cat > "$MOUNT/etc/systemd/system/getty@ttyS0.service.d/override.conf" << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF
ln -sf /lib/systemd/system/getty@.service \
  "$MOUNT/etc/systemd/system/getty.target.wants/getty@ttyS0.service" 2>/dev/null || true

# Bind scripts directory at /pleiades-scripts in the VM
cp -r "$NSPAWN_ROOT/../scripts" "$MOUNT/pleiades-scripts" 2>/dev/null || \
  cp -r "${NSPAWN_ROOT}/scripts" "$MOUNT/pleiades-scripts"

# Make sure root can log in without password
sed -i 's/^root:[^:]*:/root::/' "$MOUNT/etc/shadow" 2>/dev/null || true

umount "$MOUNT"

echo "[*] Converting raw → qcow2..."
qemu-img convert -f raw -O qcow2 -c "$RAW_IMG" "$QCOW_IMG"
rm -f "$RAW_IMG"

echo ""
echo "===== VM IMAGE READY ====="
echo "Image : $QCOW_IMG"
du -sh "$QCOW_IMG"
echo ""
echo "Boot command:"
cat << BOOTEOF
qemu-system-x86_64 \\
  -m 2048 -smp 2 \\
  -kernel $VMLINUZ \\
  -initrd $INITRD \\
  -append "root=/dev/vda rw console=ttyS0 quiet systemd.log_level=err" \\
  -drive file=$QCOW_IMG,format=qcow2,if=virtio \\
  -net nic -net user,hostfwd=tcp::2222-:22 \\
  -nographic
BOOTEOF
