'''
Saves each page's label & word count, adds word totals for 50 most common words for valid pages
'''

import logging
from collections import Counter

from crawl_extras import db, page_check, text

# returns True if the page's links should be followed.
# Never raises: an exception here would stop the worker thread.
def process_page(url, resp):
    try:
        check = page_check.classify(url, resp)
        if check.label != page_check.NOT_200:
            _record(check)
        if check.soup is not None:
            text.free_html(check.soup)  # nothing uses the parsed page after this
        return check.follow_links
    except Exception:
        logging.getLogger(__name__).exception(f"Could not check {url}")
        return True

# one row per page (http/https, #fragment and a trailing "/" don't matter). A page's
# words are added only the first time it's saved, so nothing is counted twice.
def _record(check):
    is_ok = check.label == page_check.OK
    counts = Counter(token for token in check.tokens if text.is_countable(token)) if is_ok else {}
    with db.transaction() as conn:
        is_new = conn.execute(
            "INSERT OR IGNORE INTO pages VALUES (?, ?, ?, ?)",
            (check.page_key, check.url, check.label, len(check.tokens))).rowcount == 1
        if is_new:
            for word, count in counts.items():
                conn.execute("INSERT OR IGNORE INTO words VALUES (?, 0)", (word,))
                conn.execute("UPDATE words SET count = count + ? WHERE word = ?", (count, word))