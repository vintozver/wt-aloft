import tkinter as tk
import tkinter.font as tk_font
import requests
import time
import math
import logging
import datetime
import dateutil
import json
import pytz
import urllib.parse
from collections import deque


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

    def __init__(self,
        latitude: float, longitude: float,
        font_title: int, font_stuff: int,
        altitudes: list[int],
        wt_update_interval: int, state_switch_interval: int,
        aircraft: list[tuple[str, str]], master=None
    ):
        self.FONT_TITLE = font_title
        self.FONT_STUFF = font_stuff
        self.WIND_ARROW_SZ = font_stuff * 0.75
        self.ALTITUDES = altitudes
        self.tz = pytz.timezone('America/Los_Angeles')
        self.wt_update_interval = wt_update_interval * 1000
        self.state_switch_interval = state_switch_interval * 1000
        self.aircraft_update_interval = 10000
        self.aircraft = aircraft
        self.aircraft_history = {
            registration: deque([None] * 10, maxlen=10)
            for registration, _ in aircraft
        }

        self.wt_uri = urllib.parse.urlunsplit((
            'https', 'www.markschulze.net', '/winds/winds_openmeteo.php',
            urllib.parse.urlencode((('lat', '%.4f' % latitude), ('lon', '%.4f' % longitude), ('hourOffset', '0'))),
            ''
            ))
        self.sun_uri = urllib.parse.urlunsplit((
            'https', 'api.sunrise-sunset.org', '/json',
            urllib.parse.urlencode((('lat', '%.4f' % latitude), ('lng', '%.4f' % longitude), ('formatted', '0'), ('tzid', self.tz.zone))),
            ''
        ))
        log.info('WT uri: ' + self.wt_uri)
        log.info('Sun uri: ' + self.sun_uri)


        super().__init__(master, background=self.background_color)

        self.shutdown_event = False

        for state in (self.STATE_MAIN, self.STATE_ALTERNATE):
            for alt in self.ALTITUDES:
                self.create_vars(state, alt)

        self.state = -1

        self.master = master
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.create_widgets()

        self.master.after(0, self.check)
        self.master.after(0, self.update_wt)
        self.master.after(0, self.update_sun)
        self.master.after(0, self.update_aircraft)
        self.master.after(0, self.invoke_switch_windows)

    def check(self):
        self.master.after(100, self.check)

    def create_vars(self, state: int, alt: int):
        v_wind_spd = tk.StringVar()
        setattr(self, 'v_%d_%dk_wind_spd' % (state, alt), v_wind_spd)
        v_wind_spd.set('?%dWS' % alt)
        v_wind_dir = tk.StringVar()
        setattr(self, 'v_%d_%dk_wind_dir' % (state, alt), v_wind_dir)
        v_wind_dir.set('?%dWD' % alt)
        v_temp = tk.StringVar()
        setattr(self, 'v_%d_%dk_temp' % (state, alt), v_temp)
        v_temp.set('?%dT' % alt)

    def create_line(self, frame_main, state: int, alt: int):
        # alt is thousands of feet without 'k' suffix

        if alt > 0:
            alt_str = '%d ft' % (alt * 1000)
        else:
            alt_str = 'ground'

        frame = tk.Frame(frame_main, background=self.background_color)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame_in = tk.Frame(frame, background=self.background_color)
        frame_in.place(anchor=tk.CENTER, relx=.5, rely=.5)

        frame_label = tk.Label(frame_in, width=8, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text=alt_str
        )
        frame_label.pack(side=tk.LEFT)

        canvas_wind_dir = tk.Canvas(frame_in, width=32, height=32, background=self.background_color,
            highlightthickness=0, borderwidth=0
        )
        canvas_wind_dir.pack(side=tk.LEFT)
        setattr(self, 'v_%d_%dk_wind_dir_arrow' % (state, alt), canvas_wind_dir)

        label_wind_dir = tk.Label(frame_in, width=7, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%d_%dk_wind_dir' % (state, alt)),
        )
        label_wind_dir.pack(side=tk.LEFT)
        label_wind_spd = tk.Label(frame_in, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%d_%dk_wind_spd' % (state, alt)),
        )
        label_wind_spd.pack(side=tk.LEFT)
        label_temp = tk.Label(frame_in, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%d_%dk_temp' % (state, alt)),
        )
        label_temp.pack(side=tk.LEFT)

    @staticmethod
    def format_temperature(temperature: int, state: int) -> str:
        if state == Application.STATE_ALTERNATE:
            return '%d °F' % round(temperature * 9 / 5 + 32)
        return '%d °C' % temperature

    @staticmethod
    def format_wind_speed(speed: int, state: int) -> str:
        if state == Application.STATE_ALTERNATE:
            return '%dmph' % round(speed * 1.15078)
        return '%dkts' % speed

    @staticmethod
    def format_time(value: datetime.datetime, state: int) -> str:
        if state == Application.STATE_ALTERNATE:
            formatted_time = value.strftime('%I:%M %p')
            return formatted_time[1:] if formatted_time.startswith('0') else formatted_time
        return value.strftime('%H:%M')

    def update_line(self, state: int, alt: int, directions: dict, speeds: dict, temps: dict):
        k = '%d' % (alt * 1000)
        wind_dir = directions[k]
        getattr(self, 'v_%d_%dk_wind_dir' % (state, alt)).set('%d°' % wind_dir)
        getattr(self, 'v_%d_%dk_wind_spd' % (state, alt)).set(self.format_wind_speed(speeds[k], state))
        getattr(self, 'v_%d_%dk_temp' % (state, alt)).set(self.format_temperature(temps[k], state))
        wind_canvas = getattr(self, 'v_%d_%dk_wind_dir_arrow' % (state, alt))
        wind_canvas.delete(tk.ALL)
        sina = math.sin(math.radians(wind_dir))
        cosa = math.cos(math.radians(wind_dir))
        wind_canvas.create_line(
            self.WIND_ARROW_SZ * (1.0 - sina),
            self.WIND_ARROW_SZ * (1.0 + cosa),
            self.WIND_ARROW_SZ * (1.0 + sina),
            self.WIND_ARROW_SZ * (1.0 - cosa),
            arrow=tk.FIRST,
            fill=self.text_color
        )

    def create_widgets(self):
        self.frames = {}
        self.create_main_page()
        self.create_alternate_page()
        self.create_aircraft_page()

    def create_page(self, state: int, title: str, create):
        frame_main = tk.Frame(self, background=self.background_color)
        self.frames[state] = frame_main
        top_label = tk.Label(
            frame_main,
            padx=5,
            pady=5,
            justify=tk.CENTER,
            background=self.background_color,
            foreground=self.header_color,
            font=tk_font.Font(size=self.FONT_TITLE),
            text=title
        )
        top_label.pack(side=tk.TOP, fill=tk.X)
        create(frame_main, state)

    def create_main_page(self):
        self.create_page(self.STATE_MAIN, 'Winds and Temps aloft', self.create_winds_page)

    def create_alternate_page(self):
        self.create_page(self.STATE_ALTERNATE, 'Winds and Temps aloft', self.create_winds_page)

    def create_aircraft_page(self):
        frame_main = tk.Frame(self, background=self.background_color)
        self.frames[self.STATE_AIRCRAFT] = frame_main
        top_label = tk.Label(
            frame_main, padx=5, pady=5, justify=tk.CENTER,
            background=self.background_color, foreground=self.header_color,
            font=tk_font.Font(size=self.FONT_TITLE), text='Aircraft statuses'
        )
        top_label.pack(side=tk.TOP, fill=tk.X)
        self.create_aircraft_widgets(frame_main)

    def create_winds_page(self, frame_main, state):
        frame_titles = tk.Frame(frame_main, background=self.background_color)
        frame_titles.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame_titles_in = tk.Frame(frame_titles)
        frame_titles_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        frame_titles_empty = tk.Label(frame_titles_in, width=8, padx=5, pady=5, anchor=tk.NE, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='altitude'
        )
        frame_titles_empty.pack(side=tk.LEFT)
        frame_titles_wind_dir = tk.Label(frame_titles_in, width=9, padx=5, pady=5, anchor=tk.NE, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='wind from'
        )
        frame_titles_wind_dir.pack(side=tk.LEFT)
        frame_titles_wind_speed = tk.Label(frame_titles_in, width=6, padx=5, pady=5, anchor=tk.NE, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='speed'
        )
        frame_titles_wind_speed.pack(side=tk.LEFT)
        frame_titles_temp = tk.Label(frame_titles_in, width=5, padx=5, pady=5, anchor=tk.NE, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='temp'
        )
        frame_titles_temp.pack()

        for alt in self.ALTITUDES:
            self.create_line(frame_main, state, alt)

        v_upd = tk.StringVar()
        setattr(self, 'v_%d_upd' % state, v_upd)
        v_upd.set('- ? -')

        frame_upd = tk.Frame(frame_main, background=self.background_color)
        frame_upd.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame_upd_in = tk.Frame(frame_upd)
        frame_upd_in.place(anchor=tk.CENTER, relx=.5, rely=.5)

        frame_upd_label = tk.Label(frame_upd_in, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='⇄'
        )
        frame_upd_label.pack(side=tk.LEFT)
        label_upd = tk.Label(frame_upd_in, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground='yellow', font=tk_font.Font(size=int(self.FONT_STUFF)),
            textvariable=v_upd,
        )
        label_upd.pack(side=tk.LEFT)

        v_sun_up = tk.StringVar()
        setattr(self, 'v_%d_sun_up' % state, v_sun_up)
        v_sun_up.set("UU:UU")
        v_sun_down = tk.StringVar()
        setattr(self, 'v_%d_sun_down' % state, v_sun_down)
        v_sun_down.set("DD:DD")
        frame_sun_up_label = tk.Label(frame_upd_in, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='☼↑'
        )
        frame_sun_up_label.pack(side=tk.LEFT)
        frame_sun_up_value = tk.Label(frame_upd_in, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=v_sun_up
        )
        frame_sun_up_value.pack(side=tk.LEFT)
        frame_sun_down_label = tk.Label(frame_upd_in, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='☼↓'
        )
        frame_sun_down_label.pack(side=tk.LEFT)
        frame_sun_down_value = tk.Label(frame_upd_in, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=v_sun_down
        )
        frame_sun_down_value.pack(side=tk.LEFT)

    def create_aircraft_widgets(self, frame_main):
        frame_titles = tk.Frame(frame_main, background=self.background_color)
        frame_titles.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame_titles_in = tk.Frame(frame_titles)
        frame_titles_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        for title, width in (('aircraft', 12), ('altitude', 10), ('speed', 8), ('status', 8)):
            label = tk.Label(
                frame_titles_in, width=width, padx=5, pady=5, anchor=tk.NE,
                justify=tk.LEFT, background=self.background_color,
                foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
                text=title
            )
            label.pack(side=tk.LEFT)

        self.aircraft_vars = {}
        for registration, alias in self.aircraft:
            variables = [tk.StringVar(value='N/A') for _ in range(4)]
            self.aircraft_vars[registration] = variables
            frame = tk.Frame(frame_main, background=self.background_color)
            frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            frame_in = tk.Frame(frame)
            frame_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
            for variable, width in zip(variables, (12, 10, 8, 8)):
                label = tk.Label(
                    frame_in, width=width, padx=5, pady=5, anchor=tk.E,
                    justify=tk.LEFT, background=self.background_color,
                    foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
                    textvariable=variable
                )
                label.pack(side=tk.LEFT)
            variables[0].set(alias)

        v_upd = tk.StringVar(value='- ? -')
        self.aircraft_update_label = v_upd
        frame_upd = tk.Frame(frame_main, background=self.background_color)
        frame_upd.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame_upd_in = tk.Frame(frame_upd)
        frame_upd_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        tk.Label(
            frame_upd_in, padx=5, pady=5, background=self.background_color,
            foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='⇄'
        ).pack(side=tk.LEFT)
        tk.Label(
            frame_upd_in, padx=5, pady=5, background=self.background_color,
            foreground='yellow', font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=v_upd
        ).pack(side=tk.LEFT)


    def invoke_switch_windows(self):
        if self.shutdown_event:
            log.warning("switch_windows invoked but shutdown is requested. noop, return")
            return

        for frame in self.frames.values():
            frame.pack_forget()
        self.state = (self.state + 1) % self._STATE_DELIMITER
        self.frames[self.state].pack(side=tk.TOP, fill=tk.BOTH, expand=True)
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
                http_content = requests.get(self.wt_uri, timeout=10).content
                log.info('Fetching data success')
            except requests.exceptions.RequestException as err:
                log.info('Fetching data failure', repr(err))
                return

            try:
                result = json.loads(http_content)
            except json.decoder.JSONDecodeError:
                log.warning('WT data not decoded | %s' % http_content)
                return
        finally:
            if result is not None:
                log.info('updating widgets')
                update_time = datetime.datetime.now(self.tz)
                for state in (self.STATE_MAIN, self.STATE_ALTERNATE):
                    for alt in self.ALTITUDES:
                        self.update_line(state, alt, result["direction"], result["speed"], result["temp"])
                    getattr(self, 'v_%d_upd' % state).set(
                        update_time.strftime('%Y-%m-%d ') + self.format_time(update_time, state)
                    )
            else:
                log.info('not updating widgets (result is None)')

            # next update - regardless of the error
            self.master.after(self.wt_update_interval, self.update_wt)

    def update_sun(self):
        result = None
        try:
            log.info('Fetching data ...')
            try:
                http_content = requests.get(self.sun_uri, timeout=10).content
                log.info('Fetching data success')
            except requests.exceptions.RequestException as err:
                log.info('Fetching data failure', repr(err))
                return

            try:
                result = json.loads(http_content)
            except json.decoder.JSONDecodeError:
                log.warning('WT data not decoded | %s' % http_content)
                return
        finally:
            if result is not None:
                if result.get('status') == 'OK':
                    sunrise = datetime.datetime.fromisoformat(result['results']['sunrise'])
                    sunset = datetime.datetime.fromisoformat(result['results']['sunset'])
                    log.info('updating widgets')
                    for state in (self.STATE_MAIN, self.STATE_ALTERNATE):
                        getattr(self, 'v_%d_sun_up' % state).set(self.format_time(sunrise, state))
                        getattr(self, 'v_%d_sun_down' % state).set(self.format_time(sunset, state))

                    # updating once per day in the beginning of the day in the current timezone
                    dt = datetime.datetime.now(self.tz)
                    next_upd = int((dt + dateutil.relativedelta.relativedelta(days=1, hour=0, minute=0, second=0) - dt).total_seconds())
                    log.info('update_sun scheduling next update in %d seconds' % next_upd)
                    self.master.after(next_upd * 1000, self.update_sun)
                    return
                else:
                    log.warning('not updating widgets (status is not OK)')
            else:
                log.info('not updating widgets (result is None)')

            # failure to update - retry
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
        if altitude is None or speed is None:
            return None
        if isinstance(altitude, str) or isinstance(speed, str):
            return None
        if vertical_rate is None:
            status = '—'
        elif vertical_rate > 0:
            status = '↑'
        elif vertical_rate < 0:
            status = '↓'
        else:
            status = '—'
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

        for registration, alias in self.aircraft:
            value = values_by_registration.get(registration)
            self.aircraft_history[registration].append(value)
            if registration not in self.aircraft_vars:
                continue
            current = next((item for item in reversed(self.aircraft_history[registration]) if item is not None), None)
            values = self.aircraft_vars[registration]
            values[0].set(alias)
            if current is None:
                values[1].set('N/A')
                values[2].set('N/A')
                values[3].set('N/A')
            else:
                for variable, item in zip(values[1:], current):
                    variable.set(item)

        self.aircraft_update_label.set(
            datetime.datetime.now(self.tz).strftime('%Y-%m-%d %H:%M')
        )
        self.master.after(self.aircraft_update_interval, self.update_aircraft)

    def mainloop(self):
        super(Application, self).mainloop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    import argparse

    def parse_aircraft(value: str) -> tuple[str, str]:
        parts = [item.strip() for item in value.split(',', 1)]
        if len(parts) != 2 or not all(parts):
            raise argparse.ArgumentTypeError(
                'aircraft must be specified as REGISTRATION,ALIAS'
            )
        return parts[0], parts[1]

    parser = argparse.ArgumentParser(prog='wt_aloft')
    parser.add_argument('--geometry', type=str, help='Geometry to set initially. Fixes the bug with the slow hosts.')
    parser.add_argument('--font-title', type=int, default=85, help='Title font size')
    parser.add_argument('--font-stuff', type=int, default=65, help='Stuff font size')
    parser.add_argument('--latitude', type=float, required=True, help='GPS latitude in degrees (decimal with dot)')
    parser.add_argument('--longitude', type=float, required=True, help='GPS longitude in degrees (decimal with dot)')
    parser.add_argument('--altitudes',
        type=lambda val: [int(item.strip()) for item in val.split(",")],
        default='15,12,9,6,3,0',
        help='Comma separated list of altitudes in thousands of feet each'
    )
    parser.add_argument('--wt-update-interval', type=int, default=60, help='WindsTemps update interval (seconds)')
    parser.add_argument('--state-switch-interval', type=int, default=30, help='Display state switch interval (seconds)')
    parser.add_argument(
        '--aircraft', action='append', type=parse_aircraft, default=[],
        metavar='REGISTRATION,ALIAS',
        help='Aircraft registration and display alias; may be repeated'
    )
    args = parser.parse_args()

    root = tk.Tk()
    if args.geometry is not None:
        root.geometry(args.geometry)
    root.after(0, lambda: root.attributes('-fullscreen', True))
    app = Application(
        args.latitude, args.longitude,
        args.font_title, args.font_stuff, args.altitudes,
        args.wt_update_interval, args.state_switch_interval,
        args.aircraft,
        master=root
    )
    log.setLevel(logging.DEBUG)
    log.critical("Entering application mainloop")
    app.mainloop()
    log.critical("Exiting application mainloop")
