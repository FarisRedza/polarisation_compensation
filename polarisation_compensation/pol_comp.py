import time
import datetime
import logging
import threading

import polarimeter.thorlabs_polarimeter as thorlabs_polarimeter
import motor.remote_motor as remote_motor
import motor.base_motor as base_motor

MOTOR_SERVER_HOST = '137.195.89.222'
MOTOR_SERVER_PORT = 5002
POLARIMETER_SERVER_HOST = '137.195.89.222'
POLARIMETER_SERVER_PORT = 5003

def get_data(
        polarisation_device: thorlabs_polarimeter.Polarimeter,
        raw_data_container: list,
        polling_rate: float = 1
    ) -> None:
    while True:
        for i in range(len(raw_data_container)):
            raw_data_container[i] = polarisation_device.measure()
        if event.is_set():
            break
        time.sleep(polling_rate)

def compensate(
        motor_list: list[base_motor.Motor],
        motor_1_serial_no: str,
        motor_2_serial_no: str,
        parameter_1_target: float,
        parameter_2_target: float,
        parameter_1_velocities: list[tuple[float, float]],
        parameter_2_velocities: list[tuple[float, float]],
        parameter_1_current_value: float,
        parameter_2_current_value: float
) -> bool:
    motor_1_index = next(
        (i for i, m in enumerate(motor_list) if m.device_info.serial_number == motor_1_serial_no),
        -1
    )
    motor_2_index = next(
        (i for i, m in enumerate(motor_list) if m.device_info.serial_number == motor_2_serial_no),
        -1
    )

    def adjust_motor(
        motor_list: list[base_motor.Motor],
        motor_index: int,
        current_value: float,
        target_value: float,
        thresholds_velocities: list[tuple[float, float]]
    ) -> None:
        if motor_index == -1:
            return

        motor = motor_list[motor_index]
        delta = target_value - current_value

        target_direction = base_motor.MotorDirection.FORWARD if delta > 0 else base_motor.MotorDirection.BACKWARD
        abs_delta = abs(delta)

        for threshold, velocity in sorted(thresholds_velocities, reverse=True):
            if abs_delta > threshold:
                if (motor.direction != target_direction or
                        motor.max_velocity != velocity):
                    motor.direction = target_direction
                    motor.jog(
                        direction=motor.direction,
                        acceleration=20.0,
                        max_velocity=velocity
                    )
                print(f'Rotating motor {motor.device_info.serial_number} {motor.direction.name}')
                break
            elif motor.is_moving == True:
                motor.stop()
            else:
                pass


    adjust_motor(
        motor_list=motor_list,
        motor_index=motor_1_index,
        current_value=parameter_1_current_value,
        target_value=parameter_1_target,
        thresholds_velocities=parameter_1_velocities
    )

    adjust_motor(
        motor_list=motor_list,
        motor_index=motor_2_index,
        current_value=parameter_2_current_value,
        target_value=parameter_2_target,
        thresholds_velocities=parameter_2_velocities
    )

    return True

if __name__ == '__main__':
    # logging.basicConfig(
    #     level=logging.DEBUG,
    #     filename=f'polarimeter_{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.log',
    #     encoding='utf-8',
    #     filemode='a',
    #     format='{asctime} - {levelname} - {message}',
    #     style='{',
    # )

    event = threading.Event()
    raw_data_container = [thorlabs_polarimeter.RawData()]
    meaurement_rate = 0.1
    compensation_rate = 1

    polarisation_device = thorlabs_polarimeter.Polarimeter(
        serial_number='M00910360'
    )
    motors = remote_motor.list_motors(
        host=MOTOR_SERVER_HOST,
        port=MOTOR_SERVER_PORT
    )
    QWP = '55353314'  # azimuth
    HWP = '55356974'  # ellipticity
    target_qber = 0
    target_qx = 0

    qber_velocity = [
        (5.0, 25.0),
        (2.5, 15.0),
    ]
    qx_velocity = [
        (5.0, 25.0),
        (2.5, 15.0),
    ]

    measurement_thread = threading.Thread(
        target=get_data,
        args=(
            polarisation_device,
            raw_data_container,
            meaurement_rate
        )
    )
    measurement_thread.start()
    while True:
        try:
            if isinstance(raw_data_container[0], thorlabs_polarimeter.RawData):
                data = thorlabs_polarimeter.Data().from_raw_data(
                    raw_data=raw_data_container[0]
                )
                qber = 1 - data.normalised_s1**2
                qx = 1 - data.normalised_s2**2
                compensate(
                    motor_list=motors,
                    motor_1_serial_no=QWP,
                    motor_2_serial_no=HWP,
                    parameter_1_target=target_qber,
                    parameter_2_target=target_qx,
                    parameter_1_velocities=qber_velocity,
                    parameter_2_velocities=qx_velocity,
                    parameter_1_current_value=qber,
                    parameter_2_current_value=qx
                )
                print(f'{qber=}, {qx=}')

            time.sleep(compensation_rate)
        except KeyboardInterrupt:
            event.set()
            break

    measurement_thread.join()

    for m in motors:
        m.stop()
        m.disconnect()
    polarisation_device.disconnect()
