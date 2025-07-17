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
import timetag.python.timetag as timetag

class UQD(timetagger.TimeTagger):
    def __init__(self) -> None:
        self._uqd = ttag.TTBuffer(buffernumber=ttag.getfreebuffer()-1)
        # self._uqd = timetag.CTimeTag()


        self.device_info = timetagger.DeviceInfo(
            manufacturer = 'UQDevices',
            model = 'Logic-16',
            serial_number = 'N/A',
            firmware_version = 'N/A'
        )

        # self._uqd.Open()

    # def __del__(self) -> None:
        # if self._uqd.IsOpen():
        #     self._uqd.Close()

    def measure(self, seconds: int = 1) -> timetagger.RawData:
        # self._uqd.StartTimetags()
        # channels, timetags = self._uqd.ReadTags()
        channels, timetags = self._uqd(seconds)
        channels, timetags = self._uqd()
        raw_data = timetagger.RawData(
            timetags=timetags,
            channels=channels
        )
        # self._uqd.StopTimetags()
        return raw_data
    
if __name__ == '__main__':
    tt = UQD()
    raw_data = tt.measure()
    print(raw_data)
    print(len(raw_data.channels))