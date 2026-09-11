import asyncio
import datetime
import inspect
import unittest
from unittest import mock

import pytz

from src.app import Application, AircraftWorker, SunWorker, WindTempWorker


class WorkerConfigurationTests(unittest.TestCase):
    def test_worker_signatures_only_require_used_configuration(self):
        self.assertEqual(
            list(inspect.signature(WindTempWorker).parameters),
            ['latitude', 'longitude', 'interval'],
        )
        self.assertEqual(
            list(inspect.signature(SunWorker).parameters),
            ['latitude', 'longitude', 'tz'],
        )
        self.assertEqual(
            list(inspect.signature(AircraftWorker).parameters),
            ['screen', 'interval'],
        )

    def test_workers_build_existing_uris(self):
        timezone = pytz.timezone('America/Los_Angeles')

        wind_worker = WindTempWorker(47.12345, -122.98765, 60)
        sun_worker = SunWorker(47.12345, -122.98765, timezone)

        self.assertEqual(
            wind_worker.uri,
            'https://www.markschulze.net/winds/winds_openmeteo.php'
            '?lat=47.1234&lon=-122.9877&hourOffset=0',
        )
        self.assertEqual(
            sun_worker.uri,
            'https://api.sunrise-sunset.org/json'
            '?lat=47.1234&lng=-122.9877&formatted=0&tzid=America%2FLos_Angeles',
        )
        self.assertFalse(hasattr(wind_worker, 'screens'))
        self.assertFalse(hasattr(wind_worker, 'tz'))
        self.assertFalse(hasattr(sun_worker, 'screens'))


class WindTempTimestampTests(unittest.TestCase):
    def test_worker_stores_update_timestamp_in_utc(self):
        worker = WindTempWorker(47.0, -122.0, 0)

        async def request_json(uri):
            worker.stop_event.set()
            return {'direction': {}, 'speed': {}, 'temp': {}}

        worker.request_json = request_json
        asyncio.run(worker.run())

        update_time = worker.data[3]
        self.assertEqual(update_time.tzinfo, datetime.timezone.utc)
        self.assertEqual(update_time.utcoffset(), datetime.timedelta())

    def test_application_converts_update_timestamp_for_display(self):
        update_time = datetime.datetime(2026, 1, 15, 12, tzinfo=datetime.timezone.utc)
        aviation_screen = mock.Mock()
        imperial_screen = mock.Mock()
        application = mock.Mock(
            wind_temp_worker=mock.Mock(data=({}, {}, {}, update_time)),
            wind_temp_aviation=aviation_screen,
            wind_temp_imperial=imperial_screen,
            tz=pytz.timezone('America/Los_Angeles'),
            wt_update_interval=60000,
        )

        Application.update_wt(application)

        displayed_time = update_time.astimezone(application.tz)
        aviation_screen.update.assert_called_once_with({}, {}, {}, displayed_time)
        imperial_screen.update.assert_called_once_with({}, {}, {}, displayed_time)
        application.master.after.assert_called_once_with(60000, application.update_wt)


if __name__ == '__main__':
    unittest.main()
