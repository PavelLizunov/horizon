# Search Deployment Agent Guide (`deploy/search/`)

Local rules and architectural constraints for the Elasticsearch digest search service. Parent rules in root `AGENTS.md` and `deploy/AGENTS.md` apply.

## Local Scope & Architecture

The `deploy/search/` directory contains:
- `docker-compose.yml`: Defines single-node Elasticsearch 8.15.3 (`es`) and read-only Python shaping proxy (`search-api`).
- `search_api.py`: Minimal standard-library Python HTTP server bridging browser queries to Elasticsearch.
- `README.md`: System topology, Caddy proxy instructions, and administrative procedures.

## Security Boundary & Network Topology

- **Elasticsearch Localhost Binding**: Elasticsearch port `9200` is bound strictly to localhost (`127.0.0.1:9200:9200`). Disabling security (`xpack.security.enabled=false`) is permissible **only** because Elasticsearch is unreachable from external networks or LAN interface.
- **Pipeline Ingestion**: Pipeline orchestrator indexes articles directly over `http://127.0.0.1:9200`.
- **Public & LAN Gateway**: `search-api` listens on port `8788` (`0.0.0.0:8788`). Caddy ingress reverse-proxies `/api/search*` to `<MAC_LAN_IP>:8788`.
- **Endpoint Isolation**: Only `GET /search` and `GET /api/search` are proxied (max query length 200 chars). Unknown GET paths return 404; unsupported HTTP methods inherit `BaseHTTPRequestHandler`'s 501 response and cannot reach Elasticsearch.

## Graceful Failure Boundaries

- **Pipeline Ingestion Boundary**: If Elasticsearch is offline or unreachable during a run (`search.enabled: true`), the pipeline logs a warning and degrades gracefully without interrupting digest generation or site publishing.
- **Search API Boundary**: If Elasticsearch queries fail or time out (10s limit), `search_api.py` catches `URLError`, `OSError`, and `ValueError`, then returns HTTP 502 with `{"total": 0, "hits": [], "error": "..."}`. The raw exception string and five-minute cache header on that error response are current audit findings, not contracts to preserve.
- **Ingress Boundary**: If Docker Desktop is stopped or LAN IP shifts, `/api/search` returns HTTP 502, but static site pages continue serving unaffected.

## Portability & Configuration Constraints

- **JVM Heap Limit**: Elasticsearch JVM heap is explicitly pinned via `ES_JAVA_OPTS=-Xms512m -Xmx512m` to prevent excess host memory consumption.
- **Environment Interop**: Service host resolution relies on Docker DNS (`http://es:9200`). Do not hardcode host IPs inside `docker-compose.yml` or `search_api.py`.
- **Highlight Sentinels**: `search_api.py` uses unicode sentinels (`\u0001` / `\u0002`) and `balance_highlights()` to safely format Russian morphological search highlights without HTML tag corruption.

## Verification Commands

- Validate Python API script syntax: `python3 -m py_compile deploy/search/search_api.py`
- Validate Docker Compose configuration: `docker compose -f deploy/search/docker-compose.yml config`
- Verify git diff for whitespace or trailing formatting errors: `git diff --check -- deploy/AGENTS.md deploy/search/AGENTS.md`
