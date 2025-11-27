import sys
import os
import pathlib
import typing
import subprocess
import time

import numpy as np

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from bb84 import timetagger
from UQDinterface.ttag.python import ttag

class UQD(timetagger.TimeTagger):
    def __init__(self) -> None:
        self._buffer_number: typing.Optional[int] = None
        self._uqdinterface_proc: typing.Optional[subprocess.Popen] = None
        self._uqd_reader: typing.Optional[ttag.TTBuffer] = None
        self.start_reader()

        self.device_info = timetagger.DeviceInfo(
            manufacturer = 'UQDevices',
            model = 'Logic-16',
            serial_number = 'N/A',
            firmware_version = 'N/A'
        )
        self.channel_groups = timetagger.default_channel_groups
        self.clock_offset = np.uint64(0)

    def measure(self, seconds: float = 1.0) -> timetagger.RawData:
        if self._uqd_reader:
            channels: np.typing.NDArray[np.uint8]
            timetags: np.typing.NDArray[np.uint64]
            channels, timetags = self._uqd_reader(t=seconds)
            raw_data = timetagger.RawData(
                timetags=(timetags - self.clock_offset).astype(np.int64),
                channels=channels
            )
            return raw_data
        else:
            RuntimeError('No UQD reader')

    def flush(self) -> None:
        if self._uqd_reader:
            _, timetags = self._uqd_reader(t=0.1)
            self.clock_offset = np.uint64(timetags[-1])
        else:
            RuntimeError('No UQD reader')

    def clear_buffers(self) -> None:
        print('Clearing buffers')
        for i in range(ttag.getfreebuffer()-1):
            ttag.deletebuffer(i)
        self.buffer_number = int(ttag.getfreebuffer())
        print(f'First free buffer: {self.buffer_number}')

    def start_reader(self, tagsAsTime: bool = False) -> None:
        self._uqd_reader = ttag.TTBuffer(buffernumber=ttag.getfreebuffer()-1)
        self._uqd_reader.tagsAsTime = tagsAsTime
        if self._uqd_reader.getrunners() == 0:
            self._uqd_reader.start()
        else:
            RuntimeWarning('Reader already started')

    def start_uqdinterface(
            self,
            clear_buffers: bool = False,
            dcfile: typing.Optional[pathlib.Path] = None,
            fg_period: typing.Optional[int] = None,
            fg_high: typing.Optional[int] = None,
            uqd_dir: typing.Optional[pathlib.Path] = None
    ) -> None:
        if clear_buffers:
            self.clear_buffers()
        
        if uqd_dir:
            uqdinterface_dir = uqd_dir
        else:
            uqdinterface_dir = pathlib.Path(__file__).resolve().parents[1].joinpath(
                'UQDinterface',
            )

        uqd_bin = 'UQDinterface'
        command = [f'{uqdinterface_dir.joinpath(uqd_bin)}']

        if dcfile:
            command.append(f'--dcfile={dcfile}')
        if fg_period:
            command.append(f'--fg_period={fg_period}')
        if fg_high:
            command.append(f'--fg_period={fg_high}')

        self._current_dir = pathlib.Path.cwd()
        os.chdir(path=uqdinterface_dir)
        self._uqdinterface_proc = subprocess.Popen(command)
        time.sleep(0.2)

    def stop_uqdinterface(self) -> None:
        if self._uqdinterface_proc:
            self._uqdinterface_proc.kill()
            os.chdir(path=self._current_dir)
            print('Killed UQDinterface process')
        else:
            RuntimeWarning('UQDinterface already stopped')

    def __del__(self) -> None:
        if self._uqdinterface_proc:
            self.stop_uqdinterface()

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
    uqd.start_uqdinterface(clear_buffers=True)
    # time.sleep(0.2)
    uqd.start_reader()
    while True:
        print(uqd.measure())
        time.sleep(1)