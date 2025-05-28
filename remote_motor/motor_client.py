import sys
import os
import socket
import threading
import json
import time
import typing
import enum
import pprint
import dataclasses

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
# import motor.motor as thorlabs_motor
server_ip = '127.0.0.1'
# server_ip = '137.195.89.222'
server_port = 5002
motor_refresh_time = 0.1

MAX_ACCELERATION = 20.0
MAX_VELOCITY = 25.0

@dataclasses.dataclass
class DeviceInfo:
    device_name: str
    model: str
    serial_number: str
    firmware_version: str

class MotorDirection(enum.Enum):
    FORWARD = '+'
    BACKWARD = '-'
    IDLE = None

def send_request(
        host: str,
        port: int,
        command: str,
        arguments: list = [],
        timeout: int = 5
) -> typing.Any:
    request = {'command': command}
    try:
        with socket.create_connection(address=(host,port), timeout=timeout) as s:
            match command:
                case 'list_motors':
                    pass

                case 'get_position':
                    request['serial_number'] = arguments[0]

                case 'move_by':
                    request['serial_number'] = arguments[0]
                    request['angle'] = arguments[1]

                case 'move_to':
                    request['serial_number'] = arguments[0]
                    request['position'] = arguments[1]

                case 'jog':
                    request['serial_number'] = arguments[0]
                    request['direction'] = arguments[1]

                case 'stop':
                    request['serial_number'] = arguments[0]

                case _:
                    raise Exception

            s.sendall(json.dumps(request).encode())
            buffer = ""
            while True:
                data = s.recv(1024).decode()
                if not data:
                    break
                buffer += data
                if "\n" in buffer:
                    break
            response = json.loads(buffer.strip())
            return response

    except Exception as e:
        return {f'Error sending request {request}': str(e)}
    
def list_thorlabs_motors(
        host: str,
        port: int,
        timeout: int = 5
) -> list[DeviceInfo]:
    result = send_request(
        host=host,
        port=port,
        command='list_motors',
        timeout=timeout
    )
    return [DeviceInfo(**motor) for motor in result['motors']] 
    
