import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, GObject

import motor.remote_motor as remote_motor
import motor.thorlabs_motor as thorlabs_motor
import motor.gui_widget as motor_gui_widget
import polarimeter.thorlabs_polarimeter as thorlabs_polarimeter
import polarimeter.gui_widget as polarimeter_gui_widget

from . import pol_comp

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_title(title='Polarisation Compensation')
        self.set_default_size(width=1300, height=800)
        self.set_size_request(width=1250, height=300)
        self.connect(
            'close-request',
            self.on_close_request
        )

        # main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content=main_box)

        ## header_bar
        header_bar = Adw.HeaderBar()
        main_box.append(child=header_bar)

        ## content_box
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(child=self.content_box)

        ### polarimeter box
        self.measurement_box = polarimeter_gui_widget.PolarimeterBox(
            polarimeter=thorlabs_polarimeter.Polarimeter(
                serial_number='M00910360'
            )
        )
        main_box.append(child=self.measurement_box)

    def on_close_request(self, window: Adw.ApplicationWindow) -> bool:
        if type(self.measurement_box) == polarimeter_gui_widget.PolarimeterBox:
            self.measurement_box.polarimeter.disconnect()
        # for i in self.motor_controllers:
        #     i.motor_controls_group.motor.stop()
        return False

class App(Adw.Application):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app) -> None:
        self.win = MainWindow(application=app)
        self.win.present()

if __name__ == '__main__':
    app = App(application_id='com.github.FarisRedza.PolarisationCompensation')
    try:
        app.run(sys.argv)
    except Exception as e:
        # if type(app.win.polarisation_box) == polarimeter_gui_widget.PolarimeterBox:
            # app.win.polarisation_box.polarimeter.disconnect()
        print('App crashed with an exception:', e)