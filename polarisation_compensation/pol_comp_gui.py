import sys
import os
import enum
import typing

import numpy
import matplotlib.pyplot
import matplotlib.backends.backend_gtk4agg
import matplotlib.backend_bases

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, GObject

import pol_compensation as pol_compensation

sys.path.append(
    os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        os.path.pardir
    ))
)
import polarimeter.polarimeter_box as polarimeter_box
import motor.motor_box as motor_box
import motor.thorlabs_motor as thorlabs_motor

class CurveBox(Gtk.Box):
    def __init__(
            self,
            # angle_velocity: list[tuple]
            set_angle_velocity_callback: typing.Callable,
            get_angle_velocity_callback: typing.Callable
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_angle_velocity = set_angle_velocity_callback
        self.get_angle_velocity = get_angle_velocity_callback

        self.fig, self.ax = matplotlib.pyplot.subplots()
        self.ax.grid(True)
        self.ax.set_xlim(0, 45)
        self.ax.set_ylim(0, 25)
        self.ax.set_xlabel(xlabel='Angle (°)')
        self.ax.set_ylabel(ylabel='Acceleration (m/s^2)')

        self.selected_index = None

        self.angle = numpy.array(
            [angle for angle, acceleration in self.get_angle_velocity()]
        )
        self.acceleration = numpy.array(
            [acceleration for angle, acceleration in self.get_angle_velocity()]
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
            picker=len(self.get_angle_velocity())
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

        self.set_angle_velocity(
            value=list(zip([float(f) for f in self.angle],[float(f) for f in self.acceleration]))
        )

        self.canvas.draw()

class ControlGroup(Adw.PreferencesGroup):
    class MotorWP(enum.Enum):
        QWP = 55353314  # azimuth
        HWP = 55356974  # ellipticity

    class MotorDirection(enum.Enum):
        FORWARD = '+'
        BACKWARD = '-'
        IDLE = None
    def __init__(
            self,
            polarimeter_box: polarimeter_box.PolarimeterBox,
            motor_controllers: list[motor_box.MotorControlPage],
            set_enable_compensation_callback: typing.Callable,
            get_enable_compensation_callback: typing.Callable,
            set_target_azimuth_callback: typing.Callable,
            get_target_azimuth_callback: typing.Callable,
            set_target_ellipticity_callback: typing.Callable,
            get_target_ellipticity_callback: typing.Callable,
            set_qwp_motor_callback: typing.Callable,
            get_qwp_motor_callback: typing.Callable,
            set_hwp_motor_callback: typing.Callable,
            get_hwp_motor_callback: typing.Callable,
            set_polarimeter_callback: typing.Callable,
            get_polarimeter_callback: typing.Callable,
            set_azimuth_velocity_callback: typing.Callable,
            get_azimuth_velocity_callback: typing.Callable,
            set_ellipticity_velocity_callback: typing.Callable,
            get_ellipticity_velocity_callback: typing.Callable,
    ) -> None:
        super().__init__(title='Polarisation Compensation')
        self.polarimeter_box = polarimeter_box
        self.motor_controllers = [m.motor_controls_group for m in motor_controllers]

        self.set_enable_compensation = set_enable_compensation_callback
        self.get_enable_compensation = get_enable_compensation_callback
        self.set_target_azimuth = set_target_azimuth_callback
        self.get_target_azimuth = get_target_azimuth_callback
        self.set_target_ellipticity = set_target_ellipticity_callback
        self.get_target_ellipticity = get_target_ellipticity_callback

        self.set_qwp_motor = set_qwp_motor_callback
        self.get_qwp_motor = get_qwp_motor_callback
        self.set_hwp_motor = set_hwp_motor_callback
        self.get_hwp_motor = get_hwp_motor_callback
        self.set_polarimeter = set_polarimeter_callback
        self.get_polarimeter = get_polarimeter_callback

        self.set_azimuth_velocity = set_azimuth_velocity_callback
        self.get_azimuth_velocity = get_azimuth_velocity_callback
        self.set_ellipticity_velocity = set_ellipticity_velocity_callback
        self.get_ellipticity_velocity = get_ellipticity_velocity_callback


        self.set_qwp_motor(value=self.MotorWP.QWP.value)
        self.set_hwp_motor(value=self.MotorWP.HWP.value)
        self.set_polarimeter(
            value=self.polarimeter_box.polarimeter.device_info.serial_number
        )

        for mc in self.motor_controllers:
            mc.enable_controls_switch.connect(
                'notify::active',
                self.on_update_available_motors
            )

        self.available_motors = [
            m.motor for m in self.motor_controllers if m.manual_motor_control == False
        ]

        self.target_azimuth = 0
        self.target_ellipticity = 0

        # motor settings
        self.azimuth_motor_step_size = 0
        self.azimuth_motor_acceleration = 0
        self.azimuth_motor_max_velocity = 0
        self.azimuth_motor_direction = self.MotorDirection.IDLE
        self.ellipticity_motor_step_size = 0
        self.ellipticity_motor_acceleration = 0
        self.ellipticity_motor_max_velocity = 0
        self.ellipticity_motor_direction = self.MotorDirection.IDLE

        motor_poling_interval = 100

        # enable compensation
        enable_compensation_row = Adw.ActionRow(
            title='Enable compensation'
        )
        self.add(child=enable_compensation_row)

        enable_compensation_switch = Gtk.Switch(
            active=self.get_enable_compensation(),
            valign=Gtk.Align.CENTER
        )
        enable_compensation_switch.connect(
            'notify::active',
            lambda sw, _: self.set_enable_compensation(sw.get_active())
        )
        enable_compensation_row.add_suffix(
            widget=enable_compensation_switch
        )
        enable_compensation_row.set_activatable_widget(
            widget=enable_compensation_switch
        )

        # azimuth
        target_azimuth_row = Adw.ActionRow(title='Target azimuth')
        self.add(child=target_azimuth_row)

        self.target_azimuth_entry = Gtk.Entry(
            text=self.get_target_azimuth(),
            valign=Gtk.Align.CENTER,
        )
        target_azimuth_row.add_suffix(widget=self.target_azimuth_entry)
        self.target_azimuth_entry.connect(
            'activate',
            self.on_set_target_azimuth
        )

        # ellipticity
        target_ellipticity_row = Adw.ActionRow(title='Target ellipticity')
        self.add(child=target_ellipticity_row)

        self.target_ellipticity_entry = Gtk.Entry(
            text=self.get_target_ellipticity(),
            valign=Gtk.Align.CENTER,
        )
        target_ellipticity_row.add_suffix(widget=self.target_ellipticity_entry)
        self.target_ellipticity_entry.connect(
            'activate',
            self.on_set_target_ellipticity
        )

        GLib.timeout_add(
            interval=motor_poling_interval,
            function=self.pol_comp
        )

    def on_set_target_azimuth(self, entry: Gtk.Entry):
        try:
            value = float(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.set_target_azimuth(value=value)

    def on_set_target_ellipticity(self, entry: Gtk.Entry):
        try:
            value = float(entry.get_text())
        except:
            print(f'Invalid entry: {entry.get_text()}')
        else:
            self.set_target_ellipticity(value=value)

    def set_motor_step_size(self, attr_str: str, value: float) -> None:
        attr = getattr(self, f'{attr_str}_step_size')
        setattr(self, attr, value)

    def get_motor_step_size(self, attr_str: str) -> float:
        attr = getattr(self, f'{attr_str}_step_size')
        return attr

    def on_update_available_motors(
            self,
            switch: Gtk.Entry,
            gparam: GObject.GParamSpec
    ) -> None:
        self.available_motors = [
            m.motor for m in self.motor_controllers if m.manual_motor_control == False
        ]

    def pol_comp(
            self
    ) -> bool:
        if not self.get_enable_compensation():
            return True
        pol_compensation.pol_comp(
            motor_list=self.available_motors,
            motor_qwp_serial_no=self.MotorWP.QWP.value,
            motor_hwp_serial_no=self.MotorWP.HWP.value,
            target_azimuth=self.target_azimuth,
            target_ellipticity=self.target_ellipticity,
            azimuth_velocities=self.get_azimuth_velocity(),
            ellipticity_velocities=self.get_ellipticity_velocity(),
            current_azimuth=self.polarimeter_box.data.azimuth,
            current_ellipticity=self.polarimeter_box.data.ellipticity
        )
        return True

class DevicesGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            set_qwp_motor_callback: typing.Callable,
            get_qwp_motor_callback: typing.Callable,
            set_hwp_motor_callback: typing.Callable,
            get_hwp_motor_callback: typing.Callable,
            set_polarimeter_callback: typing.Callable,
            get_polarimeter_callback: typing.Callable,
            set_azimuth_velocity_callback: typing.Callable,
            get_azimuth_velocity_callback: typing.Callable,
            set_ellipticity_velocity_callback: typing.Callable,
            get_ellipticity_velocity_callback: typing.Callable,
    ) -> None:
        super().__init__(title='Devices')
        self.set_qwp_motor = set_qwp_motor_callback
        self.get_qwp_motor = get_qwp_motor_callback
        self.set_hwp_motor = set_hwp_motor_callback
        self.get_hwp_motor = get_hwp_motor_callback
        self.set_polarimeter = set_polarimeter_callback
        self.get_polarimeter = get_polarimeter_callback

        self.set_azimuth_velocity = set_azimuth_velocity_callback
        self.get_azimuth_velocity = get_azimuth_velocity_callback
        self.set_ellipticity_velocity = set_ellipticity_velocity_callback
        self.get_ellipticity_velocity = get_ellipticity_velocity_callback

        qwp_motor_row = Adw.ActionRow(
            title='Azimuth',
            subtitle='QWP Motor'
        )
        self.add(child=qwp_motor_row)
        # qwp_motor_curve_button = Gtk.Button(
        #     icon_name='settings-symbolic',
        #     valign=Gtk.Align.CENTER
        # )
        # qwp_motor_curve_button.connect(
        #     'clicked',
        #     self.on_qwp_motor_settings
        # )
        # qwp_motor_row.add_suffix(
        #     widget=qwp_motor_curve_button
        # )
        qwp_motor_label = Gtk.Label(
            label=self.get_qwp_motor(),
            valign=Gtk.Align.CENTER
        )
        qwp_motor_row.add_suffix(
            widget=qwp_motor_label
        )

        hwp_motor_row = Adw.ActionRow(
            title='Ellipticity',
            subtitle='HWP Motor'
        )
        self.add(child=hwp_motor_row)
        # hwp_motor_curve_button = Gtk.Button(
        #     icon_name='settings-symbolic',
        #     valign=Gtk.Align.CENTER
        # )
        # hwp_motor_curve_button.connect(
        #     'clicked',
        #     self.on_hwp_motor_settings
        # )
        # hwp_motor_row.add_suffix(
        #     widget=hwp_motor_curve_button
        # )
        hwp_motor_label = Gtk.Label(
            label=self.get_hwp_motor(),
            valign=Gtk.Align.CENTER
        )
        hwp_motor_row.add_suffix(
            widget=hwp_motor_label
        )

        polarimeter_row = Adw.ActionRow(title='Polarimeter')
        self.add(child=polarimeter_row)
        polarimeter_label = Gtk.Label(
            label=self.get_polarimeter(),
            valign=Gtk.Align.CENTER
        )
        polarimeter_row.add_suffix(
            widget=polarimeter_label
        )

    def on_qwp_motor_settings(
            self,
            button: Gtk.Button
    ) -> None:
        dialog_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dialog = Gtk.Dialog(
            child=dialog_box,
            title='Acceleration Curve'
        )
        curve_box = CurveBox(
            set_angle_velocity_callback=self.set_azimuth_velocity,
            get_angle_velocity_callback=self.get_azimuth_velocity
        )
        dialog_box.append(child=curve_box)

        dialog.present()

    def on_hwp_motor_settings(
            self,
            button: Gtk.Button
    ) -> None:
        dialog_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        dialog = Gtk.Dialog(
            child=dialog_box,
            title='Acceleration Curve'
        )
        curve_box = CurveBox(
            set_angle_velocity_callback=self.set_ellipticity_velocity,
            get_angle_velocity_callback=self.get_ellipticity_velocity
        )
        dialog_box.append(child=curve_box)

        dialog.present()

class PolCompPage(Adw.PreferencesPage):
    def __init__(
            self,
            polarimeter_box: polarimeter_box.PolarimeterBox,
            motor_controllers: list[motor_box.MotorControlPage]
    ) -> None:
        super().__init__()
        self.enable_compensation = False

        self.target_azimuth = 0
        self.target_ellipticity = 0

        self.qwp_motor = None
        self.hwp_motor = None
        self.polarimeter = None

        ## thresholds (descending order)
        self.azimuth_velocity = [
            (5.0, 25.0),
            (2.5, 15.0),
            (1.0, 5.0),
            (0.075, 0.5)
        ]
        self.ellipticity_velocity = [
            (5.0, 25.0),
            (2.5, 15.0),
            (1.0, 5.0),
            (0.075, 0.5)
        ]
        # self.azimuth_velocity = [
        #     (2.5, 25.0),
        #     (1.5, 20.0),
        #     (1, 15.0),
        #     (0.5, 5.0),
        #     (0.1, 1.0),
        #     (0.05, 0.5)
        # ]

        # self.ellipticity_velocity = [
        #     (5.0, 25.0),
        #     (3.5, 20.0),
        #     (2.5, 15.0),
        #     (1.0, 5.0),
        #     (0.1, 1.0),
        #     (0.075, 0.5)
        # ]

        self.control_group = ControlGroup(
            polarimeter_box=polarimeter_box,
            motor_controllers=motor_controllers,
            set_enable_compensation_callback=self.set_enable_compensation,
            get_enable_compensation_callback=self.get_enable_compensation,
            set_target_azimuth_callback=self.set_target_azimuth,
            get_target_azimuth_callback=self.get_target_azimuth,
            set_target_ellipticity_callback=self.set_target_ellipticity,
            get_target_ellipticity_callback=self.get_target_ellipticity,
            set_qwp_motor_callback=self.set_qwp_motor,
            get_qwp_motor_callback=self.get_qwp_motor,
            set_hwp_motor_callback=self.set_hwp_motor,
            get_hwp_motor_callback=self.get_hwp_motor,
            set_polarimeter_callback=self.set_polarimeter,
            get_polarimeter_callback=self.get_polarimeter,
            set_azimuth_velocity_callback=self.set_azimuth_velocity,
            get_azimuth_velocity_callback=self.get_azimuth_velocity,
            set_ellipticity_velocity_callback=self.set_ellipticity_velocity,
            get_ellipticity_velocity_callback=self.get_ellipticity_velocity,
        )
        self.add(group=self.control_group)

        self.devices_group = DevicesGroup(
            set_qwp_motor_callback=self.set_qwp_motor,
            get_qwp_motor_callback=self.get_qwp_motor,
            set_hwp_motor_callback=self.set_hwp_motor,
            get_hwp_motor_callback=self.get_hwp_motor,
            set_polarimeter_callback=self.set_polarimeter,
            get_polarimeter_callback=self.get_polarimeter,
            set_azimuth_velocity_callback=self.set_azimuth_velocity,
            get_azimuth_velocity_callback=self.get_azimuth_velocity,
            set_ellipticity_velocity_callback=self.set_ellipticity_velocity,
            get_ellipticity_velocity_callback=self.get_ellipticity_velocity,
        )
        self.add(group=self.devices_group)

    def set_enable_compensation(self, value: bool) -> None:
        self.enable_compensation = value

    def get_enable_compensation(self) -> bool:
        return self.enable_compensation
    
    def set_target_azimuth(self, value: float) -> None:
        self.target_azimuth = value

    def get_target_azimuth(self) -> float:
        return self.target_azimuth
    
    def set_target_ellipticity(self, value: float) -> None:
        self.target_ellipticity = value

    def get_target_ellipticity(self) -> float:
        return self.target_ellipticity
    
    def set_qwp_motor(self, value: str) -> None:
        self.qwp_motor = value

    def get_qwp_motor(self) -> str:
        return self.qwp_motor
    
    def set_hwp_motor(self, value: str) -> None:
        self.hwp_motor = value

    def get_hwp_motor(self) -> str:
        return self.hwp_motor
    
    def set_polarimeter(self, value: str) -> None:
        self.polarimeter = value

    def get_polarimeter(self) -> str:
        return self.polarimeter
    
    def set_azimuth_velocity(self, value: list[tuple]) -> None:
        self.azimuth_velocity = value

    def get_azimuth_velocity(self) -> list[tuple]:
        return self.azimuth_velocity
    
    def set_ellipticity_velocity(self, value: list[tuple]) -> None:
        self.ellipticity_velocity = value

    def get_ellipticity_velocity(self) -> list[tuple]:
        return self.ellipticity_velocity

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
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
        self.polarimeter_box = polarimeter_box.PolarimeterBox()
        self.content_box.append(child=self.polarimeter_box)

        ### init motor control boxes
        self.motors = thorlabs_motor.list_motors()
        self.motor_controllers: list[motor_box.MotorControlPage] = []
        for i, m in enumerate(self.motors):
            self.motor_controllers.append(
                motor_box.MotorControlPage(
                    motor=thorlabs_motor.Motor(
                        serial_number=m.get_device_info().serial_no
                    )
                )
            )

        ### pol comp
        self.pol_comp_page = PolCompPage(
            polarimeter_box=self.polarimeter_box,
            motor_controllers=self.motor_controllers
        )
        self.content_box.append(child=self.pol_comp_page)

        ### add motor boxes
        for i, m in enumerate(self.motor_controllers):
            self.content_box.append(
                child=self.motor_controllers[i]
            )

    def on_close_request(self, window: Adw.ApplicationWindow) -> bool:
        self.polarimeter_box.polarimeter.disconnect()
        for i in self.motor_controllers:
            i.motor_controls_group.motor._motor.stop()
        return False
    
class App(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        self.win = MainWindow(application=app)
        self.win.present()

if __name__ == '__main__':
    app = App(application_id='com.github.FarisRedza.PolarisationCompensation')
    try:
        app.run(sys.argv)
    except Exception as e:
        app.win.polarimeter_box.polarimeter.disconnect()
        print('App crashed with an exception:', e)