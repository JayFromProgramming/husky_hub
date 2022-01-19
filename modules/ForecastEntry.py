import io
import time

import pint
import pygame
import datetime

from urllib.request import urlopen
import logging as log

from atmos import calculate
# import metpy.calc as mpcalc
from Utils import humidity_converter

from OpenWeatherWrapper import OpenWeatherWrapper
from Utils import buttonGenerator

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)


class FocusedForecast:

    def __init__(self, forecast):
        """
        Constructor for the FocusedForecast class.
        :param forecast: The forecast object to be shown in more detail.
        """
        self.forecast = forecast
        self.x = 5
        self.y = 155
        self.weather = forecast.weather
        self.open_since = time.time()
        self.lines = []
        ref = self.weather.reference_time()
        self.delta = int((ref - ref % (3600 * 1.5)) - (time.time() - time.time() % (3600 * 1.5)))

        font1 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 42)
        font2 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 18)
        font3 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 15)
        font4 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 25)
        self.radar_buttons = []
        self.radar_buttons.append(buttonGenerator.Button(font3, (75, 115, 100, 35), "Radar View", [255, 206, 0], (0, 0, 0),
                                                         button_data=[("PR0", self.delta, ""), ("CL", self.delta, "")]))
        self.radar_buttons.append(buttonGenerator.Button(font3, (185, 115, 100, 35), "Wind View", [255, 206, 0], (0, 0, 0),
                                                         button_data=[("WND", self.delta, "&use_norm=false&arrow_step=16")]))
        self.radar_buttons.append(buttonGenerator.Button(font3, (295, 115, 100, 35), "Temp Map", [255, 206, 0], (0, 0, 0),
                                                         button_data=[("TA2", self.delta, "")]))
        self.radar_buttons.append(buttonGenerator.Button(font3, (405, 115, 120, 35), "Humidity Map", [255, 206, 0], (0, 0, 0),
                                                         button_data=[("HRD0", self.delta, "")]))
        self.radar_buttons.append(buttonGenerator.Button(font3, (535, 115, 120, 35), "Combined Map", [255, 206, 0], (0, 0, 0),
                                                         button_data=[("PR0", self.delta, ""),
                                                                      ("WND", self.delta, "&use_norm=true&arrow_step=16")]))
        temp = self.weather.temperature('fahrenheit')
        wind = self.weather.wind('miles_hour')
        humidity = self.weather.humidity
        status = self.weather.detailed_status
        sky_icon = self.weather.weather_icon_name
        visibility = self.weather.visibility(unit='miles')
        rain = self.weather.rain
        snow = self.weather.snow
        clouds = self.weather.clouds
        uvi = self.weather.uvi
        updated = self.weather.reference_time()
        updated = datetime.datetime.fromtimestamp(updated)
        pressure = self.weather.pressure['press']
        dew_point = self.weather.dewpoint
        temp_difference = 67 - temp['temp']
        temp_c = self.weather.temperature('celsius')['temp']
        absolute_humidity = calculate('AH', RH=humidity, p=pressure, T=temp_c, p_units='hPa', debug=True)
        # print(absolute_humidity)
        inside_humidity = humidity_converter.convert_absolute_humidity(absolute_humidity[0], temp['temp'], pressure)

        # inside_humidity = mpcalc.relative_humidity_from_specific_humidity(
        #     specific_humidity=pint.Quantity(absolute_humidity), temperature=pint.Quantity(67, units="fahrenheit"),
        #     pressure=pint.Quantity(pressure, units="hPa"))

        self.time_info = font4.render(updated.strftime('Forecast for %A, %B %d at %I:00 %p'), True, pallet_one)
        self.big_info = font1.render(f"{round(temp['temp'])}°F {status.capitalize()}", True, pallet_one)
        self.lines.append(font2.render(f"It will feel like {round(temp['feels_like'])}°F with an expected humidity of {humidity}%",
                                       True, pallet_three))

        self.lines.append(font2.render(f"Calculated inside humidity with outside air will be Not_Implemented",
                                       True, pallet_three))

        self.lines.append(font2.render(f"Expected cloud cover of {round(clouds)}%  "
                                       + (f"with a {OpenWeatherWrapper.uvi_scale(uvi).lower()} UV index of {uvi}" if uvi else '')
                                       , True, pallet_three))

        self.lines.append(font2.render(f"Expected wind speed of {OpenWeatherWrapper.get_angle_arrow(wind['deg'])}{round(wind['speed'], 1)} mph "
                                       + f"with gusts of up to {round(wind['gust'], 1)} mph" if 'gust' in wind else "",
                                       True, pallet_three))

        self.lines.append(font2.render(f"The expected visibility will be {str(round(visibility, 2)) + 'mi' if visibility < 6 else 'clear'}",
                                       True, pallet_three))
        if rain:
            self.lines.append(font2.render(f"There is a {round(self.weather.precipitation_probability * 100)}% chance of rain "
                                           f"with {round(rain['1h'] / 25.4, 4)} inches of rain expected", True, pallet_three))
        if snow:
            self.lines.append(font2.render(f"There is a {round(self.weather.precipitation_probability * 100)}% chance of snow "
                                           f"with {round(snow['1h'] / 25.4, 4)} inches of snow expected", True, pallet_three))

        if not rain and not snow and self.weather.precipitation_probability > 0.1:
            self.lines.append(font2.render(f"There is a {round(self.weather.precipitation_probability * 100)}% chance of precipitation expected"
                                           , True, pallet_three))

    def draw(self, screen):
        """
        Draws the detailed weather information to the screen
        :param screen: The screen to draw to
        :return: None
        """
        x = self.x
        y = self.y
        for button in self.radar_buttons:
            button.blit(screen)
        screen.blit(self.time_info, (x + 85, y))
        screen.blit(self.forecast.pic, self.forecast.pic.get_rect(center=(x + 42.5, y + 40)))
        screen.blit(self.big_info, (x + 85, y + 25))
        count = 0
        for line in self.lines:
            screen.blit(line, (x + 40, y + (count * 27) + 76))
            count += 1

        if self.open_since < time.time() - 30:
            self.forecast.focused = False


