import time
import random
import io
import sys

import numpy as np

import bb84.timetagger as timetagger
import bb84.remote_timetagger as remote_timetagger
import motor.thorlabs_motor as thorlabs_motor
import motor.elliptec_motor as elliptec_motor
import motor.base_motor as base_motor

MEASUREMENT_SERVER_HOST = '137.195.63.6'
MEASUREMENT_SERVER_PORT = 5001

QWP1 = '55353314'
HWP = '55356974'
QWP2 = '11400887'

def binary_entropy(x: float) -> float:
    x = np.clip(x, 1e-12, 1 - 1e-12) # avoid log2(0)
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
        stable_sleep: float = 0.5
    ) -> None:
        no_progress_iters = 0

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
                    f'KeyRate={kps:.2f}, '
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
                            f'KeyRate={verification_round_kps:.2f}'
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

                for motor in self.motors:
                    direction = random.choice([
                        base_motor.MotorDirection.BACKWARD,
                        base_motor.MotorDirection.FORWARD
                    ])
                    print(f'  Motor {motor.device_info.serial_number} probing {direction.name}')

                    motor_baseline_data = timetagger.Data.from_raw_data(
                        raw_data=self.tt.measure(),
                        channel_groups=self.tt.channel_groups
                    )
                    motor_baseline_objective = objective(data=motor_baseline_data)

                    text_trap = io.StringIO()
                    old_stdout = sys.stdout
                    try:
                        sys.stdout = text_trap
                        motor.jog(
                            direction=direction,
                            acceleration=acceleration,
                            max_velocity=max_velocity
                        )
                        time.sleep(rotation_time)
                        motor.stop()
                    finally:
                        sys.stdout = old_stdout

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
                        state_improved = True
                        print(
                            f'    ✔ Improvement: Obj {motor_baseline_objective:.2f} -> {motor_probe_objective:.2f} '
                            f'(Δrel={100*rel_improve:.2f}%). '
                            f'QBER {motor_baseline_data.qber:.4f} -> {motor_probe_data.qber:.4f}, '
                            f'Qx {motor_baseline_data.qx:.4f} -> {motor_probe_data.qx:.4f}'
                        )
                    else:
                        reverse = (
                            base_motor.MotorDirection.BACKWARD
                            if direction == base_motor.MotorDirection.FORWARD
                            else base_motor.MotorDirection.FORWARD
                        )
                        print(f'    ✖ No improvement (Obj {motor_baseline_objective:.2f} -> {motor_probe_objective:.2f}). Reversing.')
                        text_trap = io.StringIO()
                        old_stdout = sys.stdout
                        try:
                            sys.stdout = text_trap
                            motor.jog(
                                direction=reverse,
                                acceleration=acceleration,
                                max_velocity=max_velocity
                            )
                            time.sleep(rotation_time)
                            motor.stop()
                        finally:
                            sys.stdout = old_stdout

                # Plateau / progress logic
                if not state_improved:
                    no_progress_iters += 1
                    print(f'  No improvement this iteration ({no_progress_iters}/{plateau_patience}).')
                    if no_progress_iters >= plateau_patience:
                        print('Stopping: plateau reached (no improvements).')
                        break
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
    text_trap = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = text_trap
        motors: list[base_motor.Motor] = []
        motors.append(thorlabs_motor.ThorlabsMotor(serial_number=QWP1))
        motors.append(thorlabs_motor.ThorlabsMotor(serial_number=HWP))
        motors.append(elliptec_motor.ElliptecMotor(serial_number=QWP2))
    finally:
        sys.stdout = old_stdout

    print('Scrambling state')
    text_trap = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = text_trap
        for motor in motors:
            while abs(motor.position) > 5:
                motor.move_to(
                    position=0,
                    acceleration=20.0,
                    max_velocity=25.0
                )
                time.sleep(0.1)
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
    finally:
        sys.stdout = old_stdout

    tt = remote_timetagger.RemoteTimetagger(
        host=MEASUREMENT_SERVER_HOST,
        port=MEASUREMENT_SERVER_PORT,
        model='Logic-16'
    )

    pol_comp = PolarisationCompensator(
        motors=motors,
        tt=tt
    )

    print('Starting compensation')
    pol_comp.optimise()
    for motor in motors:
        try:
            motor.stop()
        except Exception:
            pass
    try:
        tt.disconnect()
    except Exception:
        pass
