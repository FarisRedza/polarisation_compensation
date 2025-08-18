import os
import sys
import typing

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw, GLib

import numpy as np

from . import timetagger

class Counter(Gtk.Box):
    def __init__(self, label: str, counter_size: int | float = 40) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.counter_size = counter_size
        channel_label = Gtk.Label(label=label)
        self.append(child=channel_label)

        self.channel_counts_label = Gtk.Label()
        self.channel_counts_label.set_halign(align=Gtk.Align.END)
        self.channel_counts_label.set_hexpand(expand=True)
        self.channel_counts_label.set_markup(
            f'<span font_desc="Monospace {counter_size}">{0}</span>'
        )
        self.append(child=self.channel_counts_label)

    def update_counts(self, value: int | float) -> None:
        match value:
            case int() | np.int64():
                self.channel_counts_label.set_markup(
                    f'<span font_desc="Monospace {self.counter_size}">{value}</span>'
                )
            case float():
                self.channel_counts_label.set_markup(
                    f'<span font_desc="Monospace {self.counter_size}">{value:.2f}</span>'
                )
            case _:
                raise RuntimeError(f'Invalid value type: {type(value)}')

class SinglesGroup(Adw.PreferencesGroup):
    def __init__(self, channels: int) -> None:
        super().__init__(title='Singles')

        row = Adw.ActionRow()
        self.add(child=row)

        margin = 6
        box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            orientation=Gtk.Orientation.HORIZONTAL
        )
        row.set_child(child=box)

        left_box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            orientation=Gtk.Orientation.VERTICAL
        )
        box.append(child=left_box)
        box.append(child=Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        right_box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            orientation=Gtk.Orientation.VERTICAL
        )
        box.append(child=right_box)

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

    def update_counts(self, data: timetagger.Data) -> None:
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

    def update_counts(self, data: timetagger.Data) -> None:
        self.s1_counter.update_counts(value=data.normalised_s1)
        self.s2_counter.update_counts(value=data.normalised_s2)
        self.s3_counter.update_counts(value=data.normalised_s3)

        self.qber_counter.update_counts(value=data.qber)
        self.qx_counter.update_counts(value=data.qx)

class MeasurementBox(Gtk.Box):
    def __init__(self, channels: int) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.singles_group = SinglesGroup(channels=channels)
        self.append(child=self.singles_group)

        self.measurement_info_group = MeasurementInfoGroup()
        self.append(child=self.measurement_info_group)

    def update_data(self, data: timetagger.Data) -> None:
        self.singles_group.update_counts(data=data)
        self.measurement_info_group.update_counts(data=data)

class SettingsScale(Gtk.Box):
    def __init__(
            self,
            label_string: str,
            min: float,
            max: float,
            set_value_callback: typing.Callable,
            default_value: float = 0,
            digits: int = 0
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(
            label=label_string,
            width_chars=7,
            wrap=True,
            justify=Gtk.Justification.CENTER
        )
        self.append(child=label)

        self.min_entry = Gtk.Entry(
            valign=Gtk.Align.CENTER,
            max_length=5,
            max_width_chars=5,
            text=str(min)
        )
        # self.min_entry.connect('activate', self.on_update_window_range)
        self.append(child=self.min_entry)

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
        self.append(child=self.scale)

        self.max_entry = Gtk.Entry(
            valign=Gtk.Align.CENTER,
            max_length=5,
            max_width_chars=5,
            text=str(max)
        )
        # self.max_entry.connect('activate', self.on_update_window_range)
        self.append(child=self.max_entry)

    def on_set_value(
            self,
            scale: Gtk.Scale,
            set_value_callback: typing.Callable
    ) -> None:
        set_value_callback(value=int(scale.get_value()))

class Settings(Gtk.Box):
    def __init__(
            self,
            set_window_callback: typing.Callable,
            get_window_callback: typing.Callable,
            set_refresh_rate_callback: typing.Callable,
            get_refresh_rate_callback: typing.Callable,
            set_delay_callback: typing.Callable,
            get_delay_callback: typing.Callable
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        window_scale = SettingsScale(
            label_string='Window (ns)',
            min=1,
            max=2000,
            default_value=get_window_callback(),
            set_value_callback=set_window_callback
        )
        self.append(child=window_scale)

        delay_scale = SettingsScale(
            label_string='Delay (ns)',
            min=-1000,
            max=1000,
            default_value=get_delay_callback(),
            set_value_callback=set_delay_callback
        )
        self.append(child=delay_scale)

        refresh_rate_scale = SettingsScale(
            label_string='Refresh Rate (ms)',
            min=1,
            max=500,
            default_value=get_refresh_rate_callback(),
            # digits=3,
            set_value_callback=set_refresh_rate_callback
        )
        self.append(child=refresh_rate_scale)

class Display(Gtk.ScrolledWindow):
    def __init__(
            self,
            get_data_callback: typing.Callable
    ) -> None:
        super().__init__(vexpand=True)
        self.get_data_callback = get_data_callback

        self.set_policy(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC
        )
        self.counter_size = 40
        self.window = 1
        self.delay = 0
        self.refresh_rate = 250
    

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_margin_top(margin=20)
        main_box.set_margin_bottom(margin=20)
        main_box.set_margin_start(margin=20)
        main_box.set_margin_end(margin=20)
        self.set_child(main_box)

        self.measurement_box = MeasurementBox(channels=8)
        main_box.append(child=self.measurement_box)

        self.settings_box = Settings(
            set_window_callback=self.set_window,
            get_window_callback=self.get_window,
            set_delay_callback=self.set_delay,
            get_delay_callback=self.get_delay,
            set_refresh_rate_callback=self.set_refresh_rate,
            get_refresh_rate_callback=self.get_refresh_rate
        )
        main_box.append(child=self.settings_box)

        # self.singles_group = SinglesGroup(channels=8)
        # displayBox.append(child=self.singles_group)

        # self.measurement_info_group = MeasurementInfoGroup()
        # displayBox.append(child=self.measurement_info_group)

        # displayBox.append(
        #     child=Settings(
        #         set_window_callback=self.set_window,
        #         get_window_callback=self.get_window,
        #         set_delay_callback=self.set_delay,
        #         get_delay_callback=self.get_delay,
        #         set_refresh_rate_callback=self.set_refresh_rate,
        #         get_refresh_rate_callback=self.get_refresh_rate
        #     )
        # )

        self._timeout_id = GLib.timeout_add(
            self.refresh_rate,
            self.update_data,
            self.get_data_callback
        )

    def update_data(
            self,
            get_data_callback: typing.Callable
    ) -> bool:
        data: timetagger.Data = get_data_callback()
        self.measurement_box.update_data(data=data)
        # self.singles_group.update_counts(data=data)
        # self.measurement_info_group.update_counts(data=data)
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
            self.update_data,
            self.get_data_callback
        )

    def get_refresh_rate(self) -> int:
        return self.refresh_rate