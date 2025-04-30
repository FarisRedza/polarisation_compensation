import sys
import os

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
import polarimeter.polarimeter as polarimeter

class PolPage(Adw.PreferencesPage):
    def __init__(self):
        super().__init__()

        self.plot_ellipse_group = PolEllipseGroup()
        self.add(self.plot_ellipse_group)

        self.plot_bloch_group = BlochSphere3D()
        self.add(self.plot_bloch_group)

class PolEllipseGroup(Adw.PreferencesGroup):
    def __init__(self):
        super().__init__(title='Polarisation Ellipse')

        self.fig, self.ax = matplotlib.pyplot.subplots()
        self.ax.set_aspect('equal')
        self.ax.axis('off')

        # circle
        circle = matplotlib.pyplot.Circle((0, 0), 1.0, color='gray', fill=False, linewidth=1)
        self.ax.add_patch(circle)

        # circle cross
        self.ax.plot([-1, 1], [0, 0], color='gray', linewidth=1)
        self.ax.plot([0, 0], [-1, 1], color='gray', linewidth=1)

        self.ellipse, = self.ax.plot([], [], color='blue')
        self.major_axis, = self.ax.plot([], [], color='blue')
        self.minor_axis, = self.ax.plot([], [], color='blue')

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(self.fig)
        self.canvas.set_size_request(200, 200)
        self.add(self.canvas)

    def update_plot(self, data: polarimeter.Data):
        theta = numpy.radians(data.azimuth)
        eta = numpy.radians(data.ellipticity)

        ## parametric angle
        t = numpy.linspace(0, 2 * numpy.pi, 500)
        
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
        circle = matplotlib.pyplot.Circle((0, 0), 1.0, color='gray', fill=False)
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

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(self.fig)
        self.canvas.set_size_request(300, 300)
        self.append(self.canvas)

    def update_point(self, data: polarimeter.Data):
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
    def __init__(self):
        super().__init__(title='Bloch Sphere')
        
        self.fig = matplotlib.figure.Figure(figsize=(4, 4))
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.axis('off')
        self.ax.set_box_aspect([1, 1, 1])

        # sphere surface
        u = numpy.linspace(0, 2 * numpy.pi, 50)
        v = numpy.linspace(0, numpy.pi, 50)
        x = numpy.outer(numpy.cos(u), numpy.sin(v))
        y = numpy.outer(numpy.sin(u), numpy.sin(v))
        z = numpy.outer(numpy.ones_like(u), numpy.cos(v))
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
        self.canvas.set_size_request(200, 200)
        self.add(self.canvas)

    def is_behind_camera(self, x, y, z):
        # Get current 3D projection matrix
        proj = self.ax.get_proj()

        vec = numpy.array([x, y, z, 1.0])

        transformed = proj @ vec

        # if z < 0, it's behind the viewer
        return transformed[2] < 0


    def update_point(self, data: polarimeter.Data):
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


