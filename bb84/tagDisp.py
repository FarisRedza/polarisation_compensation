import sys
import os
import signal
import typing
import socket

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio

from . import timetagger
from . import uqd
from . import remote_timetagger
from . import tagDisp_device

class DeviceListGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            title,
            devices_infos: list[timetagger.DeviceInfo],
            set_device_callback: typing.Callable,
            remote: bool = False
    ) -> None:
        super().__init__(title=title)
        self.remote = remote
        
        if len(devices_infos) == 0:
            no_devices_row = Adw.ActionRow(
                child=Gtk.Label(
                    label='No devices found',
                    valign=Gtk.Align.CENTER,
                    vexpand=True
                )
            )
            self.add(child=no_devices_row)

        else:
            for d in devices_infos:
                device_row = Adw.ActionRow(
                    title=d.manufacturer,
                    subtitle=f'Serial number: {d.serial_number}'
                )
                self.add(child=device_row)
                connect_device_button = Gtk.Button(
                    label='Connect',
                    valign=Gtk.Align.CENTER
                )
                connect_device_button.connect(
                    'clicked',
                    lambda button,
                    model=d.model: self.on_connect_device(
                        button=button,
                        set_device=set_device_callback,
                        model=model
                    )
                )
                device_row.add_suffix(widget=connect_device_button)

    def on_connect_device(
            self, button: Gtk.Button,
            set_device: typing.Callable,
            model: str
    ) -> None:
        set_device(
            model=model,
            remote=self.remote
        )

class RemoteConnectionGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            set_host_callback: typing.Callable,
            set_port_callback: typing.Callable,
            set_sock_callback: typing.Callable,
            server_connect_callback: typing.Callable
        ) -> None:
        super().__init__(title='Remote Connection')
        self.set_host_callback = set_host_callback
        self.set_port_callback = set_port_callback
        self.set_sock_callback = set_sock_callback
        self.server_connect_callback = server_connect_callback

        # host
        self.host_row = Adw.ActionRow(title='Host')
        self.add(child=self.host_row)
        host_entry = Gtk.Entry(
            text='127.0.0.1',
            valign=Gtk.Align.CENTER
        )
        host_entry.connect(
            'activate',
            self.on_set_host
        )
        self.host_row.add_suffix(
            widget=host_entry
        )
        # port
        self.port_row = Adw.ActionRow(title='Port')
        self.add(child=self.port_row)
        port_entry = Gtk.Entry(
            text='5001',
            valign=Gtk.Align.CENTER
        )
        port_entry.connect(
            'activate',
            self.on_set_port
        )
        self.port_row.add_suffix(
            widget=port_entry
        )

        # connect
        self.connect_row = Adw.ActionRow()
        self.add(child=self.connect_row)
        connect_button = Gtk.Button(
            label='Connect',
            valign=Gtk.Align.CENTER
        )
        connect_button.connect(
            'clicked',
            self.on_server_connect
        )
        self.connect_row.set_child(
            child=connect_button
        )

    def on_set_host(self, entry: Gtk.Entry) -> None:
        self.set_host_callback(host=entry.get_text())

    def on_set_port(self, entry: Gtk.Entry) -> None:
        try:    
            port = int(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.set_port_callback(port=port)

    def on_server_connect(self, button: Gtk.Button) -> None:
        self.server_connect_callback()

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title(title='tagDisp')
        self.set_default_size(width=650, height=575)
        self.set_size_request(width=350, height=125)
        self.connect('close-request', self.on_close_request)

        self.host = '127.0.0.1'
        self.port = 5001
        self._sock: socket.socket | None = None

        # main box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content=self.main_box)

        ## header_bar
        self.header_bar = Gtk.HeaderBar()
        if Gtk.HeaderBar().find_property(property_name='use_native_controls'):
            self.header_bar.set_use_native_controls(True)
        self.main_box.append(child=self.header_bar)

        self.main_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE
        )
        self.main_box.append(child=self.main_stack)

        self.device_select_page = Adw.PreferencesPage()
        self.main_stack.add_child(child=self.device_select_page)
        self.main_stack.set_visible_child(child=self.device_select_page)

        local_device_infos = [
            d.device_info for d in uqd.list_devices()
        ]
        # local_device_infos += [
        #     d.device_info for d in qutag.list_devices()
        # ]
        local_device_infos = [timetagger.TimeTagger().device_info]
        local_device_group = DeviceListGroup(
            title='Local Devices',
            devices_infos=local_device_infos,
            set_device_callback=self.set_device
        )
        self.device_select_page.add(group=local_device_group)

        self.remote_connection_group = RemoteConnectionGroup(
            set_host_callback=self.set_host,
            set_port_callback=self.set_port,
            set_sock_callback=self.set_sock,
            server_connect_callback=self.server_connect
        )
        self.device_select_page.add(group=self.remote_connection_group)

    def server_connect(self) -> None:
        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        sock.settimeout(5)
        sock.connect((self.host, self.port))
        self._sock = sock

        remote_device_infos = remote_timetagger.list_device_info(
            sock=self._sock
        )

        self.device_select_page.remove(group=self.remote_connection_group)
        self.device_select_page.add(
            group=DeviceListGroup(
                title='Remote Devices',
                devices_infos=remote_device_infos,
                set_device_callback=self.set_device,
                remote=True
            )
        )

    def set_device(self, model: str, remote: bool = False) -> None:
        self.main_box.remove(child=self.header_bar)
        if not remote:
            match model:
                case 'Logic-16':
                    self.timetagger_box = tagDisp_device.DeviceBox(
                        tt=uqd.UQD()
                    )
                case _:
                    self.timetagger_box = tagDisp_device.DeviceBox(
                        tt=timetagger.TimeTagger()
                    )
        else:
            self.timetagger_box = tagDisp_device.DeviceBox(
                tt=remote_timetagger.RemoteTimetagger(
                    model=model,
                    sock=self._sock
                )
            )
            pass
        self.main_stack.add_child(child=self.timetagger_box)
        self.main_stack.set_visible_child(child=self.timetagger_box)

    def on_close_request(self, window: Adw.ApplicationWindow) -> bool:
        os.kill(os.getpid(), signal.SIGINT)
        return False
    
    def get_host(self) -> str:
        return self.host
    
    def set_host(self, host: str) -> None:
        self.host = host

    def get_port(self) -> int:
        return self.port

    def set_port(self, port: int) -> None:
        self.port = port

    def set_sock(self, sock: socket.socket) -> None:
        self._sock = sock

