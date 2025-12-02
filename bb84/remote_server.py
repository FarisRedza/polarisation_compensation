import sys
import pathlib
import socket
import threading
import struct

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from bb84 import remote_protocol
from bb84 import uqd
from bb84 import qutag

def recvall(size: int, sock: socket.socket) -> bytes:
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise ConnectionError('Socket closed')
        data.extend(part)
    return data

def receive_command(
        sock: socket.socket
) -> tuple[remote_protocol.Command, list]:
    header = recvall(size=8, sock=sock)
    command_id, num_args = struct.unpack('II', header)

    try:
        command = remote_protocol.Command(command_id)
    except ValueError:
        raise ValueError(f'Invalid command ID: {command_id}')

    args = []    
    for _ in range(num_args):
        arg_len = struct.unpack('I', recvall(size=4, sock=sock))[0]
        arg = recvall(size=arg_len, sock=sock)
        args.append(arg.decode(encoding='utf-8'))

    return command, args

def send_message(
        sock: socket.socket,
        message: str,
        response_id: remote_protocol.Response
) -> None:
    payload = struct.pack(
        f'I{len(message)}s',
        len(message),
        message.encode(encoding='utf-8')
    )
    header = struct.pack(
        'IB',
        len(payload) + 1,
        response_id
    )
    sock.sendall(header + payload)

def send_payload(
        sock: socket.socket,
        payload: bytes,
        response_id: remote_protocol.Response
) -> None:
    header = struct.pack('IB', len(payload) +1, response_id)
    sock.sendall(header + payload)

def handle_client(
        sock: socket.socket,
        address
) -> None:
    with sock:
        try:
            while True:
                try:
                    command, args = receive_command(sock=sock)
                except (ValueError, ConnectionError) as e:
                    print(f'[{address}] Disconnected: {e}')
                    break

                if command == remote_protocol.Command.LIST_DEVICES:
                    dev_infos = [dev.device_info.serialise() for dev in devices]
                    payload = struct.pack('I', len(dev_infos))

                    for info in dev_infos:
                        payload += struct.pack('I', len(info)) + info

                    send_payload(
                        sock=sock,
                        payload=payload,
                        response_id=remote_protocol.Response.LIST_DEVICES
                    )

                elif args:
                    model = str(args[0])
                    device = next(
                        (d for d in devices if d.device_info.model == model),
                        None
                    )
                    if not device:
                        send_message(
                            sock=sock,
                            message=f'Device {model} not found',
                            response_id=remote_protocol.Response.ERROR
                        )
                        continue

                    match command:
                        case remote_protocol.Command.DEVICE_INFO:
                            send_payload(
                                sock=sock,
                                payload=device.device_info.serialise(),
                                response_id=remote_protocol.Response.DEVICE_INFO
                            )

                        case remote_protocol.Command.MEASURE:
                            seconds = float(args[1])
                            send_payload(
                                sock=sock,
                                payload=device.measure(seconds=seconds).serialise(),
                                response_id=remote_protocol.Response.RAWDATA
                            )

                        case _:
                            send_message(
                                sock=sock,
                                message=f'Unsupported command: {command}',
                                response_id=remote_protocol.Response.ERROR
                            )

                else:
                    send_message(
                        sock=sock,
                        message=f'No arguments provided',
                        response_id=remote_protocol.Response.ERROR    
                    )

        except Exception as e:
            print(f'[{address}] Unexpected error: {e}')
        finally:
            print(f'Disconnected from {address}')

def start_server(
        host: str = '0.0.0.0',
        port: int = 5001
) -> None:
    sock = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM
    )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen()
    print(f'Measurement server listening on {host}:{port}')
    try:
        while True:
            conn, addr = sock.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            ).start()

    except KeyboardInterrupt:
        print('Measurement server shutting down')
    finally:
        sock.close()
        for dev in devices:
            dev.disconnect()

if __name__ == '__main__':
    devices = uqd.list_devices() + qutag.list_devices()
    start_server()