class Motor:
    def __init__(
            self,
            serial_number: str,
            ip_addr: str,
            port: int
    ) -> None:
        self.ip_addr = ip_addr
        self.port = port

        self._position_lock = threading.Lock()
        self._position_polling = 0.1
        self._position: list[float] = [0.0]
        self.motor_thread: threading.Thread | None = None

        self.step_size: float = 5
        self.acceleration: float = MAX_ACCELERATION
        self.max_velocity: float = MAX_VELOCITY

        available_motors = send_request(
            host=ip_addr,
            port=server_port,
            command='list_motors'
        )['motors']
        motor_index = next(
            (i for i, motor in enumerate(available_motors) if str(motor['serial_number']) == serial_number),
            None
        )
        if motor_index is None:
            raise Exception
        else:
            self.device_info = DeviceInfo(**available_motors[motor_index])
            status = send_request(
                host=self.ip_addr,
                port=self.port,
                command='get_position',
                arguments=[self.device_info.serial_number]
            )
            self.position = float(status['position'])
            self.is_moving = bool(status['moving'])
            self.direction = MotorDirection(status['direction'])

            print(f'Connected to motor {self.device_info.serial_number}')

    def move_by(
            self,
            angle: float,
            acceleration: float = MAX_ACCELERATION,
            max_velocity: float = MAX_VELOCITY
    ) -> bool:
        result = send_request(
            host=self.ip_addr,
            port=self.port,
            command='move_by',
            arguments=[self.device_info.serial_number, angle]
        )
        print('Command sent:', result.get('status') or result.get('error'))
        while True:
            time.sleep(motor_refresh_time)
            update = send_request(
                host=server_ip,
                port=server_port,
                command='get_position',
                arguments=[self.device_info.serial_number]
            )
            if 'error' in update:
                print('Error:', update['error'])
                break
            print(
                f"Motor {self.device_info.serial_number} position: {update['position']} | Moving: {update['moving']}"
            )
            if not update['moving']:
                break
        return True
    
    def threaded_move_by(
            self, 
            angle: float,
            acceleration: float = MAX_ACCELERATION,
            max_velocity: float = MAX_VELOCITY
    ) -> None:
        if self.motor_thread is None or not self.motor_thread.is_alive():
            self.motor_thread = threading.Thread(
                target=self.move_by,
                args=(
                    angle,
                    acceleration,
                    max_velocity
                )
            )
            self.motor_thread.start()
        else:
            print('Warning: Motor is busy')

    def move_to(
            self,
            position: float,
            acceleration: float = MAX_ACCELERATION,
            max_velocity: float = MAX_VELOCITY
    ) -> bool:
        result = send_request(
            host=self.ip_addr,
            port=self.port,
            command='move_to',
            arguments=[self.device_info.serial_number, position]
        )
        print('Command sent:', result.get('status') or result.get('error'))
        self._start_tracking_positon()
        while True:
            time.sleep(motor_refresh_time)
            update = send_request(
                host=server_ip,
                port=server_port,
                command='get_position',
                arguments=[self.device_info.serial_number]
            )
            if 'error' in update:
                print('Error:', update['error'])
                break
            print(
                f"Motor {self.device_info.serial_number} position: {update['position']} | Moving: {update['moving']}"
            )
            if not update['moving']:
                break
        return True
    
    def threaded_move_to(
            self, 
            position: float,
            acceleration: float = MAX_ACCELERATION,
            max_velocity: float = MAX_VELOCITY
    ) -> None:
        if self.motor_thread is None or not self.motor_thread.is_alive():
            self.motor_thread = threading.Thread(
                target=self.move_to,
                args=(
                    position,
                    acceleration,
                    max_velocity
                )
            )
            self.motor_thread.start()
        else:
            print('Warning: Motor is busy')

    def jog(
            self,
            direction: MotorDirection,
            acceleration: float = MAX_ACCELERATION,
            max_velocity: float = MAX_VELOCITY
    ) -> None:
        result = send_request(
            host=self.ip_addr,
            port=self.port,
            command='jog',
            arguments=[
                self.device_info.serial_number,
                direction.value,
                acceleration,
                max_velocity
            ]
        )
        self._start_tracking_positon()
        print("Command sent:", result.get("status") or result.get("error"))

    def stop(self) -> None:
        result = send_request(
            host=self.ip_addr,
            port=self.port,
            command='stop',
            arguments=[self.device_info.serial_number]
        )
        self._stop_tracking_position()
        print("Command sent:", result.get("status") or result.get("error"))

    def _get_motor_position(self) -> None:
        with self._position_lock:
            result = send_request(
                host=self.ip_addr,
                port=self.port,
                command='get_position',
                arguments=[self.device_info.serial_number]
            )
            self.position = float(result['position'])

    def _track_position(self):
        self.is_moving = True
        while self.is_moving == True:
            time.sleep(motor_refresh_time)
            update = send_request(
                host=server_ip,
                port=server_port,
                command='get_position',
                arguments=[self.device_info.serial_number]
            )
            if 'error' in update:
                print('Error:', update['error'])
                break
            # print(
            #     f"Motor {self.device_info.serial_number} position: {update['position']} | Moving: {update['moving']}"
            # )
            if not update['moving']:
                self.is_moving = False

    def _start_tracking_positon(self):
        self._position_thread = threading.Thread(
            target=self._track_position
        )
        self._position_thread.start()

    def _stop_tracking_position(self):
        self._position_thread.join()

