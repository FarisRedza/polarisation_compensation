import threading
import time
import random
import numpy as np

import bb84.timetagger as timetagger
import bb84.remote_timetagger as remote_timetagger
import motor.thorlabs_motor as thorlabs_motor
import motor.base_motor as base_motor

MEASUREMENT_SERVER_HOST = '137.195.63.6'
MEASUREMENT_SERVER_PORT = 5001

QWP = '55353314'
HWP = '55356974'

class PolarisationCompensator:
    def __init__(
            self,
            hwp_motor: base_motor.Motor,
            qwp_motor: base_motor.Motor,
            timetagger: timetagger.TimeTagger
    ) -> None:
        self.hwp = hwp_motor
        self.qwp = qwp_motor
        self.tt = timetagger
        self.stop_event = threading.Event()
        
        # SPSA hyperparameters
        self.a = 0.1           # initial step size multiplier
        self.c = 0.5           # initial perturbation size multiplier
        self.A = 10            # stability constant
        self.alpha = 0.602     # decay rate for a_k
        self.gamma = 0.101     # decay rate for c_k
        
        # Physical angle bounds (degrees)
        self.theta_min = 0.0
        self.theta_max = 180.0
        
        # Start from known or guessed angles
        self.initial_angles = [0.0, 0.0]  # [HWP_angle, QWP_angle]
    
    def start(self):
        """Launch the real-time compensation loop in a background thread."""
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Signal the loop to terminate and wait for clean shutdown."""
        self.stop_event.set()
        self.thread.join()
    
    def _measure_cost(self):
        """Return (cost, qber, qx)."""
        data = timetagger.Data().from_raw_data(raw_data=self.tt.measure())
        qber, qx = data.qber, data.qx
        return qber*qber + qx*qx, qber, qx
    
    def _current_angles(self):
        """Assumes motor has .angle attribute tracking absolute position."""
        return [self.hwp.position, self.qwp.position]
    
    def _set_angles(self, target_angles):
        """
        Move each waveplate from its current angle to target_angles.
        Chooses the shortest rotation direction (±180° wrap).
        """
        current = self._current_angles()
        diffs = []
        for curr, targ in zip(current, target_angles):
            d = (targ - curr) % 180.0
            if d > 90.0:
                d -= 180.0
            diffs.append(d)
        
        # Blocking moves—small angles so this is fast
        self.hwp.move_by(angle=diffs[0], acceleration=self.hwp.acceleration, max_velocity=self.hwp.max_velocity)
        self.qwp.move_by(angle=diffs[1], acceleration=self.qwp.acceleration, max_velocity=self.qwp.max_velocity)
    
    def _run(self):
        """Main SPSA loop."""
        # Initialize
        print('hello')
        theta = np.array(self.initial_angles, dtype=float)
        self._set_angles(theta)
        time.sleep(0.1)  # let system settle
        
        k = 0
        while not self.stop_event.is_set():
            # Decaying step and perturbation sizes
            a_k = self.a / ((k + 1 + self.A) ** self.alpha)
            c_k = self.c / ((k + 1) ** self.gamma)
            
            # Random perturbation vector ∈ {+1, −1}²
            delta = np.array([random.choice([1, -1]) for _ in range(2)])
            
            # --- Evaluate f(θ + c_k δ) ---
            theta_plus = np.clip(theta + c_k * delta,
                                 self.theta_min, self.theta_max)
            self._set_angles(theta_plus)
            time.sleep(0.05)
            f_plus, _, _ = self._measure_cost()
            
            # --- Evaluate f(θ − c_k δ) ---
            theta_minus = np.clip(theta - c_k * delta,
                                  self.theta_min, self.theta_max)
            self._set_angles(theta_minus)
            time.sleep(0.05)
            f_minus, _, _ = self._measure_cost()
            
            # Estimate gradient
            grad_est = (f_plus - f_minus) / (2 * c_k) * delta
            
            # Update rule
            theta = theta - a_k * grad_est
            theta = np.clip(theta, self.theta_min, self.theta_max)
            
            # Move to new estimate
            self._set_angles(theta)
            time.sleep(0.05)
            
            # Early idle if below error threshold
            cost, qber, qx = self._measure_cost()
            if qber < 0.05 and qx < 0.05:
                time.sleep(0.1)
            
            k += 1

if __name__ == '__main__':
    motor_qwp = thorlabs_motor.ThorlabsMotor(serial_number=QWP)
    motor_hwp = thorlabs_motor.ThorlabsMotor(serial_number=HWP)
    measurement_device = remote_timetagger.RemoteTimetagger(
        host=MEASUREMENT_SERVER_HOST,
        port=MEASUREMENT_SERVER_PORT,
        model='Logic-16'
    )
    comp = PolarisationCompensator(
        hwp_motor=motor_hwp,
        qwp_motor=motor_qwp,
        timetagger=measurement_device
    )

    while True:
        try:
            comp.start()
        except KeyboardInterrupt:
            comp.stop()