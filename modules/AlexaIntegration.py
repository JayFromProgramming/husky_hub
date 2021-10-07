import io
import json
import os
import threading
import time

import pygame
import datetime

import requests

pallet_one = (255, 206, 0)
pallet_two = (0, 0, 0)
pallet_three = (255, 255, 255)

api_file = "../APIKey.json"
monkey_routines = "Configs/Monkey.json"


class RoutineButton:

    def __init__(self, host_bar, data):
        self.data = data
        self.name = data['name']
        self.run = False
        self.color = [64, 64, 64]
        self.button = None
        self.last_run = time.time()
        self.color_changed = False
        self.type = data["type"]
        self.host_bar = host_bar
        self.request_thread = None
        self.request_success = None
        self.font2 = pygame.font.SysFont('timesnewroman', 20)

    def preform_action(self):
        if self.type == "action":
            return self.data['request']
        elif self.type == "SubMenu":
            if self.host_bar.expanded and self.host_bar.expanded_to == self:
                self.host_bar.collapse()
                self.name = self.data['name']
            else:
                self.host_bar.collapse()
                self.host_bar.expand(self)
                self.name = self.data['name_2']
            return "no_routine"
        elif self.type == "code":
            thread = threading.Thread(target=self._exec, args=(self, self.data['eval']))
            thread.start()
            self.request_thread = thread
        elif self.type == "toggle":
            if self.data['current_state']:
                self.data['current_state'] = False
                return self.data['requests'][1]
            else:
                self.data['current_state'] = True
                return self.data['requests'][0]

    def _exec(self, thread, code):
        try:
            exec(code)
        except Exception as err:
            print(f"Custom code button error: {err}")
            self.request_success = False
            return
        self.request_success = True

    def draw(self, screen, pos):
        x, y = pos

        if time.time() > self.last_run + 0.75 and self.color_changed:
            self.color = [64, 64, 64]
            self.color_changed = False

        if self.request_thread:
            if not self.request_thread.is_alive():
                self.request_thread.join()
                if self.request_success:
                    self.color = [0, 255, 0]
                    self.color_changed = True
                    self.last_run = time.time()
                else:
                    self.color = [255, 0, 0]
                    self.color_changed = True
                    self.last_run = time.time()
                self.request_thread = None

        self.button = pygame.Rect(x, y, 75, 60)
        text = self.font2.render(self.name, True, pallet_three)

        pygame.draw.rect(screen, self.color, self.button)
        screen.blit(text, text.get_rect(center=self.button.center))


class OptionBar:

    def __init__(self, request_name, data, host):
        self.request_name = request_name
        self.description = data["description"]
        self.routine_title = data["title"]
        # self.routine_actions = [list(data["actions"].items())[i:i+5] for i in range(0, len(list(data["actions"].items())), 5)]
        self.routine_actions = data['actions']
        self.button = None
        self.action_buttons = []
        self.sub_menus = []
        self.running_routine = None
        self.running_status = [255, 255, 255]
        self.expanded = False
        self.expanded_to = None
        self.host = host
        self.font1 = pygame.font.SysFont('timesnewroman', 30)
        self.font2 = pygame.font.SysFont('timesnewroman', 20)

        count = 0  # 95
        for thing, action in dict(self.routine_actions).items():
            # print(action)
            self.action_buttons.append(RoutineButton(self, action))
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
                return True
            count += 1
        for submenu in self.sub_menus:
            val = submenu.check_collide(mouse_pos)
            if val:
                return val

        return None

    def expand(self, button):
        """"""
        self.sub_menus = []
        self.expanded = True
        self.expanded_to = button
        count = 0
        for page in button.data['sub_menus']:
            self.sub_menus.append(SubOptionBar(self, page['actions'], page['name']))
            count += 1

    def collapse(self):
        self.sub_menus = []
        if self.expanded_to:
            self.expanded_to.name = self.expanded_to.data['name']
        self.expanded = False
        self.expanded_to = None

    def draw_routine(self, screen, position):
        x, y = position
        if y > 400:
            return

        title = self.font1.render(f"{self.routine_title}", True, pallet_two)
        description = self.font2.render(f"{self.description}", True, pallet_two)
        # self.action_buttons = []

        count = 80
        for sub_bar in self.sub_menus:
            sub_bar.draw_routine(screen, (x, y + count))
            self.host.scroll += 80
            count += 80

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


