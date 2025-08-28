import typing
import platform

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, GObject, Gdk

import numpy as np
import matplotlib.backends.backend_gtk4agg
import matplotlib.figure
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
        self._build_tetupleate()

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
        self._build_tetupleate()
        self.update_counts(value=self._last_value)

    def _build_tetupleate(self) -> None:
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
    def __init__(self) -> None:
        super().__init__(title='Polarisation Ellipse')

        row = Adw.PreferencesRow(can_target=False)
        self.add(child=row)

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
        self.circle = matplotlib.pyplot.Circle(
            xy=(0, 0),
            radius=1.0,
            fill=False,
            linewidth=1
        )
        self.axes.add_patch(p=self.circle)
        self.circle_h_line = self.axes.plot(
            [-1, 1],
            [0, 0],
            linewidth=1
        )[0]
        self.circle_v_line = self.axes.plot(
            [0, 0], 
            [-1, 1],
            linewidth=1
        )[0]

        self.ellipse = self.axes.plot(
            [],
            [],
        )[0]
        self.major_axis = self.axes.plot(
            [],
            [],
        )[0]
        self.minor_axis = self.axes.plot(
            [],
            [],
        )[0]

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.figure
        )
        self.canvas.set_size_request(width=200, height=200)

        margin = 2
        box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
        )
        row.set_child(child=box)
        box.append(child=self.canvas)

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
        sin_theta = np.sin(theta)
        cos_theta = np.cos(theta)
        
        # semi-axes
        a = 1
        b = a * np.tan(eta)

        # ellipse
        x = a * self._cos_t
        y = b * self._sin_t

        # rotate ellipse by azimuth angle
        x_rotated = x * cos_theta - y * sin_theta
        y_rotated = x * sin_theta + y * cos_theta

        self.ellipse.set_data(x_rotated, y_rotated)

        # ellipse cross
        ## major/minor axes
        x_major = np.array([-a, a])
        y_major = np.array([0, 0])

        x_minor = np.array([0, 0])
        y_minor = np.array([-b, b])

        ## rotate axes
        x_major_rotated = x_major * cos_theta - y_major * sin_theta
        y_major_rotated = x_major * sin_theta + y_major * cos_theta

        x_minor_rotated = x_minor * cos_theta - y_minor * sin_theta
        y_minor_rotated = x_minor * sin_theta + y_minor * cos_theta

        self.major_axis.set_data(x_major_rotated, y_major_rotated)
        self.minor_axis.set_data(x_minor_rotated, y_minor_rotated)

        accent_colour = rgba_to_tuple(
            rgba=self.get_style_context().lookup_color(
                color_name='accent_color'
            )[1]
        )
        if any(e > 1 for e in accent_colour):
            accent_colour = Colours().BLUE

        if self.ellipse.get_color() != accent_colour:
            self.ellipse.set_color(color=accent_colour)
            self.major_axis.set_color(color=accent_colour)
            self.minor_axis.set_color(color=accent_colour)

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
                self.figure.set_facecolor(color=Colours().DARK)
                self.axes.set_facecolor(color=Colours().DARK)
                self.axes.tick_params(colors=Colours().LIGHT)
                self.axes.spines[:].set_color(c=Colours().LIGHT)
                self.axes.xaxis.label.set_color(color=Colours().LIGHT)
                self.axes.yaxis.label.set_color(color=Colours().LIGHT)
                self.axes.title.set_color(color=Colours().LIGHT)
                self.circle.set_color(c=Colours().LIGHT)
                self.circle_h_line.set_color(color=Colours().LIGHT)
                self.circle_v_line.set_color(color=Colours().LIGHT)

            else:
                self.figure.set_facecolor(color=Colours().LIGHT)
                self.axes.set_facecolor(color=Colours().LIGHT)
                self.axes.tick_params(colors=Colours().DARK)
                self.axes.spines[:].set_color(c=Colours().DARK)
                self.axes.xaxis.label.set_color(color=Colours().DARK)
                self.axes.yaxis.label.set_color(color=Colours().DARK)
                self.axes.title.set_color(color=Colours().DARK)
                self.circle.set_color(c=Colours().DARK)
                self.circle_h_line.set_color(color=Colours().DARK)
                self.circle_v_line.set_color(color=Colours().DARK)

