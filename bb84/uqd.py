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

    def measure(self) -> timetagger.RawData:
        data = timetagger.RawData()

        singles = self._uqd.singles(1)[0:4]

        data.singles_h=int(singles[timetagger.C_H])
        data.singles_v=int(singles[timetagger.C_V])
        # data.singles_d=int(singles[timetagger.C_D])
        # data.singles_a=int(singles[timetagger.C_A])
        data.singles_r=int(singles[timetagger.C_R])
        data.singles_l=int(singles[timetagger.C_L])

        return data
        