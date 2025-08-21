import typing
import collections

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, GObject, Gdk

import numpy as np
import matplotlib.backends.backend_gtk4agg
import matplotlib.pyplot

from . import timetagger

def rgba_to_tuple(rgba: Gdk.RGBA) -> tuple[float, float, float, float]:
    return (rgba.red, rgba.green, rgba.blue, rgba.alpha)

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
        if Adw.get_minor_version() >= 6:
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

class QBERPlotGroup(Adw.PreferencesGroup):
    def __init__(self, get_data_callback: typing.Callable) -> None:
        super().__init__()
        row = Adw.PreferencesRow(can_target=False)
        self.add(child=row)

        self.refresh_rate = 33
        self.plot_length = 1000
        self.cycles = 5
        self.grid = False

        self.figure, self.axes = matplotlib.pyplot.subplots()
        self.figure.tight_layout()

        self.plots = {}
        self.add_line_to_plot(
            name='QBER',
            colour=Colours().BLUE
        )
        self.add_line_to_plot(
            name='Qx',
            colour=Colours().ORANGE
        )
        
        self.axes.set_ylim(0, 1)
        self.axes.set_xlim(0, self.plot_length)
        self.axes.legend(frameon=False)

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.figure
        )
        self.canvas.set_size_request(width=0, height=300)

        margin = 2
        box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
        )
        row.set_child(child=box)
        box.append(child=self.canvas)

        cycles_row = EntryRow(
            title='Cycles',
            text=str(self.cycles),
            on_set_callback=self.on_set_cycles
        )
        self.add(child=cycles_row)

        points_row = EntryRow(
            title='Points',
            text=str(self.plot_length),
            on_set_callback=self.on_set_plot_length
        )
        self.add(child=points_row)

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
            colour: tuple[float, float, float, float]
    ) -> None:
        self.plots[name] = {
            'current_value': collections.deque(maxlen=self.cycles),
            'value_history': collections.deque(maxlen=self.plot_length),
            'line': self.axes.plot([], [], color=colour, label=name)[0]
        }

    def on_set_cycles(self, entry: Gtk.Entry) -> None:
        try:
            value = int(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.cycles = value

            for _, info in self.plots.items():
                info['current_value'] = collections.deque(maxlen=self.cycles)

    def on_set_plot_length(self, entry: Gtk.Entry) -> None:
        try:
            value = int(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.plot_length = value

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

        for name, info in self.plots.items():
            value = getattr(data, name.lower(), None)
            if value is not None:
                info['current_value'].append(value)
                avg = np.mean(info['current_value'])
                info['value_history'].append(avg)

                info['line'].set_data(
                    range(len(info['value_history'])),
                    info['value_history']
                )

                for text in self.axes.get_legend().get_texts():
                    if text.get_text().startswith(name):
                        text.set_text(f'{name} - {avg:.3f}')

        self.axes.set_xlim(0, self.plot_length)
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
                self.figure.set_facecolor(color=Colours().DARK)
                self.axes.set_facecolor(color=Colours().DARK)
                self.axes.tick_params(colors=Colours().LIGHT)
                self.axes.spines[:].set_color(c=Colours().LIGHT)
                self.axes.xaxis.label.set_color(color=Colours().LIGHT)
                self.axes.yaxis.label.set_color(color=Colours().LIGHT)
                self.axes.title.set_color(color=Colours().LIGHT)
                for text in self.axes.get_legend().get_texts():
                    text.set_color(color=Colours().LIGHT)

            else:
                self.figure.set_facecolor(color=Colours().LIGHT)
                self.axes.set_facecolor(color=Colours().LIGHT)
                self.axes.tick_params(colors=Colours().DARK)
                self.axes.spines[:].set_color(c=Colours().DARK)
                self.axes.xaxis.label.set_color(color=Colours().DARK)
                self.axes.yaxis.label.set_color(color=Colours().DARK)
                self.axes.title.set_color(color=Colours().DARK)
                for text in self.axes.get_legend().get_texts():
                    text.set_color(color=Colours().DARK)

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

        qber_plot = QBERPlotGroup(get_data_callback=get_data_callback)
        main_box.append(child=qber_plot)