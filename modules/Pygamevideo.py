import time
import pygame
import numpy
import cv2
from ffpyplayer.player import MediaPlayer

__version__ = "1.4.2"


class Time:
    def __init__(self, hour=0, minute=0, second=0, millisecond=0):
        self.hour, self.minute, self.second, self.millisecond = hour, minute, second, millisecond

    def __repr__(self):
        return self.format("<pygamevideo.Time(%h:%m:%s:%f)>")

    def __add__(self, other):
        return Time.from_millisecond(self.to_millisecond() + other.to_millisecond())

    def __sub__(self, other):
        return Time.from_millisecond(self.to_millisecond() - other.to_millisecond())

    def format(self, format_string):
        if "%H" in format_string: format_string = format_string.replace("%H", str(self.hour).zfill(2))
        if "%M" in format_string: format_string = format_string.replace("%M", str(self.minute).zfill(2))
        if "%S" in format_string: format_string = format_string.replace("%S", str(self.second).zfill(2))
        if "%F" in format_string: format_string = format_string.replace("%F", str(self.millisecond).zfill(2))
        if "%h" in format_string: format_string = format_string.replace("%h", str(int(self.hour)).zfill(2))
        if "%m" in format_string: format_string = format_string.replace("%m", str(int(self.minute)).zfill(2))
        if "%s" in format_string: format_string = format_string.replace("%s", str(int(self.second)).zfill(2))
        if "%f" in format_string: format_string = format_string.replace("%f", str(int(self.millisecond)).zfill(2))

        return format_string

    def to_hour(self):
        return self.hour + self.minute / 60 + self.second / 3600 + self.millisecond / 3600000

    def to_minute(self):
        return self.hour * 60 + self.minute + self.second / 60 + self.millisecond / 60000

    def to_second(self):
        return self.hour * 3600 + self.minute * 60 + self.second + self.millisecond / 1000

    def to_millisecond(self):
        return self.hour * 3600000 + self.minute * 60000 + self.second * 1000 + self.millisecond

    @classmethod
    def from_millisecond(cls, ms):
        h = ms // 3600000
        hr = ms % 3600000

        m = hr // 60000
        mr = hr % 60000

        s = mr // 1000
        sr = mr % 1000

        return cls(hour=h, minute=m, second=s, millisecond=sr)


