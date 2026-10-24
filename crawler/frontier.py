import sqlite3
from threading import Thread, RLock, Lock
import threading
from collections import deque
from queue import Queue, Empty
from enum import Enum
import time
from urllib.parse import urlparse

from utils import get_logger, get_urlhash, host_alias, normalize
from scraper import is_valid


class Domain():
    def __init__(self, domain: str):
        # Like https://www.ics.uci.edu
        self.domain = (urlparse(domain).hostname or "").removeprefix("www.")
        self.busy = False
        
        # use a dequeue for bfs since it isnt hurt by traps as much. 
        # also important pages appear closer relative to seed urls
        # Can also hold depth limit later to avoid traps
        self.queue = deque() 
        self.last_access = 0.0 # In seconds


class Frontier(object):
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config

        # 1 frontier per domain (ics, cs, informatics, stat)
        self.domain_frontiers = [Domain(url) for url in config.seed_urls] 
        self.domain_frontiers = self.domain_frontiers[::-1] # reverse because we want ics frontier last
                                                            # sites like https://informatics.ics.uci.edu/ and https://informatics.uci.edu/ are the same
 
        self.next_frontier = 0 # Holds which frontier to look at next (rotates around in a cycle)
        self.in_flight = 0 # non 0 if a worker can add urls to the frontier
                           # add url increments, mark complete decrements
        self.lock = threading.Lock() # Lock for the entire frontier object

        # SQL Connection setup
        self.conn = sqlite3.connect("unique_pages.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA journal_mode=WAL;")
        self.conn.commit()

        # Save file is SQLite table
        # workers take turns and each write is saved right away
        self.save = sqlite3.connect(self.config.save_file, check_same_thread=False, isolation_level=None)
        self.save.execute("CREATE TABLE IF NOT EXISTS frontier (urlhash TEXT PRIMARY KEY, url TEXT, completed INTEGER)")

        if restart:
            self.save.execute("DELETE FROM frontier")

            # Delete old table
            self.cursor.execute("""
                DROP TABLE IF EXISTS unique_pages;     
            """)
            self.conn.commit()


            for url in self.config.seed_urls:
                self.add_url(url)
        else:
            # Set the frontier state with contents of save file.
            self._parse_save_file() # also restores the urls to the queues
            if self.save.execute("SELECT COUNT(*) FROM frontier").fetchone()[0] == 0:
                for url in self.config.seed_urls:
                    self.add_url(url)

        # database stuff after drop table. MANAGED BY FRONTIER BECAUSE FRONTIER HAS THE LOCK
        # FRONTIER ENFORCES CONCURENCY
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS unique_pages (
                url TEXT PRIMARY KEY,
                subdomain TEXT,
                hash TEXT
            )
        """)
        self.conn.commit()

    def _parse_save_file(self):
        total_count = self.save.execute("SELECT COUNT(*) FROM frontier").fetchone()[0]
        pending = []
        not_added_count = 0
        # Restore valid urls that were not visited, in the order they were found (rowid = insert order, better for breadth)
        for url, completed in self.save.execute("SELECT url, completed FROM frontier ORDER BY rowid"):
            if not completed and is_valid(url):
                pending.append(url)
            else:
                not_added_count += 1

        for url in pending:
            self._add_url_to_domain_queue(url) # url already normalized

        self.logger.info(
            f"Resumed {len(pending)} pending urls from {total_count} "
            f"total urls discovered. "
            f"{not_added_count} urls not added"
        )

    def get_tbd_url(self):
        """
        Always loop until success
            get lock
            for each frontier try to get a url
            if fail release lock and wait for a bit to try again
        """
        n = len(self.domain_frontiers)
        while True:
            with self.lock:
                now = time.monotonic()
                soonest = None # earliest time any non-empty frontier becomes ready
                for i in range(n):
                    index = (self.next_frontier + i) % n
                    domain_frontier = self.domain_frontiers[index]
                    if not domain_frontier.queue or domain_frontier.busy: # if empty or busy, skip
                        continue
                    
                    ready_at = domain_frontier.last_access + self.config.time_delay
                    # If enough time has passed for politeness
                    if ready_at <= now:
                        domain_frontier.busy = True # Need this bc politeness is based on download, not get url
                        self.next_frontier = (index + 1) % n
                        self.in_flight += 1 # Add 1 since we may add more urls from this url that will be returned
                                            # Mark complete will decrement this counter

                        return_url = domain_frontier.queue.popleft()
                        self.logger.info(f"Popping {return_url} from frontier {self.domain_frontiers[index].domain}")
                        return return_url
                    # If not enough time pass, keep track of when to wake up
                    soonest = ready_at if soonest is None else min(soonest, ready_at)

                # If all queues are empty and no thread is processing a url
                if soonest is None and self.in_flight == 0:
                    return None

                wait_time = (soonest - now) if soonest is not None else self.config.time_delay
            # out of lock now
            log_str = f"Failed to obtain a lock. Waiting for {wait_time} seconds"
            self.logger.info(log_str)

            time.sleep(max(wait_time, 0.05)) # arbitrary min wait time, can be whatever


    def _route(self, url):
        """
        Finds longest matching host frontier
        """
        host = host_alias.canonical_host(urlparse(url).hostname or "")
        best = None # best domain frontier match
        for df in self.domain_frontiers:
            if host == df.domain or host.endswith("." + df.domain):
                if best is None or len(df.domain) > len(best.domain):
                    best = df
        return best

    # Only call this in add_url()
    def _add_url_to_domain_queue(self, url):
        frontier = self._route(url)
        if frontier is None:
            self.logger.info(f"No frontier for {url}. Not adding this url to a queue")
            return
        frontier.queue.append(url)
        # self.logger.info(f"Adding {url} to {domain_frontier.domain} frontier")
        

    def add_url(self, url):
        with self.lock:
            url = normalize(url)
            urlhash = get_urlhash(url)
            if self.save.execute("SELECT 1 FROM frontier WHERE urlhash = ?", (urlhash,)).fetchone() is None:
                self.save.execute("INSERT INTO frontier VALUES (?, ?, 0)", (urlhash, url))

                # Add to domain queue
                self._add_url_to_domain_queue(url)
    
    def mark_url_complete(self, url):
        with self.lock:
            urlhash = get_urlhash(url)
            # UPDATE changes 0 rows if the url was never saved
            if self.save.execute("UPDATE frontier SET completed = 1 WHERE urlhash = ?", (urlhash,)).rowcount == 0:
                # Should not happen
                self.logger.error(f"Completed url {url}, but have not seen it before.")
            self.in_flight -= 1

    def mark_url_failed(self, url):
        with self.lock:
            self.in_flight -= 1

    # Called by worker after download to release a domain
    # Otherwise might run into race conditions
    def release_domain(self, url):
        with self.lock:
            df = self._route(url)
            if df is not None:
                df.busy = False
                df.last_access = time.monotonic()

    # def url_exist_in_db(self, url):
    #     exists = False
    #     with self.lock:
    #         self.cursor.execute("""
    #             SELECT EXISTS(SELECT 1 FROM unique_pages WHERE url = ?);
    #         """, (url, ))
    #         exists = self.cursor.fetchone()[0]
    #     return exists

    def url_can_be_downloaded(self, url, hash):
        # Checks if url is in db and if hash exists
        seen = False
        with self.lock:
            self.cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM unique_pages WHERE url = ? OR hash = ?)",
                (url, hash))
            seen = self.cursor.fetchone()[0]
        return not seen

        return not url_exists and not hash_exists

    def add_unique_page_to_db(self, scheme, hostname, url, hash = ""):
        with self.lock:
            subdomain = f"{scheme.lower()}://{hostname.lower()}"

            self.cursor.execute("""
                INSERT INTO unique_pages (url, subdomain, hash) 
                VALUES (?, ?, ?)
            """, (url, subdomain, hash))
            self.conn.commit()

    def close_db(self):
        with self.lock:
            self.conn.close()