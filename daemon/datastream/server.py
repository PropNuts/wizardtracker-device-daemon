import logging
import socket
import queue


LOGGER = logging.getLogger(__name__)


class DataStreamServer:
    HOST = '127.0.0.1'
    PORT = 3092

    def __init__(self):
        self._should_exit = False

        self._sock = None
        self._client_socks = []

        self._data_queue = queue.Queue()

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self._sock.bind((self.HOST, self.PORT))
        self._sock.listen()

        LOGGER.info('Listening on %s:%d...', self.HOST, self.PORT)
        self._loop()

    def stop(self):
        LOGGER.info('Shutting down...')
        self._should_exit = True
        self._sock.close()

    def queue_data(self, data):
        self._data_queue.put(data)

    def _loop(self):
        while not self._should_exit:
            try:
                (client_sock, address) = self._sock.accept()
                LOGGER.info('Accepted connection from %s.', address[0])

                self._sock.listen()
                self._client_socks.append(client_sock)
            except BlockingIOError:
                pass

            while not self._data_queue.empty():
                try:
                    data = self._data_queue.get()
                    data = [str(d) for d in data]
                    data = '{}\r\n'.format(' '.join(data)).encode()

                    for sock in self._client_socks:
                        try:
                            sock.sendall(data)
                        except ConnectionAbortedError:
                            LOGGER.info('%s disconnected, pruning...',
                                sock.getsockname()[0])
                            self._prune_socket(sock)
                except queue.Empty:
                    LOGGER.debug('Data queue is empty.')

    def _prune_socket(self, sock):
        self._client_socks.remove(sock)
