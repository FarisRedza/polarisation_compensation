import dataclasses
import typing
import math
import struct
import time

import numpy as np
import tomtag as tomt

Percent = typing.NewType('Percent', float)
Degrees = typing.NewType('Degrees', float)
Radians = typing.NewType('Radians', float)
Watts = typing.NewType('Watts', float)
Metres = typing.NewType('Metres', float)
DecibelMilliwatts = typing.NewType('DecibelMilliwatts', float)

@dataclasses.dataclass
class ChannelGroup:
    name: str
    H: int | None = None
    V: int | None = None
    A: int | None = None
    D: int | None = None
    R: int | None = None
    L: int | None = None

default_channel_groups = [
    ChannelGroup(
        name='780',
        H=4,
        V=5,
        D=6,
        A=7,
        R=None,
        L=None
    ),
    ChannelGroup(
        name='1550',
        H=0,
        V=1,
        D=2,
        A=3,
        R=None,
        L=None
    )
]

def find_delay(
        tags_1550: np.ndarray,
        tags_780: np.ndarray,
        tcc: int = 15
    ) -> int:
    """
    Find the delay between the two channels.
    """
    # find delay between 1550 and 780 nm
    cc = []
    for delay in np.arange(-3000, 3000,10):
        cc.append(
            tomt.count_twofolds(
                tags_1550, tags_780 + delay,
                len(tags_1550), len(tags_780), 15
            )
        )
    return np.arange(-3000, 3000,10)[np.argmax(cc)]

def get_qber(
        channels: np.typing.NDArray[np.uint8],
        timetags: np.typing.NDArray[np.int64],
        channel_group_1: ChannelGroup,
        channel_group_2: ChannelGroup,
        delay: float = 0,
        tcc: float = 50,
        verbose: bool = False
) -> tuple[float, float, float]:
    tags_H_1550 = timetags[channels == channel_group_2.H]
    tags_V_1550 = timetags[channels == channel_group_2.V]
    tags_D_1550 = timetags[channels == channel_group_2.D]
    tags_A_1550 = timetags[channels == channel_group_2.A]
    tags_H_780 = timetags[channels == channel_group_1.H]
    print(len(tags_H_1550))
    delay=find_delay(tags_H_1550, tags_H_780)
    tags_H_780 = timetags[channels == channel_group_1.H] + delay
    tags_V_780 = timetags[channels == channel_group_1.V] + delay
    tags_D_780 = timetags[channels == channel_group_1.D] + delay
    tags_A_780 = timetags[channels == channel_group_1.A] + delay

    HH: int = tomt.count_twofolds(tags_H_1550, tags_H_780, len(tags_H_1550), len(tags_H_780),tcc)
    HV: int = tomt.count_twofolds(tags_H_1550, tags_V_780, len(tags_H_1550), len(tags_V_780),tcc)
    VH: int = tomt.count_twofolds(tags_V_1550, tags_H_780, len(tags_V_1550), len(tags_H_780),tcc)
    VV: int = tomt.count_twofolds(tags_V_1550, tags_V_780, len(tags_V_1550), len(tags_V_780),tcc)

    qber: float =  (VH + HV) / (HH + HV + VH + VV)
    if verbose == True:
        print('qber =',qber)
        print(HH, HV, VH, VV)

    DD: int = tomt.count_twofolds(tags_D_1550, tags_D_780, len(tags_D_1550), len(tags_D_780),tcc)
    DA: int = tomt.count_twofolds(tags_D_1550, tags_A_780, len(tags_D_1550), len(tags_A_780),tcc)
    AD: int = tomt.count_twofolds(tags_A_1550, tags_D_780, len(tags_A_1550), len(tags_D_780),tcc)
    AA: int = tomt.count_twofolds(tags_A_1550, tags_V_780, len(tags_A_1550), len(tags_A_780),tcc)

    qx: float =  (DA + AD) / (DD + AD + DA + AA)
    if verbose == True and qx > 1:
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
    timetags: np.typing.NDArray[np.int64] = dataclasses.field(
        default_factory=lambda: np.array([], dtype=np.int64)
    )
    channels: np.typing.NDArray[np.uint8] = dataclasses.field(
        default_factory=lambda: np.array([], dtype=np.uint8)
    )

    def serialise(self) -> bytes:
        n_data_points = len(self.timetags)

        header = struct.pack('!II', n_data_points, n_data_points)
        timetags_bytes = self.timetags.tobytes()
        channels_bytes = self.channels.tobytes()

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

        # prev '>i64' > for endian, check this later with numpy
        timetags = np.frombuffer(payload[offset_timetags:offset_channels], dtype=np.int64)
        channels = np.frombuffer(payload[offset_channels:offset_channels + channels_bytes], dtype=np.uint8)

        return RawData(timetags=timetags, channels=channels)

