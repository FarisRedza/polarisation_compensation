import time
import threading
import logging
import json
import datetime
import typing
import pathlib
import collections

# import polarimeter.thorlabs_polarimeter as thorlabs_polarimeter
import bb84.timetagger as timetagger
import bb84.remote_timetagger as remote_timetagger
import motor.thorlabs_motor as thorlabs_motor
import motor.base_motor as base_motor

MOTOR_SERVER_HOST = '137.195.89.222'
MOTOR_SERVER_PORT = 5002
MEASUREMENT_SERVER_HOST = '137.195.89.222'
MEASUREMENT_SERVER_HOST = '137.195.63.6'
MEASUREMENT_SERVER_PORT = 5001

class JsonFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created)
        if datefmt:
            return dt.strftime(datefmt).replace('%f', f"{dt.microsecond // 1000:03d}")
        return dt.isoformat()

    def format(self, record) -> str:
        log_record = {
            'time': self.formatTime(record=record, datefmt=f'{datetime_format}.%f'),
            'level': record.levelname,
            'name': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info:
            log_record['exception'] = self.formatException(ei=record.exc_info)

        standard_attrs = vars(
            logging.LogRecord(
                name='',
                level=0,
                pathname='',
                lineno=0,
                msg='',
                args=(),
                exc_info=None
            )
        ).keys()
        for attr, value in record.__dict__.items():
            if attr not in standard_attrs:
                log_record[attr] = value

        return json.dumps(log_record)

def get_data(
        measurement_device: timetagger.TimeTagger,
        raw_data_container: list,
        measurement_rate: float = 1
    ) -> None:
    # while True:
        for i in range(len(raw_data_container)):
            raw_data_container[i] = measurement_device.measure()
        # if event.is_set():
        #     break
        time.sleep(measurement_rate)

def compensate(
    motor_list: list[base_motor.Motor],
    motor_1_serial_no: str,
    motor_2_serial_no: str,
    parameter_1_target: float,
    parameter_2_target: float,
    parameter_1_velocities: list[tuple[float, float]],
    parameter_2_velocities: list[tuple[float, float]],
    parameter_1_current_value: float,
    parameter_2_current_value: float,
    mode: typing.Literal['direct', 'probe'] = 'probe',
    prev_value_1: typing.Optional[float] = None,
    prev_value_2: typing.Optional[float] = None,
    probe_direction_1: typing.Optional[base_motor.MotorDirection] = None,
    probe_direction_2: typing.Optional[base_motor.MotorDirection] = None,
):
# ) -> tuple[bool, float, float, base_motor.MotorDirection, base_motor.MotorDirection]:

    motor_1_index = next(
        (i for i, m in enumerate(motor_list) if m.device_info.serial_number == motor_1_serial_no),
        -1
    )
    motor_2_index = next(
        (i for i, m in enumerate(motor_list) if m.device_info.serial_number == motor_2_serial_no),
        -1
    )

    def adjust_motor(
        motor_index: int,
        current_value: float,
        target_value: float,
        thresholds_velocities: list[tuple[float, float]],
        prev_value: typing.Optional[float],
        probe_direction: typing.Optional[base_motor.MotorDirection],
    ) -> tuple[typing.Optional[float], typing.Optional[base_motor.MotorDirection]]:
        if motor_index == -1:
            return prev_value, probe_direction

        motor = motor_list[motor_index]
        delta = target_value - current_value
        abs_delta = abs(delta)

        if mode == "direct":
            target_direction = (
                base_motor.MotorDirection.FORWARD if delta > 0 else
                base_motor.MotorDirection.BACKWARD if delta < 0 else
                base_motor.MotorDirection.IDLE
            )

        elif mode == "probe":
            if probe_direction is None:
                probe_direction = base_motor.MotorDirection.FORWARD

            if prev_value is not None:
                improving = current_value <= prev_value
                if not improving:
                    probe_direction = (
                        base_motor.MotorDirection.BACKWARD
                        if probe_direction == base_motor.MotorDirection.FORWARD
                        else base_motor.MotorDirection.FORWARD
                    )

            target_direction = probe_direction
        else:
            raise ValueError(f"Unknown mode: {mode}")

        if target_direction == base_motor.MotorDirection.IDLE:
            if motor.is_moving:
                motor.stop()
            return current_value, probe_direction

        for threshold, velocity in sorted(thresholds_velocities, reverse=True):
            if abs_delta > threshold or mode == "probe":
                if (motor.direction != target_direction or
                        motor.max_velocity != velocity):
                    motor.direction = target_direction
                    motor.jog(
                        direction=motor.direction,
                        acceleration=20.0,
                        max_velocity=velocity
                    )
                motor_logger.info(
                    msg='Motor adjustment',
                    extra={
                        'serial number': motor.device_info.serial_number,
                        'direction': motor.direction.name,
                        'method': mode,
                        'velocity': motor.max_velocity
                    }
                )
                break
            elif motor.is_moving:
                motor.stop()

        return current_value, probe_direction

    new_prev_1, new_probe_direction_1 = adjust_motor(
        motor_index=motor_1_index,
        current_value=parameter_1_current_value,
        target_value=parameter_1_target,
        thresholds_velocities=parameter_1_velocities,
        prev_value=prev_value_1,
        probe_direction=probe_direction_1,
    )

    # new_prev_2 = None
    # new_probe_direction_2 = None
    new_prev_2, new_probe_direction_2 = adjust_motor(
        motor_index=motor_2_index,
        current_value=parameter_2_current_value,
        target_value=parameter_2_target,
        thresholds_velocities=parameter_2_velocities,
        prev_value=prev_value_2,
        probe_direction=probe_direction_2,
    )

    return True, new_prev_1, new_prev_2, new_probe_direction_1, new_probe_direction_2


if __name__ == '__main__':
    # settings
    meaurement_rate = 0.1
    compensation_rate = 0.1
    cycles = 5

    QWP = '55353314'  # azimuth
    HWP = '55356974'  # ellipticity
    
    M1 = QWP
    M2 = HWP
    
    target_qber = 0
    target_qx = 0

    # 5 mins maintained with cycles = 3
    # qber_velocity = [
    #     (0.5, 25.0),
    #     (0.25, 15.0),
    #     (0.1, 1.0),
    # ]
    # qx_velocity = [
    #     (0.5, 25.0),
    #     (0.25, 15.0),
    #     (0.1, 0.1)
    # ]

    qber_velocity = [
        (0.0, 5.0),
    ]
    qx_velocity = [
        (0.0, 5.0)
    ]

    # setup logging
    datetime_format = '%Y_%m_%d_%H_%M_%S'
    handler = logging.StreamHandler()
    handler.setFormatter(fmt=JsonFormatter())

    pathlib.Path('logs').mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        filename=f'logs/pol_comp_{datetime.datetime.now().strftime(datetime_format)}.log'
    )
    file_handler.setFormatter(fmt=JsonFormatter())

    motor_logger = logging.getLogger(name='Motor')
    motor_logger.setLevel(level=logging.INFO)
    motor_logger.addHandler(hdlr=file_handler)

    data_logger = logging.getLogger(name='Data')
    data_logger.setLevel(level=logging.INFO)
    data_logger.addHandler(hdlr=file_handler)

    # devices
    measurement_device = remote_timetagger.RemoteTimetagger(
        host=MEASUREMENT_SERVER_HOST,
        port=MEASUREMENT_SERVER_PORT,
        model='Logic-16'
    )
    # measurement_device = timetagger.TimeTagger()

    motors = [
        thorlabs_motor.ThorlabsMotor(serial_number=m[0])
        for m in thorlabs_motor.list_thorlabs_motors()
    ]

    raw_data_container = [timetagger.RawData()]
    qber_avg = None
    qx_avg = None

    prev_qber = None
    prev_qx = None
    qber_direction = None
    qx_direction = None
    while True:
        try:
            get_data(
                measurement_device=measurement_device,
                raw_data_container=raw_data_container,
                measurement_rate=meaurement_rate
            )
            data = timetagger.Data().from_raw_data(raw_data=raw_data_container[0])
            qber_values = collections.deque(maxlen=cycles)
            qx_values = collections.deque(maxlen=cycles)

            qber_values.append(data.qber)
            qx_values.append(data.qx)

            qber_avg = sum(qber_values) / len(qber_values)
            qx_avg = sum(qx_values) / len(qx_values)

            # print(qber_avg)
            # print(qx_avg)

            data_logger.info(
                msg='Measurement taken',
                extra={
                    'singles': data.singles.tolist(),
                    'QBER': data.qber,
                    'Qx': data.qx
                }
            )

            _, prev_qber, prev_qx, qber_direction, qx_direction = compensate(
                motor_list=motors,
                motor_1_serial_no=M1,
                motor_2_serial_no=M2,
                parameter_1_target=target_qber,
                parameter_2_target=target_qx,
                parameter_1_velocities=qber_velocity,
                parameter_2_velocities=qx_velocity,
                parameter_1_current_value=qber_avg,
                parameter_2_current_value=qx_avg,
                mode='probe',
                prev_value_1=prev_qber,
                prev_value_2=prev_qx,
                probe_direction_1=qber_direction,
                probe_direction_2=qx_direction
            )
            time.sleep(compensation_rate)

        except KeyboardInterrupt:
            for m in motors:
                m.stop()
                m.disconnect()
            break