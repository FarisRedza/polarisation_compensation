import sys

import numpy
import matplotlib.pyplot
import matplotlib.backends.backend_gtk4agg
import matplotlib.backend_bases

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, GObject

azimuth_thresholds_velocities = [
    (25.0, 25.0),
    (20.0, 20.0),
    (15.0, 15.0),
    (10.0, 10.0),
    (5.0, 5.0),
    (1.0, 1.0)
]

class CurveBox(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.fig, self.ax = matplotlib.pyplot.subplots()
        self.ax.grid(True)
        self.ax.set_xlim(0, 45)
        self.ax.set_ylim(0, 25)
        self.ax.set_xlabel(xlabel='Angle (°)')
        self.ax.set_ylabel(ylabel='Acceleration (m/s^2)')

        self.selected_index = None

        self.angle = numpy.array(
            [angle for angle, thresholds in azimuth_thresholds_velocities]
        )
        self.acceleration = numpy.array(
            [acceleration for angle, acceleration in azimuth_thresholds_velocities]
        )

        self.acceleration_curve = self.ax.plot(
            self.angle,
            self.acceleration,
            'b-'
        )[0]
        self.acceleration_points = self.ax.plot(
            self.angle,
            self.acceleration,
            'ro',
            picker=len(azimuth_thresholds_velocities)
        )[0]

        self.canvas = matplotlib.backends.backend_gtk4agg.FigureCanvasGTK4Agg(
            figure=self.fig
        )
        self.canvas.set_size_request(width=200, height=200)

        self.canvas.mpl_connect(
            'button_press_event',
            self.on_press
        )
        self.canvas.mpl_connect(
            'button_release_event',
            self.on_release
        )
        self.canvas.mpl_connect(
            'motion_notify_event',
            self.on_motion
        )

        self.append(child=Gtk.Frame(child=self.canvas))

    def on_press(self, event: matplotlib.backend_bases.MouseEvent):
        # discount mouse events outside of axes
        if event.inaxes != self.ax:
            return
        distances = numpy.hypot(
            self.angle - event.xdata,
            self.acceleration - event.ydata
        )
        if numpy.min(distances) < 1:
            self.selected_index = numpy.argmin(distances)

    def on_release(self, event: matplotlib.backend_bases.MouseEvent) -> None:
        self.selected_index = None
        print(f'angle: {self.angle}')
        print(f'acceleration: {self.acceleration}')

    def on_motion(self, event: matplotlib.backend_bases.MouseEvent):
        # discount if no selection or mouse events outside of axes
        if self.selected_index is None or event.inaxes != self.ax:
            return
       
        self.angle[self.selected_index] = round(event.xdata,2)
        self.acceleration[self.selected_index] = round(event.ydata,2)

        sorted_indices = numpy.argsort(self.angle)
        self.angle = self.angle[sorted_indices]
        self.acceleration = self.acceleration[sorted_indices]

        self.acceleration_curve.set_data(self.angle, self.acceleration)
        self.acceleration_points.set_data(self.angle, self.acceleration)

        self.canvas.draw()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title(title='Test Curve')
        self.set_default_size(width=600, height=500)
        self.set_size_request(width=400, height=300)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content=main_box)

        header_bar = Adw.HeaderBar()
        main_box.append(child=header_bar)

        dialog_row = Adw.ActionRow(title='Curve')
        dialog_button = Gtk.Button(
            icon_name='settings-symbolic',
            valign=Gtk.Align.CENTER
        )
        dialog_button.connect(
            'clicked',
            self.on_dialog_button
        )
        dialog_row.add_suffix(widget=dialog_button)
        main_box.append(child=dialog_row)

        # curve_box = CurveBox()
        # main_box.append(child=curve_box)

    def on_dialog_button(self, button: Gtk.Button) -> None:
        dialog_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dialog = Gtk.Dialog(
            child=dialog_box,
            title='Acceleration Curve'
        )
        # dialog_header_bar = Adw.HeaderBar()
        # dialog_box.append(child=dialog_header_bar)
        
        curve_box = CurveBox()
        dialog_box.append(child=curve_box)

        dialog.present()
        

class App(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        self.win = MainWindow(application=app)
        self.win.present()

if __name__ == '__main__':
    app = App(application_id='com.github.FarisRedza.TestCurve')
    app.run(sys.argv)