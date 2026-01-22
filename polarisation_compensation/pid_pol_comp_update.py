import sys
import pathlib
import typing
import time
import random
import io
import threading
import contextlib
import itertools
import collections
import logging

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


def scramble_motor(
        motor: base_motor.Motor,
        min_time: int = 10,
        max_time: int = 20
) -> None:
    direction = random.choice([base_motor.MotorDirection.BACKWARD, base_motor.MotorDirection.FORWARD])
    rotation_time = random.randint(min_time, max_time)
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

def objective(qber: float, qx: float, tq: float = 0.05) -> float:
    return max(0, qber - tq)**2 + max(0, qx - tq)**2

class PID:
    def __init__(
            self,
            kp: float,
            ki: float,
            kd: float,
            min_limit: float = -25.0,
            max_limit: float = 25.0,
            enable_p: bool = True,
            enable_i: bool = True,
            enable_d: bool = True,
    ) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.min_limit = min_limit
        self.max_limit = max_limit
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

    def compute(self, error, timestamp) -> tuple[float, float, float]:
        if self.prev_time is None:
            self.prev_time = timestamp
            self.prev_error = error
            return 0.0, 0.0, 0.0

        dt = timestamp - self.prev_time
        if dt <= 0:
            return 0.0, 0.0, 0.0

        p = self.kp * error if self.enable_p else 0.0
        self.integral += error * dt
        i = self.ki * self.integral  if self.enable_i else 0.0
        d = self.kd * (error - self.prev_error) / dt  if self.enable_d else 0.0

        self.prev_error = error
        self.prev_time = timestamp

        return p, i, d


