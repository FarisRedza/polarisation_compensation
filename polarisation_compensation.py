import time
import threading
import pprint

import polarimeter.polarimeter as polarimeter
import motor.motor as motor

def polarimeter_measure(pax: polarimeter.Polarimeter, data: list[polarimeter.Data]) -> None:
    while True:
        for i in range(len(data)):
            data[i] = pax.measure().to_data()
        if event.is_set():
            break
        time.sleep(0.1)
    pax.disconnect()
    print('Stop taking data')

def move_motor(motor: motor.Motor, data: list[polarimeter.Data]) -> None:
    while True:
        if data[0].azimuth > 0:
            print('moving motor cw')
            motor.move_by(5)
        else:
            print('moving motor ccw')
            motor.move_by(-5)
        if event.is_set():
            break
    print('Stop moving motor')
    

def main():
    pax = polarimeter.Polarimeter(
        id='1313:8031',
        serial_number='M00910360'
    )
    data = [0]
    pax_thread = threading.Thread(
        target=polarimeter_measure,
        args=(pax, data)
    )
    pax_thread.start()

    motor_1 = motor.Motor(
        serial_number=55356974
    )
    motor_thread = threading.Thread(
        target=move_motor,
        args=(motor_1, data)
    )
    motor_thread.start()

    while True:
        try:
            pprint.pprint(data[0])
            time.sleep(1)
        except KeyboardInterrupt:
            event.set()
            break
    
    pax_thread.join()
    motor_thread.join()

if __name__ == '__main__':
    event = threading.Event()
    main()