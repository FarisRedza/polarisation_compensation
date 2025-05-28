import sys
import os
import time
import dataclasses
import typing
import math
import pprint

import numpy

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import quTAG.QuTAG_HR as QuTAG_HR
# import socket_method.motor_client as thorlabs_motor

Percent = typing.NewType('Percent', float)
Degrees = typing.NewType('Degrees', float)
Radians = typing.NewType('Radians', float)
Watts = typing.NewType('Watts', float)
Metres = typing.NewType('Metres', float)
DecibelMilliwatts = typing.NewType('DecibelMilliwatts', float)

C_H = 0
C_V = 1
# C_D = 2
# C_A = 3
C_R = 2
C_L = 3

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
    singles_h: int = 0
    singles_v: int = 0
    singles_d: int = 0
    singles_a: int = 0
    singles_r: int = 0
    singles_l: int = 0

    def to_data(self) -> Data:
        try:
            s1 = (self.singles_h - self.singles_v)/(self.singles_h + self.singles_v)
        except:
            s1 = 0
        try:
            s2 = (self.singles_d - self.singles_a)/(self.singles_d + self.singles_a)
        except:
            s2 = 0
        try:
            s3 = (self.singles_r - self.singles_l)/(self.singles_r + self.singles_l)
        except:
            s3 = 0

        try:
            eta = math.asin(s1)/2
        except:
            eta = 0
        try:
            theta = math.acos(s3/math.cos(2*eta))/2
        except:
            theta = 0

        return Data(
            azimuth=math.degrees(theta),
            ellipticity=math.degrees(eta),
            normalised_s1=s1,
            normalised_s2=s2,
            normalised_s3=s3
        )

class Qutag():
    def __init__(self):
        self._qutag = QuTAG_HR.QuTAG()
        for channel in range(4, 9):
            self._qutag.setSignalConditioning(
                channel=channel,
                conditioning=3,
                edge=True,
                threshold=1
            )
            self._qutag.setChannelDelay(channel=channel, delays=0)
            self._qutag.setExposureTime(expTime=exposure_time)

    def __del__(self):
        self._qutag.deInitialize()

    def measure(self) -> RawData:
        data = RawData()
        
        self._qutag.getLastTimestamps(reset=True)
        time.sleep(0.1)
        tags, channels, valid = self._qutag.getLastTimestamps(reset=True)

        singles = numpy.bincount(channels, minlength=8)[4:]

        data.singles_h=int(singles[C_H])
        data.singles_v=int(singles[C_V])
        data.singles_r=int(singles[C_R])
        data.singles_l=int(singles[C_L])

        # data.normalised_s1 = float((singles[C_H] - singles[C_V])/(singles[C_H] + singles[C_V]))
        # data.normalised_s3 = float((singles[C_R] - singles[C_L])/(singles[C_R] + singles[C_L]))

        # try:
        #     eta = math.asin(data.normalised_s1)/2
        #     theta = math.acos(data.normalised_s3/math.cos(2*eta))/2
        # except (ValueError, ZeroDivisionError):
        #     pass
        # else:
        #     data.azimuth = math.degrees(theta)
        #     data.ellipticity = math.degrees(eta)

        return data

exposure_time = 100

target_azimuth = 0
azimuth_threshold = 1
target_ellipticity = 0
ellipticity_threshold = 1

# qwp_motor = thorlabs_motor.RemoteMotor(
#     serial_number='55353314',
#     ip_addr=thorlabs_motor.server_ip,
#     port=thorlabs_motor.server_port
# )
# hwp_motor = thorlabs_motor.RemoteMotor(
#     serial_number='55356974',
#     ip_addr=thorlabs_motor.server_ip,
#     port=thorlabs_motor.server_port
# )

# def main():
#     while True:
#         qutag.getLastTimestamps(reset=True)
#         time.sleep(10/exposure_time)
#         tags, channels, valid = qutag.getLastTimestamps(reset=True)
#         singles = numpy.bincount(channels, minlength=8)[4:]
        
#         s_1 = (singles[C_H] - singles[C_V])/(singles[C_H] + singles[C_V])
#         s_3 = (singles[C_R] - singles[C_L])/(singles[C_R] + singles[C_L])

#         print(f'QBER: {1-s_1**2}')

#         try:
#             eta = math.asin(s_3)/2
#             theta = math.acos(s_1/math.cos(2*eta))/2
#         except (ValueError, ZeroDivisionError):
#             pass
#         else:
#             azimuth = math.degrees(theta)
#             ellipticity = math.degrees(eta)

#             print(f'azimuth: {azimuth} | ellipticity: {ellipticity}')

#             if azimuth > target_azimuth + azimuth_threshold/2:
#                 qwp_motor.jog(direction=thorlabs_motor.thorlabs_motor.MotorDirection.BACKWARD)
#             elif azimuth < target_azimuth - azimuth_threshold/2:
#                 qwp_motor.jog(direction=thorlabs_motor.thorlabs_motor.MotorDirection.FORWARD)
#             else:
#                 qwp_motor.stop()

#             if ellipticity > target_ellipticity + ellipticity_threshold/2:
#                 hwp_motor.jog(direction=thorlabs_motor.thorlabs_motor.MotorDirection.BACKWARD)
#             elif ellipticity < target_ellipticity - ellipticity_threshold/2:
#                 hwp_motor.jog(direction=thorlabs_motor.thorlabs_motor.MotorDirection.FORWARD)
#             else:
#                 hwp_motor.stop()

#             time.sleep(1)

def init_qutag() -> QuTAG_HR.QuTAG:
    qutag = QuTAG_HR.QuTAG()
    for channel in range(4, 9):
        qutag.setSignalConditioning(
            channel=channel,
            conditioning=3,
            edge=True,
            threshold=1
        )
        print(f'Channel {channel}: {qutag.getSignalConditioning(channel=channel)}')
        qutag.setChannelDelay(channel=channel, delays=0)
        qutag.setExposureTime(expTime=exposure_time)
    return qutag

if __name__ == '__main__':
    qutag = Qutag()

    # try:
    #     main()
    # except KeyboardInterrupt:
    #     qutag.deInitialize()
    #     print('QuTAG deinitialised')

    #     qwp_motor.stop()
    #     print('QWP Motor stopped')
    #     hwp_motor.stop()
    #     print('HWP Motor stopped')
    
    # data = Data()
    for _ in range(10):
        time.sleep(10/exposure_time)
        print(qutag.measure().to_data())
        # tags, channels, valid = qutag.getLastTimestamps(reset=True)
        # singles = numpy.bincount(channels, minlength=8)[4:]

        # data.normalised_s1 = float((singles[C_H] - singles[C_V])/(singles[C_H] + singles[C_V]))
        # data.normalised_s3 = float((singles[C_R] - singles[C_L])/(singles[C_R] + singles[C_L]))

        # try:
        #     eta = math.asin(data.normalised_s1)/2
        #     theta = math.acos(data.normalised_s3/math.cos(2*eta))/2
        # except (ValueError, ZeroDivisionError):
        #     pass
        # else:
        #     data.azimuth = math.degrees(theta)
        #     data.ellipticity = math.degrees(eta)

        # pprint.pprint(data)

    qutag.deInitialize()