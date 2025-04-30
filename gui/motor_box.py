import sys
import os
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import motor.motor as motor

class MotorControls(Adw.PreferencesGroup):
    def __init__(self, motor: motor.Motor):
        super().__init__()
        self.set_title(title='Motor Controls')
        self.motor = motor
        self.manual_motor_control = False
        self.motor_step_size = 5
        self.motor_acceleration = 20
        self.motor_max_velocity = 25

        # enable controls
        enable_controls_row = Adw.ActionRow(title='Enable motor controls')
        self.add(child=enable_controls_row)

        enable_controls_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        enable_controls_switch.connect('notify::active', self.on_enable_controls)
        enable_controls_row.add_suffix(widget=enable_controls_switch)
        enable_controls_row.set_activatable_widget(widget=enable_controls_switch)

        # position
        position_row = Adw.ActionRow(title='Position')
        self.add(child=position_row)

        self.position_label = Gtk.Label(label=f'{self.motor._motor.get_position():.3f}')
        position_row.add_suffix(widget=self.position_label)

        # step size
        step_size_row = Adw.ActionRow(title='Step size')
        self.add(child=step_size_row)

        self.step_size_entry = Gtk.Entry(
            text=self.motor_step_size,
            valign=Gtk.Align.CENTER,
            sensitive=False
        )
        step_size_row.add_suffix(widget=self.step_size_entry)
        self.step_size_entry.connect('activate', self.on_set_step_size)

        # acceleration
        acceleration_row = Adw.ActionRow(title='Acceleration')
        self.add(child=acceleration_row)

        self.acceleration_entry = Gtk.Entry(
            text=self.motor_acceleration,
            placeholder_text = 'Max value: 20',
            valign=Gtk.Align.CENTER,
            sensitive=False
        )
        acceleration_row.add_suffix(widget=self.acceleration_entry)
        self.acceleration_entry.connect('activate', self.on_set_acceleration)

        # max velocity
        max_velocity_row = Adw.ActionRow(title='Max velocity')
        self.add(child=max_velocity_row)

        self.max_velocity_entry = Gtk.Entry(
            text=self.motor_max_velocity,
            placeholder_text = 'Max value: 25',
            valign=Gtk.Align.CENTER,
            sensitive=False
        )
        max_velocity_row.add_suffix(widget=self.max_velocity_entry)
        self.max_velocity_entry.connect('activate', self.on_set_max_velocity)

        # rotation row
        rotation_row = Adw.ActionRow()
        self.add(child=rotation_row)

        ## control box
        control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        control_box.set_valign(Gtk.Align.CENTER)
        control_box.set_halign(Gtk.Align.CENTER)
        control_box.set_hexpand(True)
        rotation_row.set_child(child=control_box)

        ## control grid
        control_grid = Gtk.Grid(
            column_spacing=6,
            row_spacing=6
        )
        control_box.append(child=control_grid)

        # rotation controls
        rotation_control_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.add(child=rotation_control_row)

        ## ccw
        self.ccw_button = Gtk.Button(
            label='CCW',
            valign=Gtk.Align.CENTER,
            sensitive=False
        )
        control_grid.attach(self.ccw_button, 1, 1, 1, 1)
        self.ccw_button.connect('clicked', self.rotate_motor_ccw)

        ## rotate to 0
        self.rot_0_button = Gtk.Button(
            label='0',
            valign=Gtk.Align.CENTER,
            sensitive=False
        )
        control_grid.attach(self.rot_0_button, 2, 1, 1, 1)
        self.rot_0_button.connect('clicked', self.rotate_motor_0)

        ## cw
        self.cw_button = Gtk.Button(
            label='CW',
            valign=Gtk.Align.CENTER,
            sensitive=False
        )
        control_grid.attach(self.cw_button, 3, 1, 1, 1)
        self.cw_button.connect('clicked', self.rotate_motor_cw)

        GLib.timeout_add(100, self.update_motor_info)

    def on_enable_controls(self, switch, gparam):
        self.manual_motor_control = not self.manual_motor_control
        self.step_size_entry.set_sensitive(switch.get_active())
        self.acceleration_entry.set_sensitive(switch.get_active())
        self.max_velocity_entry.set_sensitive(switch.get_active())
        self.ccw_button.set_sensitive(switch.get_active())
        self.rot_0_button.set_sensitive(switch.get_active())
        self.cw_button.set_sensitive(switch.get_active())

    def update_motor_info(self) -> bool:
        self.position_label.set_text(f'{self.motor.position:.3f}')
        return True
    
    def on_set_step_size(self, entry):
        try:
            value = abs(float(entry.get_text()))
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.motor_step_size = value

    def on_set_acceleration(self, entry):
        try:
            value = abs(float(entry.get_text()))
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            if value > 20:
                self.motor_acceleration = 20
            else:
                self.motor_acceleration = value

    def on_set_max_velocity(self, entry):
        try:
            value = abs(float(entry.get_text()))
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            if value > 25:
                self.motor_max_velocity = 25
            else:
                self.motor_max_velocity = value

    def rotate_motor_ccw(self, button):
        self.motor.threaded_move_by(
            angle=-self.motor_step_size,
            acceleration=self.motor_acceleration,
            max_velocity=self.motor_max_velocity
        )

    def rotate_motor_0(self, button):
        self.motor.threaded_move_to(
            position=0,
            acceleration=self.motor_acceleration,
            max_velocity=self.motor_max_velocity
        )

    def rotate_motor_cw(self, button):
        self.motor.threaded_move_by(
            angle=self.motor_step_size,
            acceleration=self.motor_acceleration,
            max_velocity=self.motor_max_velocity
        )

class DeviceInfoGroup(Adw.PreferencesGroup):
    def __init__(self, motor: motor.Motor):
        super().__init__()
        self.set_title(title='Motor Info')
        self.motor = motor

        # serial number
        serial_no_row = Adw.ActionRow(title='Serial number')
        self.add(child=serial_no_row)

        self.serial_no_label = Gtk.Label(label=self.motor._motor.get_device_info().serial_no)
        serial_no_row.add_suffix(widget=self.serial_no_label)

        # model number
        model_no_row = Adw.ActionRow(title='Model number')
        self.add(child=model_no_row)

        self.model_no_label = Gtk.Label(label=self.motor._motor.get_device_info().model_no)
        model_no_row.add_suffix(widget=self.model_no_label)

        # firmware
        fw_ver_row = Adw.ActionRow(title='Firmware version')
        self.add(child=fw_ver_row)

        self.fw_ver_label = Gtk.Label(label=self.motor._motor.get_device_info().fw_ver)
        fw_ver_row.add_suffix(widget=self.fw_ver_label)

        # device_name
        device_name_row = Adw.ActionRow(title='Device name')
        self.add(child=device_name_row)

        self.device_name_label = Gtk.Label(label=self.motor._motor.get_device_info().notes)
        device_name_row.add_suffix(widget=self.device_name_label)

class MotorControlPage(Adw.PreferencesPage):
    def __init__(self, motor: motor.Motor):
        super().__init__()

        self.motor_controls_group = MotorControls(motor=motor)
        self.add(self.motor_controls_group)

        device_info_group = DeviceInfoGroup(motor=motor)
        self.add(device_info_group)