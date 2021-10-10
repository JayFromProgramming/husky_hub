import json
import os
import time
import dill
from pyowmmodifed import OWM
from pyowm.tiles.enums import MapLayerEnum
from concurrent import futures

api_file = "../APIKey.json"
cache_location = "Caches/weather.cache"


class OpenWeatherWrapper:

    def __init__(self, log, current_weather_refresh_rate=2, future_weather_refresh_rate=15):
        if os.path.isfile(api_file):
            with open(api_file) as f:
                apikey = json.load(f)
                self.owm = OWM(apikey['key'])
        else:
            log.critial("No api key file present")
            # raise FileNotFoundError

        self.mgr = self.owm.weather_manager()
        self._current_max_refresh = current_weather_refresh_rate
        self._future_max_refresh = future_weather_refresh_rate
        self._radar_max_refresh = 15
        self._last_current_refresh = 0
        self._last_future_refresh = 0
        self._last_radar_refresh = 0
        self.current_weather = None
        self.one_call = None
        self.radar_buffer = []

        if os.path.isfile(cache_location):
            log.info("Loading weather cache")
            with open(cache_location, 'rb') as inp:
                try:
                    cache = dill.load(inp)
                    self.current_weather = cache.current_weather
                    self.one_call = cache.one_call
                    self.radar_buffer = cache.radar_buffer
                    self._last_current_refresh = cache._last_current_refresh
                    self._last_future_refresh = cache._last_future_refresh
                    self._last_radar_refresh = cache._last_radar_refresh
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

    def update_future_weather(self):
        """Update future weather values"""
        if self._last_future_refresh < time.time() - self._future_max_refresh * 60:
            print("Updating Forecast")
            self._last_future_refresh = time.time()
            try:
                self.one_call = self.mgr.one_call(lat=47.1219, lon=-88.569, units='imperial')
                self._save_cache()
            except Exception as e:
                self.log.warning(f"Unable to load forecast: {e}")
                return True
            return True
        return None

    def _load_radar_tile(self, tile_manager, x, y):
        """"""
        tile = tile_manager.get_tile(x=x, y=y, zoom=6).image.data
        self.radar_buffer.append(((x, y), tile))

    def update_weather_map(self):
        """Update radar"""
        if self._last_radar_refresh < time.time() - self._radar_max_refresh * 60:
            print("Requesting Radar From OpenWeather")
            self.radar_buffer = []
            tile_manager = self.owm.tile_manager("precipitation_new")
            self._load_radar_tile(tile_manager, 15, 22)
            self._load_radar_tile(tile_manager, 16, 22)
            self._load_radar_tile(tile_manager, 17, 22)
            self._last_radar_refresh = time.time()
            self._save_cache()
            # image_file = io.BytesIO(image_str)
            # print(self.radar_buffer)

    @staticmethod
    def get_angle_arrow(degree):
        def offset(check):
            return (degree - check + 180 + 360) % 360 - 180

        if 22.5 >= offset(0) >= -22.5:
            return "↑"
        if 22.5 >= offset(45) >= -22.5:
            return "↗"
        if 22.5 >= offset(90) >= -22.5:
            return "→"
        if 22.5 >= offset(135) >= -22.5:
            return "↘"
        if 22.5 >= offset(180) >= -22.5:
            return "↓"
        if 22.5 >= offset(225) >= -22.5:
            return "↙"
        if 22.5 >= offset(270) >= -22.5:
            return "←"
        if 22.5 >= offset(315) >= -22.5:
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
