import pathlib
import dataclasses
import re
import pprint
import time

from pylablib.devices import Thorlabs

@dataclasses.dataclass
class Motor:
    model: str
    serial_number: str
    device_path: str


def get_thorlabs_motors() -> list[Motor]:
    serial_by_id_path = pathlib.Path('/dev/serial/by-id')
    if serial_by_id_path.exists():
        devices = []
        s = 'usb-Thorlabs_Kinesis_K10CR1_Rotary_Stage_55356974-if00-port0'
        match = re.search(r'Thorlabs_Kinesis_(\w+)_Rotary_Stage_(\d+)', s)
        for symlink in serial_by_id_path.iterdir():
            if match:
                devices.append(Motor(
                    model=match.group(1),
                    serial_number=match.group(2),
                    device_path=str(symlink.resolve())
                ))
        return devices
    else:
        print('/dev/serial/by-id/ does not exist, check device connection')

def main():
    devices = get_thorlabs_motors()
    pprint.pprint(devices)

    motor_1 = Thorlabs.KinesisMotor(
        conn=devices[0].device_path,
        scale=devices[0].model,
    )
    motor_2 = Thorlabs.KinesisMotor(
        conn=devices[1].device_path,
        scale=devices[1].model,
    )

    motor_1.setup_velocity(
        acceleration=20,
        max_velocity=25,
        scale=True
    )
    motor_2.setup_velocity(
        acceleration=20,
        max_velocity=25,
        scale=True
    )

    motor_1.move_by(90)
    motor_2.move_by(90)

    time.sleep(5)

    motor_1.move_by(-90)
    motor_2.move_by(-90)


if __name__ == '__main__':
    main()