class App(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

        help_action = Gio.SimpleAction(name='help')
        help_action.connect('activate', self.on_help)
        self.add_action(action=help_action)

        about_action = Gio.SimpleAction(name='about')
        about_action.connect('activate', self.on_about)
        self.add_action(action=about_action)

        quit_action = Gio.SimpleAction(name='quit')
        quit_action.connect('activate', self.on_quit)
        self.add_action(action=quit_action)

    def on_activate(self, app: Adw.Application) -> None:
        self.win = MainWindow(application=app)
        self.win.present()

    def on_help(
            self,
            simple_action,
            parameter_type = None
    ) -> None:
        help_dialog = Gtk.MessageDialog(
            transient_for=self.get_active_window(),
            modal=True,
            buttons=Gtk.ButtonsType.OK,
            text='Help',
            secondary_text='Select a UQD time tagger device, click start, and then click the Simple Display button'
        )
        help_dialog.connect(
            'response',
            lambda dialog, response: dialog.destroy()
        )
        help_dialog.present()

    def on_about(
            self,
            simple_action: Gio.SimpleAction,
            parameter_type = None
        ) -> None:
        about_dialog = Gtk.AboutDialog(
            transient_for=self.win,
            modal=True,
            logo_icon_name='tag-symbolic',
            name='tagDisp',
            version='0.1',
            authors=[
                'Faris Redza',
                'Peter Barrow'
            ],
            website='https://github.com/edinburgh-mostly-quantum-lab/tagDisp'
        )
        about_dialog.present()

    def on_quit(
            self,
            simple_action: Gio.SimpleAction,
            parameter_type = None
    ) -> None:
        # self.quit()
        os.kill(os.getpid(), signal.SIGINT)

if __name__ == '__main__':
    app = App(application_id='com.github.FarisRedza.tagDisp')
    try:
        app.run(sys.argv)
    except Exception as e:
        print('App crashed with an exception:', e)
    except KeyboardInterrupt:
        if hasattr(app.win, 'timetagger_box'):
            app.win.timetagger_box._event.set()
            app.win.timetagger_box._measurement_thread.join()
            app.win.timetagger_box.timetagger.disconnect()