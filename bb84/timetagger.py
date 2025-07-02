import dataclasses
import typing
import math
import struct
import random

import numpy

Percent = typing.NewType('Percent', float)
Degrees = typing.NewType('Degrees', float)
Radians = typing.NewType('Radians', float)
Watts = typing.NewType('Watts', float)
Metres = typing.NewType('Metres', float)
DecibelMilliwatts = typing.NewType('DecibelMilliwatts', float)

C_1550_H = 0
C_1550_V = 1
C_1550_D = None
C_1550_A = None
C_1550_R = 2
C_1550_L = 3

C_780_H = 4
C_780_V = 5
C_780_D = None
C_780_A = None
C_780_R = 6
C_780_L = 7

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

# @dataclasses.dataclass
# class RawData:
#     channel_1: int = 0
#     channel_2: int = 0
#     channel_3: int = 0
#     channel_4: int = 0
#     channel_5: int = 0
#     channel_6: int = 0
#     channel_7: int = 0
#     channel_8: int = 0

# @dataclasses.dataclass
# class Data:
#     azimuth: float = 0.0
#     ellipticity: float = 0.0
#     normalised_s1: float = 0.0
#     normalised_s2: float = 0.0
#     normalised_s3: float = 0.0

#     @classmethod
#     def from_raw_data(cls, raw_data: RawData) -> 'Data':
#         singles = [int(val) for channel, val in raw_data.__dict__.items()]
#         try:
#             s1 = (singles[C_780_H] - singles[C_780_V])/(singles[C_780_H]+ singles[C_780_V])
#         except:
#             s1 = None
#         try:
#             s2 = (singles[C_780_D] - singles[C_780_A])/(singles[C_780_D] + singles[C_780_A])
#         except:
#             s2 = None
#         try:
#             s3 = (singles[C_780_R] - singles[C_780_L])/(singles[C_780_R] + singles[C_780_L])
#         except:
#             s3 = None

#         match (s1, s2, s3):
#             case (float(), None, float()):
#                 s2 = math.sqrt(1 - s1**2 - s3**2)

#             case (None, float(), float()):
#                 s1 = math.sqrt(1 - s2**2 - s3**2)

#             case (float(), float(), None):
#                 s3 = math.sqrt(1 - s1**2 - s2**2)

#             case _:
#                 raise RuntimeError(f'Error: Unsupported basis setup {(type(s1), type(s2), type(s3))}')

#         try:
#             eta = math.asin(s3)/2
#         except:
#             eta = 0
#         try:
#             theta = math.acos(s1/math.cos(2*eta))/2
#         except:
#             theta = 0

#         return cls(
#             azimuth=math.degrees(theta),
#             ellipticity=math.degrees(eta),
#             normalised_s1=s1,
#             normalised_s2=s2,
#             normalised_s3=s3
#         )

@dataclasses.dataclass
class RawData:
    timetags: list[int]
    channels: list[int]

    def serialise(self) -> bytes:
        n_data_points = len(self.timetags)

        header = struct.pack('!II', n_data_points, n_data_points)
        timetags_bytes = struct.pack(f'!{n_data_points}I', *self.timetags)
        channels_bytes = struct.pack(f'!{n_data_points}I', *self.channels)

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

        timetags = list(struct.unpack(
            f'!{n_data_points}I',
            payload[timetags_start:timetags_end]
        ))
        channels = list(struct.unpack(
            f'!{n_data_points}I',
            payload[channels_start:channels_end]
        ))

        return RawData(timetags=timetags, channels=channels)

@dataclasses.dataclass
class Data:
    azimuth: float = 0.0
    ellipticity: float = 0.0
    normalised_s1: float = 0.0
    normalised_s2: float = 0.0
    normalised_s3: float = 0.0

    @classmethod
    def from_raw_data(cls, raw_data: RawData) -> 'Data':
        singles = numpy.bincount(raw_data.channels, minlength=8)

        try:
            s1 = (singles[C_780_H] - singles[C_780_V])/(singles[C_780_H]+ singles[C_780_V])
        except:
            s1 = None
        try:
            s2 = (singles[C_780_D] - singles[C_780_A])/(singles[C_780_D] + singles[C_780_A])
        except:
            s2 = None
        try:
            s3 = (singles[C_780_R] - singles[C_780_L])/(singles[C_780_R] + singles[C_780_L])
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
                raise RuntimeError(f'Error: Unsupported basis setup {(type(s1), type(s2), type(s3))}')

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
            normalised_s3=s3
        )

class TimeTagger:
    def __init__(self):
        self.device_info = DeviceInfo()

    def measure(self) -> RawData:
        data_size = 100000
        timetags = list(range(0,data_size))
        channels = [random.randint(1,8) for _ in range(data_size)]
        raw_data = RawData(
            timetags=timetags,
            channels=channels
        )
        return raw_data
    
    def disconnect(self) -> None:
        pass

if __name__ == '__main__':
    tt = TimeTagger()
    for _ in range(100):
        payload = tt.measure().serialise()
        data = RawData.deserialise(payload=payload)
        # print(data)
