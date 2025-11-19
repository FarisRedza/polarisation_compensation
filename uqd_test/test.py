import subprocess
import pathlib
import sys
import time
import os

sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))
from emqTools.ttag.python import ttag
print(pathlib.Path(ttag.__file__).resolve())

def clear_buffers() -> None:
    for i in range(ttag.getfreebuffer()-1):
        ttag.deletebuffer(i)
    print('CLEARING ALL BUFFERS')
    print(f'FIRST FREE BUFFER IS {ttag.getfreebuffer()}')

def start_uqdinterface() -> subprocess.Popen:
    uqdinterface_path = pathlib.Path(
        '/home/ap2055/emqTools',
        'ttag',
        'UQD',
        'UQDinterface'
    )

    command = [
#        'gnome-terminal',
 #       '--',
        str(uqdinterface_path)
    ]
    print(f'Running command: {command}')
    proc = subprocess.Popen(command)
    print('Started UQDinterface')
    return proc

def reader() -> None:
    comm  = '/home/ap2055/emqTools/tagDisp/smallDispWindow.py'
    subprocess.Popen([sys.executable, comm])

def reader_no_window() -> ttag.TTBuffer:
    if ttag.getfreebuffer() == 0:
        buffernumber = int(ttag.getfreebuffer())
    else:
        buffernumber = int(ttag.getfreebuffer()) - 1

    reader = ttag.TTBuffer(buffernumber=buffernumber)
    print('starting reader')
    reader.start()
    print('reader started')
    return reader

if __name__ == '__main__':
    #clear_buffers()
    #uqd_proc = start_uqdinterface()
    #time.sleep(2)
    reader()
    #reader = reader_no_window()
    try:
        while True:
            #print(reader(t=1))
            #time.sleep(1)
            pass
    except KeyboardInterrupt:
        uqd_proc.kill()
        print('Killed UQDinterface process')
