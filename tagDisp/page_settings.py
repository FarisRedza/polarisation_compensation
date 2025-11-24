import pathlib
import typing
import subprocess

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw

from bb84 import timetagger

class UQDSettingsGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            start_timetagger_callback: typing.Callable,
            stop_timetagger_callback: typing.Callable,
            clear_buffers_callback: typing.Callable
        ) -> None:
        super().__init__(title='UQD Settings')
        self.start_timetagger = start_timetagger_callback
        self.stop_timetagger = stop_timetagger_callback
        self.clear_buffers = clear_buffers_callback

        reference_row = Adw.ActionRow(
            title='Reference',
            subtitle='Enable the 10MHz reference'
        )
        self.add(child=reference_row)

        ### reference switch
        reference_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        reference_switch.connect('activate', self.on_toggle_reference)
        reference_row.add_suffix(widget=reference_switch)
        reference_row.set_activatable_widget(widget=reference_switch)

        ## led brightness
        led_row = Adw.ActionRow(title='LED Brightness')
        self.add(child=led_row)

        ### led scale
        self.led_scale = Gtk.Scale(
            valign=Gtk.Align.CENTER,
            width_request=250,
            height_request=-1,
            draw_value=True,
            value_pos=Gtk.PositionType.LEFT,
            digits=0
        )
        self.led_scale.set_range(min=0, max=100)
        self.led_scale.set_value(value=30)
        self.led_scale.add_mark(
            value=30,
            position=Gtk.PositionType.BOTTOM
        )
        self.led_scale.connect('value-changed', self.on_led)
        led_row.add_suffix(widget=self.led_scale)

        ## dc calibration row
        dc_calibration_row = Adw.ActionRow(
            title='DC Calibration',
            subtitle='Apply a DC calibration file'
        )
        self.add(child=dc_calibration_row)

        ### dc calibration entry
        self.dc_calibration_entry = Gtk.Entry(
            placeholder_text='No file selected',
            valign=Gtk.Align.CENTER
        )
        self.dc_calibration_entry.set_icon_from_icon_name(
            icon_pos=Gtk.EntryIconPosition.SECONDARY,
            icon_name='edit-clear-symbolic'
        )
        self.dc_calibration_entry.set_icon_tooltip_text(
            Gtk.EntryIconPosition.SECONDARY,
            'Clear'
        )
        self.dc_calibration_entry.connect('icon_press', self.on_file_clear)
        dc_calibration_row.add_suffix(widget=self.dc_calibration_entry)

        ### dc calibration button
        dc_calibration_button = Gtk.Button(valign=Gtk.Align.CENTER)
        dc_calibration_button.connect('clicked', self.on_open_file)
        dc_calibration_row.add_suffix(widget=dc_calibration_button)

        #### dc calibration button content
        dc_calibration_button_content = Adw.ButtonContent(
            icon_name='document-open-symbolic',
            label='Open'
        )
        dc_calibration_button.set_child(dc_calibration_button_content)

        ## clear buffers row
        clear_buffers_row = Adw.ActionRow(title='Clear Buffers')
        self.add(child=clear_buffers_row)

        ### clear buffers button
        clear_buffers_button = Gtk.Button(
            label='Clear',
            valign=Gtk.Align.CENTER
        )
        clear_buffers_button.connect('clicked', self.on_clear_buffers)
        clear_buffers_row.add_suffix(widget=clear_buffers_button)

        ## uqdinterface control box
        uqdinterface_control_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            margin_top=30,
            spacing=60,
            halign=Gtk.Align.CENTER
        )
        self.add(child=uqdinterface_control_box)

        ### uqd stop button
        uqd_stop_button = Gtk.Button(
            label='Stop',
            valign=Gtk.Align.CENTER,
            css_classes=['destructive-action', 'pill']
        )
        uqd_stop_button.connect('clicked', self.on_uqd_stop)
        uqdinterface_control_box.append(uqd_stop_button)

        ### uqd start button
        uqd_start_button = Gtk.Button(
            label='Start',
            valign=Gtk.Align.CENTER,
            css_classes=['suggested-action', 'pill']
        )
        uqd_start_button.connect('clicked', self.on_uqd_start)
        uqdinterface_control_box.append(uqd_start_button)

    def on_uqd_start(self, button: Gtk.Button) -> None:
        self.start_timetagger()

    def on_uqd_stop(self, button: Gtk.Button) -> None:
        self.stop_timetagger()

    def on_toggle_reference(self, switch: Gtk.Switch) -> None:
        # self.settings.led = int(self.led_scale.get_value())
        pass

    def on_led(self, scale: Gtk.Scale) -> None:
        # self.settings.reference = not self.settings.reference
        pass

    def on_open_file(self, button: Gtk.Button) -> None:
        if hasattr(Gtk, 'FileDialog'):
            dialog = Gtk.FileDialog()
            dialog.open(
                # parent=self.get_root(),
                cancellable=None,
                callback=self.on_file_selected
            )
        else:
            dialog = Gtk.FileChooserDialog(
                title='Select DC Calibration File',
                # transient_for=self.get_root(),
                modal=True,
                action=Gtk.FileChooserAction.OPEN
            )
            dialog.add_buttons(
                '_Cancel', Gtk.ResponseType.CANCEL,
                '_Open', Gtk.ResponseType.ACCEPT
            )

            dialog.connect('response', self.on_file_selected)
            dialog.show()

    def on_file_clear(
            self,
            entry: Gtk.Entry,
            _,
            set_dc_calibration_file: typing.Callable
    ) -> None:
        set_dc_calibration_file(path=pathlib.Path())
        self.dc_calibration_entry.set_text(text='No file selected')

    def on_file_selected(self, dialog, response, path: pathlib.Path) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            self.dc_calibration_entry.set_text(text=path.name)
        dialog.destroy()

    def on_clear_buffers(self, button: Gtk.Button) -> None:
        self.clear_buffers()


class DeviceInfoGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            get_device_info_callback: typing.Callable
    ) -> None:
        super().__init__(title='Device Info')
        device_info: timetagger.DeviceInfo = get_device_info_callback()

        # serial number
        serial_no_row = Adw.ActionRow(title='Serial number')
        self.add(child=serial_no_row)
        serial_no_label = Gtk.Label(label=device_info.serial_number)
        serial_no_row.add_suffix(widget=serial_no_label)

        # model number
        model_no_row = Adw.ActionRow(title='Model number')
        self.add(child=model_no_row)
        model_no_label = Gtk.Label(label=device_info.model)
        model_no_row.add_suffix(widget=model_no_label)

        # firmware
        fw_ver_row = Adw.ActionRow(title='Firmware version')
        self.add(child=fw_ver_row)
        fw_ver_label = Gtk.Label(label=device_info.firmware_version)
        fw_ver_row.add_suffix(widget=fw_ver_label)


class SettingsPage(Adw.PreferencesPage):
    def __init__(
            self,
            name: str,
            start_timetagger_callback: typing.Callable,
            stop_timetagger_callback: typing.Callable,
            clear_buffers_callback: typing.Callable,
            get_device_info_callback: typing.Callable
    ) -> None:
        super().__init__(name=name)

        settings_group = UQDSettingsGroup(
            start_timetagger_callback=start_timetagger_callback,
            stop_timetagger_callback=stop_timetagger_callback,
            clear_buffers_callback=clear_buffers_callback
        )
        self.add(group=settings_group)

        device_info_group = DeviceInfoGroup(
            get_device_info_callback=get_device_info_callback
        )
        self.add(group=device_info_group)