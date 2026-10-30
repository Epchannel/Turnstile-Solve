# Changelog

All notable changes to this project are documented here.

## [2.1.0] — 2026-10-30

### Fixed

- Real Chrome/Turnstile challenges no longer fail with `ERROR_CAPTCHA_UNSOLVABLE`:
  - Headed Chrome is now the default. `--headless=new` is detected by Cloudflare, even with persistent profiles and a spoofed UA.
  - Removed forced User-Agent and `sec-ch-ua` overrides in headed mode. A UA mismatch (for example Chrome 150 vs. installed Chrome 156) makes `navigator.userAgentData` inconsistent.
  - Removed locale/timezone overrides, which were verified to break token issuance.
  - Removed all `context.add_init_script()` fingerprint injection. Any init script, even an empty string, is detected by Turnstile. Patchright + native headed Chrome already expose correct values.
- `cf_clearance`: wait until the interstitial actually disappears instead of returning the cookie too early.
- Bounded the Turnstile solve deadline so route + real-page fallback cannot exceed the requested `timeout`.

### Added

- Per-request `proxy` and `timeout` query parameters on `GET /turnstile`.
- `ERROR_WRONG_PROXY` for malformed proxy strings.
- Robust Next.js/SPA widget handling:
  - wait for the Turnstile iframe / response input to mount;
  - read the token from `input[name=cf-turnstile-response]` or the widget callback;
  - read widget error codes for diagnostics;
  - inject a widget on real pages when the app has not rendered one.
- Human-like bezier-curve mouse movement and checkbox click fallback.
- WAF interstitial detection and early interaction on the real page.
- `core/stealth.py`: fingerprint verification (`webdriver`, `chrome`, plugins, languages, WebGL, screen, timezone) printed with `--debug`.
- `test_solve.py`: CLI client for `turnstile` and `cf_clearance`, with proxy and deadline support.
- `CHANGELOG.md`, expanded README (EN/RU), and integration guide updates.

### Changed

- **Breaking:** `python api.py` now runs headed by default. Use `--headless` only for Turnstile test keys. `--no-headless` remains accepted and is the default.
- Browser window is 1366×900; headed contexts use `no_viewport=True` to avoid CDP device-metrics emulation.
- Linux without `DISPLAY`/`WAYLAND_DISPLAY` falls back to headless with a warning; use Xvfb for real challenges.
- Proxy parser now supports `host:port`, `host:port:user:pass`, `user:pass@host:port`, `scheme://host:port`, and `scheme://user:pass@host:port`.
- Dashboard/console version display updated to 2.1.0.

### Verified

- iHerb target `https://checkout9.iherb.com/auth/ui/account/login`, sitekey `0x4AAAAAADmKZAkmJVxUyvHF`, action `account_check`:
  - `status: ready`
  - token length: **752** characters
  - elapsed: **~6 s** (including browser startup)
- One run required the human-like click fallback after 12 s and solved at ~16.5 s, also with a 752-character token.
- Turnstile demo key with `--headless`: `XXXX.DUMMY.TOKEN.XXXX`.
- Malformed proxy: `ERROR_WRONG_PROXY`.

## [2.0.0]

- IUAM support: new `/cf_clearance` endpoint returning cookies, User-Agent, headers, and a replay warning.
- Modular architecture: `turnstile/`, `cf_clearance/`, `core/`.
- In-memory task storage with TTL cleanup.
- Quiet logging mode.
