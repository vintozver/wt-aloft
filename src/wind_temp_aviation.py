import tkinter as tk
import tkinter.font as tk_font
import math


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
        self.wind_vars = {
            alt: tuple(tk.StringVar(value=value) for value in
                       ('?%dWD' % alt, '?%dWS' % alt, '?%dT' % alt))
            for alt in self.ALTITUDES
        }
        self.update_var = tk.StringVar(value='- ? -')
        self.sun_up_var = tk.StringVar(value='UU:UU')
        self.sun_down_var = tk.StringVar(value='DD:DD')

    def _create_widgets(self):
        tk.Label(self, padx=5, pady=5, justify=tk.CENTER,
                 background=self.background_color, foreground=self.header_color,
                 font=tk_font.Font(size=self.FONT_TITLE), text=self.title).pack(
                     side=tk.TOP, fill=tk.X)
        titles = tk.Frame(self, background=self.background_color)
        titles.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        titles_in = tk.Frame(titles)
        titles_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        for title, width in (('altitude', 8), ('wind from', 9), ('speed', 6), ('temp', 5)):
            tk.Label(titles_in, width=width, padx=5, pady=5, anchor=tk.NE,
                     justify=tk.LEFT, background=self.background_color,
                     foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
                     text=title).pack(side=tk.LEFT)
        for alt in self.ALTITUDES:
            self._create_line(alt)
        update = tk.Frame(self, background=self.background_color)
        update.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        update_in = tk.Frame(update)
        update_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        tk.Label(update_in, padx=5, pady=5, background=self.background_color,
                 foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
                 text='⇄').pack(side=tk.LEFT)
        tk.Label(update_in, padx=5, pady=5, background=self.background_color,
                 foreground='yellow', font=tk_font.Font(size=self.FONT_STUFF),
                 textvariable=self.update_var).pack(side=tk.LEFT)
        for label, variable in (('☼↑', self.sun_up_var), ('☼↓', self.sun_down_var)):
            tk.Label(update_in, padx=5, pady=5, background=self.background_color,
                     foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
                     text=label).pack(side=tk.LEFT)
            tk.Label(update_in, padx=5, pady=5, background=self.background_color,
                     foreground=self.text_color, font=tk_font.Font(size=self.FONT_STUFF),
                     textvariable=variable).pack(side=tk.LEFT)

    def _create_line(self, alt):
        frame = tk.Frame(self, background=self.background_color)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        frame_in = tk.Frame(frame, background=self.background_color)
        frame_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        alt_str = '%d ft' % (alt * 1000) if alt > 0 else 'ground'
        tk.Label(frame_in, width=8, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
                 background=self.background_color, foreground=self.label_color,
                 font=tk_font.Font(size=self.FONT_STUFF), text=alt_str).pack(side=tk.LEFT)
        canvas = tk.Canvas(frame_in, width=self.FONT_STUFF, height=self.FONT_STUFF,
                           background=self.background_color, highlightthickness=0, borderwidth=0)
        canvas.pack(side=tk.LEFT)
        self.wind_vars[alt] += (canvas,)
        for variable, width in zip(self.wind_vars[alt][:3], (7, 6, 5)):
            tk.Label(frame_in, width=width, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
                     background=self.background_color, foreground=self.text_color,
                     font=tk_font.Font(size=self.FONT_STUFF),
                     textvariable=variable).pack(side=tk.LEFT)

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
            sina, cosa = math.sin(math.radians(wind_dir)), math.cos(math.radians(wind_dir))
            canvas.create_line(self.WIND_ARROW_SZ * (1.0 - sina),
                               self.WIND_ARROW_SZ * (1.0 + cosa),
                               self.WIND_ARROW_SZ * (1.0 + sina),
                               self.WIND_ARROW_SZ * (1.0 - cosa),
                               arrow=tk.FIRST, fill=self.text_color)
        self.update_var.set(update_time.strftime('%Y-%m-%d ') + self.format_time(update_time))

    def update_sun(self, sunrise, sunset):
        self.sun_up_var.set(self.format_time(sunrise))
        self.sun_down_var.set(self.format_time(sunset))
