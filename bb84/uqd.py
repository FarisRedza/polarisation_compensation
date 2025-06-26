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
sys.path.append(os.environ['TTAG'])
import ttag as tt

os.environ['TIMETAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'timetag',
    'python'
))
sys.path.append(os.environ['TIMETAG'])
import timetag

class UQD(timetagger.TimeTagger):
    def __init__(self):
        self._uqd = tt.TTBuffer(buffernumber=tt.getfreebuffer()-1)

        self.device_info = timetagger.DeviceInfo(
            manufacturer = 'UQDevices',
            model = 'Logic-16',
            serial_number = 'N/A',
            firmware_version = 'N/A'
        )

    def measure(self) -> timetagger.RawData:
        data = timetagger.RawData()

        singles = self._uqd.singles(1)

        data.singles_780_h=int(singles[timetagger.C_780_H])
        data.singles_780_v=int(singles[timetagger.C_780_V])
        # data.singles_780_d=int(singles[timetagger.C_780_D])
        # data.singles_780_a=int(singles[timetagger.C_780_A])
        data.singles_780_r=int(singles[timetagger.C_780_R])
        data.singles_780_l=int(singles[timetagger.C_780_L])

        data.singles_1550_h=int(singles[timetagger.C_1550_H])
        data.singles_1550_v=int(singles[timetagger.C_1550_V])
        # data.singles_1550_d=int(singles[timetagger.C_1550_D])
        # data.singles_1550_a=int(singles[timetagger.C_1550_A])
        data.singles_1550_r=int(singles[timetagger.C_1550_R])
        data.singles_1550_l=int(singles[timetagger.C_1550_L])

        return data
        