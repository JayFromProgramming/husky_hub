import os
import threading
import time
import traceback

import serial


class Coprocessor:

    def __init__(self, port, baudrate=19200):
        self.port = port
        self.baudrate = baudrate
        self.arduino = None
        self.ready = False
        self.connected = False
        self.enabled = False
        self.establish_connection()
        self.last_update = 0
        self.data_slots = []
        self.last_data_slots = []
        self.current_uploaded_image = None
        self.pause_refresh = False
        for i in range(0, 16):
            self.data_slots.append(None)
            self.last_data_slots.append(None)
        self.returned_data = None
        self.returned_data_slots = []
        self.data_slots[6] = -1
        self.set_display_mode(0)
        self.wait_ready()

    def establish_connection(self):
        try:
            self.arduino = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
        except Exception as e:
            print(e)
            self.arduino = None
            self.connected = False

    def set_data_slot_state(self, slot: int, state):
        self.data_slots[slot] = state
        # self._send()

    def get_data(self):
        return self.returned_data

    def wait_ready(self):
        timeout_time = time.time() + 5
        if not self.connected:
            return
        while not self.ready or time.time() < timeout_time:
            time.sleep(0.1)
            self._send(immediately=True)
            if len(self.returned_data) > 3:
                self.ready = True

    def _upload_image(self, file):
        self.pause_refresh = True
        if not self.connected:
            return
        if os.path.exists(f'Assets/Splash Tiles/{file}'):
            with open(f"Assets/Splash Tiles/{file}", "rb") as f:
                for i in range(8):
                    self.data_slots[2] = 10
                    self.data_slots[8] = i
                    self._send()
                    print(f"Sending image {i}", end="\r")
                    for i in range(8):
                        data = f.read(1)
                        print(f"-{i}: {data}", end="")
                        self.arduino.write(data)
                    self.arduino.read(self.arduino.inWaiting())
                    self.data_slots[2] = 11
                    self._send()
            self.current_uploaded_image = file
        self.pause_refresh = False

    def set_display_mode(self, mode: int):
        self.data_slots[2] = mode
        self._send()

    def display_splash(self, line1: bytes = '', line2: bytes = '', file="husky.mtb"):
        if self.current_uploaded_image != file:
            self._upload_image(file=file)
        self.data_slots[0] = line1[:12]
        self.data_slots[1] = line2[:11]
        self.set_display_mode(4)

    def draw_buffered_image(self, position=12, file="husky.mtb"):
        if self.current_uploaded_image != file:
            self._upload_image(file=file)
        self.data_slots[6] = position

    def hide_buffered_image(self):
        self.data_slots[6] = -1
        self._send()

    def display_loading_bar(self, title: bytes = 'Loading bar', progress=0, immediately=False):
        if self.data_slots[2] != 3:
            self.set_display_mode(3)
        self.data_slots[0] = title
        self.data_slots[1] = int(progress)
        if immediately:
            self._send()

    def display(self, upper_line="", lower_line="", immediately=False):
        if self.data_slots[2] != 0:
            self.set_display_mode(0)
        self.data_slots[0] = upper_line[:16]
        self.data_slots[1] = lower_line[:16]
        if immediately:
            self._send()

    def start_refresh(self):
        if self.connected and not self.enabled:
            self.enabled = True
            threading.Thread(target=self._refresh_cycle).start()

    def _refresh_cycle(self):
        while self.enabled and self.connected:
            if not self.pause_refresh:
                try:
                    self._send()
                except Exception as e:
                    print(f"Arduino serial error: {e}\n{traceback.format_exc()}")
                    self.connected = False
            time.sleep(0.25)

    def _send(self, immediately=False):
        if not self.connected and self.arduino.isOpen():
            return
        self.last_update = time.time()
        data_changed = False
        for i in range(0, 16):
            if self.data_slots[i] != self.last_data_slots[i]:
                data_changed = True
        if not data_changed and not immediately:
            return
        data = b''
        for i in range(0, 16):
            if self.data_slots[i] is not None:
                if isinstance(self.data_slots[i], bytes):
                    data += self.data_slots[i]
                else:
                    data += bytes(str(self.data_slots[i]), 'ascii')
            else:
                data += b' '
            data += b'\a'
        data += b'\n'
        self.last_data_slots = self.data_slots.copy()
        print(data.split(b'\a'))
        try:
            self.arduino.write(data)
        except serial.SerialException as e:
            print(f"Arduino write error: {e}\n{traceback.format_exc()}")
            self.last_update = time.time() + 35
        try:
            self.returned_data = self.arduino.read(self.arduino.inWaiting()).split(b'\a')
        except Exception as e:
            print(f"Arduino read error: {e}\n{traceback.format_exc()}")
            self.connected = False
            for i in range(0, 8):
                self.returned_data[i] = None
        print(self.returned_data)