class PolarisationCompensator:
    def __init__(
            self,
            motors: list[base_motor.Motor],
            tt: timetagger.TimeTagger,
    ) -> None:
        self.motors = motors
        self.tt = tt

    def set_motor_pos_to_0(self) -> None:
        """
        Returns all motor positions to 0
        """
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
        time.sleep(0.1)

    def scramble_motor_pos(
            self,
            min_time: int = 10,
            max_time: int = 20
    ) -> None:
        """
        Jogs all motors in a random direction
        
        :param min_time: Minimum jog time
        :type min_time: int
        :param max_time: Maximum jog time
        :type max_time: int
        """
        print('Scrambling motors')
        with suppress_stdout():
            threads = [
                threading.Thread(
                    target=scramble_motor,
                    args=(motor, min_time, max_time)
                )
                for motor in self.motors
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join() 
        time.sleep(0.1)   

    def stop_all_motors(self) -> None:
        for motor in self.motors:
            motor.stop()

    def measure(
            self,
            samples: int = 0,
            measure_time: float = 1.0
    ) -> tuple[float, float]:
        qber_samples, qx_samples, rate_samples = collections.deque(), collections.deque(), collections.deque()

        for _ in range(samples):
            data = timetagger.Data.from_raw_data(
                raw_data=self.tt.measure(seconds=measure_time),
                channel_groups=self.tt.channel_groups
            )
            qber_samples.append(data.qber)
            qx_samples.append(data.qx)
            rate_samples.append(data.rate)

        m_qber = float(np.mean(qber_samples))
        m_qx = float(np.mean(qx_samples))

        return m_qber, m_qx

    def compensate(
            self,
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
            min_velocity: float = 1.0,
            max_velocity: float = 25.0,
            wait_before_measure: float = 0.0,
            measure_time: float = 1.0,
            random_direction: bool = True,
            try_reverse_direction: bool = True,
            allow_mixed_improvement: bool = True,
            enable_logging: bool = True,
            verbose: bool = True
    ) -> None:
        """
        Polarisation compensation method

        :param target_qber: Max QBER allowed
        :type target_qber: float
        :param target_qx: Max Qx allowed
        :type target_qx: float
        :param max_iterations: Number iterations allowed, set to 0 for continuous mode
        :type max_iterations: int
        :param samples: Number of measurement samples
        :type samples: int
        :param p_gain: Proportional control gain
        :type p_gain: float
        :param i_gain: Integral action gain
        :type i_gain: float
        :param d_gain: Derivative action gain
        :type d_gain: float
        :param enable_p: Enable proportional control
        :type enable_p: bool
        :param enable_i: Enable integral action
        :type enable_i: bool
        :param enable_d: Enable derivative action
        :type enable_d: bool
        :param acceleration: Motor acceleration
        :type acceleration: float
        :param min_velocity: Minimum motor velocity
        :type min_velocity: float
        :param max_velocity: Maximum motor velocity
        :type max_velocity: float
        :param measure_time: Measurmement time for each measurement sample
        :type measure_time: float
        :param random_direction: Choose a random direction for each motor jog
        :type random_direction: bool
        :param try_reverse_direction: If jog direction stops improving, try other direction on
        :type try_reverse_direction: bool
        :param allow_mixed_improvement: Allow situations where for example QBER drops but Qx increases
        :type allow_mixed_improvement: bool
        """
        logger = logging.getLogger(__file__.strip('.py'))
        logging.basicConfig(
            filename=f'{__file__}'.replace('.py','_27.log'),
            encoding='utf-8',
            filemode='a',
            format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s', 
            datefmt='%H:%M:%S',
            level=logging.DEBUG
        )

        prev_motor = ''
        motor_states = {}
        for motor in self.motors:
            motor_states[motor.device_info.serial_number] = {
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
                    min_limit=min_velocity,
                    max_limit=max_velocity
                )
            }

        print('Starting compensation')
        start_time = time.time()

        if max_iterations == 0:
            iterator = itertools.count()
        else:
            iterator = range(max_iterations)

        for iter in iterator:
            if max_iterations != 0:
                if verbose: print(f'Iteration: {iter+1}/{max_iterations}')

            if try_reverse_direction:
                motor_list = [m_i for m in self.motors for m_i in (m,m)]
            else:
                motor_list = self.motors

            for motor in motor_list:
                if verbose: print(f'\n=== Motor {motor.device_info.serial_number} ===')
                if random_direction and motor.device_info.serial_number != prev_motor:
                    direction = random.choice([
                        base_motor.MotorDirection.FORWARD,
                        base_motor.MotorDirection.BACKWARD
                    ])
                    if verbose: print(f'Jogging direction {direction.name}')
                    logger.debug(f'{iter=}: Motor {motor.device_info.serial_number} | Jogging direction {direction.name}')
                else:
                    direction: base_motor.MotorDirection = motor_states[motor.device_info.serial_number]['direction']
                    if verbose: print(f'Jogging reverse direction {direction.name}')
                    logger.debug(f'{iter=}: Motor {motor.device_info.serial_number} | Jogging reverse direction {direction.name}')

                baseline_qber, baseline_qx = self.measure(
                    samples=samples,
                    measure_time=measure_time
                )
                baseline_objective = objective(
                    qber=baseline_qber,
                    qx=baseline_qx
                )
                logger.info(
                    f'{iter=}: Motor {motor.device_info.serial_number} | QBER={baseline_qber}, Qx={baseline_qx}'
                )
                if (
                    baseline_qber < target_qber
                    and baseline_qx < target_qx
                ):
                    if max_iterations == 0:
                        if verbose: print('Already at target - skipping motor')
                        logger.debug(f'{iter=}: Motor {motor.device_info.serial_number} | Already at target - skipping motor')
                    else:
                        total_time = time.time()
                        print(f'Target achieved in {iter+1}/{max_iterations} iterations - Time: {(total_time - start_time):.2f} s')
                        logger.debug(f'Target achieved in {iter+1}/{max_iterations} iterations - Time: {(total_time - start_time):.2f} s')
                        return
                else:
                    while True:
                        p, i, d = motor_states[motor.device_info.serial_number]['pid'].compute(
                            error=baseline_objective - objective(
                                qber=target_qber,
                                qx=target_qx
                            ),
                            timestamp=time.time()
                        )
                        pid = float(p+i+d)
                        velocity = max(min_velocity, min(max_velocity, pid))
                        if verbose: print(f'Velocity: {velocity:.2f}, P: {p:.2f}, I: {iter:.2f}, D: {d:.2f}')

                        if verbose: print(f'QBER: {baseline_qber:.4f} | Qx {baseline_qx:.4f}')
                        if motor_states[motor.device_info.serial_number]['moving'] == False:
                            motor.jog(
                                direction=direction,
                                acceleration=acceleration,
                                max_velocity=abs(velocity)
                            )
                            motor_states[motor.device_info.serial_number]['moving'] = True

                        time.sleep(wait_before_measure)
                        jog_qber, jog_qx = self.measure(
                            samples=samples,
                            measure_time=measure_time
                        )
                        jog_objective = objective(
                            qber=jog_qber,
                            qx=jog_qx
                        )

                        prev_motor = motor.device_info.serial_number

                        logger.info(
                            f'{iter=}: Motor {motor.device_info.serial_number} | QBER={jog_qber}, Qx={jog_qx} | Dir={direction.name}, Vel={velocity}, P={p}, I={i}, D={d}'
                        )

                        if jog_objective > baseline_objective:
                            if verbose: print('No improvement - stopping motor')
                            logger.debug(f'{iter=}: Motor {motor.device_info.serial_number} | No improvement - stopping motor')
                            motor.stop()
                            motor_states[motor.device_info.serial_number]['moving'] = False
                            match direction:
                                case base_motor.MotorDirection.FORWARD:
                                    motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.BACKWARD
                                case base_motor.MotorDirection.BACKWARD:
                                    motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.FORWARD
                            break

                        if not allow_mixed_improvement:
                            if (jog_qber > baseline_qber and jog_qx < baseline_qx) \
                            or (jog_qber < baseline_qber and jog_qx > baseline_qx):
                                if verbose: print('Mixed improvement - stopping motor')
                                logger.debug(f'{iter=}: Motor {motor.device_info.serial_number} | Mixed improvement - stopping motor')
                                motor.stop()
                                motor_states[motor.device_info.serial_number]['moving'] = False
                                match direction:
                                    case base_motor.MotorDirection.FORWARD:
                                        motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.BACKWARD
                                    case base_motor.MotorDirection.BACKWARD:
                                        motor_states[motor.device_info.serial_number]['direction'] = base_motor.MotorDirection.FORWARD
                                break

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
        pol_comp = PolarisationCompensator(
            motors=motors,
            tt=tt,
        )
        pol_comp.set_motor_pos_to_0()
        pol_comp.scramble_motor_pos()

        # # 24
        # pol_comp.compensate(
        #     target_qber=0.05,
        #     target_qx=0.05,
        #     max_iterations=0,
        #     samples=5,
        #     p_gain=17.0,
        #     i_gain=0.0,
        #     d_gain=0.0,
        #     enable_p=True,
        #     enable_i=True,
        #     enable_d=True,
        #     measure_time=0.05,
        #     wait_before_measure=0.0,
        #     random_direction=True,
        #     try_reverse_direction=True,
        #     allow_mixed_improvement=True,
        #     min_velocity=0.0,
        #     max_velocity=25.0,
        #     enable_logging=True,
        #     verbose=False
        # )

        # # 25
        # pol_comp.compensate(
        #     target_qber=0.05,
        #     target_qx=0.05,
        #     max_iterations=0,
        #     samples=5,
        #     p_gain=30.0,
        #     i_gain=0.0,
        #     d_gain=0.0,
        #     enable_p=True,
        #     enable_i=True,
        #     enable_d=True,
        #     measure_time=0.05,
        #     wait_before_measure=0.0,
        #     random_direction=True,
        #     try_reverse_direction=True,
        #     allow_mixed_improvement=True,
        #     min_velocity=0.0,
        #     max_velocity=25.0,
        #     enable_logging=True,
        #     verbose=False
        # )

        # # 26
        # pol_comp.compensate(
        #     target_qber=0.05,
        #     target_qx=0.05,
        #     max_iterations=0,
        #     samples=5,
        #     p_gain=100.0,
        #     i_gain=0.0,
        #     d_gain=0.0,
        #     enable_p=True,
        #     enable_i=True,
        #     enable_d=True,
        #     measure_time=0.05,
        #     wait_before_measure=0.0,
        #     random_direction=True,
        #     try_reverse_direction=True,
        #     allow_mixed_improvement=True,
        #     min_velocity=0.0,
        #     max_velocity=25.0,
        #     enable_logging=True,
        #     verbose=False
        # )

        # 27
        pol_comp.compensate(
            target_qber=0.05,
            target_qx=0.05,
            max_iterations=0,
            samples=5,
            p_gain=75.0,
            i_gain=0.0,
            d_gain=0.0,
            enable_p=True,
            enable_i=True,
            enable_d=True,
            measure_time=0.05,
            wait_before_measure=0.0,
            random_direction=True,
            try_reverse_direction=True,
            allow_mixed_improvement=True,
            min_velocity=0.0,
            max_velocity=25.0,
            enable_logging=True,
            verbose=False
        )

    except KeyboardInterrupt:
        print('KeyboardInterrupt received - stopping motors.')
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
