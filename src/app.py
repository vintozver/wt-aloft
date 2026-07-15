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


log = logging.getLogger(__name__)


class Application(tk.Frame):
    STATE_MAIN = 0
    _STATE_DELIMITER = 1

    background_color = 'black'
    text_color = 'white'
    header_color = 'red'
    label_color = 'green'

    def __init__(self,
        latitude: float, longitude: float,
        font_title: int, font_stuff: int,
        altitudes: list[int],
        wt_update_interval: int, master=None
    ):
        self.FONT_TITLE = font_title
        self.FONT_STUFF = font_stuff
        self.ALTITUDES = altitudes
        self.tz = pytz.timezone('America/Los_Angeles')
        self.wt_update_interval = wt_update_interval * 1000

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

        for alt in self.ALTITUDES:
            self.create_vars(alt)

        self.state = 0

        self.master = master
        self.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.create_widgets()

        self.master.after(0, self.check)
        self.master.after(0, self.update_wt)
        self.master.after(0, self.update_sun)
        self.master.after(0, self.invoke_switch_windows)

    def check(self):
        self.master.after(100, self.check)

    def create_vars(self, alt: int):
        v_wind_spd = tk.StringVar()
        setattr(self, 'v_%dk_wind_spd' % alt, v_wind_spd)
        v_wind_spd.set('?%dWS' % alt)
        v_wind_dir = tk.StringVar()
        setattr(self, 'v_%dk_wind_dir' % alt, v_wind_dir)
        v_wind_dir.set('?%dWD' % alt)
        v_temp = tk.StringVar()
        setattr(self, 'v_%dk_temp' % alt, v_temp)
        v_temp.set('?%dT' % alt)

    def create_line(self, alt: int):
        # alt is thousands of feet without 'k' suffix

        if alt > 0:
            alt_str = '%d ft' % (alt * 1000)
        else:
            alt_str = 'ground'

        frame = tk.Frame(self.frame_main, background=self.background_color)
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
        setattr(self, 'v_%dk_wind_dir_arrow' % alt, canvas_wind_dir)

        label_wind_dir = tk.Label(frame_in, width=7, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_wind_dir' % alt),
        )
        label_wind_dir.pack(side=tk.LEFT)
        label_wind_spd = tk.Label(frame_in, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_wind_spd' % alt),
        )
        label_wind_spd.pack(side=tk.LEFT)
        label_temp = tk.Label(frame_in, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_temp' % alt),
        )
        label_temp.pack(side=tk.LEFT)

    def update_line(self, alt: int, directions: dict, speeds: dict, temps: dict):
        k = '%d' % (alt * 1000)
        wind_dir = directions[k]
        getattr(self, 'v_%dk_wind_dir' % alt).set('%d°' % wind_dir)
        getattr(self, 'v_%dk_wind_spd' % alt).set('%dkts' % speeds[k])
        getattr(self, 'v_%dk_temp' % alt).set('%d °C' % temps[k])
        wind_canvas = getattr(self, 'v_%dk_wind_dir_arrow' % alt)
        wind_canvas.delete(tk.ALL)
        sina = math.sin(math.radians(wind_dir))
        cosa = math.cos(math.radians(wind_dir))
        wind_canvas.create_line(
            16 * (1.0 - sina),
            16 * (1.0 + cosa),
            16 * (1.0 + sina),
            16 * (1.0 - cosa),
            arrow=tk.FIRST,
            fill=self.text_color
        )

    def create_widgets(self):
        self.frame_main = tk.Frame(self, background=self.background_color)
        top_label = tk.Label(
            self.frame_main,
            padx=5,
            pady=5,
            justify=tk.CENTER,
            background=self.background_color,
            foreground=self.header_color,
            font=tk_font.Font(size=self.FONT_TITLE),
            text='Winds and Temps aloft'
        )
        top_label.pack(side=tk.TOP, fill=tk.X)

        frame_titles = tk.Frame(self.frame_main, background=self.background_color)
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
            self.create_line(alt)

        self.v_upd = tk.StringVar()
        self.v_upd.set('- ? -')

        frame_upd = tk.Frame(self.frame_main, background=self.background_color)
        frame_upd.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame_upd_in = tk.Frame(frame_upd)
        frame_upd_in.place(anchor=tk.CENTER, relx=.5, rely=.5)

        frame_upd_label = tk.Label(frame_upd_in, width=1, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='⇄'
        )
        frame_upd_label.pack(side=tk.LEFT)
        label_upd = tk.Label(frame_upd_in, width=15, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground='yellow', font=tk_font.Font(size=int(self.FONT_STUFF)),
            textvariable=self.v_upd,
        )
        label_upd.pack(side=tk.LEFT)

        self.v_sun_up = tk.StringVar()
        self.v_sun_up.set("UU:UU")
        self.v_sun_down = tk.StringVar()
        self.v_sun_down.set("DD:DD")
        frame_sun_up_label = tk.Label(frame_upd_in, width=3, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='☼↑'
        )
        frame_sun_up_label.pack(side=tk.LEFT)
        frame_sun_up_value = tk.Label(frame_upd_in, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=self.v_sun_up
        )
        frame_sun_up_value.pack(side=tk.LEFT)
        frame_sun_down_label = tk.Label(frame_upd_in, width=3, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='☼↓'
        )
        frame_sun_down_label.pack(side=tk.LEFT)
        frame_sun_down_value = tk.Label(frame_upd_in, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=self.v_sun_down
        )
        frame_sun_down_value.pack(side=tk.LEFT)


    def invoke_switch_windows(self):
        if self.shutdown_event:
            log.warning("switch_windows invoked but shutdown is requested. noop, return")
            return

        self.frame_main.pack_forget()
        if self.state == self.STATE_MAIN:
            self.frame_main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        else:
            pass

        self.state = (self.state + 1) % self._STATE_DELIMITER

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
                for alt in self.ALTITUDES:
                    self.update_line(alt, result["direction"], result["speed"], result["temp"])
                self.v_upd.set(datetime.datetime.now(self.tz).strftime('%Y-%m-%d %H:%M'))
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
                    self.v_sun_up.set(sunrise.strftime('%H:%M'))
                    self.v_sun_down.set(sunset.strftime('%H:%M'))

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

    def mainloop(self):
        super(Application, self).mainloop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    import argparse
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
    args = parser.parse_args()

    root = tk.Tk()
    if args.geometry is not None:
        root.geometry(args.geometry)
    root.after(0, lambda: root.attributes('-fullscreen', True))
    app = Application(
        args.latitude, args.longitude,
        args.font_title, args.font_stuff, args.altitudes,
        args.wt_update_interval,
        master=root
    )
    log.setLevel(logging.DEBUG)
    log.critical("Entering application mainloop")
    app.mainloop()
    log.critical("Exiting application mainloop")

