from threading import Thread

from inspect import getsource
from utils.download import download
from utils import get_logger
import scraper
import time
from urllib.parse import urlparse
import hashlib


class Worker(Thread):
    def __init__(self, worker_id, config, frontier):
        self.logger = get_logger(f"Worker-{worker_id}", "Worker")
        self.config = config
        self.frontier = frontier
        # basic check for requests in scraper
        assert {getsource(scraper).find(req) for req in {"from requests import", "import requests"}} == {-1}, "Do not use requests in scraper.py"
        assert {getsource(scraper).find(req) for req in {"from urllib.request import", "import urllib.request"}} == {-1}, "Do not use urllib.request in scraper.py"
        super().__init__(daemon=True)

        
    def run(self):
        while True:
            
            tbd_url = self.frontier.get_tbd_url()
            if not tbd_url:
                self.logger.info("Frontier is empty. Stopping Crawler.")
                self.frontier.close_db()
                break

            start = time.monotonic()

            # Disgusting nested try just in case something goes wrong.
            # We need to nest try blocks bc python is stupid where finally doesnt catch excpetions
            # so if download raises but it isnt in the nested try it will propagate
            # if we use only one big try, we release domain after scraping which wastes lots of time
            try:
                # Try to download, release regardless
                try:
                    resp = download(tbd_url, self.config, self.logger)
                finally:
                    self.frontier.release_domain(tbd_url)

                self.logger.info(
                    f"Downloaded {tbd_url}, status <{resp.status}>, "
                    f"using cache {self.config.cache_server}.")
                if resp.status == 600:
                    raise ConnectionError(resp.error)
                # Ignore all sites that do not return status 200 and already exist in db.
                # Also ignore sites where content cannot be downloaded or where there is no content.
                # NOTE: Crawler already traverses through redirect to retrieve redirected content, no need to check 300s status codes
                if (resp.status == 200 and resp.raw_response and resp.raw_response.content):
                    # Store current downloaded page (already confirmed by is_valid to be valid) into db.
                    # Moved to this spot to consider redirected urls and ensure that the actual page of a redirected url is being stored rather than just all urls before redirect.
                    # How? resp.raw_response.url is used to consider only redirected url (url that is actually retrieved) if redirect occurs.
                    # As a result, only the actual page's url is processed and stored in db.
                    parsed = urlparse(resp.raw_response.url)

                    # Check if url can be downloaded
                    hashed = hashlib.sha256(resp.raw_response.content).hexdigest()
                    can_be_downloaded = self.frontier.url_can_be_downloaded(resp.raw_response.url, hashed)

                    # Check if url can be added to unique db, but based on just url
                    can_be_added = self.frontier.url_can_be_added(resp.raw_response.url)
                    if can_be_added:
                        self.frontier.add_unique_page_to_db(parsed.scheme, parsed.hostname, resp.raw_response.url, hashed)
                    if (can_be_downloaded):
                        scraped_urls = scraper.scraper(tbd_url, resp)
                        self.logger.info(f"Completed scaper.scraper() in {time.monotonic() - start} seconds")
                        for scraped_url in scraped_urls:
                            self.frontier.add_url(scraped_url) # unclean url. will be cleaned in this function
            except Exception:
                # the crawl keeps going, and the next resume tries the url again
                self.logger.exception(f"Error while crawling {tbd_url}, leaving it for the resume")
                self.frontier.mark_url_failed(tbd_url)
                continue
            self.frontier.mark_url_complete(tbd_url)
            self.logger.info(f"Worker loop iteration completed in {time.monotonic() - start} seconds")