# Zien Quant frontend 0.2.0

Released 26 October 2026.

The new homepage adopts the layout and visual language from `finance reff/outputs/marketscope/static/`: a persistent workspace sidebar, compact top bar, market overview, stock scanner, watchlist, owner console, stock inspection, and Laya drawer. It keeps the Zien Quant identity and connects those views to the current repository's backend.

## Open the workspace

Start the server from the repository root:

```powershell
python server.py --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. No frontend bundler or additional runtime dependencies are needed.

| URL | Interface |
| --- | --- |
| `/` or `/index.html` | New reference-inspired workspace |
| `/flow` or `/flow.html` | Existing Flow River terminal |
| `/matrix` or `/terminal` | Existing flow matrix |
| `/console` or `/orderblock` | Existing order block console |
| `/bloomberg` or `/terminal-bloomberg` | Existing Bloomberg-style terminal |
| `/mobile` | Existing mobile terminal |
| `/static/index.html` | Previous homepage |

## Assets and data

The new frontend uses `marketscope/static/workspace.html`, `workspace.css`, `workspace.js`, and `workspace-api.js`. The API adapter maps the existing market, stock, session, catalogue, authentication, and analysis responses to the workspace. Existing API routes and data processing stay in place.

The reference folder also contains an older application's demo and provider modes. Version 0.2.0 uses its frontend design with the current repository's real-data service. Auto session and previous session controls use received exchange observations or persisted real candles. Missing prices, invalid candles, and unavailable feeds remain unavailable; the workspace does not fabricate candles or replace a failed real feed with the reference application's generated replay.

The interface exposes owner actions through the existing authentication and authorization endpoints. Running the new frontend does not create an owner account or change the server's security configuration. Follow the existing installation guide to initialize the owner account.

## Verification

`marketscope/tests/test_workspace_routes.py` checks the new homepage aliases, preserved terminal routes, and static assets over local HTTP without initializing a feed, candle archive, or database. It also covers deterministic unknown-symbol analysis validation, valid-symbol feed failures, and tracked-symbol handling with stubbed services.
