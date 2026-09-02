# Search Deployment Agent Guide (`deploy/search/`)

Local rules for the Elasticsearch archive-search artifact and its reference
Compose topology. Parent rules in root `AGENTS.md` and `deploy/AGENTS.md` apply.

## Local scope and deployment modes

- `search_api.py`: dependency-free read-only HTTP proxy and the artifact copied
  into the current production search host.
- `docker-compose.yml`: supported local/reference stack; it is not the current
  production topology.
- `README.md`: public contract, systemd production topology, Compose reference,
  indexing path, ingress, and verification procedures.

Production runs on a dedicated Debian/Linux guest, separate from the macOS
pipeline host:

- `horizon-elasticsearch.service`: Elasticsearch 8.15.3 with HTTP/transport
  ports bound to loopback (`9200`/`9300`).
- `horizon-search-api.service`: Python 3.11 running the committed artifact at
  `/opt/horizon/search/search_api.py`, binding `0.0.0.0:8788` behind ingress.
  Its unit must set `ES_URL=http://127.0.0.1:9200`; the code default
  `http://es:9200` belongs to Compose DNS.
- The API unit uses `DynamicUser=yes`, restart-on-failure,
  `NoNewPrivileges=yes`, strict systemd sandboxing, and `MemoryMax=128M`.
- The pipeline reaches Elasticsearch through an operator-managed local SSH
  forward; never make port `9200` LAN-facing as a shortcut.

Do not add real hostnames, IP addresses, LXC/VM identifiers, usernames, or SSH
aliases to tracked files. Unit files and tunnel definitions remain
operator-managed infrastructure unless explicitly added through a separate
approved change.

## Public API and security invariants

- Only `GET /search` and `GET /api/search` reach Elasticsearch. Query text is
  normalized and capped at 200 characters; result size remains 30.
- Successful responses preserve the existing `{total, hits}` envelope and use
  `Cache-Control: public, max-age=300`.
- Backend failures return sanitized HTTP 502 payloads with
  `error_code: "backend_unavailable"`; raw exceptions stay server-side.
- Every non-2xx response uses `Cache-Control: no-store`.
- `SearchHTTPServer` acquires a bounded semaphore before starting a handler.
  `SEARCH_MAX_CONCURRENCY` defaults to 8 and `SEARCH_REQUEST_TIMEOUT` defaults
  to 15 seconds for client inactivity and Elasticsearch requests.
- Keep Elasticsearch unauthenticated only while both Elasticsearch ports remain
  loopback-only. The LAN-facing API is read-only but still benefits from
  ingress rate limiting.

## Failure and deployment boundaries

- Search indexing failure warns and degrades without aborting digest publishing.
- Search/API failure does not affect static site availability.
- Deploy the exact committed `search_api.py`, syntax-check the candidate, retain
  the previous artifact, atomically replace it, and restart only
  `horizon-search-api.service`. Do not restart Elasticsearch for proxy-only
  changes and never run the paid pipeline as a deployment check.
- Compose uses Docker DNS (`http://es:9200`) and a 512 MB Elasticsearch JVM heap;
  production systemd uses loopback and manages resources independently.
- Preserve highlight sentinels (`\u0001` / `\u0002`) and per-fragment balancing;
  they prevent indexed content from injecting HTML while retaining highlights.

## Verification commands

```bash
.venv/bin/pytest tests/test_search_api.py -q
python3 -m py_compile deploy/search/search_api.py
docker compose -f deploy/search/docker-compose.yml config  # reference stack only
```

On the production search host, verify both services are active, the deployed
artifact hash matches the committed file, local aliases return the successful
contract, and the public `/api/search` path preserves cache/error headers.
