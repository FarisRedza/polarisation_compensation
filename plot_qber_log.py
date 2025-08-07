import matplotlib.pyplot as plt
import numpy as np
import json

file_name = 'logs/pol_comp_2025_08_06_16_43_26.log'
with open(file_name, 'r') as f:
    qbers  = []
    qxs = []
    times = []
    singles = []
    for line in f:
        if 'Data' not in line:
            continue
        data = json.loads(line)
        qbers += [data['QBER']]
        qxs += [data['Qx']]
        singles += [data['singles']]
        time = data['time'].split('_')[3:]
        times += [int(time[0])*3600 + int(time[1])*60 + float(time[2])]
        # else:
        #     sn = data['serial number']
        #     dir = 1 if data['direction'] == 'BACKWARD' else 0

times = np.array(times)
times -= times[0]  # Normalize time to start at 0
plt.plot(times, qbers, label='QBER')
plt.plot(times, qxs, label='Qx')
plt.legend()
plt.grid()
plt.xlabel('Time (s)')
# plt.ylabel('Singles')
plt.show()
