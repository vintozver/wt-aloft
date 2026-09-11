import tkinter as tk
import tkinter.font as tk_font
import requests
import math
import logging
import datetime
import dateutil
import pytz
import urllib.parse
from collections import deque


log = logging.getLogger(__name__)


class WindTempAviation(tk.Frame):
    background_color = 'black'
    text_color = 'white'
    header_color = 'red'
    label_color = 'green'
    title = 'Winds and Temps aloft'

    def __init__(self, font_title, font_stuff, altitudes, master=None):
        super().__init__(master, background=self.background_color)
        self.FONT_TITLE = font_title
        self.FONT_STUFF = font_stuff
        self.WIND_ARROW_SZ = font_stuff / 2
        self.ALTITUDES = altitudes
        self._create_vars()
        self._create_widgets()

    def _create_vars(self):
        self.wind_vars = {}
        for alt in self.ALTITUDES:
            self.wind_vars[alt] = tuple(tk.StringVar(value=value) for value in (
                '?%dWD' % alt, '?%dWS' % alt, '?%dT' % alt
            ))
        self.update_var = tk.StringVar(value='- ? -')
        self.sun_up_var = tk.StringVar(value='UU:UU')
        self.sun_down_var = tk.StringVar(value='DD:DD')

    def _create_widgets(self):
        tk.Label(
            self, padx=5, pady=5, justify=tk.CENTER,
            background=self.background_color, foreground=self.header_color,
            font=tk_font.Font(size=self.FONT_TITLE),
            text=self.title
        ).pack(side=tk.TOP, fill=tk.X)

        titles = tk.Frame(self, background=self.background_color)
        titles.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        titles_in = tk.Frame(titles)
        titles_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        for title, width in (('altitude', 8), ('wind from', 9), ('speed', 6), ('temp', 5)):
            tk.Label(
                titles_in, width=width, padx=5, pady=5, anchor=tk.NE,
                justify=tk.LEFT, background=self.background_color,
                foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
                text=title
            ).pack(side=tk.LEFT)

        for alt in self.ALTITUDES:
            self._create_line(alt)

        update = tk.Frame(self, background=self.background_color)
        update.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        update_in = tk.Frame(update)
        update_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        tk.Label(
            update_in, padx=5, pady=5, background=self.background_color,
            foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF), text='⇄'
        ).pack(side=tk.LEFT)
        tk.Label(
            update_in, padx=5, pady=5, background=self.background_color,
            foreground='yellow', font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=self.update_var
        ).pack(side=tk.LEFT)
        for label, variable in (('☼↑', self.sun_up_var), ('☼↓', self.sun_down_var)):
            tk.Label(
                update_in, padx=5, pady=5, background=self.background_color,
                foreground=self.label_color if label == '☼↑' else self.text_color,
                font=tk_font.Font(size=self.FONT_STUFF), text=label
            ).pack(side=tk.LEFT)
            tk.Label(
                update_in, padx=5, pady=5, background=self.background_color,
                foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
                textvariable=variable
            ).pack(side=tk.LEFT)

    def _create_line(self, alt):
        alt_str = '%d ft' % (alt * 1000) if alt > 0 else 'ground'
        frame = tk.Frame(self, background=self.background_color)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame_in = tk.Frame(frame, background=self.background_color)
        frame_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        tk.Label(
            frame_in, width=8, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color,
            font=tk_font.Font(size=self.FONT_STUFF), text=alt_str
        ).pack(side=tk.LEFT)
        canvas = tk.Canvas(
            frame_in, width=self.FONT_STUFF, height=self.FONT_STUFF,
            background=self.background_color, highlightthickness=0, borderwidth=0
        )
        canvas.pack(side=tk.LEFT)
        self.wind_vars[alt] += (canvas,)
        for variable, width in zip(self.wind_vars[alt][:3], (7, 6, 5)):
            tk.Label(
                frame_in, width=width, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
                background=self.background_color, foreground=self.text_color,
                font=tk_font.Font(size=self.FONT_STUFF), textvariable=variable
            ).pack(side=tk.LEFT)

    def format_temperature(self, temperature):
        return '%d °C' % temperature

    def format_wind_speed(self, speed):
        return '%dkts' % speed

    def format_time(self, value):
        return value.strftime('%H:%M')

    def update(self, directions, speeds, temps, update_time):
        for alt in self.ALTITUDES:
            wind_dir = directions[str(alt * 1000)]
            direction, speed, temperature, canvas = self.wind_vars[alt]
            direction.set('%d°' % wind_dir)
            speed.set(self.format_wind_speed(speeds[str(alt * 1000)]))
            temperature.set(self.format_temperature(temps[str(alt * 1000)]))
            canvas.delete(tk.ALL)
            sina = math.sin(math.radians(wind_dir))
            cosa = math.cos(math.radians(wind_dir))
            canvas.create_line(
                self.WIND_ARROW_SZ * (1.0 - sina), self.WIND_ARROW_SZ * (1.0 + cosa),
                self.WIND_ARROW_SZ * (1.0 + sina), self.WIND_ARROW_SZ * (1.0 - cosa),
                arrow=tk.FIRST, fill=self.text_color
            )
        self.update_var.set(update_time.strftime('%Y-%m-%d ') + self.format_time(update_time))

    def update_sun(self, sunrise, sunset):
        self.sun_up_var.set(self.format_time(sunrise))
        self.sun_down_var.set(self.format_time(sunset))


