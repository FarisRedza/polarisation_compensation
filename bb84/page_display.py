import typing
import enum

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw, GLib, GObject

import numpy as np
import matplotlib.backends.backend_gtk4agg
import matplotlib.pyplot

from . import timetagger

class Counter(Gtk.Box):
    def __init__(self, label: str, counter_size: int = 40) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.counter_size = counter_size
        channel_label = Gtk.Label(label=label)
        self.append(child=channel_label)

        self.channel_counts_label = Gtk.Label()
        self.channel_counts_label.set_halign(align=Gtk.Align.END)
        self.channel_counts_label.set_hexpand(expand=True)
        self.append(child=self.channel_counts_label)
        self._build_template()

    def update_counts(self, value: int | float) -> None:
        self._last_value = value
        match value:
            case int() | np.integer():
                text = str(value)
            case float():
                text = f'{value:.2f}'
            case _:
                raise RuntimeError(f'Invalid value type: {type(value)}')

        self.channel_counts_label.set_text(str=text)
    
    def set_counter_size(self, counter_size: int) -> None:
        self.counter_size = counter_size
        self._build_template()
        self.update_counts(value=self._last_value)

    def _build_template(self) -> None:
        ctx = self.channel_counts_label.get_style_context()
        css = f"label {{ font-family: Monospace; font-size: {self.counter_size}pt; }}"
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        ctx.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

class SinglesGroup(Adw.PreferencesGroup):
    def __init__(self, channels: int) -> None:
        super().__init__(title='Singles')

        row = Adw.ActionRow()
        self.add(child=row)

        margin = 6
        main_box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            orientation=Gtk.Orientation.HORIZONTAL
        )
        row.set_child(child=main_box)

        left_box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            orientation=Gtk.Orientation.VERTICAL
        )
        main_box.append(child=left_box)
        main_box.append(child=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        right_box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            orientation=Gtk.Orientation.VERTICAL
        )
        main_box.append(child=right_box)

        self.counters: list[Counter] = []
        for i in range(1, int(channels/2)+1):
            counter = Counter(
                label=f'Channel {i}',
                counter_size=24
            )
            self.counters.append(counter)
            left_box.append(child=counter)

        for i in range(int(channels/2)+1, channels+1):
            counter = Counter(
                label=f'Channel {i}',
                counter_size=24
            )
            self.counters.append(counter)
            right_box.append(child=counter)

    def update_data(self, data: timetagger.Data) -> None:
        for counter, value in zip(self.counters, data.singles):
            counter.update_counts(value=value)

class MeasurementInfoGroup(Adw.PreferencesGroup):
    def __init__(self) -> None:
        super().__init__(title='Measurement Info')

        row = Adw.ActionRow()
        self.add(child=row)

        margin = 6
        box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            orientation=Gtk.Orientation.VERTICAL
        )
        row.set_child(child=box)

        self.s1_counter = Counter(
            label='s1',
            counter_size=16
        )
        box.append(child=self.s1_counter)

        self.s2_counter = Counter(
            label='s2',
            counter_size=16
        )
        box.append(child=self.s2_counter)

        self.s3_counter = Counter(
            label='s3',
            counter_size=16
        )
        box.append(child=self.s3_counter)

        self.qber_counter = Counter(
            label='QBER',
            counter_size=16
        )
        box.append(child=self.qber_counter)

        self.qx_counter = Counter(
            label='Qx',
            counter_size=16
        )
        box.append(child=self.qx_counter)

    def update_data(self, data: timetagger.Data) -> None:
        self.s1_counter.update_counts(value=data.normalised_s1)
        self.s2_counter.update_counts(value=data.normalised_s2)
        self.s3_counter.update_counts(value=data.normalised_s3)

        self.qber_counter.update_counts(value=data.qber)
        self.qx_counter.update_counts(value=data.qx)

class PolEllipseGroup(Adw.PreferencesGroup):
    class Colours(enum.Enum):
        BLUE = (0, 115/255, 229/255, 1.0)
        ORANGE = (233/255, 84/255, 32/255, 1.0)
        DARK = (61/255, 61/255, 61/255, 1.0)
        LIGHT = (1.0, 1.0, 1.0, 1.0)
    def __init__(self) -> None:
        super().__init__(title='Polarisation Ellipse')
        # parametric angle
        self._t = np.linspace(
            start=0,
            stop=2 * np.pi,
            num=36
        )
        self._cos_t = np.cos(self._t)
        self._sin_t = np.sin(self._t)

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
        self.axes.plot(
            [-1, 1],
            [0, 0],
            color='gray',
            linewidth=1
        )
        self.axes.plot(
            [0, 0], 
            [-1, 1],
            color='gray',
            linewidth=1
        )

        self.ellipse = self.axes.plot([], [], color=self.Colours.BLUE.value)[0]
        self.major_axis = self.axes.plot([], [], color=self.Colours.BLUE.value)[0]
        self.minor_axis = self.axes.plot([], [], color=self.Colours.BLUE.value)[0]

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.figure
        )
        self.add(child=Gtk.Frame(child=self.canvas))

        settings = Gtk.Settings.get_default()
        settings.connect(
            'notify::gtk-application-prefer-dark-theme',
            self.on_theme_changed
        )
        self.dark_mode = settings.props.gtk_application_prefer_dark_theme
        self._last_dark_mode = None
        self.update_plot_theme()

    def update_data(self, data: timetagger.Data) -> None:
        theta = np.radians(data.azimuth)
        eta = np.radians(data.ellipticity)
        
        # semi-axes
        a = 1
        b = a * np.tan(eta)

        # ellipse
        x = a * self._cos_t
        y = b * self._sin_t

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

