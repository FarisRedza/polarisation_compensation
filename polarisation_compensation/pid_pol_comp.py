import sys
import pathlib
import typing
import time
import random
import io
import threading
import contextlib
import itertools

import numpy as np

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
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
        motor.move_to(position=0, acceleration=20.0, max_velocity=25.0)
        time.sleep(0.1)


def scramble_motor(motor: base_motor.Motor) -> None:
    direction = random.choice([base_motor.MotorDirection.BACKWARD, base_motor.MotorDirection.FORWARD])
    rotation_time = random.randint(10, 20)
    motor.jog(direction=direction, acceleration=20.0, max_velocity=25.0)
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
        qber: float,
        qx: float,
        qber_weight: float = 1.0,
        qx_weight: float = 1.0
    ) -> float:
    return qber*qber_weight + qx*qx_weight


class PID:
    def __init__(
            self,
            kp: float,
            ki: float,
            kd: float,
            output_limit: float = 25.0,
            enable_p: bool = True,
            enable_i: bool = True,
            enable_d: bool = True,
    ) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_limit = output_limit
        self.enable_p = enable_p
        self.enable_i = enable_i
        self.enable_d = enable_d

        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_time = None

    def reset(self) -> None:
        self.integral = 0
        self.prev_error = 0
        self.prev_time = None

    def compute(self, error, timestamp) -> float:
        if self.prev_time is None:
            self.prev_time = timestamp
            self.prev_error = error
            return 0.0

        dt = timestamp - self.prev_time
        if dt <= 0:
            return 0.0

        p = self.kp * error if self.enable_p else 0.0
        self.integral += error * dt
        i = self.ki * self.integral  if self.enable_i else 0.0
        d = self.kd * (error - self.prev_error) / dt  if self.enable_d else 0.0

        self.prev_error = error
        self.prev_time = timestamp

        output = p + i + d
        print(f'Velocity: {output:.2f}, P: {p:.2f}, I: {i:.2f}, D: {d:.2f}')
        return max(-self.output_limit, min(self.output_limit, output))


