from utils import get_logger
from crawler.frontier import Frontier
from crawler.worker import Worker

GREEN = "\033[32m"
RESET = "\033[0m"  

class Crawler(object):
    def __init__(self, config, restart, frontier_factory=Frontier, worker_factory=Worker):
        self.config = config
        self.logger = get_logger("CRAWLER")
        self.frontier = frontier_factory(config, restart) # Construct a frontier
        self.workers = list()
        self.worker_factory = worker_factory # Constructor for workers

    def start_async(self):
        # Construct N workers
        self.workers = [
            self.worker_factory(worker_id, self.config, self.frontier)
            for worker_id in range(self.config.threads_count)]
        # Start N workers
        for worker in self.workers:
            worker.start()
        

    def start(self):
        self.start_async()
        print(f"{GREEN}crawler/__init__.py::Crawler::start Started all workers{RESET}")
        self.join()
        print(f"{GREEN}crawler/__init__.py::Crawler::start Joined all workers{RESET}")

    def join(self):
        for worker in self.workers:
            worker.join()
