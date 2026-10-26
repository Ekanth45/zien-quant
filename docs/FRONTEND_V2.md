# Zien Quant frontend 2.0.0

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

The reference folder also contains an older application's demo and provider modes. Version 2.0.0 uses its frontend design with the current repository's real-data service. Auto session and previous session controls use received exchange observations or persisted real candles. Missing prices, invalid candles, and unavailable feeds remain unavailable; the workspace does not fabricate candles or replace a failed real feed with the reference application's generated replay.

The interface exposes owner actions through the existing authentication and authorization endpoints. Running the new frontend does not create an owner account or change the server's security configuration. Follow the existing installation guide to initialize the owner account.

## Verification

`marketscope/tests/test_workspace_routes.py` checks the new homepage aliases, preserved terminal routes, and static assets over local HTTP without initializing a feed, candle archive, or database. It also covers deterministic unknown-symbol analysis validation, valid-symbol feed failures, and tracked-symbol handling with stubbed services.

### Frontend development checks

Node.js 22 or newer is only required for frontend regression checks. The running website still serves plain local HTML, CSS and JavaScript with no package installation.

```sh
npm ci --ignore-scripts
npm test
```

The DOM tests execute the actual controller against the existing test fixture API contract. They check startup, risk-qualified cards, scanner filtering, watchlist persistence, historical chart selection, confirmed-view gating, unavailable data, trajectory gaps and bounded live-history caching. API tests verify the normalization and authentication boundary. Both run in CI alongside the Python suite.

The visual design was ported directly from the supplied reference CSS and shell. Interactive browser visual inspection was unavailable because local browser control was disabled in the authoring environment; DOM checks do not certify pixel layout. No production brokerage connection or local-model inference was verified for this frontend release.
