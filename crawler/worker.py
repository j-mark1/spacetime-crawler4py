from threading import Thread

from inspect import getsource
from utils.download import download
from utils import get_logger
import scraper
import time
import sqlite3
from urllib.parse import urlparse


class Worker(Thread):
    def __init__(self, worker_id, config, frontier):
        self.logger = get_logger(f"Worker-{worker_id}", "Worker")
        self.config = config
        self.frontier = frontier
        # basic check for requests in scraper
        assert {getsource(scraper).find(req) for req in {"from requests import", "import requests"}} == {-1}, "Do not use requests in scraper.py"
        assert {getsource(scraper).find(req) for req in {"from urllib.request import", "import urllib.request"}} == {-1}, "Do not use urllib.request in scraper.py"
        super().__init__(daemon=True)

        # Initialize connection to database
        self.conn = sqlite3.connect("unique_pages.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA journal_mode=WAL;")
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS unique_pages (
                url TEXT PRIMARY KEY,
                subdomain TEXT
            )
        """)
        self.conn.commit()
        
    def run(self):
        while True:
            tbd_url = self.frontier.get_tbd_url()
            if not tbd_url:
                self.logger.info("Frontier is empty. Stopping Crawler.")
                self.conn.close()
                break
            resp = download(tbd_url, self.config, self.logger)
            self.logger.info(
                f"Downloaded {tbd_url}, status <{resp.status}>, "
                f"using cache {self.config.cache_server}.")

            # Ignore all sites that do not return status 200 and already exist in db.
            # Also ignore sites where content cannot be downloaded or where there is no content.
            # NOTE: Crawler already traverses through redirect to retrieve redirected content, no need to check 300s status codes
            if (resp.status == 200 and resp.raw_response and resp.raw_response.content):
                # Check if url already exists in the db
                self.cursor.execute("""
                    SELECT EXISTS(SELECT 1 FROM unique_pages WHERE url = ?);
                """, (resp.raw_response.url, ))
                exists = self.cursor.fetchone()[0]

                if (not exists):
                    # Store current downloaded page (already confirmed by is_valid to be valid) into db.
                    # Moved to this spot to consider redirected urls and ensure that the actual page of a redirected url is being stored rather than just all urls before redirect.
                    # How? resp.raw_response.url is used to consider only redirected url (url that is actually retrieved) if redirect occurs.
                    # As a result, only the actual page's url is processed and stored in db.
                    parsed = urlparse(resp.raw_response.url)
                    self.add_unique_page(parsed.scheme, parsed.hostname, resp.raw_response.url)

                    scraped_urls = scraper.scraper(tbd_url, resp)
                    for scraped_url in scraped_urls:
                        self.frontier.add_url(scraped_url)
            self.frontier.mark_url_complete(tbd_url)
            time.sleep(self.config.time_delay)
    
    # Store unique pages (url, subdomain, and frequency count) in a sqllite database and increment count if the url already exists
    def add_unique_page(self, scheme, hostname, url):
        subdomain = f"{scheme.lower()}://{hostname.lower()}"

        self.cursor.execute("""
            INSERT INTO unique_pages (url, subdomain) 
            VALUES (?, ?)
        """, (url, subdomain,))
        self.conn.commit()