class WindTempImperial(WindTempAviation):
    title = 'Winds and Temps aloft'

    def format_temperature(self, temperature):
        return '%d °F' % round(temperature * 9 / 5 + 32)

    def format_wind_speed(self, speed):
        return '%dmph' % round(speed * 1.15078)

    def format_time(self, value):
        formatted_time = value.strftime('%I:%M %p')
        return formatted_time[1:] if formatted_time.startswith('0') else formatted_time


class Aircraft(tk.Frame):
    background_color = 'black'
    text_color = 'white'
    header_color = 'red'
    label_color = 'green'

    def __init__(self, font_title, font_stuff, aircraft, master=None):
        super().__init__(master, background=self.background_color)
        self.FONT_TITLE = font_title
        self.FONT_STUFF = font_stuff
        self.aircraft = aircraft
        self.aircraft_vars = {}
        self._create_widgets()

    def _create_widgets(self):
        tk.Label(
            self, padx=5, pady=5, justify=tk.CENTER,
            background=self.background_color, foreground=self.header_color,
            font=tk_font.Font(size=self.FONT_TITLE), text='Aircraft statuses'
        ).pack(side=tk.TOP, fill=tk.X)
        titles = tk.Frame(self, background=self.background_color)
        titles.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        titles_in = tk.Frame(titles)
        titles_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        for title, width in (('aircraft', 8), ('altitude', 10), ('speed', 6), ('status', 6)):
            tk.Label(
                titles_in, width=width, padx=5, pady=5, anchor=tk.NE, justify=tk.LEFT,
                background=self.background_color, foreground=self.label_color,
                font=tk_font.Font(size=self.FONT_STUFF), text=title
            ).pack(side=tk.LEFT)
        for registration, alias in self.aircraft:
            variables = [tk.StringVar(value='N/A') for _ in range(4)]
            variables[0].set(alias)
            self.aircraft_vars[registration] = variables
            frame = tk.Frame(self, background=self.background_color)
            frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            frame_in = tk.Frame(frame)
            frame_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
            for variable, width in zip(variables, (8, 10, 6, 6)):
                tk.Label(
                    frame_in, width=width, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
                    background=self.background_color, foreground=self.text_color,
                    font=tk_font.Font(size=self.FONT_STUFF), textvariable=variable
                ).pack(side=tk.LEFT)
        self.update_var = tk.StringVar(value='- ? -')
        update = tk.Frame(self, background=self.background_color)
        update.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        update_in = tk.Frame(update)
        update_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        tk.Label(
            update_in, padx=5, pady=5, background=self.background_color,
            foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF), text='⇄'
        ).pack(side=tk.LEFT)
        tk.Label(
            update_in, padx=5, pady=5, background=self.background_color,
            foreground='yellow', font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=self.update_var
        ).pack(side=tk.LEFT)

    def update(self, values_by_registration, history, update_time):
        for registration, alias in self.aircraft:
            history[registration].append(values_by_registration.get(registration))
            current = next((item for item in reversed(history[registration]) if item is not None), None)
            values = self.aircraft_vars[registration]
            values[0].set(alias)
            if current is None:
                for variable in values[1:]:
                    variable.set('N/A')
            else:
                for variable, item in zip(values[1:], current):
                    variable.set(item)
        self.update_var.set(update_time.strftime('%Y-%m-%d %H:%M'))


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
        self.screens = (
            WindTempAviation(font_title, font_stuff, altitudes, self),
            WindTempImperial(font_title, font_stuff, altitudes, self),
            Aircraft(font_title, font_stuff, aircraft, self),
        )
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
        self.state = (self.state + 1) % self._STATE_DELIMITER
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
                for screen in self.screens[:2]:
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
                for screen in self.screens[:2]:
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
        self.screens[2].update(values_by_registration, self.aircraft_history, datetime.datetime.now(self.tz))
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
