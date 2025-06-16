import sys
import os
import typing

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

import matplotlib.backends.backend_gtk4agg
import matplotlib.figure
import matplotlib.pyplot
import numpy

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.thorlabs_polarimeter as thorlabs_polarimeter

class PolEllipseGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            get_data_callback: typing.Callable
        ) -> None:
        super().__init__(title='Polarisation Ellipse')
        self.get_data_callback = get_data_callback

        self.fig, self.ax = matplotlib.pyplot.subplots()
        self.ax.set_aspect(aspect='equal')
        self.ax.axis('off')
        self.fig.tight_layout()

        # circle
        circle = matplotlib.pyplot.Circle(
            xy=(0, 0),
            radius=1.0,
            color='gray',
            fill=False,
            linewidth=1
        )
        self.ax.add_patch(p=circle)

        # circle cross
        self.ax.plot([-1, 1], [0, 0], color='gray', linewidth=1)
        self.ax.plot([0, 0], [-1, 1], color='gray', linewidth=1)

        self.ellipse = self.ax.plot([], [], color='blue')[0]
        self.major_axis = self.ax.plot([], [], color='blue')[0]
        self.minor_axis = self.ax.plot([], [], color='blue')[0]

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.fig
        )
        self.canvas.set_size_request(width=200, height=200)
        self.add(child=Gtk.Frame(child=self.canvas))

    def update_plot(self) -> None:
        data: thorlabs_polarimeter.Data = self.get_data_callback()

        theta = numpy.radians(data.azimuth)
        eta = numpy.radians(data.ellipticity)

        ## parametric angle
        t = numpy.linspace(
            start=0,
            stop=2 * numpy.pi,
            num=500
        )
        
        ## semi-axes
        a = 1
        b = a * numpy.tan(eta)

        ## ellipse
        x = a * numpy.cos(t)
        y = b * numpy.sin(t)

        # rotate ellipse by azimuth angle
        x_rotated = x * numpy.cos(theta) - y * numpy.sin(theta)
        y_rotated = x * numpy.sin(theta) + y * numpy.cos(theta)

        self.ellipse.set_data(x_rotated, y_rotated)

        # ellipse cross
        ## major/minor axes
        x_major = numpy.array([-a, a])
        y_major = numpy.array([0, 0])

        x_minor = numpy.array([0, 0])
        y_minor = numpy.array([-b, b])

        ## rotate axes
        x_major_rotated = x_major * numpy.cos(theta) - y_major * numpy.sin(theta)
        y_major_rotated = x_major * numpy.sin(theta) + y_major * numpy.cos(theta)

        x_minor_rotated = x_minor * numpy.cos(theta) - y_minor * numpy.sin(theta)
        y_minor_rotated = x_minor * numpy.sin(theta) + y_minor * numpy.cos(theta)

        self.major_axis.set_data(x_major_rotated, y_major_rotated)
        self.minor_axis.set_data(x_minor_rotated, y_minor_rotated)

        self.canvas.draw_idle()

class BlochSphere2D(Gtk.Box):
    def __init__(self, max_trail_length=30):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.max_trail_length = max_trail_length
        self.history = []  # Stores (x, y, z)

        self.fig, self.ax = matplotlib.pyplot.subplots()
        self.ax.set_title('Bloch Sphere (2D projection)')
        self.ax.set_aspect('equal')
        self.ax.axis('off')

        # circle
        circle = matplotlib.pyplot.Circle(
            xy=(0, 0),
            radius=1.0,
            color='gray',
            fill=False
        )
        self.ax.add_patch(circle)
        self.ax.plot([-1, 1], [0, 0], color='gray', linewidth=1)
        self.ax.plot([0, 0], [-1, 1], color='gray', linewidth=1)

        # dot
        self.point = self.ax.plot(0, 0, 'o', color='blue', markersize=10)[0]

        # trail dots
        self.trail_points = [
            self.ax.plot([], [], 'o', color='blue', markersize=4, alpha=0)[0]
            for _ in range(self.max_trail_length)
        ]

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.fig
        )
        self.canvas.set_size_request(300, 300)
        self.append(self.canvas)

    def update_point(self, data: thorlabs_polarimeter.Data):
        x = data.normalised_s1
        y = data.normalised_s2
        z = data.normalised_s3

        norm = numpy.sqrt(x**2 + y**2 + z**2)
        if norm > 1e-6:
            x, y, z = x / norm, y / norm, z / norm

        # dot history
        self.history.append((x, y, z))
        if len(self.history) > self.max_trail_length:
            self.history.pop(0)

        # dot
        self.point.set_data([x], [y])
        self.point.set_alpha(1.0 if z >= 0 else 0.3 + 0.7 * (1 + z))

        # update trail points
        for i, (tx, ty, tz) in enumerate(self.history[:-1]):
            age = i / self.max_trail_length
            alpha = (1 - age) * (1.0 if tz >= 0 else 0.3 + 0.7 * (1 + tz))
            self.trail_points[i].set_data([tx], [ty])
            self.trail_points[i].set_alpha(alpha)

        # clear unused trail points
        for i in range(len(self.history) - 1, self.max_trail_length):
            self.trail_points[i].set_alpha(0)

        self.canvas.draw_idle()


