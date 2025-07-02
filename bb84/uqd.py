import sys
import os
import pathlib

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.timetagger as timetagger

os.environ['TTAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'ttag',
    'python'
))
# sys.path.append(os.environ['TTAG'])
# import ttag.python.ttag as libttag

os.environ['TIMETAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'timetag',
    'python'
))
# sys.path.append(os.environ['TIMETAG'])
# import timetag.python.timetag as libtimetag

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import ttag.python.ttag as ttag
import timetag.python.timetag as timetag

class UQD(timetagger.TimeTagger):
    def __init__(self):
        # self._uqd = ttag.TTBuffer(buffernumber=ttag.getfreebuffer()-1)
        self._uqd = timetag.CTimeTag()

        self.device_info = timetagger.DeviceInfo(
            manufacturer = 'UQDevices',
            model = 'Logic-16',
            serial_number = 'N/A',
            firmware_version = 'N/A'
        )

        self._uqd.Open()

    def __del__(self) -> None:
        if self._uqd.IsOpen():
            self._uqd.Close()

    def measure(self) -> timetagger.RawData:
        self._uqd.StartTimetags()
        channels, timetags = self._uqd.ReadTags()
        raw_data = timetagger.RawData(
            timetags=timetags,
            channels=channels
        )
        self._uqd.StopTimetags()
        return raw_data

        # data = timetagger.RawData()
        # print(self._uqd.singles(0.1))
        # singles = self._uqd.singles(1)

        # data.singles_780_h=int(singles[timetagger.C_780_H])
        # data.singles_780_v=int(singles[timetagger.C_780_V])
        # # data.singles_780_d=int(singles[timetagger.C_780_D])
        # # data.singles_780_a=int(singles[timetagger.C_780_A])
        # data.singles_780_r=int(singles[timetagger.C_780_R])
        # data.singles_780_l=int(singles[timetagger.C_780_L])

        # data.singles_1550_h=int(singles[timetagger.C_1550_H])
        # data.singles_1550_v=int(singles[timetagger.C_1550_V])
        # # data.singles_1550_d=int(singles[timetagger.C_1550_D])
        # # data.singles_1550_a=int(singles[timetagger.C_1550_A])
        # data.singles_1550_r=int(singles[timetagger.C_1550_R])
        # data.singles_1550_l=int(singles[timetagger.C_1550_L])

        # return data
    
if __name__ == '__main__':
    import time
    tt = UQD()
    raw_data = tt.measure()
    print(raw_data)
    print(len(raw_data.channels))