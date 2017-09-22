import logging
import sqlite3
import time
import threading


LOGGER = logging.getLogger(__name__)


class DatabaseWriter:
    SYNC_INTERVAL = 5

    def __init__(self):
        self._conn = None
        self._round_id = None
        self._last_sync_time = 0

    def open(self):
        LOGGER.info('Opening database...')
        self._conn = sqlite3.connect('tracker.db', check_same_thread=False)
        self._init_db()
        self._last_sync_time = time.clock()

    def close(self):
        LOGGER.info('Closing database...')
        self._conn.commit()

    def prepare_round(self, round_id):
        self._round_id = round_id

        if self._round_exists(round_id):
            LOGGER.warning(
                'Round %d already has data. Clearing...',
                round_id)
            self._conn.execute(
                '''
                DELETE FROM rssi WHERE round_id = (?)
                ''',
                (round_id,)
            )

    def log(self, timestamp, readings):
        self._conn.executemany(
            'INSERT INTO rssi VALUES (?, ?, ?, ?)',
            [
                (self._round_id, i, r, timestamp)
                for i, r in enumerate(readings)
            ]
        )

    def sync(self):
        if time.clock() >= self._last_sync_time + self.SYNC_INTERVAL:
            if self._conn.in_transaction:
                LOGGER.debug('Syncing database...')
                self._conn.commit()

            self._last_sync_time = time.clock()

    def _round_exists(self, round_id):
        cur = self._conn.execute(
            '''
            SELECT EXISTS(
                SELECT 1 FROM rssi WHERE round_id = (?)
            )
            ''',
            (round_id,)
        )

        return cur.fetchone()[0] == 1

    def _init_db(self):
        self._conn.execute('''\
            CREATE TABLE IF NOT EXISTS rssi (
                round_id INTEGER,
                rx_id INTEGER,
                rssi INTEGER,
                timestamp DOUBLE
            )
        ''')

        self._conn.execute('''
            CREATE INDEX IF NOT EXISTS round_rx_ids
            ON rssi (round_id, rx_id)
        ''')

        self._conn.execute('''
            CREATE INDEX IF NOT EXISTS round_timestamp
            ON rssi (round_id, timestamp)
        ''')

        self._conn.commit()
