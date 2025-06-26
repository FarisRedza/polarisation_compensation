import sys
import os
import socket
import typing
import json

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.timetagger as timetagger

server_host = '127.0.0.1'
# server_host = '137.195.89.222'
server_port = 5003

def send_request(
        host: str,
        port: int,
        command: str,
        arguments: list = [],
        timeout: int = 5
) -> typing.Any:
    request = {'command': command}
    try:
        with socket.create_connection(
            address=(host, port),
            timeout=timeout
        ) as s:
            match command:
                case 'list_devices':
                    pass

                case 'measure':
                    pass

                case _:
                    raise Exception('Unknown command')

            s.sendall(json.dumps(request).encode())
            buffer = ""
            while True:
                data = s.recv(1024).decode()
                if not data:
                    break
                buffer += data
                if "\n" in buffer:
                    break
            response = json.loads(buffer.strip())
            return response

    except Exception as e:
        return {f'Error sending request {request}': str(e)}
    
def list_device_info(
        host: str,
        port: int
) -> list[timetagger.DeviceInfo]:
    result = send_request(
        host=host,
        port=port,
        command='list_devices'
    )
    return [timetagger.DeviceInfo(**dev) for dev in result['devices']]

class Timetagger(timetagger.TimeTagger):
    def __init__(
            self,
            host: str,
            port: int,
    ) -> None:
        self.host = host
        self.port = port

        self._get_timetagger()

    def _get_timetagger(
            self
    ) -> None:
        devices = list_device_info(
            host=self.host,
            port=self.port
        )
        # dev_index = next(
        #     (i for i, dev in enumerate(devices) if str(dev.serial_number) == serial_number),
        #     None
        # )
        # if dev_index is None:
        #     raise Exception
        # else:
        #     self.device_info = devices[dev_index]

        self.device_info = devices[0]

    def measure(self) -> timetagger.RawData:
        result = send_request(
            host=self.host,
            port=self.port,
            command='measure'
        )
        rawdata = timetagger.RawData(**result['rawdata'])
        return rawdata

if __name__ == '__main__':
    tt = Timetagger(
        host=server_host,
        port=server_port
    )
    print(tt.measure().to_data())