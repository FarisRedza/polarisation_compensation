import sys
import os

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

from . import gui_widget
from . import uqd

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_title(title='UQD Viewer')
        self.set_default_size(width=600, height=500)
        self.set_size_request(width=450, height=150)
        self.connect("close-request", self.on_close_request)

        # main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content=main_box)

        ## header_bar
        header_bar = Adw.HeaderBar()
        main_box.append(child=header_bar)

        ### timetagger box
        try:
            self.timetagger_box = gui_widget.TimeTaggerBox(
                tt=uqd.UQD()
            )
        except:
            main_box.append(
                child=Gtk.Label(
                    label='No UQD found',
                    valign=Gtk.Align.CENTER,
                    vexpand=True
                )
            )
        else:
            main_box.append(child=self.timetagger_box)

    def on_close_request(self, window: Adw.ApplicationWindow) -> bool:
        try:
            if type(self.timetagger_box.timetagger) == uqd.UQD:
                # self.timetagger_box.timetagger._uqd.deInitialize()
                pass
        except Exception as e:
            print('Error: UQD already disconnected')
        return False

class App(Adw.Application):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app: Adw.Application):
        self.win = MainWindow(application=app)
        self.win.present()

if __name__ == '__main__':
    app = App(application_id='com.github.FarisRedza.UQDViewer')
    try:
        app.run(sys.argv)
    except Exception as e:
        if type(app.win.timetagger_box.timetagger) == uqd.UQD:
            # app.win.timetagger_box.timetagger._uqd.deInitialize()
            pass
        print('App crashed with an exception:', e)