"""Stealth helpers.

Patchright already removes the classical automation leaks:
``--enable-automation``, ``navigator.webdriver``, the Runtime.enable leak and
the command-flag leaks.  On top of that, a real *headed* Chrome exposes correct
plugins, languages, WebGL and audio values.

Do **not** inject JavaScript with ``context.add_init_script()`` here.  We
verified against checkout9.iherb.com that *any* init script (even an empty
string) is detected by Turnstile and makes the challenge time out: the
underlying ``Page.addScriptToEvaluateOnNewDocument`` call is itself a signal.
The safest configuration is therefore native headed Chrome with Patchright and
no fingerprint injection at all.

This module only builds UA/Client-Hints values and verifies the resulting
fingerprint for ``--debug``.
"""

import re
from typing import Optional

from .logger import get_logger

logger = get_logger()

CHROME_MAJOR_RE = re.compile(r"Chrome/(\d+)")

FINGERPRINT_JS = r"""() => {
  const gl = (() => {
    try {
      const c = document.createElement('canvas');
      const g = c.getContext('webgl') || c.getContext('experimental-webgl');
      const d = g.getExtension('WEBGL_debug_renderer_info');
      return {
        vendor: g.getParameter(d.UNMASKED_VENDOR_WEBGL),
        renderer: g.getParameter(d.UNMASKED_RENDERER_WEBGL),
      };
    } catch (e) { return null; }
  })();
  return {
    ua: navigator.userAgent,
    webdriver: navigator.webdriver,
    languages: navigator.languages,
    language: navigator.language,
    plugins: navigator.plugins ? navigator.plugins.length : 0,
    chrome: typeof window.chrome,
    chromeRuntime: !!(window.chrome && window.chrome.runtime),
    webgl: gl,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigator.deviceMemory,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    screen: [screen.width, screen.height],
    inner: [innerWidth, innerHeight],
  };
}"""


def chrome_major(ua: Optional[str]) -> Optional[str]:
    if not ua:
        return None
    match = CHROME_MAJOR_RE.search(ua)
    return match.group(1) if match else None


def sec_ch_ua_for(ua: Optional[str]) -> Optional[str]:
    """Build a ``sec-ch-ua`` header matching a forced User-Agent."""
    major = chrome_major(ua)
    if not major:
        return None
    return (
        f'"Chromium";v="{major}", "Not=A?Brand";v="24", '
        f'"Google Chrome";v="{major}"'
    )


def ua_is_headless(ua: Optional[str]) -> bool:
    return bool(ua and 'HeadlessChrome' in ua)


async def apply_stealth(context, config) -> None:
    """Intentionally a no-op.

    Kept as a single place to document/verify the stealth strategy.  Injecting
    scripts is counter-productive with Turnstile (see module docstring), and
    Patchright's launch flags already hide ``navigator.webdriver``.
    """
    return None


async def fingerprint(page) -> dict:
    try:
        return await page.evaluate(FINGERPRINT_JS)
    except Exception as exc:  # pragma: no cover - diagnostics only
        return {"error": str(exc)}


def log_fingerprint(report: dict) -> None:
    if "error" in report:
        logger.debug(f"Fingerprint check failed: {report['error']}")
        return
    webgl = report.get("webgl") or {}
    logger.debug(
        "Fingerprint: webdriver={} chrome={}/{} plugins={} languages={} "
        "webgl={} screen={} inner={} tz={}".format(
            report.get("webdriver"),
            report.get("chrome"),
            report.get("chromeRuntime"),
            report.get("plugins"),
            report.get("languages"),
            f"{webgl.get('vendor')} | {webgl.get('renderer')}" if webgl else None,
            report.get("screen"),
            report.get("inner"),
            report.get("timezone"),
        )
    )
    if report.get("webdriver") is not False:
        logger.warning("navigator.webdriver is not false - Patchright is not active")
    if not report.get("webgl"):
        logger.warning("WebGL is unavailable - browser may be running headless")
