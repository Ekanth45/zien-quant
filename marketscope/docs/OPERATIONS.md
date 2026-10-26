# MarketScope Operations & Production Readiness

## Operational Characteristics
- Single-instance bounded threaded Python server (`http.server.ThreadingHTTPServer`).
- In-memory rate limiting: 120 requests/minute per IP.
- Persistent SQLite database in WAL mode with foreign key checks.
- CSRF protection on state-mutating requests (`X-CSRF-Token`).
- Content Security Policy (CSP), Strict-Origin-When-Cross-Origin, nosniff, and frame-busting headers.

## Running Tests
Run the 50-test unit verification suite:
```sh
python -m unittest discover -s marketscope/tests -v
```

## Production Docker Deployment
```sh
cd marketscope/deploy
docker compose up -d --build
```
Caddy handles automated HTTPS TLS termination on ports 80/443.
