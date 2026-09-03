# Linux Production Migration Plan

## Runtime layout

```text
Debian LXC
├── /opt/horizon/                  exact tested Git checkout + gitignored state
├── /var/lib/horizon/              service home, SSH identities, logs
├── /var/cache/horizon/uv/         bounded installation cache; no ML model cache
├── horizon-video.timer/service    subtitles -> configured vision fallback
├── horizon-digest.timer/service   run-daily.sh -> index -> build -> publish
└── horizon-search-tunnel.service  local :9200 -> loopback search guest
```

The unprivileged `horizon` account owns the checkout and service home. Systemd
sets `HOME`, an explicit `PATH`, `UMask=0022`, timeouts, CPU/memory limits,
`NoNewPrivileges`, `PrivateTmp`, and writable-path boundaries. The two one-shot
services use `/run/lock/horizon-production.lock`; digest waits for the video lock
while video refuses a concurrent run.

## Provisioning

1. Create an unprivileged Debian 12 LXC with the approved resource envelope.
2. Install only core runtime packages; install `uv` in an isolated bootstrap venv.
3. Clone `origin/main`, verify the expected SHA, and run `uv sync --frozen`.
4. Install MkDocs Material as an isolated `uv tool`, not a project dependency.
5. Copy runtime state from the stopped Mac source over an SSH tar stream, then
   restore ownership and secret/public file modes.
6. Change only Linux-specific live config: video ASR off and search URL to local
   loopback. Do not copy these overrides back during rollback.

## Network boundaries

- A dedicated outbound key maintains a local forward to the separate,
  loopback-only Elasticsearch service. Its destination account permits only
  forwarding to that port.
- A second key reaches the ingress publisher account. The forced command accepts
  a gzip tar stream, rejects absolute/traversal/link/device members, requires a
  non-empty site index, and writes only the static document root.
- Direct and proxy egress are measured separately. An optional mode-0600
  `video-egress.env` is loaded only by `horizon-video.service`; internal paths
  are never sent through it.

## Scheduling and cutover

1. Persistently disable and unload the Mac Horizon scheduler labels, then prove
   there is no Horizon cron job or active pipeline process.
2. Perform the final state copy and reapply Linux-only config.
3. Pass offline pytest, strict MkDocs build, config validation, search-tunnel
   HTTP check, and one bounded model-gateway smoke.
4. Run the video service manually and require a successful extraction summary
   with zero ASR on Linux.
5. Run the digest service manually and verify collection, AI work, search index,
   webhook delivery, site publish, process exit, and live HTTP responses.
6. Seed persistent timer timestamps before first start when today's scheduled
   slots have already passed, preventing an immediate duplicate catch-up run.
7. Enable both timers only after manual acceptance.

## Rollback

Disable both Linux timers first. Stop any active Linux one-shot, copy only newer
runtime state back to the preserved Mac checkout, retain the Mac-specific
`asr: "local"` setting, and run manually or restore launchd. Never run both
schedulers. The Linux guest remains intact for diagnosis.

## Verification

- Full offline pytest and strict MkDocs build pass on the guest.
- `systemd-analyze verify` accepts all units; tunnel and timers survive reboot.
- Restricted publisher produces HTTP 200 pages readable by the web service.
- Video summary proves subtitles/vision operation with ASR zero.
- Gateway telemetry shows the target model and no request errors for acceptance.
- Guest memory/disk remain below the configured service and filesystem limits.