class MeasurementBox(Gtk.Box):
    def __init__(self, channels: int, spacing: int = 20) -> None:
        super().__init__(
            spacing=spacing,
            orientation=Gtk.Orientation.VERTICAL
        )

        self.singles_group = SinglesGroup(channels=channels)
        self.append(child=self.singles_group)

        bottom_box = Gtk.Box(
            spacing=spacing,
            orientation=Gtk.Orientation.HORIZONTAL
        )
        self.append(child=bottom_box)

        self.measurement_info_group = MeasurementInfoGroup()
        bottom_box.append(child=self.measurement_info_group)

        self.polarisation_ellipse_group = PolEllipseGroup()
        bottom_box.append(child=self.polarisation_ellipse_group)

    def update_data(self, data: timetagger.Data) -> None:
        self.singles_group.update_data(data=data)
        self.measurement_info_group.update_data(data=data)
        self.polarisation_ellipse_group.update_data(data=data)

class SettingsScale(Adw.ActionRow):
    def __init__(
            self,
            label_string: str,
            min: float,
            max: float,
            set_value_callback: typing.Callable,
            default_value: float = 0,
            digits: int = 0
    ) -> None:
        super().__init__()
        margin = 6
        main_box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            spacing=margin,
            orientation=Gtk.Orientation.HORIZONTAL
        )
        self.set_child(child=main_box)

        label = Gtk.Label(
            label=label_string,
            width_chars=7,
            wrap=True,
            justify=Gtk.Justification.CENTER
        )
        main_box.append(child=label)

        self.min_entry = Gtk.Entry(
            valign=Gtk.Align.CENTER,
            max_length=5,
            max_width_chars=5,
            text=str(min)
        )
        # self.min_entry.connect('activate', self.on_update_window_range)
        main_box.append(child=self.min_entry)

        self.scale = Gtk.Scale(
            digits=digits,
            draw_value=True,
            hexpand=True,
        )
        self.scale.set_range(
            min=min,
            max=max
        )
        self.scale.set_value(value=default_value)
        self.scale.connect(
            'value-changed',
            self.on_set_value,
            set_value_callback
        )
        main_box.append(child=self.scale)

        self.max_entry = Gtk.Entry(
            valign=Gtk.Align.CENTER,
            max_length=5,
            max_width_chars=5,
            text=str(max)
        )
        # self.max_entry.connect('activate', self.on_update_window_range)
        main_box.append(child=self.max_entry)

    def on_set_value(
            self,
            scale: Gtk.Scale,
            set_value_callback: typing.Callable
    ) -> None:
        set_value_callback(value=int(scale.get_value()))

class SettingsGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            set_window_callback: typing.Callable,
            get_window_callback: typing.Callable,
            set_refresh_rate_callback: typing.Callable,
            get_refresh_rate_callback: typing.Callable,
            set_delay_callback: typing.Callable,
            get_delay_callback: typing.Callable
    ) -> None:
        super().__init__(title='Display Settings')
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(child=main_box)

        window_scale = SettingsScale(
            label_string='Window (ns)',
            min=1,
            max=2000,
            default_value=get_window_callback(),
            set_value_callback=set_window_callback
        )
        self.add(child=window_scale)

        delay_scale = SettingsScale(
            label_string='Delay (ns)',
            min=-1000,
            max=1000,
            default_value=get_delay_callback(),
            set_value_callback=set_delay_callback
        )
        self.add(child=delay_scale)

        refresh_rate_scale = SettingsScale(
            label_string='Refresh Rate (ms)',
            min=1,
            max=500,
            default_value=get_refresh_rate_callback(),
            # digits=3,
            set_value_callback=set_refresh_rate_callback
        )
        self.add(child=refresh_rate_scale)

class Display(Gtk.ScrolledWindow):
    def __init__(
            self,
            name: str,
            get_page_callback: typing.Callable,
            get_data_callback: typing.Callable
    ) -> None:
        super().__init__(
            name=name,
            vexpand=True
        )
        self.get_page_callback = get_page_callback
        self.get_data_callback = get_data_callback

        self.set_policy(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC
        )
        self.counter_size = 40
        self.window = 1
        self.delay = 0
        self.refresh_rate = 250
    
        margin = 20
        main_box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            spacing=margin,
            orientation=Gtk.Orientation.VERTICAL
        )
        self.set_child(main_box)

        self.measurement_box = MeasurementBox(channels=8, spacing=margin)
        main_box.append(child=self.measurement_box)

        self.settings_box = SettingsGroup(
            set_window_callback=self.set_window,
            get_window_callback=self.get_window,
            set_delay_callback=self.set_delay,
            get_delay_callback=self.get_delay,
            set_refresh_rate_callback=self.set_refresh_rate,
            get_refresh_rate_callback=self.get_refresh_rate
        )
        main_box.append(child=self.settings_box)

        self._timeout_id = GLib.timeout_add(
            self.refresh_rate,
            self.update_data
        )

    def update_data(self) -> bool:
        if self.get_page_callback() == self.get_name():
            data: timetagger.Data = self.get_data_callback()
            self.measurement_box.update_data(data=data)
        return True

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
            self.update_data
        )

    def get_refresh_rate(self) -> int:
        return self.refresh_rate