class DataViewPage(Adw.PreferencesPage):
    def __init__(self, data: polarimeter.Data):
        super().__init__()

        data_group = Adw.PreferencesGroup(title='Measurement Value Table')
        self.add(data_group)

        data_row = Adw.ActionRow()
        data_group.add(data_row)

        data_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6
        )
        data_row.set_child(child=data_box)

        ## wavelength
        wavelength_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=wavelength_row)
        self.wavelength_label = Gtk.Label(label=f'Wavelength: {data.wavelength} m', xalign=0)
        wavelength_row.append(child=self.wavelength_label)

        ## azimuth
        azimuth_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=azimuth_row)
        self.azimuth_label = Gtk.Label(
            label=f'Azimuth: {data.azimuth} °',
            xalign=0
        )
        azimuth_row.append(child=self.azimuth_label)

        ## ellipticity
        ellipticity_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=ellipticity_row)
        self.ellipticity_label = Gtk.Label(
            label=f'Ellipticity: {data.ellipticity} °',
            xalign=0
        )
        ellipticity_row.append(child=self.ellipticity_label)

        ## dop
        dop_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=dop_row)
        self.dop_label = Gtk.Label(
            label=f'DOP: {data.degree_of_polarisation} %',
            xalign=0
        )
        dop_row.append(child=self.dop_label)

        ## dolp
        dolp_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=dolp_row)
        self.dolp_label = Gtk.Label(
            label=f'DOLP: {data.degree_of_linear_polarisation} %',
            xalign=0
        )
        dolp_row.append(child=self.dolp_label)
        
        ## docp
        docp_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=docp_row)
        self.docp_label = Gtk.Label(
            label=f'DOCP: {data.degree_of_circular_polarisation} %',
            xalign=0
        )
        docp_row.append(child=self.docp_label)

        ## power
        power_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=power_row)
        self.power_label = Gtk.Label(
            label=f'Power: {data.power} dBm',
            xalign=0
        )
        power_row.append(child=self.power_label)

        ## power_polarised
        power_polarised_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=power_polarised_row)
        self.power_polarised_label = Gtk.Label(
            label=f'PPol: {data.power_polarised} dBm',
            xalign=0
        )
        power_polarised_row.append(child=self.power_polarised_label)

        ## power_unpolarised
        power_unpolarised_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=power_unpolarised_row)
        self.power_unpolarised_label = Gtk.Label(
            label=f'PUnpol: {data.power_unpolarised} dBm',
            xalign=0
        )
        power_unpolarised_row.append(child=self.power_unpolarised_label)

        ## normalised_s1
        normalised_s1_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=normalised_s1_row)
        self.normalised_s1_label = Gtk.Label(
            label=f's1: {data.normalised_s1}',
            xalign=0
        )
        normalised_s1_row.append(child=self.normalised_s1_label)

        ## normalised_s2
        normalised_s2_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=normalised_s2_row)
        self.normalised_s2_label = Gtk.Label(
            label=f's2: {data.normalised_s2}',
            xalign=0
        )
        normalised_s2_row.append(child=self.normalised_s2_label)

        ## normalised_s3
        normalised_s3_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=normalised_s3_row)
        self.normalised_s3_label = Gtk.Label(
            label=f's3: {data.normalised_s3}',
            xalign=0
        )
        normalised_s3_row.append(child=self.normalised_s3_label)

        ## S0
        S0_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=S0_row)
        self.S0_label = Gtk.Label(
            label=f'S0 {data.S0} W',
            xalign=0
        )
        S0_row.append(child=self.S0_label)

        ## S1
        S1_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=S1_row)
        self.S1_label = Gtk.Label(
            label=f'01: {data.S1} W',
            xalign=0
        )
        S1_row.append(child=self.S1_label)

        ## S2
        S2_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=S2_row)
        self.S2_label = Gtk.Label(
            label=f'S2 {data.S2} W',
            xalign=0
        )
        S2_row.append(child=self.S2_label)

        ## S3
        S3_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=S3_row)
        self.S3_label = Gtk.Label(
            label=f'S3 {data.S3} W',
            xalign=0
        )
        S3_row.append(child=self.S3_label)

        ## power_split_ratio
        power_split_ratio_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=power_split_ratio_row)
        self.power_split_ratio_label = Gtk.Label(
            label=f'Power-split-ratio: {data.power_split_ratio}',
            xalign=0
        )
        power_split_ratio_row.append(child=self.power_split_ratio_label)

        ## phase_difference
        phase_difference_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=phase_difference_row)
        self.phase_difference_label = Gtk.Label(
            label=f'Phase-difference: {data.phase_difference} °',
            xalign=0
        )
        phase_difference_row.append(child=self.phase_difference_label)

        ## circularity
        circularity_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=6
        )
        data_box.append(child=circularity_row)
        self.circularity_label = Gtk.Label(
            label=f'Circularity: {data.circularity} %',
            xalign=0
        )
        circularity_row.append(child=self.circularity_label)

    def update_polarimeter_info(self, data: polarimeter.Data):
        self.wavelength_label.set_text(f'Wavelength: {data.wavelength} m')
        self.azimuth_label.set_text(f'Azimuth: {data.azimuth:.2f} °')
        self.ellipticity_label.set_text(f'Ellipticity: {data.ellipticity:.2f} °')
        self.dop_label.set_text(f'DOP: {data.degree_of_polarisation:.2f} %')
        self.dolp_label.set_text(f'DOLP: {data.degree_of_linear_polarisation:.2f} %')
        self.docp_label.set_text(f'DOCP: {data.degree_of_circular_polarisation:.2f} %')
        self.power_label.set_text(f'Power: {data.power:.2f} dBm')
        self.power_polarised_label.set_text(f'PPol: {data.power_polarised:.2f} dBm')
        self.power_unpolarised_label.set_text(f'PUnpol: {data.power_unpolarised:.2f} dBm')
        self.normalised_s1_label.set_text(f's1: {data.normalised_s1:.2f}')
        self.normalised_s2_label.set_text(f's2: {data.normalised_s2:.2f}')
        self.normalised_s3_label.set_text(f's3: {data.normalised_s3:.2f}')
        self.S0_label.set_text(f'S0: {data.S0:.2} W')
        self.S1_label.set_text(f'S1: {data.S1:.2} W')
        self.S2_label.set_text(f'S2: {data.S2:.2} W')
        self.S3_label.set_text(f'S3: {data.S3:.2} W')
        self.power_split_ratio_label.set_text(f'Power-split-ratio: {data.power_split_ratio:.2f}')
        self.phase_difference_label.set_text(f'Phase-difference: {data.phase_difference:.2f}')
        self.circularity_label.set_text(f'Circularity: {data.circularity:.2f} %')

class PolarimeterBox(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)

        self.pax = polarimeter.Polarimeter(
            id='1313:8031',
            serial_number='M00910360'
        )
        self.pax.set_wavelength(wavelength=7e-7)
        self.data = polarimeter.Data()

        self.plot_box = PolPage()
        self.append(self.plot_box)

        self.data_view_page = DataViewPage(data=self.data)
        self.append(self.data_view_page)

        GLib.timeout_add(100, self.update_from_polarimeter)

    def update_from_polarimeter(self) -> bool:
        self.data = self.pax.measure().to_data()
        self.set_polarimeter_data(data=self.data)
        return True

    def set_polarimeter_data(self, data: polarimeter.Data):
        self.plot_box.plot_ellipse_group.update_plot(data=data)
        self.plot_box.plot_bloch_group.update_point(data=data)
        self.data_view_page.update_polarimeter_info(data=self.data)