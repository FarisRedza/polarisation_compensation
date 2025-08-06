import dataclasses
import typing
import math
import struct

import numpy
import tomtag as tomt

Percent = typing.NewType('Percent', float)
Degrees = typing.NewType('Degrees', float)
Radians = typing.NewType('Radians', float)
Watts = typing.NewType('Watts', float)
Metres = typing.NewType('Metres', float)
DecibelMilliwatts = typing.NewType('DecibelMilliwatts', float)

C_1550_H = 0
C_1550_V = 1
C_1550_D = 2
C_1550_A = 3
C_1550_R = None
C_1550_L = None

C_780_H = 4
C_780_V = 5
C_780_D = 6
C_780_A = 7
C_780_R = None
C_780_L = None

def find_delay(
        tags_1550: numpy.ndarray,
        tags_780: numpy.ndarray,
        tcc: int = 15
    ) -> int:
    """
    Find the delay between the two channels.
    """
    # find delay between 1550 and 780 nm
    cc = []
    for delay in numpy.arange(-3000, 3000,10):
        cc.append(
            tomt.count_twofolds(
                tags_1550, tags_780 + delay,
                len(tags_1550), len(tags_780), 15
            )
        )
    return numpy.arange(-3000, 3000,10)[numpy.argmax(cc)]
    
def get_qber(channels, timetags, delay=0, tcc=50):
    """
    Assume that channels are HVDAHVDA
    """
    tags_H_1550 = timetags[channels == 0]
    tags_V_1550 = timetags[channels == 1]
    tags_D_1550 = timetags[channels == 2]
    tags_A_1550 = timetags[channels == 3]
    tags_H_780 = timetags[channels == 4] + delay
    tags_V_780 = timetags[channels == 5] + delay
    tags_D_780 = timetags[channels == 6] + delay
    tags_A_780 = timetags[channels == 7] + delay

    # self.find_delay(tags_H_1550, tags_H_780, tcc)

    HH = tomt.count_twofolds(tags_H_1550, tags_H_780, len(tags_H_1550), len(tags_H_780),tcc)
    HV = tomt.count_twofolds(tags_H_1550, tags_V_780, len(tags_H_1550), len(tags_V_780),tcc)
    VH = tomt.count_twofolds(tags_V_1550, tags_H_780, len(tags_V_1550), len(tags_H_780),tcc)
    VV = tomt.count_twofolds(tags_V_1550, tags_V_780, len(tags_V_1550), len(tags_V_780),tcc)

    qber =  (VH + VH) / (HH + HV + VH + VV)
    print('qber =',qber)
    print( HH, HV, VH, VV)

    DD = tomt.count_twofolds(tags_D_1550, tags_D_780, len(tags_D_1550), len(tags_D_780),tcc)
    DA = tomt.count_twofolds(tags_D_1550, tags_A_780, len(tags_D_1550), len(tags_A_780),tcc)
    AD = tomt.count_twofolds(tags_A_1550, tags_D_780, len(tags_A_1550), len(tags_D_780),tcc)
    AA = tomt.count_twofolds(tags_A_1550, tags_V_780, len(tags_A_1550), len(tags_A_780),tcc)

    qx =  (DA + AD) / (DD + AD + DA + AA)
    print('qx =', qx)
    print(DD, AD, DA, AA)

    return qber, qx, HH+HV+VH+VV

@dataclasses.dataclass
class DeviceInfo:
    manufacturer: str = 'N/A'
    model: str = 'N/A'
    serial_number: str = 'N/A'
    firmware_version: str = 'N/A'

    def serialise(self) -> bytes:
        def encode_string(s: str):
            b = s.encode()
            return struct.pack(f'I{len(b)}s', len(b), b)

        return (
            encode_string(self.manufacturer) +
            encode_string(self.model) +
            encode_string(self.serial_number) +
            encode_string(self.firmware_version)
        )
    
    @classmethod
    def deserialise(cls, payload: bytes) -> 'DeviceInfo':
        offset = 0
        fields = []
        for _ in range(4):
            length = struct.unpack_from('I', payload, offset)[0]
            offset += 4
            value = struct.unpack_from(
                f'{length}s',
                payload,
                offset
            )[0].decode()
            offset += length
            fields.append(value)
        return DeviceInfo(*fields)

