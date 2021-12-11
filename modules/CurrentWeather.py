import io
import os

import pygame
import datetime

from urllib.request import urlopen
import logging as log

import Coordinator

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)
pallet_four = (0, 0, 0)


class CurrentWeather:

    def __init__(self, weather_api, icon_cache, icon, coordinator: Coordinator.Coordinator):
        """
        Initializes the current weather display class
        :param weather_api: The OpenWeatherWrapper object
        :param icon_cache: The weather icon cache
        :param icon: The default weather icon
        :param thermostat: The thermostat object
        """
        self.weather_api = weather_api
        self.coordinator = coordinator.coordinator
        self.big_info = None
        self.small_info = None
        self.small_info2 = None
        self.icon_cache = icon_cache
        self.icon = icon
        self.current_icon = None
        self.font1 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 42)
        self.font2 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 15)
        self.update()

    def update(self):
        """
        Updates the current weather data
        :return: None
        """
        if self.weather_api.current_weather is not None:
            temp = self.weather_api.current_weather.temperature('fahrenheit')
            wind = self.weather_api.current_weather.wind('miles_hour')
            humidity = self.weather_api.current_weather.humidity
            status = self.weather_api.current_weather.detailed_status
            secondary_status_list = self.weather_api.current_weather.extra_status_info
            sky_icon = self.weather_api.current_weather.weather_icon_name
            visibility = self.weather_api.current_weather.visibility(unit='miles')
            icon_url = f"http://openweathermap.org/img/wn/{sky_icon}@2x.png"
            rain = self.weather_api.current_weather.rain
            snow = self.weather_api.current_weather.snow
            clouds = self.weather_api.current_weather.clouds
            updated = self.weather_api.current_weather.reference_time()
            secondary_temp = f"Feels: {round(temp['feels_like'])}°F"
        else:
            temp = {'temp': 0, 'temp_max': 0, 'temp_min': 0, 'feels_like': 0, 'temp_kf': None}
            wind = {'speed': 0, 'deg': 0}
            status = "No data"
            secondary_status_list = ["No data"]
            humidity = 0
            visibility = 0
            icon_url = None
            rain = {}
            snow = {}
            clouds = 0
            alert = None
            updated = 0
            secondary_temp = None
        if visibility > 6:
            visibility = "Clear"
        elif visibility % 1 == 0:
            visibility = f"{int(visibility)} mi"
        elif visibility > 1:
            visibility = f"{round(visibility, 2)} mi"
        elif len(str(float(visibility).as_integer_ratio()[0])) > 4:
            visibility = f"{round(visibility, 2)} mi"
        else:
            top, bottom = float(visibility).as_integer_ratio()
            visibility = f"{top}/{bottom} mi"

        secondary_status_string = ""
        for secondary_status in secondary_status_list:
            secondary_status_string += f" & {secondary_status['main']}"

        # if self.coordinator.get_temperature() != -9999:
        #     secondary_temp = f"{round(self.coordinator.get_temperature(), 2)}°F"

        updated = datetime.datetime.fromtimestamp(updated)
        self.big_info = self.font1.render(f"{round(temp['temp'])}°F {status.capitalize()}{secondary_status_string}", True, pallet_one, pallet_four).convert_alpha()
        self.small_info = self.font2.render(f"{secondary_temp}; Clouds: {round(clouds)}%"
                                            f"; Humidity: {humidity}%", True, pallet_three, pallet_four).convert()
        self.small_info2 = self.font2.render(f"Vis: {visibility}; Wind: {self.weather_api.get_angle_arrow(wind['deg'])}{round(wind['speed'], 1)} mph"
                                             f"; {updated.strftime('%I:%M %p')}", True, pallet_three, pallet_four).convert()

        try:
            if icon_url in self.icon_cache:
                self.current_icon = self.icon_cache[icon_url]
            else:
                image_str = urlopen(icon_url, timeout=0.5).read()
                image_file = io.BytesIO(image_str)
                self.current_icon = pygame.image.load(image_file).convert_alpha()
                self.icon_cache.update({icon_url: self.current_icon})
        except Exception as e:
            # print(f"Current weather icon load error: {e}")
            self.current_icon = self.icon

    def draw_current(self, screen, location):
        """
        Draws the current weather data
        :param screen: The screen to draw the current weather data on
        :param location: The x, y location to draw the current weather data at
        :return: None
        """
        x, y = location
        # Load temp
        screen.blit(self.current_icon, self.current_icon.get_rect(center=(x + 42.5, y + 40)))
        screen.blit(self.big_info, (x + 75, y))
        screen.blit(self.small_info, (x + 75, y + 52))
        screen.blit(self.small_info2, (x + 75, y + 76))
        # if precipitation_text:
        #     screen.blit(precipitation_text, (50, 350))
