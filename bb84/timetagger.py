import dataclasses
import typing
import math

Percent = typing.NewType('Percent', float)
Degrees = typing.NewType('Degrees', float)
Radians = typing.NewType('Radians', float)
Watts = typing.NewType('Watts', float)
Metres = typing.NewType('Metres', float)
DecibelMilliwatts = typing.NewType('DecibelMilliwatts', float)

C_1550_H = 0
C_1550_V = 1
# C_1550_D = 2
# C_1550_A = 3
C_1550_R = 2
C_1550_L = 3

C_780_H = 4
C_780_V = 5
# C_780_D = 6
# C_780_A = 7
C_780_R = 6
C_780_L = 7

@dataclasses.dataclass
class DeviceInfo:
    manufacturer: str = 'N/A'
    model: str = 'N/A'
    serial_number: str = 'N/A'
    firmware_version: str = 'N/A'

@dataclasses.dataclass
class Data:
    # timestamp = float(0.0)
    # wavelength = Metres(0.0)
    azimuth: float = 0.0
    ellipticity: float = 0.0
    # degree_of_polarisation = Percent(0.0)
    # degree_of_linear_polarisation = Percent(0.0)
    # degree_of_circular_polarisation = Percent(0.0)
    # power = DecibelMilliwatts(0.0)
    # power_polarised = DecibelMilliwatts(0.0)
    # power_unpolarised = DecibelMilliwatts(0.0)
    normalised_s1: float = 0.0
    normalised_s2: float = 0.0
    normalised_s3: float = 0.0
    # S0 = Watts(0.0)
    # S1 = Watts(0.0)
    # S2 = Watts(0.0)
    # S3 = Watts(0.0)
    # power_split_ratio: float = 0.0
    # phase_difference = Degrees(0.0)
    # circularity = Percent(0.0)

@dataclasses.dataclass
class RawData:
    singles_780_h: int = 0
    singles_780_v: int = 0
    singles_780_d: int = 0
    singles_780_a: int = 0
    singles_780_r: int = 0
    singles_780_l: int = 0

    singles_1550_h: int = 0
    singles_1550_v: int = 0
    singles_1550_d: int = 0
    singles_1550_a: int = 0
    singles_1550_r: int = 0
    singles_1550_l: int = 0

    def to_data(self) -> Data:
        try:
            s1 = (self.singles_780_h - self.singles_780_v)/(self.singles_780_h + self.singles_780_v)
        except:
            s1 = None
        try:
            s2 = (self.singles_780_d - self.singles_780_a)/(self.singles_780_d + self.singles_780_a)
        except:
            s2 = None
        try:
            s3 = (self.singles_780_r - self.singles_780_l)/(self.singles_780_r + self.singles_780_l)
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

        return Data(
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
        data = RawData()
        return data
