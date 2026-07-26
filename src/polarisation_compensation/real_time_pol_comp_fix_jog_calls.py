import sys
import typing
import time
import random
import io
import threading
import itertools
import contextlib

import numpy as np

from bb84 import timetagger
from bb84 import remote_timetagger
from motor import thorlabs_motor
from motor import k10cr2_motor
from motor import base_motor

MEASUREMENT_SERVER_HOST = '137.195.63.45'
MEASUREMENT_SERVER_PORT = 5001

QWP1 = '55353314'
HWP = '55356974'
QWP2 = '55536714'

@contextlib.contextmanager
def suppress_stdout():
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout


def set_motor_to_0(motor: base_motor.Motor) -> None:
    while abs(motor.position) > 5:
        motor.move_to(
            position=0,
            acceleration=20.0,
            max_velocity=25.0
        )
        time.sleep(0.1)

def scramble_motor(
        motor: base_motor.Motor,
        min_time: int,
        max_time: int
) -> None:
    direction = random.choice([
        base_motor.MotorDirection.BACKWARD,
        base_motor.MotorDirection.FORWARD
    ])
    rotation_time = random.randint(min_time, max_time)
    motor.jog(
        direction=direction,
        acceleration=20.0,
        max_velocity=25.0
    )
    time.sleep(rotation_time)
    motor.stop()

def binary_entropy(x: float) -> float:
    x = np.clip(x, 1e-12, 1 - 1e-12)
    return -x * np.log2(x) - (1 - x) * np.log2(1 - x)


def keys_per_second(
        coincidences: float,
        qber: float,
        qx: float,
        f_ec: float = 1.1
) -> float:
    rate = coincidences * (1 - f_ec * binary_entropy(qber) - binary_entropy(qx))
    return rate


def objective(
        data: typing.Optional[timetagger.Data] = None,
        qber: typing.Optional[float] = None,
        qx: typing.Optional[float] = None,
        rate: typing.Optional[int | float] = None,
) -> float:
    """Hybrid objective: maximise key rate if positive, else minimise QBER+Qx."""
    if data:
        d_rate = data.rate
        d_qber = data.qber
        d_qx = data.qx
    elif qber and qx and rate:
        d_rate = rate
        d_qber = qber
        d_qx = qx
    else:
        raise RuntimeError('Must provide data or qber, qx, rate')

    kps = keys_per_second(
        coincidences=d_rate,
        qber=d_qber,
        qx=d_qx
    )
    if kps > 0:
        obj = kps
    else:
        obj = - (d_qber + d_qx)

    return obj

