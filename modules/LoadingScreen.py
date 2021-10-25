import io
import os.path
import time

import pygame
import datetime
from concurrent import futures

from urllib.request import urlopen
import logging as log

from OpenWeatherWrapper import OpenWeatherWrapper

pallet_one = (255, 206, 0)
pallet_two = (0, 0, 0)
pallet_three = (255, 255, 255)


class LoadingScreen:

    def __init__(self, weather_api: OpenWeatherWrapper, icon_cache, forecast, icons, modules, screen: pygame.Surface, ignore_cache=False):
        """"""
        self.weather_api = weather_api
        self.icon_cache = icon_cache
        self.no_image, self.husky, self.empty_image, self.splash = icons
        self.forecast = forecast
        self.webcams, self.current_weather = modules
        self.ignore_cache = ignore_cache
        self.screen = screen

        self._common_icons = ["01", "02", "03", "04", "09", "10", "11", "13", "50"]
        self._current_icon_number = 0

        self.loading_status_strings = []
        self.loading_percent_bias = {"Icons": 0.35, "Forecast": 0.55, "Webcams": 0.1}
        self.loading_percentage = 0

        self.splash = pygame.transform.scale(self.splash, self.screen.get_size())

    def load_weather(self):
        """"""
        self.loading_status_strings.append("Loading weather data from OpenWeatherMap.org")
        self.weather_api.update_current_weather()
        self.weather_api.update_forecast_weather()
        self.weather_api.update_future_weather()
        self.loading_status_strings.append("Loaded weather data from OpenWeatherMap.org")

    def _load_icon(self, icon):

        def update_cache(new_image_str):
            f = open(f"Caches/Icon_cache/{icon}.png", "wb")
            f.write(new_image_str)
            f.close()

        def load():
            if os.path.exists(f"Caches/Icon_cache/{icon}.png") and not self.ignore_cache:
                f = open(f"Caches/Icon_cache/{icon}.png", "rb")
                image_str = f.read()
                f.close()
            else:
                image_str = urlopen(icon_url, timeout=0.25).read()
                update_cache(image_str)

            image_file = io.BytesIO(image_str)
            return pygame.image.load(image_file).convert_alpha()

        self.loading_percentage += (self.loading_percent_bias['Icons'] / (len(self._common_icons) * 2)) * 0.1
        icon_url = f"http://openweathermap.org/img/wn/{icon}@2x.png"
        try:
            self.loading_status_strings.append(f"Loading icon: {icon_url}")
            pic = load()
            self.icon_cache.update({icon_url: pic})
            self.loading_status_strings.append(f"Loaded icon: {icon_url}")
            self.loading_percentage += (self.loading_percent_bias['Icons'] / (len(self._common_icons) * 2)) * 0.9
        except Exception as e:
            self.loading_status_strings.append(f"Failed icon: {icon_url}, reason {e}")
            print(e)
            self.loading_percentage += (self.loading_percent_bias['Icons'] / (len(self._common_icons) * 2)) * 0.9

    def cache_icons(self):
        if self._current_icon_number < len(self._common_icons):
            with futures.ThreadPoolExecutor(max_workers=2) as executor:
                executor.submit(self._load_icon, f"{self._common_icons[self._current_icon_number]}d")
                executor.submit(self._load_icon, f"{self._common_icons[self._current_icon_number]}n")
            self._current_icon_number += 1
            return False
        else:
            return True

    def draw_progress(self, screen, location, max_length):
        x, y = location
        font = pygame.font.SysFont('couriernew', 16)
        loading_fonts = []
        screen.blit(self.splash, (0, 0))
        for event in self.loading_status_strings[-8:].__reversed__():
            loading_fonts.append(font.render(f"{event}", True, pallet_one))
        loading_bar = pygame.Rect(x, y, self.loading_percentage * max_length, 20)
        pygame.draw.rect(screen, [255, 206, 0], loading_bar)
        pos_modifier = 0
        for text in loading_fonts:
            screen.blit(text, text.get_rect(center=(self.screen.get_width() / 2, y + 30 + (24 * pos_modifier))))
            pos_modifier += 1
