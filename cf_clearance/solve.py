import asyncio
import time
from typing import Optional, Tuple

from core.logger import get_logger
from core.templates import CF_INTERSTITIAL_JS
from turnstile.solve import click_turnstile_checkbox

logger = get_logger()

REPLAY_WARNING = (
    "cf_clearance is bound to IP + JA3/TLS + User-Agent. Replay only from the "
    "same IP, with this exact User-Agent, over a TLS stack producing the same JA3."
)


def find_clearance(cookies: list) -> Optional[dict]:
    return next((c for c in cookies if c.get('name') == 'cf_clearance'), None)


async def is_interstitial(page) -> bool:
    try:
        return bool(await page.evaluate(CF_INTERSTITIAL_JS))
    except Exception:
        return False


async def _wait_clearance(page, timeout_s: int) -> Tuple[Optional[dict], list]:
    deadline = time.monotonic() + timeout_s
    clearance: Optional[dict] = None
    cookies: list = []
    while time.monotonic() < deadline:
        cookies = await page.context.cookies()
        found = find_clearance(cookies)
        if found:
            clearance = found
        interstitial = await is_interstitial(page)
        if clearance and not interstitial:
            return clearance, cookies
        await asyncio.sleep(1)
    return clearance, cookies


async def solve(page, url: str, timeout_s: int = 60) -> dict:
    """Pass the Cloudflare interstitial on a real page and harvest cf_clearance."""
    start = time.monotonic()
    status = None
    try:
        response = await page.goto(url, wait_until='domcontentloaded', timeout=45000)
        status = response.status if response else None
    except Exception as exc:
        logger.warning(f"cf_clearance navigation failed: {exc}")

    if status and status >= 400:
        logger.info(f"cf_clearance page returned HTTP {status}; waiting for challenge")

    # A Cloudflare WAF/Turnstile interstitial may need an interaction. Only
    # click when one is actually present, so we never disturb an already
    # solved page or an SPA that renders its own widget later.
    if await is_interstitial(page):
        try:
            await click_turnstile_checkbox(page, attempts=8)
        except Exception:
            pass

    clearance, cookies = await _wait_clearance(page, timeout_s)
    ua = await page.evaluate('() => navigator.userAgent')
    lang = await page.evaluate('() => navigator.language')

    result = {
        'cf_clearance': clearance,
        'cookies': cookies,
        'user_agent': ua,
        'headers': {'User-Agent': ua, 'Accept-Language': lang},
        'elapsed': round(time.monotonic() - start, 1),
        'warning': REPLAY_WARNING,
    }
    if not clearance:
        result['error'] = 'cf_clearance not set (challenge unsolved)'
    return result
