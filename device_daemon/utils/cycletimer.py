import time


class CycleTimer:
    def __init__(self):
        self._cycles = 0
        self._time = time.perf_counter()

    def tick(self):
        self._cycles = self._cycles + 1

    def reset(self):
        self._cycles = 0
        self._time = time.perf_counter()

    @property
    def hz(self):
        return self._cycles / (time.perf_counter() - self._time)

    @property
    def time_since_reset(self):
        return time.perf_counter() - self._time
