import time
import threading
import pathlib

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GObject, GLib

from . import timetagger
from . import page_settings
from . import page_simple_display
from . import page_channels
from . import page_plot

class Sidebar(Gtk.Revealer):
    def __init__(self) -> None:
        super().__init__(
            transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT,
            reveal_child=True
        )
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(child=main_box)

        header_bar = Gtk.HeaderBar(show_title_buttons=False)
        main_box.append(child=header_bar)

        self.stack_sidebar = Gtk.StackSidebar(vexpand=True)
        main_box.append(child=self.stack_sidebar)

        menu_button = Gtk.MenuButton(
            icon_name='open-menu-symbolic',
            tooltip_text='Main Menu'
        )
        header_bar.pack_end(child=menu_button)

        popover = Gtk.Popover(
            position=Gtk.PositionType.BOTTOM,
        )
        menu_button.set_popover(popover=popover)

        popover_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
        )
        popover.set_child(child=popover_box)

        counter_size_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            margin_start=10
        )
        popover_box.append(child=counter_size_box)

        counter_size_label = Gtk.Label(label='Counter Size')
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

        def add_menu_button(label: str, detailed_action: str) -> None:
            button = Gtk.Button(
                label=label,
                halign=Gtk.Align.START,
                hexpand=True,
                css_classes=['flat', 'body']
            )
            button.connect('clicked', lambda b: menu_button.activate_action(name=detailed_action))
            popover_box.append(child=button)

        add_menu_button(label='Full Screen', detailed_action='app.full_screen')
        add_menu_button(label='Help', detailed_action='app.help')
        add_menu_button(label='About tagDisp', detailed_action='app.about')
        add_menu_button(label='Quit', detailed_action='app.quit')

    #     menu = Gio.Menu.new()
    #     menu.append(label='New Window', detailed_action='app.new_window')
    #     menu.append(label='Full Screen', detailed_action='app.full_screen')
    #     menu.append(label='Help', detailed_action='app.help')
    #     menu.append(label='About tagDisp', detailed_action='app.about')
    #     menu.append(label='Quit', detailed_action='app.quit')
    
    #     popover_menu = Gtk.PopoverMenu()
    #     popover_menu.set_menu_model(model=menu)
    #     menu_button.set_popover(popover=popover_menu)

    def set_stack(self, stack: Gtk.Stack) -> None:
        self.stack_sidebar.set_stack(stack=stack)

    def on_increase_counter_size(self, button: Gtk.Button) -> None:
        print('+')

    def on_decrease_counter_size(self, button: Gtk.Button) -> None:
        print('-')

class DeviceBox(Gtk.Box):
    def __init__(
            self,
            tt: timetagger.TimeTagger
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.timetagger = tt
        self._data = timetagger.Data()
        self._measurement_rate = 0.1
        self._event = threading.Event()
        self._raw_data_container = [timetagger.RawData()]
        self._measurement_thread = threading.Thread(
            target=self._measure,
            args=(self,)
        )
        self._measurement_thread.start()

        self.window = 1
        self.delay = 0
        self.refresh_rate = 250

        self.dc_calibration_file = pathlib.Path()

        sidebar = Sidebar()
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

        stack = Gtk.Stack()
        stack.set_transition_type(
            transition=Gtk.StackTransitionType.CROSSFADE
        )
        stack.connect(
            'notify::visible-child-name',
            self.on_page_changed,
            window_title
        )
        sidebar.set_stack(stack=stack)
        content_box.append(child=stack)

        stack.add_titled(
            child=page_settings.UQDSettings(),
            name='Settings',
            title='Settings'
        )

        self.simple_display = page_simple_display.SimpleDisplay(
            get_data_callback=self.get_data
        )
        stack.add_titled(
            child=self.simple_display,
            name='Simple Display',
            title='Simple Display'
        )

        self.channels_page = page_channels.ChannelsPage()
        stack.add_titled(
            child=self.channels_page,
            name='Channels',
            title='Channels'
        )

        plot_page = page_plot.PlotPage(
            get_data_callback=self.get_data
        )
        stack.add_titled(
            child=plot_page,
            name='Plot',
            title='Plot'
        )

        self._timeout_id = GLib.timeout_add(
            self.refresh_rate,
            self.set_data
        )


    def _measure(self, _) -> None:
        while True:
            for i in range(len(self._raw_data_container)):
                self._raw_data_container[i] = self.timetagger.measure()
            if self._event.is_set():
                break
            time.sleep(self._measurement_rate)

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

    def set_data(self) -> bool:
        self._data = timetagger.Data().from_raw_data(
            raw_data=self._raw_data_container[0],
            pattern=self.get_pattern()
        )
        return True

    def get_data(self) -> timetagger.Data:
        return self._data
    
    def set_pattern(self, pattern: dict) -> None:
        self.timetagger.pattern = pattern

    def get_pattern(self) -> dict:
        return self.timetagger.pattern
    
    def get_device_info(self) -> timetagger.DeviceInfo:
        return self.timetagger.device_info

    def set_dc_calibration_file(self, path: pathlib.Path) -> None:
        self.dc_calibration_file = path

    def get_dc_calibration_file(self) -> pathlib.Path:
        return self.dc_calibration_file
    
    def set_window(self, value: int) -> None:
        self.window = value

    def get_window(self) -> int:
        return self.window
    
    def set_delay(self, value: int) -> None:
        self.delay = value

    def get_delay(self) -> int:
        return self.delay

    def set_refresh_rate(self, value: int) -> None:
        self.refresh_rate = value
        if hasattr(self, '_timeout_id'):
            GLib.source_remove(self._timeout_id)
        self._timeout_id = GLib.timeout_add(
            self.refresh_rate,
            self.set_data,
            self.simple_display,
        )

    def get_refresh_rate(self) -> int:
        return self.refresh_rate
