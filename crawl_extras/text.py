'''
Turning a page into words with visible text extraction, tokenization, and stop words.
'''

import importlib.util
import os

from bs4 import BeautifulSoup
from bs4.element import PreformattedString

HTML_PARSER = "lxml" if importlib.util.find_spec("lxml") else "html.parser"
SPACE = 32
STOPWORDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stopwords.txt")
INVISIBLE_TAGS = frozenset(["script", "style", "noscript", "template"])
MIN_COUNTABLE_LENGTH = 2

# A-Z -> a-z, a-z and 0-9 unchanged, every other byte -> space (A1 rules)
def _build_translation_table():
    table = bytearray()
    for code in range(256):
        if ord("A") <= code <= ord("Z"):
            table.append(code - ord("A") + ord("a"))
        elif ord("a") <= code <= ord("z") or ord("0") <= code <= ord("9"):
            table.append(code)
        else:
            table.append(SPACE)
    return bytes(table)

TRANSLATION_TABLE = _build_translation_table()

# "Don't STOP, café!" -> ["don", "t", "stop", "caf"]
def tokenize(text):
    if not text:
        return []
    cleaned = text.encode("utf-8", errors="replace").translate(TRANSLATION_TABLE)
    return cleaned.decode("ascii").split()

# stop words go through the same tokenizer, so "don't" matches our tokens "don" and "t"
def load_stopwords(path=STOPWORDS_PATH):
    words = set()
    with open(path, encoding="utf-8") as file:
        for line in file:
            words.update(tokenize(line))
    return frozenset(words)

# allow for cases of can't, won't, and let's
STOPWORDS = load_stopwords() - {"can", "won", "let"}

# counts toward the top 50: 2+ characters, not a number, not a stop word
def is_countable(token):
    return (len(token) >= MIN_COUNTABLE_LENGTH
            and not token.isdigit()
            and token not in STOPWORDS)

# the encoding hint ("utf-8" or the server's charset) skips BeautifulSoup's slow guessing
def parse_html(content, encoding=None):
    return BeautifulSoup(content, HTML_PARSER, from_encoding=encoding)

# frees a parsed page now instead of at Python's next full garbage collection.
# soup.decompose() alone only wipes the top object, so detach and decompose each child first
def free_html(soup):
    children, soup.contents = soup.contents, []
    for child in children:
        child.parent = None
        child.decompose()
    soup.decompose()

# the text a reader sees: no comments or doctype, nothing inside script/style/noscript/template.
# Joined with spaces so "<li>Home</li><li>About</li>" doesn't become "HomeAbout"
def extract_visible_text(soup):
    pieces = []
    for string in soup.find_all(string=True):
        if isinstance(string, PreformattedString) or _inside_invisible_tag(string):
            continue
        pieces.append(string)
    return " ".join(pieces)

def _inside_invisible_tag(node):
    parent = node.parent
    while parent is not None:
        if parent.name in INVISIBLE_TAGS:
            return True
        parent = parent.parent
    return False

def page_title(soup):
    if soup.title is None:
        return ""
    return soup.title.get_text(" ", strip=True)