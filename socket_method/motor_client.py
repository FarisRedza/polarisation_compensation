import sys
import os
import socket
import threading
import json
import time
import typing

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import motor.motor as thorlabs_motor
server_ip = '127.0.0.1'
server_port = 5002
motor_refresh_time = 0.1

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
            # response = s.recv(1024)
            # return json.loads(response.decode())
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
    
class RemoteMotor(thorlabs_motor.Motor):
    def __init__(
            self,
            serial_number: str,
            ip_addr: str,
            port: int
    ) -> None:
        self.serial_no = serial_number
        self.ip_addr = ip_addr
        self.port = port

        available_motors = send_request(
            host=ip_addr,
            port=server_port,
            command='list_motors'
        )['motors']
        if self.serial_no not in available_motors:
            raise Exception
        else:
            print(f'Connected to motor {self.serial_no}')

    def move_by(
            self,
            angle: float,
            acceleration: float = thorlabs_motor.MAX_ACCELERATION,
            max_velocity: float = thorlabs_motor.MAX_VELOCITY
    ) -> bool:
        result = send_request(
            host=self.ip_addr,
            port=self.port,
            command='move_by',
            arguments=[self.serial_no, angle]
        )
        print('Command sent:', result.get('status') or result.get('error'))
        while True:
            time.sleep(motor_refresh_time)
            update = send_request(
                host=server_ip,
                port=server_port,
                command='get_position',
                arguments=[self.serial_no]
            )
            if 'error' in update:
                print('Error:', update['error'])
                break
            print(
                f"Motor {self.serial_no} position: {update['position']} | Moving: {update['moving']}"
            )
            if not update['moving']:
                break
        return True
    
    def move_to(
            self,
            position: float,
            acceleration: float = thorlabs_motor.MAX_ACCELERATION,
            max_velocity: float = thorlabs_motor.MAX_VELOCITY
    ) -> bool:
        result = send_request(
            host=self.ip_addr,
            port=self.port,
            command='move_to',
            arguments=[self.serial_no, position]
        )
        print('Command sent:', result.get('status') or result.get('error'))
        while True:
            time.sleep(motor_refresh_time)
            update = send_request(
                host=server_ip,
                port=server_port,
                command='get_position',
                arguments=[self.serial_no]
            )
            if 'error' in update:
                print('Error:', update['error'])
                break
            print(
                f"Motor {self.serial_no} position: {update['position']} | Moving: {update['moving']}"
            )
            if not update['moving']:
                break
        return True
    
    def jog(
            self,
            direction: thorlabs_motor.MotorDirection,
            acceleration: float = thorlabs_motor.MAX_ACCELERATION,
            max_velocity: float = thorlabs_motor.MAX_VELOCITY
    ) -> None:
        result = send_request(
            host=self.ip_addr,
            port=self.port,
            command='jog',
            arguments=[self.serial_no, direction.value]
        )
        print("Command sent:", result.get("status") or result.get("error"))

    def stop(self) -> None:
        result = send_request(
            host=self.ip_addr,
            port=self.port,
            command='stop',
            arguments=[self.serial_no]
        )
        print("Command sent:", result.get("status") or result.get("error"))
        
def main():
    motor = RemoteMotor(
        serial_number='55353314',
        ip_addr=server_ip,
        port=server_port
    )
    motor.move_by(angle=45)
    time.sleep(0.1)
    motor.move_to(
        position=0
    )


if __name__ == '__main__':
    # main()
    result = send_request(
        host=server_ip,
        port=server_port,
        command='list_motors'
    )
    motors: list[str] = result.get('motors')
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
                        direction = thorlabs_motor.MotorDirection.FORWARD
                    case '2':
                        direction = thorlabs_motor.MotorDirection.BACKWARD
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
        