@dataclasses.dataclass
class RawData:
    timetags: numpy.ndarray = dataclasses.field(
        default_factory=lambda: numpy.array([])
    )
    channels: numpy.ndarray = dataclasses.field(
        default_factory=lambda: numpy.array([])
    )

    def serialise(self) -> bytes:
        n_data_points = len(self.timetags)

        header = struct.pack('!II', n_data_points, n_data_points)
        timetags_bytes = self.timetags.astype(dtype='>i8').tobytes()
        channels_bytes = self.channels.astype(dtype='>u1').tobytes()

        return header + timetags_bytes + channels_bytes

    @classmethod
    def deserialise(cls, payload: bytes) -> 'RawData':
        header_size = struct.calcsize('!II')
        n_data_points, _ = struct.unpack('!II', payload[:header_size])

        timetags_size = n_data_points * 4
        channels_size = timetags_size

        timetags_start = header_size
        timetags_end = timetags_start + timetags_size
        channels_start = timetags_end
        channels_end = channels_start + channels_size

        timetags_bytes = n_data_points * 8
        channels_bytes = n_data_points

        offset_timetags = header_size
        offset_channels = offset_timetags + timetags_bytes

        timetags = numpy.frombuffer(payload[offset_timetags:offset_channels], dtype='>i8').astype(numpy.int64)
        channels = numpy.frombuffer(payload[offset_channels:offset_channels + channels_bytes], dtype='>u1').astype(numpy.uint8)

        return RawData(timetags=timetags, channels=channels)

@dataclasses.dataclass
class Data:
    azimuth: float = 0.0
    ellipticity: float = 0.0
    normalised_s1: float = 0.0
    normalised_s2: float = 0.0
    normalised_s3: float = 0.0
    qber: float = 0.0
    qx: float = 0.0

    @classmethod
    def from_raw_data(cls, raw_data: RawData) -> 'Data':
        singles = numpy.bincount(raw_data.channels.astype(numpy.int64) , minlength=8)

        with numpy.errstate(invalid='ignore'):
            try:
                s1 = float((singles[C_780_H] - singles[C_780_V])/(singles[C_780_H] + singles[C_780_V]))
            except:
                s1 = None
            try:
                s2 = float((singles[C_780_D] - singles[C_780_A])/(singles[C_780_D] + singles[C_780_A]))
            except:
                s2 = None
            try:
                s3 = float((singles[C_780_R] - singles[C_780_L])/(singles[C_780_R] + singles[C_780_L]))
            except:
                s3 = None

        match (s1, s2, s3):
            case (float(), None, float()):
                s2 = math.sqrt(1 - s1**2 - s3**2)

            case (None, float(), float()):
                s1 = math.sqrt(1 - s2**2 - s3**2)

            case (float(), float(), None):
                s3 = math.sqrt(1 - s1**2 - s2**2)

            case _:
                raise TypeError(f'Error: Unsupported basis setup {(type(s1), type(s2), type(s3))}')

        try:    
            qber, qx, rate = get_qber(channels=raw_data.channels, timetags=raw_data.timetags)
        except:
            qber = 0
            qx = 0
        try:
            eta = math.asin(s3)/2
        except:
            eta = 0
        try:
            theta = math.acos(s1/math.cos(2*eta))/2
        except:
            theta = 0

        return cls(
            azimuth=math.degrees(theta),
            ellipticity=math.degrees(eta),
            normalised_s1=s1,
            normalised_s2=s2,
            normalised_s3=s3,
            qber=qber,
            qx=qx
        )

class TimeTagger:
    def __init__(self) -> None:
        self.device_info = DeviceInfo()

    def measure(self) -> RawData:
        data_points = 10000
        timetags = numpy.array(
            object=range(data_points),
            dtype=numpy.int64
        )
        channels = numpy.random.randint(
            low=1,
            high=8,
            size=data_points
        ).astype(dtype=numpy.uint8)
        raw_data = RawData(
            timetags=timetags,
            channels=channels
        )
        return raw_data
    
    def disconnect(self) -> None:
        pass

