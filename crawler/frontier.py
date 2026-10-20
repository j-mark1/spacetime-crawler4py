import os
import shelve

from threading import Thread, RLock, Lock
import threading
from collections import deque
from queue import Queue, Empty
from enum import Enum
import time
from urllib.parse import urlparse

from utils import get_logger, get_urlhash, normalize
from scraper import is_valid

# Globals for indicies



class Domain():
    def __init__(self, domain: str):
        # Like https://www.ics.uci.edu
        self.domain = (urlparse(domain).hostname or "").removeprefix("www.")
        
        # use a dequeue for bfs since it isnt hurt by traps as much. 
        # also important pages appear closer relative to seed urls
        # Can also hold depth limit later to avoid traps
        self.queue = deque() 
        self.last_access = 0.0 # In seconds


class Frontier(object):
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config
        self.count = 0

        # 1 frontier per domain (ics, cs, informatics, stat)
        self.domain_frontiers = [Domain(url) for url in config.seed_urls] 
        self.next_frontier = 0 # Holds which frontier to look at next (rotates around in a cycle)
        self.in_flight = 0 # non 0 if a worker can add urls to the frontier
                           # add url increments, mark complete decrements
        self.lock = threading.Lock() # Lock for the entire frontier object

        self.to_be_downloaded = list()


        # TODO deal with saves later
        if not os.path.exists(self.config.save_file) and not restart:
            # Save file does not exist, but request to load save.
            self.logger.info(
                f"Did not find save file {self.config.save_file}, "
                f"starting from seed.")
        elif os.path.exists(self.config.save_file) and restart:
            # Save file does exists, but request to start from seed.
            self.logger.info(
                f"Found save file {self.config.save_file}, deleting it.")
            os.remove(self.config.save_file)
        # Load existing save file, or create one if it does not exist.
        self.save = shelve.open(self.config.save_file)
        if restart:
            for url in self.config.seed_urls:
                self.add_url(url)
        else:
            # Set the frontier state with contents of save file.
            self._parse_save_file()
            if not self.save:
                for url in self.config.seed_urls:
                    self.add_url(url)

    def _parse_save_file(self):
        ''' This function can be overridden for alternate saving techniques. '''
        total_count = len(self.save)
        tbd_count = 0
        for url, completed in self.save.values():
            if not completed and is_valid(url):
                self.to_be_downloaded.append(url)
                tbd_count += 1
        self.logger.info(
            f"Found {tbd_count} urls to be downloaded from {total_count} "
            f"total urls discovered.")

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
                    if not domain_frontier.queue: # if empty
                        continue
                    ready_at = domain_frontier.last_access + self.config.time_delay
                    # If enough time has passed for politeness
                    if ready_at <= now:
                        domain_frontier.last_access = now
                        self.next_frontier = (index + 1) % n
                        self.in_flight += 1 # Add 1 since we may add more urls from this url that will be returned
                                            # Mark complete will decrement this counter
                        return domain_frontier.queue.popleft()
                    # If not enough time pass, keep track of when to wake up
                    soonest = ready_at if soonest is None else min(soonest, ready_at)

                # If all queues are empty and no thread is processing a url
                if soonest is None and self.in_flight == 0:
                    return None

                wait_time = (soonest - now) if soonest is not None else self.config.time_delay
            # out of lock
            self.logger.info(f"Failed to obtain a lock. Waiting for {wait_time} seconds")
            time.sleep(max(wait_time, 0.05)) # arbitrary min wait time, can be whatever




    def _add_url_to_domain_queue(self, url):
        host = urlparse(url).hostname or ""
        for domain_frontier in self.domain_frontiers:
            if host == domain_frontier.domain or host.endswith("." + domain_frontier.domain):
                self.logger.info(f"Adding {url} to {domain_frontier.domain} frontier")
                domain_frontier.queue.append(url)
                break
        

    def add_url(self, url):
        with self.lock:
            url = normalize(url)
            urlhash = get_urlhash(url)
            if urlhash not in self.save:
                self.save[urlhash] = (url, False)
                self.save.sync()

                # Add to domain queue
                self._add_url_to_domain_queue(url)
    
    def mark_url_complete(self, url):
        urlhash = get_urlhash(url)
        if urlhash not in self.save:
            # This should not happen.
            self.logger.error(
                f"Completed url {url}, but have not seen it before.")

        self.save[urlhash] = (url, True)
        self.save.sync()
