import time

from . import timetagger
from ..quTAG import QuTAG_HR

class Qutag(timetagger.TimeTagger):
    def __init__(self):
        self._qutag = QuTAG_HR.QuTAG()
        for channel in range(4, 9):
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

    def __del__(self) -> None:
        self._qutag.deInitialize()

    def measure(self) -> timetagger.RawData:        
        self._qutag.getLastTimestamps(reset=True)
        time.sleep(0.1)
        timetags, channels, valid = self._qutag.getLastTimestamps(
            reset=True
        )
        raw_data = timetagger.RawData(
            timetags=timetags,
            channels=channels
        )
        return raw_data

if __name__ == '__main__':
    qutag = Qutag()

    for _ in range(10):
        time.sleep(0.1)
        print(qutag.measure().to_data())

    qutag._qutag.deInitialize()