import sys
import pathlib
import logging
import time

import matplotlib.pyplot as plt

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import bb84.uqd as uqd
import bb84.qutag as qutag
# import bb84.remote_timetagger as remote_timetagger
import bb84.timetagger as timetagger

import tomtag as tomt
import numpy as np
from tqdm import tqdm
import matplotlib

def find_delay(
        tags_QuTAG: np.ndarray,
        tags_UQD: np.ndarray,
        tcc: int = 2000,
        left: int = -500000,
        right: int = 500000
    ) -> int:
    """
    Find the delay between the two channels.
    """
    # find delay between 1550 and 780 nm
    cc = []
    tags_UQD = tags_UQD.astype(np.int64)
    array = np.arange(
        left,
        right,
        tcc,
        dtype=np.int64
    )
    for delay in tqdm(array):
        cc.append(
            tomt.count_twofolds(
                tags_QuTAG, tags_UQD + delay,
                len(tags_QuTAG), len(tags_UQD), tcc
            )
        )
    
    plt.plot(
        array*78.125/1e3,
        cc

    )
    plt.xlabel("delay (ns)")
    plt.show()
    return array[np.argmax(cc)]

def get_qber(channels, timetags, delay=0, tcc=15):
    """
    Assume that channels are HVDAHVDA
    """
    tags_H_1550 = timetags[channels == 0]
    tags_V_1550 = timetags[channels == 1]
    tags_D_1550 = timetags[channels == 2]
    tags_A_1550 = timetags[channels == 3]
    tags_H_780 = timetags[channels == 4] + delay
    tags_V_780 = timetags[channels == 5] + delay
    tags_D_780 = timetags[channels == 6] + delay
    tags_A_780 = timetags[channels == 7] + delay

    # self.find_delay(tags_H_1550, tags_H_780, tcc)

    HH = tomt.count_twofolds(tags_H_1550, tags_H_780, len(tags_H_1550), len(tags_H_780),tcc)
    HV = tomt.count_twofolds(tags_H_1550, tags_V_780, len(tags_H_1550), len(tags_V_780),tcc)
    VH = tomt.count_twofolds(tags_V_1550, tags_H_780, len(tags_V_1550), len(tags_H_780),tcc)
    VV = tomt.count_twofolds(tags_V_1550, tags_V_780, len(tags_V_1550), len(tags_V_780),tcc)

    qber =  (VH + VH) / (HH + HV + VH + VV)

    DD = tomt.count_twofolds(tags_D_1550, tags_D_780, len(tags_D_1550), len(tags_D_780),tcc)
    DA = tomt.count_twofolds(tags_D_1550, tags_A_780, len(tags_D_1550), len(tags_A_780),tcc)
    AD = tomt.count_twofolds(tags_A_1550, tags_D_780, len(tags_A_1550), len(tags_D_780),tcc)
    AA = tomt.count_twofolds(tags_A_1550, tags_V_780, len(tags_A_1550), len(tags_A_780),tcc)

    qx =  (DA + AD) / (DD + AD + DA + AA)

    return qber, qx, HH+HV+VH+VV

if __name__ == '__main__':
    tag_device_QuTAG = qutag.Qutag()
    # tag_device_UQD._uqd_timetag.Use10MHz(use=True)
    
    tag_device_UQD = uqd.UQD()
    tag_device_QuTAG._qutag.enableExternalClock(enable=1)
    if tag_device_QuTAG._qutag.getClockState()==(1,0):
        print("clocks locked!")
    else:
        print("attention: clocks not locked!")
    # zero both internal clocks
    tag_device_QuTAG.flush()
    tag_device_UQD.flush()
    data_QuTAG = tag_device_QuTAG.measure(0.1)
    data_UQD = tag_device_UQD.measure(0.1)
    print(f'QuTAG time {(data_QuTAG.timetags[-1] - data_QuTAG.timetags[0])*tag_device_QuTAG.resolution/1e12:.3f}s') 
    print(f'UQD time {(data_UQD.timetags[-1] - data_UQD.timetags[0])*tag_device_QuTAG.resolution/1e12:.3f}s')       
    print(f'raw delay {(data_QuTAG.timetags[0] - data_UQD.timetags[0])*tag_device_QuTAG.resolution/1e12:.5f}s') 
    # data_QuTAG.timetags += data_UQD.timetags[0] - data_QuTAG.timetags[0] 
    # print(data_UQD.timetags)

    print(f' tags in QuTAG: {len(np.where(data_QuTAG.channels==0)[0])}')
    print(f' tags in UQD: {len(np.where(data_UQD.channels==0)[0])}')

    delay = find_delay(
        tags_QuTAG=data_QuTAG.timetags[data_QuTAG.channels==0],
        tags_UQD=data_UQD.timetags[data_UQD.channels==0],
        left=-400000000,
        right=-100000000
    )
    data_QuTAG = tag_device_QuTAG.measure(0.1)
    data_UQD = tag_device_UQD.measure(0.1) 
    print(f'QuTAG time {(data_QuTAG.timetags[-1] - data_QuTAG.timetags[0])*tag_device_QuTAG.resolution/1e12:.3f}s') 
    print(f'UQD time {(data_UQD.timetags[-1] - data_UQD.timetags[0])*tag_device_QuTAG.resolution/1e12:.3f}s')       
    print(f'raw delay {(data_QuTAG.timetags[0] - data_UQD.timetags[0])*tag_device_QuTAG.resolution/1e12:.5f}s')
    data_UQD.timetags += delay
    delay = find_delay(
        tags_QuTAG=data_QuTAG.timetags[data_QuTAG.channels==0],
        tags_UQD=data_UQD.timetags[data_UQD.channels==0],
        left=-5000,
        right=5000,
        tcc = 1
    )


    print(f'{delay=}')