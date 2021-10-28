import time
import pygame
import numpy
import cv2
from ffpyplayer.player import MediaPlayer

__version__ = "2.0.2"


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
        """
        The constructor of the Pygame Video class.
        :param filepath: The path of the video file or the URL of the m3u8 playlist.
        """
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
        """
        Releases the video stream and the underlying cv2.VideoCapture object back to the system.
        :return: None
        """
        self.stream.release()
        # self.ff.close_player()
        self.is_ready = False

    # Control methods

    def play(self, loop=False):
        """
        Starts the video playback.
        :param loop: If True, the video will loop when it reaches the end as long as it isn't a live stream.
        :return: None
        """
        if not self.is_playing:
            if not self.is_ready: self.__init__(self.filepath)

            self.is_playing = True
            self.is_looped = loop

            self.start_time = time.time()
            self.ostart_time = time.time()

    def restart(self):
        """
        Restarts the video playback from the beginning, as long as it isn't a live stream.
        :return: None
        """
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
        """
        Stops the video playback, and releases the underlying cv2.VideoCapture object back to the system.
        :return: None
        """
        if self.is_playing:
            self.is_playing = False
            self.is_paused = False
            self.is_ended = True
            self.is_looped = False
            self.draw_frame = 0

            self.frame_surf = pygame.Surface((self.frame_width, self.frame_height))

            self.release()

    def toggle_pause(self):
        """
        Toggles the video playback between paused and playing.
        :return: None
        """
        if self.is_paused:
            self.resume()
        else:
            self.pause()

    def pause(self):
        """
        Pauses the video playback.
        :return: None
        """
        self.is_paused = True

    def resume(self):
        """
        Resumes the video playback.
        :return: None
        """
        self.is_paused = False

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
        """
        Returns the duration of the video in seconds.
        :return: The duration of the video in seconds.
        """
        return Time.from_millisecond((self.total_frames / self.fps) * 1000)

    @property
    def current_time(self):
        """
        The current playback time of the video.
        :return: The current playback time of the video in seconds.
        """
        return Time.from_millisecond(self.stream.get(cv2.CAP_PROP_POS_MSEC))

    @property
    def remaining_time(self):
        """
        The remaining time of the video.
        :return: The remaining time of the video in seconds.
        """
        return self.duration - self.current_time

    @property
    def current_frame(self):
        """
        The current frame number of the video.
        :return: The current frame number of the video.
        """
        return self.stream.get(cv2.CAP_PROP_POS_FRAMES)

    def seek_time(self, t):
        """
        Seeks the video to the specified time.
        :param t: The time to seek to in the formats of Time, Time: str, Time: int, or Time: float.
        :return: None
        """
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
        """
        Seeks the video to the specified frame.
        :param frame: The frame to seek to.
        :return: None
        """
        self.seek_time((frame / self.fps) * 1000)

    # Dimension methods

    def get_size(self):
        """
        Returns the size of the video.
        :return: The size of the video in the format (width, height).
        """
        return self.frame_width, self.frame_height

    def get_width(self):
        """
        Returns the width of the video.
        :return: The width of the video in pixels.
        """
        return self.frame_width

    def get_height(self):
        """
        Returns the height of the video.
        :return: The height of the video in pixels.
        """
        return self.frame_height

    def set_size(self, size):
        """
        Sets the size of the video.
        :param size: The size of the video in the format (width, height).
        :return: None
        :raises ValueError: If the width or height is not a positive integer.
        """
        self.frame_width, self.frame_height = size
        self.frame_surf = pygame.Surface((self.frame_width, self.frame_height), pygame.HWSURFACE | pygame.ASYNCBLIT).convert()

        if not (self.frame_width > 0 and self.frame_height > 0):
            raise ValueError(f"Size must be positive")

    def change_width(self, width: int):
        """
        Changes the width of the video.
        :param width: The new width of the video in pixels.
        :return: None
        :raises ValueError: If the width is negative.
        """
        self.frame_width = width
        self.frame_surf = pygame.Surface((width, self.frame_height), pygame.HWSURFACE | pygame.ASYNCBLIT).convert()

        if self.frame_width <= 0:
            raise ValueError(f"Width must be positive")

    def change_height(self, height: int):
        """
        Changes the height of the video.
        :param height: The new height of the video in pixels.
        :return: None
        :raises ValueError: If the height is negative.
        """
        self.frame_height = height
        self.frame_surf = pygame.Surface((self.frame_width, height), pygame.HWSURFACE | pygame.ASYNCBLIT).convert()

        if self.frame_height <= 0:
            raise ValueError(f"Height must be positive")

    def set_fps(self, fps):
        """
        Overrides the FPS of the video.
        :param fps: The new FPS of the video.
        :return: None
        """
        self.fps = fps

    # Process & draw video

    def update_frame(self, anti_alias=False):
        """
        Grabs the next frame from the video and updates the frame surface.
        :param anti_alias: A boolean indicating whether use smooth scaling.
        :return: The total time spent processing the frame.
        """
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
            if time_difference < 0 and makeup_frames > 5 and self.last_segment < time.time() - 1:
                self.draw_frame += int(self.stream.get(cv2.CAP_PROP_POS_FRAMES))
                self.dropped_frames += makeup_frames
                self.stream.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Sets position to the next Iframe
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
        """
        Draws the current buffered frame to the given surface.
        :param surface: The surface to draw to.
        :param pos: The position in X, Y coordinates to draw the frame.
        :return: None
        """
        if self.frame_width != 0 and self.frame_height != 0:
            surface.blit(self.frame_surf, pos)

    def stream_to(self, surface, pos, anti_alias=False):
        """
        Loads the next frame from the video and draws it to the given surface.
        :param surface: The surface to draw to.
        :param pos: The position in X, Y coordinates to draw the frame.
        :param anti_alias: True if the frame should be anti-aliased with smooth scaling.
        :return: None
        """
        if self.frame_width != 0 and self.frame_height != 0:
            self.update_frame(anti_alias)
            surface.blit(self.frame_surf, pos)
