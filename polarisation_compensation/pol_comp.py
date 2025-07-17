import time
import datetime
import logging

# import polarimeter.gui_widget as polarimeter_gui_widget
import polarimeter.remote_polarimeter as remote_polarimeter

# import motor.gui_widget as motor_gui_widget
import motor.remote_motor as remote_motor

MOTOR_SERVER_HOST = '137.195.89.222'
MOTOR_SERVER_PORT = 5002
POLARIMETER_SERVER_HOST = '137.195.89.222'
POLARIMETER_SERVER_PORT = 5003

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename=f'polarimeter_{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.log',
        encoding='utf-8',
        filemode='a',
        format='{asctime} - {levelname} - {message}',
        style='{',
    )

    # pax = remote_polarimeter.Polarimeter(
    #     host=POLARIMETER_SERVER_HOST,
    #     port=POLARIMETER_SERVER_PORT,
    #     serial_number='M00910360'
    # )
    # print(pax.device_info)

    for _ in range(5):
        # data = remote_polarimeter.thorlabs_polarimeter.Data().from_raw_data(
        #     raw_data=pax.measure()
        # )
        # logging.info(f'{data.azimuth=}, {data.ellipticity=}')
        logging.info(time.time())
        time.sleep(0.1)