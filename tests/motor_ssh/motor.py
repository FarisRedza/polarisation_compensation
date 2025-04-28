import math
import time
import pathlib
import platform
import threading

from pylablib.devices import Thorlabs

def list_motors(motors: list[Thorlabs.KinesisMotor]) -> list[str]:
    motor_list = []
    for motor in motors:
        motor_list.append(motor.get_device_info().serial_no)
    return motor_list

def rotation_time(
        angle: float,
        acceleration: float,
        max_velocity: float,
        degrees=False
) -> float:
    if degrees:
        angle = math.radians(angle)
        acceleration = math.radians(acceleration)
        max_velocity = math.radians(max_velocity)

    t_accel = max_velocity / acceleration
    # Angle covered during acceleration/deceleration
    angle_accel = 0.5 * acceleration * t_accel**2
    angle_decel = angle_accel
    angle_cruise = angle - angle_accel - angle_decel

    if angle_cruise < 0:
        # The motor never reaches max velocity (triangular profile)
        t_accel = math.sqrt(abs(angle) / acceleration)
        total_time = 2 * t_accel
    else:
        # Full trapezoidal profile
        t_cruise = angle_cruise / max_velocity
        total_time = 2 * t_accel + t_cruise

    return total_time

def get_motor(
        motors: list[Thorlabs.KinesisMotor],
        serial_no: str
) -> Thorlabs.KinesisMotor:
    return next((motor for motor in motors if str(motor.get_device_info().serial_no) == serial_no), None)

def move_motor(
        motor: Thorlabs.KinesisMotor,
        angle: float,
        acceleration: float = 20,
        max_velocity: float = 25
) -> str:
    motor_status = motor.get_status()
    match motor_status:
        case ['enabled'] | ['homed', 'enabled']:
            motor.setup_velocity(
                acceleration=acceleration,
                max_velocity=max_velocity,
                scale=True
            )
            sleep_time = rotation_time(
                angle=angle,
                acceleration=acceleration,
                max_velocity=max_velocity,
                degrees=True
            )
            motor.move_by(angle)
            time.sleep(sleep_time)
            position = motor.get_position()
            
            return f'{motor.get_device_info().serial_no} moved by {angle}, new position {position}'

        case ['moving_bk', 'moving_fw', 'enabled'] | ['moving_bk', 'moving_fw', 'homed', 'enabled']:
            return f'Motor {motor.get_device_info().serial_no} busy'
        
        case ['hw_bk_lim', 'enabled'] | ['hw_bk_lim', 'homed', 'enabled']:
            return f'Motor {motor.get_device_info().serial_no} at backward limit'
        
        case ['hw_fw_lim', 'enabled'] | ['hw_fw_lim', 'homed', 'enabled']:
            return f'Motor {motor.get_device_info().serial_no} at forward limit'

        case _:
            return f'Motor {motor.get_device_info().serial_no} unavailable'

def get_thorlabs_motors() -> list[Thorlabs.KinesisMotor]:
    '''Detects and returns a list of connected Thorlabs motors.'''
    system = platform.system()
    match system:
        case 'Linux':
            return _get_thorlabs_motors_linux()
        case 'Windows':
            return _get_thorlabs_motors_windows()
        case _:
            raise NotImplementedError(f'Unsupported system: {system}')

def _get_thorlabs_motors_linux() -> list[Thorlabs.KinesisMotor]:
    device_path = pathlib.Path('/dev/serial/by-id')
    if not device_path.exists():
        return []

    motors = []
    for symlink in device_path.iterdir():
        if 'Thorlabs' in symlink.name:
            try:
                motors.append(
                    Thorlabs.KinesisMotor(
                        conn=str(symlink.resolve()),
                        scale='stage'
                    )
                )
            except IndexError:
                continue

    return motors

def _get_thorlabs_motors_windows() -> list[Thorlabs.KinesisMotor]:
    motors = []
    for device in Thorlabs.list_kinesis_devices():
        try:
            motors.append(
                Thorlabs.KinesisMotor(
                    conn=device[0],
                    scale='stage'
                )
            )
        except IndexError:
            continue

    return motors


if __name__ == '__main__':
    motors = get_thorlabs_motors()
    motor = get_motor(motors=motors, serial_no='55356974')
    move_motor(motor=motor, angle=-25)
    # move_motor(motor=motor,angle=-25)