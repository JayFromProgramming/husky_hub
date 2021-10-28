import io
import json
import os
import threading
from os import listdir
from os.path import isfile

import pygame
import datetime

from urllib.request import urlopen

pallet_one = (255, 206, 0)
pallet_two = (255, 255, 255)
pallet_three = (0, 0, 0)


def update_cache(serial_bytes, name):
    """
    Updates the radar cache with the given bytes
    :param serial_bytes: The bytes to save
    :param name: The name of the file to save
    :return: None
    """
    f = open(f"Caches/Radar_cache/KMQT_Frames/{name}.png", "wb")
    f.write(serial_bytes)
    f.close()


def scale_tile(tile, scale):
    """
    Scales the given tile to the given scale
    :param tile: The tile to scale
    :param scale: The scale to scale to
    :return: The scaled tile
    """
    return pygame.transform.scale(tile, (int(tile.get_width() * scale), int(tile.get_height() * scale)))


def load_frame(name, timestamp):
    """
    Loads the radar frame from the radar station with the given name
    :param name: The name of the frame to load
    :param timestamp: The timestamp of the frame to save to cache
    :return: None
    """
    image_str = urlopen(f"https://data.rainviewer.com/images/KMQT/{name}_0_source.png").read()
    update_cache(image_str, f"KMQT_{timestamp}")
    print(f"Loaded new frame [{name}] saved as [KMQT_{timestamp}.png]")


