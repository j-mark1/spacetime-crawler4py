import re
import sqlite3
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urldefrag

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    # Ignore all sites that do not return status 200
    if (resp.status != 200):
        return list()

    next_links = []

    soup = BeautifulSoup(resp.raw_response.content, "lxml")

    # Retrieve all anchor link tags and hrefs
    all_anchors = soup.find_all("a")
    for anchor in all_anchors:
        url = anchor.get("href")

        # Defragment link before appending
        next_links.append(urldefrag(url)[0])

    return next_links

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        allowed_domains = ["ics.uci.edu", "cs.uci.edu", "informatics.uci.edu", "stat.uci.edu"]
        parsed = urlparse(url)

        if parsed.scheme not in set(["http", "https"]):
            return False

        # Check that the domains in the list of allowed domains are the domain itself of the url or a subdomain
        valid_domain = False
        for domain in allowed_domains:
            if parsed.hostname == domain or parsed.hostname.endswith("." + domain):
                valid_domain = True
        if not valid_domain:
            return False

        if not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            add_unique_page(parsed.scheme, parsed.hostname, url)
            return True
        return False

    except TypeError:
        print ("TypeError for ", parsed)
        raise

# Store unique pages (url, subdomain, and frequency count) in a sqllite database and increment count if the url already exists
def add_unique_page(scheme, hostname, url):
    subdomain = f"{scheme.lower()}://{hostname.lower()}"

    conn = sqlite3.connect("unique_pages.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unique_pages (
            url TEXT PRIMARY KEY,
            subdomain TEXT,
            count INTEGER DEFAULT 0
        )
    """)
    conn.commit()

    cursor.execute("""
        INSERT INTO unique_pages (url, subdomain, count) 
        VALUES (?, ?, 1)
        ON CONFLICT(url) DO UPDATE SET count = count + 1
    """, (url, subdomain,))
    conn.commit()

    conn.close()