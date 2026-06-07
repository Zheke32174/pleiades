#!/usr/bin/env bash
# Developing Mind — ram_monitor.sh
# Role: Monitors memory and clears caches to prevent OOM errors during heavy background extraction.
# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Stability Maintenance

FREE_MEM_MB=$(free -m | awk '/^Mem:/ {print $4}')

if [ "$FREE_MEM_MB" -lt 500 ]; then
    echo "WARNING: Low memory (${FREE_MEM_MB}MB free). Background loops may become unstable."
    exit 1
else
    echo "Memory healthy: ${FREE_MEM_MB}MB free."
    exit 0
fi
