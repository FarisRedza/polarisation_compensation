import sys
import os
import pathlib
import time
import subprocess
import typing

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
from timetag.python import timetag

class UQD(timetagger.TimeTagger):
    def __init__(self,headless=False) -> None:
        self._buffer_number: typing.Optional[int] = None
        self._uqdinterface_proc: typing.Optional[subprocess.Popen] = None
        self.clock_offset = 0
        if not headless:
            self._uqd = ttag.TTBuffer(buffernumber=0)
            self._uqd.tagsAsTime = False

            if self._uqd.getrunners() == 0:
                self._uqd.start()
        else:
            self.start_uqdinterface()
            
            
        if self._uqdinterface_proc:
            if self._uqd.getrunners() == 0:
                self._uqd.start()
            else:
                raise RuntimeError('No runners')

        # self._uqd_timetag = timetag.CTimeTag()
        self.device_info = timetagger.DeviceInfo(
            manufacturer = 'UQDevices',
            model = 'Logic-16',
            serial_number = 'N/A',
            firmware_version = 'N/A'
        )
        self.channel_groups = timetagger.default_channel_groups
    
    def clear_buffers(self) -> None:
        for i in range(ttag.getfreebuffer()-1):
            ttag.deletebuffer(i)
        print('CLEARING ALL BUFFERS')
        print(f'FIRST FREE BUFFER IS {ttag.getfreebuffer()}')

    def start_uqdinterface(
            self,
            clear_all_buffers: bool = False,
            dcfile: typing.Optional[pathlib.Path] = None,
            fg_period: typing.Optional[int] = None,
            fg_high: typing.Optional[int] = None
        ) -> None:
        if clear_all_buffers:
            self.clear_buffers()

        self._buffer_number = int(ttag.getfreebuffer())

        uqdinterface_path = pathlib.Path(
            '/home/ap2055/emqTools',
            'ttag',
            'UQD',
            'UQDinterface'
            # pathlib.Path(__file__).resolve().parents[1],
            # 'UQDinterface',
            # 'UQDinterface'
        )
        command = [
            # 'gnome-terminal',
            # '--',
            str(uqdinterface_path)
        ]
        if dcfile:
            command.append(f'--dcfile={dcfile}')
        if fg_period:
            command.append(f'--fg_period={fg_period}')
        if fg_high:
            command.append(f'--fg_high={fg_high}')

        # start
        self._uqdinterface_proc = subprocess.Popen(command)
        time.sleep(2)
    
    def stop_uqdinterface(self) -> None:
        if self._uqdinterface_proc is not None:
            self._uqdinterface_proc.kill()
            print('Killed UQDinterface process')

    def start_reader(
            self,
            buffer_number: typing.Optional[int] = None,
            tagsAsTime: bool = False
    ) -> None:
        if buffer_number is not None:
            self._buffer_number = buffer_number
            self._uqd = ttag.TTBuffer(buffernumber=self._buffer_number)
        else:
            if self._buffer_number is not None:
                # use internal uqdinterface instance
                self._uqd = ttag.TTBuffer(buffernumber=self._buffer_number)
            else:
                # use existing uqdinterface (tagDisp)
                if ttag.getfreebuffer() == 0:
                    self._buffer_number = int(ttag.getfreebuffer())
                    self._uqd = ttag.TTBuffer(buffernumber=self._buffer_number)
                else:
                    self._buffer_number = int(ttag.getfreebuffer())-1
                    self._uqd = ttag.TTBuffer(buffernumber=self._buffer_number)

        print(f'Reading from buffer {self._buffer_number}')
        self._uqd.tagsAsTime = tagsAsTime

        if self._uqd.getrunners() == 0:
            self._uqd.start()

        time.sleep(1.1)

    def __del__(self) -> None:
        self.stop_uqdinterface()

    def flush(self) -> None:
        _, timetags = self._uqd(t=0.01)
        self.clock_offset = np.max(timetags)

    
    def measure(self,seconds=1) -> timetagger.RawData:
        channels: np.typing.NDArray[np.uint8]
        timetags: np.typing.NDArray[np.uint64]
        channels, timetags = self._uqd(t=seconds)
        raw_data = timetagger.RawData(
            timetags=(timetags - self.clock_offset).astype(np.int64),
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
    uqd = UQD()
    # uqd.start_uqdinterface(clear_all_buffers=True, fg_period=20, fg_high=10)
    uqd.start_uqdinterface(clear_all_buffers=True)
    # uqd.start_reader(tagsAsTime=True)
    while True:
        # raw_data = uqd.measure()
        # print(raw_data)
        # time.sleep(1)
        pass