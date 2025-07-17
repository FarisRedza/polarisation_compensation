import logging
import time

import matplotlib.pyplot as plt

import bb84.uqd as uqd
import bb84.qutag as qutag
# import bb84.remote_timetagger as remote_timetagger
import bb84.timetagger as timetagger

import tomtag as tomt
import numpy as np
import matplotlib

def find_delay(
        tags_1550: np.ndarray,
        tags_780: np.ndarray,
        tcc: int = 10000
    ) -> int:
    """
    Find the delay between the two channels.
    """
    # find delay between 1550 and 780 nm
    cc = []
    # print(f'1550: {tags_1550.dtype}')
    # print(f'780: {tags_780.dtype}')
    tags_780 = tags_780.astype(np.int64)
    array = np.arange(
        -300000000,
        300000000,
        tcc,
        dtype=np.int64
    )
    for delay in array:
        cc.append(
            tomt.count_twofolds(
                tags_1550, tags_780 + delay,
                len(tags_1550), len(tags_780), tcc
            )
        )
    
    plt.plot(
        array,
        cc

    )
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
    tag_device_780 = uqd.UQD()
    tag_device_1550 = qutag.Qutag()
    tag_device_1550._qutag.enableExternalClock(enable=1)

    start_time_1550 = time.time()
    data_1550 = tag_device_1550.measure()
    print(f'1580 time {time.time() - start_time_1550}')    

    data_780 = tag_device_780.measure()
    start_time_780 = time.time()
    print(f'780 time {time.time() - start_time_780}')

    data_780.timetags -= data_780.timetags[0]
    data_1550.timetags -= data_1550.timetags[0]

    print(f'{data_780.timetags=}')
    print(f'{data_1550.timetags=}')

    print(f' 1550: {np.unique(data_1550.channels)}')
    print(f' 780: {np.unique(data_780.channels)}')

    delay = find_delay(
        tags_1550=data_1550.timetags[data_1550.channels==0],
        tags_780=data_780.timetags[data_780.channels==4]
    )

    print(f'{delay=}')