@dataclasses.dataclass
class Data:
    singles: np.typing.NDArray[np.int64] = dataclasses.field(
        default_factory=lambda: np.array([], dtype=np.int64)
    )
    azimuth: float = 0.0
    ellipticity: float = 0.0
    normalised_s1: float = 0.0
    normalised_s2: float = 0.0
    normalised_s3: float = 0.0
    qber: float = 0.0
    qx: float = 0.0
    rate: int = 0

    @classmethod
    def from_raw_data(
            cls,
            raw_data: RawData,
            channel_groups: list[ChannelGroup] | None = None
    ) -> 'Data':
        singles = np.bincount(raw_data.channels, minlength=8)

        if channel_groups:
            with np.errstate(invalid='ignore'):
                try:
                    s1 = float((singles[getattr(channel_groups[0], 'H')] - singles[getattr(channel_groups[0], 'V')])/(singles[getattr(channel_groups[0], 'H')] + singles[getattr(channel_groups[0], 'V')]))
                except:
                    s1 = None
                try:
                    s2 = float((singles[getattr(channel_groups[0], 'D')] - singles[getattr(channel_groups[0], 'A')])/(singles[getattr(channel_groups[0], 'D')] + singles[getattr(channel_groups[0], 'A')]))
                except:
                    s2 = None
                try:
                    s3 = float((singles[getattr(channel_groups[0], 'R')] - singles[getattr(channel_groups[0], 'L')])/(singles[getattr(channel_groups[0], 'R')] + singles[getattr(channel_groups[0], 'L')]))
                except:
                    s3 = None

            match (s1, s2, s3):
                case (float(), None, float()):
                    s2 = math.sqrt(max(0.0, 1 - s1**2 - s3**2))

                case (None, float(), float()):
                    s1 = math.sqrt(max(0.0, 1 - s2**2 - s3**2))

                case (float(), float(), None):
                    s3 = math.sqrt(max(0.0, 1 - s1**2 - s2**2))

                case _:
                    raise TypeError(f'Error: Unsupported basis setup {(type(s1), type(s2), type(s3))}')

            try:
                if len(channel_groups) > 1:
                    cg_780_inx = next((i for i, cg in enumerate(channel_groups) if cg.name == '780'))
                    cg_1550_inx = next((i for i, cg in enumerate(channel_groups) if cg.name == '1550'))

                    qber, qx, rate = get_qber(
                        channels=raw_data.channels,
                        timetags=raw_data.timetags,
                        channel_group_1=channel_groups[cg_780_inx],
                        channel_group_2=channel_groups[cg_1550_inx]
                    )
                elif len(channel_groups) == 1:
                    qber = 1 - s1**2
                    qx = 1 - s2**2
                    rate = 0
                else:
                    qber = 0
                    qx = 0
                    rate = 0
            except:
                qber = 0
                qx = 0
                rate = 0
            try:
                eta = np.asin(s3)/2
            except:
                eta = 0
            try:
                # theta = np.acos(s1/np.cos(2*eta))/2
                theta = 0.5 * np.arctan2(s2, s1)
            except:
                theta = 0
        
        else:
            theta = 0.0
            eta =0.0
            s1 = 0.0
            s2 = 0.0
            s3 = 0.0
            qber = 0.0
            qx = 0.0
            rate = 0

        return cls(
            singles=singles,
            azimuth=np.degrees(theta),
            ellipticity=np.degrees(eta),
            normalised_s1=s1,
            normalised_s2=s2,
            normalised_s3=s3,
            qber=qber,
            qx=qx,
            rate=rate
        )

class TimeTagger:
    def __init__(self) -> None:
        self.device_info = DeviceInfo(
            manufacturer='Dummy Device'
        )
        self.channel_groups = [
            ChannelGroup(
                name='780',
                H=0,
                V=1,
                D=2,
                A=3,
                R=None,
                L=None
            )
        ]

    def measure(self) -> RawData:
        total_counts = np.random.randint(low=30000, high=35000)

        detector_proportions = {
            "H": 0.5,
            "V": 0.0,
            "D": 0.495,
            "A": 0.005,
            # "R": 0.0,
            # "L": 0.0
        }

        noisy_props = np.array(list(detector_proportions.values())) + np.random.normal(loc=0, scale=0.0001, size=len(detector_proportions))
        noisy_props = np.clip(a=noisy_props, a_min=0, a_max=None)
        noisy_props = noisy_props / noisy_props.sum()

        dark_counts = np.random.poisson(lam=200, size=len(detector_proportions))

        counts = np.random.multinomial(n=total_counts, pvals=noisy_props) + dark_counts

        channels = np.concatenate([
            np.full(c, i, dtype=np.uint8)
            for i, c in enumerate(counts)
        ])
        np.random.shuffle(channels)

        timetags = np.arange(total_counts, dtype=np.int64)

        raw_data = RawData(
            timetags=timetags,
            channels=channels
        )
        return raw_data
    
    def disconnect(self) -> None:
        pass

if __name__ == '__main__':
    tt = TimeTagger()
    for _ in range(5):
        print(Data().from_raw_data(
            raw_data=tt.measure(),
        ))
        time.sleep(0.5)