class BlochSphereGroup(Adw.PreferencesGroup):
    def __init__(self) -> None:
        super().__init__(title='Bloch Sphere')
        row = Adw.PreferencesRow(activatable=False)
        self.add(child=row)

        self.figure = matplotlib.figure.Figure()
        self.axes = self.figure.add_subplot(111, projection='3d')
        size = 0.7
        self.axes.set_xlim([-size, size])
        self.axes.set_ylim([-size, size])
        self.axes.set_zlim([-size, size])
        self.axes.axis('off')
        self.axes.set_box_aspect([1, 1, 1])
        self.figure.tight_layout()

        # sphere surface
        u = np.linspace(
            start=0,
            stop=2 * np.pi,
            num=20
        )
        v = np.linspace(
            start=0,
            stop=np.pi,
            num=20
        )
        x = np.outer(a=np.cos(u), b=np.sin(v))
        y = np.outer(a=np.sin(u), b=np.sin(v))
        z = np.outer(a=np.ones_like(u), b=np.cos(v))

        self.sphere_wireframe = self.axes.plot_wireframe(
            x,
            y,
            z,
            linewidth=0.5,
            alpha=0.3
        )
        self.sphere_hv_line = self.axes.plot3D(
            [-1, 1],
            [0, 0],
            [0, 0],
            linestyle='--',
            linewidth=1
        )[0]
        self.sphere_da_line = self.axes.plot3D(
            [0, 0],
            [-1, 1],
            [0, 0],
            linestyle='--',
            linewidth=1
        )[0]
        self.sphere_rl_line = self.axes.plot3D(
            [0, 0],
            [0, 0],
            [-1, 1],
            linestyle='--',
            linewidth=1
        )[0]

        # polarisation basis labels
        spacing = 1.1
        self._h_label = self.axes.text(
            x=spacing,
            y=0,
            z=0,
            s='H',
            ha='center',
            va='center',
            fontsize=10
        )
        self._v_label = self.axes.text(
            x=-spacing,
            y=0,
            z=0,
            s='V',
            ha='center',
            va='center',
            fontsize=10
        )

        self._d_label = self.axes.text(
            x=0,
            y=spacing,
            z=0,
            s='D',
            ha='center',
            va='center',
            fontsize=10
        )
        self._a_label = self.axes.text(
            x=0,
            y=-spacing,
            z=0,
            s='A',
            ha='center',
            va='center',
            fontsize=10
        )

        self._r_label = self.axes.text(
            x=0,
            y=0,
            z=spacing,
            s='R',
            ha='center',
            va='center',
            fontsize=10
        )
        self._l_label = self.axes.text(
            x=0,
            y=0,
            z=-spacing,
            s='L',
            ha='center',
            va='center',
            fontsize=10
        )

        # dot
        self.point = self.axes.plot(
            [0],
            [0],
            [0],
            marker='o',
            markersize=6
        )[0]

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.figure
        )
        self.canvas.set_size_request(width=200, height=200)

        margin = 2
        box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
        )
        row.set_child(child=box)
        box.append(child=self.canvas)

        settings = Gtk.Settings.get_default()
        settings.connect(
            'notify::gtk-application-prefer-dark-theme',
            self.on_theme_changed
        )
        self.dark_mode = settings.props.gtk_application_prefer_dark_theme
        self._last_dark_mode = None
        self.update_plot_theme()

    def is_behind_camera(self, x: float, y: float, z: float) -> bool:
        # Get current 3D projection matrix
        proj = self.axes.get_proj()

        vec = np.array([x, y, z, 1.0])

        transformed = proj @ vec

        # if z < 0, it's behind the viewer
        return transformed[2] < 0

    def update_data(self, data: timetagger.Data) -> None:
        x = data.normalised_s1
        y = data.normalised_s2
        z = data.normalised_s3

        norm = np.sqrt(x**2 + y**2 + z**2)
        if norm > 1e-6:
            x, y, z = x / norm, y / norm, z / norm

        self.point.set_data([x], [y])
        self.point.set_3d_properties([z])

        is_behind = self.is_behind_camera(x=x, y=y, z=z)

        # add transparency if dot behind sphere
        # self.point.set_alpha(0.3 if is_behind else 1.0)

        accent_colour = rgba_to_tuple(
            rgba=self.get_style_context().lookup_color(
                color_name='accent_color'
            )[1]
        )
        if any(e > 1 for e in accent_colour):
            accent_colour = Colours().BLUE

        if self.point.get_color() != accent_colour:
            self.point.set_color(color=accent_colour)
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
                self.figure.set_facecolor(color=Colours().DARK)
                self.axes.set_facecolor(color=Colours().DARK)
                self.axes.tick_params(colors=Colours().LIGHT)
                self.axes.spines[:].set_color(Colours().LIGHT)
                self.axes.xaxis.label.set_color(color=Colours().LIGHT)
                self.axes.yaxis.label.set_color(color=Colours().LIGHT)
                self.axes.title.set_color(color=Colours().LIGHT)
                self._h_label.set_color(color=Colours().LIGHT)
                self._v_label.set_color(color=Colours().LIGHT)
                self._d_label.set_color(color=Colours().LIGHT)
                self._a_label.set_color(color=Colours().LIGHT)
                self._r_label.set_color(color=Colours().LIGHT)
                self._l_label.set_color(color=Colours().LIGHT)
                self.sphere_wireframe.set_color(c=Colours().LIGHT)
                self.sphere_hv_line.set_color(color=Colours().LIGHT)
                self.sphere_da_line.set_color(color=Colours().LIGHT)
                self.sphere_rl_line.set_color(color=Colours().LIGHT)

            else:
                self.figure.set_facecolor(color=Colours().LIGHT)
                self.axes.set_facecolor(color=Colours().LIGHT)
                self.axes.tick_params(colors=Colours().DARK)
                self.axes.spines[:].set_color(Colours().DARK)
                self.axes.xaxis.label.set_color(color=Colours().DARK)
                self.axes.yaxis.label.set_color(color=Colours().DARK)
                self.axes.title.set_color(color=Colours().DARK)
                self._h_label.set_color(color=Colours().DARK)
                self._v_label.set_color(color=Colours().DARK)
                self._d_label.set_color(color=Colours().DARK)
                self._a_label.set_color(color=Colours().DARK)
                self._r_label.set_color(color=Colours().DARK)
                self._l_label.set_color(color=Colours().DARK)
                self.sphere_wireframe.set_color(c=Colours().DARK)
                self.sphere_hv_line.set_color(color=Colours().DARK)
                self.sphere_da_line.set_color(color=Colours().DARK)
                self.sphere_rl_line.set_color(color=Colours().DARK)

