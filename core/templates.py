from typing import Optional
from urllib.parse import urlsplit

HTML_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Turnstile</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 100%; height: 100%; }
body { background: #ffffff; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
</style>
<script>
window.__tsToken = '';
window.__tsError = null;
window.__tsCallback = function (token) { window.__tsToken = token || ''; };
window.__tsErrorCallback = function (code) { window.__tsError = code; };
</script>
</head>
<body>
<!--WIDGET-->
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
</body></html>"""

WIDGET_INJECT_JS = r"""(opts) => {
  const key = typeof opts === 'string' ? opts : opts.sitekey;
  if (!key) return false;
  if (document.querySelector('.cf-turnstile')) return true;
  const d = document.createElement('div');
  d.className = 'cf-turnstile';
  d.setAttribute('data-sitekey', key);
  if (opts && opts.action) d.setAttribute('data-action', opts.action);
  if (opts && opts.cdata) d.setAttribute('data-cdata', opts.cdata);
  // The callbacks only exist on our synthetic page. On a real site they are
  // undefined, and Turnstile rejects an unknown callback name.
  if (typeof window.__tsCallback === 'function') {
    d.setAttribute('data-callback', '__tsCallback');
  }
  if (typeof window.__tsErrorCallback === 'function') {
    d.setAttribute('data-error-callback', '__tsErrorCallback');
  }
  (document.body || document.documentElement).prepend(d);
  if (window.turnstile && typeof window.turnstile.render === 'function') {
    try { window.turnstile.render(d); } catch (e) {}
  }
  return true;
}"""

TOKEN_VALUE_JS = r"""() => {
  const e = document.querySelector('[name=cf-turnstile-response]');
  const fromInput = e && e.value ? e.value : '';
  return fromInput || window.__tsToken || '';
}"""

WIDGET_ERROR_JS = r"""() => {
  const e = document.querySelector('[name=cf-turnstile-response]');
  return window.__tsError || (e ? e.getAttribute('data-error-code') : null) || null;
}"""

WIDGET_PRESENT_JS = r"""() => {
  return !!document.querySelector(
    'iframe[src*="challenges.cloudflare.com"], input[name=cf-turnstile-response]'
  );
}"""

CF_INTERSTITIAL_JS = r"""() => {
  const html = document.documentElement ? document.documentElement.outerHTML : '';
  const t = (document.title || '').toLowerCase();
  return (
    !!document.querySelector('#challenge-form, form#challenge-form') ||
    !!document.querySelector('#cf-wrapper, .cf-browser-verification, #challenge-running, #trk_jschal_js') ||
    !!document.querySelector('iframe[src*="challenges.cloudflare.com/cdn-cgi/challenge-platform"]') ||
    /window\._cf_chl_opt|__cf_chl_/.test(html) ||
    /just a moment|attention required|checking your browser|verifying you are human/.test(t)
  );
}"""


def route_glob(url: str) -> str:
    parts = urlsplit(url)
    if parts.path in ('', '/'):
        return f'{parts.scheme}://{parts.netloc}/**'
    return url


def build_route_html(sitekey: str, action: Optional[str] = None,
                     cdata: Optional[str] = None) -> str:
    div = f'<div class="cf-turnstile" data-sitekey="{sitekey}"'
    if action:
        div += f' data-action="{action}"'
    if cdata:
        div += f' data-cdata="{cdata}"'
    div += ' data-callback="__tsCallback" data-error-callback="__tsErrorCallback"'
    return HTML_TEMPLATE.replace('<!--WIDGET-->', div + '></div>')
