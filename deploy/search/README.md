# Archive search (Elasticsearch)

The site's search page queries `/api/search?q=…` on the digest domain. The
public reverse proxy forwards only that read-only operation to `search-api`;
the browser never reaches Elasticsearch administration.

```text
browser ── /api/search ── ingress ── search-api (:8788)
                                             │
pipeline (macOS) ── local SSH forward ── Elasticsearch (loopback :9200)
```

## Current production topology

Production separates the scheduled macOS pipeline from archive search:

- A dedicated Debian/Linux guest runs Elasticsearch 8.15.3 and the stdlib
  Python 3.11 proxy as native systemd services:
  `horizon-elasticsearch.service` and `horizon-search-api.service`.
- Elasticsearch HTTP (`9200`) and transport (`9300`) bind to loopback on the
  search host. The macOS pipeline reaches the HTTP port through a persistent
  local SSH forward and points `search.url` at that deployment-specific local
  endpoint.
- `search-api` binds `0.0.0.0:8788` behind ingress and serves only
  `GET /search` and `GET /api/search`; unknown GET paths return 404.
- The committed API artifact is deployed as
  `/opt/horizon/search/search_api.py`. Its systemd unit uses `DynamicUser=yes`,
  `Restart=on-failure`, `NoNewPrivileges=yes`, a strict filesystem/kernel
  sandbox, and `MemoryMax=128M`.
- The systemd unit files and SSH-forward LaunchAgent are operator-managed
  infrastructure; this repository ships the API artifact and a reference
  Compose topology, not those host-specific definitions.

On the search host, safe status checks are:

```bash
systemctl status horizon-elasticsearch.service horizon-search-api.service
journalctl -u horizon-search-api.service --since today
curl -fsS 'http://127.0.0.1:8788/api/search?q=test'
```

Deploy the exact committed `deploy/search/search_api.py`, compile it before the
swap, retain the previous artifact for rollback, and restart only
`horizon-search-api.service`. A proxy-only update does not require restarting
Elasticsearch or running the paid Horizon pipeline.

## Reference Docker Compose topology

`docker-compose.yml` remains a supported local/reference deployment where
Elasticsearch and `search-api` share one Compose network. It is not the current
production topology.

```bash
cd deploy/search
docker compose up -d
docker compose ps
```

The reference stack pins the Elasticsearch JVM heap to 512 MB and uses
`python:3.12-slim` for the proxy. These Compose choices are independent of the
Python 3.11 systemd production host.

`search_api.py` defaults `ES_URL` to the Compose service name
`http://es:9200`. A standalone/systemd unit must override it with
`ES_URL=http://127.0.0.1:9200`; otherwise Docker DNS is unavailable.

## Proxy resource controls

| Variable | Default | Effect |
|---|---:|---|
| `SEARCH_MAX_CONCURRENCY` | `8` | Maximum active request-handler threads; saturation back-pressures new connections through the finite listen backlog. |
| `SEARCH_REQUEST_TIMEOUT` | `15` | Client socket inactivity timeout and Elasticsearch request timeout, in seconds. |

Values must be positive; invalid values fail startup rather than silently
disabling the guard. Production currently uses these code defaults unless its
unit explicitly overrides them.

## HTTP contract

- `GET /search?q=…` and `GET /api/search?q=…` are aliases. Query whitespace is
  normalized, input is capped at 200 characters, and fewer than two characters
  returns an empty HTTP 200 response without querying Elasticsearch.
- Successful responses retain `{"total": <int>, "hits": [...]}` and
  `Cache-Control: public, max-age=300`.
- Backend failures return HTTP 502 with
  `{"total": 0, "hits": [], "error": "Search backend unavailable", "error_code": "backend_unavailable"}`
  and `Cache-Control: no-store`. Internal exception text stays in server logs.
- Unknown GET paths remain 404; unsupported methods remain 501. Every non-2xx
  response carries `Cache-Control: no-store`.

The offline contract/resource suite is:

```bash
.venv/bin/pytest tests/test_search_api.py -q
python3 -m py_compile deploy/search/search_api.py
```

## Indexing

- With `search.enabled: true`, each language pass upserts its rendered articles
  after writing local site pages. A dead backend logs a warning and does not fail
  digest generation or delivery.
- In the separated production topology, keep Elasticsearch loopback-only and
  set `search.url` to the pipeline host's local SSH-forward endpoint. Do not
  expose port `9200` to the LAN merely to simplify ingestion.
- Backfill historical summaries only after a dry run:

  ```bash
  uv run python scripts/dev_reindex_archive.py --dry-run
  uv run python scripts/dev_reindex_archive.py
  ```

  Document IDs are issue-scoped page slugs, so reindexing is idempotent.

Issue indexing stores the resolved classification profile and replaces the exact
date/language slice: current documents are bulk-indexed first, then stale IDs in
that same issue are deleted. Partial bulk failures abort cleanup, and failures
remain non-fatal to digest publishing.

## Ingress

The public proxy needs only the read-only API route plus the static site:

```caddyfile
handle /api/search* {
    reverse_proxy <search-host>:8788
}
handle {
    root * /srv/<digest-domain>
    file_server
}
```

Keep the search host address stable through the local network's normal address
management. Validate the complete Caddy configuration before reload, then test
the API and neighbouring virtual hosts.

`/api/search*` must be excluded from static-site cache rules so successful
results retain the service's five-minute cache while 4xx/5xx responses remain
`no-store`.

## Access and failure boundaries

- Elasticsearch is unauthenticated only because both of its ports are
  loopback-only on the search host.
- `search-api` is unauthenticated and LAN-facing, but it exposes no index
  administration, bounds concurrency, and times out idle/backend operations.
  Ingress rate limiting remains useful defense in depth.
- If either systemd service or the SSH forwarding path is unavailable, static
  pages continue serving; search and/or indexing degrade independently.
- A public health check should query
  `https://<digest-domain>/api/search?q=test` and require HTTP 200 without
  printing result content or internal error details.
