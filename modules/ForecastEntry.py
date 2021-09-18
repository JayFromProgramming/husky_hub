import io
import pygame
import datetime

from urllib.request import urlopen
import logging as log

from OpenWeatherWrapper import OpenWeatherWrapper

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)


class ForecastEntry:

    def __init__(self, screen, location, weather, delta_time, icon_cache, icon):
        """Houses a forecast"""
        self.x, self.y = location
        self.delta_time = delta_time
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
            rain = weather.rain
            snow = weather.snow
            reference_time = weather.reference_time()
            reference_time = datetime.datetime.fromtimestamp(reference_time)
            percip_percent = weather.precipitation_probability
        else:
            # icon_url = "http://openweathermap.org/img/wn/01d@2x.png"
            icon_url = None
            status = "None"
            temp = -10
            feels_like = 67
            wind = {'speed': 60, 'deg': 0}
            humidity = 99
            rain = None
            snow = None
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
            self.second_data = font1.render(f"{round(percip_percent*100)}%", True, pallet_one)
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
        except Exception:
            self.pic = icon

    def draw(self, screen):
        pygame.draw.line(screen, pallet_two, (self.x + 85, self.y - 10), (self.x + 85, self.y + 300))
        screen.blit(self.day_text, self.day_text.get_rect(center=(self.x + 42.5, self.y - 5)))
        screen.blit(self.time_text, self.time_text.get_rect(center=(self.x + 42.5, self.y + 15)))
        screen.blit(self.pic, self.pic.get_rect(center=(self.x + 42.5, self.y + 60)))
        screen.blit(self.small_info, self.small_info.get_rect(center=(self.x + 42.5, self.y + 100)))
        screen.blit(self.forecast_temp, self.forecast_temp.get_rect(center=(self.x + 42.5, self.y + 130)))
        screen.blit(self.second_name, self.second_name.get_rect(center=(self.x + 42.5, self.y + 157)))
        screen.blit(self.second_data, self.second_data.get_rect(center=(self.x + 42.5, self.y + 185)))
        screen.blit(self.humidity_text, self.humidity_text.get_rect(center=(self.x + 42.5, self.y + 210)))
        screen.blit(self.humidity_percent, self.humidity_percent.get_rect(center=(self.x + 42.5, self.y + 237)))
        screen.blit(self.wind_text, self.wind_text.get_rect(center=(self.x + 42.5, self.y + 266)))
        screen.blit(self.wind_speed, self.wind_speed.get_rect(center=(self.x + 42.5, self.y + 290)))
