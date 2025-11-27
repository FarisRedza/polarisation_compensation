import typing
import collections
import dataclasses
import platform

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, GObject, Gdk

import numpy as np
import matplotlib.backends.backend_gtk4agg
import matplotlib.pyplot

from bb84 import timetagger

def rgba_to_tuple(rgba: Gdk.RGBA) -> tuple[float, float, float, float]:
    return (rgba.red, rgba.green, rgba.blue, rgba.alpha)

@dataclasses.dataclass
class Colours:
    BLUE: tuple[float, float, float, float]
    TEAL: tuple[float, float, float, float]
    GREEN: tuple[float, float, float, float]
    YELLOW: tuple[float, float, float, float]
    ORANGE: tuple[float, float, float, float]
    RED: tuple[float, float, float, float]
    PINK: tuple[float, float, float, float]
    PURPLE: tuple[float, float, float, float]
    SLATE: tuple[float, float, float, float]
    BROWN: tuple[float, float, float, float]
    LIGHT: tuple[float, float, float, float]
    DARK: tuple[float, float, float, float]

    def __init__(self) -> None:
        if Adw.get_minor_version() >= 6 and platform.system() == 'Linux':
            colours = {}
            for colour in Adw.AccentColor:
                colours[colour.name] = rgba_to_tuple(colour.to_rgba())

            colours['LIGHT'] = (1, 1, 1, 1)
            colours['DARK'] = (61/255, 61/255, 61/255, 1)
        else:
            colours = {
                'BLUE': (0.207843, 0.517647, 0.894118, 1.000000),
                'TEAL': (0.129412, 0.564706, 0.643137, 1.000000),
                'GREEN':(0.227451, 0.580392, 0.290196, 1.000000),
                'YELLOW': (0.784314, 0.533333, 0.000000, 1.000000),
                'ORANGE': (0.929412, 0.356863, 0.000000, 1.000000),
                'RED': (0.901961, 0.176471, 0.258824, 1.000000),
                'PINK': (0.835294, 0.380392, 0.600000, 1.000000),
                'PURPLE': (0.568627, 0.254902, 0.674510, 1.000000),
                'SLATE': (0.435294, 0.513726, 0.588235, 1.000000),
                'BROWN': (0.701961, 0.568627, 0.411765, 1.000000),
                'LIGHT': (1, 1, 1, 1),
                'DARK': (53/255, 53/255, 53/255, 1)
            }

        for name, rgba in colours.items():
            setattr(self, name, rgba)

class EntryRow(Adw.ActionRow):
    def __init__(
            self,
            title: str,
            text: str,
            on_set_callback: typing.Callable
    ) -> None:
        super().__init__(title=title)
        entry = Gtk.Entry(
            text=text,
            valign=Gtk.Align.CENTER
        )
        entry.connect(
            'activate',
            on_set_callback
        )
        self.add_suffix(widget=entry)

class SwitchRow(Adw.ActionRow):
    def __init__(
            self,
            title: str,
            on_set_callback: typing.Callable
    ) -> None:
        super().__init__(title=title)
        switch = Gtk.Switch(
            valign=Gtk.Align.CENTER
        )
        switch.connect(
            'notify::active',
            on_set_callback
        )
        self.add_suffix(widget=switch)
        self.set_activatable_widget(
            widget=switch
        )

