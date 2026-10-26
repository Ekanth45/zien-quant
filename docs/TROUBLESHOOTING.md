# Zien Quant - Troubleshooting & Operational Runbook

This runbook catalogs common symptoms, root causes, diagnostic procedures, and resolutions.

---

## 1. Quick Troubleshooting Matrix

| Symptom | Probable Cause | Diagnostic Command | Remediation |
|:---|:---|:---|:---|
| **Port 8765 in use (`OSError: [Errno 98] Address already in use`)** | Another instance of Zien Quant or dev server is running. | `netstat -ano \| findstr 8765` (Win) or `lsof -i :8765` (Linux) | Terminate conflicting PID or change port: `python server.py --port 8766`. |
| **Scraper returns HTTP 429 / Circuit Breaker tripped** | Upstream rate limiting due to aggressive polling. | `python manage.py doctor` | The terminal automatically backs off and engages the circuit breaker for 60s. Wait for cooldown or switch to Previous Session replay. |
| **Ollama connection refused (`Failed to connect to 127.0.0.1:11434`)** | Ollama daemon is not started. | `curl http://127.0.0.1:11434/api/tags` | Start daemon via `ollama serve`. Terminal operates normally with rules engine fallback in the interim. |
| **Ollama model missing (`gemma4:12b not found`)** | Model weights have not been downloaded. | `ollama list` | Run: `ollama pull gemma4:12b`. |
| **Owner account lockout / Forgotten password** | Lost credentials or missing TOTP secret. | `python manage.py status` | Reset owner password or credentials via CLI: `python manage.py init-owner` or update through DB manager. |
| **Database migration mismatch / SQLite schema error** | Database tables uninitialized or old schema. | `python manage.py doctor` | Backup DB (`python manage.py backup`), then re-run automated migrations by executing setup script. |
| **Stock search returns 0 results** | Stock master database has not been populated. | `python manage.py doctor` | Run: `python manage.py import-stock-master` to download official NSE equity master or seed top-100 universe. |
| **Candles show 'Market Closed' on weekday** | NSE official trading holiday or market timing. | Check `/api/market/schedule` | Check NSE holiday schedule. Terminal automatically activates Previous Session replay view. |

---

## 2. In-Depth Diagnostics

### 2.1 Running System Doctor
Run the built-in diagnostic suite from the repository root:
```bash
python manage.py doctor
```
The tool validates Python version, disk capacity, database file integrity, migration levels, owner account presence, Ollama reachability, model readiness, and upstream feed connectivity.

### 2.2 Database Recovery
If SQLite database files encounter lock contention or corruption:
1. Verify no orphaned processes hold file handles:
   ```bash
   # On Windows
   Get-Process python*
   ```
2. Check SQLite WAL files (`*.db-wal`, `*.db-shm`). If server is stopped cleanly, WAL files automatically checkpoint and clean up.
3. To recover from a backup:
   ```bash
   cp work/backups/marketscope_backup_<timestamp>.db work/runtime/marketscope.db
   ```

### 2.3 Resetting Owner Account Credentials
To reset MFA or assign a new owner password when locked out:
```bash
python manage.py init-owner --email "owner@example.com" --password "NewSecurePassword123!"
```
*(If an owner already exists, verify via `python manage.py status` or remove the existing owner record).*
