import asyncio
import random
import time
from typing import Optional, Tuple

from core.logger import get_logger
from core.templates import (
    CF_INTERSTITIAL_JS,
    TOKEN_VALUE_JS,
    WIDGET_ERROR_JS,
    WIDGET_INJECT_JS,
    WIDGET_PRESENT_JS,
    build_route_html,
    route_glob,
)

logger = get_logger()


def _cubic_bezier(p0, p1, p2, p3, t):
    mt = 1 - t
    x = (mt ** 3) * p0[0] + 3 * (mt ** 2) * t * p1[0] + 3 * mt * (t ** 2) * p2[0] + (t ** 3) * p3[0]
    y = (mt ** 3) * p0[1] + 3 * (mt ** 2) * t * p1[1] + 3 * mt * (t ** 2) * p2[1] + (t ** 3) * p3[1]
    return x, y


async def human_mouse_move(page, target_x: float, target_y: float) -> None:
    """Move the mouse along a jittered cubic-bezier path (human-like)."""
    start_x = random.uniform(15, 220)
    start_y = random.uniform(15, 180)
    cp1 = (
        start_x + (target_x - start_x) * random.uniform(0.15, 0.4) + random.uniform(-40, 40),
        start_y + (target_y - start_y) * random.uniform(0.0, 0.3) + random.uniform(-30, 30),
    )
    cp2 = (
        start_x + (target_x - start_x) * random.uniform(0.6, 0.9) + random.uniform(-30, 30),
        start_y + (target_y - start_y) * random.uniform(0.7, 1.0) + random.uniform(-20, 20),
    )
    steps = random.randint(18, 30)
    for i in range(1, steps + 1):
        t = i / steps
        # ease-in-out so the pointer accelerates then settles on target
        eased = t * t * (3 - 2 * t)
        x, y = _cubic_bezier((start_x, start_y), cp1, cp2, (target_x, target_y), eased)
        await page.mouse.move(
            x + random.uniform(-0.8, 0.8),
            y + random.uniform(-0.8, 0.8),
            steps=1,
        )
        await asyncio.sleep(random.uniform(0.006, 0.018))
    await page.mouse.move(target_x, target_y, steps=1)


async def _human_click_iframe(page, frame) -> bool:
    try:
        el = await frame.frame_element()
        box = await el.bounding_box()
    except Exception:
        return False
    if not box or box['width'] < 20 or box['height'] < 10:
        return False

    # Turnstile checkbox sits on the left edge of the widget.
    offset_x = random.uniform(24, min(38, box['width'] - 8))
    target_x = box['x'] + offset_x
    target_y = box['y'] + box['height'] / 2 + random.uniform(-3, 3)

    await human_mouse_move(page, target_x, target_y)
    await asyncio.sleep(random.uniform(0.15, 0.4))
    try:
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.06, 0.14))
        await page.mouse.up()
        return True
    except Exception:
        return False


async def click_turnstile_checkbox(page, attempts: int = 15) -> bool:
    for _ in range(attempts):
        for fr in page.frames:
            if 'challenges.cloudflare.com' not in (fr.url or ''):
                continue
            if await _human_click_iframe(page, fr):
                logger.debug("Clicked Turnstile checkbox with human-like motion")
                return True
            # Coordinate click can fail if the widget is re-rendered; fall back
            # to the frame-relative API.
            for sel in ('input[type=checkbox]', 'label', 'body'):
                try:
                    await fr.click(sel, timeout=1500)
                    return True
                except Exception:
                    continue
        await asyncio.sleep(1)
    return False


async def wait_for_widget(page, timeout_s: int = 20) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if await page.evaluate(WIDGET_PRESENT_JS):
                return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def _read_error(page) -> Optional[str]:
    try:
        return await page.evaluate(WIDGET_ERROR_JS)
    except Exception:
        return None


async def wait_for_token(page, timeout_s: int = 90, click_after_s: int = 12) -> Optional[str]:
    start = time.monotonic()
    clicked = False
    last_error: Optional[str] = None

    while time.monotonic() - start < timeout_s:
        try:
            token = await page.evaluate(TOKEN_VALUE_JS)
        except Exception:
            token = ''
        if token:
            return token

        error = await _read_error(page)
        if error:
            last_error = error

        elapsed = time.monotonic() - start
        if not clicked and elapsed >= click_after_s:
            # One interaction attempt. Turnstile's managed mode usually solves
            # without a click; retrying every poll would look automated.
            clicked = True
            if await click_turnstile_checkbox(page, attempts=1):
                logger.debug("Turnstile did not auto-solve; interaction attempted")
        await asyncio.sleep(0.5)

    if last_error:
        logger.warning(f"Turnstile widget error: {last_error}")
    return None


