import datetime
import io
import pygame

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)


def time_in_range(start, end, x):
    """Return true if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end


class WeatherAlert:

    def __init__(self, alert=None):
        """"""
        self.alert = alert
        self.sender_name = None
        self.event = None
        self.start = None
        self.end = None
        self.description_raw = None
        self.tags = None
        self.description_lines = []

    def build_alert(self):
        font1 = pygame.font.SysFont('NoticaText', 48)
        font2 = pygame.font.SysFont('couriernew', 24)
        font3 = pygame.font.SysFont('couriernew', 16)

        if self.alert:
            self.sender_name = self.alert['sender_name']
            self.event = self.alert['event']
            self.start = datetime.datetime.fromtimestamp(self.alert['start'])
            self.end = datetime.datetime.fromtimestamp(self.alert['end'])
            self.description_raw = [line for line in self.alert['description'].split("\n")]
            self.tags = self.alert['tags']

        self.event_text = font1.render(f"Alert: {self.event}" + " In Effect" if time_in_range(self.start, self.end, datetime.datetime.now()) else "", True,
                                       pallet_one)
        self.sender_text = font2.render(f"Issued by: {self.alert['sender_name']}", True, pallet_one)
        self.time_range_text = font2.render(f"In Effect From: ", True, pallet_one)
        for line in self.description_raw:
            self.description_lines.append(font3.render(line, True, pallet_one))

    def draw(self, screen, location):
        x, y = location
        screen.blit(self.event_text, (x, y+10))
        screen.blit(self.sender_text, (x, y + 45))
        # screen.blit(self.time_range_text, (x, y + 49))
        count = 0
        for line in self.description_lines:
            screen.blit(line, (x, y + 72 + (16 * count)))
            count += 1