def motor_cli():
    result = send_request(
        host=server_ip,
        port=server_port,
        command='list_motors'
    )
    motors: list[str] = [DeviceInfo(**motor).serial_number for motor in result.get('motors')]
    while True:
        print(f'Available motors: {motors}' or result.get('error'))
        print('1. Print motor position')
        print('2. Move motor by offset')
        print('3. Move motor to')
        print('4. Jog motor')
        print('5. Stop motor')
        print('q. Quit')

        choice = input().strip().lower()
        match choice:
            case '1':
                print('Select motor')
                for i, motor in enumerate(motors):
                    print(f'{i+1}. {motor}')
                motor_choice = int(input().strip()) - 1
                serial_number = motors[motor_choice]

                result = send_request(
                    host=server_ip,
                    port=server_port,
                    command='get_position',
                    arguments=[serial_number]
                )
                print(
                    f"Motor {serial_number} position: {result['position']} | Moving: {result['moving']}"
                )

            case '2':
                print('Select motor')
                for i, motor in enumerate(motors):
                    print(f'{i+1}. {motor}')
                motor_choice = int(input().strip()) - 1
                serial_number = motors[motor_choice]

                angle = input('Enter offset angle: ')
                result = send_request(
                    host=server_ip,
                    port=server_port,
                    command='move_by',
                    arguments=[serial_number, angle]
                )
                print('Command sent:', result.get('status') or result.get('error'))

                while True:
                    update = send_request(
                        host=server_ip,
                        port=server_port,
                        command='get_position',
                        arguments=[serial_number]
                    )
                    if 'error' in update:
                        print('Error:', update['error'])
                        break
                    print(
                        f"Motor {serial_number} position: {update['position']} | Moving: {update['moving']}"
                    )
                    if not update['moving']:
                        break
                    time.sleep(motor_refresh_time)

            case '3':
                print('Select motor')
                for i, motor in enumerate(motors):
                    print(f'{i+1}. {motor}')
                motor_choice = int(input().strip()) - 1
                serial_number = motors[motor_choice]

                position = input('Enter position: ')
                result = send_request(
                    host=server_ip,
                    port=server_port,
                    command='move_to',
                    arguments=[serial_number, position]
                )
                print('Command sent:', result.get('status') or result.get('error'))

                while True:
                    update = send_request(
                        host=server_ip,
                        port=server_port,
                        command='get_position',
                        arguments=[serial_number]
                    )
                    if 'error' in update:
                        print('Error:', update['error'])
                        break
                    print(
                        f"Motor {serial_number} position: {update['position']} | Moving: {update['moving']}"
                    )
                    if not update['moving']:
                        break
                    time.sleep(motor_refresh_time)

            case '4':
                print('Select motor')
                for i, motor in enumerate(motors):
                    print(f'{i+1}. {motor}')
                motor_choice = int(input().strip()) - 1
                serial_number = motors[motor_choice]

                print('Choose direction')
                print('1. Forward')
                print('2. Backward')
                direction_choice = input().strip()
                match direction_choice:
                    case '1':
                        direction = MotorDirection.FORWARD
                    case '2':
                        direction = MotorDirection.BACKWARD
                    case _:
                        print('Invalid choice')
                        break

                result = send_request(
                    host=server_ip,
                    port=server_port,
                    command='jog',
                    arguments=[serial_number, direction.value]
                )
                print('Command sent:', result.get('status') or result.get('error'))

            case '5':
                print('Select motor')
                for i, motor in enumerate(motors):
                    print(f'{i+1}. {motor}')
                motor_choice = int(input().strip()) - 1
                serial_number = motors[motor_choice]

                result = send_request(
                    host=server_ip,
                    port=server_port,
                    command='stop',
                    arguments=[serial_number]
                )
                print('Command sent:', result.get('status') or result.get('error'))

            case 'q':
                break

            case _:
                print("Invalid choice")
        
if __name__ == '__main__':
    # motor_cli()

    print(list_thorlabs_motors(host=server_ip, port=server_port))
    motor = Motor(
        serial_number='55356974',
        ip_addr=server_ip,
        port=server_port
    )
    motor.jog(direction=MotorDirection.BACKWARD)
    for _ in range(5):
        print(motor.position)
        time.sleep(1)
    motor.stop()