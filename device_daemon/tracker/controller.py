import logging
import threading
import time
import enum

import serial
import serial.tools.list_ports

from ..utils.cycletimer import CycleTimer


LOGGER = logging.getLogger(__name__)


@enum.unique
class TrackerState(enum.Enum):
    DISCONNECTED = 1
    WAITING_FOR_FIRST_DATA = 2
    WAITING_FOR_STATUS = 3
    READY = 4


class TrackerController:
    BAUD_RATE = 250000

    def __init__(self, datastream):
        self._should_stop = False
        self._control_lock = threading.RLock()

        self._state = TrackerState(TrackerState.DISCONNECTED)

        self._datastream = datastream

        self._serial = serial.Serial()
        self._serial.baudrate = self.BAUD_RATE

        self._read_hz_timer = CycleTimer()

        self.receiver_count = None
        self.raw_mode = None
        self.frequencies = None
        self.voltage = None
        self.temperature = None
        self.rssi = None

    def start(self):
        LOGGER.info('Starting up...')
        self._loop()

        LOGGER.info('Shutting down...')
        if self._serial.is_open:
            self._serial.close()

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
                self._serial.timeout = 1
                self._serial.open()
                self._read_hz_timer.reset()
            except serial.SerialException as err:
                LOGGER.error('Failed to connect device (%s): (%s).', port, err)
                return False

            LOGGER.info('Connected to device (%s).', port)

            self._state = TrackerState.WAITING_FOR_FIRST_DATA
            LOGGER.info('Awaiting first data from device...')

            return True

    def disconnect(self):
        with self._control_lock:
            if not self._serial.is_open:
                return True

            self._serial.close()
            self._state = TrackerState(TrackerState.DISCONNECTED)

            LOGGER.info('Disconnected from device.')
            return True

    def set_frequency(self, receiver_id, frequency):
        with self._control_lock:
            if not self.is_ready
                return False

            self._write_serial_command('f', receiver_id, frequency)
            self.frequencies[receiver_id] = frequency

            return True

    def get_ports(self):
        ports = serial.tools.list_ports.comports()
        return ports

    def _loop(self):
        while not self._should_stop:
            with self._control_lock:
                self._parse_serial()

    def _parse_serial(self):
        if self._serial.is_open:
            line = self._serial.readline()
            if not line:
                return

            command, args = TrackerController._decode_serial_command(line)
            if self._state == TrackerState.WAITING_FOR_FIRST_DATA:
                self._parse_serial_waiting_for_first_data(command, args)
            elif self._state == TrackerState.WAITING_FOR_STATUS:
                self._parse_serial_waiting_for_status(command, args)
            elif self._state == TrackerState.READY:
                self._parse_serial_ready(command, args)

            self._tick_read_hz_timer()

    def _parse_serial_waiting_for_first_data(self, command, args):
        LOGGER.info('First data received.')

        self._state = TrackerState.WAITING_FOR_STATUS
        self._write_serial_command('?')
        LOGGER.info('Awaiting device status...')

    def _parse_serial_waiting_for_status(self, command, args):
        if command != '?':
            return

        self.raw_mode = int(args[-1]) == 1
        self.receiver_count = int(args[0])
        self.frequencies = [
            int(f) for f in args[1:self.receiver_count + 1]
        ]

        LOGGER.info('Device status received.')
        LOGGER.info('- Receivers: %d', self.receiver_count)
        LOGGER.info('- Raw Mode: %s', 'ON' if self.raw_mode else 'OFF')
        LOGGER.info('- Frequencies: %s', ', '.join(
            [str(f) for f in self.frequencies]))

        self._state = TrackerState.READY
        LOGGER.info('Device ready!')

    def _parse_serial_ready(self, command, args):
        if command == 'r':
            timestamp = time.clock()
            readings = [int(r) for r in args]
            queue_data = [timestamp] + readings

            self._datastream.queue_data(queue_data)
            self.rssi = tuple(readings)
            #LOGGER.debug('RSSI: %s', readings)
        elif command == 'v':
            self.voltage = float(args[0])
            #LOGGER.debug('Voltage: %sV', self.voltage)
        elif command == 't':
            self.temperature = float(args[0])
            #LOGGER.debug('Temperature: %sC', self.temperature)

    def _write_serial_command(self, command, *args):
        encoded_command = TrackerController._encode_serial_command(
            command, *args)

        self._serial.write(encoded_command)
        self._serial.flush()

    def _tick_read_hz_timer(self):
        self._read_hz_timer.tick()
        if self._read_hz_timer.time_since_reset >= 15:
            hz = self._read_hz_timer.hz
            #LOGGER.debug('RSSI Rate: %dHz (%.3fs accuracy)', hz, 1 / hz)
            self._read_hz_timer.reset()

    @staticmethod
    def _decode_serial_command(line):
        line = line.decode('ascii').strip()
        tokens = line.split(' ')
        command = tokens[0]
        args = tuple(tokens[1:])

        return command, args

    @staticmethod
    def _encode_serial_command(command, *args):
        command_string = None
        if args:
            args = [str(a) for a in args]
            command_string = '{} {}\n'.format(command, ' '.join(args))
        else:
            command_string = '{}\n'.format(command)

        return command_string.encode('ascii')

    @property
    def is_connected(self):
        return self._serial.is_open

    @property
    def is_ready(self):
        return self._state == TrackerState.READY

    @property
    def hz(self):
        return self._read_hz_timer.hz
