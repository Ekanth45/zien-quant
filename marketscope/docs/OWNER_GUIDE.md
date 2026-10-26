# MarketScope Owner & Operator Guide

## 1. Quick Start
To launch the server locally:
```sh
python server.py --host 127.0.0.1 --port 8765
```
Open `http://127.0.0.1:8765` in your browser.

## 2. Initializing the Owner Account
The application supports a single protected owner account with mandatory TOTP two-factor authentication:
```sh
python manage.py init-owner
```
Follow the interactive prompt to set:
- Owner email
- Password (salted PBKDF2-HMAC-SHA256 with 600,000 iterations)
- Authenticator TOTP secret (add to Google Authenticator, 1Password, or Authy)

## 3. Database Status & Backups
```sh
# Check database status
python manage.py status

# Create an ACID-compliant SQLite online backup
python manage.py backup
```

## 4. Upstream Market Data Source
By default, Zien Quant uses Yahoo Finance delayed chart candles with built-in SQLite caching and previous session replay. Zero external pip packages are needed for default operation. (Zerodha Kite Connect is a future integration placeholder; leave `KITE_*` empty in `.env`).