class PlotDisplayGroup(Adw.PreferencesGroup):
    def __init__(self, get_data_callback: typing.Callable) -> None:
        super().__init__()
        self._colours = Colours()
        row = Adw.PreferencesRow(can_target=False)
        self.add(child=row)

        self.ylim_min = 0
        self.ylim_max = 1

        self.refresh_rate = 33
        self.time_window = 30
        self.plot_length = int(self.time_window / (self.refresh_rate / 1000)) + 1
        self.samples = 5
        self.grid = False

        self.figure, self.axes = matplotlib.pyplot.subplots()
        self.figure.tight_layout()

        self.plots = {}
        
        self.axes.set_ylim(self.ylim_min, self.ylim_max)
        self.axes.set_xlim(0, self.plot_length)

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.figure
        )
        self.canvas.set_size_request(width=0, height=500)

        margin = 2
        box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
        )
        row.set_child(child=box)
        box.append(child=self.canvas)

        samples_row = EntryRow(
            title='Samples',
            text=str(self.samples),
            on_set_callback=self.on_set_samples
        )
        self.add(child=samples_row)

        time_window_row = EntryRow(
            title='Time window (s)',
            text=str(self.time_window),
            on_set_callback=self.on_set_time_window
        )
        self.add(child=time_window_row)

        ylim_min_row = EntryRow(
            title='Y limit minimum value',
            text=str(self.ylim_min),
            on_set_callback=self.on_set_ylim_min
        )
        self.add(child=ylim_min_row)

        ylim_max_row = EntryRow(
            title='Y limit maximum value',
            text=str(self.ylim_max),
            on_set_callback=self.on_set_ylim_max
        )
        self.add(child=ylim_max_row)

        grid_row = SwitchRow(
            title='Grid',
            on_set_callback=self.on_set_grid
        )
        self.add(child=grid_row)

        settings = Gtk.Settings.get_default()
        settings.connect(
            'notify::gtk-application-prefer-dark-theme',
            self.on_theme_changed
        )
        self.dark_mode = settings.props.gtk_application_prefer_dark_theme
        self._last_dark_mode = None
        self.update_plot_theme()

        self._timeout_id = GLib.timeout_add(
            self.refresh_rate,
            self.update_plot,
            get_data_callback
        )

    def add_line_to_plot(
            self,
            name: str,
            attribute: str,
            colour: tuple[float, float, float, float]
    ) -> None:
        self.plots[name] = {
            'attribute': attribute,
            'current_value': collections.deque(maxlen=self.samples),
            'value_history': collections.deque(maxlen=self.plot_length),
            'line': self.axes.plot([], [], color=colour, label=name)[0]
        }
        self.axes.legend(frameon=False)

    def remove_line_from_plot(
            self,
            name: str
    ) -> None:
        info = self.plots.pop(name, None)
        if info is not None:
            info['line'].remove()
            if self.axes.get_legend():
                self.axes.legend(frameon=False)
            self.canvas.draw() 

    def get_plots(self) -> typing.KeysView:
        return self.plots.keys()

    def on_set_samples(self, entry: Gtk.Entry) -> None:
        try:
            value = int(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.samples = value

            for _, info in self.plots.items():
                info['current_value'] = collections.deque(maxlen=self.samples)

    def on_set_time_window(self, entry: Gtk.Entry) -> None:
        try:
            value = int(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.time_window = value
            dt = self.refresh_rate / 1000
            self.plot_length = int(self.time_window / dt) + 1
            for _, info in self.plots.items():
                old_history = info['value_history']
                info['value_history'] = collections.deque(old_history, maxlen=self.plot_length)

    def on_set_ylim_min(self, entry: Gtk.Entry) -> None:
        try:
            value = float(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.ylim_min = value

    def on_set_ylim_max(self, entry: Gtk.Entry) -> None:
        try:
            value = float(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.ylim_max = value

    def on_set_grid(
            self,
            switch: Gtk.Switch,
            g_param_spec: GObject.GParamSpec
    ) -> None:
        self.grid = switch.get_active()

    def update_plot(
            self,
            get_data_callback: typing.Callable
    ) -> bool:
        data: timetagger.Data = get_data_callback()

        dt = self.refresh_rate / 1000
        for name, info in self.plots.items():
            value = getattr(data, info['attribute'], None)
            if value is not None:
                info['current_value'].append(value)
                avg = np.mean(info['current_value'])
                info['value_history'].append(avg)

                x_values = np.linspace(
                    -dt * (len(info['value_history']) - 1),
                    0,
                    len(info['value_history'])
                )

                info['line'].set_data(
                    x_values,
                    info['value_history']
                )

                for text in self.axes.get_legend().get_texts():
                    if text.get_text().startswith(name):
                        text.set_text(f'{name} - {avg:.3f}')
                        text.set_color(color=self._colours.LIGHT) if self.dark_mode else text.set_color(color=self._colours.DARK)

        self.axes.set_ylim(self.ylim_min, self.ylim_max)
        self.axes.set_xlim(-dt * self.plot_length, 0)
        self.axes.grid(visible=self.grid)

        self.canvas.draw()
        return True
    
    def on_theme_changed(
            self,
            settings: Gtk.Settings,
            g_param_spec: GObject.GParamSpec
    ) -> None:
        self.dark_mode = settings.props.gtk_application_prefer_dark_theme
        self.update_plot_theme()

    def update_plot_theme(self) -> None:
        if self.dark_mode != self._last_dark_mode:
            self._last_dark_mode = self.dark_mode

            if self.dark_mode:
                self.figure.set_facecolor(color=self._colours.DARK)
                self.axes.set_facecolor(color=self._colours.DARK)
                self.axes.tick_params(colors=self._colours.LIGHT)
                self.axes.spines[:].set_color(c=self._colours.LIGHT)
                self.axes.xaxis.label.set_color(color=self._colours.LIGHT)
                self.axes.yaxis.label.set_color(color=self._colours.LIGHT)
                self.axes.title.set_color(color=self._colours.LIGHT)
                if self.axes.get_legend():
                    for text in self.axes.get_legend().get_texts():
                        text.set_color(color=self._colours.LIGHT)

            else:
                self.figure.set_facecolor(color=self._colours.LIGHT)
                self.axes.set_facecolor(color=self._colours.LIGHT)
                self.axes.tick_params(colors=self._colours.DARK)
                self.axes.spines[:].set_color(c=self._colours.DARK)
                self.axes.xaxis.label.set_color(color=self._colours.DARK)
                self.axes.yaxis.label.set_color(color=self._colours.DARK)
                self.axes.title.set_color(color=self._colours.DARK)
                if self.axes.get_legend():
                    for text in self.axes.get_legend().get_texts():
                        text.set_color(color=self._colours.DARK)

class PlotsGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            add_line_to_plot_callback: typing.Callable,
            remove_line_from_plot_callback: typing.Callable,
            get_plots_callback: typing.Callable
    ) -> None:
        super().__init__(title='Plots')
        self._colours = Colours()
        self.plot_strings = Gtk.StringList()

        self.add_plot(
            name='qber',
            colour=self._colours.ORANGE,
            add_line_to_plot_callback=add_line_to_plot_callback,
            remove_line_from_plot_callback=remove_line_from_plot_callback,
            get_plots_callback=get_plots_callback
        )
        self.add_plot(
            name='qx',
            colour=self._colours.BLUE,
            add_line_to_plot_callback=add_line_to_plot_callback,
            remove_line_from_plot_callback=remove_line_from_plot_callback,
            get_plots_callback=get_plots_callback
        )

        add_plot_row = Adw.ActionRow(title='Add plot')
        self.add(child=add_plot_row)

        colour_dropown = Gtk.DropDown(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        add_plot_row.add_suffix(widget=colour_dropown)
        colour_strings = Gtk.StringList()
        colour_dropown.props.model = colour_strings
        for field in dataclasses.fields(Colours)[:-2]:
            colour_strings.append(string=field.name)

        plot_dropown = Gtk.DropDown(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        add_plot_row.add_suffix(widget=plot_dropown)
        plot_dropown.props.model = self.plot_strings

        self.set_plot_strings_list(get_plots_callback=get_plots_callback)

        add_plot_button = Gtk.Button(
            icon_name='list-add-symbolic',
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        add_plot_button.add_css_class(css_class='suggested-action')
        add_plot_button.connect(
            'clicked',
            self.on_add_plot,
            plot_dropown,
            colour_dropown,
            add_plot_row,
            add_line_to_plot_callback,
            remove_line_from_plot_callback,
            get_plots_callback
        )
        add_plot_row.add_suffix(widget=add_plot_button)

    def on_remove_plot(
            self,
            button: Gtk.Button,
            row: Adw.ActionRow,
            remove_line_from_plot_callback: typing.Callable,
            get_plots_callback: typing.Callable
    ) -> None:
        remove_line_from_plot_callback(name=row.get_title())
        self.set_plot_strings_list(get_plots_callback=get_plots_callback)
        self.remove(child=row)

    def add_plot(
            self,
            name: str,
            colour: tuple[float, float, float, float],
            add_line_to_plot_callback: typing.Callable,
            remove_line_from_plot_callback: typing.Callable,
            get_plots_callback: typing.Callable,
            row: Adw.ActionRow | None = None
    ) -> None:
        add_line_to_plot_callback(
            name=name,
            attribute=name,
            colour=colour
        )
        self.set_plot_strings_list(
            name=name,
            get_plots_callback=get_plots_callback
        )

        new_row = Adw.ActionRow(title=name)
        self.add(child=new_row)
        remove_plot_button = Gtk.Button(
            icon_name='list-remove-symbolic',
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        remove_plot_button.add_css_class(css_class='destructive-action')
        remove_plot_button.connect(
            'clicked',
            self.on_remove_plot,
            new_row,
            remove_line_from_plot_callback,
            get_plots_callback
        )
        new_row.add_suffix(widget=remove_plot_button)

        if row:
            self.remove(child=row)
            self.add(child=row)

    def on_add_plot(
            self,
            button: Gtk.Button,
            dropown: Gtk.DropDown,
            colour_dropown: Gtk.DropDown,
            row: Adw.ActionRow,
            add_line_to_plot_callback: typing.Callable,
            remove_line_from_plot_callback: typing.Callable,
            get_plots_callback: typing.Callable
    ) -> None:
        name: str = dropown.props.selected_item.props.string
        colour: tuple[float, float, float, float] = getattr(
            self._colours,
            colour_dropown.props.selected_item.props.string
        )

        self.add_plot(
            name=name,
            colour=colour,
            row=row,
            add_line_to_plot_callback=add_line_to_plot_callback,
            remove_line_from_plot_callback=remove_line_from_plot_callback,
            get_plots_callback=get_plots_callback
        )

    def set_plot_strings_list(
            self,
            get_plots_callback: typing.Callable,
            name: str | None = None,
    ) -> None:
        strings = []
        for i, _ in enumerate(self.plot_strings):
            strings.append(self.plot_strings.get_string(i))
        if name and name in strings:
            self.plot_strings.remove(strings.index(name))
            strings.remove(name)
        for field in dataclasses.fields(timetagger.Data):
            if field.name != 'singles' and field.name not in list(get_plots_callback()) and field.name not in strings:
                self.plot_strings.append(string=field.name)

class PlotPage(Gtk.ScrolledWindow):
    def __init__(
            self,
            get_data_callback: typing.Callable
    ) -> None:
        super().__init__(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC
        )

        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
            spacing=12
        )
        self.set_child(child=main_box)

        plot_display_group = PlotDisplayGroup(get_data_callback=get_data_callback)
        main_box.append(child=plot_display_group)

        plots_group = PlotsGroup(
            add_line_to_plot_callback=plot_display_group.add_line_to_plot,
            remove_line_from_plot_callback=plot_display_group.remove_line_from_plot,
            get_plots_callback=plot_display_group.get_plots
        )
        main_box.append(child=plots_group)