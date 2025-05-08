import matplotlib.pyplot as plt
import numpy as np

class DraggableFanCurve:
    def __init__(self, ax, rpm_points, duty_points):
        self.ax = ax
        self.rpm = np.array(rpm_points)
        self.duty = np.array(duty_points)
        self.selected_index = None

        self.line, = ax.plot(self.rpm, self.duty, 'b-', label="Fan Curve")
        self.points = ax.plot(self.rpm, self.duty, 'ro', picker=5)[0]

        self.cid_press = self.points.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cid_release = self.points.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cid_motion = self.points.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

        ax.set_xlabel("RPM")
        ax.set_ylabel("PWM Duty Cycle (%)")
        ax.set_title("Interactive Fan Curve")

    def on_press(self, event):
        if event.inaxes != self.ax:
            return
        # Find closest point
        distances = np.hypot(self.rpm - event.xdata, self.duty - event.ydata)
        if np.min(distances) < 500:  # Adjust sensitivity as needed
            self.selected_index = np.argmin(distances)

    def on_release(self, event):
        self.selected_index = None

    def on_motion(self, event):
        if self.selected_index is None or event.inaxes != self.ax:
            return
        # Clamp RPM and duty cycle values if needed
        self.rpm[self.selected_index] = event.xdata
        self.duty[self.selected_index] = np.clip(event.ydata, 0, 100)
        # Sort by RPM to keep the curve valid
        sorted_indices = np.argsort(self.rpm)
        self.rpm = self.rpm[sorted_indices]
        self.duty = self.duty[sorted_indices]
        self.line.set_data(self.rpm, self.duty)
        self.points.set_data(self.rpm, self.duty)
        self.points.figure.canvas.draw()

# Example usage
fig, ax = plt.subplots()
rpm_points = [1000, 2000, 3000, 4000, 5000]
duty_points = [20, 30, 50, 70, 90]

draggable_curve = DraggableFanCurve(ax, rpm_points, duty_points)
plt.show()
