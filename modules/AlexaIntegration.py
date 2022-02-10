import io
import json
import logging
import os
import threading
import time
import traceback
import typing
import random

import pygame
import datetime

import requests

# from modules.Coordinator import Coordinator

pallet_one = (255, 206, 0)
pallet_two = (0, 0, 0)
pallet_three = (255, 255, 255)

api_file = "../APIKey.json"
monkey_routines = "Configs/Monkey.json"


# This is the main class for the Alexa integration.

class RoutineButton:

    def __init__(self, host_bar, data, ident):
        """
        This is the constructor for the RoutineButton class.
        :param host_bar: The host bar that the button is in.
        :param data: The button configuration data.
        """
        self.data = data
        self.id = ident
        self.name = data['name']
        self.run = False
        self.button = None
        self.last_run = time.time()
        self.last_state_refresh = time.time() + (random.randint(0, 50) / 100)
        self.color_changed = False
        self.status_color_enabled = False
        self.host_bar: typing.Union[OptionBar, SubOptionBar] = host_bar
        self.request_thread = None
        self.thread_second_action = None
        self.request_success = None
        self.font2 = pygame.font.SysFont('timesnewroman', 20)
        self.surf = None
        self.type = data["type"]
        if "state_exec" in self.data:
            threading.Thread(target=self._exec, args=(self, self.data['state_exec'])).start()
        if "requests" in self.data:
            self.req = self.data["requests"]
        if self.status_color_enabled:
            self.color = [64, 128, 255]
        else:
            self.color = [64, 64, 64]
        self.render_self()

    def update_state(self):
        if "state_exec" in self.data:
            threading.Thread(target=self._exec, args=(self, self.data['state_exec'])).start()
            # exec(self.data['state_exec'])
            if (not self.host_bar.host.coordinator.is_connected() and self.status_color_enabled is True) or self.status_color_enabled is None:
                self.color = [255, 64, 64]
            elif self.status_color_enabled is True:
                self.color = [64, 128, 255]
            elif self.status_color_enabled is False:
                self.color = [64, 64, 64]
        elif time.time() > self.last_run + 0.75:
            self.color = [64, 64, 64]
        self.render_self()

    def render_self(self):
        """
        Render the button surface.
        :return: None
        """
        self.surf = pygame.Surface((75, 60))

        button = pygame.Rect(0, 0, 75, 60)
        text = self.font2.render(self.name, True, pallet_three)

        pygame.draw.rect(self.surf, self.color, button)
        self.surf.blit(text, text.get_rect(center=button.center))

        self.surf = self.surf.convert()

    def preform_action(self):
        """
        Run the queued action associated with the button.
        :return: None
        """
        self.request_success = None
        if self.thread_second_action:
            print(f"Running second action for {self.name}, {self.thread_second_action}")
            action = self.thread_second_action
            self.thread_second_action = None
            self.run = False
            return action
        else:
            if self.type == "action":
                self.run = False
                if "eval" in self.data:
                    self.request_thread = threading.Thread(target=self._exec, args=(self, self.data['eval'])).start()
                return self.data['request']
            elif self.type == "SubMenu":
                self.run = False
                self.color_changed = True
                self.request_success = True
                self.last_run = time.time()
                if self.host_bar.expanded and self.host_bar.expanded_to == self:
                    self.host_bar.collapse()
                    self.name = self.data['name']
                else:
                    self.host_bar.collapse()
                    self.host_bar.expand(self)
                    self.name = self.data['name_2']
                return "no_routine"
            elif self.type == "code":
                self.request_thread = threading.Thread(target=self._exec, args=(self, self.data['eval'])).start()
                return "exec"
            elif self.type == "toggle":
                self.run = False
                if self.data['current_state']:
                    self.data['current_state'] = False
                    return self.data['requests'][1]
                else:
                    self.data['current_state'] = True
                    return self.data['requests'][0]

    def _exec(self, thread, code):
        """
        Execute custom button code in a separate thread.
        :param thread: The thread that is running the code.
        :param code: The code to be executed.
        :return:
        """
        try:
            self.run = False
            exec(code)
            # print(f"{self.name} executed successfully.")
            if self.thread_second_action:
                self.run = True
            else:
                self.request_success = True
        except Exception as err:
            print(f"Custom code button({self.name}:{self.id}) error: {err} Traceback: {traceback.format_exc()}")
            self.request_success = False
            return

    def draw(self, screen, pos):
        """
        Draw the button to the screen.
        :param screen: The screen to draw the button to.
        :param pos: The X,Y position to draw the button at.
        :return: None
        """
        x, y = pos

        if self.color_changed:
            self.render_self()

        if self.last_state_refresh < time.time() - 5 and not self.color_changed:
            self.update_state()
            self.last_state_refresh = time.time() + (random.randint(0, 25) / 100)

        if time.time() > self.last_run + 0.75 and self.color_changed and self.request_success is not None:
            self.update_state()
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
            self.render_self()

        self.button = pygame.Rect(x, y, 75, 60)

        if self.data['type'] == "spacer":
            return

        screen.blit(self.surf, (x, y))


