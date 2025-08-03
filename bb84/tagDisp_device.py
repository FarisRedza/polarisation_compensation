import time
import threading
import pathlib

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GObject, GLib

from . import timetagger
from . import page_simple_display
from . import page_settings as page_settings

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

        menu = Gio.Menu.new()
        menu_button.set_menu_model(menu)

        menu.append(label='New Window', detailed_action='app.new_window')
        menu.append(label='Full Screen', detailed_action='app.full_screen')
        menu.append(label='Help', detailed_action='app.help')
        menu.append(label='About tagDisp', detailed_action='app.about')
        menu.append(label='Quit', detailed_action='app.quit')

    def set_stack(self, stack: Gtk.Stack) -> None:
        self.stack_sidebar.set_stack(stack=stack)

class DeviceBox(Gtk.Box):
    def __init__(
            self,
            tt: timetagger.TimeTagger
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.timetagger = tt
        self._measurement_rate = 0.1
        self._event = threading.Event()
        self._raw_data_container = [timetagger.RawData()]
        self._measurement_thread = threading.Thread(
            target=self._measure,
            args=(self,)
        )
        self._measurement_thread.start()

        self._data = timetagger.Data()
        self.enable_polarimeter = True

        self.poling_interval = 100

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

        simple_display = page_simple_display.SimpleDisplay()
        stack.add_titled(
            child=simple_display,
            name='Simple Display',
            title='Simple Display'
        )

        GLib.timeout_add(
            self.poling_interval,
            self.update_from_timetagger,
            simple_display,
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

    def get_data(self) -> timetagger.Data:
        return self._data
    
    def get_device_info(self) -> timetagger.DeviceInfo:
        return self.timetagger.device_info

    def update_from_timetagger(
            self,
            simple_display: page_simple_display.SimpleDisplay
    ) -> bool:
        self._data = timetagger.Data().from_raw_data(
            raw_data=self._raw_data_container[0]
        )
        self.set_timetagger_data(simple_display=simple_display)
        return True

    def set_timetagger_data(
            self,
            simple_display: page_simple_display.SimpleDisplay
    ) -> None:
        simple_display.update_counts(raw_data=self._raw_data_container[0])
        # self.plot_box.plot_ellipse_group.update_plot()
        # self.plot_box.plot_bloch_group.update_point()
        # self.columntwo.measurement_group.update_timetagger_info()

    def set_dc_calibration_file(self, path: pathlib.Path) -> None:
        self.dc_calibration_file = path

    def get_dc_calibration_file(self) -> pathlib.Path:
        return self.dc_calibration_file