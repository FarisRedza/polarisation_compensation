import sys
import os

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

        GLib.timeout_add(1000, self.pol_comp)

    def on_close_request(self, window) -> bool:
        self.polarimeter_box.pax.disconnect()
        return False
    
    def pol_comp(self) -> bool:
        print(self.polarimeter_box.data)
        angle = 5
        for i in self.motor_controllers:
            if i.motor_controls_group.motor_control_enabled == False:
                if self.polarimeter_box.data.azimuth > 0:
                    i.motor_controls_group.motor.threaded_move_by(angle=-angle)
                else:
                    i.motor_controls_group.motor.threaded_move_by(angle=angle)
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