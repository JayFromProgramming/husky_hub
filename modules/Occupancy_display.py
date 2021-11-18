import datetime
from datetime import time

import pygame

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)


class Occupancy_display:

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.lines = []
        self.state_text = None
        self.refresh()

    def refresh(self):
        occupancy = self.coordinator.get_object_state("room_occupancy_info", False)
        self.lines = []
        font1 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 32)
        font2 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 22)
        font3 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 15)
        if occupancy['room_occupied'] is None:
            state = "Unknown"
        elif occupancy['room_occupied'] is True:
            state = "Occupied"
        else:
            state = "Unoccupied"

        self.state_text = font1.render(f"Room State: {state}", True, pallet_one)
        present = [occupant for occupant in occupancy['occupants'].values() if occupant['present'] is True]
        absent = [occupant for occupant in occupancy['occupants'].values() if occupant['present'] is False]
        self.lines.append(font2.render(f"-------------Currently Present-------------", True, pallet_one))
        for occupant in present:
            self.lines.append(font2.render(f"{occupant['name']}: Arrived at "
                                           f"{datetime.datetime.fromtimestamp(occupant['updated_at']).strftime('%I:%M:%S%p-%m/%d/%y')}"
                                           f" Connection: {'Stable' if occupant['stable'] else 'Unstable'}"
                                           , True, pallet_one))
        self.lines.append(font2.render(f"----------------Not Present----------------", True, pallet_one))
        for occupant in absent:
            self.lines.append(font2.render(f"{occupant['name']}: Last seen at "
                                           f"{datetime.datetime.fromtimestamp(occupant['updated_at']).strftime('%I:%M:%S%p-%m/%d/%y')}"
                                           , True, pallet_one))

    def draw(self, screen, location):
        x, y = location
        screen.blit(self.state_text, (x, y + 10))
        count = 0
        for line in self.lines:
            screen.blit(line, (x, y + 50 + (28 * count)))
            count += 1
