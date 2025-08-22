import typing

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

import numpy as np

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

class ChannelScale(Adw.ActionRow):
    def __init__(
            self,
            title: str,
            max_channel: int,
            default_value: int = 1
    ) -> None:
        super().__init__(title=title)

        self.scale = Gtk.Scale(
            digits=0,
            draw_value=True,
            value_pos=Gtk.PositionType.LEFT,
            hexpand=True,
        )
        self.scale.set_range(
            min=1,
            max=max_channel
        )
        self.scale.set_value(value=default_value)
        self.scale.set_size_request(
            width=170,
            height=-1
        )
        for i in range(1, max_channel + 1):
            self.scale.add_mark(
                value=i,
                position=Gtk.PositionType.BOTTOM
            )
        self.add_suffix(widget=self.scale)

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

class CountsGroup(Adw.PreferencesGroup):
    def __init__(self) -> None:
        super().__init__()
        counter_size = 40

        counts_row = Adw.ActionRow()
        self.add(child=counts_row)

        margin = 6
        counts_box = Gtk.Box(
            margin_top=margin,
            margin_bottom=margin,
            margin_start=margin,
            margin_end=margin,
            orientation=Gtk.Orientation.VERTICAL
        )
        counts_row.set_child(child=counts_box)

        self.channel_a_counter = Counter(
            label='Channel A',
            counter_size=counter_size
        )
        counts_box.append(child=self.channel_a_counter)

        self.channel_b_counter = Counter(
            label='Channel B',
            counter_size=counter_size
        )
        counts_box.append(child=self.channel_b_counter)

        self.coincidence_counter = Counter(
            label='Coincidences',
            counter_size=counter_size
        )
        counts_box.append(child=self.coincidence_counter)

        self.efficiency = Counter(
            label='Efficiency',
            counter_size=counter_size
        )
        counts_box.append(child=self.efficiency)

        channel_a_row = Adw.ActionRow()
        self.channel_a_scale = ChannelScale(
            title='Channel A',
            max_channel=8
        )
        channel_a_row.set_child(child=self.channel_a_scale)
        self.add(child=channel_a_row)

        channel_b_row = Adw.ActionRow()
        self.channel_b_scale = ChannelScale(
            title='Channel B',
            max_channel=8,
            default_value=2
        )
        channel_b_row.set_child(child=self.channel_b_scale)
        self.add(child=channel_b_row)

    def update_data(self, data: timetagger.Data) -> None:
        channel_a_counts = int(self.channel_a_scale.scale.get_value() - 1)
        channel_b_counts = int(self.channel_b_scale.scale.get_value() - 1)

        if len(data.singles) > 0:
            self.channel_a_counter.update_counts(
                value=data.singles[channel_a_counts]
            )
            self.channel_b_counter.update_counts(
                value=data.singles[channel_b_counts]
            )

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

class SimpleDisplay(Gtk.ScrolledWindow):
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

        self.counts_group = CountsGroup()
        main_box.append(child=self.counts_group)

        self.settings_group = SettingsGroup(
            set_window_callback=self.set_window,
            get_window_callback=self.get_window,
            set_delay_callback=self.set_delay,
            get_delay_callback=self.get_delay,
            set_refresh_rate_callback=self.set_refresh_rate,
            get_refresh_rate_callback=self.get_refresh_rate
        )
        main_box.append(child=self.settings_group)

        self._timeout_id = GLib.timeout_add(
            self.refresh_rate,
            self.update_counts
        )

    def update_counts(self) -> bool:
        if self.get_page_callback() == self.get_name():
            data: timetagger.Data = self.get_data_callback()
            self.counts_group.update_data(data=data)
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
            self.update_counts
        )

    def get_refresh_rate(self) -> int:
        return self.refresh_rate