class PolarisationCompensator:
    def __init__(
            self,
            motors: list[base_motor.Motor],
            tt: timetagger.TimeTagger,
            target_qber: float = 0.05,
            target_qx: float = 0.1,
            samples: int = 3,
            acceleration: float = 20.0,
            max_velocity: float = 25.0,
            max_iterations: int = 3,
            start_at_0: bool = False,
            scramble_motors: bool = False,
            scramble_min_time: int = 10,
            scramble_max_time: int = 20
    ) -> None:
        self.motors = motors
        self.tt = tt

        self._motor_states = {}
        for motor in self.motors:
            self._motor_states[motor.device_info.serial_number] = {
                'moving': False,
                'direction': random.choice([
                        base_motor.MotorDirection.BACKWARD,
                        base_motor.MotorDirection.FORWARD
                    ])
            }

        if start_at_0:
            print('Setting motor positions to 0')
            with suppress_stdout():
                motor_thread: list[threading.Thread] = []
                for i, motor in enumerate(self.motors):
                    motor_thread.append(threading.Thread(
                        target=set_motor_to_0,
                        args=(motor,)
                    ))
                    motor_thread[i].start()
                for thread in motor_thread:
                    thread.join()

        if scramble_motors:
            print('Scrambling state')
            with suppress_stdout():
                motor_thread: list[threading.Thread] = []
                for i, motor in enumerate(self.motors):
                    motor_thread.append(threading.Thread(
                        target=scramble_motor,
                        args=(motor, scramble_min_time, scramble_max_time)
                    ))
                    motor_thread[i].start()
                for thread in motor_thread:
                    thread.join()

        time.sleep(1)
        start_time = time.time()
        print('Starting compensation')

        if max_iterations == 0:
            iterator = itertools.count()
        else:
            iterator = range(max_iterations)

        for i in iterator:
            if max_iterations != 0:
                print(f'Iteration: {i+1}/{max_iterations}')
            # for motor in self.motors:
            for motor in [x for x in self.motors for _ in range(2)]:
                # direction = random.choice([
                #     base_motor.MotorDirection.BACKWARD,
                #     base_motor.MotorDirection.FORWARD
                # ])
                direction = self._motor_states[motor.device_info.serial_number]['direction']
                print(f'  Motor: {motor.device_info.serial_number} probing direction {direction.name}')
                while True:
                    (
                        motor_baseline_qber,
                        motor_baseline_qx,
                        motor_baseline_rate,
                        motor_baseline_objective,
                        motor_baseline_kps
                    ) = self.measure(samples=samples)

                    if (
                        motor_baseline_qber < target_qber
                        and motor_baseline_qx < target_qx
                        and motor_baseline_kps > 0
                    ):
                        if max_iterations != 0:
                            print(f'Target achieved in {i+1} iterations, time: {time.time()-start_time}s')
                            return
                        else:
                            print(f'Target achieved: QBER={motor_baseline_qber:.4f}, Qx={motor_baseline_qx:.4f}, KPS={motor_baseline_kps:.2f}')

                    elif (
                        motor_baseline_qber < 3*target_qber
                        and motor_baseline_qx < 3*target_qx
                    ):
                        print(f'  QBER and Qx below 3x target, performing fine adjustment')
                        if self._motor_states[motor.device_info.serial_number]['moving'] == False:
                            motor.jog(
                                direction=direction,
                                acceleration=acceleration,
                                max_velocity=1
                            )
                            self._motor_states[motor.device_info.serial_number]['moving'] = True
                            time.sleep(0.1)
                            motor.stop()
                            self._motor_states[motor.device_info.serial_number]['moving'] = False

                    else:
                        with suppress_stdout():
                            if self._motor_states[motor.device_info.serial_number]['moving'] == False:
                                motor.jog(
                                    direction=direction,
                                    acceleration=acceleration,
                                    max_velocity=max_velocity
                                )
                                self._motor_states[motor.device_info.serial_number]['moving'] = True
                            (
                                motor_probe_qber,
                                motor_probe_qx,
                                motor_probe_rate,
                                motor_probe_objective,
                                motor_probe_kps
                            ) = self.measure(samples=samples)
                            if (motor_probe_objective < motor_baseline_objective):
                                motor.stop()
                                self._motor_states[motor.device_info.serial_number]['moving'] = False

                                # set reverse direction for next iteration
                                if direction == base_motor.MotorDirection.FORWARD:
                                    self._motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.BACKWARD
                                else:
                                    self._motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.FORWARD
                                break

    def measure(
            self,
            samples: int = 3
    ) -> tuple[float, float, float, float, float]:
        qber_samples: list[float] = []
        qx_samples: list[float] = []
        rate_samples: list[float] = []
        for _ in range(samples):
            baseline_data = timetagger.Data.from_raw_data(
                raw_data=self.tt.measure(),
                channel_groups=self.tt.channel_groups
            )

            qber_samples.append(baseline_data.qber)
            qx_samples.append(baseline_data.qx)
            rate_samples.append(baseline_data.rate)

        m_qber = float(np.mean(qber_samples))
        m_qx = float(np.mean(qx_samples))
        m_rate = float(np.mean(rate_samples))

        m_objective = objective(
            rate=m_rate,
            qber=m_qber,
            qx=m_qx
        )
        m_kps = keys_per_second(
            coincidences=m_rate,
            qber=m_qber,
            qx=m_qx
        )

        return m_qber, m_qx, m_rate, m_objective, m_kps
    
    # def __del__(self) -> None:
    #     print('Stopping motors')
    #     for motor in self.motors:
    #         motor.stop()

    #     print('Disconnecting timetagger')
    #     try:
    #         self.tt.disconnect()
    #     except Exception:
    #         pass

def main() -> None:
    with suppress_stdout():
        motors: list[base_motor.Motor] = []
        motors.append(thorlabs_motor.ThorlabsMotor(serial_number=QWP1))
        motors.append(thorlabs_motor.ThorlabsMotor(serial_number=HWP))
        motors.append(k10cr2_motor.ThorlabsMotor(serial_number=QWP2))

    tt = remote_timetagger.RemoteTimetagger(
        host=MEASUREMENT_SERVER_HOST,
        port=MEASUREMENT_SERVER_PORT,
        model='Logic-16'
    )

    try:
        pol_comp = PolarisationCompensator(
            motors=motors,
            tt=tt,
            target_qber=0.05,
            target_qx=0.05,
            samples=2,
            max_velocity=5.0,
            max_iterations=0,
            # start_at_0=True,
            # scramble_motors=True,
            # scramble_min_time=1,
            # scramble_max_time=2
        )

    except KeyboardInterrupt:
        print('KeyboardInterrupt received — stopping motors.')
        for m in motors:
            try:
                m.stop()
            except Exception:
                pass

    finally:
        print('Stopping motors')
        for motor in motors:
            motor.stop()

        print('Disconnecting timetagger')
        try:
            tt.disconnect()
        except Exception:
            pass

if __name__ == '__main__':
    # for setting motors to 0 without running pol comp
    # with suppress_stdout():
    #     motors: list[base_motor.Motor] = []
    #     motors.append(thorlabs_motor.ThorlabsMotor(serial_number=QWP1))
    #     motors.append(thorlabs_motor.ThorlabsMotor(serial_number=HWP))
    #     motors.append(k10cr2_motor.ThorlabsMotor(serial_number=QWP2))
    
    # for motor in motors:
    #     set_motor_to_0(motor=motor)
    #     motor.stop()

    main()