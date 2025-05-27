import sys
import os
import typing

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, GObject

import motor_client as thorlabs_motor

class MotorControls(Adw.PreferencesGroup):
    def __init__(
        self,
        motor: thorlabs_motor.Motor,
        get_position_callback: typing.Callable
    ) -> None:
        super().__init__(title='Motor Controls')
        self.get_position_callback = get_position_callback

        self.motor = motor

        # position
        position_row = Adw.ActionRow(title='Position')
        self.add(child=position_row)

        self.position_label = Gtk.Label(label=f'{self.get_position_callback():.3f}')
        position_row.add_suffix(widget=self.position_label)

        # rotation row
        rotation_row = Adw.ActionRow()
        self.add(child=rotation_row)

        ## control box
        control_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        control_box.set_valign(Gtk.Align.CENTER)
        control_box.set_halign(Gtk.Align.CENTER)
        control_box.set_hexpand(True)
        rotation_row.set_child(child=control_box)

        ### control grid
        control_grid = Gtk.Grid(
            column_spacing=6,
            row_spacing=6
        )
        control_box.append(child=control_grid)

        #### ccw
        self.ccw_button = Gtk.Button(
            label='CCW',
            valign=Gtk.Align.CENTER,
            sensitive=True
        )
        control_grid.attach(self.ccw_button, 1, 1, 1, 1)
        self.ccw_button.connect('clicked', self.rotate_motor_ccw)

        #### rotate to 0
        self.rot_0_button = Gtk.Button(
            label='0',
            valign=Gtk.Align.CENTER,
            sensitive=True
        )
        control_grid.attach(self.rot_0_button, 2, 1, 1, 1)
        self.rot_0_button.connect('clicked', self.rotate_motor_0)

        #### cw
        self.ccw_button = Gtk.Button(
            label='CW',
            valign=Gtk.Align.CENTER,
            sensitive=True
        )
        control_grid.attach(self.ccw_button, 3, 1, 1, 1)
        self.ccw_button.connect('clicked', self.rotate_motor_cw)

        GLib.timeout_add(
            interval=100,
            function=self.update_motor_info
        )

    def update_motor_info(self) -> bool:
        self.position_label.set_text(str=f'{self.get_position_callback():.3f}')
        # self.direction_label.set_text(str=self.get_direction_callback().name)
        # self.acceleration_entry.set_text(text=f'{self.get_acceleration_callback():.3f}')
        # self.max_velocity_entry.set_text(text=f'{self.get_max_velocity_callback():.3f}')
        return True

    def rotate_motor_ccw(self, button: Gtk.Button):
        self.motor.move_by(
            angle=-45,
            acceleration=20,
            max_velocity=25
        )

    def rotate_motor_0(self, button: Gtk.Button):
        self.motor.move_to(
            position=0,
            acceleration=20,
            max_velocity=25
        )

    def rotate_motor_cw(self, button: Gtk.Button):
        self.motor.move_by(
            angle=45,
            acceleration=20,
            max_velocity=25
        )

class DeviceInfoGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            get_device_info_callback: typing.Callable
    ) -> None:
        super().__init__()
        self.set_title(title='Motor Info')
        device_info: thorlabs_motor.DeviceInfo = get_device_info_callback()

        # serial number
        serial_no_row = Adw.ActionRow(title='Serial number')
        self.add(child=serial_no_row)

        self.serial_no_label = Gtk.Label(label=device_info.serial_number)
        serial_no_row.add_suffix(widget=self.serial_no_label)

        # model number
        model_no_row = Adw.ActionRow(title='Model number')
        self.add(child=model_no_row)

        self.model_no_label = Gtk.Label(label=device_info.model)
        model_no_row.add_suffix(widget=self.model_no_label)

        # firmware
        fw_ver_row = Adw.ActionRow(title='Firmware version')
        self.add(child=fw_ver_row)

        self.fw_ver_label = Gtk.Label(label=device_info.firmware_version)
        fw_ver_row.add_suffix(widget=self.fw_ver_label)

        # device_name
        device_name_row = Adw.ActionRow(title='Device name')
        self.add(child=device_name_row)

        self.device_name_label = Gtk.Label(label=device_info.device_name)
        device_name_row.add_suffix(widget=self.device_name_label)

class MotorControlPage(Adw.PreferencesPage):
    def __init__(self, motor: thorlabs_motor.Motor) -> None:
        super().__init__()
        self.motor = motor
        print(self.motor)

        motor_controls_group = MotorControls(
            motor=self.motor,
            get_position_callback=self.get_position
        )
        self.add(group=motor_controls_group)

        device_info_group = DeviceInfoGroup(
            get_device_info_callback=self.get_device_info
        )
        self.add(group=device_info_group)

    def get_device_info(self) -> thorlabs_motor.DeviceInfo:
        return self.motor.device_info
    
    def get_position(self) -> float:
        return self.motor.position
