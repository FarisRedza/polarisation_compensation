import threading
import time

import motor.motor as thorlabs_motor
import polarimeter.polarimeter as scpi_polarimeter

def polarimeter_measure(pax: scpi_polarimeter.Polarimeter, data: list[scpi_polarimeter.Data]) -> None:
    while True:
        for i in range(len(data)):
            data[i] = pax.measure().to_data()
        if event.is_set():
            break
        time.sleep(0.1)
    pax.disconnect()
    print('Stop taking data')

def main():
    stage = thorlabs_motor.Motor(serial_number=55356974)
    pax = scpi_polarimeter.Polarimeter(
        id='1313:8031',
        serial_number='M00910360'
    )
    data = [scpi_polarimeter.Data()]
    pax_thread = threading.Thread(
        target=polarimeter_measure,
        args=(pax, data)
    )
    pax_thread.start()

    while True:
        try:
            azimuth = data[0].azimuth
            if azimuth > 0:
                stage._motor.jog(direction='+')
            else:
                stage._motor.jog(direction='-')
            time.sleep(1)
        except KeyboardInterrupt:
            stage._motor.stop()
            event.set()
            break

    pax_thread.join()

if __name__ == '__main__':
    event = threading.Event()
    main()