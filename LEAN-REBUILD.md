# Lean rebuild (2026-06)

The original eight-script suite half-worked: shipped systemd units pointed at binaries
the scripts never built (so they crash-looped), failures were masked wholesale (`|| true`),
agents wrote all over the host, and a few carried offensive code. See the analysis in
[`lean/docs/`](lean/docs/).

A clean, from-scratch reimplementation now lives in **[`lean/`](lean/)** — built one agent at
a time, each verified for real. Its hard invariants:

1. One canonical binary + one unit per agent; `build.sh` refuses a unit whose `ExecStart`
   binary is missing. No runtime `curl|sh`, no self-installed units.
2. No error masking — failures are logged and surface in an honest status.
3. systemd owns supervision (`Restart=on-failure` + `StartLimitBurst`); **no in-process
   `while true` loops** — periodic work is a slow, jittered `.timer`.
4. Agents stay in the container — the read-only host boundary is enforced by the sandbox.
5. The Nexus is a hash-chained, Ed25519-signed, append-only ledger; never self-vacuumed.

The always-on Windows side (AD/Security sensors, self-heal supervisor, Command Deck) lives in
the companion repo: [`pleiades-windows`](https://github.com/Zheke32174/pleiades-windows).

The previous scripts remain in place untouched — this is an additive update.