class MeasurementBox(Gtk.Box):
    def __init__(self, channels: int, spacing: int = 20) -> None:
        super().__init__(
            spacing=spacing,
            orientation=Gtk.Orientation.VERTICAL
        )

        self.singles_group = SinglesGroup(channels=channels)
        self.append(child=self.singles_group)

        self.measurement_info_group = MeasurementInfoGroup()
        self.append(child=self.measurement_info_group)

        bottom_box = Gtk.Box(
            spacing=spacing,
            orientation=Gtk.Orientation.HORIZONTAL
        )
        self.append(child=bottom_box)

        self.polarisation_ellipse_group = PolEllipseGroup()
        bottom_box.append(child=self.polarisation_ellipse_group)

        self.bloch_sphere_group = BlochSphereGroup()
        bottom_box.append(child=self.bloch_sphere_group)

    def update_data(self, data: timetagger.Data) -> None:
        self.singles_group.update_data(data=data)
        self.measurement_info_group.update_data(data=data)
        self.polarisation_ellipse_group.update_data(data=data)
        self.bloch_sphere_group.update_data(data=data)

class SettingsScale(Adw.ActionRow):
    def __init__(
            self,
            label_string: str,
            min: float,
            max: float,
            set_value_callback: typing.Callable,
            default_value: float = 0,
            digits: int = 0,
            abs_min: float | None = None,
            abs_max: float | None = None
    ) -> None:
        super().__init__()
        self.min = min
        self.max = max

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
            text=str(self.min)
        )
        self.min_entry.connect(
            'activate',
            self.on_set_min_value,
            abs_min
        )
        main_box.append(child=self.min_entry)

        self.scale = Gtk.Scale(
            digits=digits,
            draw_value=True,
            hexpand=True,
        )
        self.scale.set_range(
            min=self.min,
            max=self.max
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
            text=str(self.max)
        )
        self.max_entry.connect(
            'activate',
            self.on_set_max_value,
            abs_max
        )
        main_box.append(child=self.max_entry)

    def on_set_value(
            self,
            scale: Gtk.Scale,
            set_value_callback: typing.Callable
    ) -> None:
        set_value_callback(value=int(scale.get_value()))

    def on_set_min_value(self, entry: Gtk.Entry, abs_min: float) -> None:
        try:
            value = float(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            if abs_min and value < abs_min:
                print(f'Value too small: {entry.get_text()}')
            else:
                self.min = value
                self.scale.set_range(min=self.min, max=self.max)
                

    def on_set_max_value(self, entry: Gtk.Entry, abs_max: float) -> None:
        try:
            value = float(entry.get_text())
            _ = value / value
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            if abs_max and value > abs_max:
                print(f'Value too large: {entry.get_text()}')
            else:
                self.max = value
                self.scale.set_range(min=self.min, max=self.max)

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
            set_value_callback=set_window_callback,
            abs_min=1
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
            set_value_callback=set_refresh_rate_callback,
            abs_min=1
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