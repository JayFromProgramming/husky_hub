import io
import json
import os
import threading
import time
from os import listdir
from os.path import isfile

import pygame
import datetime

from urllib.request import urlopen

pallet_one = (255, 206, 0)
pallet_two = (255, 255, 255)
pallet_three = (0, 0, 0)


def update_cache(serial_bytes, name):
    f = open(f"Caches/Radar_cache/{name}.png", "wb")
    f.write(serial_bytes)
    f.close()


def scale_tile(tile, scale):
    return pygame.transform.scale(tile, (int(tile.get_width() * scale), int(tile.get_height() * scale)))


class Radar:

    def load_frame(self, name, timestamp):
        image_str = urlopen(f"https://data.rainviewer.com/images/KMQT/{name}_0_source.png").read()
        update_cache(image_str, f"KMQT_{timestamp}")
        print(f"Loaded new frame [{name}] saved as [KMQT_{timestamp}.png]")

    def text(self, text):
        return self.text_font.render(text, True, pallet_one, pallet_three)

    def __init__(self, log):
        # 2,445.984905 meters per pixel on tile 22
        # 1680.0299963321 meters per pixel for the radar image
        scale = 2445.984905 / 1680.0299963321
        self.current_frame_number = 0
        self.last_frame = None
        self.playback_buffer = []
        self.log = log  # Zoom 6
        self.background_left = pygame.image.load(os.path.join("Assets/Tiles/left.png"))  # 15, 22 or 15, 41
        self.background_center = pygame.image.load(os.path.join("Assets/Tiles/center.png"))  # 16, 22 or 16, 41
        self.background_right = pygame.image.load(os.path.join("Assets/Tiles/right.png"))  # 17, 22 or 17, 41
        self.background_bottom = pygame.image.load(os.path.join("Assets/Tiles/bottom.png"))  # 16, 23 or 16, 40
        self.text_font = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 11)
        self.radar_directory_url = "https://data.rainviewer.com/images/KMQT/0_products.json"
        self.background_left = scale_tile(self.background_left, scale)
        self.background_center = scale_tile(self.background_center, scale)
        self.background_right = scale_tile(self.background_right, scale)
        self.background_bottom = scale_tile(self.background_bottom, scale)
        try:
            self.radar_directory = json.loads(urlopen(self.radar_directory_url).read())
        except Exception as e:
            print(f"Failed to load radar because {e}")
        self.playing = False

    def update_radar(self):
        self.playback_buffer = []
        print("Updating radar")
        try:
            self.radar_directory = json.loads(urlopen(self.radar_directory_url).read())
        except Exception as e:
            print(f"Failed to load radar because {e}")
        for frame in self.radar_directory["products"][0]["scans"]:
            name = frame["name"].split("_2_map.png", 1)[0]
            timestamp = frame["timestamp"]
            if not os.path.exists(os.path.join(f"Caches/Radar_cache/KMQT_{timestamp}.png")):
                thread = threading.Thread(target=self.load_frame, args=(name, timestamp))
                thread.start()
                print(f"Queued frame load for: {name}")
            # self.playback_buffer.append((radar_raw, timestamp))

        self.playback_buffer = [f for f in listdir("Caches/Radar_cache/") if isfile(os.path.join("Caches/Radar_cache/", f))]

        self.playback_buffer.sort(key=lambda sort_frame: int(sort_frame.split("_")[1].split(".")[0]))

        while len(self.playback_buffer) > 301:
            removed = self.playback_buffer.pop(0)
            os.remove(os.path.join(f"Caches/Radar_cache/{removed}"))
            print(f"Removing 300th radar cache item [{removed}]")

        self.current_frame_number = len(self.playback_buffer) - 1

    def play_pause(self):
        self.playing = not self.playing

    def jump_too_now(self):
        self.current_frame_number = len(self.playback_buffer) - 1
        self.playing = False

    def draw(self, screen):
        if self.last_frame:
            radar, last_timestamp = self.last_frame
        else:
            last_timestamp = 0
        if (self.last_frame is not None or not self.playing) and self.current_frame_number > 0:
            frame_file = self.playback_buffer[self.current_frame_number]
            f = open(f"Caches/Radar_cache/{frame_file}", "rb")
            image_str = f.read()
            f.close()
            image_file = io.BytesIO(image_str)
            radar = pygame.image.load(image_file)
            timestamp = int(frame_file.split("_")[1].split(".")[0])
            self.last_frame = (radar, timestamp)
        else:
            radar, timestamp = self.last_frame

        screen.blit(self.background_center, self.background_center.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2)))
        screen.blit(self.background_left, self.background_left.get_rect(
            center=((screen.get_width() / 2)-self.background_left.get_rect().width, screen.get_height() / 2)))
        screen.blit(self.background_right, self.background_right.get_rect(
            center=((screen.get_width() / 2) + self.background_right.get_rect().width, screen.get_height() / 2)))
        screen.blit(self.background_bottom, self.background_bottom.get_rect(
            center=((screen.get_width() / 2), (screen.get_height() / 2) + self.background_bottom.get_rect().height)))
        screen.blit(self.text(datetime.datetime.fromtimestamp(timestamp).
                              strftime(f"Frame time: %Y-%m-%d %H:%M:%S Frame: {self.current_frame_number}/{len(self.playback_buffer) - 1}")), (0, 0))
        screen.blit(self.text(f"Frame delta: {datetime.timedelta(seconds=timestamp-last_timestamp)}"),
                    (0, 14))
        screen.blit(radar, radar.get_rect(center=(screen.get_width() / 2, screen.get_height() / 2 + 50)))
        if self.playing:
            self.current_frame_number += 1
            if self.current_frame_number > len(self.playback_buffer) - 1:
                self.current_frame_number = -30
