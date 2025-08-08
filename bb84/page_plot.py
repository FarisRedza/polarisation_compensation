import typing
import collections
import enum

import numpy as np
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw, GLib, GObject

import matplotlib.backends.backend_gtk4agg
import matplotlib.pyplot

from . import timetagger

class PolEllipsePlot(Gtk.Box):
    class Colours(enum.Enum):
        BLUE = (0, 115/255, 229/255, 1.0)
        ORANGE = (233/255, 84/255, 32/255, 1.0)
        DARK = (61/255, 61/255, 61/255, 1.0)
        LIGHT = (247/255, 247/255, 247/255, 1.0)
    def __init__(
            self,
            get_data_callback: typing.Callable
    ) -> None:
        super().__init__()
        self.refresh_rate = 33

        self.figure, self.axes = matplotlib.pyplot.subplots()
        self.axes.set_aspect(aspect='equal')
        self.axes.axis('off')
        self.figure.tight_layout()

        # circle
        circle = matplotlib.pyplot.Circle(
            xy=(0, 0),
            radius=1.0,
            color='gray',
            fill=False,
            linewidth=1
        )
        self.axes.add_patch(p=circle)

        # circle cross
        self.axes.plot([-1, 1], [0, 0], color='gray', linewidth=1)
        self.axes.plot([0, 0], [-1, 1], color='gray', linewidth=1)

        self.ellipse = self.axes.plot([], [], color=self.Colours.BLUE.value)[0]
        self.major_axis = self.axes.plot([], [], color=self.Colours.BLUE.value)[0]
        self.minor_axis = self.axes.plot([], [], color=self.Colours.BLUE.value)[0]

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.figure
        )
        self.canvas.set_size_request(width=200, height=200)
        self.append(child=Gtk.Frame(child=self.canvas))

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

    def update_plot(
            self,
            get_data_callback: typing.Callable
    ) -> bool:
        data: timetagger.Data = get_data_callback()

        theta = np.radians(data.azimuth)
        eta = np.radians(data.ellipticity)

        ## parametric angle
        t = np.linspace(
            start=0,
            stop=2 * np.pi,
            num=500
        )
        
        ## semi-axes
        a = 1
        b = a * np.tan(eta)

        ## ellipse
        x = a * np.cos(t)
        y = b * np.sin(t)

        # rotate ellipse by azimuth angle
        x_rotated = x * np.cos(theta) - y * np.sin(theta)
        y_rotated = x * np.sin(theta) + y * np.cos(theta)

        self.ellipse.set_data(x_rotated, y_rotated)

        # ellipse cross
        ## major/minor axes
        x_major = np.array([-a, a])
        y_major = np.array([0, 0])

        x_minor = np.array([0, 0])
        y_minor = np.array([-b, b])

        ## rotate axes
        x_major_rotated = x_major * np.cos(theta) - y_major * np.sin(theta)
        y_major_rotated = x_major * np.sin(theta) + y_major * np.cos(theta)

        x_minor_rotated = x_minor * np.cos(theta) - y_minor * np.sin(theta)
        y_minor_rotated = x_minor * np.sin(theta) + y_minor * np.cos(theta)

        self.major_axis.set_data(x_major_rotated, y_major_rotated)
        self.minor_axis.set_data(x_minor_rotated, y_minor_rotated)

        self.canvas.draw_idle()
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
                self.figure.set_facecolor(color=self.Colours.DARK.value)
                self.axes.set_facecolor(color=self.Colours.DARK.value)
                self.axes.tick_params(colors=self.Colours.LIGHT.value)
                self.axes.spines[:].set_color(self.Colours.LIGHT.value)
                self.axes.xaxis.label.set_color(color=self.Colours.LIGHT.value)
                self.axes.yaxis.label.set_color(color=self.Colours.LIGHT.value)
                self.axes.title.set_color(color=self.Colours.LIGHT.value)

            else:
                self.figure.set_facecolor(color=self.Colours.LIGHT.value)
                self.axes.set_facecolor(color=self.Colours.LIGHT.value)
                self.axes.tick_params(colors=self.Colours.DARK.value)
                self.axes.spines[:].set_color(self.Colours.DARK.value)
                self.axes.xaxis.label.set_color(color=self.Colours.DARK.value)
                self.axes.yaxis.label.set_color(color=self.Colours.DARK.value)
                self.axes.title.set_color(color=self.Colours.DARK.value)


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

