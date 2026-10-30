# 🚀 Cloudflare Turnstile & IUAM Automation API

Local REST API for automated handling of Cloudflare Turnstile and IUAM (Under Attack Mode) challenge pages in a real browser — returns tokens and `cf_clearance` session bundles.

[![Version](https://img.shields.io/badge/version-2.1.0-blue)](https://github.com/D3-vin/Turnstile-Solver-NEW/releases)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Educational%20Use-green)](LICENSE)

[![Telegram Channel](https://img.shields.io/badge/Telegram-Channel-blue?logo=telegram)](https://t.me/D3_vin)
[![Telegram Chat](https://img.shields.io/badge/Telegram-Chat-blue?logo=telegram)](https://t.me/D3vin_chat)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black?logo=github)](https://github.com/D3-vin/Turnstile-Solver-NEW)

[Features](#features) • [How it works](#how-it-works) • [Quick Start](#quick-start) • [Usage](#usage) • [API](#api-documentation) • [Troubleshooting](#troubleshooting) • [Changelog](CHANGELOG.md) • [Contact](#contact)

[English](#) | [Русский](README_RU.md)

---

> **New in 2.1:** headed Chrome by default, stealth rules validated against a real Cloudflare challenge, per-request `proxy` on `/turnstile`, robust Next.js/SPA widget handling, human-like checkbox interaction, bounded solve deadlines, and a working `test_solve.py`. Verified against iHerb (`checkout9.iherb.com`, sitekey `0x4AAAAAADmKZAkmJVxUyvHF`, action `account_check`) — 752-character token.

## Features

- 🎯 **Turnstile challenge automation** — route-intercept stub page with real-page fallback; usually 4–20 seconds of solve time, excluding queue and browser startup
- 🛡️ **IUAM / Challenge pass** — Managed Challenge + JS Challenge interstitials, returns `cf_clearance` with the full session bundle (cookies, User-Agent, headers)
- 🥷 **Stealth-first** — Patchright + real **headed** Chrome. No User-Agent/locale/fingerprint injection (init scripts are themselves detected by Turnstile)
- 🚀 **Multi-threaded** — multiple tasks simultaneously with a concurrency limit
- 🌐 **Multiple browsers** — Chrome, Edge, Chromium, Camoufox
- 🔌 **Proxy support** — every common format from `proxies.txt`, plus a per-request `proxy` parameter on both endpoints
- 📊 **REST API** — async task model (create task → poll result), easy to integrate
- 📦 **No database** — tasks live in memory, nothing to maintain

---

## How it works

### Turnstile (`/turnstile`)

1. A browser context is created, optionally with the per-request proxy.
2. The solver registers a route for the target URL and fulfills it with a minimal page that renders a Turnstile widget using the supplied `sitekey`, `action` and `cdata`.
3. The widget is rendered at the **target origin** (for example `checkout9.iherb.com`), so domain-bound sitekeys keep working while the real page — and its WAF — is bypassed.
4. The solver waits for the Turnstile iframe, then reads the token from `input[name=cf-turnstile-response]` or the widget callback.
5. If Turnstile requires interaction, a human-like bezier-curve mouse movement clicks the checkbox.
6. If the route approach fails, the solver unroutes, loads the real page, waits out a Cloudflare interstitial, waits for the SPA/widget to hydrate, injects a widget if necessary, and retries within the remaining deadline.

### IUAM / `cf_clearance` (`/cf_clearance`)

1. The real protected URL is loaded in a headed browser.
2. If a Cloudflare interstitial is present, the solver clicks the checkbox with human-like motion.
3. The browser context is polled until a `cf_clearance` cookie exists **and** the interstitial is gone.
4. The API returns the cookie, all context cookies, the User-Agent, `Accept-Language`, and a replay warning.

### Stealth rules (important)

These rules were verified against a real iHerb Turnstile challenge:

- **Headed Chrome is required** for real challenges. `--headless=new` is detected, even with persistent profiles and a spoofed UA.
- **Do not force a User-Agent.** A UA such as Chrome 150 while the installed Chrome is 156 makes `navigator.userAgentData` inconsistent and fails the challenge.
- **Do not override locale/timezone.** `locale="en-US"` alone was enough to make the token never arrive.
- **Do not inject JavaScript fingerprints.** Any `context.add_init_script()`, even an empty string, is detected by Turnstile. Patchright already hides `navigator.webdriver`; native headed Chrome already has real `window.chrome`, plugins, languages, WebGL and audio values.
- `--debug` prints a fingerprint report (`webdriver`, `chrome`, plugins, languages, WebGL, screen, timezone) so regressions are visible.

### Task lifecycle

- Tasks are stored in RAM. A restart loses all tasks.
- Tasks older than **3600 s** are removed every **600 s**.
- `--thread` (default **4**) limits concurrent browser tasks; extra tasks wait with `status: "processing"`.
- There is no cancel endpoint and no idempotency key. Each create call creates a new task.
- Queued time and browser startup are **not** included in the solver-side `timeout`; keep a separate client-side deadline.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/D3-vin/Turnstile-Solver-NEW.git
cd Turnstile-Solver-NEW
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 2. Install a browser

```bash
python -m patchright install chromium   # or: install msedge / use system Chrome
python -m camoufox fetch                # optional, only for --browser_type camoufox
```

System Chrome via `channel="chrome"` is recommended. If Chrome is already installed, no extra download is needed.

### 3. Run

```bash
python api.py
```

Server starts on `http://0.0.0.0:5072`. The browser runs **headed by default** — real Turnstile/WAF challenges reject headless Chrome, even with stealth patches. Use `--headless` only for Turnstile test keys.

On Windows you can also double-click `start_solver.bat` (binds `127.0.0.1:5072`).

> On Linux without a desktop, run Chrome under Xvfb (`xvfb-run -a python api.py`). The server falls back to headless when no `DISPLAY`/`WAYLAND_DISPLAY` is found, and real challenges will then fail.

---

## Usage

```bash
python api.py [options]

Options:
  --headless              Run headless (test keys only; real Cloudflare needs a display)
  --no-headless           Show the browser window (default)
  --browser_type string   chromium | chrome | msedge | camoufox (default "chrome")
  --thread int            Max concurrent tasks (default 4)
  --proxy                 Use a random proxy from proxies.txt
  --useragent string      Custom User-Agent (best left unset for real challenges)
  --debug                 Verbose logs + fingerprint report + HTTP access logs
  --host string           Listen address (default "0.0.0.0")
  --port string           Listen port (default "5072")
```

### Test client

`test_solve.py` defaults to the public Turnstile demo. It supports both task types, per-request proxies and a client-side deadline.

```bash
# Turnstile demo (dummy token)
python test_solve.py

# IUAM / cf_clearance (defaults to ivasms.com)
python test_solve.py --type cf_clearance
python test_solve.py --type cf_clearance --proxy http://user:pass@ip:port

# Real, domain-bound Turnstile (iHerb)
python test_solve.py --type turnstile --url https://checkout9.iherb.com/auth/ui/account/login --sitekey 0x4AAAAAADmKZAkmJVxUyvHF --action account_check
```

| Client option | Default | Description |
|---|---|---|
| `--type` | `turnstile` | `turnstile` or `cf_clearance` |
| `--base` | `http://127.0.0.1:5072` | Solver base URL |
| `--url` | demo / ivasms | Target page URL |
| `--sitekey` | demo key | Turnstile site key |
| `--action` | — | Widget `data-action` |
| `--cdata` | — | Widget `data-cdata` |
| `--proxy` | — | Per-request proxy |
| `--solve-timeout` | `60` | Server-side cookie wait for `cf_clearance` |
| `--deadline` | `180` | Client-side total deadline (seconds) |

---

## API Documentation

All endpoints are **HTTP GET** and return JSON. There is no API key. Business errors still use HTTP 200; check the `errorId` field.

`GET /` returns an HTML usage page, not a JSON health check.

### Turnstile

```
GET /turnstile?url=https://example.com&sitekey=0x4AAAAAAA
```

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `url` | string | Page where Turnstile is validated | Yes |
| `sitekey` | string | Turnstile site key | Yes |
| `action` | string | Widget `data-action` binding | No |
| `cdata` | string | Widget `data-cdata` binding | No |
| `proxy` | string | Per-request proxy (`http://user:pass@host:port`) | No |
| `timeout` | int | Solve budget in seconds, after browser startup (default 90, min 10) | No |

> `proxy` is applied to the browser context **before** navigation, so Turnstile sees the proxy exit IP instead of the server IP. If omitted and the server was started with `--proxy`, a random proxy from `proxies.txt` is used.

### IUAM (`cf_clearance`)

```
GET /cf_clearance?url=https://protected.com&proxy=http://user:pass@ip:port
```

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `url` | string | Cloudflare-protected page URL | Yes |
| `proxy` | string | Per-request proxy (`cf_clearance` is bound to the exit IP) | No |
| `timeout` | int | Cookie wait in seconds (default 60, min 10) | No |

### Create task

Both endpoints return:

```json
{ "errorId": 0, "taskId": "d2cbb257-9c37-4f9c-9bc7-1eaee72d96a8" }
```

This only confirms task creation, not a successful solve.

### Get result

```
GET /result?id=d2cbb257-9c37-4f9c-9bc7-1eaee72d96a8
```

Processing (or waiting for a free slot):

```json
{ "status": "processing" }
```

Turnstile ready:

```json
{ "errorId": 0, "status": "ready", "solution": { "token": "1.xxxxx..." } }
```

`/result` intentionally does **not** expose the internal `method` (`route` / `real-page`) or solver timing for Turnstile.

`cf_clearance` ready:

```json
{
  "errorId": 0,
  "status": "ready",
  "solution": {
    "cf_clearance": {
      "name": "cf_clearance",
      "value": "...",
      "domain": ".example.com",
      "path": "/",
      "httpOnly": true,
      "secure": true
    },
    "cookies": [ "..." ],
    "user_agent": "Mozilla/5.0 ...",
    "headers": { "User-Agent": "Mozilla/5.0 ...", "Accept-Language": "en-US" },
    "elapsed": 12.3,
    "elapsed_time": 14.567,
    "proxy": "http://...",
    "warning": "cf_clearance is bound to IP + JA3/TLS + User-Agent..."
  }
}
```

> ⚠️ Replay `cf_clearance` only from the same IP, with the returned `user_agent`, over a client with a matching TLS fingerprint (curl-impersonate or a real browser).

### Error codes

Business errors use HTTP 200 and `errorId: 1`:

```json
{
  "errorId": 1,
  "errorCode": "ERROR_CAPTCHA_UNSOLVABLE",
  "errorDescription": "Workers could not solve the Captcha"
}
```

| `errorCode` | Meaning | Client action |
|---|---|---|
| `ERROR_WRONG_PAGEURL` | Missing `url`, or missing `sitekey` for Turnstile | Fix the request |
| `ERROR_WRONG_PROXY` | `proxy` could not be parsed | Fix the proxy format |
| `ERROR_WRONG_CAPTCHA_ID` | Unknown, expired or cleaned-up task ID | Stop polling this ID |
| `ERROR_CAPTCHA_UNSOLVABLE` | No token/cookie, browser error, or exception | Stop polling; inspect server logs |

`processing` responses do not contain `errorId`; do not treat that as an error. Detailed exceptions are never returned to the client.

---

## Proxy formats

`proxies.txt` accepts one proxy per line. Blank lines and lines starting with `#` are ignored.

```text
# host:port
1.2.3.4:8080

# host:port:user:pass
1.2.3.4:8080:user:pass

# user:pass@host:port
user:pass@1.2.3.4:8080

# scheme://host:port
socks5://1.2.3.4:1080

# scheme://user:pass@host:port
http://user:pass@1.2.3.4:8080
```

The same formats are accepted by the per-request `proxy` query parameter. Proxy credentials are masked in debug logs.

---

## Project Structure

```
Turnstile-Solver-NEW/
├── api.py               # Quart app: routes, in-memory tasks, CLI
├── test_solve.py        # Test client (turnstile / cf_clearance)
├── requirements.txt
├── API_INTEGRATION.md   # Detailed integration guide for client agents
├── CHANGELOG.md         # Release notes
├── core/
│   ├── browser.py       # Browser config, launch, context, proxy helpers
│   ├── logger.py        # Colored logger
│   ├── stealth.py       # UA/Client-Hints helpers + fingerprint verification
│   └── templates.py     # Turnstile HTML template, JS snippets, route glob
├── turnstile/
│   └── solve.py         # Route-intercept + real-page Turnstile automation
└── cf_clearance/
    └── solve.py         # IUAM interstitial pass + cf_clearance session bundle
```

---

## Troubleshooting

### "Browser not found"

Install the browser: `python -m patchright install chromium` (or use `--browser_type chrome` with system Chrome).

### "Port already in use"

Change it: `python api.py --port 5080`.

### `ERROR_CAPTCHA_UNSOLVABLE` on a real site

1. Confirm the browser is **headed** (default). `--headless` is rejected by real Cloudflare challenges.
2. Do **not** set `--useragent`: a forced UA that differs from the real Chrome version makes `navigator.userAgentData` inconsistent and is detected.
3. Watch `--debug` logs:
   - `Route-intercept ...` followed by `Turnstile solved via route` means the widget worked.
   - `Real-page returned HTTP 403 (Cloudflare WAF?)` means the target itself is behind a WAF; the route-intercept path intentionally bypasses it.
   - `Turnstile widget error: ...` indicates an invalid sitekey/domain/action binding, which cannot be solved by stealth.
4. Datacenter IPs are scored harshly — pass `proxy=` per request or run with a residential proxy.
5. Make sure the server has a real Chrome window/display. On Windows, an interactive desktop session is required; on Linux use Xvfb.

### `cf_clearance` not set

- Confirm the browser is headed.
- Check that the proxy exit IP is not blocked.
- Some sites require a specific region or a residential IP; datacenter IPs are often rejected.
- `timeout` only covers the cookie wait, not queue time or browser startup. Increase it and/or the client deadline.

### The process leaves Chrome windows behind

Each task closes its own browser and context. On Ctrl+C the server kills child processes via `psutil`. If a browser is orphaned after a hard kill, terminate the remaining `chrome.exe` processes manually.

---

## Deployment notes

- **Windows:** run the API in an interactive desktop session. A service running in session 0 has no real display and may behave like headless.
- **Linux:** use `xvfb-run -a python api.py`, or provide a real X11/Wayland display.
- **Docker:** include Chrome/Chromium and an Xvfb entrypoint; headless mode is not suitable for real challenges.
- **Concurrency:** each task launches a full browser. Lower `--thread` on memory-constrained machines.
- **Security:** the API has no authentication. Bind it to `127.0.0.1` or a trusted network only.

---

## Contact

- **GitHub**: https://github.com/D3-vin/Turnstile-Solver-NEW
- **Telegram Channel**: [@D3_vin](https://t.me/D3_vin)
- **Telegram Chat**: [@D3vin_chat](https://t.me/D3vin_chat)

---

## License

Educational use only — see [LICENSE](LICENSE).

## ⚠️ Disclaimer

This software is provided **for educational and research purposes only**, "AS IS", without warranty of any kind. The author is not responsible for any misuse, API blocking, IP bans, or other consequences — responsibility lies entirely on the end user. By using it, you agree to the Terms of Service of the respective services and the laws of your country. Not affiliated with Cloudflare, Inc.

> ПО предоставляется исключительно в образовательных и ознакомительных целях, «как есть». Автор не несёт ответственности за использование.
