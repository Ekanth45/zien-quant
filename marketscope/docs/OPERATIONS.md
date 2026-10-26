# MarketScope Operations & Production Readiness

## Operational Characteristics
- Single-instance bounded threaded Python server (`http.server.ThreadingHTTPServer`).
- In-memory rate limiting: 120 requests/minute per IP.
- Persistent SQLite database in WAL mode with foreign key checks.
- CSRF protection on state-mutating requests (`X-CSRF-Token`).
- Content Security Policy (CSP), Strict-Origin-When-Cross-Origin, nosniff, and frame-busting headers.

## Running Tests
Run the comprehensive automated test suite (139 tests across root and marketscope suites):
```sh
python -m unittest discover -s tests -v
```

## Production Docker Deployment
```sh
cd marketscope/deploy
docker compose up -d --build
```
Caddy handles automated HTTPS TLS termination on ports 80/443 (ensure your domain and email are updated in `Caddyfile`). Note: Docker deployment is provided as a reference configuration and should be tested locally in environments with Docker installed.
