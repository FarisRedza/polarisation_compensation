import sys
import os
import socket
import threading
import json
import dataclasses

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.timetagger as timetagger
import bb84.qutag as qutag
import bb84.uqd as uqd

def handle_client(connection: socket.socket, address) -> None:
    print(f'Connected by {address}')
    with connection:
        while True:
            try:
                data = connection.recv(1024).decode()
                if not data:
                    break

                request = json.loads(data)
                command = str(request['command'])
                print(f'Command received: {command}')
                match command:
                    case 'list_devices':
                        response = {'devices': [dataclasses.asdict(tt.device_info)]}

                    case 'measure':
                        response = {'rawdata': dataclasses.asdict(tt.measure())}

                    case _:
                        response = {'error': 'Unkown command'}

                print(response)
                connection.sendall((json.dumps(response) + '\n').encode())

            except Exception as e:
                connection.sendall(json.dumps({'error': str(e)}).encode())
                break

def start_server(host: str = '0.0.0.0', port: int = 5003) -> None:
    server = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM
    )
    try:
        server.bind((host, port))
        server.listen()
        print(f'Timetagger server listening on {host}:{port}')
        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr),
                # daemon=True
            ).start()
    except KeyboardInterrupt:
        server.close()

if __name__ == '__main__':
    tt = qutag.Qutag()
    start_server()