class SubOptionBar:

    def __init__(self, master_bar, my_buttons, name):
        """"""
        self.master_bar = master_bar
        self.host = master_bar.host
        self.name = name
        self.button = None
        self.action_buttons = []
        self.running_routine = None
        self.running_status = [255, 255, 255]
        self.font2 = pygame.font.SysFont('timesnewroman', 19)
        count = 0
        for thing, action in my_buttons.items():
            self.action_buttons.append(RoutineButton(self, action))
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
                return True
            count += 1
        return None

    def draw_routine(self, screen, position):
        x, y = position
        # self.action_buttons = []
        self.button = pygame.Rect(x + 90, y, 610, 70)
        description = self.font2.render(f"{self.name}", True, pallet_two)
        pygame.draw.line(screen, pallet_one, (x + 40, y - 50), (x + 40, y + 35))
        pygame.draw.line(screen, pallet_one, (x + 40, y + 35), (x + 90, y + 35))
        pygame.draw.rect(screen, [255, 206, 0], self.button)
        screen.blit(description, description.get_rect(midleft=(x + 100, y + 35)))
        # pygame.draw.rect(screen, [64, 64, 64], self.action_buttons[1])
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
        self.queued_routine = False
        self.scroll = 0
        self.open_since = 0
        self.raincheck = False
        if os.path.isfile(api_file):
            with open(api_file) as f:
                apikey = json.load(f)
                self.api_token = apikey['monkey_token']
                self.api_secret = apikey['monkey_secret']
        else:
            log.critical("No api key file found")
            raise FileNotFoundError("No api key file found")
        if os.path.isfile(monkey_routines):
            with open(monkey_routines) as f:
                monkey = json.load(f)
                self.monkeys = monkey
        else:
            log.critical("No monkey file found")
            self.monkeys = {}
            # raise FileNotFoundError("No monkey file found")

    def run_queued(self):
        def check_button(test_button):
            if test_button.run is True:
                action = test_button.preform_action()
                if action == "no_routine":
                    test_button.color = [0, 0, 255]
                    test_button.color_changed = True
                    test_button.last_run = time.time()
                else:
                    thread = threading.Thread(target=self.run_routine, args=(self, action, test_button))
                    thread.start()
                    test_button.request_thread = thread
                    # if self.run_routine(action):
                    #     test_button.color = [0, 255, 0]
                    # else:
                    #     test_button.color = [255, 0, 0]
                test_button.run = False
                self.queued_routine = False
                self.open_since = time.time()

        for routine in self.routines:
            for button in routine.action_buttons:
                check_button(button)
            for submenu in routine.sub_menus:
                for button in submenu.action_buttons:
                    check_button(button)

    def run_routine(self, test, request, test_button=None):
        template = "https://api.voicemonkey.io/trigger?access_token={access_token}&secret_token={secret_token}&monkey={request}"
        query = str(template).format(access_token=self.api_token, secret_token=self.api_secret, request=request)
        # print(query)

        try:
            r = requests.get(url=query)
        except requests.exceptions.ConnectionError:
            if test_button:
                test_button.request_success = False
        except requests.exceptions.MissingSchema:
            if test_button:
                test_button.request_success = False
        if test_button:
            # print(f"Code: {r.status_code}, Response: {r.json()}")
            if r.status_code == 200 and r.json()['status'] == "success":
                test_button.request_success = True
            else:
                test_button.request_success = False

    def build_routines(self, starting_point):
        for routine, items in self.monkeys.items():
            # print(routine)
            # print(items)
            self.routines.append(OptionBar(routine, items, self))

    def check_click(self, mouse_pos):
        for routine in self.routines:
            val = routine.check_collide(mouse_pos)
            if val:
                self.queued_routine = True
                return val

    def draw_routine(self, screen, offset):
        self.scroll = offset + 40
        for routine in self.routines:
            routine.draw_routine(screen, (50, self.scroll))
            self.scroll += 80
