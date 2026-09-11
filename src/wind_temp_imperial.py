from .wind_temp_aviation import WindTempAviation


class WindTempImperial(WindTempAviation):
    def format_temperature(self, temperature):
        return '%d °F' % round(temperature * 9 / 5 + 32)

    def format_wind_speed(self, speed):
        return '%dmph' % round(speed * 1.15078)

    def format_time(self, value):
        formatted_time = value.strftime('%I:%M %p')
        return formatted_time[1:] if formatted_time.startswith('0') else formatted_time