class Video:
    # def __init__(self, filepath):
    #
    #     self.load(filepath)

    def __repr__(self):
        return f"<pygamevideo.Video(frame#{self.current_frame})>"

    def __init__(self, filepath):

        if not filepath:
            raise ValueError("No Stream Source Provided")

        self._frame = None
        self.draw_frame = 0
        self.last_segment = time.time()
        self.dropped_frames = 0
        self.is_ready = False

        self.filepath = filepath

        self.is_playing = False
        self.is_ended = True
        self.is_paused = False
        self.is_looped = False

        self.draw_frame = 0
        self.start_time = 0
        self.ostart_time = 0

        self.volume = 1
        self.is_muted = False

        self.stream = cv2.VideoCapture(self.filepath)

        # self.ff = MediaPlayer(self.filepath)

        self.fps = self.stream.get(cv2.CAP_PROP_FPS)

        self.last_frame_timestamp = None

        self._last_frame_time = time.time()

        self.total_frames = int(self.stream.get(cv2.CAP_PROP_FRAME_COUNT))

        self.frame_width = int(self.stream.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.keep_aspect_ratio = False

        self.frame_surf = pygame.Surface((self.frame_width, self.frame_height), pygame.HWSURFACE | pygame.ASYNCBLIT).convert()

        self.is_ready = True

        # print(f"Stream ready with resolution {self.frame_height}x{self.frame_width}@{self.fps}fps")

        self._frame = None

    def release(self):
        self.stream.release()
        # self.ff.close_player()
        self.is_ready = False

    # Control methods

    def play(self, loop=False):
        if not self.is_playing:
            if not self.is_ready: self.__init__(self.filepath)

            self.is_playing = True
            self.is_looped = loop

            self.start_time = time.time()
            self.ostart_time = time.time()

    def restart(self):
        if self.is_playing:
            self.release()
            self.stream = cv2.VideoCapture(self.filepath)
            self.ff = MediaPlayer(self.filepath)
            self.is_ready = True

            self.draw_frame = 0
            self.is_paused = False

            self.start_time = time.time()
            self.ostart_time = time.time()

    def stop(self):
        if self.is_playing:
            self.is_playing = False
            self.is_paused = False
            self.is_ended = True
            self.is_looped = False
            self.draw_frame = 0

            self.frame_surf = pygame.Surface((self.frame_width, self.frame_height))

            self.release()

    def pause(self):
        self.is_paused = True
        self.ff.set_pause(True)

    def resume(self):
        self.is_paused = False
        self.ff.set_pause(False)

    # Audio methods

    def mute(self):
        self.is_muted = True
        self.ff.set_mute(True)

    def unmute(self):
        self.is_muted = False
        self.ff.set_mute(False)

    def has_audio(self):
        pass

    def set_volume(self, volume):
        self.volume = volume
        self.ff.set_volume(volume)

    # Duration methods & properties

    @property
    def duration(self):
        return Time.from_millisecond((self.total_frames / self.fps) * 1000)

    @property
    def current_time(self):
        return Time.from_millisecond(self.stream.get(cv2.CAP_PROP_POS_MSEC))

    @property
    def remaining_time(self):
        return self.duration - self.current_time

    @property
    def current_frame(self):
        return self.stream.get(cv2.CAP_PROP_POS_FRAMES)

    def seek_time(self, t):
        if isinstance(t, Time):
            _t = t.to_millisecond()
            self.seek_time(_t)

        elif isinstance(t, str):
            h = int(t[:2])
            m = int(t[3:5])
            s = int(t[6:8])
            f = int(t[9:])

            _t = Time(hour=h, minute=m, second=s, millisecond=f)
            self.seek_time(_t.to_millisecond())

        elif isinstance(t, (int, float)):
            self.start_time = self.ostart_time + t / 1000
            self.draw_frame = int((time.time() - self.start_time) * self.fps)
            self.stream.set(cv2.CAP_PROP_POS_MSEC, t)
            self.ff.seek(t / 1000, relative=False)

        else:
            raise ValueError("Time can only be represented in Time, str, int or float")

    def seek_frame(self, frame):
        self.seek_time((frame / self.fps) * 1000)

    # Dimension methods

    def get_size(self):
        return self.frame_width, self.frame_height

    def get_width(self):
        return self.frame_width

    def get_height(self):
        return self.frame_height

    def set_size(self, size):
        self.frame_width, self.frame_height = size
        self.frame_surf = pygame.Surface((self.frame_width, self.frame_height), pygame.HWSURFACE | pygame.ASYNCBLIT).convert()

        if not (self.frame_width > 0 and self.frame_height > 0):
            raise ValueError(f"Size must be positive")

    def change_width(self, width: int):
        self.frame_width = width
        self.frame_surf = pygame.Surface((width, self.frame_height), pygame.HWSURFACE | pygame.ASYNCBLIT).convert()

        if self.frame_width <= 0:
            raise ValueError(f"Width must be positive")

    def change_height(self, height: int):
        self.frame_height = height
        self.frame_surf = pygame.Surface((self.frame_width, height), pygame.HWSURFACE | pygame.ASYNCBLIT).convert()

        if self.frame_height <= 0:
            raise ValueError(f"Height must be positive")

    def set_fps(self, fps):
        self.fps = fps

    # Process & draw video

    def update_frame(self, anti_alias=False):
        if not self.is_playing:
            return 0
            # return self.frame_surf
        start_time = time.time()

        elapsed_frames = int((time.time() - self.start_time) * self.fps)

        seeked_frames = int(self.stream.get(cv2.CAP_PROP_POS_FRAMES) + self.draw_frame + self.dropped_frames)
        makeup_frames = elapsed_frames - seeked_frames

        time_difference = round(self.stream.get(cv2.CAP_PROP_POS_MSEC) / 1000 - elapsed_frames / self.fps, 2)

        self.last_frame_timestamp = self.stream.get(cv2.CAP_PROP_POS_MSEC) / 1000 + self.start_time - 30

        if seeked_frames >= elapsed_frames:
            return 0

        if not self.is_paused:
            # In the event that we have fallen behind in processing the stream skip to the next Iframe
            # print(f"Time based Elapsed: {elapsed_frames}; Seeked frames: {seeked_frames}; Makeup_frames: {makeup_frames - 1};"
            #       f" Time delta: {time_difference}; Dropped Frames: {self.dropped_frames}")
            if time_difference < 0 and makeup_frames > 5 and self.last_segment < time.time() - 1:
                self.draw_frame += int(self.stream.get(cv2.CAP_PROP_POS_FRAMES))
                self.dropped_frames += makeup_frames
                self.stream.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Sets position to the next Iframe
                # self.stream.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Sets position to the next Iframe
                self.last_segment = time.time()
            else:
                if makeup_frames > 5: makeup_frames = 5  # Set a max makeup amount to prevent process locking
                for _ in range(makeup_frames):
                    success, self._frame = self.stream.read()
                    # time.sleep(1 / (self.fps * 1.1))
            if type(self._frame) is not numpy.ndarray:
                return 0
            if anti_alias: frame = cv2.resize(self._frame, (int(self.frame_width), int(self.frame_height)), interpolation=cv2.INTER_AREA)
            if not anti_alias: frame = cv2.resize(self._frame, (int(self.frame_width), int(self.frame_height)), interpolation=cv2.INTER_NEAREST)
            # audio_frame, val = self.ff.get_frame()
            try:
                pygame.pixelcopy.array_to_surface(self.frame_surf, numpy.flip(numpy.rot90(frame[::-1])))
            except ValueError:
                return 0

        finish_time = time.time()
        total_time = (finish_time - start_time)
        return total_time
        # print(total_time)

    def draw_to(self, surface, pos):
        if self.frame_width != 0 and self.frame_height != 0:
            surface.blit(self.frame_surf, pos)

    def stream_to(self, surface, pos, anti_alias=False):
        if self.frame_width != 0 and self.frame_height != 0:
            self.update_frame(anti_alias)
            surface.blit(self.frame_surf, pos)
