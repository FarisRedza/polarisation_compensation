import time
import threading

import polarimeter.polarimeter as scpi_polarimeter

event = threading.Event()

def measure_azimuth(pax: scpi_polarimeter.Polarimeter, data: list) -> None:
    while True:
        for i in range(len(data)):
            data[i] = pax.measure().to_data().azimuth
        if event.is_set():
            break
        time.sleep(0.1)
    print('Stop taking data')

pax = scpi_polarimeter.Polarimeter(
    id='1313:8031',
    serial_number='M00910360'
)

data = [0]
t = threading.Thread(
    target=measure_azimuth,
    args=(pax, data,)
)
t.start()

while True:
    try:
        print(data)
        time.sleep(1)
    except KeyboardInterrupt:
        event.set()
        break
t.join()
print(data)