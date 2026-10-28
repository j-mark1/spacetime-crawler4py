import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urldefrag, urljoin, parse_qs
from crawl_extras import page_stats
from crawl_extras.scope import in_allowed_domains

def scraper(url, resp):
    if not page_stats.process_page(url, resp):
        return []
    links = extract_next_links(url, resp)
    return [link for link in links if is_crawlable(link)]

# a malformed url skips instead of crashing the worker
def is_crawlable(url):
    try:
        return is_valid(url) and not is_trap_url(url)
    except ValueError:
        return False

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

    next_links = []

    soup = BeautifulSoup(resp.raw_response.content, "lxml")

    # Retrieve all anchor link tags and hrefs
    all_anchors = soup.find_all("a")
    for anchor in all_anchors:
        anchor_url = anchor.get("href")

        if not isinstance(anchor_url, str):
            continue

        anchor_url = anchor_url.strip() # to ignore spaces

        try:
            # Ensure url is absolute (relative to page's real url)
            absolute_url = urljoin(resp.raw_response.url, anchor_url)

            # Defragment link before appending
            defragmented_url = urldefrag(absolute_url)[0]

            next_links.append(defragmented_url)
        except ValueError:
            # Ignore malformed urls
            continue

    return next_links

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        # ASCII urls only
        if not in_allowed_domains(url) or not url.isascii():
            return False

        allowed_domains = ["ics.uci.edu", "cs.uci.edu", "informatics.uci.edu", "stat.uci.edu"]
        parsed = urlparse(url)

        if parsed.scheme not in set(["http", "https"]):
            return False

        # Check that the domains in the list of allowed domains are the domain itself of the url or a subdomain
        valid_domain = False
        for domain in allowed_domains:
            if parsed.hostname and (parsed.hostname == domain or parsed.hostname.endswith("." + domain)):
                valid_domain = True
        if not valid_domain:
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz"
            + r"|cpp|cc|c|h|txt|dev|admin|ppsx|pps|bib|apk|sql|nb|m|img)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def is_trap_url(url):
    parsed = urlparse(url)

    # Skip paths that are way too long
    if (len(parsed.path.split('/')) > 6):
        return True
    # Block non-standard ports (allow only None, 80, 443)
    if parsed.port and parsed.port not in (80, 443):
        return True

    query_params = parse_qs(parsed.query)
    blacklisted_queries = ["do", "idx", "C", "O", "MA", "SA", "skin"]

    # Avoid duplicate params
    if any(len(params) > 1 for params in query_params.values()):
        return True

    # Avoid params that could lead to infinite traps
    for blacklisted_query in blacklisted_queries:
        if blacklisted_query in query_params.keys():
            return True

    return False
    
