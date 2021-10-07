import io
import os

import pygame
import datetime

from urllib.request import urlopen
import logging as log

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)


class CurrentWeather:

    def __init__(self, weather_api, icon_cache, icon):
        """"""
        self.weather_api = weather_api
        self.big_info = None
        self.icon_cache = icon_cache
        self.icon = icon
        self.font1 = pygame.font.SysFont('timesnewroman', 48)
        self.font2 = pygame.font.Font(os.path.join("Assets/Fonts/Merri/Merriweather-Regular.ttf"), 15)

    def draw_current(self, screen, location):
        """Draws the current temp with high low"""
        x, y = location
        # Load temp

        if self.weather_api.current_weather is not None:
            temp = self.weather_api.current_weather.temperature('fahrenheit')
            wind = self.weather_api.current_weather.wind('miles_hour')
            humidity = self.weather_api.current_weather.humidity
            status = self.weather_api.current_weather.detailed_status
            sky_icon = self.weather_api.current_weather.weather_icon_name
            visibility = self.weather_api.current_weather.visibility(unit='miles')
            icon_url = f"http://openweathermap.org/img/wn/{sky_icon}@2x.png"
            rain = self.weather_api.current_weather.rain
            snow = self.weather_api.current_weather.snow
            clouds = self.weather_api.current_weather.clouds
            updated = self.weather_api.current_weather.reference_time()
        else:
            temp = {'temp': 0, 'temp_max': 0, 'temp_min': 0, 'feels_like': 0, 'temp_kf': None}
            wind = {'speed': 0, 'deg': 0}
            status = "No data"
            humidity = 0
            visibility = 0
            icon_url = None
            rain = {}
            snow = {}
            clouds = 0
            alert = None
            updated = 0
        if visibility > 6:
            visibility = "Clear"
        elif visibility % 1 == 0:
            visibility = f"{int(visibility)} mi"
        elif visibility > 1:
            visibility = f"{round(visibility, 2)} mi"
        else:
            visibility = f"{int(visibility*5280)} ft"
        updated = datetime.datetime.fromtimestamp(updated)
        self.big_info = self.font1.render(f"{round(temp['temp'])}°F {status.capitalize()}", True, pallet_one)
        small_info = self.font2.render(f"Feels: {round(temp['feels_like'])}°F; Clouds: {round(clouds)}%"
                                       f"; Humidity: {humidity}%", True, pallet_three)
        small_info2 = self.font2.render(f"Vis: {visibility}; Wind: {self.weather_api.get_angle_arrow(wind['deg'])}{round(wind['speed'], 1)} mph"
                                        f"; {updated.strftime('%I:%M %p')}", True, pallet_three)

        # if rain:
        #     precipitation_text = font2.render(f"Rain: {rain}", True, (255, 255, 255))
        # elif snow:
        #     precipitation_text = font2.render(f"Snow: {snow}", True, (255, 255, 255))
        # else:
        #     precipitation_text = font2.render(f"No precipitation", True, (255, 255, 255))

        try:
            if icon_url in self.icon_cache:
                current_icon = self.icon_cache[icon_url]
            else:
                image_str = urlopen(icon_url, timeout=0.5).read()
                image_file = io.BytesIO(image_str)
                current_icon = pygame.image.load(image_file)
                self.icon_cache.update({icon_url: current_icon})
        except Exception as e:
            # print(f"Current weather icon load error: {e}")
            current_icon = self.icon

        screen.blit(current_icon, current_icon.get_rect(center=(x + 42.5, y + 40)))
        screen.blit(self.big_info, (x + 85, y))
        screen.blit(small_info, (x + 85, y + 52))
        screen.blit(small_info2, (x + 85, y + 76))
        # if precipitation_text:
        #     screen.blit(precipitation_text, (50, 350))
