import sys
import pathlib
import time
import random
import io
import threading
from contextlib import contextmanager

import numpy as np

sys.path.append(str(pathlib.Path.cwd()))
from bb84 import timetagger
from bb84 import remote_timetagger
from motor import thorlabs_motor
# from motor import elliptec_motor
from motor import k10cr2_motor
from motor import base_motor

MEASUREMENT_SERVER_HOST = '137.195.63.45'
MEASUREMENT_SERVER_PORT = 5001

QWP1 = '55353314'
HWP = '55356974'
# QWP2 = '11400887'
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
    with suppress_stdout():
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
    x = np.clip(x, 1e-12, 1 - 1e-12)  # avoid log2(0)
    return -x * np.log2(x) - (1 - x) * np.log2(1 - x)


def keys_per_second(
        coincidences: float,
        qber: float,
        qx: float,
        f_ec: float = 1.1
) -> float:
    rate = coincidences * (1 - f_ec * binary_entropy(qber) - binary_entropy(qx))
    return rate


def objective(data: timetagger.Data) -> float:
    """Hybrid objective: maximise key rate if positive, else minimise QBER+Qx."""
    kps = keys_per_second(
        coincidences=data.rate,
        qber=data.qber,
        qx=data.qx
    )
    if kps > 0:
        return kps
    else:
        return - (data.qber + data.qx)


