import sys
import os
import pathlib
import time
import datetime

import matplotlib.pyplot as plt

filepath = pathlib.Path(__file__).parent

for i in range(29,30):
    file_name = f'pid_pol_comp_update_lock_{i}.log'
    timestamps: list[datetime.datetime] = []
    qbers: list[float] = []
    qxs: list[float] = []
    with open(file=filepath.joinpath(file_name), mode='r') as file:
        for line in file.readlines():
            if 'QBER' in line:
                parts = line.split('|')
                timestamp = datetime.datetime.strptime(
                    parts[0].split('-')[0].strip(),
                    '%H:%M:%S.%f'
                )
                timestamps.append(timestamp)
                data = parts[1].split(',')
                qber = float(data[0].split('=')[1])
                qx = float(data[1].split('=')[1])
                qbers.append(qber)
                qxs.append(qx)


    times = [(x - timestamps[0]).total_seconds() for x in timestamps]
    fig, ax = plt.subplots(figsize=(12,7))
    ax.plot(times, qxs, label='Qx')
    ax.plot(times, qbers, label='QBER')
    ax.plot(times, [sum(x) for x in zip(qxs,qbers)], label='Objective')
    ax.set_xlabel(xlabel='Time (s)')
    ax.set_xlim(times[0], times[-1])
    ax.set_ylim(0, 2)
    ax.set_title(file_name)
    ax.grid()
    ax.axhline(y=0.05, color='r', linestyle='--')
    ax.legend()
    fig.tight_layout()
    fig.savefig(
        fname=file_name.replace('.log','.png'),
        dpi=300,
        bbox_inches='tight'
    )
    plt.show()