import typing

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw, GLib, Gio

class ChannelRow(Adw.ActionRow):
    def __init__(
            self,
            title: str,
            set_channel_number_callback: typing.Callable
    ) -> None:
        super().__init__(title=title)
        channel_number_entry = Gtk.Entry(
            placeholder_text='Enter channel number',
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        channel_number_entry.connect(
            'changed',
            self.on_set_channel_number,
            set_channel_number_callback
        )
        self.add_suffix(widget=channel_number_entry)

    def on_set_channel_number(
            self,
            entry: Gtk.Entry,
            set_pattern_callback: typing.Callable
    ) -> None:
        channel = self.get_title()
        input = entry.get_text()
        if input.isdigit():
            set_pattern_callback(channel=channel, number=int(input))
        elif input == '':
            set_pattern_callback(channel=channel, number=None)
        else:
            pass


class ChannelGroup(Adw.PreferencesGroup):
    def __init__(self, title: str) -> None:
        super().__init__(title=title)
        self.channels: dict[str, int | None] = {
            'H': None,
            'V': None,
            'D': None,
            'A': None,
            'R': None,
            'L': None,
        }

        h_row = ChannelRow(
            title='H',
            set_channel_number_callback=self.set_channel_number
        )
        self.add(child=h_row)

        v_row = ChannelRow(
            title='V',
            set_channel_number_callback=self.set_channel_number
        )
        self.add(child=v_row)

        d_row = ChannelRow(
            title='D',
            set_channel_number_callback=self.set_channel_number
        )
        self.add(child=d_row)

        a_row = ChannelRow(
            title='A',
            set_channel_number_callback=self.set_channel_number
        )
        self.add(child=a_row)

        r_row = ChannelRow(
            title='R',
            set_channel_number_callback=self.set_channel_number
        )
        self.add(child=r_row)

        l_row = ChannelRow(
            title='L',
            set_channel_number_callback=self.set_channel_number
        )
        self.add(child=l_row)

    def set_channel_number(self, channel: str, number: int | None) -> None:
        self.channels[channel] = number

class AddChannelGroup(Adw.PreferencesGroup):
    def __init__(self, add_pattern_callback: typing.Callable) -> None:
        super().__init__()
        self.group_title = 'Group'

        add_group_row = Adw.ActionRow(
            title='Add channel group'
        )
        self.add(child=add_group_row)

        add_group_entry = Gtk.Entry(
            placeholder_text='Group',
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        add_group_entry.connect('changed', self.on_set_group_title)
        add_group_row.add_suffix(widget=add_group_entry)

        add_group_button = Gtk.Button(
            icon_name='list-add-symbolic',
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        add_group_button.connect(
            'clicked',
            self.on_add_group,
            add_pattern_callback
        )
        add_group_row.add_suffix(widget=add_group_button)

    def on_set_group_title(self, entry: Gtk.Entry) -> None:
        self.group_title = entry.get_text()

    def on_add_group(
            self,
            button: Gtk.Button,
            add_pattern_callback: typing.Callable
    ) -> None:
        add_pattern_callback(title=self.group_title)

class ChannelsPage(Adw.PreferencesPage):
    def __init__(
            self,
            name: str
    ) -> None:
        super().__init__(name=name)

        self.add_channel_group = AddChannelGroup(
            add_pattern_callback=self.add_channels
        )
        self.add(group=self.add_channel_group)

    def add_channels(self, title: str) -> None:
        self.remove(group=self.add_channel_group)
        self.add(group=ChannelGroup(title=title))
        self.add_channel_group = AddChannelGroup(
            add_pattern_callback=self.add_channels
        )
        self.add(group=self.add_channel_group)
