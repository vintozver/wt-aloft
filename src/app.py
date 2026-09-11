import datetime
import logging
import tkinter as tk

import pytz

from .aircraft import Aircraft
from .wind_temp_aviation import WindTempAviation
from .wind_temp_imperial import WindTempImperial
from .workers import AircraftWorker, SunWorker, WindTempWorker


log = logging.getLogger(__name__)


class Application(tk.Frame):
    STATE_MAIN = 0
    STATE_ALTERNATE = 1
    STATE_AIRCRAFT = 2
    _STATE_DELIMITER = 3

    WIND_TEMP_UPDATED = '<<WindTempUpdated>>'
    SUN_UPDATED = '<<SunUpdated>>'
    AIRCRAFT_UPDATED = '<<AircraftUpdated>>'

    background_color = 'black'
    text_color = 'white'
    header_color = 'red'
    label_color = 'green'

    def __init__(
        self, latitude, longitude, font_title, font_stuff, altitudes,
        wt_update_interval, state_switch_interval, aircraft, master=None
    ):
        super().__init__(master, background=self.background_color)
        self.tz = pytz.timezone('America/Los_Angeles')
        self.state_switch_interval = state_switch_interval * 1000
        self.aircraft_update_interval = 10000
        self.shutdown_event = False
        self.state = -1
        self.master = master
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.wind_temp_aviation = WindTempAviation(font_title, font_stuff, altitudes, self)
        self.wind_temp_imperial = WindTempImperial(font_title, font_stuff, altitudes, self)
        self.screens = [self.wind_temp_aviation, self.wind_temp_imperial]
        self.aircraft_screen = None
        self.aircraft_worker = None
        if aircraft:
            self.aircraft_screen = Aircraft(font_title, font_stuff, aircraft, self)
            self.screens.append(self.aircraft_screen)
            self.aircraft_worker = AircraftWorker(
                [registration for registration, _ in aircraft],
                self.aircraft_update_interval / 1000
            )
        self._state_delimiter = len(self.screens)
        for screen in self.screens:
            screen.pack_forget()
        self.wind_temp_worker = WindTempWorker(latitude, longitude, wt_update_interval)
        self.sun_worker = SunWorker(latitude, longitude, self.tz)
        log.info('WT uri: ' + self.wind_temp_worker.uri)
        log.info('Sun uri: ' + self.sun_worker.uri)
        self.workers = (self.wind_temp_worker, self.sun_worker)
        if self.aircraft_worker is not None:
            self.workers += (self.aircraft_worker,)
        self.bind(self.WIND_TEMP_UPDATED, self.update_wt)
        self.bind(self.SUN_UPDATED, self.update_sun)
        if self.aircraft_worker is not None:
            self.bind(self.AIRCRAFT_UPDATED, self.update_aircraft)
        self.wind_temp_worker.notify = lambda: self.notify(self.WIND_TEMP_UPDATED)
        self.sun_worker.notify = lambda: self.notify(self.SUN_UPDATED)
        if self.aircraft_worker is not None:
            self.aircraft_worker.notify = lambda: self.notify(self.AIRCRAFT_UPDATED)
        for worker in self.workers:
            worker.start()
        self.master.after(0, self.invoke_switch_windows)

    def notify(self, event):
        if not self.shutdown_event:
            try:
                self.event_generate(event, when='tail')
            except tk.TclError:
                pass

    def invoke_switch_windows(self):
        if self.shutdown_event:
            log.warning("switch_windows invoked but shutdown is requested. noop, return")
            return
        for screen in self.screens:
            screen.pack_forget()
        self.state = (self.state + 1) % self._state_delimiter
        self.screens[self.state].pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.master.after(self.state_switch_interval, self.invoke_switch_windows)

    def invoke_quit(self):
        log.info("quit enter")
        self.shutdown_event = True
        for worker in self.workers:
            worker.stop()
        self.master.destroy()
        log.info("quit exit")

    def update_wt(self, _event=None):
        if self.wind_temp_worker.data is not None:
            directions, speeds, temps, update_time = self.wind_temp_worker.data
            update_time = update_time.astimezone(self.tz)
            for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                screen.update(directions, speeds, temps, update_time)

    def update_sun(self, _event=None):
        if self.sun_worker.data is not None:
            sunrise, sunset = self.sun_worker.data
            for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                screen.update_sun(sunrise, sunset)

    def update_aircraft(self, _event=None):
        if self.aircraft_screen is not None:
            self.aircraft_screen.update(
                self.aircraft_worker.data, self.aircraft_worker.history, datetime.datetime.now(self.tz)
            )

    def mainloop(self):
        try:
            super(Application, self).mainloop()
        finally:
            for worker in self.workers:
                worker.stop()
            for worker in self.workers:
                worker.thread.join()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    import argparse

    def parse_aircraft(value):
        parts = [item.strip() for item in value.split(',', 1)]
        if len(parts) != 2 or not all(parts):
            raise argparse.ArgumentTypeError('aircraft must be specified as REGISTRATION,ALIAS')
        return parts[0], parts[1]

    parser = argparse.ArgumentParser(prog='wt_aloft')
    parser.add_argument('--geometry', type=str, help='Geometry to set initially. Fixes the bug with the slow hosts.')
    parser.add_argument('--font-title', type=int, default=85, help='Title font size')
    parser.add_argument('--font-stuff', type=int, default=65, help='Stuff font size')
    parser.add_argument('--latitude', type=float, required=True, help='GPS latitude in degrees (decimal with dot)')
    parser.add_argument('--longitude', type=float, required=True, help='GPS longitude in degrees (decimal with dot)')
    parser.add_argument('--altitudes', type=lambda val: [int(item.strip()) for item in val.split(",")],
                        default='15,12,9,6,3,0', help='Comma separated list of altitudes in thousands of feet each')
    parser.add_argument('--wt-update-interval', type=int, default=60, help='WindsTemps update interval (seconds)')
    parser.add_argument('--state-switch-interval', type=int, default=30, help='Display state switch interval (seconds)')
    parser.add_argument('--aircraft', action='append', type=parse_aircraft, default=[],
                        metavar='REGISTRATION,ALIAS', help='Aircraft registration and display alias; may be repeated')
    args = parser.parse_args()
    root = tk.Tk()
    if args.geometry is not None:
        root.geometry(args.geometry)
    root.after(0, lambda: root.attributes('-fullscreen', True))
    app = Application(args.latitude, args.longitude, args.font_title, args.font_stuff, args.altitudes,
                      args.wt_update_interval, args.state_switch_interval, args.aircraft, master=root)
    log.setLevel(logging.DEBUG)
    log.critical("Entering application mainloop")
    app.mainloop()
    log.critical("Exiting application mainloop")
