import sys
import os

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

def execute_client_command() -> str:
    motors = thorlabs_motor.list_thorlabs_motors()

    command = sys.argv[1]
    match command:
        case 'list_motors':
            return motors

        case 'move_motor':
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

        case _:
            return f'Unknown command: {command}'
