import sys
import os
import pathlib

import numpy as np

os.environ['TTAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'ttag',
    'python'
))
os.environ['TIMETAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'timetag',
    'python'
))

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from bb84 import timetagger
from ttag.python import ttag 

class UQD(timetagger.TimeTagger):
    def __init__(self, tagsAsTime: bool = False) -> None:
        self._uqd = ttag.TTBuffer(buffernumber=ttag.getfreebuffer()-1)
        self._uqd.tagsAsTime = tagsAsTime
        self.device_info = timetagger.DeviceInfo(
            manufacturer = 'UQDevices',
            model = 'Logic-16',
            serial_number = 'N/A',
            firmware_version = 'N/A'
        )
        self.channel_groups = timetagger.default_channel_groups

    def measure(self) -> timetagger.RawData:
        channels: np.typing.NDArray[np.uint8]
        timetags: np.typing.NDArray[np.uint64]
        channels, timetags = self._uqd(1)
        raw_data = timetagger.RawData(
            timetags=timetags.astype(np.int64),
            channels=channels
        )
        return raw_data

def list_devices() -> list[UQD]:
    # will expand on this later, but needed now for compat
    try:
        tt = UQD()
    except:
        return []
    else:
        return [tt]

if __name__ == '__main__':
    devs = list_devices()
    for d in devs:
        print(d.measure())