# Archive search (Elasticsearch)

The site's search page queries `/api/search?q=…` on the digest domain. Caddy
proxies that path to a tiny read-only API, which is the only client of
Elasticsearch. The browser can never reach index administration.

```
browser ── /api/search ── Caddy (LXC 210) ── search-api (:8788, Mac LAN IP)
                                                    │
pipeline (Mac) ── 127.0.0.1:9200 ── Elasticsearch ──┘  (same compose network)
```

## Topology

- Host: the Mac mini that already runs the pipeline (Docker Desktop, 16 GB).
  Elasticsearch is bound to `127.0.0.1:9200` only; the pipeline indexes over
  localhost.
- `search-api` (stdlib Python in `python:3.12-slim`) is the one LAN-facing
  port (`8788`). It serves exactly `/search` and `/api/search`; everything
  else 404s.
- Caddy on the ingress adds to `conf.d/digest.ninitux.com.caddy`:

  ```
  handle /api/search* {
      reverse_proxy <MAC_LAN_IP>:8788
  }
  handle {
      root * /srv/digest.ninitux.com
      file_server
  }
  ```

  Validate before reload: `caddy validate --config /etc/caddy/Caddyfile
  --adapter caddyfile`, then `systemctl reload caddy`, then curl the
  neighbours to prove nothing broke.

  **Pin `<MAC_LAN_IP>` with a DHCP reservation.** It is written into the proxy
  by hand, so a lease change silently breaks search and nothing reports it:
  the site keeps serving, the search page keeps loading, and only
  `/api/search` answers 502. This has happened once — a reboot moved the Mac
  by one address while the proxy kept pointing at the old one.

Two failure modes worth knowing, both from the same reboot:

- **Docker Desktop does not start at login by default.** Nothing brings
  `es`/`search-api` back after a restart until someone opens it. Enable
  "Start Docker Desktop when you sign in" in its settings.
- The pipeline degrades rather than fails when the backend is unreachable, by
  design — so a dead index costs nothing at run time and stays invisible.
  `curl -s -o /dev/null -w '%{http_code}' https://<digest-domain>/api/search?q=test`
  is the one-line check; anything but 200 means the chain is broken.

## Run

```bash
cd deploy/search && docker compose up -d     # first start (~300 MB pull)
docker compose ps                            # es healthy + search-api up
```

Heap is pinned to 512 MB (`ES_JAVA_OPTS`); the archive is a few hundred small
documents. Measured footprint: report after the first real deployment in the
CHANGELOG, not before.

## Indexing

- Live runs index themselves: `search.enabled: true` in `data/config.json`
  makes the orchestrator upsert that run's articles after the site publish.
  A dead backend degrades the run (warning), never fails it.
- Backfill the history once:

  ```bash
  uv run python scripts/dev_reindex_archive.py --dry-run   # look first
  uv run python scripts/dev_reindex_archive.py
  ```

  Document ids are the issue-scoped page slugs, so reindexing is idempotent.

## Access control

- Elasticsearch: localhost-only port, security off is acceptable because
  nothing outside the Mac can reach it.
- search-api: read-only by construction (one GET endpoint, no ES admin
  passthrough), LAN-facing on a trusted home network.
- Public: only what Caddy proxies (`/api/search*`), which is search-api's
  single endpoint.
