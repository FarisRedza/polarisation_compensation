import enum

class Command(enum.IntEnum):
    LIST_DEVICES = 1
    DEVICE_INFO = 2
    SET_WAVELENGTH = 3
    SET_WAVEPLATE_ROTATION = 4
    MEASURE = 5

class Response(enum.IntEnum):
    ERROR = 0
    LIST_DEVICES = 1
    DEVICE_INFO = 2
    STATUS = 3
    RAWDATA = 4
