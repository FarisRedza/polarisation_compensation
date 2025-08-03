import os
import sys

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
import numpy

sys.path.append(os.environ['TTAG'])
import ttag

from . import timetagger

class ChannelCounter(Gtk.Box):
    def __init__(self, label: str) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        channel_label = Gtk.Label(label=label)
        self.append(child=channel_label)

        self.channel_counts_label = Gtk.Label()
        self.channel_counts_label.set_halign(align=Gtk.Align.END)
        self.channel_counts_label.set_hexpand(expand=True)
        self.channel_counts_label.set_markup(
            f'<span font_desc="Monospace 40">{0}</span>'
        )
        self.append(child=self.channel_counts_label)

    def update_counts(self, value: int) -> None:
        self.channel_counts_label.set_markup(
            f'<span font_desc="Monospace 40">{value}</span>'
        )

class ChannelScale(Gtk.Box):
    def __init__(
            self,
            label: str,
            max_channel: int,
            default_value: int = 1
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        channel_label = Gtk.Label(label=label)
        self.append(child=channel_label)

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
        self.append(child=self.scale)

class SettingsScale(Gtk.Box):
    def __init__(
            self,
            label_string: str,
            min: int,
            max: int,
            default_value: int = 0
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
            digits=0,
            draw_value=True,
            hexpand=True,
        )
        self.scale.set_range(
            min=min,
            max=max
        )
        self.scale.set_value(value=default_value)
        self.append(child=self.scale)

        self.max_entry = Gtk.Entry(
            valign=Gtk.Align.CENTER,
            max_length=5,
            max_width_chars=5,
            text=str(max)
        )
        # self.max_entry.connect('activate', self.on_update_window_range)
        self.append(child=self.max_entry)

class Settings(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        window_scale = SettingsScale(
            label_string='Window (ns)',
            min=0,
            max=2000
        )
        self.append(child=window_scale)

        delay_scale = SettingsScale(
            label_string='Delay (ns)',
            min=-1000,
            max=1000
        )
        self.append(child=delay_scale)

        refresh_rate_scale = SettingsScale(
            label_string='Refresh Rate (s)',
            min=0,
            max=1000,
            default_value=500
        )
        self.append(child=refresh_rate_scale)   


class SimpleDisplay(Gtk.ScrolledWindow):
    def __init__(self) -> None:
        super().__init__(vexpand=True)
        self.set_policy(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC
        )
        simpleDisplayBox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        simpleDisplayBox.set_margin_top(margin=20)
        simpleDisplayBox.set_margin_bottom(margin=20)
        simpleDisplayBox.set_margin_start(margin=20)
        simpleDisplayBox.set_margin_end(margin=20)
        self.set_child(simpleDisplayBox)

        self.channel_a_counter = ChannelCounter(label='Channel A')
        simpleDisplayBox.append(child=self.channel_a_counter)

        self.channel_b_counter = ChannelCounter(label='Channel B')
        simpleDisplayBox.append(child=self.channel_b_counter)

        self.coincidence_counter = ChannelCounter(label='Coincidences')
        simpleDisplayBox.append(child=self.coincidence_counter)

        self.efficiency = ChannelCounter(label='Efficiency')
        simpleDisplayBox.append(child=self.efficiency)

        self.channel_a_scale = ChannelScale(
            label='Channel A',
            max_channel=8
        )
        simpleDisplayBox.append(child=self.channel_a_scale)

        self.channel_b_scale = ChannelScale(
            label='Channel B',
            max_channel=8,
            default_value=2
        )
        simpleDisplayBox.append(child=self.channel_b_scale)

        simpleDisplayBox.append(child=Settings())

    def update_counts(self, raw_data: timetagger.RawData) -> None:
        singles = numpy.bincount(raw_data.channels, minlength=8)
        self.channel_a_counter.update_counts(
            value=singles[int(self.channel_a_scale.scale.get_value() - 1)]
        )
        self.channel_b_counter.update_counts(
            value=singles[int(self.channel_b_scale.scale.get_value() - 1)]
        )