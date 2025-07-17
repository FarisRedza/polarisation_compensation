import socket
import struct
import typing
import time

import numpy

from . import timetagger
from . import remote_protocol

server_host = '127.0.0.1'
server_host = '137.195.63.6'
server_port = 5003

def parse_status(payload: bytes) -> str:
    message_len = struct.unpack('I', payload[:4])[0]
    message = struct.unpack(f'{message_len}s', payload[4:])[0]
    return bytes(message).decode()

class Timetagger(timetagger.TimeTagger):
    def __init__(
            self,
            host: str,
            port: int
    ) -> None:
        self.host = host
        self.port = port

        self._sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        self._sock.connect((self.host, self.port))
        self._get_device_info()

    def __del__(self) -> None:
        self.disconnect()

    def measure(self, seconds: int = 1) -> timetagger.RawData:
        self._send_command(
            command=remote_protocol.Command.MEASURE_ONCE
        )
        resp_type, payload = self._receive_response()
        if resp_type == remote_protocol.Response.RAWDATA:
            return timetagger.RawData.deserialise(
                payload=payload
            )
        else:
            print('Unexpected response:', resp_type)
            return timetagger.RawData(
                timetags=numpy.empty(0),
                channels=numpy.empty(0)
            )

    def disconnect(self) -> None:
        self._sock.close()

    def get_network_delay(self) -> float:
        connect_request_time = time.time()
        self._send_command(
            command=remote_protocol.Command.NETWORK_DELAY
        )
        resp_type, payload = self._receive_response()
        if resp_type == remote_protocol.Response.TIME:
            remote_time = struct.unpack(payload)


    def _get_device_info(self) -> None:
        self._send_command(
            command=remote_protocol.Command.LIST_DEVICES
        )
        resp_type, payload = self._receive_response()
        if resp_type == remote_protocol.Response.DEVICE_INFO:
            self.device_info=timetagger.DeviceInfo.deserialise(
                payload=payload
            )
        else:
            print('Unexpected response:', resp_type)

    def _send_command(
            self,
            command: remote_protocol.Command
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

    def _receive_response(self) -> tuple[typing.Any, bytes]:
        header = self._recvall(size=5)
        total_len, resp_type = struct.unpack('IB', header)
        payload = self._recvall(total_len - 1)
        return resp_type, payload

if __name__ == '__main__':
    tt = Timetagger(
        host=server_host,
        port=server_port
    )
    print(tt.device_info)
    # for _ in range(10):
    #     raw_data = tt.measure()
    #     # print(timetagger.Data.from_raw_data(raw_data=raw_data))
    #     # singles = numpy.bincount(raw_data.channels, minlength=8)
    #     # print(singles)
    #     pprint.pprint(raw_data)
    #     time.sleep(1)