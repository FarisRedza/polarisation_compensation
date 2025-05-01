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

class PolCompPage(Adw.PreferencesPage):
    class MotorWP(enum.Enum):
        QWP = 55353314  # azimuth
        HWP = 55356974  # ellipticity

    def __init__(self, polarimeter_box: polarisation_box.PolarimeterBox, motor_controllers: list[motor_box.MotorControls]):
        super().__init__()
        self.polarimeter_box = polarimeter_box
        self.motor_controllers = motor_controllers
        self.enable_compensation = False
        self.motor_1_direction = '+'
        self.motor_2_direction = '+'

        self.motor_1_jog_max_velocity = 0
        self.motor_2_jog_max_velocity = 0

        self.target_azimuth = 0
        self.target_ellipticity = 0

        # descending order
        self.azimuth_thresholds_velocities = [
            (10, 25),
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
        self.add(pol_comp_group)

        # enable compensation
        enable_compensation_row = Adw.ActionRow(title='Enable compensation')
        pol_comp_group.add(child=enable_compensation_row)

        enable_compensation_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        enable_compensation_switch.connect('notify::active', self.on_enable_compensation)
        enable_compensation_row.add_suffix(widget=enable_compensation_switch)
        enable_compensation_row.set_activatable_widget(widget=enable_compensation_switch)

        # azimuth
        target_azimuth_row = Adw.ActionRow(title='Target azimuth')
        pol_comp_group.add(child=target_azimuth_row)

        self.target_azimuth_entry = Gtk.Entry(
            text=self.target_azimuth,
            valign=Gtk.Align.CENTER,
        )
        target_azimuth_row.add_suffix(widget=self.target_azimuth_entry)
        self.target_azimuth_entry.connect('activate', self.on_set_target_azimuth)

        # ellipticity
        target_ellipticity_row = Adw.ActionRow(title='Target ellipticity')
        pol_comp_group.add(child=target_ellipticity_row)

        self.target_ellipticity_entry = Gtk.Entry(
            text=self.target_ellipticity,
            valign=Gtk.Align.CENTER,
        )
        target_ellipticity_row.add_suffix(widget=self.target_ellipticity_entry)
        self.target_ellipticity_entry.connect('activate', self.on_set_target_ellipticity)

        # qwp
        motor_qwp_row = Adw.ActionRow(
            title='QWP motor',
            subtitle='Azimuth'
        )
        pol_comp_group.add(motor_qwp_row)

        motor_qwp_label = Gtk.Label(label=self.MotorWP.QWP.value)
        motor_qwp_row.add_suffix(widget=motor_qwp_label)

        # hwp
        motor_hwp_row = Adw.ActionRow(
            title='HWP motor',
            subtitle='Ellipticity'
        )
        pol_comp_group.add(motor_hwp_row)

        motor_hwp_label = Gtk.Label(label=self.MotorWP.HWP.value)
        motor_hwp_row.add_suffix(widget=motor_hwp_label)

        GLib.timeout_add(
            interval=100,
            function=self.pol_comp
        )

    def on_enable_compensation(self, switch, gparam):
        self.enable_compensation = not self.enable_compensation

    def on_set_target_azimuth(self, entry):
        try:
            value = float(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.target_azimuth = value

    def on_set_target_ellipticity(self, entry):
        try:
            value = float(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.target_ellipticity = value

    def pol_comp(self) -> bool:
        if not self.enable_compensation:
            return True

        motor_list: list[motor.Motor] = [m.motor_controls_group.motor for m in self.motor_controllers]
        motor_qwp_index = next((i for i, m in enumerate(motor_list) if m.serial_no == self.MotorWP.QWP.value), -1)
        motor_hwp_index = next((i for i, m in enumerate(motor_list) if m.serial_no == self.MotorWP.HWP.value), -1)

        def adjust_motor(
                motor_index: int,
                current_value: float,
                target_value: float,
                direction_attr: str,
                max_velocity_attr: str,
                thresholds_velocities: list[tuple[float, int]]
        ) -> None:
            mcg: motor_box.MotorControls = self.motor_controllers[motor_index].motor_controls_group
            if mcg.manual_motor_control:
                return

            mcg.motor.position = mcg.motor._motor.get_position()
            delta = current_value - target_value
            direction = '+' if delta > 0 else '-'

            if getattr(self, direction_attr) != direction:
                mcg.motor._motor.stop()
                setattr(self, direction_attr, direction)

            abs_delta = abs(delta)
            for threshold, velocity in sorted(thresholds_velocities, reverse=True):
                if abs_delta > threshold:
                    if getattr(self, max_velocity_attr) != velocity:
                        mcg.motor._motor.setup_jog(
                            mode='continuous',
                            max_velocity=velocity
                        )
                        setattr(self, max_velocity_attr, velocity)
                    mcg.motor._motor.jog(
                        direction=direction,
                        kind='builtin'
                    )
                    break
            else:
                mcg.motor._motor.stop()

        adjust_motor(
            motor_index=motor_qwp_index,
            current_value=self.polarimeter_box.data.azimuth,
            target_value=self.target_azimuth,
            direction_attr='motor_1_direction',
            max_velocity_attr='motor_1_jog_max_velocity',
            thresholds_velocities=self.azimuth_thresholds_velocities
        )

        adjust_motor(
            motor_index=motor_hwp_index,
            current_value=self.polarimeter_box.data.ellipticity,
            target_value=self.target_ellipticity,
            direction_attr='motor_2_direction',
            max_velocity_attr='motor_2_jog_max_velocity',
            thresholds_velocities=self.ellipticity_thresholds_velocities
        )

        return True


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title(title='Polarisation Compensation')
        self.set_default_size(width=1300, height=800)
        self.set_size_request(width=1250, height=300)
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

        ### init motor control boxes
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
        self.polarimeter_box.pax.disconnect()
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
        app.win.polarimeter_box.pax.disconnect()
        print('App crashed with an exception:', e)