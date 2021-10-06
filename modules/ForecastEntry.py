import io
import time

import pygame
import datetime

from urllib.request import urlopen
import logging as log

from OpenWeatherWrapper import OpenWeatherWrapper

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)


class FocusedForecast:

    def __init__(self, forecast):
        self.forecast = forecast
        self.x = 5
        self.y = 155
        self.weather = forecast.weather
        self.open_since = time.time()
        self.lines = []

        font1 = pygame.font.SysFont('timesnewroman', 42)
        font2 = pygame.font.Font("Assets/Fonts/Merri/Merriweather-Regular.ttf", 18)
        font3 = pygame.font.Font("Assets/Fonts/Merri/Merriweather-Regular.ttf", 48)
        font4 = pygame.font.SysFont('timesnewroman', 25)

        temp = self.weather.temperature()
        wind = self.weather.wind()
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

        self.time_info = font4.render(updated.strftime('Forecast for %A, %B %d at %I:00 %p'), True, pallet_one)
        self.big_info = font1.render(f"{round(temp['temp'])}°F {status.capitalize()}", True, pallet_one)
        self.lines.append(font2.render(f"It will feel like: {round(temp['feels_like'])}°F with an expected humidity of {humidity}%",
                                       True, pallet_three))

        self.lines.append(font2.render(f"Expected cloud cover of {round(clouds)}% and a {OpenWeatherWrapper.uvi_scale(uvi).lower()} UV index of {uvi}"
                                       , True, pallet_three))

        self.lines.append(font2.render(f"Expected wind speed of {OpenWeatherWrapper.get_angle_arrow(wind['deg'])}{round(wind['speed'], 1)} mph "
                                       + f"with gusts of up to {round(wind['gust'], 1)} mph" if 'gust' in wind else "",
                                       True, pallet_three))

        self.lines.append(font2.render(f"The expected visibility will be {str(round(visibility, 2)) + 'mi' if visibility < 6 else 'clear'}",
                                       True, pallet_three))
        if rain:
            self.lines.append(font2.render(f"There is a {round(self.weather.precipitation_probability * 100)}% chance of rain "
                                           f"with {round(rain['1h']/25.4, 4)} inches of rain expected", True, pallet_three))
        if snow:
            self.lines.append(font2.render(f"There is a {round(self.weather.precipitation_probability * 100)}% chance of snow "
                                           f"with {round(snow['1h']/25.4, 4)} inches of snow expected", True, pallet_three))

        if not rain and not snow and self.weather.precipitation_probability > 0.1:
            self.lines.append(font2.render(f"There is a {round(self.weather.precipitation_probability * 100)}% chance of precipitation expected"
                                           , True, pallet_three))

    def draw(self, screen):
        x = self.x
        y = self.y
        screen.blit(self.time_info, (x + 85, y))
        screen.blit(self.forecast.pic, self.forecast.pic.get_rect(center=(x + 42.5, y + 40)))
        screen.blit(self.big_info, (x + 85, y + 25))
        count = 0
        for line in self.lines:
            screen.blit(line, (x + 85, y + (count * 27) + 72))
            count += 1

        if self.open_since < time.time() - 30:
            self.forecast.focused = False