class OptionBar:

    def __init__(self, request_name, data, host):
        """
        Initialize an option bar.
        :param request_name: The name of the request section
        :param data: The data associated with the request section
        :param host: The main screen object.
        """
        self.request_name = request_name
        self.description = data["description"]
        self.routine_title = data["title"].format(room_temp=round(host.coordinator.get_temperature(), 2),
                                                  room_humid=round(host.coordinator.get_humidity(), 2))
        # self.routine_actions = [list(data["actions"].items())[i:i+5] for i in range(0, len(list(data["actions"].items())), 5)]
        self.routine_actions = data['actions']
        self.button = None
        self.action_buttons = []
        self.sub_menus = []
        self.running_routine = None
        self.running_status = [255, 255, 255]
        self.expanded = False
        self.expanded_to = None
        self.host: AlexaIntegration = host
        self.font1 = pygame.font.SysFont('timesnewroman', 30)
        self.font2 = pygame.font.SysFont('timesnewroman', 20)

        count = 0  # 95
        for ident, action in dict(self.routine_actions).items():
            # print(action)
            self.action_buttons.append(RoutineButton(self, action, ident))
            # self.action_buttons.append(pygame.Rect(, 75, 60))
            # self.action_text.append(font2.render(action["name"], True, pallet_two))
            count += 1

    def check_collide(self, mouse_pos):
        """
        Check if the mouse is colliding with any of the option bars buttons.
        :param mouse_pos: The current X,Y position of the mouse.
        :return: The button object that was clicked.
        """
        count = 0
        for button in self.action_buttons:
            if button is None:
                continue
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
        """
        Expand the option bar to show the sub-menus.
        :param button: The button that was clicked to expand the option bar.
        :return: None
        """
        self.sub_menus = []
        self.expanded = True
        self.expanded_to = button
        count = 0
        for page in button.data['sub_menus']:
            self.sub_menus.append(SubOptionBar(self, page['actions'], page['name']))
            count += 1

    def collapse(self):
        """
        Collapse the option bar to show the main menu.
        :return: None
        """
        self.host.vertical_scroll_offset = 0
        self.sub_menus = []
        if self.expanded_to:
            self.expanded_to.name = self.expanded_to.data['name']
        self.expanded = False
        self.expanded_to = None

    def draw_routine(self, screen, position):
        """
        Draw the routine title and description along with all associated buttons.
        :param screen: The screen to draw the the option bar and buttons to.
        :param position: The X,Y position of the option bar.
        :return: None
        """
        x, y = position
        if y > screen.get_height() - 80:
            return

        title = self.font1.render(f"{self.routine_title}", True, pallet_two)
        description = self.font2.render(f"{self.description}", True, pallet_two)
        # self.action_buttons = []

        count = 80
        for sub_bar in self.sub_menus:
            # For each sub menu, draw the sub menu 80
            sub_bar.draw_routine(screen, (x, y + count))
            self.host.scroll += 80
            if self.host.scroll > screen.get_height() - 80:
                self.host.vertical_scroll_offset += 80
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
        """
        Create a sub-option bar to show the sub-menus of a master option bar.
        :param master_bar: The master option bar that this sub-option bar is a part of.
        :param my_buttons: The buttons that are part of this sub-option bar.
        :param name: The name of this sub-option bar.
        """
        self.master_bar: OptionBar = master_bar
        self.host: AlexaIntegration = master_bar.host
        self.name = name
        self.name_template = name
        self.button = None
        self.action_buttons = []
        self.running_routine = None
        self.running_status = [255, 255, 255]
        self.font2 = pygame.font.SysFont('timesnewroman', 19)
        count = 0
        for ident, action in my_buttons.items():
            self.action_buttons.append(RoutineButton(self, action, ident))
            # self.action_buttons.append(pygame.Rect(, 75, 60))
            # self.action_text.append(font2.render(action["name"], True, pallet_two))
            count += 1

    def check_collide(self, mouse_pos):
        """
        Check if the mouse is colliding with any of the buttons in this sub-option bar.
        :param mouse_pos: The X,Y position of the mouse.
        :return: If the mouse is colliding with any of the buttons in this sub-option bar.
        """
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
        """
        Draw the sub-option bar and all associated buttons.
        :param screen: The screen to draw the sub-option bar and buttons to.
        :param position: The X,Y position of the sub-option bar.
        :return: None
        """
        temp = round(self.host.coordinator.get_temperature(), 2)
        humid = round(self.host.coordinator.get_humidity(), 2)
        set_temp = self.host.coordinator.get_temperature_setpoint(False)
        self.name = self.name_template.format(room_temp=f"{temp}F" if temp != -9999 else "N/A", room_humid=f"{humid}%" if humid != -1 else "N/A",
                                              set_temp=f"{set_temp}F" if set_temp is not None else "N/A")
        x, y = position
        # self.action_buttons = []
        self.button = pygame.Rect(x + 50, y, 650, 70)
        description = self.font2.render(f"{self.name}", True, pallet_two)
        pygame.draw.line(screen, pallet_one, (x + 15, y - 50), (x + 15, y + 35))
        pygame.draw.line(screen, pallet_one, (x + 15, y + 35), (x + 50, y + 35))
        pygame.draw.rect(screen, [255, 206, 0], self.button)
        screen.blit(description, description.get_rect(midleft=(x + 60, y + 35)))
        # pygame.draw.rect(screen, [64, 64, 64], self.action_buttons[1])
        count = 0
        for button in self.action_buttons:
            button.draw(screen, (x + 215 + (95 * count), y + 5))
            # pygame.draw.rect(screen, [64, 64, 64], button)
            # screen.blit(self.action_text[count], self.action_text[count].get_rect(center=button.center))
            count += 1


