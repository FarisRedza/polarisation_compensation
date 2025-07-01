import sys
import os
import socket
import time
import threading
import struct

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.thorlabs_polarimeter as thorlabs_polarimeter
import server_struct.remote_polarimeter as remote_polarimeter

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
    streaming = False
    stop_event = threading.Event()
    stream_thread = None

    def stream_measurements():
        while not stop_event.is_set():
            try:
                time.sleep(1)
                rawdata = pax.measure()
                print(rawdata)
                payload = rawdata.serialise()
                header = struct.pack(
                    'IB',
                    len(payload) + 1,
                    remote_polarimeter.Response.RAWDATA
                )
                connection.sendall(header + payload)
            except Exception as e:
                error_msg = str(e).encode()
                payload = struct.pack(
                    f'I{len(error_msg)}s',
                    len(error_msg),
                    error_msg
                )
                header = struct.pack(
                    'IB',
                    len(payload) + 1,
                    remote_polarimeter.Response.ERROR
                )
                connection.sendall(header + payload)
                break

    with connection:
        try:
            while True:
                cmd_data = connection.recv(4)
                if not cmd_data:
                    break

                command = struct.unpack('I', cmd_data)[0]
                print(remote_polarimeter.Command(command).name)

                match remote_polarimeter.Command(command):
                    case remote_polarimeter.Command.LIST_DEVICES:
                        payload = pax.device_info.serialise()
                        header = struct.pack(
                            'IB',
                            len(payload) + 1,
                            remote_polarimeter.Response.DEVICE_INFO
                        )
                        connection.sendall(header + payload)

                    case remote_polarimeter.Command.MEASURE_ONCE:
                        payload = pax.measure().serialise()
                        header = struct.pack(
                            'IB',
                            len(payload) + 1,
                            remote_polarimeter.Response.RAWDATA
                        )
                        connection.sendall(header + payload)

                    case remote_polarimeter.Command.START_MEASURING:
                        if not streaming:
                            stop_event.clear()
                            stream_thread = threading.Thread(
                                target=stream_measurements,
                                daemon=True
                            )
                            stream_thread.start()
                            streaming = True
                            message = 'started measuring'
                        else:
                            message = 'already measuring'
                        
                        payload = pack_status(message=message)
                        header = struct.pack(
                            'IB',
                            len(payload) + 1,
                            remote_polarimeter.Response.STATUS
                        )

                    case remote_polarimeter.Command.STOP_MEASURING:
                        if streaming:
                            stop_event.set()
                            if stream_thread:
                                stream_thread.join()
                            streaming = False
                            message = 'stopped measuring'
                        else:
                            message = 'not measuring'
                        
                        payload = pack_status(message=message)
                        header = struct.pack(
                            'IB',
                            len(payload) + 1,
                            remote_polarimeter.Response.STATUS
                        )

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
                            remote_polarimeter.Response.ERROR
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
        print(f'Polarimeter server listening on {host}:{port}')
        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr)
            ).start()
    except KeyboardInterrupt:
        server.close()
        pax.disconnect()

if __name__ == '__main__':
    pax = thorlabs_polarimeter.Polarimeter(
        serial_number='M00910360'
    )
    start_server()