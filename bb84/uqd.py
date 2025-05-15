import sys
import os
import pathlib
import time

os.environ['TTAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'ttag',
    'python'
))
sys.path.append(os.environ['TTAG'])
import ttag

os.environ['TIMETAG'] = str(pathlib.Path(
    os.environ['HOME'],
    'Projects',
    'polarisation_compensation',
    'timetag',
    'python'
))
sys.path.append(os.environ['TIMETAG'])
import timetag

uqd = timetag.CTimeTag() # type: ignore
if uqd.IsOpen() == True:
    print('Starting measurement')
    uqd.StartTimeTags()
    time.sleep(1)
    uqd.StopTimeTags()
    time.sleep(1)
    print(uqd.ReadTags())