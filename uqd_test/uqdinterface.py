import sys
import pathlib
import subprocess

sys.path.append(str(pathlib.Path(__file__).resolve().parents[3]))
from emqTools.ttag.python import ttag

def clear_all_buffers() -> None:
    for i in range(ttag.getfreebuffer()-1):
        ttag.deletebuffer(i)
    print('CLEARING ALL BUFFERS')
    print(f'FIRST FREE BUFFER IS {ttag.getfreebuffer()}')

def start_uqd_interface(clear_buffers: bool = False) -> None:
    if clear_buffers:
        clear_all_buffers()

    uqdinterface_path = pathlib.Path(
        '/home/ap2055/emqTools/ttag',
        'UQD',
        'UQDinterface'
    )
    command = [
        'gnome-terminal',
        '--',
        str(uqdinterface_path)
    ]
    proc = subprocess.Popen(command)
    try:
        while True:
            pass
    except KeyboardInterrupt:
        proc.kill()

if __name__ == '__main__':
    start_uqd_interface(clear_buffers=True)