async def solve_route(page, url: str, sitekey: str, action: Optional[str] = None,
                      cdata: Optional[str] = None, deadline: Optional[float] = None
                      ) -> Tuple[Optional[str], str, Optional[str]]:
    """Render an artificial widget at the target origin (avoids the WAF page)."""
    if deadline is None:
        deadline = time.monotonic() + 90
    page_data = build_route_html(sitekey, action, cdata)
    pattern = route_glob(url)

    async def _fulfill(route):
        await route.fulfill(
            status=200,
            body=page_data,
            headers={
                'content-type': 'text/html; charset=utf-8',
                'cache-control': 'no-store',
            },
        )

    await page.route(pattern, _fulfill)
    logger.info(f"Route-intercept {pattern}")

    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
    except Exception as exc:
        logger.warning(f"Route-intercept navigation failed: {exc}")
        return None, pattern, f'goto: {exc}'

    # The Turnstile script is async: wait for its iframe to be mounted before
    # polling the response input. On Next.js SPAs this is the only reliable
    # signal that the widget has actually rendered.
    await wait_for_widget(page, min(20, max(0, deadline - time.monotonic())))
    token = await wait_for_token(page, max(0, deadline - time.monotonic()))
    error = None if token else await _read_error(page)
    return token, pattern, error


async def solve_realpage(page, url: str, sitekey: str, action: Optional[str] = None,
                         cdata: Optional[str] = None, deadline: Optional[float] = None
                         ) -> Optional[str]:
    """Load the real page and wait out WAF + app hydration before solving."""
    if deadline is None:
        deadline = time.monotonic() + 90
    logger.info(f"Real-page {url}")
    status = None
    try:
        response = await page.goto(url, wait_until='domcontentloaded', timeout=45000)
        status = response.status if response else None
    except Exception as exc:
        logger.warning(f"Real-page navigation failed: {exc}")

    if status and status >= 400:
        logger.warning(f"Real-page returned HTTP {status} (Cloudflare WAF?)")

    # A WAF interstitial may need one interaction before it clears.
    try:
        if await page.evaluate(CF_INTERSTITIAL_JS):
            await click_turnstile_checkbox(page, attempts=3)
    except Exception:
        pass

    # Wait for a Cloudflare interstitial ("Just a moment...") to clear. A
    # headed browser usually passes it automatically; headless never does.
    waf_budget = min(30, max(0, (deadline - time.monotonic()) / 2))
    waf_deadline = time.monotonic() + waf_budget
    while time.monotonic() < waf_deadline:
        try:
            interstitial = await page.evaluate(CF_INTERSTITIAL_JS)
        except Exception:
            interstitial = False
        if not interstitial:
            break
        await asyncio.sleep(1)

    # Wait for the SPA / widget to hydrate.
    await wait_for_widget(page, min(20, max(0, deadline - time.monotonic())))
    has_widget = False
    try:
        has_widget = bool(await page.evaluate(
            "() => !!document.querySelector('.cf-turnstile')"
        ))
    except Exception:
        pass

    if sitekey and not has_widget and deadline - time.monotonic() > 10:
        try:
            await page.evaluate(WIDGET_INJECT_JS, {
                'sitekey': sitekey,
                'action': action,
                'cdata': cdata,
            })
            await wait_for_widget(page, min(10, max(0, deadline - time.monotonic())))
        except Exception as exc:
            logger.warning(f"Widget injection failed: {exc}")

    token = await wait_for_token(page, max(0, deadline - time.monotonic()))
    if not token:
        error = await _read_error(page)
        if error:
            logger.warning(f"Turnstile widget error: {error}")
    return token


async def solve(page, url: str, sitekey: str, action: Optional[str] = None,
                cdata: Optional[str] = None, timeout_s: int = 90
                ) -> Tuple[Optional[str], str]:
    """Route-intercept first, real page as fallback. Returns (token, method)."""
    deadline = time.monotonic() + timeout_s
    token, pattern, error = await solve_route(
        page, url, sitekey, action, cdata, deadline
    )
    if token:
        logger.debug(f"Turnstile solved via route ({len(token)} chars)")
        return token, 'route'

    logger.info(f"Route failed ({error or 'no token'}), trying real-page")
    try:
        await page.unroute(pattern)
    except Exception:
        pass

    if deadline - time.monotonic() < 10:
        logger.warning("No time left for real-page fallback")
        return None, 'real-page'

    token = await solve_realpage(page, url, sitekey, action, cdata, deadline)
    return token, 'real-page'