class QBERPlot(Gtk.Box):
    class Colours(enum.Enum):
        BLUE = (0, 115/255, 229/255, 1.0)
        ORANGE = (233/255, 84/255, 32/255, 1.0)
        DARK = (61/255, 61/255, 61/255, 1.0)
        LIGHT = (247/255, 247/255, 247/255, 1.0)
    def __init__(self, get_data_callback: typing.Callable) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )
        self.refresh_rate = 33
        self.plot_length = 1000
        self.cycles = 5
        self.grid = False

        self.qber_values = collections.deque(maxlen=self.cycles)
        self.qx_values = collections.deque(maxlen=self.cycles)
        self.azimuth_values = collections.deque(maxlen=self.cycles)
        self.ellipticity_values = collections.deque(maxlen=self.cycles)

        self.figure, self.axes = matplotlib.pyplot.subplots()
        self.figure.tight_layout()

        self.qber_line, = self.axes.plot([], [], color=self.Colours.BLUE.value, label='QBER')
        self.qx_line, = self.axes.plot([], [], color=self.Colours.ORANGE.value, label='Qx')
        
        self.axes.set_ylim(0, 1)
        self.axes.set_xlim(0, self.plot_length)
        self.axes.legend(frameon=False)

        self.qber = collections.deque(maxlen=self.plot_length)
        self.qx = collections.deque(maxlen=self.plot_length)

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.figure
        )
        self.append(child=Gtk.Frame(child=self.canvas))

        plot_settings_group = Adw.PreferencesGroup(title='Plot Settings')
        self.append(child=plot_settings_group)

        cycles_row = EntryRow(
            title='Cycles',
            text=str(self.cycles),
            on_set_callback=self.on_set_cycles
        )
        plot_settings_group.add(child=cycles_row)

        points_row = EntryRow(
            title='Points',
            text=str(self.plot_length),
            on_set_callback=self.on_set_plot_length
        )
        plot_settings_group.add(child=points_row)

        grid_row = SwitchRow(
            title='Grid',
            on_set_callback=self.on_set_grid
        )
        plot_settings_group.add(child=grid_row)

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

    def on_set_cycles(self, entry: Gtk.Entry) -> None:
        try:
            value = int(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.cycles = value
            self.qber_values = collections.deque(maxlen=self.cycles)
            self.qx_values = collections.deque(maxlen=self.cycles)

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

        self.qber_values.append(data.qber)
        self.qx_values.append(data.qx)

        qber_avg = np.mean(self.qber_values)
        qx_avg = np.mean(self.qx_values)

        self.qber.append(qber_avg)
        self.qx.append(qx_avg)

        self.qber_line.set_data(
            range(len(self.qber)),
            self.qber
        )
        self.qx_line.set_data(
            range(len(self.qx)),
            self.qx
        )
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
                self.figure.set_facecolor(color=self.Colours.DARK.value)
                self.axes.set_facecolor(color=self.Colours.DARK.value)
                self.axes.tick_params(colors=self.Colours.LIGHT.value)
                self.axes.spines[:].set_color(self.Colours.LIGHT.value)
                self.axes.xaxis.label.set_color(color=self.Colours.LIGHT.value)
                self.axes.yaxis.label.set_color(color=self.Colours.LIGHT.value)
                self.axes.title.set_color(color=self.Colours.LIGHT.value)
                for text in self.axes.get_legend().get_texts():
                    text.set_color(color=self.Colours.LIGHT.value)

            else:
                self.figure.set_facecolor(color=self.Colours.LIGHT.value)
                self.axes.set_facecolor(color=self.Colours.LIGHT.value)
                self.axes.tick_params(colors=self.Colours.DARK.value)
                self.axes.spines[:].set_color(self.Colours.DARK.value)
                self.axes.xaxis.label.set_color(color=self.Colours.DARK.value)
                self.axes.yaxis.label.set_color(color=self.Colours.DARK.value)
                self.axes.title.set_color(color=self.Colours.DARK.value)
                for text in self.axes.get_legend().get_texts():
                    text.set_color(color=self.Colours.DARK.value)

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

        qber_plot = QBERPlot(get_data_callback=get_data_callback)
        main_box.append(child=qber_plot)
        
        pol_plot = PolEllipsePlot(get_data_callback=get_data_callback)
        main_box.append(child=pol_plot)