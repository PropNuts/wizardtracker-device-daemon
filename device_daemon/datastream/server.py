import json
import logging
import queue
import redis

LOGGER = logging.getLogger(__name__)


class DataStreamServer:
    def __init__(self):
        self._should_exit = False
        self._data_queue = queue.Queue()
        self._redis = None

    def start(self):
        LOGGER.info('Starting up...')

        self._redis = redis.StrictRedis(
            socket_connect_timeout=1,
            socket_timeout=1
        )

        self._wait_for_redis_connection()
        self._loop()

    def stop(self):
        LOGGER.info('Shutting down...')
        self._should_exit = True

    def queue_data(self, data):
        self._data_queue.put(data)

    def _wait_for_redis_connection(self):
        """
        blocks until a connection to Redis is established
        """
        connected = False
        while not connected and not self._should_exit:
            try:
                LOGGER.info('Testing Redis connection...')
                pong = self._redis.ping()
                if pong:
                    LOGGER.info('Connected to Redis successfully!')
                    connected = True
            except redis.exceptions.ConnectionError:
                LOGGER.error('Connection to Redis failed. Trying again...')

    def _loop(self):
        while not self._should_exit:
            while not self._data_queue.empty():
                try:
                    data = self._data_queue.get()
                    data_json = json.dumps(data)

                    self._redis.publish('rssiRaw', data_json)
                except queue.Empty:
                    LOGGER.debug('Data queue is empty.')
                except redis.exceptions.ConnectionError:
                    LOGGER.error('Lost connection to Redis. Trying to \
                        reconnect...')
                    self._wait_for_redis_connection()
