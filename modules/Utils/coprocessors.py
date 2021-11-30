import os
import threading
import time
import traceback

import serial


class Coprocessor:

    def __init__(self, port: list, baudrate: list = 19200, should_connect=True):
        self.port = port
        self.baudrate = baudrate
        self.arduino = [None, None]
        self.ready = False
        self.connected = [False, False]
        self.enabled = False
        self.lcd_backlight_preferred_state = 0
        self.should_connect = should_connect
        if should_connect:
            self.establish_connection(target_arduino=0)
            self.establish_connection(target_arduino=1)
        self.last_update = [time.time() - 1, time.time() - 1]
        self.data_slots = [[], []]
        self.last_data_slots = [[], []]
        self.current_uploaded_image = None
        self.pause_refresh = False
        for i in range(0, 16):
            self.data_slots[0].append(None)
            self.data_slots[1].append(None)
            self.last_data_slots[0].append(None)
            self.last_data_slots[1].append(None)
        self.returned_data = [[], []]
        self.returned_data_slots = [[], []]
        self.data_slots[0][6] = -1
        self.set_state(0)
        self.wait_ready()
        self.lcd_backlight(1)

    def establish_connection(self, target_arduino=0):
        if not self.should_connect:
            return
        print(f"[*] Establishing connection to arduino {target_arduino} on {self.port[target_arduino]}")
        try:
            self.arduino[target_arduino] = serial.Serial(self.port[target_arduino], self.baudrate[target_arduino], timeout=0.25)
            self.connected[target_arduino] = True
            print(f"[*] Connection established to arduino {target_arduino} on {self.port[target_arduino]}")
        except Exception as e:
            print(f"[!] Failed to establish connection to arduino {target_arduino} on {self.port[target_arduino]} {e}\n{traceback.format_exc()}")
            self.connected[target_arduino] = False

    def close_all(self):
        self.ready = False
        for i in range(0, 2):
            if self.connected[i]:
                self.arduino[i].close()
                self.connected[i] = False
                self.enabled = False

    def set_data_slot_state(self, slot: int, state):
        self.data_slots[slot] = state
        # self._send()

    def update_lcd_backlight_state(self, override=False, override_state: int = None):
        if self.lcd_backlight_preferred_state != self.data_slots[0][4] and not override:
            self.data_slots[0][4] = self.lcd_backlight_preferred_state
            self._send(target_arduino=0, immediately=True)
        elif override:
            self.data_slots[0][4] = override_state
            self._send(target_arduino=0, immediately=True)
        else:
            pass

    def lcd_backlight(self, state: int, immediately=False):
        self.data_slots[0][4] = state
        self.lcd_backlight_preferred_state = state
        self._send(target_arduino=0, immediately=immediately)

    def get_data(self, target_arduino=0):
        return self.returned_data[target_arduino]

    def get_state(self, target_arduino=0):
        return self.data_slots[target_arduino]

    def wait_ready(self):
        timeout_time = time.time() + 5
        if not self.connected[0] and not self.connected[1]:
            return
        while not self.ready and time.time() < timeout_time:
            time.sleep(0.1)
            if self.connected[0]:
                self._send(immediately=True, target_arduino=0)
            if self.connected[1]:
                self._send(immediately=True, target_arduino=1)
            if len(self.returned_data[0]) > 3 and len(self.returned_data[1]) > 3:
                self.ready = True

    def _upload_image(self, file, target_arduino=0):
        self.pause_refresh = True
        if not self.connected[target_arduino]:
            return
        if os.path.exists(f'Assets/Splash Tiles/{file}'):
            with open(f"Assets/Splash Tiles/{file}", "rb") as f:
                for i in range(8):
                    self.data_slots[target_arduino][2] = 10
                    self.data_slots[target_arduino][8] = i
                    self._send(immediately=True, target_arduino=target_arduino)
                    time.sleep(0.1)
                    print(f"Sending image {i}", end="\r")
                    for _ in range(8):
                        data = f.read(1)
                        print(f"-{i}: {data}", end="")
                        self.arduino[target_arduino].write(data)
                    self.arduino[target_arduino].read(self.arduino[target_arduino].inWaiting())
                    self.data_slots[target_arduino][2] = 11
                    self._send(immediately=True, target_arduino=target_arduino)
            self.current_uploaded_image = file
        self.pause_refresh = False

    def set_state(self, mode: int, target_arduino=0, immediately=False):
        self.data_slots[target_arduino][2] = mode
        self._send(immediately=immediately, target_arduino=target_arduino)

    def update_sensors(self):
        self.pause_refresh = True
        self.set_state(20, target_arduino=0, immediately=True)
        self.set_state(20, target_arduino=1, immediately=True)
        self.set_state(-1, target_arduino=0, immediately=False)
        self.set_state(-2, target_arduino=1, immediately=False)
        self.pause_refresh = False

    def display_splash(self, line1: bytes = '', line2: bytes = '', file="husky.mtb", target_arduino=0):
        if self.current_uploaded_image != file:
            self._upload_image(file=file)
        self.data_slots[target_arduino][0] = line1[:12]
        self.data_slots[target_arduino][1] = line2[:11]
        self.set_state(4)

    def draw_buffered_image(self, position=12, file="husky.mtb", target_arduino=0):
        if self.current_uploaded_image != file:
            self._upload_image(file=file)
        self.data_slots[target_arduino][6] = position

    def hide_buffered_image(self):
        self.data_slots[6] = -1
        self._send()

    def display(self, upper_line="", lower_line="", immediately=False, target_arduino=0):
        if self.data_slots[target_arduino][2] != 0:
            self.set_state(0)
        self.data_slots[target_arduino][0] = upper_line[:16]
        self.data_slots[target_arduino][1] = lower_line[:16]
        if immediately:
            self._send()

    def start_refresh(self):
        if self.connected and not self.enabled:
            self.enabled = True
            threading.Thread(target=self._refresh_cycle, args=(None, 0), daemon=True).start()
            threading.Thread(target=self._refresh_cycle, args=(None, 1), daemon=True).start()

    def _refresh_cycle(self, dummy, target_arduino=0):
        while self.enabled:
            if not self.pause_refresh:
                try:
                    if self.connected[target_arduino]:
                        self._send(target_arduino=target_arduino)
                    else:
                        self.establish_connection(target_arduino=target_arduino)
                except Exception as e:
                    print(f"Arduino {target_arduino} serial error: {e}\n{traceback.format_exc()}")
                    self.connected[target_arduino] = False

            time.sleep(0.25)

    def _send(self, immediately=False, target_arduino=0):
        if not self.connected[target_arduino]:
            return
        data_changed = False
        for i in range(0, 16):
            if self.data_slots[target_arduino][i] != self.last_data_slots[target_arduino][i]:
                data_changed = True
        if not data_changed and not immediately and self.last_update[target_arduino] + 2 > time.time():
            # print(f"Skipping update for {target_arduino}")
            return
        self.last_update[target_arduino] = time.time()
        data = b''
        for i in range(0, 16):
            if self.data_slots[target_arduino][i] is not None:
                if isinstance(self.data_slots[target_arduino][i], bytes):
                    data += self.data_slots[target_arduino][i]
                else:
                    data += bytes(str(self.data_slots[target_arduino][i]), 'ascii')
            else:
                data += b' '
            data += b'\a'
        data += b'\n'
        self.last_data_slots[target_arduino] = self.data_slots[target_arduino].copy()
        # print(data.split(b'\a')[:-1])
        try:
            self.arduino[target_arduino].write(data)
        except serial.SerialException as e:
            print(f"Arduino {target_arduino} write error: {e}\n{traceback.format_exc()}")
            self.last_update[target_arduino] = time.time() + 35
        try:
            returned_data = self.arduino[target_arduino].read(self.arduino[target_arduino].inWaiting()).split(b'\a')[:-1]
            if len(returned_data) == 8:
                self.returned_data[target_arduino] = returned_data
        except Exception as e:
            print(f"Arduino {target_arduino} read error: {e}\n{traceback.format_exc()}")
            self.connected[target_arduino] = False
            # for i in range(0, 8):
            #     self.returned_data[target_arduino][i] = None
        # print(f"Arduino[{target_arduino}]: {self.returned_data}")
