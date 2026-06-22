import tkinter as tk
import tkinter.font as tk_font
import requests
import time
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

    def __init__(self, latitude: float, longitude: float, font_title: int, font_stuff: int, altitudes: list[int], master=None):
        self.FONT_TITLE = font_title
        self.FONT_STUFF = font_stuff
        self.ALTITUDES = altitudes
        self.tz = pytz.timezone('America/Los_Angeles')

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
        self.pack(side='top', fill=tk.BOTH, expand=True)

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
        frame.pack(side='top', fill=tk.X)
        frame_label = tk.Label(frame, width=8, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text=alt_str
        )
        frame_label.pack(side='left')
        label_wind_dir = tk.Label(frame, width=9, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_wind_dir' % alt),
        )
        label_wind_dir.pack(side='left')
        label_wind_spd = tk.Label(frame, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_wind_spd' % alt),
        )
        label_wind_spd.pack(side='left')
        label_temp = tk.Label(frame, width=10, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_temp' % alt),
        )
        label_temp.pack(side='left')

    def update_line(self, alt: int, directions: dict, speeds: dict, temps: dict):
        k = '%d' % (alt * 1000)
        getattr(self, 'v_%dk_wind_dir' % alt).set('%d°' % directions[k])
        getattr(self, 'v_%dk_wind_spd' % alt).set('%dkts' % speeds[k])
        getattr(self, 'v_%dk_temp' % alt).set('%d °C' % temps[k])

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
        top_label.pack(side='top', fill=tk.X)

        frame_titles = tk.Frame(self.frame_main, background=self.background_color)
        frame_titles.pack(side='top', fill=tk.X)
        frame_titles_empty = tk.Label(frame_titles, width=8, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='altitude'
        )
        frame_titles_empty.pack(side='left')
        frame_titles_wind_dir = tk.Label(frame_titles, width=9, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='wind from'
        )
        frame_titles_wind_dir.pack(side='left')
        frame_titles_wind_speed = tk.Label(frame_titles, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='speed'
        )
        frame_titles_wind_speed.pack(side='left')
        frame_titles_temp = tk.Label(frame_titles, width=10, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='temp'
        )
        frame_titles_temp.pack(side='left')

        for alt in self.ALTITUDES:
            self.create_line(alt)

        self.v_upd = tk.StringVar()
        self.v_upd.set('- ? -')
        frame_upd = tk.Frame(self.frame_main, background=self.background_color)
        frame_upd.pack(side='top', fill=tk.X)
        frame_upd_label = tk.Label(frame_upd, width=1, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='⇄'
        )
        frame_upd_label.pack(side='left')
        label_upd = tk.Label(frame_upd, width=15, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground='yellow', font=tk_font.Font(size=int(self.FONT_STUFF)),
            textvariable=self.v_upd,
        )
        label_upd.pack(side='left')

        self.v_sun_up = tk.StringVar()
        self.v_sun_up.set("UU:UU")
        self.v_sun_down = tk.StringVar()
        self.v_sun_down.set("DD:DD")
        frame_sun_up_label = tk.Label(frame_upd, width=3, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='☼↑'
        )
        frame_sun_up_label.pack(side='left')
        frame_sun_up_value = tk.Label(frame_upd, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=self.v_sun_up
        )
        frame_sun_up_value.pack(side='left')
        frame_sun_down_label = tk.Label(frame_upd, width=3, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='☼↓'
        )
        frame_sun_down_label.pack(side='left')
        frame_sun_down_value = tk.Label(frame_upd, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=self.v_sun_down
        )
        frame_sun_down_value.pack(side='left')


    def invoke_switch_windows(self):
        if self.shutdown_event:
            log.warning("switch_windows invoked but shutdown is requested. noop, return")
            return

        self.frame_main.pack_forget()
        if self.state == self.STATE_MAIN:
            self.frame_main.pack(side='top', fill=tk.BOTH, expand=True)
        else:
            pass

        self.state = (self.state + 1) % self._STATE_DELIMITER

    def invoke_quit(self):
        log.info("quit enter")
        self.shutdown_event = True
        self.master.destroy()
        log.info("quit exit")

    def update_wt(self):
        log.critical('update_wt enter')

        log.info('Fetching data ...')
        try:
            http_content = requests.get(self.wt_uri, timeout=10).content
            log.info('Fetching data success')
        except requests.exceptions.RequestException as err:
            http_content = None
            log.info('Fetching data failure', repr(err))
        if http_content is None:
            return None

        try:
            result = json.loads(http_content)
        except json.decoder.JSONDecodeError:
            log.warning('WT data not decoded | %s' % http_content)
            result = None
        if result is not None:
            log.info('updating widgets')
            directions = result["direction"]
            speeds = result["speed"]
            temps = result["temp"]
            for alt in self.ALTITUDES:
                self.update_line(alt, directions, speeds, temps)
            self.v_upd.set(datetime.datetime.now(self.tz).strftime('%Y-%m-%d %H:%M'))
        else:
            log.info('not updating widgets (result is None)')

        self.master.after(60000, self.update_wt)

        log.critical('update_wt exit')

    def update_sun(self):
        log.critical('update_sun enter')

        log.info('Fetching data ...')
        try:
            http_content = requests.get(self.sun_uri, timeout=10).content
            log.info('Fetching data success')
        except requests.exceptions.RequestException as err:
            http_content = None
            log.info('Fetching data failure', repr(err))
        if http_content is None:
            return None

        try:
            result = json.loads(http_content)
        except json.decoder.JSONDecodeError:
            log.warning('WT data not decoded | %s' % http_content)
            result = None
        if result is not None:
            if result.get('status') == 'OK':
                sunrise = datetime.datetime.fromisoformat(result['results']['sunrise'])
                sunset = datetime.datetime.fromisoformat(result['results']['sunset'])
                log.info('updating widgets')
                self.v_sun_up.set(sunrise.strftime('%H:%M'))
                self.v_sun_down.set(sunset.strftime('%H:%M'))
            else:
                log.warning('not updating widgets (status is not OK)')
        else:
            log.info('not updating widgets (result is None)')

        # updating once per day in the beginning of the day in the current timezone
        dt = datetime.datetime.now(self.tz)
        next_upd = int((dt + dateutil.relativedelta.relativedelta(days=1, hour=0, minute=0, second=0) - dt).total_seconds())
        log.info('update_sun scheduling next update in %d seconds' % next_upd)
        self.master.after(next_upd * 1000, self.update_sun)

        log.critical('update_sun exit')

    def mainloop(self):
        super(Application, self).mainloop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    import argparse
    parser = argparse.ArgumentParser(prog='wt_aloft')
    parser.add_argument('--font-title', type=int, default=85, help='Title font size')
    parser.add_argument('--font-stuff', type=int, default=65, help='Stuff font size')
    parser.add_argument('--latitude', type=float, default=46.4772, help='GPS latitude in degrees (decimal with dot)')
    parser.add_argument('--longitude', type=float, default=-122.8064, help='GPS longitude in degrees (decimal with dot)')
    parser.add_argument('--altitudes',
        type=lambda val: [int(item.strip()) for item in val.split(",")],
        default='15,12,9,6,3,0',
        help='Comma separated list of altitudes in thousands of feet each'
    )
    args = parser.parse_args()

    root = tk.Tk()
    root.after(0, lambda: root.attributes('-fullscreen', True))
    app = Application(args.latitude, args.longitude, args.font_title, args.font_stuff, args.altitudes, master=root)
    log.setLevel(logging.DEBUG)
    log.critical("Entering application mainloop")
    app.mainloop()
    log.critical("Exiting application mainloop")

