import pathlib
import typing
import subprocess

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw

class SettingsGroup(Adw.PreferencesGroup):
    def __init__(self) -> None:
        super().__init__(title='UQD Settings')

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

    def on_clear_buffers(self, button) -> None:
        # for i in range(ttag.getfreebuffer()-1):
        #     ttag.deletebuffer(i)
        # print('CLEARING ALL BUFFERS')
        # print(f'FIRST FREE BUFFER IS {ttag.getfreebuffer()}')
        pass

class UQDSettings(Adw.PreferencesPage):
    def __init__(
            self,
            name: str
    ) -> None:
        super().__init__(name=name)

        settings_group = SettingsGroup()
        self.add(group=settings_group)

        uqd_interface_group = UQDInterface()
        self.add(group=uqd_interface_group)


class UQDInterface(Adw.PreferencesGroup):
    def __init__(self) -> None:
        super().__init__(title='UQD Interface')

        ## uqdinterface control box
        uqdinterface_control_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
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
        # if self.uqdinterface:
        #     return

        # self.uqd_textbuffer.set_text(text='')

        # command = [
        #         os.environ['emqTools'] + 'ttag/UQD/UQDinterface',
        #         f'--reference={self.settings.reference}',
        #         f'--led={self.settings.led}'
        #     ]
        # if self.settings.dc_calibration_file is not None:
        #     command.append(f'--dcfile={self.settings.dc_calibration_file}')

        # command = ["ping", "google.com"]
        # self.uqdinterface = subprocess.Popen(
        #     command,
        #     stdout=subprocess.PIPE,
        #     stderr=subprocess.PIPE,
        #     text=True
        # )
        # GLib.io_add_watch(self.uqdinterface.stdout, GLib.IO_IN, self.read_uqd_output)
        # GLib.io_add_watch(self.uqdinterface.stderr, GLib.IO_IN, self.read_uqd_output)
        # self.parent.on_toggle_timetagger()
        pass
        uqd_interface_path = pathlib.Path().cwd().joinpath('UQDinterface/UQDinterface')
        subprocess.Popen(['gnome-terminal', '--', uqd_interface_path])
        
        

    def on_uqd_stop(self, button) -> None:
        # if self.uqdinterface is not None:
        #     try:
        #         self.uqdinterface.wait(timeout=1)
        #         print("Process killed")
        #     except subprocess.TimeoutExpired:
        #         pass
        #     finally:
        #         self.uqdinterface = None
        pass