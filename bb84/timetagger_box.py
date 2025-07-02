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
import bb84.timetagger as timetagger
# import bb84.qutag as qutag
# import bb84.uqd as uqd

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
        data: timetagger.Data = self.get_data_callback()

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
        data: timetagger.Data = self.get_data_callback()

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

class Counts(Adw.PreferencesGroup):
    def __init__(
            self,
            get_raw_data_callback: typing.Callable
    ) -> None:
        super().__init__(title='Counts')
        self.get_raw_data_callback = get_raw_data_callback

        data_row = Adw.ActionRow()
        self.add(child=data_row)

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

        # h
        h_label = Gtk.Label(
            label='H',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=h_label)
        self.h_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.h_value_label)

        # v
        v_label = Gtk.Label(
            label='V',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=v_label)
        self.v_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.v_value_label)

        # d
        d_label = Gtk.Label(
            label='D',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=d_label)
        self.d_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.d_value_label)

        # a
        a_label = Gtk.Label(
            label='A',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=a_label)
        self.a_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.a_value_label)

        # r
        r_label = Gtk.Label(
            label='R',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=r_label)
        self.r_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.r_value_label)

        # l
        h_label = Gtk.Label(
            label='L',
            halign=Gtk.Align.START
        )
        data_header_box.append(child=h_label)
        self.l_value_label = Gtk.Label(
            halign=Gtk.Align.START,
            width_chars=width_chars
        )
        data_value_box.append(child=self.l_value_label)

    def update_timetagger_info(self):
        raw_data: timetagger.RawData = self.get_raw_data_callback()
        singles = numpy.bincount(raw_data.channels, minlength=8)
        # singles = [int(val) for channel, val in raw_data.__dict__.items()]

        self.h_value_label.set_text(f'{singles[timetagger.C_780_H]}' if timetagger.C_780_H is not None else '0')
        self.v_value_label.set_text(f'{singles[timetagger.C_780_V]}' if timetagger.C_780_V is not None else '0')
        self.d_value_label.set_text(f'{singles[timetagger.C_780_D]}' if timetagger.C_780_D is not None else '0')
        self.a_value_label.set_text(f'{singles[timetagger.C_780_A]}' if timetagger.C_780_A is not None else '0')
        self.r_value_label.set_text(f'{singles[timetagger.C_780_R]}' if timetagger.C_780_R is not None else '0')
        self.l_value_label.set_text(f'{singles[timetagger.C_780_L]}' if timetagger.C_780_L is not None else '0')

class MeasurementGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            get_data_callback: typing.Callable
    ) -> None:
        super().__init__(title='Measurement Value Table')
        self.get_data_callback = get_data_callback

        data_row = Adw.ActionRow()
        self.add(child=data_row)

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

        # # qber
        # qber_label = Gtk.Label(
        #     label='QBER',
        #     halign=Gtk.Align.START
        # )
        # data_header_box.append(child=qber_label)
        # self.qber_value_label = Gtk.Label(
        #     halign=Gtk.Align.START,
        #     width_chars=width_chars
        # )
        # data_value_box.append(child=self.qber_value_label)

    def update_qutag_info(self):
        data: timetagger.Data = self.get_data_callback()

        # self.wavelength_value_label.set_text(f'{data.wavelength} m')
        self.azimuth_value_label.set_text(f'{data.azimuth:.2f} °')
        self.ellipticity_value_label.set_text(f'{data.ellipticity:.2f} °')
        # self.dop_value_label.set_text(f'{data.degree_of_polarisation:.2f} %')
        # self.dolp_value_label.set_text(f'{data.degree_of_linear_polarisation:.2f} %')
        # self.docp_value_label.set_text(f'{data.degree_of_circular_polarisation:.2f} %')
        # self.power_value_label.set_text(f'{data.power:.2f} dBm')
        # self.power_polarised_value_label.set_text(f'{data.power_polarised:.2f} dBm')
        # self.power_unpolarised_value_label.set_text(f'{data.power_unpolarised:.2f} dBm')
        self.normalised_s1_value_label.set_text(f'{data.normalised_s1:.2f}')
        self.normalised_s2_value_label.set_text(f'{data.normalised_s2:.2f}')
        self.normalised_s3_value_label.set_text(f'{data.normalised_s3:.2f}')
        # self.qber_value_label.set_text(f'{1 - data.normalised_s1**2:.2f}')
        # self.S0_value_label.set_text(f'{data.S0:.2} W')
        # self.S1_value_label.set_text(f'{data.S1:.2} W')
        # self.S2_value_label.set_text(f'{data.S2:.2} W')
        # self.S3_value_label.set_text(f'{data.S3:.2} W')
        # self.power_split_ratio_value_label.set_text(f'{data.power_split_ratio:.2f}')
        # self.phase_difference_value_label.set_text(f'{data.phase_difference:3.2f}')
        # self.circularity_value_label.set_text(f'{data.circularity:.2f} %')

class DeviceInfoGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            get_device_info_callback: typing.Callable
    ) -> None:
        super().__init__(title='Polarimeter Info')
        device_info: timetagger.DeviceInfo = get_device_info_callback()

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

class ColumnTwo(Adw.PreferencesPage):
    def __init__(
            self,
            get_raw_data_callback: typing.Callable,
            get_data_callback: typing.Callable,
            get_device_info_callback: typing.Callable
    ) -> None:
        super().__init__()
        self.counts_group = Counts(
            get_raw_data_callback=get_raw_data_callback
        )
        self.add(group=self.counts_group)

        self.measurement_group = MeasurementGroup(
            get_data_callback=get_data_callback
        )
        self.add(group=self.measurement_group)

        self.timetagger_group = DeviceInfoGroup(
            get_device_info_callback=get_device_info_callback
        )
        self.add(group=self.timetagger_group)

class TimeTaggerBox(Gtk.Box):
    def __init__(
            self,
            tt: timetagger.TimeTagger
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        self.timetagger = tt
        # self.raw_data = timetagger.RawData()
        self.data = timetagger.Data()

        self.columnone = ColumnOne(get_data_callback=self.get_data)
        self.append(child=self.columnone)

        self.columntwo = ColumnTwo(
            get_raw_data_callback=self.get_raw_data,
            get_data_callback=self.get_data,
            get_device_info_callback=self.get_device_info
        )
        self.append(child=self.columntwo)

        GLib.timeout_add(
            interval=125,
            function=self.update_from_timetagger
        )

    def get_raw_data(self) -> timetagger.RawData:
        return self.raw_data

    def get_data(self) -> timetagger.Data:
        return self.data
    
    def get_device_info(self) -> timetagger.DeviceInfo:
        return self.timetagger.device_info
        
    def update_from_timetagger(self) -> bool:
        self.raw_data = self.timetagger.measure()
        # self.data = self.raw_data.to_data()
        try:
            self.data = timetagger.Data().from_raw_data(
                raw_data=self.raw_data
            )
        except:
            self.data = timetagger.Data()
        self.set_qutag_data()
        return True
    
    def set_qutag_data(self) -> None:
        self.columnone.plot_ellipse_group.update_plot()
        self.columnone.plot_bloch_group.update_point()
        self.columntwo.counts_group.update_timetagger_info()
        self.columntwo.measurement_group.update_qutag_info()