import io
import json
import os
import time

import pygame
import datetime

import requests

pallet_one = (255, 206, 0)
pallet_two = (0, 0, 0)
pallet_three = (255, 255, 255)

api_file = "../APIKey.json"
monkey_routines = "Monkey.json"


class RoutineButton:

    def __init__(self, action):
        self.action = action
        self.run = False
        self.color = [64, 64, 64]
        self.button = None
        self.last_run = time.time()
        self.color_changed = False

    def draw(self, screen, pos):
        x, y = pos
        font2 = pygame.font.SysFont('timesnewroman', 20)

        if time.time() > self.last_run + 1.5 and self.color_changed:
            self.color = [64, 64, 64]
            self.color_changed = False

        self.button = pygame.Rect(x, y, 75, 60)
        text = font2.render(self.action["name"], True, pallet_three)

        pygame.draw.rect(screen, self.color, self.button)
        screen.blit(text, text.get_rect(center=self.button.center))


class RoutineTile:

    def __init__(self, request_name, data):
        self.request_name = request_name
        self.description = data["description"]
        self.routine_title = data["title"]
        self.routine_actions = data["actions"]
        self.button = None
        self.action_buttons = []
        self.running_routine = None
        self.running_status = [255, 255, 255]

        count = 0  # 95
        for thing, action in self.routine_actions.items():
            self.action_buttons.append(RoutineButton(action))
            # self.action_buttons.append(pygame.Rect(, 75, 60))
            # self.action_text.append(font2.render(action["name"], True, pallet_two))
            count += 1

    def check_collide(self, mouse_pos):
        count = 0
        for button in self.action_buttons:
            if button.button.collidepoint(mouse_pos):
                button.run = True
                button.color = [64, 64, 200]
                # return self.routine_actions[str(count)]["request"]
            count += 1

        return None

    def draw_routine(self, screen, position):
        x, y = position
        font1 = pygame.font.SysFont('timesnewroman', 30)
        font2 = pygame.font.SysFont('timesnewroman', 20)
        title = font1.render(f"{self.routine_title}", True, pallet_two)
        description = font2.render(f"{self.description}", True, pallet_two)
        # self.action_buttons = []
        self.button = pygame.Rect(x, y, 700, 70)

        pygame.draw.rect(screen, [255, 206, 0], self.button)
        # pygame.draw.rect(screen, [64, 64, 64], self.action_buttons[1])
        screen.blit(title, title.get_rect(topleft=(x + 7, y)))
        screen.blit(description, description.get_rect(topleft=(x + 10, y + 30)))
        count = 0
        for button in self.action_buttons:
            button.draw(screen, (x + 215 + (95 * count), y + 5))
            # pygame.draw.rect(screen, [64, 64, 64], button)
            # screen.blit(self.action_text[count], self.action_text[count].get_rect(center=button.center))
            count += 1


class AlexaIntegration:

    def __init__(self, log):
        """"""
        self.routines = []
        self.queued_routine = None
        self.clear_time = time.time()
        if os.path.isfile(api_file):
            with open(api_file) as f:
                apikey = json.load(f)
                self.api_token = apikey['monkey_token']
                self.api_secret = apikey['monkey_secret']
        else:
            log.critial("No api key file found")
            raise FileNotFoundError("No api key file found")
        if os.path.isfile(monkey_routines):
            with open(monkey_routines) as f:
                monkey = json.load(f)
                self.monkeys = monkey
        else:
            log.critial("No monkey file found")
            raise FileNotFoundError("No monkey file found")

    def run_queued(self):
        for routine in self.routines:
            for button in routine.action_buttons:
                if button.run is True:
                    if self.run_routine(button.action['request']):
                        button.color = [0, 255, 0]
                    else:
                        button.color = [255, 0, 0]
                    button.run = False
                    button.color_changed = True
                    button.last_run = time.time()
            time.sleep(0.05)

    def run_routine(self, request):
        query = str(request).format(access_token=self.api_token, secret_token=self.api_secret)
        # print(query)
        try:
            r = requests.get(url=query)
        except requests.exceptions.ConnectionError:
            return False
        except requests.exceptions.MissingSchema:
            return False
        # print(f"Code: {r.status_code}, Response: {r.json()}")
        if r.status_code == 200 and r.json()['status'] == "success":
            return True
        else:
            return False

    def build_routines(self):
        for routine, items in self.monkeys.items():
            # print(routine)
            # print(items)
            self.routines.append(RoutineTile(routine, items))

    def check_click(self, mouse_pos):
        for routine in self.routines:
            if routine.check_collide(mouse_pos):
                return routine.check_collide(mouse_pos)

    def draw_routine(self, screen):
        scroll = 40
        for routine in self.routines:
            routine.draw_routine(screen, (50, scroll))
            scroll += 80
