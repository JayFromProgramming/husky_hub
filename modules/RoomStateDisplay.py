import datetime
from datetime import time
import time
import pygame

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (0, 0, 0)


def chunk(l, n):
    n = max(1, n)
    return (l[i:i + n] for i in range(0, len(l), n))


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
        self.refresh()

    def refresh(self):
        occupancy = self.coordinator.get_object_state("room_occupancy_info", False)
        room_data = self.coordinator.get_object_state("room_sensor_data_displayable", False)
        self.lines = []
        self.side_lines = []
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
        self.lines.append(font2.render(f"------------Currently Present------------", True, pallet_one, pallet_three).convert())
        for occupant in present:
            self.lines.append(font2.render(f"{occupant['name']}: Arrived at "
                                           f"{datetime.datetime.fromtimestamp(occupant['updated_at']).strftime('%I:%M:%S%p-%m/%d/%y')}"
                                           , True, pallet_one, pallet_three).convert())
            self.lines.append(font3.render(f" Connection: {'Stable' if occupant['stable'] else 'Unstable'}"
                                           , True, pallet_one, pallet_three).convert())
        self.lines.append(font2.render(f"---------------Not Present---------------", True, pallet_one, pallet_three).convert())
        for occupant in absent:
            self.lines.append(font2.render(f"{occupant['name']}: Last seen at "
                                           f"{datetime.datetime.fromtimestamp(occupant['updated_at']).strftime('%I:%M:%S%p-%m/%d/%y')}"
                                           , True, pallet_one, pallet_three).convert())
            self.lines.append(font3.render(f" Connection: Lost"
                                           , True, pallet_one, pallet_three).convert())

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
            shift = 0
            pygame.draw.line(screen, pallet_two, (x + 15 + (220 * shift), 120), (x + 15 + (220 * shift), 440))
            count = 0
            for line in self.side_lines:
                if count % 2 == 0:
                    if y + 18 + (20 * (count + 1)) > screen.get_height() - 60:
                        shift += 1
                        count = 0
                        pygame.draw.line(screen, pallet_two, (x + 15 + (220 * shift), 120), (x + 15 + (220 * shift), 440))
                screen.blit(line, (x + 20 + (220 * shift), y + 18 + (20 * count)))
                count += 1
            shift += 1
            pygame.draw.line(screen, pallet_two, (x + 15 + (220 * shift), 120), (x + 15 + (220 * shift), 440))
