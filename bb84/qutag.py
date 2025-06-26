import sys
import os
import time

import numpy

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.timetagger as timetagger
import quTAG.QuTAG_HR as QuTAG_HR

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

    def __del__(self):
        self._qutag.deInitialize()

    def measure(self) -> timetagger.RawData:
        data = timetagger.RawData()
        
        self._qutag.getLastTimestamps(reset=True)
        time.sleep(0.1)
        tags, channels, valid = self._qutag.getLastTimestamps(
            reset=True
        )

        singles = numpy.bincount(channels, minlength=8)[4:]

        data.singles_780_h=int(singles[timetagger.C_780_H])
        data.singles_780_v=int(singles[timetagger.C_780_V])
        # data.singles_d=int(singles[timetagger.C_D])
        # data.singles_a=int(singles[timetagger.C_A])
        data.singles_780_r=int(singles[timetagger.C_780_R])
        data.singles_780_l=int(singles[timetagger.C_780_L])

        return data

if __name__ == '__main__':
    qutag = Qutag()

    for _ in range(10):
        time.sleep(0.1)
        print(qutag.measure().to_data())

    qutag._qutag.deInitialize()