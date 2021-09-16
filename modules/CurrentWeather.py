import io
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

    def draw_current(self, screen, location):
        """Draws the current temp with high low"""
        x, y = location
        # Load temp
        font1 = pygame.font.SysFont('timesnewroman', 48)
        font2 = pygame.font.SysFont('timesnewroman', 18)
        if self.weather_api.current_weather is not None:
            temp = self.weather_api.current_weather.temperature('fahrenheit')
            wind = self.weather_api.current_weather.wind()
            humidity = self.weather_api.current_weather.humidity
            status = self.weather_api.current_weather.detailed_status
            sky_icon = self.weather_api.current_weather.weather_icon_name
            visibility = self.weather_api.current_weather.visibility_distance
            icon_url = f"http://openweathermap.org/img/wn/{sky_icon}@2x.png"
            rain = self.weather_api.current_weather.rain
            snow = self.weather_api.current_weather.snow
            # updated = self.weather_api.current_weather.reference_time()
        else:
            temp = {'temp_max': 0, 'temp': 0, 'temp_min': 0}
            wind = {'speed': 0, 'deg': 0}
            status = "No data"
            humidity = 0
            visibility = 0
            # icon_url = "http://openweathermap.org/img/wn/01d@2x.png"
            icon_url = None
            rain = {}
            snow = {}
            alert = None
            updated = "N/A"

        self.big_info = font1.render(f"{round(temp['temp'])}°F {status.capitalize()}", True, pallet_one)
        small_info = font2.render(f"Low: {round(temp['temp_min'])}°F; High: {round(temp['temp_max'])}"
                                  f"°F; Humidity: {humidity}%", True, pallet_three)
        small_info2 = font2.render(f"Vis: {str(round(visibility * 0.621371)) + 'mi' if visibility < 10000 else 'Clear'}"
                                   f"; Wind: {round(wind['speed'])} mph; Direction: {round(wind['deg'])}°", True,
                                   pallet_three)

        if rain:
            precipitation_text = font2.render(f"Rain: {rain}", True, (255, 255, 255))
        elif snow:
            precipitation_text = font2.render(f"Snow: {snow}", True, (255, 255, 255))
        else:
            precipitation_text = font2.render(f"No precipitation", True, (255, 255, 255))

        try:
            if icon_url in self.icon_cache:
                current_icon = self.icon_cache[icon_url]
            else:
                image_str = urlopen(icon_url, timeout=0.5).read()
                image_file = io.BytesIO(image_str)
                current_icon = pygame.image.load(image_file)
                self.icon_cache.update({icon_url: current_icon})
        except Exception:
            current_icon = self.icon

        screen.blit(current_icon, current_icon.get_rect(center=(x + 42.5, y + 40)))
        screen.blit(self.big_info, (x + 85, y))
        screen.blit(small_info, (x + 85, y + 52))
        screen.blit(small_info2, (x + 85, y + 76))
        # if precipitation_text:
        #     screen.blit(precipitation_text, (50, 350))