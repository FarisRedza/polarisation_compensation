import enum

class Command(enum.IntEnum):
    LIST_DEVICES = 1
    MEASURE_ONCE = 2
    START_MEASURING = 3
    STOP_MEASURING = 4

class Response(enum.IntEnum):
    ERROR = 0
    DEVICE_INFO = 1
    RAWDATA = 2
    STATUS = 3