import asyncio
import tkinter as tk
import requests
import logging
import datetime
import dateutil
import pytz
import urllib.parse
import threading
from collections import deque

from .aircraft import Aircraft
from .wind_temp_aviation import WindTempAviation
from .wind_temp_imperial import WindTempImperial


log = logging.getLogger(__name__)


class UpdateWorkers:
    def __init__(self, app):
        self.app = app
        self.stop_event = threading.Event()
        self.loop = None
        self.tasks = ()
        self.thread = threading.Thread(target=self._run, name='update-workers', daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._cancel_tasks)

    def _cancel_tasks(self):
        for task in self.tasks:
            task.cancel()

    def _run(self):
        loop = asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        self.tasks = (
            loop.create_task(self._update_wt()),
            loop.create_task(self._update_sun()),
            loop.create_task(self._update_aircraft()),
        )
        try:
            loop.run_until_complete(asyncio.gather(*self.tasks))
        except asyncio.CancelledError:
            pass
        finally:
            self.tasks = ()
            loop.close()
            self.loop = None

    async def _request_json(self, uri):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: requests.get(uri, timeout=10).json())

    async def _update_wt(self):
        while not self.stop_event.is_set():
            try:
                log.info('update_wt fetching data ...')
                result = await self._request_json(self.app.wt_uri)
                self.app.wt_data = (
                    dict(result["direction"]), dict(result["speed"]), dict(result["temp"]),
                    datetime.datetime.now(self.app.tz)
                )
                log.info('Fetching data success')
            except (requests.exceptions.RequestException, ValueError, TypeError, KeyError) as err:
                log.info('Fetching data failure %r', err)
            await asyncio.sleep(self.app.wt_update_interval / 1000)

    async def _update_sun(self):
        while not self.stop_event.is_set():
            try:
                log.info('Fetching data ...')
                result = await self._request_json(self.app.sun_uri)
                if result.get('status') == 'OK':
                    self.app.sun_data = (
                        datetime.datetime.fromisoformat(result['results']['sunrise']),
                        datetime.datetime.fromisoformat(result['results']['sunset'])
                    )
                    log.info('Fetching data success')
                    delay = int((datetime.datetime.now(self.app.tz) +
                                 dateutil.relativedelta.relativedelta(
                                     days=1, hour=0, minute=0, second=0
                                 ) - datetime.datetime.now(self.app.tz)).total_seconds())
                else:
                    delay = 60
            except (requests.exceptions.RequestException, ValueError, TypeError, KeyError, AttributeError) as err:
                log.info('Fetching data failure %r', err)
                delay = 60
            await asyncio.sleep(delay)

    async def _update_aircraft(self):
        while not self.stop_event.is_set():
            if self.app.aircraft:
                registrations = ','.join(registration for registration, _ in self.app.aircraft)
                uri = 'https://opendata.adsb.fi/api/v2/registration/' + urllib.parse.quote(
                    registrations, safe=','
                )
                try:
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(
                        None, lambda: requests.get(uri, timeout=10)
                    )
                    response.raise_for_status()
                    result = response.json()
                    records = result.get('ac', result.get('aircraft', []))
                    self.app.aircraft_data = {
                        record.get('r'): self.app.parse_aircraft_data({'ac': [record]})
                        for record in records
                        if isinstance(record, dict) and record.get('r') in self.app.aircraft_history
                    }
                except (requests.exceptions.RequestException, ValueError, TypeError, KeyError, AttributeError) as err:
                    log.info('Aircraft update failed: %s', err)
            await asyncio.sleep(self.app.aircraft_update_interval / 1000)


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
        self.wt_data = None
        self.sun_data = None
        self.aircraft_data = {}
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
        self.update_workers = UpdateWorkers(self)
        self.update_workers.start()
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
        self.update_workers.stop()
        self.master.destroy()
        log.info("quit exit")

    def update_wt(self):
        if self.wt_data is not None:
            directions, speeds, temps, update_time = self.wt_data
            for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                screen.update(directions, speeds, temps, update_time)
        self.master.after(self.wt_update_interval, self.update_wt)

    def update_sun(self):
        if self.sun_data is not None:
            sunrise, sunset = self.sun_data
            for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                screen.update_sun(sunrise, sunset)
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
        if self.aircraft_screen is not None:
            self.aircraft_screen.update(
                self.aircraft_data, self.aircraft_history, datetime.datetime.now(self.tz)
            )
        self.master.after(self.aircraft_update_interval, self.update_aircraft)

    def mainloop(self):
        try:
            super(Application, self).mainloop()
        finally:
            self.update_workers.stop()
            self.update_workers.thread.join()


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
