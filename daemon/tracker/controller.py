import logging
import threading
import time

import serial
import serial.tools.list_ports

from .db import DatabaseWriter
from ..utils.cycletimer import CycleTimer


LOGGER = logging.getLogger(__name__)


class TrackerController:
    BAUD_RATE = 250000

    def __init__(self):
        self._should_stop = False
        self._control_lock = threading.RLock()

        self._serial = serial.Serial()
        self._serial.baudrate = self.BAUD_RATE

        self._db = DatabaseWriter()
        self._should_log = False
        self._current_round_id = None
        self._round_start_timestamp = None

        self._read_hz_timer = CycleTimer()

        self.voltage = None
        self.temperature = None

    def loop(self):
        LOGGER.info('Starting up...')

        self._db.open()
        self._loop()

        LOGGER.info('Shutting down...')
        if self._serial.is_open:
            self._serial.close()

        self._db.close()

    def stop(self):
        self._should_stop = True

    def connect(self, port):
        ports = self.get_ports()
        port_devices = [p.device for p in ports]
        if not port in port_devices:
            return False

        with self._control_lock:
            if self._serial.is_open:
                return False

            try:
                self._serial.port = port
                self._serial.timeout = 0
                self._serial.open()
                self._read_hz_timer.reset()
            except serial.SerialException as err:
                LOGGER.error('Failed to connect device (%s): (%s).', port, err)
                return False

            LOGGER.info('Connected to device (%s).', port)
            return True

    def disconnect(self):
        with self._control_lock:
            if not self._serial.is_open:
                return True

            self.stop_tracking()
            self._serial.close()

            LOGGER.info('Disconnected from device.')
            return True

    def start_tracking(self, round_id):
        with self._control_lock:
            if self._should_log or not self._serial.is_open:
                return False

            self._should_log = True
            self._current_round_id = round_id
            self._round_start_timestamp = time.clock()
            self._db.prepare_round(round_id)

            LOGGER.info('Started tracking for round %d.', round_id)
            return True

    def stop_tracking(self):
        with self._control_lock:
            self._should_log = False
            self._current_round_id = None

            LOGGER.info('Stopped tracking.')
            return True

    def set_frequency(self, receiver_id, frequency):
        with self._control_lock:
            if not self._serial.is_open:
                return False

            command = 'f {} {}'.format(receiver_id, frequency).encode('ascii')
            self._serial.write(command)

            return True

    def get_ports(self):
        ports = serial.tools.list_ports.comports()
        return ports

    def _loop(self):
        while not self._should_stop:
            with self._control_lock:
                self._parse_serial()

            self._db.sync()

    def _parse_serial(self):
        if self._serial.is_open:
            line = self._serial.readline()
            if not line:
                return

            line = line.decode('ascii').strip()
            tokens = line.split(' ')
            command = tokens[0]

            if command == 'r':
                if self._should_log:
                    timestamp = time.clock() - self._round_start_timestamp

                    readings = tokens[1:]
                    readings = [int(r) for r in readings]

                    self._db.log(timestamp, readings)
                    LOGGER.debug('RSSI: %s', readings)
            elif command == 'v':
                self.voltage = float(tokens[1])
                LOGGER.debug('Voltage: %sV', self.voltage)
            elif command == 't':
                self.temperature = float(tokens[1])
                LOGGER.debug('Temperature: %sC', self.temperature)

            self._read_hz_timer.tick()
            if self._read_hz_timer.time_since_reset >= 15:
                hz = self._read_hz_timer.hz
                LOGGER.debug('RSSI Rate: %dHz (%.3fs accuracy)', hz, 1 / hz)
                self._read_hz_timer.reset()

    @property
    def is_connected(self):
        return self._serial.is_open

    @property
    def hz(self):
        return self._read_hz_timer.hz