class Radar:

    def load_owm_tile(self, location):
        """
        Loads the tile from the OWM cache
        :param location: The location of the tile to load in the form of (x, y)
        :return: A pygame surface of the tile
        """
        layers = []
        surf = pygame.Surface((256, 256), pygame.SRCALPHA | pygame.HWSURFACE | pygame.ASYNCBLIT)
        for _, time in self.weather.radar_buffer.items():
            # For every item in the radar buffer format the tile to the surf
            if len(self.v2_layers):
                # If there are v2 layers
                name, delta, options = self.v2_layers[0]
                if _ != delta:
                    # If the delta is not the same as the current frame
                    continue
            else:
                if _ != 0:
                    break
            for entry in time:
                e_location, tile, layer_name, time, e_options = entry
                if location == e_location and layer_name in self.v1_layers:
                    image_file = io.BytesIO(tile)
                    layers.append(pygame.image.load(image_file).convert_alpha())
                for name, delta, options in self.v2_layers:
                    if location == e_location and layer_name == name and _ == delta and e_options == options:
                        image_file = io.BytesIO(tile)
                        layers.append(pygame.image.load(image_file).convert_alpha())
        for layer in layers:
            # For every layer in the layers list blit the layer to the surf
            surf.blit(layer, (0, 0))
        del layers  # Delete the layers list to free up memory
        return surf.convert_alpha()

    def text(self, text):
        """
        Returns a surface of the given text
        :param text: The text to render
        :return: The surface of the text
        """
        return self.text_font.render(text, True, pallet_one, pallet_three)

    def format_owm_tiles(self, screen: pygame.Surface):
        """
        Formats the OWM tiles to the screen
        :param screen: The screen to format the tiles to
        :return: None
        """
        print("Reformatting tiles")
        self.tile_surf = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA | pygame.HWSURFACE | pygame.ASYNCBLIT)

        self.tile_surf.blit(scale_tile(self.load_owm_tile((16, 22)), self.scale),
                            self.tile.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2)))
        self.tile_surf.blit(scale_tile(self.load_owm_tile((15, 22)), self.scale), self.tile.get_rect(
                center=((screen.get_width() / 2) - self.tile.get_rect().width, screen.get_height() / 2)))
        self.tile_surf.blit(scale_tile(self.load_owm_tile((17, 22)), self.scale), self.tile.get_rect(
                center=((screen.get_width() / 2) + self.tile.get_rect().width, screen.get_height() / 2)))
        self.tile_surf.blit(scale_tile(self.load_owm_tile((16, 23)), self.scale), self.tile.get_rect(
                center=(screen.get_width() / 2, screen.get_height() / 2 + self.tile.get_rect().height)))
        self.tile_surf.blit(scale_tile(self.load_owm_tile((15, 23)), self.scale), self.tile.get_rect(
                center=((screen.get_width() / 2) - self.tile.get_rect().width,
                        screen.get_height() / 2 + self.tile.get_rect().height)))
        self.tile_surf.blit(scale_tile(self.load_owm_tile((17, 23)), self.scale), self.tile.get_rect(
                center=((screen.get_width() / 2) + self.tile.get_rect().width,
                        screen.get_height() / 2 + self.tile.get_rect().height)))
        self.tile_surf = self.tile_surf.convert_alpha()
        self.radar_tiles_last_amount = self.weather.radar_refresh_amount

    def __init__(self, log, weather):
        """
        Initializes the radar viewer
        :param log: The logger to use
        :param weather: The OpenWeatherWeather object to use
        """
        # 2,445.984905 meters per pixel on tile 22
        # 1680.0299963321 meters per pixel for the radar image
        self.weather = weather
        self.scale = 2445.984905 / 1680.0299963321
        self.radar_tiles_last_amount = 0
        self.current_frame_number = 0
        self.last_frame = None
        self.radar_display = True
        self.playback_buffer = []
        self.tile_surf = None
        self.v1_layers = []
        self.v2_layers = [("CL", 0, "")]

        self.log = log  # Zoom 6
        self.background_left = scale_tile(pygame.image.load(os.path.join("Assets/Tiles/left.png")), self.scale).convert()  # 15, 22 or 15, 41
        self.background_center = scale_tile(pygame.image.load(os.path.join("Assets/Tiles/center.png")), self.scale).convert()  # 16, 22 or 16, 41
        self.background_right = scale_tile(pygame.image.load(os.path.join("Assets/Tiles/right.png")), self.scale).convert()  # 17, 22 or 17, 41
        self.background_bottom = scale_tile(pygame.image.load(os.path.join("Assets/Tiles/bottom.png")), self.scale).convert()  # 16, 23 or 16, 40
        self.background_bottom_left = scale_tile(pygame.image.load(os.path.join("Assets/Tiles/bottom_left.png")), self.scale).convert()
        self.background_bottom_right = scale_tile(pygame.image.load(os.path.join("Assets/Tiles/bottom_right.png")), self.scale).convert()
        self.text_font = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 11)
        self.radar_directory_url = "https://data.rainviewer.com/images/KMQT/0_products.json"
        # threading.Thread(target=self.weather.update_weather_map, args=(self.v1_layers, self.v2_layers)).start()

        self.tile = self.background_center
        self.screen = None

        try:
            self.radar_directory: dict = json.loads(urlopen(self.radar_directory_url).read())
        except Exception as e:
            print(f"Failed to load radar because {e}")
        self.playing = False

    def update_radar(self):
        """
        Updates the radar data
        :return: None
        """
        self.playback_buffer = []
        self.last_frame = None
        print("Updating radar")

        try:
            self.radar_directory: dict = json.loads(urlopen(self.radar_directory_url, timeout=2).read())
        except Exception as e:
            print(f"Failed to load radar because {e}")
            return

        # image_str = urlopen("https://tilecache.rainviewer.com/v2/radar/nowcast_d63c46f420ce/256/6/16/22/1/1_0.png").read()
        #
        # self.tile_radar_center = scale_tile(pygame.image.load(image_file), self.scale)
        if self.screen:
            self.format_owm_tiles(self.screen)

        for frame in self.radar_directory["products"][0]["scans"]:
            name = frame["name"].split("_2_map.png", 1)[0]
            timestamp = frame["timestamp"]
            if not os.path.exists(os.path.join(f"Caches/Radar_cache/KMQT_Frames/KMQT_{timestamp}.png")):
                thread = threading.Thread(target=load_frame, args=(name, timestamp))
                thread.start()
                print(f"Queued frame load for: {name}")
            # self.playback_buffer.append((radar_raw, timestamp))
        # self.sort_and_load_frames()

    def sort_and_load_frames(self):
        """
        Sorts the frames and loads them into the playback buffer in time order
        :return: None
        """

        threading.Thread(target=self.weather.update_weather_map, args=(self.v1_layers, self.v2_layers)).start()

        self.playback_buffer = [f for f in listdir("Caches/Radar_cache/KMQT_Frames/") if isfile(os.path.join("Caches/Radar_cache/KMQT_Frames/", f))]

        self.playback_buffer.sort(key=lambda sort_frame: int(sort_frame.split("_")[1].split(".")[0]))

        while len(self.playback_buffer) > 376:
            removed = self.playback_buffer.pop(0)
            os.remove(os.path.join(f"Caches/Radar_cache/KMQT_Frames/{removed}"))
            print(f"Removing 375th radar cache item [{removed}]")

        self.current_frame_number = len(self.playback_buffer) - 1

    def play_pause(self):
        """
        Toggles the playback state
        :return: None
        """
        self.playing = not self.playing

    def jump_too_now(self):
        """
        Jumps to the current time
        :return: None
        """
        self.current_frame_number = len(self.playback_buffer) - 1
        self.playing = False

    def draw(self, screen: pygame.Surface):
        """
        Draws the radar to the screen
        :param screen: The screen to draw to
        :return: None
        """
        self.screen = screen

        if self.weather.radar_refresh_amount != self.radar_tiles_last_amount:
            self.format_owm_tiles(screen)

        if self.last_frame:
            radar, last_timestamp = self.last_frame
        else:
            self.sort_and_load_frames()
            last_timestamp = 0

        if (self.last_frame is not None or not self.playing) and self.current_frame_number > 0:
            frame_file = self.playback_buffer[self.current_frame_number]
            f = open(f"Caches/Radar_cache/KMQT_Frames/{frame_file}", "rb")
            image_str = f.read()
            f.close()
            image_file = io.BytesIO(image_str)
            radar = pygame.image.load(image_file).convert_alpha()
            timestamp = int(frame_file.split("_")[1].split(".")[0])
            self.last_frame = (radar, timestamp)
        else:
            radar, timestamp = self.last_frame

        screen.blit(self.background_center, self.background_center.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2)))
        screen.blit(self.background_left, self.background_left.get_rect(
            center=((screen.get_width() / 2) - self.background_left.get_rect().width, screen.get_height() / 2)))
        screen.blit(self.background_right, self.background_right.get_rect(
            center=((screen.get_width() / 2) + self.background_right.get_rect().width, screen.get_height() / 2)))
        screen.blit(self.background_bottom, self.background_bottom.get_rect(
            center=((screen.get_width() / 2), (screen.get_height() / 2) + self.background_bottom.get_rect().height)))
        screen.blit(self.background_bottom_right, self.background_bottom_right.get_rect(
            center=((screen.get_width() / 2) + self.background_bottom_right.get_rect().width, (screen.get_height() / 2)
                    + self.background_bottom_right.get_rect().height)))
        screen.blit(self.background_bottom_left, self.background_bottom_left.get_rect(
            center=((screen.get_width() / 2) - self.background_bottom_left.get_rect().width, (screen.get_height() / 2)
                    + self.background_bottom_left.get_rect().height)))
        if self.radar_display:
            overscan_x = int((radar.get_width() - 800) / 2)
            overscan_y = int((radar.get_height() - 445) / 2)
            screen.blit(radar, radar.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 + 50)),
                        area=(0, 0, radar.get_width() - overscan_x, radar.get_width() - overscan_y))

        if self.tile_surf:
            screen.blit(self.tile_surf, (0, 0))

        screen.blit(self.text(datetime.datetime.fromtimestamp(timestamp).
                              strftime(f"Frame time: %Y-%m-%d %H:%M:%S | Frame: {self.current_frame_number}/{len(self.playback_buffer) - 1}"
                                       f" | Overlays: v1{self.v1_layers} + v2{self.v2_layers}")), (0, 0))
        screen.blit(self.text(f"Frame delta: {datetime.timedelta(seconds=timestamp - last_timestamp)}"
                              f" Time delta: T-{(datetime.datetime.now() - datetime.datetime.fromtimestamp(timestamp))}"),
                    (0, 14))

        if self.playing:
            self.current_frame_number += 1
            if self.current_frame_number > len(self.playback_buffer) - 1:
                self.current_frame_number = -30
