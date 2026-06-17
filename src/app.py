import tkinter as tk
import tkinter.font as tk_font
from threading import Thread, Event
import requests
import time
import logging
import signal
import datetime
import json


log = logging.getLogger(__name__)


class Application(tk.Frame):
    STATE_MAIN = 0
    _STATE_DELIMITER = 1

    background_color = 'black'
    text_color = 'white'
    header_color = 'red'
    label_color = 'green'

    FONT_TITLE=100
    FONT_STUFF=75

    uri = 'https://www.markschulze.net/winds/winds_openmeteo.php?lat=46.4772&lon=-122.8064&hourOffset=0'

    def __init__(self, master=None):
        super().__init__(master, background=self.background_color)

        self.shutdown_event = Event()
        
        self.create_vars(18)
        self.create_vars(12)
        self.create_vars(9)
        self.create_vars(6)
        self.create_vars(3)
        self.create_vars(0)

        self.state = 0

        self.master = master
        self.pack(side='top', fill=tk.BOTH, expand=True)

        self.create_widgets()

        self.master.after(0, self.invoke_switch_windows)

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
            alt_str = '%dk' % alt
        else:
            alt_str = 'SFC'

        frame = tk.Frame(self.frame_main, background=self.background_color)
        frame.pack(side='top', fill=tk.X)
        frame_label = tk.Label(frame, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text=alt_str
        )
        frame_label.pack(side='left')
        label_wind_dir = tk.Label(frame, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_wind_dir' % alt),
        )
        label_wind_dir.pack(side='left')
        label_wind_spd = tk.Label(frame, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_wind_spd' % alt),
        )
        label_wind_spd.pack(side='left')
        label_temp = tk.Label(frame, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=getattr(self, 'v_%dk_temp' % alt),
        )
        label_temp.pack(side='left')

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
        frame_titles_empty = tk.Label(frame_titles, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='alt'
        )
        frame_titles_empty.pack(side='left')
        frame_titles_wind_dir = tk.Label(frame_titles, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='W from'
        )
        frame_titles_wind_dir.pack(side='left')
        frame_titles_wind_speed = tk.Label(frame_titles, width=6, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='speed'
        )
        frame_titles_wind_speed.pack(side='left')
        frame_titles_temp = tk.Label(frame_titles, width=6, padx=4, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='temp'
        )
        frame_titles_temp.pack(side='left')

        self.create_line(18)
        self.create_line(12)
        self.create_line(9)
        self.create_line(6)
        self.create_line(3)
        self.create_line(0)

        self.v_upd = tk.StringVar()
        self.v_upd.set('- ? -')
        frame_upd = tk.Frame(self.frame_main, background=self.background_color)
        frame_upd.pack(side='top', fill=tk.X)
        frame_upd_label = tk.Label(frame_upd, width=5, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
            text='upd'
        )
        frame_upd_label.pack(side='left')
        label_upd = tk.Label(frame_upd, width=18, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
            background=self.background_color, foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
            textvariable=self.v_upd,
        )
        label_upd.pack(side='left')

        self.thread_fetcher = Thread(target=self.runner_fetcher, args=(), name='fetcher')
        self.thread_fetcher.start()

    def invoke_switch_windows(self):
        if self.shutdown_event.is_set():
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
        self.shutdown_event.set()
        self.master.destroy()
        log.info("quit exit")

    def runner_fetcher(self):
        log.critical('runner_fetcher enter')

        while True:
            result = self.runner_fetcher_iter()
            if result is not None:
                log.info('updating widgets')
                directions = result["direction"]
                speeds = result["speed"]
                temps = result["temp"]
                self.v_18k_wind_dir.set('%d°' % directions["18000"])
                self.v_18k_wind_spd.set('%dkts' % speeds["18000"])
                self.v_18k_temp.set('%d °C' % temps["18000"])
                self.v_12k_wind_dir.set('%d°' % directions["12000"])
                self.v_12k_wind_spd.set('%dkts' % speeds["12000"])
                self.v_12k_temp.set('%d °C' % temps["12000"])
                self.v_9k_wind_dir.set('%d°' % directions["9000"])
                self.v_9k_wind_spd.set('%dkts' % speeds["9000"])
                self.v_9k_temp.set('%d °C' % temps["9000"])
                self.v_6k_wind_dir.set('%d°' % directions["6000"])
                self.v_6k_wind_spd.set('%dkts' % speeds["6000"])
                self.v_6k_temp.set('%d °C' % temps["6000"])
                self.v_3k_wind_dir.set('%d°' % directions["3000"])
                self.v_3k_wind_spd.set('%dkts' % speeds["3000"])
                self.v_3k_temp.set('%d °C' % temps["3000"])
                self.v_0k_wind_dir.set('%d°' % directions["0"])
                self.v_0k_wind_spd.set('%dkts' % speeds["0"])
                self.v_0k_temp.set('%d °C' % temps["0"])
                self.v_upd.set(datetime.datetime.now(datetime.UTC).strftime('%Y%m%d T %H%M Z'))
            else:
                log.info('not updating widgets (result is None)')

            if signal.sigtimedwait({signal.SIGINT, signal.SIGTERM}, 60) is not None:
                self.shutdown_event.set()
                break

        log.critical('runner_fetcher exit')

    def runner_fetcher_iter(self):
        log.info('Fetching data ...')
        try:
            http_content = requests.get(self.uri, timeout=10).content
            log.info('Fetching data success')
        except requests.exceptions.RequestException as err:
            http_content = None
            log.info('Fetching data failure', err)
        if http_content is None:
            return None

        return json.loads(http_content)

    def mainloop(self):
        super(Application, self).mainloop()
        self.thread_fetcher.join()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    root = tk.Tk()
    root.after(1000, lambda: root.attributes('-fullscreen', True))
    app = Application(master=root)
    log.setLevel(logging.DEBUG)
    log.critical("Entering application mainloop")
    app.mainloop()
    log.critical("Exiting application mainloop")

