import io
import json
import logging
import os
import threading
import time
import traceback
import urllib.error
from urllib.request import urlopen

import dill

from pyowm.owm import OWM

api_file = "../APIKey.json"
cache_location = "Caches/weather.cache"


class OpenWeatherWrapper:

    def __init__(self, log, current_weather_refresh_rate=2, future_weather_refresh_rate=15, is_host=True):
        """
        Initialize the OpenWeatherWrapper class and API wrapper
        :param log: The logger to use
        :param current_weather_refresh_rate: The refresh rate for the current weather api
        :param future_weather_refresh_rate: The refresh rate for the OneCall weather api
        :param is_host: Whether or not this is the host which is used to reduce the amount of api calls when using multiple devices
        """
        self.log: logging = log
        if os.path.isfile(api_file):
            with open(api_file) as f:
                keys = json.load(f)
                self.owm = OWM(keys['key'])
                self.api_key = keys['key']
                self.main_server = keys['rPi_address']
                self.main_server_password = keys['rPi_password']
                self.main_server_filepath = keys['rPi_file_path']
        else:
            self.owm = OWM("Not a key")
            log.error("No API Key file found")
            # raise FileNotFoundError

        self.is_host = is_host
        self.mgr = self.owm.weather_manager()
        self._current_max_refresh = current_weather_refresh_rate
        self._forecast_max_refresh = future_weather_refresh_rate
        self._radar_max_refresh = 30
        self._future_max_refresh = 45
        self._last_current_refresh = 0
        self._last_forecast_refresh = 0
        self._last_radar_refresh = 0
        self._last_cache_refresh = 0
        self.radar_refresh_amount = 0
        self._last_future_refresh = 0
        self.current_weather = None
        self.weather_forecast = None
        self.one_call = None
        self.radar_buffer = {}
        self.log = log
        self._read_cache()

    def _read_cache(self):
        """
        Reads the cache file and loads the data into the class
        :return: None
        """
        if os.path.isfile(cache_location):
            self.log.info("Loading weather cache")
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
                    self.log.warning("Cache File Corrupted")
                except Exception as e:
                    self.log.warning(f"Failed to load cached weather because: {e}")

    def _load_pi_cache(self):
        """
        Loads all the data from the host machine, in the form of a dill'd file
        :return: None
        """
        pass
        # if self._last_cache_refresh < time.time() - 120 and not self.is_host and False:
        #     import paramiko
        #     ssh = paramiko.SSHClient()
        #     ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #     ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        #     ssh.connect(self.main_server, username="pi", password=self.main_server_password)
        #     sftp = ssh.open_sftp()
        #     sftp.get(f"{self.main_server_filepath}/Caches/weather.cache", cache_location)
        #     sftp.close()
        #     ssh.close()
        #     self._read_cache()
        #     self._last_cache_refresh = time.time()

    def _save_cache(self):
        """
        Saves the cache to the weather cache file
        :return: None
        """
        with open(cache_location, 'wb') as outp:
            self.log.info("Saving current weather to cache")
            dill.dump(self, outp)
            outp.close()

    def update_current_weather(self):
        """
        Updates the current weather data
        :return: True if the weather was updated, None if the weather was not updated and False if there was an error
        """
        self._load_pi_cache()
        if self._last_current_refresh < time.time() - self._current_max_refresh * 60:
            print("Updating Current")
            self._last_current_refresh = time.time()
            try:
                self.current_weather = self.mgr.weather_at_place('Houghton,US').weather
                self._save_cache()
            except Exception as e:
                self.log.warning(f"Unable to load weather: {e}")
                return False
            return True
        return None

    def update_forecast_weather(self):
        """
        Updates the forecast weather data
        :return: True if the weather was updated, None if the weather was not updated and False if there was an error
        """
        self._load_pi_cache()
        if self._last_forecast_refresh < time.time() - self._forecast_max_refresh * 60:
            print("Updating Forecast")
            self._last_forecast_refresh = time.time()
            try:
                self.one_call = self.mgr.one_call(lat=47.1219, lon=-88.569)
                self._save_cache()
            except Exception as e:
                self.log.warning(f"Unable to load forecast: {e}\nTraceback: {traceback.format_exc()}")
                return False
            return True
        return None

    def update_future_weather(self):
        """
        Updates the 4 day forecast weather data
        :return: None
        """
        self._load_pi_cache()
        if self._last_future_refresh < time.time() - self._future_max_refresh * 60:
            print("Updating Future")
            try:
                self._last_future_refresh = time.time()
                self.weather_forecast = self.mgr.forecast_at_place('Houghton,US', '1h', limit=None).weathers
                self._save_cache()
            except Exception as e:
                self.log.warning(f"Unable to load future: {e}")
                return False
            return True
        return None

    def _load_future_radar_tile(self, location, layer_name, future, options=""):
        """
        Loads the radar tiles for a particular layer and future time
        :param location: The X,Y location of the radar tile in the maps grid format Ex. (16, 22)
        :param layer_name: The OWM layer name to load Ex. "WND" or "PR0"
        :param future: The Unix time in seconds to load the tile for
        :param options: Any additional options to pass to the OWM API
        :return: The image of the radar tile in 256x256 PNG format
        """
        x, y = location
        date = int(time.time()) + future
        print(f"Loading {location} {layer_name}+{options} {future}")
        entry = [item for item in self.radar_buffer[future] if item[0] == location and item[2] == layer_name and item[4] == options]

        if len(entry):
            if entry[0][3][2] > time.time() - 30 * 60:
                print(f"{location} in cache for {layer_name}:{future}")
                self.radar_refresh_amount += 1
                return
            else:
                print(f"{location} expired in cache for {layer_name}:{future} evicting cache")
                self.radar_buffer[future] = []
        url = f"https://maps.openweathermap.org/maps/2.0/weather/{layer_name}/6/{x}/{y}?date={int(date)}{options}&appid={self.api_key}"
        try:
            data = urlopen(url).read()
            self.radar_buffer[future].append(((x, y), data, layer_name, (future, date, time.time()), options))
            self.radar_refresh_amount += 1
        except urllib.error.HTTPError as e:
            print(f"Tile get HTTP Error({e}): {url}")

    def _load_radar_tile(self, tile_manager, location, layer_name):
        """
        Loads the radar tiles for a particular layer at the current time
        :param tile_manager: The OWM tile manager to use to load the tiles
        :param location: The X,Y location of the radar tile in the maps grid format Ex. (16, 22)
        :param layer_name: The OWM layer name to load Ex. "WND" or "PR0"
        :return: None
        """
        x, y = location
        tile = tile_manager.get_tile(x=x, y=y, zoom=6).image.recent_data
        self.radar_buffer[0].append(((x, y), tile, layer_name, (0, 0, time.time())))
        self.radar_refresh_amount += 1

    def _load_layer(self, layer: str):
        """
        Loads the all the layer tiles for a particular layer at the current time
        :param layer: The OWM layer name to load Ex. "WND" or "PR0"
        :return: None
        """
        tile_manager = self.owm.tile_manager(layer)
        self._load_radar_tile(tile_manager, (15, 22), layer)
        self._load_radar_tile(tile_manager, (16, 22), layer)
        self._load_radar_tile(tile_manager, (17, 22), layer)
        self._load_radar_tile(tile_manager, (15, 23), layer)
        self._load_radar_tile(tile_manager, (16, 23), layer)
        self._load_radar_tile(tile_manager, (17, 23), layer)
        print(f"Loaded owm layer {layer}")
        self._save_cache()

    def _load_future_layers(self, layer: str, future: int, options=""):
        """
        Loads the all the layer tiles for a particular layer at the a particular future time
        :param layer: The OWM layer name to load Ex. "WND" or "PR0"
        :param future: The Unix time in seconds to load the tiles for Ex. 3600 for 1 hour
        :param options: The additional options to pass to the OWM API
        :return: None
        """
        print(f"Loading owm forecast layer {layer}")
        if future not in self.radar_buffer:
            self.radar_buffer[future] = []
        self._load_future_radar_tile((15, 22), layer, future, options=options)
        self._load_future_radar_tile((16, 22), layer, future, options=options)
        self._load_future_radar_tile((17, 22), layer, future, options=options)
        self._load_future_radar_tile((15, 23), layer, future, options=options)
        self._load_future_radar_tile((16, 23), layer, future, options=options)
        self._load_future_radar_tile((17, 23), layer, future, options=options)
        print(f"Loaded owm forecast layer {layer}")
        self._save_cache()

    def update_weather_map(self, v1_layers, v2_layers):
        """
        Updates the weather map cache with the layers specified
        :param v1_layers: The list of OWM layer names to load for the current time using the V1 API, Ex. ["wind_new", "pressure_new"]
        :param v2_layers: The list of OWM layer names to load for the current time using the V2 API, Ex. [("WND", 3600, ""), ("PR0", 3600, "")])
        :return: None
        """
        # v1_layers, v2_layers = layers
        if self._last_radar_refresh < time.time() - self._radar_max_refresh * 60:
            self.log.info("Clearing radar cache")
            # self.radar_buffer = {}
            self._last_radar_refresh = time.time()

        if self._last_radar_refresh < time.time() - (self._radar_max_refresh / 2) * 60:
            print("Refreshing current cloud cover layer")
            # self.radar_buffer[0] = []

        for layer in v1_layers:
            threading.Thread(target=self._load_layer, args=layer).start()

        for layer, delta, args in v2_layers:
            threading.Thread(target=self._load_future_layers, args=(layer, delta, args)).start()

    @staticmethod
    def get_angle_arrow(degree):
        """
        Returns the arrow character for the given angle
        :param degree: The angle to get the arrow for
        :return: The arrow character for the given angle
        """
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
        """
        Returns the UV index scale name for the given UV index
        :param uvi: The UV index to get the scale for
        :return: The UV index scale name for the given UV index
        """
        if uvi is None:
            return "Unknown"
        elif uvi < 3:
            return "Low"
        elif uvi < 6:
            return "Moderate"
        elif uvi < 8:
            return "High"
        elif uvi < 11:
            return "Very High"
        else:
            return "Extreme"
