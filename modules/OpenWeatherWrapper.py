import io
import json
import os
import threading
import time
from urllib.request import urlopen

import dill
from pyowm.owm import OWM

api_file = "../APIKey.json"
cache_location = "Caches/weather.cache"


class OpenWeatherWrapper:

    def __init__(self, log, current_weather_refresh_rate=2, future_weather_refresh_rate=15):
        if os.path.isfile(api_file):
            with open(api_file) as f:
                apikey = json.load(f)
                self.owm = OWM(apikey['key'])
                self.api_key = apikey['key']
        else:
            log.critial("No api key file present")
            # raise FileNotFoundError

        self.mgr = self.owm.weather_manager()
        self._current_max_refresh = current_weather_refresh_rate
        self._forecast_max_refresh = future_weather_refresh_rate
        self._radar_max_refresh = 5
        self._future_max_refresh = 45
        self._last_current_refresh = 0
        self._last_forecast_refresh = 0
        self._last_radar_refresh = 0
        self._last_future_refresh = 0
        self.current_weather = None
        self.weather_forecast = None
        self.one_call = None
        self.radar_buffer = []

        if os.path.isfile(cache_location):
            log.info("Loading weather cache")
            with open(cache_location, 'rb') as inp:
                try:
                    cache: OpenWeatherWrapper = dill.load(inp)
                    self.current_weather = cache.current_weather
                    self.one_call = cache.one_call
                    self.radar_buffer = cache.radar_buffer
                    self.weather_forecast = cache.weather_forecast
                    self._last_current_refresh = cache._last_current_refresh
                    self._last_forecast_refresh = cache._last_forecast_refresh
                    self._last_radar_refresh = cache._last_radar_refresh
                    self._last_future_refresh = cache._last_future_refresh
                except EOFError:
                    log.warning("Cache File Corrupted")
                except Exception as e:
                    log.warning(f"Failed to load cached weather because: {e}")
        self.log = log

    def _save_cache(self):
        with open(cache_location, 'wb') as outp:
            self.log.info("Saving current weather to cache")
            dill.dump(self, outp)
            outp.close()

    def update_current_weather(self):
        """Update current weather values"""
        if self._last_current_refresh < time.time() - self._current_max_refresh * 60:
            print("Updating Current")
            self._last_current_refresh = time.time()
            try:
                self.current_weather = self.mgr.weather_at_place('Houghton,US').weather
                self._save_cache()
            except Exception as e:
                self.log.warning(f"Unable to load weather: {e}")
                return True
            return True
        return None

    def update_forecast_weather(self):
        """Update one call forecast weather values"""
        if self._last_forecast_refresh < time.time() - self._forecast_max_refresh * 60:
            print("Updating Forecast")
            self._last_forecast_refresh = time.time()
            try:
                self.one_call = self.mgr.one_call(lat=47.1219, lon=-88.569, units='imperial')
                self._save_cache()
            except Exception as e:
                self.log.warning(f"Unable to load forecast: {e}")
                return True
            return True
        return None

    def update_future_weather(self):
        """Update the next 4 day forecast"""
        if self._last_future_refresh < time.time() - self._future_max_refresh * 60 or True:
            print("Updating Future")
            self._last_future_refresh = time.time()
            self.weather_forecast = self.mgr.forecast_at_place('Houghton,US', '1h', limit=None).weathers
            self._save_cache()

    def _load_future_radar_tile(self, location, layer_name, future, options=""):
        x, y = location
        date = time.time() + future
        data = urlopen(f"https://maps.openweathermap.org/maps/2.0/weather/"
                       f"{layer_name}/6/{x}/{y}?date={int(date)}{options}&appid={self.api_key}").read()
        self.radar_buffer.append(((x, y), data, layer_name))

    def _load_radar_tile(self, tile_manager, location, layer_name):
        """"""
        x, y = location
        tile = tile_manager.get_tile(x=x, y=y, zoom=6).image.data
        self.radar_buffer.append(((x, y), tile, layer_name))

    def _load_layer(self, ob, layer: str):
        print(f"Loading owm layer {layer}")
        tile_manager = self.owm.tile_manager(layer)

        self._load_radar_tile(tile_manager, (15, 22), layer)
        self._load_radar_tile(tile_manager, (16, 22), layer)
        self._load_radar_tile(tile_manager, (17, 22), layer)
        self._load_radar_tile(tile_manager, (15, 23), layer)
        self._load_radar_tile(tile_manager, (16, 23), layer)
        self._load_radar_tile(tile_manager, (17, 23), layer)
        print(f"Loaded owm layer {layer}")
        self._save_cache()

    def _load_future_layers(self, ob, layer: str, future: int, options=""):
        print(f"Loading owm forecast layer {layer}")
        self._load_future_radar_tile((15, 22), layer, future, options=options)
        self._load_future_radar_tile((16, 22), layer, future, options=options)
        self._load_future_radar_tile((17, 22), layer, future, options=options)
        self._load_future_radar_tile((15, 23), layer, future, options=options)
        self._load_future_radar_tile((16, 23), layer, future, options=options)
        self._load_future_radar_tile((17, 23), layer, future, options=options)
        print(f"Loaded owm forecast layer {layer}")
        self._save_cache()

    def update_weather_map(self, v1_layers, v2_layers):
        """Update radar"""
        # v1_layers, v2_layers = layers
        if self._last_radar_refresh < time.time() - self._radar_max_refresh * 60:
            print("Requesting Radar From OpenWeather")
            self.radar_buffer = []
            for layer in v1_layers:
                threading.Thread(target=self._load_layer, args=(self, layer)).start()

            for layer, delta, args in v2_layers:
                threading.Thread(target=self._load_future_layers, args=(self, layer, delta)).start()

            self._last_radar_refresh = time.time()
            # image_file = io.BytesIO(image_str)
            # print(self.radar_buffer)

    @staticmethod
    def get_angle_arrow(degree):
        def offset(check):
            return (degree - check + 180 + 360) % 360 - 180

        if 22.5 >= offset(0) >= -22.5:
            return "↑"
        elif 22.5 >= offset(45) >= -22.5:
            return "↗"
        elif 22.5 >= offset(90) >= -22.5:
            return "→"
        elif 22.5 >= offset(135) >= -22.5:
            return "↘"
        elif 22.5 >= offset(180) >= -22.5:
            return "↓"
        elif 22.5 >= offset(225) >= -22.5:
            return "↙"
        elif 22.5 >= offset(270) >= -22.5:
            return "←"
        elif 22.5 >= offset(315) >= -22.5:
            return "↖"
        return ""

    @staticmethod
    def uvi_scale(uvi):
        if uvi < 3:
            return "Low"
        elif uvi < 6:
            return "Moderate"
        elif uvi < 8:
            return "High"
        elif uvi < 11:
            return "Very High"
        else:
            return "Extreme"
