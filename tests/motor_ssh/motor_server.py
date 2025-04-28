import platform
import pathlib
import time
import sys
import math

from pylablib.devices import Thorlabs

from motor import *

def main():
    message = execute_client_command()
    print(message)

def execute_client_command() -> str:
    motors = get_thorlabs_motors()

    command = sys.argv[1]
    match command:
        case 'list_motors':
            return list_motors(motors=motors)

        case 'move_motor':
            serial_no = sys.argv[2]
            motor = get_motor(motors=motors, serial_no=serial_no)

            angle = float(sys.argv[3])
            acceleration = float(sys.argv[4])
            max_velocity = float(sys.argv[5])

            return move_motor(
                motor=motor,
                angle=angle,
                acceleration=acceleration,
                max_velocity=max_velocity
            )

        case _:
            return f'Unknown command: {command}'
