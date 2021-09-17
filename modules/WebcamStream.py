import concurrent
import http.client
import os
import socket
import urllib.error
from concurrent import futures

from Pygamevideo import Video
import pygame
import time
import io
from urllib.request import urlopen


class CampusCams:

    def __init__(self, logs, static_images, live_mode_enable):
        self.cameras = [[(0, "https://webcams.mtu.edu/webcam11/webcam11.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera011.stream/playlist.m3u8"),
                         (1, "https://webcams.mtu.edu/webcam31/webcam31.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera031.stream/playlist.m3u8"),
                         (2, "https://webcams.mtu.edu/webcam16/webcam16.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera016.stream/playlist.m3u8"),
                         (3, "https://webcams.mtu.edu/images/webcam26.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera26.stream/playlist.m3u8")],
                        [(0, "https://webcams.mtu.edu/webcam7/webcam7.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera007.stream/playlist.m3u8"),
                         (1, "https://webcams.mtu.edu/webcam25/webcam25.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera25.stream/playlist.m3u8"),
                         (2, "https://webcams.mtu.edu/webcam15/webcam15.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera015.stream/playlist.m3u8"),
                         (3, "https://webcams.mtu.edu/webcam4/webcam4.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera004.stream/playlist.m3u8")],
                        [(0, "https://webcams.mtu.edu/webcam30/webcam30.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera30.stream/playlist.m3u8"),
                         (1, "https://webcams.mtu.edu/webcam21/webcam21.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera21.stream/playlist.m3u8"),
                         (2, "https://webcams.mtu.edu/images/webcam29.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera29.stream/playlist.m3u8"),
                         (3, "https://webcams.mtu.edu/images/webcam28.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera028.stream/playlist.m3u8")],
                        [(0, "https://webcams.mtu.edu/webcam14/webcam14.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera014.stream/playlist.m3u8"),
                         (1, "https://webcams.mtu.edu/webcam13/webcam13.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera013.stream/playlist.m3u8"),
                         (2, "https://webcams.mtu.edu/webcam36/webcam36.jpg",
                          "https://streamingwebcams.mtu.edu:1935/rtplive/camera036.stream/playlist.m3u8"),
                         (3, "https://www.mtu.edu/mtu_resources/images/download-central/logos/full-horizontal/gold.png", "")]]

        self.no_image, self.husky, self.empty_image = static_images
        self.buffers = []
        self.overlay_buffers = []
        for x in range(4):
            self.buffers.append([self.husky, self.husky, self.husky, self.husky])
            self.overlay_buffers.append([self.empty_image, self.empty_image, self.empty_image, self.empty_image])
        self.page = 0
        self.current_focus = None
        self.last_update = 0
        self.update_rate = 15
        self.log = logs
        self.webcam_cycle_forward = pygame.Rect(690, 450, 100, 40)
        self.webcam_cycle_backward = pygame.Rect(580, 450, 100, 40)
        self.image_frame_boxes = [pygame.Rect(0, 0, 400, 220), pygame.Rect(400, 0, 400, 220),
                                  pygame.Rect(0, 220, 400, 220), pygame.Rect(400, 220, 400, 220)]
        self.focus_stream = pygame.Rect(0, 0, 800, 440)
        self.stream = None
        self.steaming_enabled = live_mode_enable
        self.requested_fps = 30
        self.stream_cooldown_timer = 0

    def cycle(self, amount):
        self.page += amount
        if self.page > 3:
            self.page = 0
        elif self.page < 0:
            self.page = 3
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
            self.stream = None
            self.buffers[self.page][self.current_focus] = pygame.transform.scale(self.buffers[self.page][self.current_focus], (400, 220))
            # self.stream_cooldown_timer = time.time()
            self.log.debug("Closed Stream/Focus")
        self.requested_fps = 30
        self.current_focus = cam_id
        self.last_update = time.time() - self.update_rate + 1
        # self.buffers = [self.no_image, self.no_image, self.no_image, self.no_image]
        if cam_id is not None and time.time() > self.stream_cooldown_timer + 10:
            try:
                self.create_stream(self.cameras[self.page][cam_id])
                self.log.debug(f"Created Stream/Focus for cam {cam_id}")
            except Exception as e:
                self.log.error(f"Attempted to create stream for cam {cam_id}, failed because ({e})")
                self.stream = None
            self.buffers[self.page][cam_id] = pygame.transform.scale(self.buffers[self.page][cam_id], (800, 440))
        self.update()

    def create_stream(self, camera):
        if self.steaming_enabled:
            cam_id, url, stream_url = camera
            self.stream = Video(stream_url)
            self.stream.play()

    def load_frame(self, camera):
        """Load image from internet"""
        cam_id, url, stream_url = camera
        try:
            image_str = urlopen(url, timeout=2).read()
            image_file = io.BytesIO(image_str)
            raw_frame = pygame.image.load(image_file)
            if self.current_focus is None:
                self.buffers[self.page][cam_id] = pygame.transform.scale(raw_frame, (400, 220))
                self.overlay_buffers[self.page][cam_id] = self.empty_image
                self.log.debug(f"Cam {cam_id}: Updated")
            elif self.current_focus == cam_id:
                self.buffers[self.page][cam_id] = pygame.transform.scale(raw_frame, (800, 440))
                self.overlay_buffers[self.page][cam_id] = self.empty_image
                self.log.debug(f"Cam {cam_id}: Updated and focused")
        except http.client.IncompleteRead:
            self.overlay_buffers[self.page][cam_id] = self.no_image
            self.log.info(f"Cam {cam_id}: Incomplete read")
        except urllib.error.URLError as e:
            self.overlay_buffers[self.page][cam_id] = self.no_image
            self.log.info(f"Cam {cam_id}: URLError ({e})")
        except socket.timeout:
            self.overlay_buffers[self.page][cam_id] = self.no_image
            self.log.info(f"Cam {cam_id}: Timeout")

    def update(self):
        if self.last_update == 0:
            self.last_update = time.time() - self.update_rate
        elif self.last_update < time.time() - self.update_rate:
            self.log.debug("Queueing camera updates")
            with futures.ThreadPoolExecutor(max_workers=4) as executor:
                var = {executor.submit(self.load_frame, camera): camera for camera in self.cameras[self.page]}
                self.log.debug("Cameras updates queued")
            self.last_update = time.time()

    def update_all(self):
        self.log.debug("Queueing camera updates")
        with futures.ThreadPoolExecutor(max_workers=4) as executor:
            var = {executor.submit(self.load_frame, camera): camera for camera in self.cameras[self.page]}
            self.log.debug("Cameras updates queued")
        self.page += 1
        if self.page > 3:
            self.page = 0
            return True
        else:
            return False

    def draw(self, screen):
        """Draw all buffered frames to the screen"""

        if self.current_focus is None:
            screen.blit(self.buffers[self.page][0], (0, 0))
            screen.blit(self.buffers[self.page][1], (400, 0))
            screen.blit(self.buffers[self.page][2], (0, 220))
            screen.blit(self.buffers[self.page][3], (400, 220))

            screen.blit(self.overlay_buffers[self.page][0], (0, 0))
            screen.blit(self.overlay_buffers[self.page][1], (400, 0))
            screen.blit(self.overlay_buffers[self.page][2], (0, 220))
            screen.blit(self.overlay_buffers[self.page][3], (400, 220))
        else:
            screen.blit(self.buffers[self.page][self.current_focus], (0, 0))
            try:
                if self.stream is not None:
                    self.stream.set_width(800)
                    self.stream.set_height(440)
                    self.stream.draw_to(screen, (0, 0))
                    self.requested_fps = 30
            except Exception:
                self.focus(None)

        pygame.draw.rect(screen, [255, 206, 0], self.webcam_cycle_forward)
        pygame.draw.rect(screen, [255, 206, 0], self.webcam_cycle_backward)
