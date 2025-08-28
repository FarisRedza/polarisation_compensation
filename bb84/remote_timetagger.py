import socket
import struct
import time

from . import timetagger
from . import remote_protocol

def send_command(
        sock: socket.socket,
        command: remote_protocol.Command,
        args : tuple | None = None
) -> None:
    encoded_args = [
        str(arg).encode(encoding='utf-8') for arg in args
    ] if args else []
    payload = struct.pack('II', command, len(encoded_args))

    for arg in encoded_args:
        payload += struct.pack('I', len(arg)) + arg

    sock.sendall(payload)

def recvall(size: int, sock: socket.socket) -> bytes:
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise ConnectionError('Socket closed')
        data.extend(part)
    return data

def receive_response(sock: socket.socket) -> tuple[int, bytes]:
    header = recvall(size=5, sock=sock)
    total_len, response_id = struct.unpack('IB', header)
    try:
        response = remote_protocol.Response(response_id)
    except ValueError:
        raise ValueError(f'Invalid response ID: {response_id}')
    else:
        payload = recvall(
            size=total_len - 1,
            sock=sock
        )
        return response, payload

def list_device_info(
        host: str | None = None,
        port: int | None = None,
        sock: socket.socket | None = None
) -> list[timetagger.DeviceInfo]:
    if sock:
        host, port = sock.getpeername()
    elif host and port:
        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        sock.settimeout(5)
        sock.connect((host, port))
    else:
        raise ValueError('Must provide either a socket or host and port')

    send_command(
        sock=sock,
        command=remote_protocol.Command.LIST_DEVICES
    )
    response, payload = receive_response(sock=sock)
    
    device_infos = []
    if response == remote_protocol.Response.LIST_DEVICES:
        (num_devices,) = struct.unpack('I', payload[:4])
        offset = 4
        for _ in range(num_devices):
            (length,) = struct.unpack('I', payload[offset: offset + 4])
            offset += 4
            info_bytes = payload[offset:offset + length]
            offset += length
            dev_info = timetagger.DeviceInfo.deserialise(
                payload=info_bytes
            )
            device_infos.append(dev_info)

    else:
        print(f'Unexpected response: {response}')

    return device_infos

class RemoteTimetagger(timetagger.TimeTagger):
    def __init__(
            self,
            model: str,
            host: str | None = None,
            port: int | None = None,
            sock: socket.socket | None = None
    ) -> None:
        if sock:
            self.host, self.port = sock.getpeername()
            self._sock = sock
        elif host and port:
            self.host = host
            self.port = port
            self._sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )
            self._sock.settimeout(5)
            self._sock.connect((self.host, self.port))
        else:
            raise NameError('Must provide either a socket or host and port')
        self._get_device_info(model=model)
        self.channel_groups = timetagger.default_channel_groups
    
    def disconnect(self) -> None:
        self._sock.close()

    def measure(self) -> timetagger.RawData:
        send_command(
            sock=self._sock,
            command=remote_protocol.Command.MEASURE,
            args=(self.device_info.model,)
        )
        payload = self._handle_response(
            expected_response_id=remote_protocol.Response.RAWDATA,
        )
        raw_data = timetagger.RawData.deserialise(
            payload=payload
        )
        return raw_data

    def _handle_response(
            self,
            expected_response_id: remote_protocol.Response
    ) -> bytes:
        response, payload = receive_response(self._sock)

        match response:
            case r if r == expected_response_id:
                return payload
            
            case remote_protocol.Response.ERROR:
                error_msg = payload.decode(encoding='utf-8')
                raise RuntimeError(f'Server error: {error_msg}')
            
            case _:
                raise ValueError(f'Unexpected response: {response}')

    def _get_device_info(
            self,
            model: str
    ) -> None:
        send_command(
            sock=self._sock,
            command=remote_protocol.Command.DEVICE_INFO,
            args=(model,)
        )
        payload = self._handle_response(
            expected_response_id=remote_protocol.Response.DEVICE_INFO,
        )
        self.device_info = timetagger.DeviceInfo.deserialise(
            payload=payload
        )

if __name__ == '__main__':
    tt = RemoteTimetagger(
        model='Logic-16',
        host='137.195.63.6',
        port=5001
    )
    try:
        while True:
            raw_data=tt.measure()
            data = timetagger.Data.from_raw_data(
                raw_data=raw_data,
                channel_groups=timetagger.default_channel_groups
            )
            print(data.qber, data.qx)
            # print(raw_data.timetags[:10])

    except KeyboardInterrupt:
        tt.disconnect()