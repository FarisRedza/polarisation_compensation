import sys
import os
import socket
import struct
import tomtag as tomt
import numpy as np
sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.timetagger as timetagger
# import bb84.uqd as uqd
# import bb84.qutag as qutag
import server_struct.remote_measurement_server as remote_measurement_server

server_host = '127.0.0.1'
# server_host = '137.195.89.222'
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
        # self._sock.connect((self.host, self.port))
        # self._get_device_info()

    def __del__(self) -> None:
        self.disconnect()

    def measure(self) -> timetagger.RawData:

        return timetagger.RawData(timetags = np.cumsum(np.random.randint(0, 300, size=1000)), channels = np.random.randint(0, 8, size=1000)) 
        # self._send_command(
        #     command=remote_measurement_server.Command.MEASURE_ONCE
        # )
        # resp_type, payload = self._receive_response()
        # if resp_type == remote_measurement_server.Response.RAWDATA:
        #     return timetagger.RawData.deserialise(
        #         payload=payload
        #     )
        # else:
        #     print('Unexpected response:', resp_type)

    def disconnect(self) -> None:
        self._sock.close()

    def _get_device_info(self) -> None:
        self._send_command(
            command=remote_measurement_server.Command.LIST_DEVICES
        )
        resp_type, payload = self._receive_response()
        if resp_type == remote_measurement_server.Response.DEVICE_INFO:
            self.device_info=timetagger.DeviceInfo.deserialise(
                payload=payload
            )
        else:
            print('Unexpected response:', resp_type)

    def _send_command(
            self,
            command: remote_measurement_server.Command
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

    def _receive_response(self):
        header = self._recvall(size=5)
        total_len, resp_type = struct.unpack('IB', header)
        payload = self._recvall(total_len - 1)
        return resp_type, payload


def get_qber(channels, timetags, delay=1642, tcc=15):
    """
    Assume that channels are HVDAHVDA
    """
    tags_H_1550 = timetags[channels == 0]
    tags_V_1550 = timetags[channels == 1]
    tags_D_1550 = timetags[channels == 2]
    tags_A_1550 = timetags[channels == 3]
    tags_H_780 = timetags[channels == 4] + delay
    tags_V_780 = timetags[channels == 5] + delay
    tags_D_780 = timetags[channels == 6] + delay
    tags_A_780 = timetags[channels == 7] + delay

    HH = tomt.count_twofolds(tags_H_1550, tags_H_780, len(tags_H_1550), len(tags_H_780),tcc)
    HV = tomt.count_twofolds(tags_H_1550, tags_V_780, len(tags_H_1550), len(tags_V_780),tcc)
    VH = tomt.count_twofolds(tags_V_1550, tags_H_780, len(tags_V_1550), len(tags_H_780),tcc)
    VV = tomt.count_twofolds(tags_V_1550, tags_V_780, len(tags_V_1550), len(tags_V_780),tcc)

    qber =  (VH + VH) / (HH + HV + VH + VV)

    DD = tomt.count_twofolds(tags_D_1550, tags_D_780, len(tags_D_1550), len(tags_D_780),tcc)
    DA = tomt.count_twofolds(tags_D_1550, tags_A_780, len(tags_D_1550), len(tags_A_780),tcc)
    AD = tomt.count_twofolds(tags_A_1550, tags_D_780, len(tags_A_1550), len(tags_D_780),tcc)
    AA = tomt.count_twofolds(tags_A_1550, tags_V_780, len(tags_A_1550), len(tags_A_780),tcc)

    qx =  (DA + AD) / (DD + AD + DA + AA)

    return qber, qx, HH+HV+VH+VV

if __name__ == '__main__':
    import time
    import numpy
    tt = Timetagger(
        host=server_host,
        port=server_port
    )
    # print(tt.device_info)
    for _ in range(10):
        raw_data = tt.measure()
        singles = numpy.bincount(raw_data.channels, minlength=8)
        print('singles:', singles)
        print('qber, qx, rawCC:', get_qber(raw_data.channels, raw_data.timetags))

        time.sleep(1)