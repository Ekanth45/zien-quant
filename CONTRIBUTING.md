# Contributing to Zien Quant

Thank you for your interest in contributing to Zien Quant - Order Block Terminal!

## Core Principles

1. **Standard Library Only**: Runtime code must strictly rely on the Python 3.12+ Standard Library. Do not introduce third-party runtime dependencies (e.g. `requests`, `numpy`, `pandas`, `yfinance`).
2. **Zero Fake or Synthetic Data**: The terminal must never fabricate, guess, or synthesize market prices or candles. When data is unavailable, report it honestly via `CLOSED` or `FEED_DOWN` states.
3. **Strict Secret Safety**: Never commit credentials, passwords, tokens, API keys, database files (`*.db`), or personal filesystem paths. Every commit must pass `scripts/secret_scan.py`.
4. **Preserve Visual Theme**: The dark institutional trading aesthetic, high-contrast palette, and responsive canvas river layout must be maintained across all viewport sizes.

## Local Development Setup

### Prerequisites
- Python 3.12 or newer.
- Git.
- Optional: Ollama running locally with `gemma4:12b` for AI synthesis testing.

### Quickstart
1. Clone the repository:
   ```bash
   git clone https://github.com/ekanth14/zien-quant.git
   cd zien-quant
   ```

2. Run automated setup:
   - **Linux/macOS**:
     ```bash
     bash scripts/setup.sh
     ```
   - **Windows PowerShell**:
     ```powershell
     .\scripts\setup.ps1
     ```

3. Run the automated test suite:
   ```bash
   python -m unittest discover -s tests
   ```

4. Run the secret scanner to verify no secrets are introduced:
   ```bash
   python scripts/secret_scan.py --working-tree-only
   ```

## Development Guidelines

- Run `python -m compileall -q .` before submitting changes to catch any syntax issues.
- When creating or modifying tests, place tests under `tests/` or `marketscope/tests/`. Tests should use temporary directories (`tempfile.TemporaryDirectory`) for database fixtures and never mutate real runtime databases.
- Keep commits focused and atomic with descriptive commit messages.