class AlexaIntegration:

    def __init__(self, log, coordinator):
        """
        Create an object to handle the Alexa integration.
        :param log: The clients logging handler
        :param coordinator: The room coordinator object to use for the Alexa integration device synchronization and temperature control.
        """
        self.routines = []
        self.coordinator = coordinator
        self.queued_routine = False
        self.scroll = 0
        self.vertical_scroll_offset = 0
        self.open_since = 0
        self.raincheck = False
        self.log = logging.getLogger(__name__)
        if os.path.isfile(api_file):
            with open(api_file) as f:
                apikey = json.load(f)
                self.api_token = apikey['monkey_token']
                self.api_secret = apikey['monkey_secret']
        else:
            self.log.critical("No api key file found")
            self.monkeys = {}
            # raise FileNotFoundError("No api key file found")
        if os.path.isfile(monkey_routines):
            with open(monkey_routines) as f:
                monkey = json.load(f)
                self.monkeys = monkey
        else:
            self.log.critical("No monkey file found")
            self.monkeys = {}
            # raise FileNotFoundError("No monkey file found")

    def change_occupancy(self, occupied):
        """
        Change the occupancy of the room.
        :param occupied: The new occupancy of the room.
        :return: None
        """
        state = self.coordinator.get_object_state('room_state')
        if self.coordinator.get_object_state('room_state_auto'):
            if occupied:
                if state != 1 and state != 3:
                    self.run_routine(None, 'normal')
                    self.coordinator.set_object_state('room_state', 1)
                    self.coordinator.set_object_state('bed_fan_state', False)
                    self.coordinator.set_object_states('room_lights_state', b=3, c=0)
                    self.coordinator.set_object_states('bed_lights_state', b=3, c=0)
                    self.run_routine(None, 'normal')
                # if self.coordinator.get_object_state('room_state') == 0:
            else:
                if state != 2 and state != 3:
                    self.run_routine(None, 'away')
                    self.coordinator.set_object_state('room_state', 2)
                    self.coordinator.set_object_state('bed_fan_state', False)
                    self.coordinator.set_object_states('room_lights_state', b=0, c=1)
                    self.coordinator.set_object_states('bed_lights_state', b=1, c=1)
                    self.run_routine(None, 'away')

    def run_queued(self):
        """
        Run all queued button actions.
        :return: None
        """

        def check_button(test_button):
            """
            Check if the button is pressed, and if so, run the associated routine.
            :param test_button: The button to check.
            :return: None
            """
            if test_button.run is True:
                action = test_button.preform_action()
                if action == "no_routine":
                    test_button.color = [0, 0, 255]
                    test_button.color_changed = True
                    test_button.last_run = time.time()
                    self.queued_routine = False
                elif action == "exec":
                    test_button.color = [0, 0, 255]
                    test_button.color_changed = True
                    test_button.last_run = time.time()
                    self.queued_routine = True
                else:
                    thread = threading.Thread(target=self.run_routine, args=(self, action, test_button))
                    thread.start()
                    test_button.request_thread = thread
                    # if self.run_routine(action):
                    #     test_button.color = [0, 255, 0]
                    # else:
                    #     test_button.color = [255, 0, 0]
                    self.queued_routine = False
                self.open_since = time.time()

        for routine in self.routines:
            for button in routine.action_buttons:
                check_button(button)
            for submenu in routine.sub_menus:
                for button in submenu.action_buttons:
                    check_button(button)

        for routine in self.routines:
            for button in routine.action_buttons:
                button.update_state()
            for submenu in routine.sub_menus:
                for button in submenu.action_buttons:
                    button.update_state()

    def run_routine(self, test, request, test_button=None):
        """
        Run a voicemonkey routine.
        :param test: Filler value
        :param request: The URL of the request
        :param test_button: The button to update if the routine is successful.
        :return: None
        """
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

    def build_routines(self):
        """
        Build the option bars for the routine selection.
        :return: None
        """
        for routine, items in self.monkeys.items():
            # print(routine)
            # print(items)
            self.routines.append(OptionBar(routine, items, self))

    def refresh_all_states(self):
        """
        Refresh all button states.
        :return: None
        """
        for routine in self.routines:
            routine.refresh_all_states()

    def check_click(self, mouse_pos):
        """
        Check all the buttons in all the option bars to see if the mouse has clicked one of them.
        :param mouse_pos: The X,Y position of the mouse.
        :return: The button that was clicked, or None if no button was clicked.
        """
        for routine in self.routines:
            val = routine.check_collide(mouse_pos)
            if val:
                self.queued_routine = True
                return val

    def draw_routine(self, screen, offset):
        """
        Draw all of the option bars, and their buttons.
        :param screen: The screen to draw to.
        :param offset: The vertical offset of the option bars.
        :return: None
        """

        if self.coordinator.last_download < time.time() - 10:
            self.coordinator.read_states()
            # self.refresh_all_states()

        self.scroll = offset + 40 - self.vertical_scroll_offset
        for routine in self.routines:
            routine.draw_routine(screen, (50, self.scroll))
            self.scroll += 80
