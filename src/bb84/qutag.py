import time
import typing

import numpy

from bb84 import timetagger
from quTAG import QuTAG_HR


class Qutag(timetagger.TimeTagger):
    def __init__(self) -> None:
        self._qutag: typing.Optional[QuTAG_HR.QuTAG] = None
        self.clock_offset = 0.0

        qutag = QuTAG_HR.QuTAG()
        if qutag.dev_nr == -1:
            raise RuntimeError('Qutag not found')
        else:
            self._qutag = qutag

        for channel in range(0, 8):
            self._qutag.setSignalConditioning(
                channel=channel,
                conditioning=3,
                edge=True,
                threshold=1
            )
            self._qutag.setChannelDelay(channel=channel, delays=0)
            self._qutag.setExposureTime(expTime=100)

        self.device_info = timetagger.DeviceInfo(
            manufacturer = 'qutools',
            model = 'quTAG',
            serial_number = 'N/A',
            firmware_version = 'N/A'
        )

        self.resolution = 78.125

    def __del__(self) -> None:
        if self._qutag:
            self._qutag.deInitialize()
    
    def flush(self) -> None:
        if self._qutag:
            time.sleep(0.001)
            timetags, *_ = self._qutag.getLastTimestamps(reset=True)
        else:
            RuntimeError('No QuTAG')

    def measure(self, seconds: float = 1.0) -> timetagger.RawData:    
        if self._qutag:
            time.sleep(0.001)
            self._qutag.getLastTimestamps(reset=True)
            time.sleep(seconds)
            timetags, channels, valid = self._qutag.getLastTimestamps(
                reset=True
            )
            self.clock_offset = numpy.max(timetags)
            t_var = seconds * 1e12
            channels = channels[(numpy.max(timetags) - t_var) < timetags]
            timetags = timetags[(numpy.max(timetags) - t_var) < timetags]

            timetags = (
                (timetags - self.clock_offset)//self.resolution
            ).astype(numpy.int64)

            raw_data = timetagger.RawData(
                timetags=timetags,
                channels=channels
            )
            return raw_data
        else:
            RuntimeError('No QuTAG')
    
def list_devices() -> list[Qutag]:
    # will expand on this later, but needed now for compat
    try:
        qt = Qutag()
    except:
        return []
    else:
        return [qt]

if __name__ == '__main__':
    # qutag = Qutag()

    # for _ in range(10):
    #     time.sleep(0.1)
    #     print(timetagger.Data().from_raw_data(
    #         raw_data=qutag.measure()
    #     ))

    # qutag._qutag.deInitialize()
    devs = list_devices()
    print(devs)