class PolarisationCompensator:
    def __init__(
            self,
            motors: list[base_motor.Motor],
            tt: timetagger.TimeTagger
    ) -> None:
        self.motors = motors
        self.tt = tt
        # per-motor memory: last direction and adaptive step (rotation_time)
        # keyed by motor.device_info.serial_number
        self._motor_state = {}
        for m in self.motors:
            self._motor_state[m.device_info.serial_number] = {
                'last_dir': None,
                'step': 0.05  # initial rotation_time (seconds)
            }

    def optimise(
        self,
        max_iterations: int = 30,
        target: float = 0.05,
        acceleration: float = 20.0,
        max_velocity: float = 25.0,
        rotation_time: float = 0.05,
        plateau_patience: int = 3,
        min_rel_improve: float = 0.005,
        required_stable_rounds: int = 3,
        stable_sleep: float = 0.5,
        start_at_0: bool = False,
        scramble_motors: bool = False,
        adaptive: bool = True,
        step_shrink: float = 0.6,
        step_expand: float = 1.2,
        min_step: float = 0.01,
        max_step: float = 0.5,
        random_restart_jiggle: float = 0.12
    ) -> None:
        if start_at_0:
            print('Setting motor positions to 0')
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
            motor_thread: list[threading.Thread] = []
            for i, motor in enumerate(self.motors):
                motor_thread.append(threading.Thread(
                    target=scramble_motor,
                    args=(motor,)
                ))
                motor_thread[i].start()
            for thread in motor_thread:
                thread.join()

        print('Starting compensation')
        no_progress_iters = 0
        
        for motor in self.motors:
            self._motor_state[motor.device_info.serial_number]['step'] = rotation_time

        try:
            for i in range(max_iterations):
                baseline_data = timetagger.Data.from_raw_data(
                    raw_data=self.tt.measure(),
                    channel_groups=self.tt.channel_groups
                )
                baseline_objective = objective(data=baseline_data)

                kps = keys_per_second(
                    coincidences=baseline_data.rate,
                    qber=baseline_data.qber,
                    qx=baseline_data.qx
                )
                print(
                    f'Iter {i:03d}: '
                    f'QBER={baseline_data.qber:.4f}, '
                    f'Qx={baseline_data.qx:.4f}, '
                    f'Rate={baseline_data.rate:.2f} cps, '
                    f'KeyRate={max(kps, 0):.2f}, '
                    f'Obj={baseline_objective:.2f}'
                )

                if (
                    baseline_data.qber < target
                    and baseline_data.qx < target
                    and kps > 0
                ):
                    verification_ok = True
                    for verification_round in range(required_stable_rounds):
                        time.sleep(stable_sleep)
                        verification_data = timetagger.Data.from_raw_data(
                            raw_data=self.tt.measure(),
                            channel_groups=self.tt.channel_groups
                        )
                        verification_round_kps = keys_per_second(
                            coincidences=verification_data.rate,
                            qber=verification_data.qber,
                            qx=verification_data.qx
                        )
                        print(
                            f'  Verify {verification_round+1}/{required_stable_rounds}: '
                            f'QBER={verification_data.qber:.4f}, '
                            f'Qx={verification_data.qx:.4f}, '
                            f'KeyRate={max(verification_round_kps,0):.2f}'
                        )
                        if not (
                            verification_data.qber < target
                            and verification_data.qx < target
                            and verification_round_kps > 0
                        ):
                            verification_ok = False
                            print('  Verification failed (metrics not stable).')
                            break

                    if verification_ok:
                        print(f'Target achieved and verified for {required_stable_rounds} consecutive checks. Stopping.')
                        return
                    else:
                        no_progress_iters = 0
                        print('Continuing optimisation after failed verification.')

                state_improved = False

                # iterate motors but keep a local best per outer iteration (optional future improvement)
                for motor in self.motors:
                    serial = motor.device_info.serial_number
                    # choose direction using memory: if last direction improved, bias towards it
                    last_dir = self._motor_state[serial]['last_dir']
                    # pick direction: prefer last_dir (70%) else random
                    if last_dir is None:
                        direction = random.choice([
                            base_motor.MotorDirection.BACKWARD,
                            base_motor.MotorDirection.FORWARD
                        ])
                    else:
                        if random.random() < 0.7:
                            direction = last_dir
                        else:
                            direction = base_motor.MotorDirection.BACKWARD if last_dir == base_motor.MotorDirection.FORWARD else base_motor.MotorDirection.FORWARD

                    step = self._motor_state[serial]['step'] if adaptive else rotation_time

                    print(f'  Motor {serial} probing {direction.name} (step={step:.3f}s)')

                    motor_baseline_data = timetagger.Data.from_raw_data(
                        raw_data=self.tt.measure(),
                        channel_groups=self.tt.channel_groups
                    )
                    motor_baseline_objective = objective(data=motor_baseline_data)

                    # Probe move
                    with suppress_stdout():
                        motor.jog(
                            direction=direction,
                            acceleration=acceleration,
                            max_velocity=max_velocity
                        )
                        time.sleep(step)
                        motor.stop()

                    motor_probe_data = timetagger.Data.from_raw_data(
                        raw_data=self.tt.measure(),
                        channel_groups=self.tt.channel_groups
                    )
                    motor_probe_objective = objective(data=motor_probe_data)

                    rel_improve = (motor_probe_objective - motor_baseline_objective) / (abs(motor_baseline_objective) + 1e-12)

                    if (
                        motor_probe_objective > motor_baseline_objective
                        and rel_improve >= min_rel_improve
                    ):
                        # success: keep direction and shrink step (finer search)
                        state_improved = True
                        self._motor_state[serial]['last_dir'] = direction
                        if adaptive:
                            new_step = max(min_step, self._motor_state[serial]['step'] * step_shrink)
                            self._motor_state[serial]['step'] = min(max_step, new_step)
                        print(
                            f'    ✔ Improvement: Obj {motor_baseline_objective:.2f} -> {motor_probe_objective:.2f} '
                            f'(Δrel={100*rel_improve:.2f}%). '
                            f'QBER {motor_baseline_data.qber:.4f} -> {motor_probe_data.qber:.4f}, '
                            f'Qx {motor_baseline_data.qx:.4f} -> {motor_probe_data.qx:.4f}'
                        )
                    else:
                        # failure: reverse and maybe increase step slightly to escape shallow minima
                        reverse = (
                            base_motor.MotorDirection.BACKWARD
                            if direction == base_motor.MotorDirection.FORWARD
                            else base_motor.MotorDirection.FORWARD
                        )
                        print(f'    ✖ No improvement (Obj {motor_baseline_objective:.2f} -> {motor_probe_objective:.2f}). Reversing.')
                        with suppress_stdout():
                            motor.jog(
                                direction=reverse,
                                acceleration=acceleration,
                                max_velocity=max_velocity
                            )
                            time.sleep(step)
                            motor.stop()

                        # update memory: flip last_dir (so next probe tries the other way)
                        self._motor_state[serial]['last_dir'] = reverse
                        if adaptive:
                            new_step = min(max_step, self._motor_state[serial]['step'] * step_expand)
                            self._motor_state[serial]['step'] = max(min_step, new_step)

                # Plateau / progress logic
                if not state_improved:
                    no_progress_iters += 1
                    print(f'  No improvement this iteration ({no_progress_iters}/{plateau_patience}).')
                    if no_progress_iters >= plateau_patience:
                        # perform a small random restart instead of full stop
                        print('Plateau detected — performing small random restart (jiggle).')
                        for m in self.motors:
                            small_jiggle(m, max_time=random_restart_jiggle)
                        no_progress_iters = 0
                else:
                    no_progress_iters = 0

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
        # motors.append(elliptec_motor.ElliptecMotor(serial_number=QWP2))
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
        target=0.04,
        rotation_time=0.5,
        max_iterations=500,
        plateau_patience=5,
        # adaptive=False,
        step_shrink=0.75,
        max_step=0.5,
        # start_at_0=True,
        # scramble_motors=True
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
