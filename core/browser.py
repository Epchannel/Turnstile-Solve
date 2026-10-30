import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from patchright.async_api import async_playwright

from .logger import get_logger
from .stealth import sec_ch_ua_for

logger = get_logger()

CHROMIUM_LIKE = ('chromium', 'chrome', 'msedge')

# Keep these in sync with the current stable Chrome.  They are only used when
# running headless (where Chrome reports "HeadlessChrome" in the UA) or when the
# caller explicitly forces a UA.  Headed mode uses the browser's native values,
# which is always the best choice for anti-bot scoring.
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
)

PROXIES_PATH = Path(__file__).resolve().parent.parent / 'proxies.txt'


@dataclass
class BrowserConfig:
    browser_type: str = 'chrome'
    # Real Cloudflare challenges reject headless browsers regardless of stealth
    # patches.  Headed is the default; use --headless only for test keys.
    headless: bool = False
    useragent: Optional[str] = None
    sec_ch_ua: Optional[str] = None
    proxy_support: bool = False
    debug: bool = False
    window_width: int = 1366
    window_height: int = 900

    def __post_init__(self) -> None:
        if self.browser_type in CHROMIUM_LIKE:
            if self.headless and not self.useragent:
                self.useragent = CHROME_USER_AGENT
            if self.useragent:
                # Keep UA and Client-Hints consistent whenever a UA is forced.
                self.sec_ch_ua = sec_ch_ua_for(self.useragent)


def mask_proxy(proxy: Optional[str]) -> Optional[str]:
    """Hide credentials before logging a proxy string."""
    if not proxy:
        return None
    if '@' not in proxy:
        return proxy
    scheme, rest = proxy.split('://', 1) if '://' in proxy else ('http', proxy)
    return f'{scheme}://***@{rest.split("@", 1)[1]}'


def parse_proxy(proxy: str) -> dict:
    """Parse the common proxy formats accepted by proxies.txt.

    Supported:
      host:port
      host:port:user:pass
      user:pass@host:port
      scheme://host:port
      scheme://user:pass@host:port
    """
    proxy = proxy.strip()
    if '://' not in proxy:
        if '@' in proxy:
            auth, addr = proxy.split('@', 1)
            user, sep, pwd = auth.partition(':')
            if not sep:
                raise ValueError('proxy credentials must be user:pass')
            return {'server': f'http://{addr}', 'username': user, 'password': pwd}
        parts = proxy.split(':')
        if len(parts) == 4:
            host, port, user, pwd = parts
            return {
                'server': f'http://{host}:{port}',
                'username': user,
                'password': pwd,
            }
        return {'server': f'http://{proxy}'}

    scheme, rest = proxy.split('://', 1)
    if '@' in rest:
        auth, addr = rest.split('@', 1)
        user, sep, pwd = auth.partition(':')
        if not sep:
            raise ValueError('proxy credentials must be user:pass')
        return {'server': f'{scheme}://{addr}', 'username': user, 'password': pwd}

    parts = rest.split(':')
    if len(parts) == 4:
        host, port, user, pwd = parts
        return {
            'server': f'{scheme}://{host}:{port}',
            'username': user,
            'password': pwd,
        }
    return {'server': proxy}


def pick_proxy(proxy_support: bool) -> Optional[str]:
    if not proxy_support:
        return None
    try:
        lines = PROXIES_PATH.read_text(encoding='utf-8-sig').splitlines()
    except FileNotFoundError:
        logger.warning(f"Proxy file not found: {PROXIES_PATH}")
        return None
    proxies = [
        line.strip() for line in lines
        if line.strip() and not line.lstrip().startswith('#')
    ]
    return random.choice(proxies) if proxies else None


async def launch_browser(config: BrowserConfig) -> Tuple[object, object]:
    if config.browser_type == 'camoufox':
        from camoufox.async_api import AsyncCamoufox
        driver = AsyncCamoufox(headless=config.headless)
        browser = await driver.start()
        return driver, browser

    driver = await async_playwright().start()
    args = [f'--window-size={config.window_width},{config.window_height}']
    if config.headless:
        args.append('--headless=new')
    else:
        # Keep rendering / timers alive when the window is occluded, minimized
        # or on a background desktop.
        args.extend([
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-background-timer-throttling',
        ])
    # ``headless=False`` + ``--headless=new`` is the supported way to run
    # channel=chrome headless; it also keeps Patchright's launch flags intact.
    browser = await driver.chromium.launch(
        channel=config.browser_type,
        headless=False,
        args=args,
    )
    return driver, browser


def context_options(config: BrowserConfig, proxy: Optional[str]) -> dict:
    if config.browser_type in CHROMIUM_LIKE:
        if config.headless:
            opts: dict = {
                'viewport': {
                    'width': config.window_width,
                    'height': config.window_height,
                }
            }
        else:
            # Avoid CDP device-metrics emulation: headed Chrome already has a
            # real window/screen pair, and emulation is a known bot signal.
            opts = {'no_viewport': True}
    else:
        opts = {
            'viewport': {
                'width': config.window_width,
                'height': config.window_height,
            }
        }

    if config.useragent:
        opts['user_agent'] = config.useragent
    if config.sec_ch_ua:
        opts['extra_http_headers'] = {
            'sec-ch-ua': config.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }
    if proxy:
        opts['proxy'] = parse_proxy(proxy)
    return opts


async def close_browser(driver, browser, debug: bool = False) -> None:
    try:
        if browser:
            await browser.close()
    except Exception as e:
        if debug:
            logger.debug(f"Browser close error: {e}")
    try:
        if driver and hasattr(driver, 'stop'):
            await driver.stop()
    except Exception as e:
        if debug:
            logger.debug(f"Driver stop error: {e}")
