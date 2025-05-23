import sys
import os
import socket
import threading
import json

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import motor.motor as thorlabs_motor

def handle_client(conn: socket.socket, addr) -> None:
    print(f'Connected by {addr}')
    with conn:
        while True:
            try:
                data = conn.recv(1024).decode()
                if not data:
                    break
                
                request = json.loads(data)
                command = str(request.get('command'))
                match command:
                    case 'list_motors':
                        motor_list = [motor.serial_no for motor in motors]
                        response = {'motors': motor_list}

                    case 'get_position':
                        serial_number = str(request.get('serial_number'))

                        motor = next(
                            (m for m in motors if m.serial_no == serial_number),
                            None
                        )
                        if motor == None:
                            response = {'error': f'Motor {serial_number} not found'}
                        else:
                            response = {
                                'position': motor.position,
                                'moving': motor.is_moving
                            }

                    case 'move_by':
                        serial_number = str(request.get('serial_number'))
                        angle = float(request.get('angle', 0))
                        acceleration = float(request.get('acceleration', thorlabs_motor.MAX_ACCELERATION))
                        max_velocity = float(request.get('max_velocity', thorlabs_motor.MAX_VELOCITY))

                        motor = next(
                            (m for m in motors if m.serial_no == serial_number),
                            None
                        )
                        if motor == None:
                            response = {'error': f'Motor {serial_number} not found'}
                        else:
                            motor.threaded_move_by(
                                angle=angle,
                                acceleration=acceleration,
                                max_velocity=max_velocity
                            )
                            response = {'status': f'Moving {serial_number} by {angle}'}

                    case 'move_to':
                        serial_number = str(request.get('serial_number'))
                        position = float(request.get('position', 0))
                        acceleration = float(request.get('acceleration', thorlabs_motor.MAX_ACCELERATION))
                        max_velocity = float(request.get('max_velocity', thorlabs_motor.MAX_VELOCITY))

                        motor = next(
                            (m for m in motors if m.serial_no == serial_number),
                            None
                        )
                        if motor == None:
                            response = {'error': f'Motor {serial_number} not found'}
                        else:
                            motor.threaded_move_to(
                                position=position,
                                acceleration=acceleration,
                                max_velocity=max_velocity
                            )
                            response = {'status': f'Moving {serial_number} to {position}'}

                    case 'jog':
                        serial_number = str(request.get('serial_number'))
                        direction = thorlabs_motor.MotorDirection(
                            request.get(
                                'direction',
                                None
                            ),
                        )

                        motor = next(
                            (m for m in motors if m.serial_no == serial_number),
                            None
                        )
                        if motor == None:
                            response = {'error': f'Motor {serial_number} not found'}
                        else:
                            motor.jog(
                                direction=direction
                            )
                            response = {'status': f'Moving {serial_number} {direction.name}'}

                    case 'stop':
                        serial_number = str(request.get('serial_number'))
                        motor = next(
                            (m for m in motors if m.serial_no == serial_number),
                            None
                        )
                        if motor == None:
                            response = {'error': f'Motor {serial_number} not found'}
                        else:
                            motor.stop()
                            response = {'status': f'Stopping {serial_number}'}

                    case _:
                        response = {'error': 'Unkown command'}

                conn.sendall(json.dumps(response).encode())

            except Exception as e:
                conn.sendall(json.dumps({'error': str(e)}).encode())
                break

def start_server(host: str = '0.0.0.0', port: int = 5002) -> None:
    server = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM
    )
    server.bind((host, port))
    server.listen()
    print(f'Motor server listening on {host}:{port}')
    while True:
        conn, addr = server.accept()
        threading.Thread(
            target=handle_client,
            args=(conn, addr),
            daemon=True
        ).start()

if __name__ == '__main__':
    motors = thorlabs_motor.get_motors()
    start_server()