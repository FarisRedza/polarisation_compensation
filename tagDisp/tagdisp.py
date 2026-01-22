#!/usr/bin/env python3

import sys
import pathlib
import os
import signal
import typing
import socket
import configparser
import time
import threading

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GObject, Gdk, GLib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from bb84 import timetagger
from bb84 import remote_timetagger

import page_settings
import page_simple_display
import page_display
import page_channels
import page_plot


class DeviceSelectBox(Gtk.Box):
    def __init__(
            self,
            set_device_callback: typing.Callable,
            set_host_callback: typing.Callable,
            get_host_callback: typing.Callable,
            set_port_callback: typing.Callable,
            get_port_callback: typing.Callable,
            set_socket_callback: typing.Callable,
            get_socket_callback: typing.Callable,
            server_connect_callback: typing.Callable,
            server_disconnect_callback: typing.Callable
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_device = set_device_callback
        self.get_host = get_host_callback
        self.get_port = get_port_callback
        self.set_socket = set_socket_callback
        self.get_socket = get_socket_callback
        self.server_connect = server_connect_callback
        self.server_disconnect = server_disconnect_callback

        header_bar = Gtk.HeaderBar()
        self.append(child=header_bar)

        menu_button = MenuButton()
        header_bar.pack_end(child=menu_button)

        self.page = Adw.PreferencesPage()
        self.append(child=self.page)

        local_device_infos = []
        try:
            from bb84 import uqd
        except:
            pass
        else:
            local_device_infos = [
                d.device_info for d in uqd.list_devices()
            ]
        # try:
        #     from bb84 import qutag
        # except:
        #     pass
        # else:
        #     local_device_infos += [
        #         d.device_info for d in qutag.list_devices()
        #     ]
        local_device_infos += [timetagger.TimeTagger().device_info]

        local_device_group = DeviceListGroup(
            title='Local Devices',
            devices_infos=local_device_infos,
            set_device_callback=set_device_callback
        )
        self.page.add(group=local_device_group)

        self.remote_connection_group = RemoteConnectionGroup(
            set_host_callback=set_host_callback,
            get_host_callback=get_host_callback,
            set_port_callback=set_port_callback,
            get_port_callback=get_port_callback,
            get_remote_devices_callback=self.get_remote_devices
        )
        self.page.add(group=self.remote_connection_group)
    
    def get_remote_devices(self) -> None:
        """
        Create AdwPreferencesGroup of devices advertised from the server
        """
        self.server_connect()

        remote_device_infos = remote_timetagger.list_device_info(
            sock=self.get_socket()
        )

        self.page.remove(group=self.remote_connection_group)
        self.remote_device_list_group = DeviceListGroup(
            title='Remote Devices',
            devices_infos=remote_device_infos,
            set_device_callback=self.set_device,
            remote=True,
            remote_disconnect=self.remote_disconnect
        )
        self.page.add(group=self.remote_device_list_group)
    
    def remote_disconnect(self) -> None:
        """
        Disconnect from server and return to remote connection setup
        """
        if self.get_socket():
            self.page.remove(self.remote_device_list_group)
            self.page.add(group=self.remote_connection_group)

            self.server_disconnect()


class RemoteConnectionGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            set_host_callback: typing.Callable,
            get_host_callback: typing.Callable,
            set_port_callback: typing.Callable,
            get_port_callback: typing.Callable,
            get_remote_devices_callback: typing.Callable
    ) -> None:
        super().__init__(title='Remote Connection')
        self.get_remote_devices = get_remote_devices_callback
        self.set_host = set_host_callback
        self.set_port = set_port_callback

        host_row = Adw.ActionRow(title='Host')
        self.add(child=host_row)
        host_entry = Gtk.Entry(
            text=get_host_callback(),
            valign=Gtk.Align.CENTER
        )
        host_entry.connect(
            'activate',
            self.on_set_host
        )
        host_row.add_suffix(
            widget=host_entry
        )

        port_row = Adw.ActionRow(title='Port')
        self.add(child=port_row)
        port_entry = Gtk.Entry(
            text=str(get_port_callback()),
            valign=Gtk.Align.CENTER
        )
        port_entry.connect(
            'activate',
            self.on_set_port
        )
        port_row.add_suffix(
            widget=port_entry
        )

        device_connect_button = Gtk.Button(
            label='Connect',
            valign=Gtk.Align.CENTER
        )
        device_connect_button.connect(
            'clicked',
            self.on_get_remote_devices
        )
        self.set_header_suffix(suffix=device_connect_button)

    def on_get_remote_devices(self, button: Gtk.Button) -> None:
        self.get_remote_devices()

    def on_set_host(self, entry: Gtk.Entry) -> None:
        self.set_host(host=entry.get_text())

    def on_set_port(self, entry: Gtk.Entry) -> None:
        self.set_port(port=int(entry.get_text()))


class DeviceListGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            title: str,
            devices_infos: list[timetagger.DeviceInfo],
            set_device_callback: typing.Callable,
            remote: bool = False,
            remote_disconnect: typing.Optional[typing.Callable] = None
    ) -> None:
        super().__init__(title=title)
        self.remote = remote

        if self.remote and remote_disconnect is not None:
            self.remote_disconnect = remote_disconnect
            disconnect_button = Gtk.Button(
                label='Return',
                icon_name='carousel-arrow-previous-symbolic',
                css_classes=['flat']
            )
            disconnect_button.connect(
                'clicked',
                self.on_return
            )
            self.set_header_suffix(
                suffix=disconnect_button
            )

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
                    icon_name='carousel-arrow-next-symbolic',
                    css_classes=['flat'],
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
                device_row.set_activatable_widget(
                    widget=connect_device_button
                )

    def on_connect_device(
            self,
            button: Gtk.Button,
            set_device: typing.Callable,
            model: str
    ) -> None:
        set_device(
            model=model,
            remote=self.remote
        )
    
    def on_return(self, button: Gtk.Button) -> None:
        self.remote_disconnect()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_title(title='tagDisp')
        self.set_default_size(width=650, height=575)
        self.set_size_request(width=350, height=125)
        self.connect('close-request', self.on_close_request)

        config = configparser.ConfigParser()
        config_file = 'tagDisp.cfg'
        config_path = pathlib.Path('tagDisp', config_file)

        self._host = '127.0.0.1'
        self._port = 5001
        self._socket: typing.Optional[socket.socket] = None

        self.main_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_RIGHT
        )
        self.set_content(content=self.main_stack)

        self.device_select_box = DeviceSelectBox(
            set_device_callback=self.set_device,
            set_host_callback=self.set_host,
            get_host_callback=self.get_host,
            set_port_callback=self.set_port,
            get_port_callback=self.get_port,
            set_socket_callback=self.set_socket,
            get_socket_callback=self.get_socket,
            server_connect_callback=self.server_connect,
            server_disconnect_callback=self.server_disconnect
        )
        self.main_stack.add_child(child=self.device_select_box)
        self.main_stack.set_visible_child(child=self.device_select_box)

    def set_device(self, model: str, remote: bool = False) -> None:
        if not remote:
            match model:
                case 'Logic-16':
                    from bb84 import uqd
                    self.timetagger_box = DeviceBox(
                        tt=uqd.UQD(),
                        unset_device_callback=self.unset_device,
                        get_host_callback=self.get_host,
                        get_port_callback=self.get_port
                    )
                
                case 'quTAG':
                    from bb84 import qutag
                    self.timetagger_box = DeviceBox(
                        tt=qutag.Qutag(),
                        unset_device_callback=self.unset_device,
                        get_host_callback=self.get_host,
                        get_port_callback=self.get_port
                    )

                case _:
                    self.timetagger_box = DeviceBox(
                        tt=timetagger.TimeTagger(),
                        unset_device_callback=self.unset_device,
                        get_host_callback=self.get_host,
                        get_port_callback=self.get_port
                    )
        else:
            self.timetagger_box = DeviceBox(
                tt=remote_timetagger.RemoteTimetagger(
                    model=model,
                    sock=self.get_socket()
                ),
                unset_device_callback=self.unset_device,
                get_host_callback=self.get_host,
                get_port_callback=self.get_port
            )
        self.main_stack.add_child(child=self.timetagger_box)
        self.main_stack.set_visible_child(child=self.timetagger_box)
        self.main_stack.remove(child=self.device_select_box)

    def unset_device(self) -> None:
        self.timetagger_box.timetagger.disconnect()
        self.main_stack.add_child(child=self.device_select_box)
        self.main_stack.set_visible_child(child=self.device_select_box)
        self.main_stack.remove(child=self.timetagger_box)

    def on_close_request(self, window: Adw.ApplicationWindow) -> bool:
        try:
            from bb84 import uqd
        except:
            pass
        else:
            if isinstance(self.timetagger_box.timetagger, uqd.UQD):
                self.timetagger_box.timetagger.stop_uqdinterface()
        os.kill(os.getpid(), signal.SIGINT)
        return False

    def get_host(self) -> str:
        return self._host

    def set_host(self, host: str) -> None:
        self._host = host

    def get_port(self) -> int:
        return self._port

    def set_port(self, port: int) -> None:
        self._port = port

    def set_socket(self, socket: typing.Optional[socket.socket]) -> None:
        self._socket = socket

    def get_socket(self) -> typing.Optional[socket.socket]:
        return self._socket

    def server_connect(self) -> None:
        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )
        sock.settimeout(5)
        sock.connect((self.get_host(), self.get_port()))
        self.set_socket(socket=sock)

    def server_disconnect(self) -> None:
        if self._socket:
            self._socket.close()
            self.set_socket(socket=None)


