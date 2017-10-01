import threading
import time
import signal
import sys
import logging
import coloredlogs

from .api.server import ApiServer
from .tracker.controller import TrackerController


LOGGER = logging.getLogger(__name__)


class DaemonRunner:
    def __init__(self):
        self._tracker = TrackerController()
        self._api_server = ApiServer()

        self._tracker_thread = threading.Thread(target=self._tracker.loop)
        self._server_thread = threading.Thread(target=self._api_server.start,
            args=(self._tracker,))

    def _exit_handler(self, signum, frame):
        LOGGER.info('Stopping threads...')

        LOGGER.debug('Waiting for tracker thread...')
        self._tracker.stop()
        self._tracker_thread.join()

        LOGGER.debug('Waiting for API thread...')
        self._api_server.stop()
        self._server_thread.join()

        LOGGER.info('Bye!')
        sys.exit(0)

    def start(self):
        coloredlogs.install(
            level=logging.DEBUG,
            fmt='[%(name)s] %(levelname)s %(message)s')
        signal.signal(signal.SIGINT, self._exit_handler)

        LOGGER.info('Starting threads...')

        self._tracker_thread.start()
        self._server_thread.start()

        while True:
            time.sleep(1)