class PolarisationCompensator:
    def __init__(
            self,
            motors: list[base_motor.Motor],
            tt: timetagger.TimeTagger,
            target_qber: float = 0.1,
            target_qx: float = 0.1,
            max_iterations: int = 100,
            samples: int = 5,
            p_gain: float = 25.0,
            i_gain: float = 0.1,
            d_gain: float = 0.05,
            enable_p : bool = True,
            enable_i : bool = True,
            enable_d : bool = True,
            acceleration: float = 20.0,
            max_velocity: float = 25.0,
            random_direction: bool = True,
            start_at_0: bool = False,
            scramble_motors: bool = False
    ) -> None:
        self.motors = motors
        self.tt = tt
        self.target_qber = target_qber
        self.target_qx = target_qx
        self.max_iterations = max_iterations
        self.samples = samples
        self.random_direction = random_direction
        self.acceleration = acceleration
        self.max_velocity = max_velocity

        self._motor_states = {}
        for motor in self.motors:
            self._motor_states[motor.device_info.serial_number] = {
                'direction': random.choice([
                    base_motor.MotorDirection.BACKWARD,
                     base_motor.MotorDirection.FORWARD
                ]),
                'moving': False,
                'pid': PID(
                    kp=p_gain,
                    ki=i_gain,
                    kd=d_gain,
                    enable_p=enable_p,
                    enable_i=enable_i,
                    enable_d=enable_d,
                    output_limit=self.max_velocity

                )
            }

        if start_at_0:
            print('Setting motor positions to 0')
            with suppress_stdout():
                threads = [
                    threading.Thread(target=set_motor_to_0, args=(motor,))
                    for motor in self.motors
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

        if scramble_motors:
            print('Scrambling motors')
            with suppress_stdout():
                threads = [
                    threading.Thread(target=scramble_motor, args=(motor,))
                    for motor in self.motors
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()        

        time.sleep(1)
        self.start_time = time.time()
        print('Starting compensation')
        self.compensate()

    def measure(self) -> tuple[float, float]:
        qber_samples, qx_samples, rate_samples = [], [], []

        for _ in range(self.samples):
            data = timetagger.Data.from_raw_data(
                raw_data=self.tt.measure(),
                channel_groups=self.tt.channel_groups
            )
            qber_samples.append(data.qber)
            qx_samples.append(data.qx)
            rate_samples.append(data.rate)

        m_qber = float(np.mean(qber_samples))
        m_qx = float(np.mean(qx_samples))

        return m_qber, m_qx

    def stop_all_motors(self) -> None:
        for motor in self.motors:
            motor.stop()

    # def compensate(self) -> None:
    #     if self.max_iterations == 0:
    #         iterator = itertools.count()
    #     else:
    #         iterator = range(self.max_iterations)

    #     for i in iterator:
    #         if self.max_iterations != 0:
    #             print(f'Iteration: {i+1}/{self.max_iterations}')

    #         baseline_qber, baseline_qx = self.measure()
    #         baseline_objective = objective(
    #             qber=baseline_qber,
    #             qx=baseline_qx
    #         )
    #         for motor in self.motors:
    #             print(f'  Motor {motor.device_info.serial_number}')
    #             if self.random_direction:
    #                 direction = random.choice([
    #                     base_motor.MotorDirection.FORWARD,
    #                     base_motor.MotorDirection.BACKWARD
    #                 ])
    #             else:
    #                 direction = self._motor_states[motor.device_info.serial_number]['direction']

    #             if (
    #                 baseline_qber < self.target_qber
    #                 and baseline_qx < self.target_qx
    #             ):
    #                 self.stop_all_motors()
    #             else:
    #                 velocity = self._motor_states[motor.device_info.serial_number]['pid'].compute(
    #                     error=baseline_objective - objective(
    #                         qber=self.target_qber,
    #                         qx=self.target_qx
    #                     ),
    #                     timestamp=time.time()
    #                 )
    #                 motor.jog(
    #                     direction=direction,
    #                     acceleration=self.acceleration,
    #                     max_velocity=abs(velocity)
    #                 )
    #                 jog_qber, jog_qx = self.measure()
    #                 jog_objective = objective(
    #                     qber=jog_qber,
    #                     qx=jog_qx
    #                 )
    #                 if jog_objective > baseline_objective:
    #                     print('No improvement - stopping all motors')
    #                     self.stop_all_motors()
    #                     match direction:
    #                         case base_motor.MotorDirection.FORWARD:
    #                             self._motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.BACKWARD
    #                         case base_motor.MotorDirection.BACKWARD:
    #                             self._motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.FORWARD

    #                 if (jog_qber > baseline_qber and jog_qx < baseline_qx) \
    #                 or (jog_qber < baseline_qber and jog_qx > baseline_qx):
    #                     print('Mixed improvement - stopping all motors')
    #                     self.stop_all_motors()

    #                 baseline_qber, baseline_qx = jog_qber, jog_qx
    #                 baseline_objective = jog_objective

    def compensate(self) -> None:
        if self.max_iterations == 0:
            iterator = itertools.count()
        else:
            iterator = range(self.max_iterations)

        for i in iterator:
            if self.max_iterations != 0:
                print(f'Iteration: {i+1}/{self.max_iterations}')

            # baseline_qber, baseline_qx = self.measure()
            # baseline_objective = objective(
            #     qber=baseline_qber,
            #     qx=baseline_qx
            # )
            for motor in self.motors:
                print(f'\n=== Motor {motor.device_info.serial_number} ===')
                if self.random_direction:
                    direction = random.choice([
                        base_motor.MotorDirection.FORWARD,
                        base_motor.MotorDirection.BACKWARD
                    ])
                else:
                    direction = self._motor_states[motor.device_info.serial_number]['direction']

                baseline_qber, baseline_qx = self.measure()
                baseline_objective = objective(
                    qber=baseline_qber,
                    qx=baseline_qx
                )
                if (
                    baseline_qber < self.target_qber
                    and baseline_qx < self.target_qx
                ):
                    print('  Already at target - skipping motor')
                else:
                    while True:
                        velocity = self._motor_states[motor.device_info.serial_number]['pid'].compute(
                            error=baseline_objective - objective(
                                qber=self.target_qber,
                                qx=self.target_qx
                            ),
                            timestamp=time.time()
                        )
                        if self._motor_states[motor.device_info.serial_number]['moving'] == False:
                            motor.jog(
                                direction=direction,
                                acceleration=self.acceleration,
                                max_velocity=abs(velocity)
                            )
                            self._motor_states[motor.device_info.serial_number]['moving'] = True

                        jog_qber, jog_qx = self.measure()
                        jog_objective = objective(
                            qber=jog_qber,
                            qx=jog_qx
                        )
                        if jog_objective > baseline_objective:
                            print('No improvement - stopping motor')
                            motor.stop()
                            self._motor_states[motor.device_info.serial_number]['moving'] = False
                            match direction:
                                case base_motor.MotorDirection.FORWARD:
                                    self._motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.BACKWARD
                                case base_motor.MotorDirection.BACKWARD:
                                    self._motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.FORWARD
                            break

                        # if (jog_qber > baseline_qber and jog_qx < baseline_qx) \
                        # or (jog_qber < baseline_qber and jog_qx > baseline_qx):
                        #     print('Mixed improvement - stopping motor')
                        #     motor.stop()
                        #     self._motor_states[motor.device_info.serial_number]['moving'] = False
                        #     break

                        baseline_qber, baseline_qx = jog_qber, jog_qx
                        baseline_objective = jog_objective


def main() -> None:
    with suppress_stdout():
        motors: list[base_motor.Motor] = [
            thorlabs_motor.ThorlabsMotor(serial_number=QWP1),
            thorlabs_motor.ThorlabsMotor(serial_number=HWP),
            k10cr2_motor.ThorlabsMotor(serial_number=QWP2)
        ]

    tt = remote_timetagger.RemoteTimetagger(
        host=MEASUREMENT_SERVER_HOST,
        port=MEASUREMENT_SERVER_PORT,
        model='Logic-16'
    )

    try:
        PolarisationCompensator(
            motors=motors,
            tt=tt,
            target_qber=0.05,
            target_qx=0.05,
            max_iterations=0,
            samples=2,
            p_gain=5,
            i_gain=0.1,
            d_gain=0.05,
            enable_p=True,
            enable_i=True,
            enable_d=True,
            random_direction=True,
            max_velocity=25.0,
            # start_at_0=True,
            # scramble_motors=True
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
    main()
