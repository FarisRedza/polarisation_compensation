import sys
import os
import enum

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

import polarisation_box
import gui.motor_box as motor_box
import pol_compensation

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.polarimeter as scpi_polarimeter
import motor.motor as thorlabs_motor

class PolCompPage(Adw.PreferencesPage):
    class MotorWP(enum.Enum):
        QWP = 55353314  # azimuth
        HWP = 55356974  # ellipticity

    def __init__(
            self,
            polarimeter_box: polarisation_box.PolarimeterBox,
            motor_controllers: list[motor_box.MotorControlPage]
    ) -> None:
        super().__init__()
        self.polarimeter_box = polarimeter_box
        self.motor_controllers = [m.motor_controls_group for m in motor_controllers]

        for mc in self.motor_controllers:
            mc.enable_controls_switch.connect(
                'notify::active',
                self.on_update_available_motors
            )

        self.enable_compensation = False
        self.available_motors = [
            m.motor for m in self.motor_controllers if m.manual_motor_control == False
        ]

        self.target_azimuth = 0
        self.target_ellipticity = 0

        # descending order
        self.azimuth_thresholds_velocities = [
            (5, 25),
            (2.5, 15),
            (1, 5),
            (0.05, 1)
        ]

        self.ellipticity_thresholds_velocities = [
            (5, 25),
            (2.5, 15),
            (1, 5),
            (0.075, 1)
        ]

        pol_comp_group = Adw.PreferencesGroup(title='Polarisation Compensation')
        self.add(group=pol_comp_group)

        # enable compensation
        enable_compensation_row = Adw.ActionRow(title='Enable compensation')
        pol_comp_group.add(child=enable_compensation_row)

        enable_compensation_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        enable_compensation_switch.connect(
            'notify::active',
            self.on_enable_compensation
        )
        enable_compensation_row.add_suffix(widget=enable_compensation_switch)
        enable_compensation_row.set_activatable_widget(
            widget=enable_compensation_switch
        )

        # azimuth
        target_azimuth_row = Adw.ActionRow(title='Target azimuth')
        pol_comp_group.add(child=target_azimuth_row)

        self.target_azimuth_entry = Gtk.Entry(
            text=self.target_azimuth,
            valign=Gtk.Align.CENTER,
        )
        target_azimuth_row.add_suffix(widget=self.target_azimuth_entry)
        self.target_azimuth_entry.connect(
            'activate',
            self.on_set_target_azimuth
        )

        # ellipticity
        target_ellipticity_row = Adw.ActionRow(title='Target ellipticity')
        pol_comp_group.add(child=target_ellipticity_row)

        self.target_ellipticity_entry = Gtk.Entry(
            text=self.target_ellipticity,
            valign=Gtk.Align.CENTER,
        )
        target_ellipticity_row.add_suffix(widget=self.target_ellipticity_entry)
        self.target_ellipticity_entry.connect(
            'activate',
            self.on_set_target_ellipticity
        )

        GLib.timeout_add(
            interval=100,
            function=self.pol_comp
        )

    def on_enable_compensation(self, switch: Gtk.Switch, gparam):
        self.enable_compensation = not self.enable_compensation

    def on_set_target_azimuth(self, entry: Gtk.Entry):
        try:
            value = float(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.target_azimuth = value

    def on_set_target_ellipticity(self, entry: Gtk.Entry):
        try:
            value = float(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.target_ellipticity = value

    def on_update_available_motors(self, switch: Gtk.Entry, gparam):
        self.available_motors = [
            m.motor for m in self.motor_controllers if m.manual_motor_control == False
        ]

    def pol_comp(
            self
    ) -> bool:
        if not self.enable_compensation:
            return True
        pol_compensation.pol_comp(
            motor_list=self.available_motors,
            motor_qwp_serial_no=self.MotorWP.QWP.value,
            motor_hwp_serial_no=self.MotorWP.HWP.value,
            target_azimuth=self.target_azimuth,
            target_ellipticity=self.target_ellipticity,
            azimuth_thresholds_velocities=self.azimuth_thresholds_velocities,
            ellipticity_thresholds_velocities=self.ellipticity_thresholds_velocities,
            current_azimuth=self.polarimeter_box.data.azimuth,
            current_ellipticity=self.polarimeter_box.data.ellipticity
        )

        return True

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

        ### polarimeter box
        self.polarimeter_box = polarisation_box.PolarimeterBox()
        self.content_box.append(child=self.polarimeter_box)

        ### init motor control boxes
        self.motors = thorlabs_motor.list_thorlabs_motors()
        self.motor_controllers: list[motor_box.MotorControlPage] = []
        for i, m in enumerate(self.motors):
            self.motor_controllers.append(
                motor_box.MotorControlPage(
                    motor=thorlabs_motor.Motor(
                        serial_number=m.get_device_info().serial_no
                    )
                )
            )

        ### pol comp
        self.pol_comp_page = PolCompPage(
            polarimeter_box=self.polarimeter_box,
            motor_controllers=self.motor_controllers
        )
        self.content_box.append(child=self.pol_comp_page)

        ### add motor boxes
        for i, m in enumerate(self.motor_controllers):
            self.content_box.append(
                child=self.motor_controllers[i]
            )

    def on_close_request(self, window) -> bool:
        self.polarimeter_box.polarimeter.disconnect()
        for i in self.motor_controllers:
            i.motor_controls_group.motor._motor.stop()
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
        app.win.polarimeter_box.polarimeter.disconnect()
        print('App crashed with an exception:', e)