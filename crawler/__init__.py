from utils import get_logger
from crawler.frontier import Frontier
from crawler.worker import Worker

class Crawler(object):
    def __init__(self, config, restart, frontier_factory=Frontier, worker_factory=Worker):
        self.config = config
        self.logger = get_logger("CRAWLER")
        self.frontier = frontier_factory(config, restart)
        self.workers = list()
        self.worker_factory = worker_factory

    def start_async(self):
        self.workers = [
            self.worker_factory(worker_id, self.config, self.frontier)
            for worker_id in range(self.config.threads_count)]
        for worker in self.workers:
            worker.start()

    def start(self):
        self.start_async()
        self.join()

        #urls that failed (like when server goes down) are unfinished and needs to resume
        unfinished = self.frontier.save.execute("SELECT COUNT(*) FROM frontier WHERE completed = 0").fetchone()[0]
        if unfinished:
            self.logger.warning(f"{unfinished} urls failed and are still unfinished.")

    def join(self):
        for worker in self.workers:
            worker.join()
