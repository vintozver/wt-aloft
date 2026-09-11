import asyncio
import datetime
import logging
import threading
import urllib.parse
from collections import deque

import dateutil
import requests


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

    def notify(self):
        pass

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
                self.notify()
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
                    self.notify()
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
    URI = 'https://opendata.adsb.fi/api/v2/registration/'

    def __init__(self, registrations, interval):
        registrations = list(registrations)
        if not registrations:
            raise ValueError('aircraft registrations must not be empty')
        super().__init__('aircraft-worker')
        self.registrations = registrations
        self.uri = self.URI + urllib.parse.quote(','.join(self.registrations), safe=',')
        self.interval = interval
        self.history = {
            registration: deque([None] * 10, maxlen=10)
            for registration in self.registrations
        }
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
            try:
                response = await asyncio.get_running_loop().run_in_executor(
                    None, lambda: requests.get(self.uri, timeout=10)
                )
                response.raise_for_status()
                result = response.json()
                records = result.get('ac', result.get('aircraft', []))
                self.data = {
                    record.get('r'): self.parse_data({'ac': [record]})
                    for record in records
                    if isinstance(record, dict) and record.get('r') in self.history
                }
                self.notify()
            except (requests.exceptions.RequestException, ValueError, TypeError, KeyError, AttributeError) as err:
                log.info('Aircraft update failed: %s', err)
            await asyncio.sleep(self.interval)
