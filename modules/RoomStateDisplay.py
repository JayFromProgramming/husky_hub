import datetime
from datetime import time
import time
import pygame

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (0, 0, 0)


def celsius_to_fahrenheit(celsius):
    return (float(celsius) * (9 / 5)) + 32


class Occupancy_display:

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.lines = []
        self.side_lines = []
        self.state_text = None
        self.maximize_state = False
        self.maximize_collider = pygame.Rect(550, 120, 250, 320)
        self.last_update = time.time()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        self.sensor_title = None
        self.refresh()

    def refresh(self):
        occupancy = self.coordinator.get_object_state("room_occupancy_info", True, True)
        room_data: dict = self.coordinator.get_object_state("room_sensor_data_displayable", False)
        temp = self.coordinator.get_object_state("temperature", False)
        humid = self.coordinator.get_object_state("humidity", False)
        temp = round(celsius_to_fahrenheit(temp), 2) if temp != -9999 else "N/A"
        humid = round(humid, 2) if humid != -1 else "N/A"
        self.lines = []
        self.side_lines = []
        font1 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 32)
        font2 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 22)
        font3 = pygame.font.Font("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf", 15)
        self.sensor_title = font2.render("Room Sensor Data", True, pallet_one, pallet_three).convert()
        if occupancy['room_occupied'] is None:
            state = "Unknown"
        elif occupancy['room_occupied'] is True:
            state = "Occupied"
        else:
            state = "Unoccupied"

        self.state_text = font1.render(f"Room State: {state}", True, pallet_one)
        present = [occupant for occupant in occupancy['occupants'].values() if occupant['present'] is True]
        absent = [occupant for occupant in occupancy['occupants'].values() if occupant['present'] is False]
        max_present_rjust = max([len(occupant['name']) for occupant in present] if len(present) > 0 else [0])
        max_absent_rjust = max([len(occupant['name']) for occupant in absent] if len(absent) > 0 else [0])
        self.lines.append(font2.render(f"------------Currently Present------------", True, pallet_one, pallet_three).convert())
        for occupant in present:
            self.lines.append(font2.render(f"{occupant['name'].rjust(max_present_rjust, '-')}: Arrived at "
                                           f"{datetime.datetime.fromtimestamp(occupant['updated_at']).strftime('%I:%M:%S%p-%m/%d/%y')}"
                                           , True, pallet_one, pallet_three).convert())
            self.lines.append(font3.render(f" Connection: {'Stable' if occupant['stable'] else 'Unstable'}; Device: {occupant['mac']}"
                                           , True, pallet_one, pallet_three).convert())
        self.lines.append(font2.render(f"---------------Not Present---------------", True, pallet_one, pallet_three).convert())
        for occupant in absent:
            self.lines.append(font2.render(f"{occupant['name'].rjust(max_absent_rjust, '-')}: Last seen at "
                                           f"{datetime.datetime.fromtimestamp(occupant['updated_at']).strftime('%I:%M:%S%p-%m/%d/%y')}"
                                           , True, pallet_one, pallet_three).convert())
            self.lines.append(font3.render(f" Connection: Lost; Device: {occupant['mac']}"
                                           , True, pallet_one, pallet_three).convert())
        room_data["room_air_sensor"] = f"T:{temp}°F | H:{humid}%"
        for key, value in room_data.items():
            self.side_lines.append(font3.render(f"{str(key).replace('_', ' ').capitalize()}", True, pallet_one, pallet_three).convert())
            self.side_lines.append(font3.render(f"{value if value is not None else 'N/A'}", True, pallet_one, pallet_three).convert())

    def draw(self, screen: pygame.Surface, location):
        x, y = location

        if time.time() - self.last_update > 1:
            self.refresh()
            self.last_update = time.time()

        if not self.maximize_state:
            pygame.draw.line(screen, pallet_two, (550, 120), (550, 440))
            screen.blit(self.state_text, (x, y + 10))
            count = 0
            for line in self.lines:
                screen.blit(line, (x, y + 50 + (28 * count)))
                count += 1
            count = 0
            for line in self.side_lines:
                if count % 2 == 0:
                    if y + 18 + (20 * (count + 1)) > screen.get_height() - 60:
                        break
                screen.blit(line, (x + 552, y + 18 + (20 * count)))
                count += 1
        else:
            screen.blit(self.sensor_title, (x + 15, y + 10))
            y += 40
            shift = 0
            max_column_width = 0
            pygame.draw.line(screen, pallet_two, (x + 15, y), (x + 15, (screen.get_height() - 40)))
            count = 0
            for line in self.side_lines:
                if count % 2 == 0:
                    if y + (20 * (count + 1)) > screen.get_height() - 60:
                        shift += max_column_width + 10
                        count = 0
                        max_column_width = 0
                        pygame.draw.line(screen, pallet_two, (x + 15 + shift, y), (x + 15 + shift, (screen.get_height() - 40)))
                screen.blit(line, (x + 20 + shift, y + (20 * count)))
                if line.get_rect().width > max_column_width:
                    max_column_width = min(220, line.get_rect().width)
                count += 1
            shift += max_column_width + 10
            pygame.draw.line(screen, pallet_two, (x + 15 + shift, y), (x + 15 + shift, (screen.get_height() - 40)))
