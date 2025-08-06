import sys
import os
import pathlib

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

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.timetagger as timetagger
import ttag.python.ttag as ttag

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

    def measure(self) -> timetagger.RawData:
        channels, timetags = self._uqd(1)
        raw_data = timetagger.RawData(
            timetags=timetags,
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
    print(devs[0].measure())