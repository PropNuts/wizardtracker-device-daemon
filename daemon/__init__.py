import threading
import time
import signal
import sys
import logging
import coloredlogs

from .api.server import ApiServer
from .tracker.controller import TrackerController


LOGGER = logging.getLogger(__name__)


def main():
    def exit_handler(signum, frame):
        LOGGER.info('Stopping threads...')

        LOGGER.debug('Waiting for tracker thread...')
        tracker.stop()
        tracker_thread.join()
        LOGGER.debug('Waiting for API thread...')
        api_server.stop()
        server_thread.join()

        LOGGER.info('Bye!')
        sys.exit(0)

    tracker = TrackerController()
    api_server = ApiServer()

    coloredlogs.install(
        level=logging.DEBUG,
        fmt='[%(name)s] %(levelname)s %(message)s')
    signal.signal(signal.SIGINT, exit_handler)

    LOGGER.info('Starting threads...')
    tracker_thread = threading.Thread(target=tracker.loop)
    server_thread = threading.Thread(target=api_server.start, args=(tracker,))

    tracker_thread.start()
    server_thread.start()

    while True:
        time.sleep(1)