class ForecastEntry:

    def __init__(self, screen, location, weather, delta_time, icon_cache, icon):
        """Houses a forecast"""
        self.x, self.y = location
        self.location = location
        self.focused = False
        self.focused_object = None
        self.weather = weather
        self.delta_time = delta_time
        self.clicked_rect = pygame.Rect(self.x, self.y, 85, 300)
        self.surf = pygame.Surface((100, 400), pygame.SRCALPHA)
        font1 = pygame.font.Font("Assets/Fonts/Merri/Merriweather-Regular.ttf", 24)
        font2 = pygame.font.SysFont('timesnewroman', 20)
        font3 = pygame.font.SysFont('timesnewroman', 20)
        font4 = pygame.font.Font("Assets/Fonts/Merri/Merriweather-Regular.ttf", 18)

        if weather is not None:
            icon_name = weather.weather_icon_name
            icon_url = f"http://openweathermap.org/img/wn/{icon_name}@2x.png"
            status = weather.status
            temp = weather.temperature()['temp']
            feels_like = weather.temperature()['feels_like']
            humidity = weather.humidity
            wind = weather.wind()
            reference_time = weather.reference_time()
            reference_time = datetime.datetime.fromtimestamp(reference_time)
            percip_percent = weather.precipitation_probability
        else:
            icon_url = None
            status = "None"
            temp = -10
            feels_like = 67
            wind = {'speed': 60, 'deg': 0}
            humidity = 99
            reference_time = datetime.datetime.now()
            percip_percent = 0

        if status == "Thunderstorm":
            status = "Storm"

        # self.forecast_time = datetime.datetime.now() + datetime.timedelta(hours=delta_time)
        self.forecast_time = reference_time
        self.day_formatted = self.forecast_time.strftime("%m/%d")
        self.time_formatted = self.forecast_time.strftime("%I %p")
        self.day_text = font3.render(f"{self.day_formatted}", True, pallet_one)
        self.time_text = font3.render(f"{self.time_formatted}", True, pallet_one)
        self.small_info = font2.render(f"{status.capitalize()}", True, pallet_three)
        self.forecast_temp = font1.render(f"{round(temp)}°F", True, pallet_one)
        if percip_percent > 0.2:
            self.second_name = font2.render("Chance", True, pallet_three)
            self.second_data = font1.render(f"{round(percip_percent * 100)}%", True, pallet_one)
        else:
            self.second_name = font2.render("Feels like", True, pallet_three)
            self.second_data = font1.render(f"{round(feels_like)}°F", True, pallet_one)
        self.humidity_text = font2.render("Humidity", True, pallet_three)
        self.humidity_percent = font1.render(f"{humidity}%", True, pallet_one)
        self.wind_text = font2.render("Wind", True, pallet_three)
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

        pygame.draw.line(screen, pallet_two, (85, -10), (85, 300))
        screen.blit(self.day_text, self.day_text.get_rect(center=(42.5, -5)))
        screen.blit(self.time_text, self.time_text.get_rect(center=(42.5, 15)))
        screen.blit(self.pic, self.pic.get_rect(center=(42.5, 60)))
        screen.blit(self.small_info, self.small_info.get_rect(center=(42.5, 100)))
        screen.blit(self.forecast_temp, self.forecast_temp.get_rect(center=(42.5, 130)))
        screen.blit(self.second_name, self.second_name.get_rect(center=(42.5, 157)))
        screen.blit(self.second_data, self.second_data.get_rect(center=(42.5, 185)))
        screen.blit(self.humidity_text, self.humidity_text.get_rect(center=(42.5, 210)))
        screen.blit(self.humidity_percent, self.humidity_percent.get_rect(center=(42.5, 237)))
        screen.blit(self.wind_text, self.wind_text.get_rect(center=(42.5, 266)))
        screen.blit(self.wind_speed, self.wind_speed.get_rect(center=(42.5, 290)))

    def check_click(self, mouse_pos):
        if self.clicked_rect.collidepoint(mouse_pos):
            self.focused = True

    def draw(self, screen):
        if self.focused:
            if not self.focused_object:
                self.focused_object = FocusedForecast(self)
            self.focused_object.draw(screen)
        else:
            screen.blit(self.surf, (self.x, self.y))
            # pygame.draw.line(screen, pallet_two, (self.x + 85, self.y - 10), (self.x + 85, self.y + 300))
            # screen.blit(self.day_text, self.day_text.get_rect(center=(self.x + 42.5, self.y - 5)))
            # screen.blit(self.time_text, self.time_text.get_rect(center=(self.x + 42.5, self.y + 15)))
            # screen.blit(self.pic, self.pic.get_rect(center=(self.x + 42.5, self.y + 60)))
            # screen.blit(self.small_info, self.small_info.get_rect(center=(self.x + 42.5, self.y + 100)))
            # screen.blit(self.forecast_temp, self.forecast_temp.get_rect(center=(self.x + 42.5, self.y + 130)))
            # screen.blit(self.second_name, self.second_name.get_rect(center=(self.x + 42.5, self.y + 157)))
            # screen.blit(self.second_data, self.second_data.get_rect(center=(self.x + 42.5, self.y + 185)))
            # screen.blit(self.humidity_text, self.humidity_text.get_rect(center=(self.x + 42.5, self.y + 210)))
            # screen.blit(self.humidity_percent, self.humidity_percent.get_rect(center=(self.x + 42.5, self.y + 237)))
            # screen.blit(self.wind_text, self.wind_text.get_rect(center=(self.x + 42.5, self.y + 266)))
            # screen.blit(self.wind_speed, self.wind_speed.get_rect(center=(self.x + 42.5, self.y + 290)))
