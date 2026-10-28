from configparser import ConfigParser
from argparse import ArgumentParser
import multiprocessing

from utils.server_registration import get_cache_server
from utils.config import Config
from crawler import Crawler
from crawl_extras import db


def main(config_file, restart):
    cparser = ConfigParser()
    cparser.read(config_file)
    config = Config(cparser)
    db.open_db(restart)
    config.cache_server = get_cache_server(config, restart)
    crawler = Crawler(config, restart)
    crawler.start()


if __name__ == "__main__":
    # macOS fix
    if "fork" in multiprocessing.get_all_start_methods():
        multiprocessing.set_start_method("fork")
    parser = ArgumentParser()
    parser.add_argument("--restart", action="store_true", default=False)
    parser.add_argument("--config_file", type=str, default="config.ini")
    args = parser.parse_args()
    main(args.config_file, args.restart)
