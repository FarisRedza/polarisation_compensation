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

def jog(motor: base_motor.Motor, direction: str, step_time: float) -> None:
    text_trap = io.StringIO()
    sys.stdout = text_trap
    motor_direction = base_motor.MotorDirection.FORWARD if direction == 'CW' else base_motor.MotorDirection.BACKWARD
    motor.jog(
        direction=motor_direction,
        acceleration=20.0,
        max_velocity=25.0
    )
    time.sleep(step_time)
    motor.stop()
    sys.stdout = sys.__stdout__


def measure_error(tt: timetagger.TimeTagger, repeats: int = 5) -> tuple[float, float, float]:
    qbers, qxs = [], []
    for _ in range(repeats):
        data = timetagger.Data().from_raw_data(
            raw_data=tt.measure(),
            pattern=tt.pattern
        )
        qbers.append(data.qber)
        qxs.append(data.qx)
    qber = float(np.mean(qbers))
    qx = float(np.mean(qxs))
    return qber, qx, qber + qx

class PolarisationCompensator:
    def __init__(
            self,
            motors: list[base_motor.Motor],
            tt: timetagger.TimeTagger
    ) -> None:
        self.motors = motors
        self.tt = tt
        self.step_time = 0.2  # initial jog duration (s)
        self.min_step = 0.02  # minimum jog duration
        self.decay = 0.95     # step shrink factor per iteration

    def optimise(self, max_iters=200, target=0.05):
        for i in range(max_iters):
            qber, qx, err = measure_error(tt=self.tt)
            print(f"Iter {i:03d}: QBER={qber:.3f}, Qx={qx:.3f}, Err={err:.3f}")
            
            # if qber < target and qx < target:
            if qber < target:
                print("✅ Target reached!")
                break

            # pick random motor and direction to probe
            motor = random.choice(self.motors)
            direction = random.choice(["CW", "CCW"])

            # baseline error
            baseline_qber,  baseline_qx, baseline_err = measure_error(tt=self.tt)

            # test jog
            jog(motor=motor, direction=direction, step_time=self.step_time)
            qber2, qx2, err2 = measure_error(tt=self.tt)

            # if err2 > baseline_err:
            if qber2 > baseline_qber:
                # revert if worse (jog back opposite)
                opposite = "CW" if direction == "CCW" else "CCW"
                jog(motor=motor, direction=opposite, step_time=self.step_time)
                print(f"Reverted {motor.device_info.serial_number} (error worsened)")
            else:
                print(f"Kept {motor.device_info.serial_number} move (error improved)")

            # shrink step size over time
            self.step_time = max(self.step_time * self.decay, self.min_step)



if __name__ == '__main__':
    motor_qwp_1 = thorlabs_motor.ThorlabsMotor(serial_number=QWP1)
    motor_hwp = thorlabs_motor.ThorlabsMotor(serial_number=HWP)
    motor_qwp_2 = elliptec_motor.ElliptecMotor(serial_number=QWP2)    
    motors: list[base_motor.Motor] = [motor_qwp_1, motor_hwp, motor_qwp_2]

    tt=remote_timetagger.RemoteTimetagger(
            host=MEASUREMENT_SERVER_HOST,
            port=MEASUREMENT_SERVER_PORT,
            model='Logic-16'
        )
    pol_comp = PolarisationCompensator(
        motors=motors,
        tt=tt
    )
    try:
        pol_comp.optimise(target=0.5)
    except KeyboardInterrupt:
        for motor in motors:
            motor.stop()
        tt.disconnect()