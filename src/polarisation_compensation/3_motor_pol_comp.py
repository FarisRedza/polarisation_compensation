import sys
import typing
import time
import random
import io
import threading
from contextlib import contextmanager

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

@contextmanager
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


def scramble_motor(motor: base_motor.Motor) -> None:
    direction = random.choice([
        base_motor.MotorDirection.BACKWARD,
        base_motor.MotorDirection.FORWARD
    ])
    rotation_time = random.randint(1, 10)
    motor.jog(
        direction=direction,
        acceleration=20.0,
        max_velocity=25.0
    )
    time.sleep(rotation_time)
    motor.stop()


def small_jiggle(motor: base_motor.Motor, max_time: float = 0.2) -> None:
    """Small random jitter to escape local minima."""
    direction = random.choice([
        base_motor.MotorDirection.BACKWARD,
        base_motor.MotorDirection.FORWARD
    ])
    duration = random.uniform(0.02, max_time)
    with suppress_stdout():
        motor.jog(direction=direction, acceleration=10.0, max_velocity=10.0)
        time.sleep(duration)
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
        return kps
    else:
        return - (d_qber + d_qx)


class PolarisationCompensator:
    def __init__(
            self,
            motors: list[base_motor.Motor],
            tt: timetagger.TimeTagger
    ) -> None:
        self.motors = motors
        self.tt = tt

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

    def optimise(
        self,
        target_qber: float = 0.1,
        target_qx: float = 0.1,
        max_iterations: int = 100,
        samples: int = 3,
        jog_time: float = 0.5,
        adaptive: bool = False,
        min_jog_time: typing.Optional[float] = None,
        max_jog_time: typing.Optional[float] = None,
        acceleration: float = 20.0,
        max_velocity: float = 25.0,
        start_at_0: bool = False,
        scramble_motors: bool = False,
    ) -> None:
        self._motor_state = {}
        for m in self.motors:
            self._motor_state[m.device_info.serial_number] = {
                'improved_dir': None,
                'jog_time': jog_time
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
                        args=(motor,)
                    ))
                    motor_thread[i].start()
                for thread in motor_thread:
                    thread.join()

        time.sleep(1)
        start_time = time.time()
        print('Starting compensation')

        try:
            for i in range(max_iterations):
                print(f'Iteration: {i+1}/{max_iterations}')
                for motor in self.motors:
                    motor_jog_time: float = self._motor_state[motor.device_info.serial_number]['jog_time']
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
                        print(f'Target achieved in {i+1} iterations, time: {time.time()-start_time}s')
                        return

                    direction = self._motor_state[motor.device_info.serial_number]['improved_dir']
                    if not direction:
                        direction = random.choice([
                            base_motor.MotorDirection.BACKWARD,
                            base_motor.MotorDirection.FORWARD
                        ])
                        print(f'    Probing random direction {direction.name} (jog_time={motor_jog_time:.3f}s)')
                    else:
                        print(f'    Probing direction {direction.name} (jog_time={motor_jog_time:.3f}s)')
                    with suppress_stdout():
                        motor.jog(
                            direction=direction,
                            acceleration=acceleration,
                            max_velocity=max_velocity
                        )
                        time.sleep(motor_jog_time)
                        motor.stop()
                        time.sleep(0.001)

                    (
                        motor_probe_qber,
                        motor_probe_qx,
                        motor_probe_rate,
                        motor_probe_objective,
                        motor_probe_kps
                    ) = self.measure(samples=samples)

                    if (motor_probe_objective > motor_baseline_objective):
                        self._motor_state[motor.device_info.serial_number]['improved_dir'] = direction
                        rel_improve = 100 * (
                            motor_probe_objective - motor_baseline_objective
                        ) / (abs(motor_baseline_objective) + 1e-12)

                        print(
                            f'    State improved by {rel_improve:.2f}%\n'
                            f'      QBER: {motor_baseline_qber:.4f} -> {motor_probe_qber:.4f}\n'
                            f'      Qx: {motor_baseline_qx:.4f} -> {motor_probe_qx:.4f}\n'
                            f'      Rate: {motor_baseline_rate:.2f} -> {motor_probe_rate:.2f}\n'
                            f'      KPS: {motor_baseline_kps:.2f} -> {motor_probe_kps:.2f}\n'
                            f'      Obj: {motor_baseline_objective:.2f} -> {motor_probe_objective:.2f}'
                        )
                        
                        if adaptive:
                            if rel_improve >= 2.5:
                                motor_jog_time*= 0.7
                                if max_jog_time:
                                    self._motor_state[motor.device_info.serial_number]['jog_time'] = min(
                                        motor_jog_time,
                                        max_jog_time
                                    )
                                else:
                                    self._motor_state[motor.device_info.serial_number]['jog_time'] = motor_jog_time
                            
                            elif rel_improve < 1:
                                motor_jog_time*= 1.3
                                if min_jog_time:
                                    self._motor_state[motor.device_info.serial_number]['jog_time'] = max(
                                        motor_jog_time,
                                        min_jog_time
                                    )
                                else:
                                    self._motor_state[motor.device_info.serial_number]['jog_time'] = motor_jog_time

                    else:
                        self._motor_state[motor.device_info.serial_number]['improved_dir'] = None
                        print('    State not improved, returning to original position')
                        with suppress_stdout():
                            direction = base_motor.MotorDirection.FORWARD if direction == base_motor.MotorDirection.BACKWARD else base_motor.MotorDirection.BACKWARD
                            self._motor_state[motor.device_info.serial_number]['improved_dir'] = direction
                            motor.jog(
                                direction=direction,
                                acceleration=acceleration,
                                max_velocity=max_velocity
                            )
                            time.sleep(motor_jog_time)
                            motor.stop()
                            time.sleep(0.001)

        except KeyboardInterrupt:
            print('KeyboardInterrupt received — stopping motors.')
            for m in self.motors:
                try:
                    m.stop()
                except Exception:
                    pass

        finally:
            try:
                self.tt.disconnect()
            except Exception:
                pass


if __name__ == '__main__':
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

    pol_comp = PolarisationCompensator(
        motors=motors,
        tt=tt
    )

    pol_comp.optimise(
        target_qber=0.05,
        target_qx=0.1,
        samples=5,
        jog_time=0.5,
        adaptive=False,
        # max_jog_time=1.0,
        # min_jog_time=0.1,
        max_iterations=100,
        start_at_0=True,
        scramble_motors=True
    )

    for motor in motors:
        try:
            motor.stop()
            time.sleep(0.1)
        except Exception:
            pass
    try:
        tt.disconnect()
    except Exception:
        pass
