'''
Scope of the four domains that the assignment allows us to crawl.
'''

import re
from urllib.parse import urlparse

ALLOWED_DOMAINS = ("ics.uci.edu", "cs.uci.edu", "informatics.uci.edu", "stat.uci.edu")

_HOSTNAME = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*")
# backslashes, spaces and control characters: "http://evil.com\.ics.uci.edu/" looks
# like ics.uci.edu to urlparse, but requests sends it to evil.com
_UNSAFE_CHARS = re.compile(r"[\x00-\x20\x7f\\]")

# true if the url's host is an allowed domain or a subdomain of one
# (matched on a "." boundary: ics.uci.edu is not a subdomain of cs.uci.edu)
def in_allowed_domains(url):
    if not isinstance(url, str) or _UNSAFE_CHARS.search(url):
        return False
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        parsed.port  # raises ValueError for a bad port
    except ValueError:
        return False
    if not host:
        return False
    host = host.rstrip(".")
    if not _HOSTNAME.fullmatch(host):
        return False
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)