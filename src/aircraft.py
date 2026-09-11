import tkinter as tk
import tkinter.font as tk_font


class Aircraft(tk.Frame):
    background_color = 'black'
    text_color = 'white'
    header_color = 'red'
    label_color = 'green'

    def __init__(self, font_title, font_stuff, aircraft, master=None):
        super().__init__(master, background=self.background_color)
        self.FONT_STUFF = font_stuff
        self.aircraft = aircraft
        self.aircraft_vars = {}
        self._create_widgets(font_title)

    def _create_widgets(self, font_title):
        tk.Label(self, padx=5, pady=5, justify=tk.CENTER,
                 background=self.background_color, foreground=self.header_color,
                 font=tk_font.Font(size=font_title), text='Aircraft statuses').pack(
                     side=tk.TOP, fill=tk.X)
        titles = tk.Frame(self, background=self.background_color)
        titles.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        titles_in = tk.Frame(titles)
        titles_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
        for title, width in (('aircraft', 8), ('altitude', 10), ('speed', 6), ('status', 6)):
            tk.Label(titles_in, width=width, padx=5, pady=5, anchor=tk.NE,
                     justify=tk.LEFT, background=self.background_color,
                     foreground=self.label_color, font=tk_font.Font(size=self.FONT_STUFF),
                     text=title).pack(side=tk.LEFT)
        for registration, alias in self.aircraft:
            variables = [tk.StringVar(value='N/A') for _ in range(4)]
            variables[0].set(alias)
            self.aircraft_vars[registration] = variables
            frame = tk.Frame(self, background=self.background_color)
            frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            frame_in = tk.Frame(frame)
            frame_in.place(anchor=tk.CENTER, relx=.5, rely=.5)
            for variable, width in zip(variables, (8, 10, 6, 6)):
                tk.Label(frame_in, width=width, padx=5, pady=5, anchor=tk.E, justify=tk.LEFT,
                         background=self.background_color, foreground=self.text_color,
                         font=tk_font.Font(size=self.FONT_STUFF),
                         textvariable=variable).pack(side=tk.LEFT)
        self.update_var = tk.StringVar(value='- ? -')
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

    def update(self, values_by_registration, history, update_time):
        for registration, alias in self.aircraft:
            history[registration].append(values_by_registration.get(registration))
            current = next((item for item in reversed(history[registration]) if item is not None), None)
            values = self.aircraft_vars[registration]
            values[0].set(alias)
            for variable, item in zip(values[1:], current or ('N/A', 'N/A', 'N/A')):
                variable.set(item)
        self.update_var.set(update_time.strftime('%Y-%m-%d %H:%M'))
