import time

from . import blueStalker
# import RPi.GPIO as GPIO


class OccupancyDetector:

    def __init__(self, target_devices, motion_pin, coordinator):
        self.stalker = blueStalker.BlueStalker(target_devices, coordinator.get_object_state("room_occupancy_info")['occupants'])
        self.motion_pin = motion_pin
        self.coordinator = coordinator
        self.last_motion_time = 0
        # GPIO.setmode(GPIO.BOARD)
        # GPIO.setup(self.motion_pin, GPIO.IN)

    def is_ready(self):
        return self.stalker.ready

    def is_occupied(self):
        self.check_motion()
        if self.stalker.stalk_error:
            return None
        elif self.last_motion_time > time.time() - 30 or self.stalker.room_occupied:
            return True
        else:
            return False

    def check_motion(self):
        if self.coordinator.get_object_state("room_sensor_data_displayable", False)['motion_sensor']:
            self.last_motion_time = time.time()
            return True
        else:
            return False

    def run_stalk(self):
        self.stalker.background_stalk()

    def stalk_targets_present(self):
        return self.stalker.room_occupied

    def occupancy_info(self):
        return self.stalker.targets

