import re
import sqlite3
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urldefrag, urljoin

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

    # Ignore all sites that do not return status 200. Also ignore sites where content cannot be downloaded or where there is no content.
    # NOTE: Crawler already traverses through redirect to retrieve redirected content, no need to check 300s status codes
    if (resp.status != 200 or not resp.raw_response or not resp.raw_response.content):
        return list()
    
    # Store current downloaded page (already confirmed by is_valid to be valid) into db.
    # Moved to this spot to consider redirected urls and ensure that the actual page of a redirected url is being stored rather than just all urls before redirect.
    # How? resp.raw_response.url is used to consider only redirected url (url that is actually retrieved) if redirect occurs.
    # As a result, only the actual page's url is processed and stored in db.
    parsed = urlparse(resp.raw_response.url)
    add_unique_page(parsed.scheme, parsed.hostname, resp.raw_response.url)

    next_links = []

    soup = BeautifulSoup(resp.raw_response.content, "lxml")

    # Retrieve all anchor link tags and hrefs
    all_anchors = soup.find_all("a")
    for anchor in all_anchors:
        anchor_url = anchor.get("href")

        if not isinstance(anchor_url, str):
            continue

        # Ensure url is absolute
        absolute_url = urljoin(resp.url, anchor_url)

        # Defragment link before appending
        defragmented_url = urldefrag(absolute_url)[0]

        next_links.append(defragmented_url)
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
            return True
        return False

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def tokenizer():
    #tokenize information
    pass

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


