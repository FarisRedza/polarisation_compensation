import time
import math
import random
from collections import deque

import bb84.timetagger as timetagger
import bb84.remote_timetagger as remote_timetagger
import motor.thorlabs_motor as thorlabs_motor
import motor.base_motor as base_motor

MOTOR_SERVER_HOST = '137.195.89.222'
MOTOR_SERVER_PORT = 5002
MEASUREMENT_SERVER_HOST = '137.195.89.222'
MEASUREMENT_SERVER_HOST = '137.195.63.6'
MEASUREMENT_SERVER_PORT = 5001

QWP = '55353314'
HWP = '55356974'

def averaged_measure(n_samples=12, sample_interval=0.008):
    qbers = []
    qxs = []
    for _ in range(n_samples):
        data = timetagger.Data().from_raw_data(raw_data=measurement_device.measure())
        qbers.append(data.qber)
        qxs.append(data.qx)
        time.sleep(sample_interval)
    return sum(qbers)/len(qbers), sum(qxs)/len(qxs)

def loss_from_measurements(qber, qx, target=0.05):
    # squared relative error (you can tune)
    return 1.5*(qber/target)**2 + (qx/target)**2

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def spsa_update(
        motors: list[base_motor.Motor],
        thetas,
        a_k,
        c_k,
        momentum_v,
        beta,
        max_step_deg,
        meas_samples,
        sample_interval
):
    # 1. generate perturbation ±1 for each parameter
    d = [random.choice([1.0, -1.0]) for _ in thetas]
    # 2. apply +c perturbation
    theta_plus = [t + c_k * di for t, di in zip(thetas, d)]
    theta_minus = [t - c_k * di for t, di in zip(thetas, d)]

    # move motors to theta_plus relative from current: compute deltas
    for motor, t_target, t_curr in zip(motors, theta_plus, thetas):
        delta = t_target - t_curr
        # wrap/clamp if you want to enforce physical ranges here
        motor.move_by(angle=delta, acceleration=20.0, max_velocity=25.0)
    time.sleep(0.1)  # let hardware settle (tune)
    qber_p, qx_p = averaged_measure(n_samples=meas_samples, sample_interval=sample_interval)
    L_plus = loss_from_measurements(qber_p, qx_p)

    # move to theta_minus (we are currently at theta_plus so move by -2*c*d)
    for motor, di in zip(motors, d):
        motor.move_by(angle=-2.0 * c_k * di, acceleration=20.0, max_velocity=25.0)
    time.sleep(0.1)
    qber_m, qx_m = averaged_measure(n_samples=meas_samples, sample_interval=sample_interval)
    L_minus = loss_from_measurements(qber_m, qx_m)

    # move back to nominal theta (we are at theta_minus; move +c*d to return to theta)
    for motor, di in zip(motors, d):
        motor.move_by(angle=c_k * di, acceleration=20.0, max_velocity=25.0)
    time.sleep(0.02)

    # gradient estimate (SPSA)
    # g_i ≈ (L_plus - L_minus) / (2*c_k) * (1 / d_i) but d_i = ±1 so division is trivial
    grad = [ (L_plus - L_minus) / (2.0 * c_k) * (1.0/di) for di in d ]

    # update with momentum
    # v = beta * v + a_k * grad
    momentum_v = [ beta * v + a_k * g for v, g in zip(momentum_v, grad) ]

    # compute proposed theta change (negative gradient descent direction)
    delta_theta = [ -v for v in momentum_v ]
    # clamp per-iteration max step
    delta_theta = [ clamp(dt, -max_step_deg, max_step_deg) for dt in delta_theta ]

    # apply update
    for motor, dt in zip(motors, delta_theta):
        motor.move_by(angle=dt, acceleration=20.0, max_velocity=25.0)
    time.sleep(0.01)  # let settle

    # compute new averaged loss for monitoring (optional)
    qber_new, qx_new = averaged_measure(n_samples=meas_samples, sample_interval=sample_interval)
    L_new = loss_from_measurements(qber_new, qx_new)

    # compute new theta values (or read from motors if your API gives them)
    new_thetas = [ t + dt for t, dt in zip(thetas, delta_theta) ]

    return new_thetas, momentum_v, L_new, (qber_new, qx_new)

# ---------- High-level control loop ----------
def run_compensation_loop(
        motor_hwp: base_motor.Motor,
        motor_qwp: base_motor.Motor, 
        max_iters=1000,
        meas_samples=20, 
        sample_interval=0.01
):
    motors = [motor_hwp, motor_qwp]
    thetas = [motor_hwp.position, motor_qwp.position]  # deg
    v = [0.0, 0.0]  # momentum
    beta = 0.8
    # a0 = 2.0      # initial step gain (deg-scale)
    a0 = 2.5
    # c0 = 0.5      # perturbation size in degrees
    c0 = 0.7
    max_step = 4.0
    target = 0.05
    stable_count = 0
    best_loss = float('inf')

    for k in range(1, max_iters+1):
        # cooling schedules (tunable)
        a_k = a0 / (1.0 + 0.0005 * k)   # slowly decaying step size
        c_k = c0 / (1.0 + 0.0002 * k)   # slowly decaying perturbation

        thetas, v, L, (qber, qx) = spsa_update(
            motors, thetas, a_k, c_k, v, beta, max_step, meas_samples, sample_interval
        )

        print(f"iter {k:03d}: loss={L:.4f} qber={qber:.4f} qx={qx:.4f} thetas={[round(t,2) for t in thetas]}")
        # stability check: both below target for N consecutive iters
        if qber < target and qx < target:
            stable_count += 1
        else:
            stable_count = 0

        if L < best_loss:
            best_loss = L

        # adaptivity: if loss increased too much, reduce a0 and c0
        if L > 2.0 * best_loss:
            a0 *= 0.7
            c0 *= 0.7
            print(f"Large loss increase -> reducing learning rates - {a0=}, {c0=}")

        # stop if stable for some iterations
        if stable_count >= 5:
            print("Stable for 5 iterations. Holding and switching to periodic probe mode.")
            break

    return thetas, (qber, qx)

if __name__ == '__main__':
    motor_qwp = thorlabs_motor.ThorlabsMotor(serial_number=QWP)
    motor_hwp = thorlabs_motor.ThorlabsMotor(serial_number=HWP)
    measurement_device = remote_timetagger.RemoteTimetagger(
        host=MEASUREMENT_SERVER_HOST,
        port=MEASUREMENT_SERVER_PORT,
        model='Logic-16'
    )

    run_compensation_loop(
        motor_hwp,
        motor_qwp, 
        max_iters=1000,
        meas_samples=20,
        sample_interval=0.01
    )