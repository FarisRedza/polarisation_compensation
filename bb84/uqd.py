import sys
import os
import pathlib
import time

C_H = 0
C_V = 1
C_D = 2
C_A = 3

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

buffernumber = tt.getfreebuffer()-1

ttag = tt.TTBuffer(buffernumber=buffernumber)
for _ in range(0,50):
    data = ttag.singles(1)[0:4]
    print(data)
    s_0 = 1
    s_1 = (data[C_H] - data[C_V])/(data[C_H] + data[C_V])
    s_2 = (data[C_D] - data[C_A])/(data[C_D] + data[C_A])
    print(s_1, s_2)
    
    time.sleep(0.1)