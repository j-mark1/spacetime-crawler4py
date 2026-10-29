'''
Saves each page's label & word count, adds word totals for 50 most common words for valid pages,
and stops near-duplicate pages (simhash) from adding words or links
'''

import logging
from collections import Counter

from crawl_extras import db, page_check, simhash, text

# fingerprints of every saved OK page, loaded from the db on first use; only touched inside db.transaction()
_fingerprints = None

# returns True if the page's links should be followed.
# Never raises: an exception here would stop the worker thread.
def process_page(url, resp):
    try:
        check = page_check.classify(url, resp)
        is_duplicate = check.label != page_check.NOT_200 and _record(check) # is duplicate and 200
        if check.soup is not None:
            text.free_html(check.soup)  # nothing uses the parsed page after this
        return check.follow_links and not is_duplicate
    except Exception:
        logging.getLogger(__name__).exception(f"Could not check {url}")
        return True

# one row per page (http/https, #fragment and a trailing "/" don't matter). A page's
# words are added only the first time it's saved, so nothing is counted twice.
# An OK page near an earlier one is saved as DUPLICATE with no words. Returns True for those.
# Checking and saving the fingerprint in one transaction keeps two threads from both missing a copy.
def _record(check):
    global _fingerprints
    is_ok = check.label == page_check.OK
    with db.transaction() as conn:
        if _fingerprints is None:
            _fingerprints = [int(row[0], 16) for row in conn.execute("SELECT fingerprint FROM fingerprints")]
        # if okay and any fingerprint is near a seen fingerprent
        is_duplicate = is_ok and any(
            simhash.is_near_duplicate(check.fingerprint, seen) for seen in _fingerprints)
        label = page_check.DUPLICATE if is_duplicate else check.label

        is_new = conn.execute(
            "INSERT OR IGNORE INTO pages VALUES (?, ?, ?, ?)",
            (check.page_key, check.url, label, len(check.tokens))).rowcount == 1
        if is_new and is_ok and not is_duplicate:
            counts = Counter(token for token in check.tokens if text.is_countable(token))
            for word, count in counts.items():
                conn.execute("INSERT OR IGNORE INTO words VALUES (?, 0)", (word,))
                conn.execute("UPDATE words SET count = count + ? WHERE word = ?", (count, word))
            conn.execute("INSERT INTO fingerprints VALUES (?)", (f"{check.fingerprint:016x}",))
            _fingerprints.append(check.fingerprint)  # after the inserts, so a failed save isn't remembered
    return is_duplicate
