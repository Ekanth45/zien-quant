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
python marketscope/manage.py init-owner
```
Follow the interactive prompt to set:
- Owner email
- Password (salted PBKDF2-HMAC-SHA256 with 600,000 iterations)
- Authenticator TOTP secret (add to Google Authenticator, 1Password, or Authy)

## 3. Database Status & Backups
```sh
# Check database status
python marketscope/manage.py status

# Create an ACID-compliant SQLite online backup
python marketscope/manage.py backup
```

## 4. Connecting Live Zerodha Kite Feed (Optional)
1. Install live dependencies:
   ```sh
   pip install -r marketscope/requirements-live.txt
   ```
2. Configure credentials in `.env`:
   ```env
   KITE_API_KEY=your_api_key
   KITE_ACCESS_TOKEN=your_access_token
   ```
3. Restart server and log in as owner.
