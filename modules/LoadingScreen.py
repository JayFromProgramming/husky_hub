import io
import time

import pygame
import datetime
from concurrent import futures

from urllib.request import urlopen
import logging as log

pallet_one = (255, 206, 0)
pallet_two = (0, 0, 0)
pallet_three = (255, 255, 255)


class LoadingScreen:

    def __init__(self, weather_api, icon_cache, forecast, icons, modules):
        """"""
        self.weather_api = weather_api
        self.icon_cache = icon_cache
        self.no_image, self.husky, self.empty_image, self.splash = icons
        self.forecast = forecast
        self.webcams, self.current_weather = modules

        self._common_icons = ["01", "02", "03", "04", "09", "10", "11", "13", "50"]
        self._current_icon_number = 0

        self.loading_status_strings = []
        self.loading_percent_bias = {"Icons": 0.35, "Forecast": 0.55, "Webcams": 0.1}
        self.loading_percentage = 0

    def load_weather(self):
        """"""
        self.loading_status_strings.append("Loading weather data from OpenWeatherMap.org")
        self.weather_api.update_current_weather()
        self.weather_api.update_future_weather()
        self.loading_status_strings.append("Loaded weather data from OpenWeatherMap.org")

    def _load_icon(self, icon):
        self.loading_percentage += (self.loading_percent_bias['Icons'] / (len(self._common_icons) * 2)) * 0.1
        icon_url = f"http://openweathermap.org/img/wn/{icon}@2x.png"
        try:
            self.loading_status_strings.append(f"Loading icon: {icon_url}")
            image_str = urlopen(icon_url, timeout=0.25).read()
            image_file = io.BytesIO(image_str)
            pic = pygame.image.load(image_file)
            self.icon_cache.update({icon_url: pic})
            self.loading_status_strings.append(f"Loaded icon: {icon_url}")
            self.loading_percentage += (self.loading_percent_bias['Icons'] / (len(self._common_icons) * 2)) * 0.9
        except Exception:
            self.loading_status_strings.append(f"Failed icon: {icon_url}")
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
        screen.blit(self.splash, self.splash.get_rect(center=(400, 265)))
        for event in self.loading_status_strings[-8:].__reversed__():
            loading_fonts.append(font.render(f"{event}", True, pallet_one))
        loading_bar = pygame.Rect(x, y, self.loading_percentage * max_length, 20)
        pygame.draw.rect(screen, [255, 206, 0], loading_bar)
        pos_modifier = 0
        for text in loading_fonts:
            screen.blit(text, text.get_rect(center=(400, y + 30 + (24 * pos_modifier))))
            pos_modifier += 1
