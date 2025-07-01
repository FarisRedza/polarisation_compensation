import sys
import os
import socket
import threading
import json
import dataclasses
import time
import struct

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.thorlabs_polarimeter as thorlabs_polarimeter


def handle_client(connection: socket.socket, address) -> None:
    print(f'Connected by {address}')
    streaming = False
    stop_event = threading.Event()

    def stream_measurements(
            sleep_time = 0.1
    ) -> None:
        while not stop_event.is_set():
            try:
                rawdata = pax.measure()
                response = {'rawdata': dataclasses.asdict(rawdata)}
                connection.sendall((json.dumps(response) + '\n').encode())
                time.sleep(sleep_time)
            except Exception as e:
                error = {'error': f'Measurement error: {str(e)}'}
                connection.sendall((json.dumps(error) + '\n').encode())
                break

    stream_thread = None

    with connection:
        try:
            while True:
                data = connection.recv(1024).decode()
                if not data:
                    break

                request = json.loads(data)
                command = str(request['command'])
                print(f'Command received from {address}: {command}')

                match command:
                    case 'list_devices':
                        response = {
                            'devices': [dataclasses.asdict(pax.device_info)]
                        }

                    case 'measure':
                        response = {
                            'rawdata': dataclasses.asdict(pax.measure())
                        }

                    case 'start_measuring':
                        if not streaming:
                            stop_event.clear()
                            stream_thread = threading.Thread(
                                target=stream_measurements,
                                daemon=True
                            )
                            stream_thread.start()
                            streaming = True
                            response = {'status': 'streaming started'}
                        else:
                            response = {'status': 'already streaming'}

                    case 'stop_measuring':
                        if streaming:
                            stop_event.set()
                            if stream_thread:
                                stream_thread.join()
                            streaming = False
                            response = {'status': 'streaming stopped'}
                        else:
                            response = {'status': 'not streaming'}

                    case _:
                        response = {'error': 'Unknown command'}

                print(f'Sending response to {address}: {response}')
                connection.sendall((json.dumps(response) + '\n').encode())
        
        except ConnectionResetError:
            print(f'Connection lost with {address}')
        
        finally:
            connection.close()
            print(f'Disconnected from {address}')


def start_server(host: str = '0.0.0.0', port: int = 5003) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind((host, port))
        server.listen()
        print(f'Polarimeter server listening on {host}:{port}')
        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            ).start()
    except KeyboardInterrupt:
        print("Server shutting down.")
        pax.disconnect()
        server.close()


if __name__ == '__main__':
    pax = thorlabs_polarimeter.Polarimeter(
        serial_number='M00910360'
    )
    start_server()
