'''
Detects and labels dead URLs based on each downloaded page:
- OK
- THIN
- dead/skip
'''

import re
from collections import namedtuple
from urllib.parse import urldefrag, urlparse

from crawl_extras import text
from crawl_extras.scope import in_allowed_domains

# our "low information value" thresholds; tune them from the test crawl
MIN_WORDS = 50                      # fewer visible words -> THIN
MAX_PAGE_BYTES = 10 * 1024 * 1024   # memory safety limit: bigger pages aren't parsed
SOFT_404_MAX_WORDS = 300            # real error pages are short
SOFT_404_TITLE = re.compile(r"not found|\b404\b\s*(?:error|page)|\berror\s*404\b", re.IGNORECASE)
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_CHARSET = re.compile(r"charset\s*=\s*[\"']?([\w.:-]+)", re.IGNORECASE)
_UTF16_32_BOMS = (b"\xff\xfe", b"\xfe\xff")

OK = "OK"
THIN = "THIN"
NOT_200 = "NOT_200"
DEAD_NO_RESPONSE = "DEAD_NO_RESPONSE"
DEAD_EMPTY = "DEAD_EMPTY"
DEAD_NO_TEXT = "DEAD_NO_TEXT"
SOFT_404 = "SOFT_404"
NOT_HTML = "NOT_HTML"
TOO_LARGE = "TOO_LARGE"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
INTERNAL_ERROR = "INTERNAL_ERROR"   # set by page_stats if checking a page crashed

# url = final url after redirects, tokens = every visible word, soup = parsed page or None
PageCheck = namedtuple("PageCheck", ["label", "url", "page_key", "tokens", "soup", "follow_links"])


# one key per page: lowercase host, no scheme, fragment or trailing "/"
def page_key(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower().rpartition("@")[2]
    key = host + parsed.path.rstrip("/")
    if parsed.query:
        key += "?" + parsed.query
    return key

def classify(url, resp):
    raw = getattr(resp, "raw_response", None)
    final_url = _final_url(url, raw)
    key = page_key(final_url)

    def result(label, follow_links, tokens=(), soup=None):
        return PageCheck(label, final_url, key, list(tokens), soup, follow_links)

    if getattr(resp, "status", None) != 200:
        return result(NOT_200, True)
    if raw is None:
        return result(DEAD_NO_RESPONSE, False)
    if not in_allowed_domains(final_url):
        return result(OUT_OF_SCOPE, True)  # links still followed in case this misfires

    content = body_bytes(raw)
    if not content or content.isspace():
        return result(DEAD_EMPTY, False)
    if len(content) > MAX_PAGE_BYTES:
        return result(TOO_LARGE, False)
    if not _is_html(raw):
        return result(NOT_HTML, False)

    soup = text.parse_html(content, _encoding_hint(raw, content))
    tokens = text.tokenize(text.extract_visible_text(soup))
    if not tokens:
        return result(DEAD_NO_TEXT, False, tokens, soup)
    if len(tokens) < SOFT_404_MAX_WORDS and SOFT_404_TITLE.search(text.page_title(soup)):
        return result(SOFT_404, True, tokens, soup)
    if len(tokens) < MIN_WORDS:
        return result(THIN, True, tokens, soup)
    return result(OK, True, tokens, soup)

# the url the page came from after redirects, fragment removed
def _final_url(url, raw):
    candidate = getattr(raw, "url", None) if raw is not None else None
    if not isinstance(candidate, str) or not candidate:
        candidate = url
    return urldefrag(candidate)[0]

# the body as bytes, or b"" if there isn't a usable one
def body_bytes(raw):
    try:
        content = raw.content
    except Exception:
        return b""
    if isinstance(content, bytes):
        return content
    if isinstance(content, bytearray):
        return bytes(content)
    if isinstance(content, str):
        return content.encode("utf-8", errors="replace")
    return b""

def _content_type(raw):
    headers = getattr(raw, "headers", None)
    if headers is None:
        return ""
    try:
        return headers.get("Content-Type") or ""
    except Exception:
        return ""

# a missing Content-Type counts as HTML (we try to parse it)
def _is_html(raw):
    media_type = _content_type(raw).split(";", 1)[0].strip().lower()
    return media_type == "" or media_type in HTML_CONTENT_TYPES

# the server's charset, else UTF-8; UTF-16/32 pages (byte-order mark) are left toBeautifulSoup
def _encoding_hint(raw, content):
    if content.startswith(_UTF16_32_BOMS):
        return None
    match = _CHARSET.search(_content_type(raw))
    return match.group(1) if match else "utf-8"