import concurrent
import datetime
import http.client
import json
import math
import os
import socket
import threading
import urllib.error

import numpy
import pygame
import time
import io
from PIL import Image
from urllib.request import urlopen

camera_path = "Configs/Cameras.json"
pallet_one = (255, 206, 0)
pallet_two = (255, 255, 255)
pallet_three = (0, 0, 0)


class CampusCams:

    def text(self, text):
        return self.text_font.render(text, True, pallet_one, pallet_three)

    def __init__(self, logs, static_images, live_mode_enable, multi_stream=False, linux=False):
        if os.path.exists(camera_path):
            with open(camera_path, "r") as f:
                self.cameras = json.load(f)
        else:
            raise FileNotFoundError("No Camera Config")
        self.no_image, self.husky, self.empty_image = static_images
        self.text_font = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 11)
        self.button_font = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Regular.ttf", 14)
        self.buffers = []
        self.overlay_buffers = []
        self.linux = linux
        self.name_buffer = []
        self.time_buffer = []
        self.updated_buffer = []
        self.stream_buffer = [None, None, None, None]
        for x in range(len(self.cameras)):
            self.buffers.append([self.husky, self.husky, self.husky, self.husky])
            self.overlay_buffers.append([self.empty_image, self.empty_image, self.empty_image, self.empty_image])
            self.name_buffer.append([self.text("None"), self.text("None"), self.text("None"), self.text("None")])
            self.time_buffer.append([self.text("None"), self.text("None"), self.text("None"), self.text("None")])
            self.updated_buffer.append([time.time(), time.time(), time.time(), time.time()])
        self.page = 0
        self.current_focus = None
        self.last_update = 0
        self.update_rate = 30
        self.log = logs
        self.cycle_forward = pygame.Rect(690, 430, 100, 40)
        self.cycle_forward_text = "Next"
        self.cycle_backward = pygame.Rect(580, 430, 100, 40)
        self.cycle_backward_text = "Back"
        self.cycle_forward_render = self.button_font.render(self.cycle_forward_text, True, (0, 0, 0)).convert_alpha()
        self.cycle_backward_render = self.button_font.render(self.cycle_backward_text, True, (0, 0, 0)).convert_alpha()
        self.image_frame_boxes = [pygame.Rect(0, 0, 400, 220), pygame.Rect(400, 0, 400, 220),
                                  pygame.Rect(0, 220, 400, 220), pygame.Rect(400, 220, 400, 220)]
        self.focus_stream = pygame.Rect(0, 0, 800, 440)
        self.stream = None
        self.high_performance_enabled = live_mode_enable
        self.requested_fps = 30
        self.stream_cooldown_timer = 0
        self.active_requests = []
        self.stream_info_text = self.text("Info: N/A")
        self.screen = None
        self.multi_cast = multi_stream
        self.multi_cast_threads = []
        self.thread_run = False

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
        self.close_multicast()
        self.update()

    def focus(self, cam_id):
        self.close_multicast()
        if cam_id is None and self.current_focus is not None:
            if self.linux: os.system("echo '1-1' |sudo tee /sys/bus/usb/drivers/usb/bind")
            if self.stream is not None:
                self.stream.release()
                self.stream.stop()
                del self.stream
            self.stream = None
            self.buffers[self.page][self.current_focus] = pygame.transform.scale \
                (self.buffers[self.page][self.current_focus], (int((self.screen.get_width() / 2)), int((self.screen.get_height() - 35) / 2)))
            self.log.info("Closed Stream/Focus")
        self.requested_fps = 30
        self.current_focus = cam_id
        self.last_update = time.time() - self.update_rate + 1
        if cam_id is not None and time.time() > self.stream_cooldown_timer + 10:
            self.close_multicast()
            try:
                thread = threading.Thread(target=self.create_stream, args=(self, self.cameras[self.page][cam_id]))
                thread.start()
                if self.linux: os.system("echo '1-1' |sudo tee /sys/bus/usb/drivers/usb/unbind")
                self.log.info(f"Created Stream/Focus for cam {self.page}-{cam_id}")
            except Exception as e:
                self.log.error(f"Attempted to create stream for cam {self.page}-{cam_id}, failed because ({e})")
                self.stream = None
            self.buffers[self.page][cam_id] = pygame.transform.scale(self.buffers[self.page][cam_id], (int((self.screen.get_width())),
                                                                                                       int((self.screen.get_height() - 35))))
        self.update()

    def multicast_refresh_thread(self, ob, stream, cam_id):
        clock = pygame.time.Clock()
        while stream and self.thread_run:
            process_time = stream.update_frame(anti_alias=self.high_performance_enabled)
            # self.time_buffer[self.page][cam_id] = \
            #     self.text(datetime.datetime.fromtimestamp(stream.last_frame_timestamp).strftime("%Y-%m-%d %H:%M:%S"))
            if not process_time > (1 / stream.fps):
                clock.tick(stream.fps)

    def pause_multicast(self):
        for stream in self.stream_buffer:
            if stream is not None and stream is not False:
                stream.toggle_pause()

    def close_multicast(self):
        self.stream_buffer = [None, None, None, None]
        self.thread_run = False
        for thread in self.multi_cast_threads:
            thread.join()
        for stream in self.stream_buffer:
            if stream is not None and stream is not False:
                stream.release()
                stream.stop()
                del stream
        self.thread_run = True
        self.multi_cast_threads = []

    def create_stream(self, ob, camera):
        cam_id, url, stream_url, name = camera
        stream = None
        try:
            from Pygamevideo import Video
            stream = Video(stream_url)
            if stream.fps > 30:
                stream.set_fps(30)
            self.stream_info_text = self.text(f"{stream.frame_height}x{stream.frame_width}@{round(stream.fps)}fps")
            if stream.fps == 0:
                raise BrokenPipeError("No Stream Data")
            if self.current_focus is None:
                stream.set_size((self.screen.get_width() / 2, (self.screen.get_height() - 35) / 2))
            else:
                stream.set_size((self.screen.get_width(), self.screen.get_height() - 35))
            stream.play()
        except Exception as e:
            self.log.error(f"Attempted to create stream for cam {self.page}-{cam_id}, failed because ({e})")
            self.overlay_buffers[self.page][0] = self.no_image
            self.stream_buffer[cam_id] = False
            return

        if self.multi_cast and self.current_focus is None:
            self.thread_run = True
            self.stream_buffer[cam_id] = stream
            thread = threading.Thread(target=self.multicast_refresh_thread, args=(self, stream, cam_id))
            thread.start()
            self.multi_cast_threads.append(thread)
        else:
            self.close_multicast()
            self.thread_run = True
            # thread = threading.Thread(target=self.multicast_refresh_thread, args=(self, stream, cam_id))
            # thread.start()
            # self.multi_cast_threads.append(thread)
            self.stream = stream

    def load_frame(self, ob, camera, select_buffer=None):
        """Load image from internet"""
        cam_id, url, stream_url, name = camera
        if select_buffer is not None:
            page = select_buffer
        else:
            page = self.page

        try:
            self.name_buffer[page][cam_id] = self.text(name).convert()
            image_str = urlopen(url, timeout=10).read()  # Load jpg image from source
            try:
                image_file = io.BytesIO(image_str)  # Load byte string into a bytesIO file
                raw_frame = pygame.image.load(image_file)  # Load into pygame
            except pygame.error:
                image_file = io.BytesIO(image_str)  # Load byte string into a bytesIO file
                image = Image.open(image_file)  # Open in Pillow
                with io.BytesIO() as f:  # This is a really jank way around pygame 32bit not being able to read jpgs
                    image.save(f, format='PNG')  # Save Pillow file to type PNG
                    f.seek(0)  # Move seek head
                    im = f.getvalue()  # Get file bytes
                    image = io.BytesIO(im)  # load new file into image bytes file
                raw_frame = pygame.image.load(image)  # Load into pygame

            if self.current_focus is None:
                temp: pygame.Surface = self.buffers[page][cam_id]
                self.buffers[page][cam_id]: pygame.Surface = pygame.transform.scale(raw_frame, (int((self.screen.get_width() / 2)),
                                                                                                int((self.screen.get_height() - 35) / 2))).convert()
                try:
                    if not numpy.array_equal(pygame.surfarray.pixels2d(temp), pygame.surfarray.pixels2d(self.buffers[page][cam_id].copy())):
                        self.updated_buffer[page][cam_id] = time.time()
                        # print(f"New frame {page}-{cam_id}")
                except Exception as e:
                    print(f"Cam {page}-{cam_id} warning: {e}")

                self.overlay_buffers[page][cam_id] = self.empty_image
                self.log.debug(f"Cam {page}-{cam_id}: Updated")
                if self.updated_buffer[page][cam_id] < time.time() - 65 and (page != 3 and cam_id != 3):
                    self.name_buffer[page][cam_id] = self.text(f"{name}: Unavailable").convert()
            elif self.current_focus == cam_id:
                self.buffers[page][cam_id] = pygame.transform.scale(raw_frame, (int((self.screen.get_width())),
                                                                                int((self.screen.get_height() - 35)))).convert()
                # self.overlay_buffers[page][cam_id] = self.empty_image
                self.log.debug(f"Cam {page}-{cam_id}: Updated and focused")
        except http.client.IncompleteRead:
            self.overlay_buffers[page][cam_id] = self.no_image
            self.log.info(f"Cam {page}-{cam_id}: Incomplete read")
        except urllib.error.URLError as e:
            if str(e) == "<urlopen error [Errno 11001] getaddrinfo failed>":
                self.log.info(f"Cam {page}-{cam_id}: No network")
                return
            self.overlay_buffers[page][cam_id] = self.no_image
            self.log.info(f"Cam {page}-{cam_id}: URLError ({e})")
            self.name_buffer[page][cam_id] = self.text(str(f"{name}: {str(e)[:30]}")).convert()
        except socket.timeout:
            self.overlay_buffers[page][cam_id] = self.no_image
            self.log.info(f"Cam {page}-{cam_id}: Timeout")
        except Exception as e:
            self.name_buffer[page][cam_id] = self.text(str(f"{name}: {str(e)[:30]}")).convert()
            print(f"Cam {page}-{cam_id} error: {e}")

    def resize(self, screen):
        self.screen = screen
        center_w = self.screen.get_width() / 2
        height = self.screen.get_height()
        self.image_frame_boxes = [pygame.Rect(0, 0, center_w, (height - 35) / 2),
                                  pygame.Rect(center_w, 0, center_w * 2, (height - 35) / 2),
                                  pygame.Rect(0, (height - 35) / 2, center_w, (height - 35) / 2),
                                  pygame.Rect(center_w, (height - 35) / 2, center_w * 2, (height - 35) / 2)]
        if height > 500:
            self.text_font = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Regular.ttf", 13)
        else:
            self.text_font = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Regular.ttf", 11)
        self.update_all()
        if self.stream is not None or self.multi_cast:
            # self.stream = None
            if self.multi_cast and not self.current_focus:
                for stream in self.stream_buffer:
                    if stream is not None and stream is not False:
                        if stream: stream.set_size((self.screen.get_width() / 2, (self.screen.get_height() - 35) / 2))
            else:
                self.stream.set_size((self.screen.get_width(), self.screen.get_height() - 35))
            # thread = threading.Thread(target=self.create_stream, args=(self, self.cameras[self.page][self.current_focus]))
            # thread.start()
        return True

    def update(self):
        if self.last_update == 0:
            self.last_update = time.time() - self.update_rate
        elif self.last_update < time.time() - self.update_rate:
            self.log.debug("Queueing camera updates")
            for camera in self.cameras[self.page]:
                thread = threading.Thread(target=self.load_frame, args=(self, camera))
                thread.start()
                self.active_requests.append(thread)
                if self.multi_cast and self.stream_buffer[camera[0]] is None and self.current_focus is None:
                    thread = threading.Thread(target=self.create_stream, args=(self, camera))
                    thread.start()
            self.log.debug("Cameras updates queued")
            self.last_update = time.time()

    def update_all(self):
        self.log.info("Updating all camera thumbnails")
        page_num = 0
        self.name_buffer = []
        for _ in self.cameras:
            self.name_buffer.append([self.text("None"), self.text("None"), self.text("None"), self.text("None")])
        for page in self.cameras:
            for camera in page:
                thread = threading.Thread(target=self.load_frame, args=(self, camera, page_num))
                thread.start()
                self.active_requests.append(thread)
            page_num += 1

    def draw_buttons(self, screen):
        """"""
        pygame.draw.rect(screen, [255, 206, 0], self.cycle_forward)
        screen.blit(self.cycle_forward_render, self.cycle_forward_render.get_rect(center=self.cycle_forward.center))
        pygame.draw.rect(screen, [255, 206, 0], self.cycle_backward)
        screen.blit(self.cycle_backward_render, self.cycle_backward_render.get_rect(center=self.cycle_backward.center))

    def draw(self, screen):
        """Draw all buffered frames to the screen"""

        for thread in self.active_requests:
            if not thread.is_alive():
                thread.join()
                del thread

        center_w = self.screen.get_width() / 2
        height = self.screen.get_height()

        if self.current_focus is None:

            screen.blit(self.buffers[self.page][0], (0, 0))
            screen.blit(self.buffers[self.page][1], (center_w, 0))
            screen.blit(self.buffers[self.page][2], (0, (height - 35) / 2))
            screen.blit(self.buffers[self.page][3], (center_w, (height - 35) / 2))

            if self.multi_cast:
                if self.stream_buffer[0]: self.stream_buffer[0].draw_to(screen, (0, 0))
                if self.stream_buffer[1]: self.stream_buffer[1].draw_to(screen, (center_w, 0))
                if self.stream_buffer[2]: self.stream_buffer[2].draw_to(screen, (0, (height - 35) / 2))
                if self.stream_buffer[3]: self.stream_buffer[3].draw_to(screen, (center_w, (height - 35) / 2))

                # screen.blit(self.time_buffer[self.page][0], self.time_buffer[self.page][0].get_rect(topleft=(0, 0)))
                # screen.blit(self.time_buffer[self.page][1], self.time_buffer[self.page][1].get_rect(topleft=(center_w, 0)))
                # screen.blit(self.time_buffer[self.page][2], self.time_buffer[self.page][2].get_rect(topleft=(0, (height - 35) / 2)))
                # screen.blit(self.time_buffer[self.page][3], self.time_buffer[self.page][3].get_rect(topleft=(center_w, (height - 35) / 2)))

            screen.blit(self.overlay_buffers[self.page][0], (0, 0))
            screen.blit(self.overlay_buffers[self.page][1], (center_w, 0))
            screen.blit(self.overlay_buffers[self.page][2], (0, (height - 35) / 2))
            screen.blit(self.overlay_buffers[self.page][3], (center_w, (height - 35) / 2))

            screen.blit(self.name_buffer[self.page][0], self.name_buffer[self.page][0].get_rect(midtop=(center_w - center_w / 2, 0)))
            screen.blit(self.name_buffer[self.page][1], self.name_buffer[self.page][1].get_rect(midtop=(center_w + center_w / 2, 0)))
            screen.blit(self.name_buffer[self.page][2], self.name_buffer[self.page][2].get_rect(midtop=(center_w - center_w / 2, (height - 35) / 2)))
            screen.blit(self.name_buffer[self.page][3], self.name_buffer[self.page][3].get_rect(midtop=(center_w + center_w / 2, (height - 35) / 2)))

        else:
            screen.blit(self.buffers[self.page][self.current_focus], (0, 0))
            try:
                if self.stream is not None:
                    self.stream.stream_to(screen, (0, 0), anti_alias=self.high_performance_enabled)
                    screen.blit(self.stream_info_text, self.stream_info_text.get_rect(topright=(center_w * 2, 0)))
                else:
                    screen.blit(self.overlay_buffers[self.page][0], (0, 0))
            except Exception as e:
                self.focus(None)
                self.log.error(f"Stream error: {e}")
            screen.blit(self.name_buffer[self.page][self.current_focus],
                        self.name_buffer[self.page][self.current_focus].get_rect(midtop=(center_w, 0)))
