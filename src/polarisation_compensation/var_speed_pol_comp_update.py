import sys
import typing
import time
import random
import io
import threading
import contextlib
import itertools

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


# def objective(
#         data: typing.Optional[timetagger.Data] = None,
#         qber: typing.Optional[float] = None,
#         qx: typing.Optional[float] = None,
#         rate: typing.Optional[int | float] = None
# ) -> float:
#     """Hybrid objective: maximise key rate if positive, else minimise QBER+Qx."""
#     if data:
#         d_rate = data.rate
#         d_qber = data.qber
#         d_qx = data.qx
#     elif qber is not None and qx is not None and rate is not None:
#         d_rate = rate
#         d_qber = qber
#         d_qx = qx
#     else:
#         raise RuntimeError('Must provide data or qber, qx, rate')

#     kps = keys_per_second(coincidences=d_rate, qber=d_qber, qx=d_qx)
#     return kps if kps > 0 else -(d_qber + d_qx)

def objective(
        data: typing.Optional[timetagger.Data] = None,
        qber: typing.Optional[float] = None,
        qx: typing.Optional[float] = None,
        rate: typing.Optional[int | float] = None,
        qber_limit: typing.Optional[float] = 0.11,
        qx_limit: typing.Optional[float] = 0.11,
) -> float:
    if data:
        d_rate = data.rate
        d_qber = data.qber
        d_qx = data.qx
    elif qber is not None and qx is not None and rate is not None:
        d_rate = rate
        d_qber = qber
        d_qx = qx
    else:
        raise RuntimeError('Must provide data or qber, qx, rate')

    kps = keys_per_second(d_rate, d_qber, d_qx)

    if qber_limit and qx_limit:
        qber_frac = d_qber / qber_limit
        qx_frac = d_qx / qx_limit

        security_penalty = qber_frac**2 + qx_frac**2
        beta = 50

        print(f'KPS: {kps}')
        print(f'{security_penalty=}')
        objective = kps - beta * security_penalty

    else:
        norm_kps = kps / (kps + 1e-6)

        error = d_qber + d_qx
        alpha = 0.2

        objective = norm_kps - alpha * error
    
    print(f'  Obj: {objective}')
    return objective



Measurement = typing.NamedTuple(
    'Measurement',
    [
        ('qber', float),
        ('qx', float),
        ('rate', float),
        ('objective', float),
        ('kps', float)
    ]
)


