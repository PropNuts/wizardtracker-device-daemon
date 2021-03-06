import logging
import threading
import time
import enum

import serial
import serial.tools.list_ports

from ..utils.cycletimer import CycleTimer


LOGGER = logging.getLogger(__name__)


def _decode_serial_command(line):
    line = line.decode('ascii').strip()
    tokens = line.split(' ')
    command = tokens[0]
    args = tuple(tokens[1:])

    return command, args

def _encode_serial_command(command, *args):
    command_string = None
    if args:
        args = [str(a) for a in args]
        command_string = '{} {}\n'.format(command, ' '.join(args))
    else:
        command_string = '{}\n'.format(command)

    return command_string.encode('ascii')

class NonBlockingLineReader:
    def __init__(self):
        self._buffer = bytearray()

    def append_data(self, data):
        if not data:
            return

        self._buffer.extend(data)

    def read_line(self):
        end_index = self._buffer.find(b'\n')
        if end_index >= 0:
            found_line = bytes(self._buffer[:end_index + 1])
            del self._buffer[0:end_index + 1]
            return found_line

        return None

@enum.unique
class TrackerState(enum.Enum):
    DISCONNECTED = 1
    WAITING_FOR_FIRST_DATA = 2
    WAITING_FOR_STATUS = 3
    READY = 4

class TrackerController:
    CHUNK_SIZE = 128

    def __init__(self, datastream, baudrate=250000):
        self.receiver_count = None
        self.raw_mode = None
        self.frequencies = None
        self.voltage = None
        self.temperature = None
        self.rssi = None

        self._should_stop = False
        self._control_lock = threading.RLock()

        self._state = TrackerState(TrackerState.DISCONNECTED)

        self._datastream = datastream

        self._serial = serial.Serial()
        self._serial.baudrate = baudrate
        self._serial.timeout = 0
        self._line_reader = NonBlockingLineReader()

        self._read_hz_timer = CycleTimer()

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
            if not self.is_ready:
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
            try:
                incoming_bytes = self._serial.read(
                    size=TrackerController.CHUNK_SIZE)
                self._line_reader.append_data(incoming_bytes)

                while True:
                    line = self._line_reader.read_line()
                    if not line:
                        break
                    self._parse_line(line)
                    self._tick_read_hz_timer()
            except serial.SerialException:
                LOGGER.error('Serial connection lost.')
                self._serial.close()
                self._state = TrackerState(TrackerState.DISCONNECTED)

    def _parse_line(self, line):
        try:
            command, args = _decode_serial_command(line)
        except UnicodeDecodeError:
            LOGGER.warning("Invalid data received. Skipping...")
            return

        if self._state == TrackerState.WAITING_FOR_FIRST_DATA:
            self._parse_serial_waiting_for_first_data()
        elif self._state == TrackerState.WAITING_FOR_STATUS:
            self._parse_serial_waiting_for_status(command, args)
        elif self._state == TrackerState.READY:
            self._parse_serial_ready(command, args)

    def _parse_serial_waiting_for_first_data(self):
        LOGGER.info('First data received.')

        self._state = TrackerState.WAITING_FOR_STATUS
        self._write_serial_command('?')
        LOGGER.info('Awaiting device status...')

    def _parse_serial_waiting_for_status(self, command, args):
        if command != '?':
            return

        self.receiver_count = int(args[0])
        self.raw_mode = int(args[-1]) == 1
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
            queue_data = {
                'timestamp': timestamp,
                'rssi': readings
            }

            self._datastream.queue_data(queue_data)
            self.rssi = tuple(readings)
            LOGGER.debug('RSSI: %s', readings)
        elif command == 'v':
            self.voltage = float(args[0])
            LOGGER.debug('Voltage: %sV', self.voltage)
        elif command == 't':
            self.temperature = float(args[0])
            LOGGER.debug('Temperature: %sC', self.temperature)

    def _write_serial_command(self, command, *args):
        encoded_command = _encode_serial_command(
            command, *args)

        self._serial.write(encoded_command)
        self._serial.flush()

    def _tick_read_hz_timer(self):
        self._read_hz_timer.tick()
        if self._read_hz_timer.time_since_reset >= 15:
            hz = self._read_hz_timer.hz
            LOGGER.debug('RSSI Rate: %dHz (%.3fs accuracy)', hz, 1 / hz)
            self._read_hz_timer.reset()

    @property
    def is_connected(self):
        return self._serial.is_open

    @property
    def is_ready(self):
        return self._state == TrackerState.READY

    @property
    def hz(self):
        return self._read_hz_timer.hz
