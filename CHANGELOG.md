# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-26

### Added
- **Flow River Canvas Terminal**: Real-time canvas visualization of institutional capital flows across 4 algorithmic funnel stages (Accumulation, Absorption, Breakout, Retest).
- **Setup Cards with Strict R:R Gating**: Quantitative trade setups with mandatory Risk:Reward >= 1.5 requirement. Setups failing R:R or missing valid levels are strictly rejected.
- **Previous Session Playback**: Deterministic off-market replay powered entirely by real persisted exchange candles from the most recent trading session, with automatic weekend and NSE holiday detection.
- **Laya AI Institutional Commentary**: Background synthesis worker integration with local Ollama (`gemma4:12b`), with 0ms deterministic rules fallback and strict hallucination validator.
- **Real Exchange Scraper & Circuit Breaker**: Resilient scraper engine with exponential backoff, jitter, and automatic circuit breaker tripping on consecutive upstream errors.
- **Deterministic Session State Machine**: `LIVE`, `CLOSED` (previous session), and `FEED_DOWN` states with honest status banners.
- **Security & Multi-Tenant Isolation**: PBKDF2 HMAC-SHA256 password hashing, TOTP multi-factor authentication, secure cookie session manager, CSRF protection, and endpoint rate limiting.
- **Standard Library Zero-Pip Architecture**: Pure Python 3.12+ stdlib backend with zero third-party pip dependencies required for runtime.
- **CLI & Diagnostic Suite**: Built-in CLI commands `init-owner`, `doctor`, `import-stock-master`, and `diagnose-scraper`.
- **Automated Test Suite**: 128 comprehensive unit and integration tests covering security, algorithmic scoring, flow calculations, and session replay.
