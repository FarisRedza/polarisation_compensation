import sys
import os
import typing
import time

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import motor.motor as thorlabs_motor

def main():
    message = execute_client_command()
    print(message)

def execute_client_command() -> typing.Union[str, list, None]:
    motors = thorlabs_motor.list_thorlabs_motors()

    command = sys.argv[1]
    match command:
        case 'list_motors':
            return [motor.get_device_info().serial_no for motor in motors]

        case 'move_by':
            serial_no = sys.argv[2]
            motor = thorlabs_motor.Motor(serial_number=serial_no)

            angle = float(sys.argv[3])
            acceleration = float(sys.argv[4])
            max_velocity = float(sys.argv[5])

            motor.move_by(
                angle=angle,
                acceleration=acceleration,
                max_velocity=max_velocity
            )
            return f'Motor {serial_no} movement complete'
 
        case 'jog':
            serial_no = sys.argv[2]
            motor = thorlabs_motor.Motor(serial_number=serial_no)

            direction = thorlabs_motor.MotorDirection(sys.argv[3])
            motor.jog(
                direction=direction
            )
            return f'Motor {serial_no} jogging'

        case 'stop':
            serial_no = sys.argv[2]
            motor = thorlabs_motor.Motor(serial_number=serial_no)

            motor.stop()
            return f'Motor {serial_no} stopped'

        case _:
            return f'Unknown command: {command}'
        
if __name__ == '__main__':
    main()