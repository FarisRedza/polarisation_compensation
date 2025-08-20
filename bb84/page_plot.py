import typing
import collections
import enum

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw, GLib, GObject

import numpy as np
import matplotlib.backends.backend_gtk4agg
import matplotlib.pyplot

from . import timetagger

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

class QBERPlot(Adw.PreferencesGroup):
    def __init__(self, get_data_callback: typing.Callable) -> None:
        super().__init__()
        row = Adw.PreferencesRow(can_target=False)

        self._colours = {
            'blue':(0, 115/255, 229/255, 1.0),
            'orange': (233/255, 84/255, 32/255, 1.0),
        }
        self.context = row.get_style_context()
        if not self._colours.get('light'):
            self._colours['light'] = tuple(self.context.get_color())
        self.add(child=row)
        if not self._colours.get('dark'):
            self._colours['dark'] = tuple(self.context.get_color())

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

        self.qber_line = self.axes.plot(
            [],
            [],
            color=self._colours['blue'],
            label='QBER'
        )[0]
        self.qx_line = self.axes.plot(
            [],
            [],
            color=self._colours['orange'],
            label='Qx'
        )[0]
        
        self.axes.set_ylim(0, 1)
        self.axes.set_xlim(0, self.plot_length)
        self.axes.legend(frameon=False)

        self.qber = collections.deque(maxlen=self.plot_length)
        self.qx = collections.deque(maxlen=self.plot_length)

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

        self.axes.get_legend().get_texts()[0].set_text(s=f'QBER - {qber_avg:.3f}')
        self.axes.get_legend().get_texts()[1].set_text(s=f'Qx - {qx_avg:.3f}')

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
                self.figure.set_facecolor(color=self._colours['dark'])
                self.axes.set_facecolor(color=self._colours['dark'])
                self.axes.tick_params(colors=self._colours['light'])
                self.axes.spines[:].set_color(c=self._colours['light'])
                self.axes.xaxis.label.set_color(color=self._colours['light'])
                self.axes.yaxis.label.set_color(color=self._colours['light'])
                self.axes.title.set_color(color=self._colours['light'])
                for text in self.axes.get_legend().get_texts():
                    text.set_color(color=self._colours['light'])

            else:
                self.figure.set_facecolor(color=self._colours['light'])
                self.axes.set_facecolor(color=self._colours['light'])
                self.axes.tick_params(colors=self._colours['dark'])
                self.axes.spines[:].set_color(c=self._colours['dark'])
                self.axes.xaxis.label.set_color(color=self._colours['dark'])
                self.axes.yaxis.label.set_color(color=self._colours['dark'])
                self.axes.title.set_color(color=self._colours['dark'])
                for text in self.axes.get_legend().get_texts():
                    text.set_color(color=self._colours['dark'])

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