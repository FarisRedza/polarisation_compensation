import sys
import os
import enum

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

import polarisation_box
import gui.motor_box as motor_box

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.polarimeter as polarimeter
import motor.motor as motor

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title(title='Polarisation Compensation')
        self.set_default_size(width=1200, height=800)
        self.set_size_request(width=500, height=150)
        self.connect("close-request", self.on_close_request)

        self.motor_1_direction = '+'
        self.motor_2_direction = '+'

        # main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content=main_box)

        ## header_bar
        header_bar = Adw.HeaderBar()
        main_box.append(child=header_bar)

        ## content_box
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(child=self.content_box)

        ### polarimeter box
        self.polarimeter_box = polarisation_box.PolarimeterBox()
        self.content_box.append(child=self.polarimeter_box)

        ### motor control box
        self.motors = motor.list_thorlabs_motors()
        self.motor_controllers: list[motor_box.MotorControlPage] = []
        for i, m in enumerate(self.motors):
            self.motor_controllers.append(
                motor_box.MotorControlPage(
                    motor=motor.Motor(
                        serial_number=m.get_device_info().serial_no
                    )
                )
            )
            self.content_box.append(
                child=self.motor_controllers[i]
            )

        GLib.timeout_add(100, self.pol_comp)

    def on_close_request(self, window) -> bool:
        self.polarimeter_box.pax.disconnect()
        for i in self.motor_controllers:
            i.motor_controls_group.motor._motor.stop()
        return False
    
    def pol_comp(self) -> bool:
        class MotorWP(enum.Enum):
            QWP = 0  # azimuth
            HWP = 1  # ellipticity

        target_azimuth = 0
        target_ellipticity = 0

        def adjust_motor(motor_index: int, current_value: float, target_value: float, direction_attr: str, threshold_small: float, threshold_large: float):
            mcg = self.motor_controllers[motor_index].motor_controls_group
            if mcg.motor_control_enabled == False:
                mcg.motor.position = mcg.motor._motor.get_position()
                if current_value > target_value + threshold_small:
                    if getattr(self, direction_attr) == '-':
                        mcg.motor._motor.stop()
                        setattr(self, direction_attr, '+')
                    if current_value > target_value + threshold_large:
                        mcg.motor._motor.jog(
                            direction='+',
                            kind='continuous'
                        )
                    else:
                        mcg.motor._motor.jog(
                            direction='+',
                            kind='builtin'
                        )
                elif current_value < target_value - threshold_small:
                    if getattr(self, direction_attr) == '+':
                        mcg.motor._motor.stop()
                        setattr(self, direction_attr, '-')
                    if current_value < target_value - threshold_large:
                        mcg.motor._motor.jog(
                            direction='-',
                            kind='continuous'
                        )
                    else:
                        mcg.motor._motor.jog(
                            direction='-',
                            kind='builtin'
                        )
                else:
                    mcg.motor._motor.stop()

        adjust_motor(
            motor_index=MotorWP.QWP.value,
            current_value=self.polarimeter_box.data.azimuth,
            target_value=target_azimuth,
            direction_attr='motor_1_direction',
            threshold_small=0.2,
            threshold_large=10
        )

        adjust_motor(
            motor_index=MotorWP.HWP.value,
            current_value=self.polarimeter_box.data.ellipticity,
            target_value=target_ellipticity,
            direction_attr='motor_2_direction',
            threshold_small=0.2,
            threshold_large=5
        )

        return True

class App(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        self.win = MainWindow(application=app)
        self.win.present()

if __name__ == '__main__':
    app = App(application_id='com.github.FarisRedza.PolarisationCompensation')
    try:
        app.run(sys.argv)
    except Exception as e:
        app.win.polarimeter_box.pax.disconnect()
        print('App crashed with an exception:', e)