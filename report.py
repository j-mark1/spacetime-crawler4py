'''
Reports answers from crawl_stats.db - pages per label, longest page,
50 most common words, and low-outlier cutoff for low info pages.
'''

import sqlite3
import sys
from pathlib import Path

from crawl_extras.db import DB_PATH

# opens the database read-only, so it's safe to run while the crawler is running
def main(path=DB_PATH):
    if not Path(path).exists():
        sys.exit(f"No {path} yet; run the crawler first.")
    try:
        conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        labels = conn.execute("SELECT label, COUNT(*) FROM pages GROUP BY label ORDER BY COUNT(*) DESC").fetchall()
    except sqlite3.Error as error:
        sys.exit(f"Can't read {path}: {error}")

    print("Pages checked:", sum(count for _, count in labels))
    for label, count in labels:
        print(f"  {label}: {count}")

    longest = conn.execute(
        "SELECT url, word_count FROM pages WHERE label = 'OK' ORDER BY word_count DESC, url LIMIT 1").fetchone()
    print("\nLongest page:", f"{longest[0]} ({longest[1]} words)" if longest else "none yet")

    print("\n50 most common words:")
    words = conn.execute("SELECT word, count FROM words ORDER BY count DESC, word LIMIT 50")
    for rank, (word, count) in enumerate(words, start=1):
        print(f"{rank}. {word}, {count}")

    # Tukey's rule on a log scale (word counts are lopsided): below Q1 / (Q3/Q1)^1.5 is a low outlier
    counts = sorted(n for (n,) in conn.execute("SELECT word_count FROM pages WHERE label IN ('THIN', 'OK')"))
    if counts:
        q1, q3 = max(counts[len(counts) // 4], 1), max(counts[3 * len(counts) // 4], 1)
        print(f"\nLow outliers: pages under {q1 * (q1 / q3) ** 1.5:.0f} words (Q1 = {q1}, Q3 = {q3})")

    print("\nThinnest pages:")
    thin = conn.execute(
        "SELECT url, word_count FROM pages WHERE label IN ('THIN', 'OK') ORDER BY word_count, url LIMIT 20")
    for url, word_count in thin:
        print(f"  {word_count}\t{url}")
    conn.close()

if __name__ == "__main__":
    main()