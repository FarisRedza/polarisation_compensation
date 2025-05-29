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

import remote_pol_compensation

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import bb84.qutag_box as qutag_box
import remote_motor.remote_motor_box as motor_box
import bb84.qutag as qutag
import remote_motor.motor_client as thorlabs_motor

import gui.polarisation_box as polarisation_box

class ControlGroup(Adw.PreferencesGroup):
    class MotorWP(enum.Enum):
        QWP = '55353314'
        HWP = '55356974'

    class MotorDirection(enum.Enum):
        FORWARD = '+'
        BACKWARD = '-'
        IDLE = None

    def __init__(
            self,
            qutag_box: qutag_box.QuTAGBox,
            motor_controllers: list[motor_box.MotorControlPage],
            get_enable_compensation: typing.Callable,
            set_enable_compensation: typing.Callable,
            get_target_azimuth: typing.Callable,
            set_target_azimuth: typing.Callable,
            get_target_ellipticity: typing.Callable,
            set_target_ellipticity: typing.Callable,
            set_azimuth_velocity: typing.Callable,
            get_azimuth_velocity: typing.Callable,
            set_ellipticity_velocity: typing.Callable,
            get_ellipticity_velocity: typing.Callable
    ) -> None:
        super().__init__(title='Polarisation Compensation')
        self.qutag_box = qutag_box
        self.motor_controllers = motor_controllers

        self.get_enable_compensation = get_enable_compensation
        self.set_enable_compensation = set_enable_compensation
        self.get_target_azimuth = get_target_azimuth
        self.set_target_azimuth = set_target_azimuth
        self.get_target_ellipticity = get_target_ellipticity
        self.set_target_ellipticity = set_target_ellipticity
        self.set_azimuth_velocity = set_azimuth_velocity
        self.get_azimuth_velocity = get_azimuth_velocity
        self.set_ellipticity_velocity = set_ellipticity_velocity
        self.get_ellipticity_velocity = get_ellipticity_velocity

        # enable compensation
        enable_compensation_row = Adw.ActionRow(title='Enable compensation')
        self.add(child=enable_compensation_row)

        enable_compensation_switch = Gtk.Switch(
            active=self.get_enable_compensation(),
            valign=Gtk.Align.CENTER
        )
        enable_compensation_switch.connect(
            'notify::active',
            lambda sw, _: self.set_enable_compensation(sw.get_active())
        )
        enable_compensation_row.add_suffix(
            widget=enable_compensation_switch
        )
        enable_compensation_row.set_activatable_widget(
            widget=enable_compensation_switch
        )

        # azimuth
        target_azimuth_row = Adw.ActionRow(title='Target azimuth')
        self.add(child=target_azimuth_row)
        self.target_azimuth_entry = Gtk.Entry(
            text=self.get_target_azimuth(),
            valign=Gtk.Align.CENTER
        )
        target_azimuth_row.add_suffix(widget=self.target_azimuth_entry)
        self.target_azimuth_entry.connect(
            'activate',
            self.set_target_azimuth
        )

        # ellipticity
        target_ellipticity_row = Adw.ActionRow(title='Target ellipticity')
        self.add(child=target_ellipticity_row)
        self.target_ellipticity_entry = Gtk.Entry(
            text=self.get_target_ellipticity(),
            valign=Gtk.Align.CENTER
        )
        target_ellipticity_row.add_suffix(widget=self.target_ellipticity_entry)
        self.target_ellipticity_entry.connect(
            'activate',
            self.set_target_ellipticity
        )

        GLib.timeout_add(
            interval=100,
            function=self.pol_comp
        )

    def pol_comp(self) -> bool:
        if not self.get_enable_compensation():
            return True
        remote_pol_compensation.pol_comp(
            motor_list=[m.motor for m in self.motor_controllers],
            motor_qwp_serial_no=self.MotorWP.QWP.value,
            motor_hwp_serial_no=self.MotorWP.HWP.value,
            target_azimuth=self.get_target_azimuth(),
            target_ellipticity=self.get_target_ellipticity(),
            azimuth_velocities=self.get_azimuth_velocity(),
            ellipticity_velocities=self.get_ellipticity_velocity(),
            current_azimuth=self.qutag_box.data.azimuth,
            current_ellipticity=self.qutag_box.data.ellipticity
        )
        return True

    def on_set_target_azimuth(self, entry: Gtk.Entry):
        try:
            value = float(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.set_target_azimuth(value=value)

    def on_set_target_ellipticity(self, entry: Gtk.Entry):
        try:
            value = float(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.set_target_ellipticity(value=value)

class PolCompPage(Adw.PreferencesPage):
    def __init__(
            self,
            qutag_box: qutag_box.QuTAGBox,
            motor_controllers: list[motor_box.MotorControlPage]
    ) -> None:
        super().__init__()
        self.enable_compensation = False

        self.target_azimuth = 45
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

        self.control_group = ControlGroup(
            qutag_box=qutag_box,
            motor_controllers=motor_controllers,
            get_enable_compensation=self.get_enable_compensation,
            set_enable_compensation=self.set_enable_compensation,
            get_target_azimuth=self.get_target_azimuth,
            set_target_azimuth=self.set_target_azimuth,
            get_target_ellipticity=self.get_target_ellipticity,
            set_target_ellipticity=self.set_target_ellipticity,
            set_azimuth_velocity=self.set_azimuth_velocity,
            get_azimuth_velocity=self.get_azimuth_velocity,
            set_ellipticity_velocity=self.set_ellipticity_velocity,
            get_ellipticity_velocity=self.get_ellipticity_velocity
        )
        self.add(group=self.control_group)

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
        self.connect(
            'close-request',
            self.on_close_request
        )

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
        # self.qutag_box = qutag_box.QuTAGBox()
        # self.content_box.append(child=self.qutag_box)

        ### polarimeter box
        self.qutag_box = polarisation_box.PolarimeterBox()
        self.content_box.append(child=self.qutag_box)

        ### init motor control boxes
        self.motors = thorlabs_motor.list_thorlabs_motors(
            host=thorlabs_motor.server_ip,
            port=thorlabs_motor.server_port
        )
        self.motor_controllers: list[motor_box.MotorControlPage] = []
        for i, m in enumerate(self.motors):
            self.motor_controllers.append(
                motor_box.MotorControlPage(
                    motor=thorlabs_motor.Motor(
                        serial_number=m.serial_number,
                        host=thorlabs_motor.server_ip,
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

    def on_close_request(self, window: Adw.ApplicationWindow) -> bool:
        # self.qutag_box.qutag._qutag.deInitialize()
        # for i in self.motor_controllers:
        #     i.motor_controls_group.motor._motor.stop()
        return False
    
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