class ForecastEntry:

    def __init__(self, screen, location, weather, delta_time, icon_cache, icon):
        """
        Creates a forecast entry for the weather information
        :param screen: The screen to draw to
        :param location: The X,Y location of the forecast entry
        :param weather: The weather information to use
        :param delta_time: The time difference between the current time and the time of the forecast
        :param icon_cache: The icon cache to use
        :param icon: The icon to use if no icon is found
        """
        self.x, self.y = location
        self.location = location
        self.focused = False
        self.focused_object = None
        self.weather = weather
        self.delta_time = delta_time
        self.clicked_rect = pygame.Rect(self.x, self.y, 85, 300)
        self.surf = pygame.Surface((90, 315))
        font1 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 24)
        font2 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 14)
        font3 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 20)
        font4 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 18)

        if weather is not None:
            icon_name = weather.weather_icon_name
            icon_url = f"http://openweathermap.org/img/wn/{icon_name}@2x.png"
            status = weather.status
            d_status = weather.detailed_status
            temp = weather.temperature('fahrenheit')['temp']
            feels_like = weather.temperature('fahrenheit')['feels_like']
            humidity = weather.humidity
            wind = weather.wind('miles_hour')
            reference_time = weather.reference_time()
            reference_time = datetime.datetime.fromtimestamp(reference_time)
            percip_percent = weather.precipitation_probability
        else:
            icon_url = None
            status = "None"
            d_status = None
            temp = -10
            feels_like = 67
            wind = {'speed': 60, 'deg': 0}
            humidity = 99
            reference_time = datetime.datetime.now()
            percip_percent = 0

        if status == "Thunderstorm":
            status = "Storm"
        elif status == "Rain":
            status = f"{d_status[0].capitalize()}.{status.capitalize()}"
        elif status == "Snow":
            status = f"{d_status[0].capitalize()}.{status.capitalize()}"
        else:
            status = status.capitalize()

        # self.forecast_time = datetime.datetime.now() + datetime.timedelta(hours=delta_time)
        self.forecast_time = reference_time
        self.day_formatted = self.forecast_time.strftime("%m/%d")
        self.time_formatted = self.forecast_time.strftime("%I %p")
        self.day_text = font3.render(f"{self.day_formatted}", True, pallet_one)
        self.time_text = font3.render(f"{self.time_formatted}", True, pallet_one)
        self.small_info = font3.render(f"{status}", True, pallet_three)
        self.forecast_temp = font1.render(f"{round(temp)}°F", True, pallet_one)
        if percip_percent > 0.2:
            self.second_name = font3.render("Chance", True, pallet_three)
            self.second_data = font1.render(f"{round(percip_percent * 100)}%", True, pallet_one)
        else:
            self.second_name = font3.render("Feels", True, pallet_three)
            self.second_data = font1.render(f"{round(feels_like)}°F", True, pallet_one)
        self.humidity_text = font2.render("Humidity", True, pallet_three)
        self.humidity_percent = font1.render(f"{humidity}%", True, pallet_one)
        self.wind_text = font3.render("Wind", True, pallet_three)
        self.wind_speed = font4.render(f"{OpenWeatherWrapper.get_angle_arrow(wind['deg'])}{round(wind['speed'])} mph", True, pallet_one)

        try:
            if icon_url in icon_cache:
                self.pic = icon_cache[icon_url]
            else:
                image_str = urlopen(icon_url, timeout=0.5).read()
                image_file = io.BytesIO(image_str)
                self.pic = pygame.image.load(image_file)
                icon_cache.update({icon_url: self.pic})
        except Exception as e:
            self.pic = icon
            print(f"Forecast Icon Load Error: {e}")

        screen = self.surf

        pygame.draw.line(screen, pallet_two, (85, 0), (85, self.surf.get_height()))
        screen.blit(self.day_text, self.day_text.get_rect(center=(42.5, 7)))
        screen.blit(self.time_text, self.time_text.get_rect(center=(42.5, 25)))
        screen.blit(self.pic, self.pic.get_rect(center=(42.5, 70)))
        screen.blit(self.small_info, self.small_info.get_rect(center=(42.5, 110)))
        screen.blit(self.forecast_temp, self.forecast_temp.get_rect(center=(42.5, 140)))
        screen.blit(self.second_name, self.second_name.get_rect(center=(42.5, 167)))
        screen.blit(self.second_data, self.second_data.get_rect(center=(42.5, 195)))
        screen.blit(self.humidity_text, self.humidity_text.get_rect(center=(42.5, 220)))
        screen.blit(self.humidity_percent, self.humidity_percent.get_rect(center=(42.5, 247)))
        screen.blit(self.wind_text, self.wind_text.get_rect(center=(42.5, 276)))
        screen.blit(self.wind_speed, self.wind_speed.get_rect(center=(42.5, 300)))

        del self.day_text, self.time_text, self.small_info, self.forecast_temp, self.second_name, self.second_data
        del self.humidity_text, self.humidity_percent, self.wind_text, self.wind_speed

        self.surf.convert()

    def check_click(self, mouse_pos):
        """
        Checks if the mouse is hovering over the forecast card.
        :param mouse_pos: The X,Y coordinates of the mouse.
        :return: None
        """
        if self.clicked_rect.collidepoint(mouse_pos):
            self.focused = True

    def draw(self, screen):
        """
        Draws the forecast card to the screen.
        :param screen: The screen to draw the card to.
        :return: None
        """
        if self.focused:
            if not self.focused_object:
                self.focused_object = FocusedForecast(self)
            self.focused_object.draw(screen)
        else:
            screen.blit(self.surf, (self.x, self.y))
