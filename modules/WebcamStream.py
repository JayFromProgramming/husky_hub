import concurrent
import http.client
import json
import math
import os
import socket
import threading
import urllib.error

import pygame
import time
import io
from urllib.request import urlopen

camera_path = "Assets/Configs/Cameras.json"
pallet_one = (255, 206, 0)
pallet_two = (255, 255, 255)
pallet_three = (0, 0, 0)


class CampusCams:

    def text(self, text):
        return self.text_font.render(text, True, pallet_two, pallet_three)

    def __init__(self, logs, static_images, live_mode_enable):
        if os.path.exists(camera_path):
            with open(camera_path, "r") as f:
                self.cameras = json.load(f)
        else:
            raise FileNotFoundError("No Camera Config")
        self.no_image, self.husky, self.empty_image = static_images
        self.text_font = pygame.font.SysFont('consolas', 12)
        self.buffers = []
        self.overlay_buffers = []
        self.name_buffer = []
        for x in range(len(self.cameras)):
            self.buffers.append([self.husky, self.husky, self.husky, self.husky])
            self.overlay_buffers.append([self.empty_image, self.empty_image, self.empty_image, self.empty_image])
            self.name_buffer.append([self.text("None"), self.text("None"), self.text("None"), self.text("None")])
        self.page = 0
        self.current_focus = None
        self.last_update = 0
        self.update_rate = 15
        self.log = logs
        self.cycle_forward = pygame.Rect(690, 450, 100, 40)
        self.cycle_forward_text = "Next"
        self.cycle_backward = pygame.Rect(580, 450, 100, 40)
        self.cycle_backward_text = "Back"
        self.image_frame_boxes = [pygame.Rect(0, 0, 400, 220), pygame.Rect(400, 0, 400, 220),
                                  pygame.Rect(0, 220, 400, 220), pygame.Rect(400, 220, 400, 220)]
        self.focus_stream = pygame.Rect(0, 0, 800, 440)
        self.stream = None
        self.steaming_enabled = live_mode_enable
        self.requested_fps = 30
        self.stream_cooldown_timer = 0
        self.active_requests = []

    def cycle(self, amount):
        self.page += amount
        if self.page > len(self.cameras) - 1:
            self.page = 0
        elif self.page < 0:
            self.page = len(self.cameras) - 1
        self.focus(None)
        self.last_update = time.time() - self.update_rate + 1
        # self.buffers[self.page] = [self.husky, self.husky, self.husky, self.husky]
        self.overlay_buffers[self.page] = [self.no_image, self.no_image, self.no_image, self.no_image]
        self.update()

    def focus(self, cam_id):
        if cam_id is None and self.current_focus is not None:
            if self.stream is not None:
                self.stream.release()
                self.stream.stop()
                del self.stream
            self.stream = None
            self.buffers[self.page][self.current_focus] = pygame.transform.scale(self.buffers[self.page][self.current_focus], (400, 220))
            self.log.info("Closed Stream/Focus")
        self.requested_fps = 30
        self.current_focus = cam_id
        self.last_update = time.time() - self.update_rate + 1
        if cam_id is not None and time.time() > self.stream_cooldown_timer + 10:
            try:
                thread = threading.Thread(target=self.create_stream, args=(self, self.cameras[self.page][cam_id]))
                thread.start()
                self.log.info(f"Created Stream/Focus for cam {cam_id}")
            except Exception as e:
                self.log.error(f"Attempted to create stream for cam {cam_id}, failed because ({e})")
                self.stream = None
            self.buffers[self.page][cam_id] = pygame.transform.scale(self.buffers[self.page][cam_id], (800, 440))
        self.update()

    def create_stream(self, ob, camera):
        cam_id, url, stream_url, name = camera
        try:
            from Pygamevideo import Video
            self.stream = Video(stream_url)
            self.stream.set_width(800)
            self.stream.set_height(440)
            self.stream.play()
        except Exception as e:
            self.log.error(f"Attempted to create stream for cam {cam_id}, failed because ({e})")
            self.overlay_buffers[self.page][0] = self.no_image

    def load_frame(self, ob, camera, select_buffer=None):
        """Load image from internet"""
        cam_id, url, stream_url, name = camera
        if select_buffer:
            page = select_buffer
        else:
            page = self.page

        self.name_buffer[page][cam_id] = self.text(name)
        try:
            image_str = urlopen(url, timeout=10).read()
            image_file = io.BytesIO(image_str)
            raw_frame = pygame.image.load(image_file)
            # self.get_exif(url)
            if self.current_focus is None:
                self.buffers[page][cam_id] = pygame.transform.scale(raw_frame, (400, 220))
                self.overlay_buffers[page][cam_id] = self.empty_image
                self.log.debug(f"Cam {page}-{cam_id}: Updated")
            elif self.current_focus == cam_id:
                self.buffers[page][cam_id] = pygame.transform.scale(raw_frame, (800, 440))
                # self.overlay_buffers[page][cam_id] = self.empty_image
                self.log.debug(f"Cam {page}-{cam_id}: Updated and focused")
        except http.client.IncompleteRead:
            self.overlay_buffers[page][cam_id] = self.no_image
            self.log.info(f"Cam {page}-{cam_id}: Incomplete read")
        except urllib.error.URLError as e:
            self.overlay_buffers[page][cam_id] = self.no_image
            self.log.info(f"Cam {page}-{cam_id}: URLError ({e})")
        except socket.timeout:
            self.overlay_buffers[page][cam_id] = self.no_image
            self.log.info(f"Cam {page}-{cam_id}: Timeout")
        except Exception as e:
            print(f"Cam {page}-{cam_id}: {e}")

    def update(self):
        if self.last_update == 0:
            self.last_update = time.time() - self.update_rate
        elif self.last_update < time.time() - self.update_rate:
            self.log.debug("Queueing camera updates")
            for camera in self.cameras[self.page]:
                thread = threading.Thread(target=self.load_frame, args=(self, camera))
                thread.start()
                self.active_requests.append(thread)
            self.log.debug("Cameras updates queued")
            self.last_update = time.time()

    def update_all(self):
        self.log.debug("Updating all camera thumbnails")
        page_num = 0
        for page in self.cameras:
            for camera in page:
                thread = threading.Thread(target=self.load_frame, args=(self, camera, page_num))
                thread.start()
                self.active_requests.append(thread)
            page_num += 1
        return True

    def draw_buttons(self, screen):
        """"""
        button_font = pygame.font.SysFont('couriernew', 14)
        cycle_forward_render = button_font.render(self.cycle_forward_text, True, (0, 0, 0))
        cycle_backward_render = button_font.render(self.cycle_backward_text, True, (0, 0, 0))

        pygame.draw.rect(screen, [255, 206, 0], self.cycle_forward)
        screen.blit(cycle_forward_render, cycle_forward_render.get_rect(midbottom=self.cycle_forward.center))
        pygame.draw.rect(screen, [255, 206, 0], self.cycle_backward)
        screen.blit(cycle_backward_render, cycle_backward_render.get_rect(midbottom=self.cycle_backward.center))

    def draw(self, screen):
        """Draw all buffered frames to the screen"""

        for thread in self.active_requests:
            if not thread.is_alive():
                thread.join()
                del thread

        if self.current_focus is None:
            screen.blit(self.buffers[self.page][0], (0, 0))
            screen.blit(self.buffers[self.page][1], (400, 0))
            screen.blit(self.buffers[self.page][2], (0, 220))
            screen.blit(self.buffers[self.page][3], (400, 220))

            screen.blit(self.overlay_buffers[self.page][0], (0, 0))
            screen.blit(self.overlay_buffers[self.page][1], (400, 0))
            screen.blit(self.overlay_buffers[self.page][2], (0, 220))
            screen.blit(self.overlay_buffers[self.page][3], (400, 220))

            screen.blit(self.name_buffer[self.page][0], self.name_buffer[self.page][0].get_rect(midtop=(200, 0)))
            screen.blit(self.name_buffer[self.page][1], self.name_buffer[self.page][1].get_rect(midtop=(600, 0)))
            screen.blit(self.name_buffer[self.page][2], self.name_buffer[self.page][2].get_rect(midtop=(200, 220)))
            screen.blit(self.name_buffer[self.page][3], self.name_buffer[self.page][3].get_rect(midtop=(600, 220)))
        else:
            screen.blit(self.buffers[self.page][self.current_focus], (0, 0))
            try:
                if self.stream is not None:
                    self.stream.draw_to(screen, (0, 0), anti_alias=self.steaming_enabled)
                else:
                    screen.blit(self.overlay_buffers[self.page][0], (0, 0))
            except Exception as e:
                self.focus(None)
                self.log.error(f"Stream error: {e}")

