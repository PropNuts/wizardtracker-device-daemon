import threading
import time
import signal
import sys
import logging
import coloredlogs

from .api.server import ApiServer
from .tracker.controller import TrackerController
from .datastream.server import DataStreamServer


LOGGER = logging.getLogger(__name__)


class DaemonRunner:
    def __init__(self):
        self._datastream_server = DataStreamServer()
        self._tracker = TrackerController(self._datastream_server)
        self._api_server = ApiServer(self._tracker)

        self._tracker_thread = threading.Thread(target=self._tracker.start)
        self._api_thread = threading.Thread(target=self._api_server.start)
        self._datastream_thread = threading.Thread(
            target=self._datastream_server.start
        )

    def _exit_handler(self, signum, frame):
        LOGGER.info('Stopping threads...')

        LOGGER.debug('Waiting for tracker thread...')
        self._tracker.stop()
        self._tracker_thread.join()

        LOGGER.debug('Waiting for API server thread...')
        self._api_server.stop()
        self._api_thread.join()

        LOGGER.debug('Waiting for data stream server thread...')
        self._datastream_server.stop()
        self._datastream_thread.join()

        LOGGER.info('Bye!')
        sys.exit(0)

    def start(self):
        coloredlogs.install(
            level=logging.DEBUG,
            fmt='[%(name)s] %(levelname)s %(message)s')
        signal.signal(signal.SIGINT, self._exit_handler)

        LOGGER.info('Starting threads...')

        self._datastream_thread.start()
        self._tracker_thread.start()
        self._api_thread.start()

        while True:
            time.sleep(1)
