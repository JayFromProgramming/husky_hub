import datetime
import io
import time

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

    def __init__(self, number, total, alert=None):
        """
        Initalize Weather alert manager object
        :param number: The alert number to display
        :param total: The total number of alerts
        :param alert: The alert data to display
        """
        self.alert = alert
        self.number = number
        self.total = total
        self.sender_name = None
        self.event = None
        self.start = None
        self.end = None
        self.description_raw = None
        self.tags = None
        self.description_lines = []
        self.built_line = 0
        self.initialized = False
        self.built = False

        self.scroll = 0
        self.scroll_time = time.time()

    def build_alert(self):
        """
        Build the alert text line by line
        :return: True if built, False if not
        """
        if self.built:
            return True

        font1 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 32)
        font2 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 22)
        font3 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 15)

        if not self.initialized:
            if self.alert:
                self.sender_name = self.alert['sender_name']
                self.event = self.alert['event']
                self.start = datetime.datetime.fromtimestamp(self.alert['start'])
                self.end = datetime.datetime.fromtimestamp(self.alert['end'])
                self.description_raw = [line for line in self.alert['description'].split("\n")]
                self.tags = self.alert['tags']

            self.event_text = font1.render(f"Alert {self.number}/{self.total}:"
                                           f" {self.event}",
                                           True, pallet_one)
            self.sender_text = font2.render(f"Issued by: {self.alert['sender_name']}"
                                            + (" In Effect" if time_in_range(self.start, self.end, datetime.datetime.now()) else ""),
                                            True, pallet_one)
            self.time_range_text = font2.render(f"In Effect From: ", True, pallet_one)
            self.initialized = True
        if self.built_line == 0:
            self.description_lines.append(font3.render(f"--------------------------------------Begin Alert--------------------------------------",
                                                       True, pallet_one))
            self.built_line += 1
        elif self.built_line <= len(self.description_raw):
            line = self.description_raw[self.built_line - 1]
            self.description_lines.append(font3.render(f"{str(self.built_line).zfill(2)}: {line}", True, pallet_one))
            self.built_line += 1
        else:
            self.description_lines.append(font3.render(f"---------------------------------------End Alert---------------------------------------",
                                                       True, pallet_one))
            self.description_lines.append(font3.render(f" ", True, pallet_one))
            self.description_lines.append(font3.render(f" ", True, pallet_one))
            self.built = True

    def draw(self, screen, location):
        """
        Draw the alert to the screen
        :param screen: The screen to draw to
        :param location: The X,Y location to draw to
        :return: False if not initialized, None if initialized
        """
        x, y = location
        if not self.initialized:
            return False
        screen.blit(self.event_text, (x, y+10))
        screen.blit(self.sender_text, (x, y + 45))
        # screen.blit(self.time_range_text, (x, y + 49))
        count = 0  # 17
        for value in range(self.scroll, self.scroll + 16):
            if len(self.description_lines) > 17:
                line = self.description_lines[value % len(self.description_lines)]
            elif value < len(self.description_lines):
                line = self.description_lines[value]
            else:
                break
            screen.blit(line, (x, y + 72 + (17 * count)))
            count += 1

            if len(self.description_lines) > 17 and time.time() > self.scroll_time + 5:
                self.scroll += 5
                self.scroll_time = time.time()
                if self.scroll > len(self.description_lines) - 5:
                    self.scroll = 0
