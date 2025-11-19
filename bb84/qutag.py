import sys
import pathlib
import time

import numpy

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from bb84 import timetagger
from quTAG import QuTAG_HR

class Qutag(timetagger.TimeTagger):
    def __init__(self) -> None:
        qutag = QuTAG_HR.QuTAG()
        # dev_nr seems to always be -1 now, problem with new firmware?
        # if qutag.dev_nr == -1:
        #     raise RuntimeError('Qutag not found')
        # else:
        #     self._qutag = qutag
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

        self.flush()

    def __del__(self) -> None:
        if hasattr(self, '_qutag'):
            self._qutag.deInitialize()


    def flush(self):
        self._qutag.getLastTimestamps(reset=True)
        
    def measure(self, seconds: int = 1) -> timetagger.RawData:    
        time.sleep(seconds)
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
    
def list_devices() -> list[Qutag]:
    # will expand on this later, but needed now for compat
    try:
        qt = Qutag()
    except:
        return []
    else:
        return [qt]

if __name__ == '__main__':
    qutag = Qutag()

    tt_reset, *_ = qutag._qutag.getLastTimestamps(
            reset=True
        )
    print(tt_reset)

    tt, *_ = qutag._qutag.getLastTimestamps(
            reset=False
        )
    print(tt)

    # for _ in range(10):
    #     time.sleep(0.1)
    #     pprint.pprint(timetagger.Data().from_raw_data(
    #         raw_data=qutag.measure()
    #     ))