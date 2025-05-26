import sys
import os
import pathlib
import time
import math

C_H = 0
C_V = 1
# C_D = 2
# C_A = 3
C_L = 2
C_R = 3

os.environ['TTAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'ttag',
    'python'
))
sys.path.append(os.environ['TTAG'])
import ttag as tt

os.environ['TIMETAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'timetag',
    'python'
))
sys.path.append(os.environ['TIMETAG'])
import timetag

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import socket_method.motor_client as thorlabs_motor

buffernumber = tt.getfreebuffer()-1

target_azimuth = 0
target_ellipticity = 0

qwp_motor = thorlabs_motor.RemoteMotor(
    serial_number='55353314',
    ip_addr=thorlabs_motor.server_ip,
    port=thorlabs_motor.server_port
)
hwp_motor = thorlabs_motor.RemoteMotor(
    serial_number='55356974',
    ip_addr=thorlabs_motor.server_ip,
    port=thorlabs_motor.server_port
)


ttag = tt.TTBuffer(buffernumber=buffernumber)
while True:
    data = ttag.singles(1)[0:4]
    # print(data)
    s_0 = 1
    s_1 = (data[C_H] - data[C_V])/(data[C_H] + data[C_V])
    # s_2 = (data[C_D] - data[C_A])/(data[C_D] + data[C_A])
    s_3 = (data[C_R] - data[C_L])/(data[C_R] + data[C_L])
    print(f's1: {s_1} | s3: {s_3}')

    try:
        eta = math.asin(s_3)/2
        theta = math.acos(s_1/math.cos(2*eta))/2
    except (ValueError, ZeroDivisionError):
        pass
    else:
        azimuth = math.degrees(theta)
        ellipticity = math.degrees(eta)

        print(f'azimuth: {azimuth} | ellipticity: {ellipticity}')

        if azimuth > target_azimuth + 5:
            qwp_motor.jog(direction=thorlabs_motor.thorlabs_motor.MotorDirection.BACKWARD)
        elif azimuth < target_azimuth - 5:
            qwp_motor.jog(direction=thorlabs_motor.thorlabs_motor.MotorDirection.FORWARD)
        else:
            qwp_motor.stop()

        if ellipticity > target_ellipticity + 5:
            hwp_motor.jog(direction=thorlabs_motor.thorlabs_motor.MotorDirection.BACKWARD)
        elif ellipticity < target_ellipticity - 5:
            hwp_motor.jog(direction=thorlabs_motor.thorlabs_motor.MotorDirection.FORWARD)
        else:
            hwp_motor.stop()

    time.sleep(0.1)