class DeviceBox(Gtk.Box):
    def __init__(
            self,
            tt: timetagger.TimeTagger,
            unset_device_callback: typing.Callable,
            get_host_callback: typing.Callable,
            get_port_callback: typing.Callable
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.timetagger = tt
        # if isinstance(self.timetagger, uqd.UQD):
            # self.timetagger.start_uqdinterface(clear_buffers=True)
            # self.timetagger.start_reader()

        self.dc_calibration_file: pathlib.Path | None = None

        self._event = threading.Event()

        self._measurement_rate = 0.1
        self._raw_data_container = [timetagger.RawData()]
        self._measurement_thread = threading.Thread(
            target=self._measure
        )

        self._data_rate = 0.1
        self._data_container = [timetagger.Data()]
        self._data_thread = threading.Thread(
            target=self._calc_data
        )

        sidebar = DeviceSidebar(unset_device_callback=unset_device_callback)
        self.append(child=sidebar)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.append(child=content_box)

        window_title = Adw.WindowTitle()
        content_header_bar = Gtk.HeaderBar(
            title_widget=window_title,
            hexpand=True
        )
        if Gtk.HeaderBar().find_property(property_name='use_native_controls'):
            content_header_bar.set_use_native_controls(True)

        content_box.append(child=content_header_bar)

        toggle_sidebar_button = Gtk.Button(
            icon_name='sidebar-show-symbolic',
            tooltip_text='Toggle sidebar'
        )
        toggle_sidebar_button.connect(
            'clicked',
            self.on_toggle_sidebar,
            sidebar
        )
        content_header_bar.pack_start(child=toggle_sidebar_button)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(
            transition=Gtk.StackTransitionType.CROSSFADE
        )
        self.stack.connect(
            'notify::visible-child-name',
            self.on_page_changed,
            window_title
        )
        sidebar.set_stack(stack=self.stack)
        content_box.append(child=self.stack)

        # pages
        settings_name = 'Settings'
        self.stack.add_titled(
            child=page_settings.SettingsPage(
                name=settings_name,
                start_timetagger_callback=self.start_timetagger,
                stop_timetagger_callback=self.stop_timetagger,
                clear_buffers_callback=self.clear_buffers,
                get_device_info_callback=self.get_device_info,
                get_host_callback=get_host_callback,
                get_port_callback=get_port_callback
            ),
            name=settings_name,
            title=settings_name
        )

        simple_display_name = 'Simple Display'
        self.simple_display = page_simple_display.SimpleDisplay(
            name=simple_display_name,
            get_page_callback=self.get_page,
            get_data_callback=self.get_data,
            get_raw_data_callback=self.get_raw_data
        )
        self.stack.add_titled(
            child=self.simple_display,
            name=simple_display_name,
            title=simple_display_name
        )

        display_name = 'Display'
        self.display = page_display.Display(
            name=display_name,
            get_page_callback=self.get_page,
            get_data_callback=self.get_data
        )
        self.stack.add_titled(
            child=self.display,
            name=display_name,
            title=display_name
        )

        channels_name = 'Channels'
        self.channels_page = page_channels.ChannelsPage(
            name=channels_name,
            set_channel_groups_callback=self.set_channel_groups,
            get_channel_groups_callback=self.get_channel_groups
        )
        self.stack.add_titled(
            child=self.channels_page,
            name=channels_name,
            title=channels_name
        )

        plot_page = page_plot.PlotPage(
            get_data_callback=self.get_data
        )
        self.stack.add_titled(
            child=plot_page,
            name='Plot',
            title='Plot'
        )

        self._measurement_thread.start()
        self._data_thread.start()

        # css styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b'''
            .custom-headerbar {
                background-color: @window_bg_color;
            }
        ''')
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        content_header_bar.add_css_class('custom-headerbar')

    def start_timetagger(self) -> None:
        from bb84 import uqd
        if isinstance(self.timetagger, uqd.UQD):
            self.timetagger.start_uqdinterface(clear_buffers=False)
            self.timetagger.start_reader()
    
    def stop_timetagger(self) -> None:
        from bb84 import uqd
        if isinstance(self.timetagger, uqd.UQD):
            self.timetagger.stop_uqdinterface()
    
    def clear_buffers(self) -> None:
        from bb84 import uqd
        if isinstance(self.timetagger, uqd.UQD):
            self.timetagger.clear_buffers()

    def _measure(self) -> None:
        while True:
            for i in range(len(self._raw_data_container)):
                self._raw_data_container[i] = self.timetagger.measure()
            if self._event.is_set():
                break
            time.sleep(self._measurement_rate)

    def _calc_data(self) -> None:
        while True:
            raw_data = self.get_raw_data()
            if raw_data is not None:
                self._data_container = [timetagger.Data.from_raw_data(
                    raw_data=raw_data,
                    channel_groups=self.get_channel_groups()
                )]
            if self._event.is_set():
                break
            time.sleep(self._data_rate)

    def on_toggle_sidebar(
            self,
            button: Gtk.Button,
            revealer: Gtk.Revealer
    ) -> None:
        revealer.set_reveal_child(
            not revealer.get_reveal_child()
        )

    def on_page_changed(
            self,
            stack: Gtk.Stack,
            param_spec_string: GObject.ParamSpecString,
            window_title: Adw.WindowTitle
    ) -> None:
        window_title.set_title(title=stack.get_visible_child_name() or '')

    def get_raw_data(self) -> timetagger.RawData:
        return self._raw_data_container[0]

    def get_data(self) -> timetagger.Data:
        return self._data_container[0]
    
    def set_channel_groups(
            self,
            channel_groups: list[timetagger.ChannelGroup]
    ) -> None:
        self.timetagger.channel_groups = channel_groups

    def get_channel_groups(self) -> list[timetagger.ChannelGroup]:
        return self.timetagger.channel_groups
    
    def get_device_info(self) -> timetagger.DeviceInfo:
        return self.timetagger.device_info

    def set_dc_calibration_file(self, path: pathlib.Path) -> None:
        self.dc_calibration_file = path

    def get_dc_calibration_file(self) -> pathlib.Path | None:
        return self.dc_calibration_file
    
    def get_page(self) -> str | None:
        return self.stack.get_visible_child_name()


class MenuButton(Gtk.MenuButton):
    def __init__(
            self,
            # counter_size_decrease_callback: typing.Callable,
            # counter_size_increase_callback: typing.Callable
    ) -> None:
        super().__init__(icon_name='open-menu-symbolic')
        menu = Gio.Menu()
        popover = Gtk.PopoverMenu(menu_model=menu)
        self.set_popover(popover=popover)

        counter_menu = Gio.Menu()
        counter_size_item = Gio.MenuItem()
        counter_size_item.set_attribute_value(
            'custom', GLib.Variant('s','counter_size')
        )
        counter_menu.append_item(item=counter_size_item)
        menu.append_section(label=None, section=counter_menu)

        counter_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL
        )
        counter_size_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            margin_start=12,
            spacing=6
        )
        counter_box.append(child=counter_size_box)
        counter_size_label = Gtk.Label(label='Counter size')
        counter_size_box.append(child=counter_size_label)
        counter_size_decrease_button = Gtk.Button(
            icon_name='value-decrease-symbolic',
            css_classes=['circular', 'flat'],
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER
        )
        counter_size_decrease_button.connect(
            'clicked',
            self.on_decrease_counter_size
        )
        counter_size_box.append(child=counter_size_decrease_button)

        counter_size_increase_button = Gtk.Button(
            icon_name='value-increase-symbolic',
            css_classes=['circular', 'flat'],
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER
        )
        counter_size_increase_button.connect(
            'clicked',
            self.on_increase_counter_size
        )
        counter_size_box.append(child=counter_size_increase_button)
        counter_separator = Gtk.Separator(
            orientation=Gtk.Orientation.HORIZONTAL
        )
        counter_box.append(child=counter_separator)

        popover.add_child(child=counter_box, id='counter_size')

        menu.append(label='New Window', detailed_action='app.new_window')
        menu.append(label='Full Screen', detailed_action='app.full_screen')
        menu.append(label='Help', detailed_action='app.help')
        menu.append(label='About tagDisp', detailed_action='app.about')
        menu.append(label='Quit', detailed_action='app.quit')

    def on_increase_counter_size(self, button: Gtk.Button) -> None:
        print('+')

    def on_decrease_counter_size(self, button: Gtk.Button) -> None:
        print('-')


class DeviceSidebar(Gtk.Revealer):
    def __init__(self, unset_device_callback: typing.Callable) -> None:
        super().__init__(
            transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,
            reveal_child=True
        )
        self.unset_device = unset_device_callback

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(child=main_box)

        header_bar = Gtk.HeaderBar(show_title_buttons=False)
        main_box.append(child=header_bar)

        return_button = Gtk.Button(
            label='Return',
            icon_name='carousel-arrow-previous-symbolic'
        )
        return_button.connect(
            'clicked',
            self.on_return
        )
        header_bar.pack_start(child=return_button)

        self.stack_sidebar = Gtk.StackSidebar(vexpand=True)
        main_box.append(child=self.stack_sidebar)

        menu_button = MenuButton()
        header_bar.pack_end(child=menu_button)

        # css styling
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b'''
            .custom-sidebar {
                background-color: @headerbar_bg_color;
            }
            .custom-sidebar-headerbar {
                background-color: @headerbar_bg_color;
                border-bottom: none;
                box-shadow: inset 0 -1px 0 transparent;
            }
        ''')
        self.stack_sidebar.add_css_class('custom-sidebar')
        header_bar.add_css_class('custom-sidebar-headerbar')
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def set_stack(self, stack: Gtk.Stack) -> None:
        self.stack_sidebar.set_stack(stack=stack)
    
    def on_return(self, button: Gtk.Button) -> None:
        self.unset_device()


class App(Adw.Application):
    def __init__(self, **kwargs) -> None:
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
            simple_action:  Gio.SimpleAction,
            parameter_type = None
    ) -> None:
        """
        Show a help dialog
        """
        help_dialog = Gtk.MessageDialog(
            transient_for=self.get_active_window(),
            modal=True,
            visible=True,
            buttons=Gtk.ButtonsType.OK,
            text='Help',
            secondary_text='Select a UQD time tagger device, click start, and then click the Simple Display button'
        )
        help_dialog.connect(
            'response',
            lambda dialog, response: dialog.destroy()
        )

    def on_about(
            self,
            simple_action: Gio.SimpleAction,
            parameter_type = None
    ) -> None:
        """
        Show an about dialog
        """
        about_dialog = Gtk.AboutDialog(
            transient_for=self.get_active_window(),
            modal=True,
            visible=True,
            program_name='tagDisp',
            version='0.1',
            logo_icon_name='tag-symbolic',
            website='https://github.com/edinburgh-mostly-quantum-lab/tagDisp',
            website_label='GitHub',
            authors=['Faris Redza', 'Peter Barrow']
        )

    def on_quit(
            self,
            simple_action: Gio.SimpleAction,
            parameter_type = None
    ) -> None:
        # self.quit()
        os.kill(os.getpid(), signal.SIGINT)


def main() -> None:
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

if __name__ == '__main__':
    main()