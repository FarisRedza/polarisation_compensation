import sys
import os
import enum
import typing

import numpy
import matplotlib.pyplot
import matplotlib.backends.backend_gtk4agg
import matplotlib.backend_bases

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, GObject

import bb84.qutag_box as qutag_box
import remote_motor.remote_motor_box as motor_box
import remote_pol_compensation

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.qutag as qutag
import remote_motor.motor_client as thorlabs_motor

class PolCompPage(Adw.PreferencesPage):
    def __init__(
            self,
            qutag_box: qutag_box.QuTAGBox,
            motor_controllers: list[motor_box.MotorControlPage]
    ) -> None:
        super().__init__()
        self.enable_compensation = False

        self.target_azimuth = 0
        self.target_ellipticity = 0

        self.qwp_motor = ''
        self.hwp_motor = ''
        self.qutag = ''

        self.azimuth_velocity = [
            (2.5, 25.0),
            (1.5, 20.0),
            (1, 15.0),
            (0.5, 5.0),
            (0.1, 1.0),
            (0.05, 0.5)
        ]

        self.ellipticity_velocity = [
            (5.0, 25.0),
            (3.5, 20.0),
            (2.5, 15.0),
            (1.0, 5.0),
            (0.1, 1.0),
            (0.075, 0.5)
        ]

    def set_enable_compensation(self, value: bool) -> None:
        self.enable_compensation = value

    def get_enable_compensation(self) -> bool:
        return self.enable_compensation
    
    def set_target_azimuth(self, value: float) -> None:
        self.target_azimuth = value

    def get_target_azimuth(self) -> float:
        return self.target_azimuth
    
    def set_target_ellipticity(self, value: float) -> None:
        self.target_ellipticity = value

    def get_target_ellipticity(self) -> float:
        return self.target_ellipticity
    
    def set_qwp_motor(self, value: str) -> None:
        self.qwp_motor = value

    def get_qwp_motor(self) -> str:
        return self.qwp_motor
    
    def set_hwp_motor(self, value: str) -> None:
        self.hwp_motor = value

    # def get_hwp_motor(self) -> str:
    #     return self.hwp_motor
    
    def set_polarimeter(self, value: str) -> None:
        self.qutag = value

    # def get_polarimeter(self) -> str:
    #     return self.polarimeter
    
    def set_azimuth_velocity(self, value: list[tuple]) -> None:
        self.azimuth_velocity = value

    def get_azimuth_velocity(self) -> list[tuple]:
        return self.azimuth_velocity
    
    def set_ellipticity_velocity(self, value: list[tuple]) -> None:
        self.ellipticity_velocity = value

    def get_ellipticity_velocity(self) -> list[tuple]:
        return self.ellipticity_velocity

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title(title='Polarisation Compensation')
        self.set_default_size(width=1300, height=800)
        self.set_size_request(width=1250, height=300)

        # main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content=main_box)

        ## header_bar
        header_bar = Adw.HeaderBar()
        main_box.append(child=header_bar)

        ## content_box
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(child=self.content_box)

        ### qutag box
        self.qutag_box = qutag_box.QuTAGBox()
        self.content_box.append(child=self.qutag_box)

        ### init motor control boxes
        self.motors = thorlabs_motor.list_thorlabs_motors(host=thorlabs_motor.server_ip, port=thorlabs_motor.server_port)
        self.motor_controllers: list[motor_box.MotorControlPage] = []
        for i, m in enumerate(self.motors):
            self.motor_controllers.append(
                motor_box.MotorControlPage(
                    motor=thorlabs_motor.Motor(
                        serial_number=m.serial_number,
                        ip_addr=thorlabs_motor.server_ip,
                        port=thorlabs_motor.server_port
                    )
                )
            )

        ### pol comp
        self.pol_comp_page = PolCompPage(
            qutag_box=self.qutag_box,
            motor_controllers=self.motor_controllers
        )
        self.content_box.append(child=self.pol_comp_page)

        ### add motor boxes
        for i, m in enumerate(self.motor_controllers):
            self.content_box.append(
                child=self.motor_controllers[i]
            )
    
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
        print('App crashed with an exception:', e)