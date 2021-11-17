import time

from . import blueStalker
import RPi.GPIO as GPIO


class OccupancyDetector:

    def __init__(self, target_devices, motion_pin):
        self.stalker = blueStalker.BlueStalker(target_devices)
        self.motion_pin = motion_pin
        self.last_motion_time = 0
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.motion_pin, GPIO.IN)

    def is_occupied(self):
        if self.last_motion_time < time.time() - 30 and self.stalker.room_occupied:
            return True
        else:
            return False

    def check_motion(self):
        if GPIO.input(self.motion_pin) == GPIO.HIGH:
            self.last_motion_time = time.time()
            return True
        else:
            return False

    def run_stalk(self):
        self.stalker.background_stalk()

    def stalk_targets_present(self):
        return self.stalker.room_occupied

    def which_targets_present(self):
        return self.stalker.targets_present

