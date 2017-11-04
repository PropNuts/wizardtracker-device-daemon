import threading
import logging

from wsgiref.simple_server import WSGIRequestHandler, make_server
from .app import app


LOGGER = logging.getLogger(__name__)


class QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        LOGGER.debug('%s {}'.format(format), self.client_address[0], *args)

class ApiServer:
    def __init__(self, tracker, host, port):
        self._host = host
        self._port = port

        self._httpd = None
        self._lock = threading.Lock()
        self._tracker = tracker

    def start(self):
        self._lock.acquire(True)

        app.tracker = self._tracker
        self._httpd = make_server(self._host, self._port, app,
            handler_class=QuietWSGIRequestHandler)
        LOGGER.info('Listening on %s:%d...', self._host, self._port)

        self._lock.release()
        self._httpd.serve_forever()

    def stop(self):
        self._lock.acquire(True)
        LOGGER.info('Shutting down...')
        self._httpd.shutdown()
        self._lock.release()
