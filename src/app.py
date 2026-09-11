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


class AsyncWorker:
    def __init__(self, name):
        self.stop_event = threading.Event()
        self.loop = None
        self.tasks = ()
        self.thread = threading.Thread(target=self._run, name=name, daemon=True)

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
        self.tasks = (loop.create_task(self.run()),)
        try:
            loop.run_until_complete(asyncio.gather(*self.tasks))
        except asyncio.CancelledError:
            pass
        finally:
            self.tasks = ()
            loop.close()
            self.loop = None

    async def request_json(self, uri):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: requests.get(uri, timeout=10).json())

class WindTempWorker(AsyncWorker):
    URI = 'https://www.markschulze.net/winds/winds_openmeteo.php'

    def __init__(self, latitude, longitude, interval):
        super().__init__('wind-temp-worker')
        self.uri = self.URI + '?' + urllib.parse.urlencode((
            ('lat', '%.4f' % latitude), ('lon', '%.4f' % longitude), ('hourOffset', '0')
        ))
        self.interval = interval
        self.data = None

    async def run(self):
        while not self.stop_event.is_set():
            try:
                log.info('update_wt fetching data ...')
                result = await self.request_json(self.uri)
                self.data = (
                    dict(result["direction"]), dict(result["speed"]), dict(result["temp"]),
                    datetime.datetime.now(datetime.timezone.utc)
                )
                log.info('Fetching data success')
            except (requests.exceptions.RequestException, ValueError, TypeError, KeyError) as err:
                log.info('Fetching data failure %r', err)
            await asyncio.sleep(self.interval)


class SunWorker(AsyncWorker):
    URI = 'https://api.sunrise-sunset.org/json'

    def __init__(self, latitude, longitude, tz):
        super().__init__('sun-worker')
        self.uri = self.URI + '?' + urllib.parse.urlencode((
            ('lat', '%.4f' % latitude), ('lng', '%.4f' % longitude),
            ('formatted', '0'), ('tzid', tz.zone)
        ))
        self.tz = tz
        self.data = None

    async def run(self):
        while not self.stop_event.is_set():
            try:
                log.info('Fetching data ...')
                result = await self.request_json(self.uri)
                if result.get('status') == 'OK':
                    self.data = (
                        datetime.datetime.fromisoformat(result['results']['sunrise']),
                        datetime.datetime.fromisoformat(result['results']['sunset'])
                    )
                    log.info('Fetching data success')
                    delay = int((datetime.datetime.now(self.tz) +
                                 dateutil.relativedelta.relativedelta(
                                     days=1, hour=0, minute=0, second=0
                                 ) - datetime.datetime.now(self.tz)).total_seconds())
                else:
                    delay = 60
            except (requests.exceptions.RequestException, ValueError, TypeError, KeyError, AttributeError) as err:
                log.info('Fetching data failure %r', err)
                delay = 60
            await asyncio.sleep(delay)


class AircraftWorker(AsyncWorker):
    def __init__(self, screen, interval):
        super().__init__('aircraft-worker')
        self.screen = screen
        self.interval = interval
        self.history = {
            registration: deque([None] * 10, maxlen=10)
            for registration, _ in screen.aircraft
        } if screen is not None else {}
        self.data = {}

    @staticmethod
    def parse_data(result):
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

    async def run(self):
        while not self.stop_event.is_set():
            if self.screen is not None:
                registrations = ','.join(registration for registration, _ in self.screen.aircraft)
                uri = 'https://opendata.adsb.fi/api/v2/registration/' + urllib.parse.quote(
                    registrations, safe=','
                )
                try:
                    response = await asyncio.get_running_loop().run_in_executor(
                        None, lambda: requests.get(uri, timeout=10)
                    )
                    response.raise_for_status()
                    result = response.json()
                    records = result.get('ac', result.get('aircraft', []))
                    self.data = {
                        record.get('r'): self.parse_data({'ac': [record]})
                        for record in records
                        if isinstance(record, dict) and record.get('r') in self.history
                    }
                except (requests.exceptions.RequestException, ValueError, TypeError, KeyError, AttributeError) as err:
                    log.info('Aircraft update failed: %s', err)
            await asyncio.sleep(self.interval)


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
        self.wind_temp_worker = WindTempWorker(latitude, longitude, self.wt_update_interval / 1000)
        self.sun_worker = SunWorker(latitude, longitude, self.tz)
        self.aircraft_worker = AircraftWorker(self.aircraft_screen, self.aircraft_update_interval / 1000)
        log.info('WT uri: ' + self.wind_temp_worker.uri)
        log.info('Sun uri: ' + self.sun_worker.uri)
        self.workers = (self.wind_temp_worker, self.sun_worker, self.aircraft_worker)
        for worker in self.workers:
            worker.start()
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
        for worker in self.workers:
            worker.stop()
        self.master.destroy()
        log.info("quit exit")

    def update_wt(self):
        if self.wind_temp_worker.data is not None:
            directions, speeds, temps, update_time = self.wind_temp_worker.data
            update_time = update_time.astimezone(self.tz)
            for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                screen.update(directions, speeds, temps, update_time)
        self.master.after(self.wt_update_interval, self.update_wt)

    def update_sun(self):
        if self.sun_worker.data is not None:
            sunrise, sunset = self.sun_worker.data
            for screen in (self.wind_temp_aviation, self.wind_temp_imperial):
                screen.update_sun(sunrise, sunset)
        self.master.after(60000, self.update_sun)

    def update_aircraft(self):
        if self.aircraft_screen is not None:
            self.aircraft_screen.update(
                self.aircraft_worker.data, self.aircraft_worker.history, datetime.datetime.now(self.tz)
            )
        self.master.after(self.aircraft_update_interval, self.update_aircraft)

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
