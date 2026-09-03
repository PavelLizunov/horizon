# Linux Production Migration Tasks

Each checked item has lead-observed live evidence; the seven-run soak remains a
post-cutover gate rather than a blocker for the first accepted deployment.

## Provision and runtime

- [x] **REQ-01:** Provision the unprivileged Debian 12 LXC with the approved resources.
- [x] **REQ-01/03:** Install runtime dependencies and check out the exact tested SHA.
- [x] **REQ-02:** Install verified video, digest, tunnel, and timer units.
- [x] **REQ-04:** Stream Mac runtime state and enforce ownership and file modes.

## Boundaries and media

- [x] **REQ-05:** Persistently disable/unload the Mac schedulers and confirm no
      active Horizon process.
- [x] **REQ-06:** Establish and probe the port-restricted loopback search tunnel.
- [x] **REQ-07:** Publish through the restricted identity and verify live HTTP 200.
- [x] **REQ-08:** Set Linux video ASR off.
- [x] **REQ-09:** Scope the approved HTTP proxy to the video service only.
- [x] **REQ-10:** Enable Linux-native narration via `teratts-server` (LXC 221)
      and `faster-whisper` without blocking text publishing if audio fails.

## Acceptance and handoff

- [x] Run the full offline pytest suite, strict MkDocs build, config preflight,
      search probe, and bounded gateway smoke on Linux.
- [x] Run video acceptance and observe successful subtitle extraction with zero ASR.
- [x] Run full digest acceptance and verify AI, indexing, delivery, publication,
      telemetry, and resources. On 2026-09-02 the Linux service exited 0 after
      analyzing 26 items, selecting/publishing/indexing 8, and completing all 62
      observed model requests without errors.
- [x] Enable both persistent timers without triggering a duplicate catch-up run.
      They were enabled at 14:10 MSK on 2026-09-03, before either daily slot;
      systemd reported the intended 16:00 and 17:00 next triggers.
- [x] Commit and push the reviewed deployment templates and documentation.
- [ ] **REQ-11:** Record seven consecutive automated Linux successes before Mac cleanup.