class PID:
    def __init__(
            self,
            kp,
            ki,
            kd,
            output_limit=25.0,
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
        return max(-self.output_limit, min(self.output_limit, output))

class PolarisationCompensator:
    def __init__(
            self,
            motors: list[base_motor.Motor],
            tt: timetagger.TimeTagger,
            target_qber: float = 0.1,
            target_qx: float = 0.1,
            samples: int = 3,
            probe_samples: int = 3,
            acceleration: float = 20.0,
            min_velocity: float = 1.0,
            max_velocity: float = 25.0,
            max_iterations: int = 100,
            min_rel_improvement: float = 0.001,
            start_at_0: bool = False,
            scramble_motors: bool = False,
            # pid tuning defaults (can be changed when instantiating)
            pid_kp: float = 6.0,
            pid_ki: float = 0.5,
            pid_kd: float = 0.02,
            control_dt: float = 0.12,   # jog pulse duration (s)
            deadband: float = 0.4      # °/s threshold to stop
    ) -> None:
        self.motors = motors
        self.tt = tt
        self.samples = samples
        self.probe_samples = probe_samples
        self.acceleration = acceleration
        self.min_velocity = min_velocity
        self.max_velocity = max_velocity
        self.max_iterations = max_iterations
        self.target_qber = target_qber
        self.target_qx = target_qx
        self.min_rel_improvement = min_rel_improvement

        # PID parameters & control timing
        self.pid_kp = pid_kp
        self.pid_ki = pid_ki
        self.pid_kd = pid_kd
        self.control_dt = control_dt
        self.deadband = deadband

        # per-motor state (direction, moving flag, pid object, last objective seen)
        self._motor_states = {}
        for motor in self.motors:
            serial = motor.device_info.serial_number
            self._motor_states[serial] = {
                'direction': random.choice([
                    base_motor.MotorDirection.BACKWARD,
                    base_motor.MotorDirection.FORWARD
                ]),
                'moving': False,
                'pid': PID(kp=self.pid_kp, ki=self.pid_ki, kd=self.pid_kd, output_limit=self.max_velocity),
                'last_objective': None,
                'stagnant_counter': 0,
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

    def _apply_pid_step(self, motor: base_motor.Motor, chosen_direction: base_motor.MotorDirection) -> None:
        """Compute PID and apply a short jog pulse in chosen_direction (or stop)."""
        state = self._motor_states[motor.device_info.serial_number]
        pid = state['pid']

        # get a measurement to feed PID
        meas = self.measure(self.samples)
        current_objective = meas.objective
        # store for stagnation detection
        last_obj = state.get('last_objective')
        state['last_objective'] = current_objective

        # Control error: we want to MAXIMISE objective, so minimize -objective
        error = -current_objective

        now = time.monotonic()
        pid_out = pid.compute(error, now)  # signed magnitude, but we will use absolute and preferred dir only

        # Use chosen_direction exclusively (PID sign ignored)
        mag = abs(pid_out)

        # deadband
        if mag < self.deadband:
            motor.stop()
            state['moving'] = False
            # reset small integral accumulation to avoid windup if desired
            # pid.reset()   # optional: reset integral when idle
            return

        # clamp to allowed motor velocity bounds
        speed = max(self.min_velocity, min(self.max_velocity, mag))

        # send jog for a short pulse then stop to re-measure next loop
        print(f'Jogging motor {motor.device_info.serial_number} {chosen_direction.name} at {speed}')
        motor.jog(direction=chosen_direction, acceleration=self.acceleration, max_velocity=speed)
        state['moving'] = True
        time.sleep(self.control_dt)
        motor.stop()
        state['moving'] = False

        # simple stagnation detection: if objective not improved, increment counter
        if last_obj is not None:
            if current_objective <= last_obj + 1e-12:
                state['stagnant_counter'] += 1
            else:
                state['stagnant_counter'] = 0

        # If it has been stagnant for several pid steps, consider re-probing next time
        if state['stagnant_counter'] > 6:
            # reset pid to allow fresh start on next probe
            pid.reset()
            state['stagnant_counter'] = 0
            # mark the motor's stored direction as unknown, so next iterate will probe again
            state['direction'] = random.choice([base_motor.MotorDirection.BACKWARD, base_motor.MotorDirection.FORWARD])

    # --- leave get_best_direction / _direction_probe as you have them ---
    # (no changes required; they integrate with the new PID behavior)

    def measure(self, samples: int) -> Measurement:
        qber_samples, qx_samples, rate_samples = [], [], []

        for _ in range(samples):
            data = timetagger.Data.from_raw_data(
                raw_data=self.tt.measure(),
                channel_groups=self.tt.channel_groups
            )
            qber_samples.append(data.qber)
            qx_samples.append(data.qx)
            rate_samples.append(data.rate)

        m_qber = float(np.mean(qber_samples))
        m_qx = float(np.mean(qx_samples))
        m_rate = float(np.mean(rate_samples))
        m_objective = objective(rate=m_rate, qber=m_qber, qx=m_qx)
        m_kps = keys_per_second(coincidences=m_rate, qber=m_qber, qx=m_qx)

        return Measurement(m_qber, m_qx, m_rate, m_objective, m_kps)


    def compensate(self) -> None:
        if self.max_iterations == 0:
            iterator = itertools.count()
        else:
            iterator = range(self.max_iterations)

        for iteration in iterator:
            if self.max_iterations != 0:
                print(f'Iteration: {iteration+1}/{self.max_iterations}')

            for motor in self.motors:
                baseline = self.measure(samples=self.samples)
                if (
                    baseline.qber < self.target_qber
                    and baseline.qx < self.target_qx
                    and baseline.kps > 0
                ):
                    if self.max_iterations != 0:
                        print(f'Target achieved in {iteration+1} iterations, time: {time.time() - self.start_time:.2f}s')
                        return
                    else:
                        print(f'Target achieved')

                else:
                    print(f'  Motor {motor.device_info.serial_number}: Probing')
                    direction = self.get_best_direction(motor)
                    print(f'    Choosing direction {direction.name}')

                    if direction == base_motor.MotorDirection.IDLE:
                        # nothing sensible to do right now for this motor
                        print('    No direction gives improvement, skipping motor.')
                        # optionally reset its PID so it probes next time
                        self._motor_states[motor.device_info.serial_number]['pid'].reset()
                        continue

                    # save chosen direction
                    self._motor_states[motor.device_info.serial_number]['direction'] = direction

                    # Run one PID-controlled pulse now (short jog then stop and measure on next iteration)
                    self._apply_pid_step(motor, direction)

            # small sleep so loop doesn't spin too fast; measurements are expensive anyway
            time.sleep(0.01)

    def _direction_probe(
            self,
            motor: base_motor.Motor,
            probe_direction: base_motor.MotorDirection
    ) -> float:
        baseline = self.measure(self.probe_samples)
        motor.jog(
            direction=probe_direction,
            acceleration=self.acceleration, max_velocity=10.0
        )
        self._motor_states[motor.device_info.serial_number]['moving'] = True
        time.sleep(0.1)
        motor.stop()
        self._motor_states[motor.device_info.serial_number]['moving'] = False
        probe = self.measure(self.probe_samples)
        rel_improve = (probe.objective - baseline.objective) / (abs(baseline.objective) + 1e-12)
        print(f'    Direction {probe_direction.name} gave {100*rel_improve:.2f}% improvement')
        return rel_improve

    def get_best_direction(
            self,
            motor: base_motor.Motor
    ) -> base_motor.MotorDirection:
        initial_direction = self._motor_states[motor.device_info.serial_number]['direction']
        directions = [
            initial_direction,
            base_motor.MotorDirection.FORWARD
            if initial_direction == base_motor.MotorDirection.BACKWARD
            else base_motor.MotorDirection.BACKWARD
        ]
        improvements = {
            d: self._direction_probe(motor, d)
            for d in directions
        }
        best_direction = max(improvements, key=improvements.get)
        return best_direction if improvements[best_direction] > self.min_rel_improvement else base_motor.MotorDirection.IDLE



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
            samples=5,
            probe_samples=5,
            min_velocity=5.0,
            max_velocity=25.0,
            max_iterations=0,
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
