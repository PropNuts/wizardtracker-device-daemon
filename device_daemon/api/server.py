import threading
import logging

from wsgiref.simple_server import WSGIRequestHandler, make_server
from .app import app


LOGGER = logging.getLogger(__name__)


class QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        LOGGER.debug('%s {}'.format(format), self.client_address[0], *args)

class ApiServer:
    HOST = '127.0.0.1'
    PORT = 5000

    def __init__(self, tracker):
        self._httpd = None
        self._lock = threading.Lock()
        self._tracker = tracker

    def start(self):
        self._lock.acquire(True)

        app.tracker = self._tracker
        self._httpd = make_server(self.HOST, self.PORT, app,
            handler_class=QuietWSGIRequestHandler)
        LOGGER.info('Listening on %s:%d...', self.HOST, self.PORT)

        self._lock.release()
        self._httpd.serve_forever()

    def stop(self):
        self._lock.acquire(True)
        LOGGER.info('Shutting down...')
        self._httpd.shutdown()
        self._lock.release()
