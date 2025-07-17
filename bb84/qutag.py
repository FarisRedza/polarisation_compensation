import time
import sys
import os

import numpy

from . import timetagger

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
from quTAG import QuTAG_HR

class Qutag(timetagger.TimeTagger):
    def __init__(self) -> None:
        self._qutag = QuTAG_HR.QuTAG()
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
        self._qutag.deInitialize()

    def measure(self, seconds: int = 1) -> timetagger.RawData:        
        self._qutag.getLastTimestamps(reset=True)
        time.sleep(1)
        timetags, channels, valid = self._qutag.getLastTimestamps(
            reset=False
        )
        t_var = seconds * 1e12
        channels = channels[(numpy.max(timetags) - t_var) < timetags]
        timetags = timetags[(numpy.max(timetags) - t_var) < timetags]

        timetags = (timetags//self.resolution).astype(numpy.int64)
        raw_data = timetagger.RawData(
            timetags=timetags,
            channels=channels
        )
        return raw_data

if __name__ == '__main__':
    qutag = Qutag()

    for _ in range(10):
        time.sleep(0.1)
        print(timetagger.Data().from_raw_data(
            raw_data=qutag.measure()
        ))

    qutag._qutag.deInitialize()