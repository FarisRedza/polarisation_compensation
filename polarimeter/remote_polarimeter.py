import sys
import os
import socket
import struct

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.thorlabs_polarimeter as thorlabs_polarimeter
import polarimeter.remote_polarimeter_protocol as remote_polarimeter_protocol

server_host = '127.0.0.1'
server_host = '137.195.89.222'
server_port = 5003

def parse_status(payload: bytes) -> str:
    message_len = struct.unpack('I', payload[:4])[0]
    message = struct.unpack(f'{message_len}s', payload[4:])[0]
    return bytes(message).decode()

class Polarimeter(thorlabs_polarimeter.Polarimeter):
    def __init__(
            self,
            host: str,
            port: int,
            serial_number: str
    ) -> None:
        self.host = host
        self.port = port

        self._sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        self._sock.connect((self.host, self.port))
        self._get_device_info(serial_number=serial_number)

    def __del__(self) -> None:
        self.disconnect()

    def measure(self) -> thorlabs_polarimeter.RawData:
        self._send_command(
            command=remote_polarimeter_protocol.Command.MEASURE_ONCE
        )
        resp_type, payload = self._receive_response()
        if resp_type == remote_polarimeter_protocol.Response.RAWDATA:
            return thorlabs_polarimeter.RawData.deserialise(
                payload=payload
            )
        else:
            print('Unexpected response:', resp_type)

    def disconnect(self) -> None:
        self._sock.close()

    def _get_device_info(
            self,
            serial_number: str
    ) -> None:
        self._send_command(
            command=remote_polarimeter_protocol.Command.LIST_DEVICES
        )
        resp_type, payload = self._receive_response()
        if resp_type == remote_polarimeter_protocol.Response.DEVICE_INFO:
            self.device_info=thorlabs_polarimeter.DeviceInfo.deserialise(
                payload=payload
            )
        else:
            print('Unexpected response:', resp_type)

    def _send_command(
            self,
            command: remote_polarimeter_protocol.Command
        ) -> None:
        self._sock.sendall(struct.pack('I', command))

    def _recvall(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            part = self._sock.recv(size - len(data))
            if not part:
                raise ConnectionError('Socket closed')
            data.extend(part)
        return data

    def _receive_response(self) -> tuple[int, bytes]:
        header = self._recvall(size=5)
        total_len, resp_type = struct.unpack('IB', header)
        payload = self._recvall(total_len - 1)
        return resp_type, payload

if __name__ == '__main__':
    pax = Polarimeter(
        host=server_host,
        port=server_port,
        serial_number='M00910360'
    )
    print(pax.device_info)