import typing

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Adw

from . import timetagger

class ChannelRow(Adw.ActionRow):
    def __init__(
            self,
            title: str,
            set_channel_number_callback: typing.Callable,
            text: str | None = None
    ) -> None:
        super().__init__(title=title)
        channel_number_entry = Gtk.Entry(
            placeholder_text='Enter channel number',
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        if text and text != 'None':
            channel_number_entry.set_text(text=text)
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
    def __init__(
            self,
            channel_group: timetagger.ChannelGroup,
            remove_channel_group_callback: typing.Callable
    ) -> None:
        super().__init__(title=channel_group.name)
        self.channel_group = channel_group

        remove_button = Gtk.Button(
            icon_name='list-remove-symbolic',
            css_classes=['flat'],
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        remove_button.connect(
            'clicked',
            self.on_remove_group,
            remove_channel_group_callback
        )
        self.set_header_suffix(suffix=remove_button)

        h_row = ChannelRow(
            title='H',
            set_channel_number_callback=self.set_channel_number,
            text=str(self.channel_group.H)
        )
        self.add(child=h_row)

        v_row = ChannelRow(
            title='V',
            set_channel_number_callback=self.set_channel_number,
            text=str(self.channel_group.V)
        )
        self.add(child=v_row)

        d_row = ChannelRow(
            title='D',
            set_channel_number_callback=self.set_channel_number,
            text=str(self.channel_group.D)
        )
        self.add(child=d_row)

        a_row = ChannelRow(
            title='A',
            set_channel_number_callback=self.set_channel_number,
            text=str(self.channel_group.A)
        )
        self.add(child=a_row)

        r_row = ChannelRow(
            title='R',
            set_channel_number_callback=self.set_channel_number,
            text=str(self.channel_group.R)
        )
        self.add(child=r_row)

        l_row = ChannelRow(
            title='L',
            set_channel_number_callback=self.set_channel_number,
            text=str(self.channel_group.L)
        )
        self.add(child=l_row)

    def set_channel_number(self, channel: str, number: int | None) -> None:
        setattr(self.channel_group, channel, number)

    def on_remove_group(
            self,
            button: Gtk.Button,
            remove_channel_group_callback: typing.Callable
    ) -> None:
        remove_channel_group_callback(channel_group=self.channel_group)

class SettingsGroup(Adw.PreferencesGroup):
    def __init__(
            self,
            add_channel_group_callback: typing.Callable,
            set_channel_groups_callback: typing.Callable,
    ) -> None:
        super().__init__()
        self._group_name = 'Group'

        add_group_row = Adw.ActionRow(
            title='Add channel group'
        )
        self.add(child=add_group_row)

        add_group_entry = Gtk.Entry(
            placeholder_text='Group',
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        add_group_entry.connect('changed', self.on_set_group_name)
        add_group_row.add_suffix(widget=add_group_entry)

        add_group_button = Gtk.Button(
            icon_name='list-add-symbolic',
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER
        )
        add_group_button.connect(
            'clicked',
            self.on_add_channel_group,
            add_channel_group_callback
        )
        add_group_row.add_suffix(widget=add_group_button)

        self.set_channel_groups_row = Adw.ActionRow()
        self.add(child=self.set_channel_groups_row)
        set_channel_groups_button = Gtk.Button(
            label='Set channel groups',
            valign=Gtk.Align.CENTER
        )
        set_channel_groups_button.add_css_class(
            css_class='flat'
        )
        set_channel_groups_button.connect(
            'clicked',
            self.on_set_channel_groups,
            set_channel_groups_callback
        )
        self.set_channel_groups_row.set_child(
            child=set_channel_groups_button
        )

    def on_set_channel_groups(
            self,
            button: Gtk.Button,
            set_channel_groups_callback: typing.Callable
    ) -> None:
        set_channel_groups_callback()

    def on_set_group_name(self, entry: Gtk.Entry) -> None:
        self._group_name = entry.get_text()

    def on_add_channel_group(
            self,
            button: Gtk.Button,
            add_channel_group_callback: typing.Callable
    ) -> None:
        add_channel_group_callback(
            channel_group=timetagger.ChannelGroup(name=self._group_name)
        )
        self._group_name = 'Group'

class ChannelsPage(Adw.PreferencesPage):
    def __init__(
            self,
            name: str,
            set_channel_groups_callback: typing.Callable,
            get_channel_groups_callback: typing.Callable
    ) -> None:
        super().__init__(name=name)
        self.set_channel_groups_callback = set_channel_groups_callback

        self.channel_groups_widgets: list[ChannelGroup] = []

        for channel_group in get_channel_groups_callback():
                widget=ChannelGroup(
                    channel_group=channel_group,
                    remove_channel_group_callback=self.remove_channel_group
                )
                self.channel_groups_widgets.append(widget)
                self.add(group=widget)

        self.settings_group = SettingsGroup(
            add_channel_group_callback=self.add_channel_group,
            set_channel_groups_callback=self.set_channel_groups
        )
        self.add(group=self.settings_group)

    def add_channel_group(
            self,
            channel_group: timetagger.ChannelGroup
    ) -> None:
        widget=ChannelGroup(
            channel_group=channel_group,
            remove_channel_group_callback=self.remove_channel_group
        )
        self.channel_groups_widgets.append(widget)

        self.remove(group=self.settings_group)
        self.add(group=widget)
        self.add(group=self.settings_group)

    def remove_channel_group(
            self,
            channel_group: timetagger.ChannelGroup
    ) -> None:
        cgw = next(
            (cgw for cgw in self.channel_groups_widgets if cgw.get_title() == channel_group.name),
            None
        )
        if cgw:
            self.remove(group=cgw)
            self.channel_groups_widgets.remove(cgw)


    def set_channel_groups(self) -> None:
        channel_groups = [cg.channel_group for cg in self.channel_groups_widgets]
        self.set_channel_groups_callback(channel_groups)