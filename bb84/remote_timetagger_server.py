import sys
import os
import socket
import threading
import struct

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.remote_timetagger_protocol as remote_timetagger_protocol
import bb84.timetagger as timetagger
import bb84.uqd as uqd
# import bb84.qutag as qutag

def pack_status(message: str):
    b = message.encode()
    return struct.pack(
        f'I{len(b)}s',
        len(b),
        b
    )

def handle_client(
        connection: socket.socket,
        address
) -> None:
    print(f'Connected by {address}')
    with connection:
        try:
            while True:
                cmd_data = connection.recv(4)
                if not cmd_data:
                    break

                command = struct.unpack('I', cmd_data)[0]
                match remote_timetagger_protocol.Command(command):
                    case remote_timetagger_protocol.Command.LIST_DEVICES:
                        payload = measurement_device.device_info.serialise()
                        header = struct.pack(
                            'IB',
                            len(payload) + 1,
                            remote_timetagger_protocol.Response.DEVICE_INFO
                        )
                        connection.sendall(header + payload)

                    case remote_timetagger_protocol.Command.MEASURE_ONCE:
                        payload = measurement_device.measure().serialise()
                        header = struct.pack(
                            'IB',
                            len(payload) + 1,
                            remote_timetagger_protocol.Response.RAWDATA
                        )
                        connection.sendall(header + payload)

                    case _:
                        message = f'Unkown command: {command}'
                        payload = struct.pack(
                            f'I{len(message)}s',
                            len(message),
                            message.encode()
                        )
                        header = struct.pack(
                            'IB',
                            len(payload) + 1,
                            remote_timetagger_protocol.Response.ERROR
                        )
                        connection.sendall(header + payload)

        except ConnectionResetError:
            print(f'Connection lost with {address}')

        finally:
            connection.close()
            print(f'Disconnected from {address}')

def start_server(
        host: str = '0.0.0.0',
        port: int = 5003
) -> None:
    server = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM
    )
    try:
        server.bind((host, port))
        server.listen()

        match type(measurement_device):
            case timetagger.TimeTagger:
                print(f'TimeTagger server listening on {host}:{port}')

            case uqd.UQD:
                print(f'UQD server listening on {host}:{port}')

            # case qutag.Qutag:
            #     print(f'Qutag server listening on {host}:{port}')

            case _:
                print('Unknown device')
                raise TypeError

        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr)
            ).start()
    except KeyboardInterrupt:
        server.close()
        measurement_device.disconnect()

if __name__ == '__main__':
    # measurement_device = timetagger.TimeTagger()
    measurement_device = uqd.UQD()
    start_server()