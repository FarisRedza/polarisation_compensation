import sys
import os
import socket
import time
import struct
import enum

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.thorlabs_polarimeter as thorlabs_polarimeter

server_host = '127.0.0.1'
# server_host = '137.195.89.222'
server_port = 5003

def parse_status(payload: bytes) -> str:
    message_len = struct.unpack('I', payload[:4])[0]
    message = struct.unpack(f'{message_len}s', payload[4:])[0]
    return bytes(message).decode()

class Command(enum.IntEnum):
    LIST_DEVICES = 1
    MEASURE_ONCE = 2
    START_MEASURING = 3
    STOP_MEASURING = 4

class Response(enum.IntEnum):
    ERROR = 0
    DEVICE_INFO = 1
    RAWDATA = 2
    STATUS = 3

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

    def __del__(self):
        self._sock.close()

    def measure(self) -> thorlabs_polarimeter.RawData:
        self._send_command(Command.MEASURE_ONCE)
        resp_type, payload = self._receive_response()
        if resp_type == Response.RAWDATA:
            return thorlabs_polarimeter.RawData.deserialise(
                payload=payload)
        else:
            print('Unexpected response:', resp_type)

    def start_measuring(self):
        self._send_command(Command.START_MEASURING)
        resp_type, payload = self._receive_response()
        print('Start:', payload.decode())

        # for _ in range(3):
        #     resp_type, payload = self._receive_response()
        #     if resp_type == Response.RAWDATA:
        #         print(
        #             thorlabs_polarimeter.RawData.deserialise(payload=payload).wavelength
        #         )
        #     elif resp_type == Response.ERROR:
        #         print('Error:', parse_status(payload))
        #         break

        self._send_command(Command.STOP_MEASURING)
        resp_type, payload = self._receive_response()
        print('Stop:', payload.decode())

    def disconnect(self):
        self._sock.close()

    def _get_device_info(
            self,
            serial_number: str
        ) -> None:
        self._send_command(cmd_id=Command.LIST_DEVICES)
        resp_type, payload = self._receive_response()
        if resp_type == Response.DEVICE_INFO:
            self.device_info=thorlabs_polarimeter.DeviceInfo.deserialise(
                payload=payload
            )
        else:
            print('Unexpected response:', resp_type)

    def _send_command(self, cmd_id: Command):
        self._sock.sendall(struct.pack('I', cmd_id))

    def _recvall(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            part = self._sock.recv(size - len(data))
            if not part:
                raise ConnectionError('Socket closed')
            data.extend(part)
        return data

    def _receive_response(self):
        header = self._recvall(size=5)
        total_len, resp_type = struct.unpack('IB', header)
        payload = self._recvall(total_len - 1)
        return resp_type, payload

if __name__ == '__main__':
    pax = Polarimeter(
        host='127.0.0.1',
        port=5003,
        serial_number='M00910360'
    )
    print(pax.device_info)
    time.sleep(1)
    pax.start_measuring()
    pax.disconnect()