class BlochSphere3D(Adw.PreferencesGroup):
    def __init__(
            self,
            get_data_callback: typing.Callable
    ) -> None:
        super().__init__(title='Bloch Sphere')
        self.get_data_callback = get_data_callback
        
        self.fig = matplotlib.figure.Figure(figsize=(4, 4))
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.axis('off')
        self.ax.set_box_aspect([1, 1, 1])
        self.fig.tight_layout()

        # sphere surface
        u = numpy.linspace(
            start=0,
            stop=2 * numpy.pi,
            num=50
        )
        v = numpy.linspace(
            start=0,
            stop=numpy.pi,
            num=50
        )
        x = numpy.outer(a=numpy.cos(u), b=numpy.sin(v))
        y = numpy.outer(a=numpy.sin(u), b=numpy.sin(v))
        z = numpy.outer(a=numpy.ones_like(u), b=numpy.cos(v))
        self.ax.plot_wireframe(x, y, z, color='lightgray', linewidth=0.5, alpha=0.3)

        self.ax.plot3D([-1, 1], [0, 0], [0, 0], color='gray', linestyle='--', linewidth=1)

        # D–A axis s2
        self.ax.plot3D([0, 0], [-1, 1], [0, 0], color='gray', linestyle='--', linewidth=1)

        # R–L axis s3
        self.ax.plot3D([0, 0], [0, 0], [-1, 1], color='gray', linestyle='--', linewidth=1)

        # polarisation basis labels
        self.ax.text(1.05, 0, 0, 'H', ha='center', va='center', fontsize=10)
        self.ax.text(-1.05, 0, 0, 'V', ha='center', va='center', fontsize=10)

        self.ax.text(0, 1.05, 0, 'D', ha='center', va='center', fontsize=10)
        self.ax.text(0, -1.05, 0, 'A', ha='center', va='center', fontsize=10)

        self.ax.text(0, 0, 1.05, 'R', ha='center', va='center', fontsize=10)
        self.ax.text(0, 0, -1.05, 'L', ha='center', va='center', fontsize=10)

        # dot
        self.point = self.ax.plot([0], [0], [0], 'o', color='blue', markersize=6)[0]

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(self.fig)
        self.canvas.set_size_request(width=200, height=200)
        self.add(child=Gtk.Frame(child=self.canvas))

    def is_behind_camera(self, x, y, z) -> bool:
        # Get current 3D projection matrix
        proj = self.ax.get_proj()

        vec = numpy.array([x, y, z, 1.0])

        transformed = proj @ vec

        # if z < 0, it's behind the viewer
        return transformed[2] < 0


    def update_point(self) -> None:
        data: thorlabs_polarimeter.Data = self.get_data_callback()

        x = data.normalised_s1
        y = data.normalised_s2
        z = data.normalised_s3

        norm = numpy.sqrt(x**2 + y**2 + z**2)
        if norm > 1e-6:
            x, y, z = x / norm, y / norm, z / norm

        self.point.set_data([x], [y])
        self.point.set_3d_properties([z])

        is_behind = self.is_behind_camera(x, y, z)

        # add transparency if dot behind sphere
        self.point.set_alpha(0.3 if is_behind else 1.0)

        self.canvas.draw_idle()

class ColumnOne(Adw.PreferencesPage):
    def __init__(
            self,
            get_data_callback: typing.Callable        
    ) -> None:
        super().__init__()

        self.plot_ellipse_group = PolEllipseGroup(
            get_data_callback=get_data_callback
        )
        self.add(group=self.plot_ellipse_group)

        self.plot_bloch_group = BlochSphere3D(
            get_data_callback=get_data_callback
        )
        self.add(group=self.plot_bloch_group)

class MeasurementGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            get_data_callback: typing.Callable
    ) -> None:
        super().__init__(title='Measurement Value Table')
        self.get_data_callback = get_data_callback

        data_row = Adw.ActionRow()
        self.add(data_row)

        margin = 6
        box_spacing = 6
        width_chars = 9

        data_header_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin_top=margin,
            margin_bottom=margin,
            valign=Gtk.Align.CENTER,
            spacing=box_spacing
        )
        data_row.add_prefix(widget=data_header_box)

        data_value_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            margin_top=margin,
            margin_bottom=margin,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.END,
            spacing=box_spacing,
        )
        data_row.add_suffix(widget=data_value_box)

        # wavelength
        wavelength_label = Gtk.Label(
            label='Wavelength',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=wavelength_label)
        self.wavelength_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.wavelength_value_label)

        # azimuth
        azimuth_label = Gtk.Label(
            label='Azimuth',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=azimuth_label)
        self.azimuth_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.azimuth_value_label)

        # ellipticity
        ellipticity_label = Gtk.Label(
            label='Ellipticity',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=ellipticity_label)
        self.ellipticity_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.ellipticity_value_label)

        # dop
        dop_label = Gtk.Label(
            label='DOP',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=dop_label)
        self.dop_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.dop_value_label)

        # dolp
        dolp_label = Gtk.Label(
            label='DOLP',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=dolp_label)
        self.dolp_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.dolp_value_label)

        # docp
        docp_label = Gtk.Label(
            label='DOCP',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=docp_label)
        self.docp_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.docp_value_label)

        # power
        power_label = Gtk.Label(
            label='Power',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=power_label)
        self.power_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.power_value_label)

        # power polarised
        poewr_polarised_label = Gtk.Label(
            label='PPol',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=poewr_polarised_label)
        self.power_polarised_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.power_polarised_value_label)

        # power unpolarised
        power_unpolarised_label = Gtk.Label(
            label='PUnpol',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=power_unpolarised_label)
        self.power_unpolarised_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.power_unpolarised_value_label)

        # normalised s1
        normalised_s1_label = Gtk.Label(
            label='s1',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=normalised_s1_label)
        self.normalised_s1_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.normalised_s1_value_label)

        # normalised s2
        normalised_s2_label = Gtk.Label(
            label='s2',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=normalised_s2_label)
        self.normalised_s2_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.normalised_s2_value_label)

        # normalised s3
        normalised_s3_label = Gtk.Label(
            label='s3',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=normalised_s3_label)
        self.normalised_s3_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.normalised_s3_value_label)

        # qber
        qber_label = Gtk.Label(
            label='QBER',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=qber_label)
        self.qber_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.qber_value_label)

        # S0
        S0_label = Gtk.Label(
            label='S0',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=S0_label)
        self.S0_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.S0_value_label)

        # S1
        S1_label = Gtk.Label(
            label='S1',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=S1_label)
        self.S1_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.S1_value_label)

        # S2
        S2_label = Gtk.Label(
            label='S2',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=S2_label)
        self.S2_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.S2_value_label)

        # S3
        S3_label = Gtk.Label(
            label='S3',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=S3_label)
        self.S3_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.S3_value_label)

        # power split ratio
        power_split_ratio_label = Gtk.Label(
            label='Power-split-ratio',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=power_split_ratio_label)
        self.power_split_ratio_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.power_split_ratio_value_label)

        # phase difference
        phase_difference_label = Gtk.Label(
            label='Phase-difference',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=phase_difference_label)
        self.phase_difference_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.phase_difference_value_label)

        # circularity
        circularity_label = Gtk.Label(
            label='Circularity',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=circularity_label)
        self.circularity_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.circularity_value_label)

    def update_polarimeter_info(self):
        data: thorlabs_polarimeter.Data = self.get_data_callback()

        self.wavelength_value_label.set_text(f'{data.wavelength} m')
        self.azimuth_value_label.set_text(f'{data.azimuth:.2f} °')
        self.ellipticity_value_label.set_text(f'{data.ellipticity:.2f} °')
        self.dop_value_label.set_text(f'{data.degree_of_polarisation:.2f} %')
        self.dolp_value_label.set_text(f'{data.degree_of_linear_polarisation:.2f} %')
        self.docp_value_label.set_text(f'{data.degree_of_circular_polarisation:.2f} %')
        self.power_value_label.set_text(f'{data.power:.2f} dBm')
        self.power_polarised_value_label.set_text(f'{data.power_polarised:.2f} dBm')
        self.power_unpolarised_value_label.set_text(f'{data.power_unpolarised:.2f} dBm')
        self.normalised_s1_value_label.set_text(f'{data.normalised_s1:.2f}')
        self.normalised_s2_value_label.set_text(f'{data.normalised_s2:.2f}')
        self.normalised_s3_value_label.set_text(f'{data.normalised_s3:.2f}')
        self.qber_value_label.set_text(f'{1 - data.normalised_s1**2:.2f}')
        self.S0_value_label.set_text(f'{data.S0:.2} W')
        self.S1_value_label.set_text(f'{data.S1:.2} W')
        self.S2_value_label.set_text(f'{data.S2:.2} W')
        self.S3_value_label.set_text(f'{data.S3:.2} W')
        self.power_split_ratio_value_label.set_text(f'{data.power_split_ratio:.2f}')
        self.phase_difference_value_label.set_text(f'{data.phase_difference:3.2f}')
        self.circularity_value_label.set_text(f'{data.circularity:.2f} %')

class DeviceSettingsGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            set_enable_polarimeter_callback: typing.Callable,
            get_enable_polarimeter_callback: typing.Callable,
            set_wavelength_callback: typing.Callable,
            get_wavelegnth_callback: typing.Callable,
            set_poling_interval_callback: typing.Callable,
            get_poling_interval_callback: typing.Callable,
            get_data_callback: typing.Callable
    ) -> None:
        super().__init__(title='Settings')
        self.set_enable_polarimeter = set_enable_polarimeter_callback
        self.get_enable_polarimeter = get_enable_polarimeter_callback
        self.set_wavelength = set_wavelength_callback
        self.get_wavelength = get_wavelegnth_callback
        self.set_poling_interval = set_poling_interval_callback
        self.get_poling_interval = get_poling_interval_callback

        enable_polarimeter_row = Adw.ActionRow(title='Enable polarimeter')
        self.add(child=enable_polarimeter_row)

        enable_polarimeter_switch = Gtk.Switch(
            valign=Gtk.Align.CENTER,
            active=self.get_enable_polarimeter()
        )
        enable_polarimeter_switch.connect(
            'notify::active',
            lambda sw, _: self.set_enable_polarimeter(sw.get_active())
        )
        enable_polarimeter_row.add_suffix(
            widget=enable_polarimeter_switch
        )
        enable_polarimeter_row.set_activatable_widget(
            widget=enable_polarimeter_switch
        )

        wavelength_row = Adw.ActionRow(title='Wavelength')
        self.add(child=wavelength_row)
        wavelength_entry = Gtk.Entry(
            text=float(get_data_callback().wavelength) * 1e9,
            placeholder_text='nm',
            valign=Gtk.Align.CENTER
        )
        wavelength_entry.connect(
            'activate',
            self.on_set_wavelength
        )
        wavelength_row.add_suffix(widget=wavelength_entry)

        poling_interval_row = Adw.ActionRow(title='Poling interval')
        self.add(child=poling_interval_row)
        poling_interval_label = Gtk.Entry(
            text=self.get_poling_interval(),
            placeholder_text='ms',
            valign=Gtk.Align.CENTER
        )
        poling_interval_label.connect(
            'activate',
            self.on_set_poling_interval
        )
        poling_interval_row.add_suffix(
            widget=poling_interval_label
        )

    def on_set_wavelength(self, entry: Gtk.Entry) -> None:
        try:
            value = abs(float(entry.get_text()) * 1e-9)
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.set_wavelength(value=value)

    def on_set_poling_interval(self, entry: Gtk.Entry) -> None:
        try:
            value = abs(float(entry.get_text()))
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.set_poling_interval(value=value)

class DeviceInfoGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            get_device_info_callback: typing.Callable
    ) -> None:
        super().__init__(title='Polarimeter Info')
        device_info: thorlabs_polarimeter.DeviceInfo = get_device_info_callback()

        # serial number
        serial_no_row = Adw.ActionRow(title='Serial number')
        self.add(child=serial_no_row)
        serial_no_label = Gtk.Label(label=device_info.serial_number)
        serial_no_row.add_suffix(widget=serial_no_label)

        # model number
        model_no_row = Adw.ActionRow(title='Model number')
        self.add(child=model_no_row)
        model_no_label = Gtk.Label(label=device_info.model)
        model_no_row.add_suffix(widget=model_no_label)

        # firmware
        fw_ver_row = Adw.ActionRow(title='Firmware version')
        self.add(child=fw_ver_row)
        fw_ver_label = Gtk.Label(label=device_info.firmware_version)
        fw_ver_row.add_suffix(widget=fw_ver_label)

class ColumnTwo(Adw.PreferencesPage):
    def __init__(
            self,
            set_enable_polarimeter_callback: typing.Callable,
            get_enable_polarimeter_callback: typing.Callable,
            set_wavelength_callback: typing.Callable,
            get_wavelength_callback: typing.Callable,
            set_poling_interval_callback: typing.Callable,
            get_poling_interval_callback: typing.Callable,
            get_data_callback: typing.Callable,
            get_device_info_callback: typing.Callable
    ) -> None:
        super().__init__()

        self.measurement_group = MeasurementGroup(
            get_data_callback=get_data_callback
        )
        self.add(group=self.measurement_group)

        self.device_settings_group = DeviceSettingsGroup(
            set_enable_polarimeter_callback=set_enable_polarimeter_callback,
            get_enable_polarimeter_callback=get_enable_polarimeter_callback,
            set_wavelength_callback=set_wavelength_callback,
            get_wavelegnth_callback=get_wavelength_callback,
            set_poling_interval_callback=set_poling_interval_callback,
            get_poling_interval_callback=get_poling_interval_callback,
            get_data_callback=get_data_callback
        )
        self.add(group=self.device_settings_group)

        self.polarimeter_group = DeviceInfoGroup(
            get_device_info_callback=get_device_info_callback
        )
        self.add(group=self.polarimeter_group)

class PolarimeterBox(Gtk.Box):
    def __init__(
            self,
            polarimeter: thorlabs_polarimeter.Polarimeter
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        # self.polarimeter = thorlabs_polarimeter.Polarimeter(
        #     id='1313:8031',
        #     serial_number='M00910360'
        # )
        self.polarimeter = polarimeter
        try:
            self.data = self.polarimeter.measure().to_data()
        except:
            self.data = thorlabs_polarimeter.Data()
        self.enable_polarimeter = True

        self.plot_box = ColumnOne(
            get_data_callback=self.get_data
        )
        self.append(child=self.plot_box)

        self.poling_interval = 100

        self.columntwo = ColumnTwo(
            set_enable_polarimeter_callback=self.set_enable_polarimeter,
            get_enable_polarimeter_callback=self.get_enable_polarimeter,
            set_wavelength_callback=self.set_wavelength,
            get_wavelength_callback=self.get_wavelength,
            set_poling_interval_callback=self.set_poling_interval,
            get_poling_interval_callback=self.get_poling_interval,
            get_data_callback=self.get_data,
            get_device_info_callback=self.get_device_info
        )
        self.append(child=self.columntwo)

        GLib.timeout_add(
            interval=self.poling_interval,
            function=self.update_from_polarimeter
        )

    def set_enable_polarimeter(self, value: bool) -> None:
        self.enable_polarimeter = value

    def get_enable_polarimeter(self) -> bool:
        return self.enable_polarimeter
    
    def set_wavelength(self, value: float) -> None:
        self.polarimeter.set_wavelength(wavelength=value)

    def get_wavelength(self) -> float:
        return self.polarimeter.measure().to_data().wavelength

    def set_poling_interval(self, value: int) -> None:
        self.poling_interval = value
        print(self.poling_interval)

    def get_poling_interval(self) -> int:
        return self.poling_interval

    def get_data(self) -> thorlabs_polarimeter.Data:
        return self.data
    
    def get_device_info(self) -> thorlabs_polarimeter.DeviceInfo:
        return self.polarimeter.device_info

    def update_from_polarimeter(self) -> bool:
        if self.enable_polarimeter == True:
            self.data = self.polarimeter.measure().to_data()
            self.set_polarimeter_data()
        return True

    def set_polarimeter_data(self):
        self.plot_box.plot_ellipse_group.update_plot()
        self.plot_box.plot_bloch_group.update_point()
        self.columntwo.measurement_group.update_polarimeter_info()