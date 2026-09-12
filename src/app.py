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
    WIND_TEMP_UPDATED = '<<WindTempUpdated>>'
    SUN_UPDATED = '<<SunUpdated>>'
    AIRCRAFT_UPDATED = '<<AircraftUpdated>>'

    background_color = 'black'
    text_color = 'white'
    header_color = 'red'
    label_color = 'green'

    def __init__(
        self, screens, font_title, font_stuff, screen_switch_interval=30,
        wt_altitudes=None, latitude=None, longitude=None, wt_update_interval=60, aircraft=None,
        aircraft_update_interval=10, master=None
    ):
        super().__init__(master, background=self.background_color)
        self.tz = pytz.timezone('America/Los_Angeles')
        self.screen_switch_interval = screen_switch_interval * 1000
        self.shutdown_event = False
        self.current_screen = None
        self.screen_index = -1
        self.master = master
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.wind_temp_aviation = None
        self.wind_temp_imperial = None
        if any(name in screens for name in ('wt_aviation', 'wt_imperial')):
            if latitude is None or longitude is None:
                raise ValueError('latitude and longitude are required for wind-temperature screens')
            if wt_altitudes is None:
                wt_altitudes = [15, 12, 9, 6, 3, 0]
            if 'wt_aviation' in screens:
                self.wind_temp_aviation = WindTempAviation(font_title, font_stuff, wt_altitudes, self)
            if 'wt_imperial' in screens:
                self.wind_temp_imperial = WindTempImperial(font_title, font_stuff, wt_altitudes, self)
        screen_map = {
            name: screen for name, screen in (
                ('wt_aviation', self.wind_temp_aviation),
                ('wt_imperial', self.wind_temp_imperial),
            ) if screen is not None
        }
        self.aircraft_screen = None
        self.aircraft_worker = None
        if 'aircraft' in screens:
            if not aircraft:
                raise ValueError('aircraft screen requires aircraft options')
            self.aircraft_screen = Aircraft(font_title, font_stuff, aircraft, self)
            screen_map['aircraft'] = self.aircraft_screen
            self.aircraft_worker = AircraftWorker(
                [registration for registration, _ in aircraft],
                aircraft_update_interval
            )
        try:
            self.screens = [screen_map[name] for name in screens]
        except KeyError as err:
            raise ValueError('unknown screen: %s' % err.args[0]) from err
        if not self.screens:
            raise ValueError('at least one screen is required')
        for screen in self.screens:
            screen.pack_forget()
        self.wind_temp_worker = None
        self.sun_worker = None
        self.workers = ()
        if self.wind_temp_aviation is not None or self.wind_temp_imperial is not None:
            self.wind_temp_worker = WindTempWorker(latitude, longitude, wt_update_interval)
            self.sun_worker = SunWorker(latitude, longitude, self.tz)
            log.info('WT uri: ' + self.wind_temp_worker.uri)
            log.info('Sun uri: ' + self.sun_worker.uri)
            self.workers = (self.wind_temp_worker, self.sun_worker)
        if self.aircraft_worker is not None:
            self.workers += (self.aircraft_worker,)
        if self.wind_temp_worker is not None:
            self.bind(self.WIND_TEMP_UPDATED, self.update_wt)
            self.bind(self.SUN_UPDATED, self.update_sun)
        if self.aircraft_worker is not None:
            self.bind(self.AIRCRAFT_UPDATED, self.update_aircraft)
        if self.wind_temp_worker is not None:
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
        self.screen_index = (self.screen_index + 1) % len(self.screens)
        self.current_screen = self.screens[self.screen_index]
        self.current_screen.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        if len(self.screens) > 1:
            self.master.after(self.screen_switch_interval, self.invoke_switch_windows)

    def invoke_quit(self):
        log.info("quit enter")
        self.shutdown_event = True
        for worker in self.workers:
            worker.stop()
        self.master.destroy()
        log.info("quit exit")

    def update_wt(self, _event=None):
        if self.wind_temp_worker is not None and self.wind_temp_worker.data is not None:
            directions, speeds, temps, update_time = self.wind_temp_worker.data
            update_time = update_time.astimezone(self.tz)
            for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                if screen is not None:
                    screen.update(directions, speeds, temps, update_time)

    def update_sun(self, _event=None):
        if self.sun_worker is not None and self.sun_worker.data is not None:
            sunrise, sunset = self.sun_worker.data
            for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                if screen is not None:
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
    parser.add_argument('--font-title', type=int, required=True, help='Title font size')
    parser.add_argument('--font-stuff', type=int, required=True, help='Stuff font size')
    parser.add_argument('--latitude', type=float, help='GPS latitude in degrees (decimal with dot)')
    parser.add_argument('--longitude', type=float, help='GPS longitude in degrees (decimal with dot)')
    parser.add_argument('--wt-altitudes', type=lambda val: [int(item.strip()) for item in val.split(",")],
                        help='Comma separated list of altitudes in thousands of feet each')
    parser.add_argument('--wt-update-interval', type=int, default=60, help='WindsTemps update interval (seconds)')
    parser.add_argument('--screen-switch-interval', type=int, default=30,
                        help='Display screen switch interval (seconds)')
    parser.add_argument('--aircraft-update-interval', type=int, default=10,
                        help='Aircraft update interval in seconds')
    parser.add_argument('--aircraft', action='append', type=parse_aircraft, default=[],
                        metavar='REGISTRATION,ALIAS', help='Aircraft registration and display alias; may be repeated')
    parser.add_argument('--screens', action='append',
                        choices=('wt_aviation', 'wt_imperial', 'aircraft'),
                        default=None,
                        help='Screen to display; may be repeated')
    args = parser.parse_args()
    if args.screens is None:
        args.screens = ['wt_aviation', 'wt_imperial']
    root = tk.Tk()
    if args.geometry is not None:
        root.geometry(args.geometry)
    root.after(0, lambda: root.attributes('-fullscreen', True))
    app = Application(
        args.screens, args.font_title, args.font_stuff,
        screen_switch_interval=args.screen_switch_interval,
        wt_altitudes=args.wt_altitudes, latitude=args.latitude, longitude=args.longitude,
        wt_update_interval=args.wt_update_interval, aircraft=args.aircraft,
        aircraft_update_interval=args.aircraft_update_interval, master=root
    )
    log.setLevel(logging.DEBUG)
    log.critical("Entering application mainloop")
    app.mainloop()
    log.critical("Exiting application mainloop")
