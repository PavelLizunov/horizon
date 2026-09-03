# Linux Production Guide (`specs/linux-production/`)

This directory owns the production-host contract for the dedicated Debian LXC.
`spec.md` defines requirements, `plan.md` defines the implementation, and
`tasks.md` records only lead-verified status.

## Invariants

- Exactly one Mac/Linux scheduler may be active.
- Production runs an exact tested source revision; generated and gitignored state
  is preserved rather than reset during upgrades.
- `.env`, live config, cookies, private keys, endpoints, and topology identifiers
  never enter tracked files.
- Elasticsearch stays on its separate guest and loopback; access uses the
  restricted tunnel identity.
- Static publishing uses a separate forced-command identity.
- Linux video uses subtitles then configured vision fallback with ASR off.
- Any proxy is operator-approved, untracked, and scoped to the video service.
- Linux narration remains disabled until an independent grader exists.
- The Mac remains a cold rollback for seven successful automated Linux runs.

Update all three SDD documents together when any of these contracts changes.
