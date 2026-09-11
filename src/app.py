import tkinter as tk
import requests
import logging
import datetime
import dateutil
import pytz
import urllib.parse
from collections import deque

from .aircraft import Aircraft
from .wind_temp_aviation import WindTempAviation
from .wind_temp_imperial import WindTempImperial


log = logging.getLogger(__name__)


class Application(tk.Frame):
    STATE_MAIN = 0
    STATE_ALTERNATE = 1
    STATE_AIRCRAFT = 2
    _STATE_DELIMITER = 3

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
        self.wt_update_interval = wt_update_interval * 1000
        self.state_switch_interval = state_switch_interval * 1000
        self.aircraft_update_interval = 10000
        self.aircraft = aircraft
        self.aircraft_history = {
            registration: deque([None] * 10, maxlen=10) for registration, _ in aircraft
        }
        self.wt_uri = urllib.parse.urlunsplit((
            'https', 'www.markschulze.net', '/winds/winds_openmeteo.php',
            urllib.parse.urlencode((('lat', '%.4f' % latitude), ('lon', '%.4f' % longitude), ('hourOffset', '0'))), ''
        ))
        self.sun_uri = urllib.parse.urlunsplit((
            'https', 'api.sunrise-sunset.org', '/json',
            urllib.parse.urlencode((('lat', '%.4f' % latitude), ('lng', '%.4f' % longitude),
                                    ('formatted', '0'), ('tzid', self.tz.zone))), ''
        ))
        log.info('WT uri: ' + self.wt_uri)
        log.info('Sun uri: ' + self.sun_uri)
        self.shutdown_event = False
        self.state = -1
        self.master = master
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.wind_temp_aviation = WindTempAviation(font_title, font_stuff, altitudes, self)
        self.wind_temp_imperial = WindTempImperial(font_title, font_stuff, altitudes, self)
        self.screens = [self.wind_temp_aviation, self.wind_temp_imperial]
        self.aircraft_screen = None
        if aircraft:
            self.aircraft_screen = Aircraft(font_title, font_stuff, aircraft, self)
            self.screens.append(self.aircraft_screen)
        self._state_delimiter = len(self.screens)
        for screen in self.screens:
            screen.pack_forget()
        self.master.after(0, self.check)
        self.master.after(0, self.update_wt)
        self.master.after(0, self.update_sun)
        self.master.after(0, self.update_aircraft)
        self.master.after(0, self.invoke_switch_windows)

    def check(self):
        self.master.after(100, self.check)

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
        self.master.destroy()
        log.info("quit exit")

    def update_wt(self):
        result = None
        try:
            log.info('update_wt fetching data ...')
            try:
                result = requests.get(self.wt_uri, timeout=10).json()
                log.info('Fetching data success')
            except (requests.exceptions.RequestException, ValueError) as err:
                log.info('Fetching data failure %r', err)
        finally:
            if result is not None:
                update_time = datetime.datetime.now(self.tz)
                for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                    screen.update(result["direction"], result["speed"], result["temp"], update_time)
            self.master.after(self.wt_update_interval, self.update_wt)

    def update_sun(self):
        result = None
        try:
            log.info('Fetching data ...')
            try:
                result = requests.get(self.sun_uri, timeout=10).json()
                log.info('Fetching data success')
            except (requests.exceptions.RequestException, ValueError) as err:
                log.info('Fetching data failure %r', err)
        finally:
            if result is not None and result.get('status') == 'OK':
                sunrise = datetime.datetime.fromisoformat(result['results']['sunrise'])
                sunset = datetime.datetime.fromisoformat(result['results']['sunset'])
                for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                    screen.update_sun(sunrise, sunset)
                dt = datetime.datetime.now(self.tz)
                next_upd = int((dt + dateutil.relativedelta.relativedelta(
                    days=1, hour=0, minute=0, second=0
                ) - dt).total_seconds())
                self.master.after(next_upd * 1000, self.update_sun)
                return
            self.master.after(60000, self.update_sun)

    @staticmethod
    def parse_aircraft_data(result):
        records = result.get('ac', result.get('aircraft', [])) if isinstance(result, dict) else []
        if not records or not isinstance(records[0], dict):
            return None
        data = records[0]
        altitude = data.get('alt_baro', data.get('alt_geom'))
        speed = data.get('gs')
        vertical_rate = data.get('baro_rate', data.get('geom_rate', data.get('vert_rate')))
        if altitude is None or speed is None or isinstance(altitude, str) or isinstance(speed, str):
            return None
        status = '—' if vertical_rate is None else '↑' if vertical_rate > 0 else '↓' if vertical_rate < 0 else '—'
        return '%d ft' % round(altitude), '%d kts' % round(speed), status

    def update_aircraft(self):
        if not self.aircraft:
            self.master.after(self.aircraft_update_interval, self.update_aircraft)
            return
        values_by_registration = {}
        registrations = ','.join(registration for registration, _ in self.aircraft)
        uri = 'https://opendata.adsb.fi/api/v2/registration/' + urllib.parse.quote(registrations, safe=',')
        try:
            response = requests.get(uri, timeout=10)
            response.raise_for_status()
            result = response.json()
            records = result.get('ac', result.get('aircraft', []))
            values_by_registration = {
                record.get('r'): self.parse_aircraft_data({'ac': [record]})
                for record in records
                if isinstance(record, dict) and record.get('r') in self.aircraft_history
            }
        except (requests.exceptions.RequestException, ValueError, TypeError, KeyError, AttributeError) as err:
            log.info('Aircraft update failed: %s', err)
        self.aircraft_screen.update(
            values_by_registration, self.aircraft_history, datetime.datetime.now(self.tz)
        )
        self.master.after(self.aircraft_update_interval, self.update_aircraft)

    def mainloop(self):
        super(Application, self).mainloop()


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
