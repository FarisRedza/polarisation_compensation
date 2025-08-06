import matplotlib.pyplot as plt
import numpy as np
import json

file_name = 'logs/pol_comp_2025_08_06_11_36_45.847868.log'
with open(file_name, 'r') as f:
    qbers  = []
    qxs = []
    times = []
    singles = []
    for line in f:
        data = json.loads(line)
        qbers += [data['QBER']]
        qxs += [data['Qx']]
        singles += [data['singles']]
        time = data['time'].split(' ')[1].split(',')[0].split(':')
        times += [int(time[0])*3600 + int(time[1])*60 + float(time[2])]

times = np.array(times)
times -= times[0]  # Normalize time to start at 0
plt.plot(times, qbers, label='QBER')
plt.plot(times, qxs, label='Qxs')
plt.xlabel('Time (s)')
plt.ylabel('Singles')
plt.show()
        
