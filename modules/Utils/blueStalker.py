import datetime
import random
import threading
import time
import traceback

import bluetooth


class BlueStalker:

    def __init__(self, target_devices: list, targets: dict):
        self.target_devices = target_devices
        self.failed_attempts = 0
        self.ready = False
        self.total_devices_detected = 0
        self.room_occupied = True
        self.targets = targets.copy()
        self.temp_targets = targets
        for target in self.target_devices:
            if target[1] not in self.targets.keys():
                self.targets[target[1]] = {"name": target[0], "updated_at": 0, "present": None, "stable": None, "mac": target[1]}
        self.socket_connections = []
        self.already_stalking = False
        self.stalk_error = False
        self.stalker_logs = []

    def check_inventory(self):
        for sock, mac_address in self.socket_connections:
            try:
                self.stalker_logs.append(f"[*] Checking if {mac_address} is still connected")
                sock.getpeername()  # Check if the socket is alive
                # self.stalker_logs.append(f"[*] {mac_address} is still connected")
            except bluetooth.BluetoothError:  # If not, remove it from the connected socket list
                self.stalker_logs.append(f"[!] {mac_address} is not connected anymore")
                self.socket_connections.remove((sock, mac_address))

    def seek_device(self, target_name: str, target_mac: str):
        try:
            print("[*] Attempting to connect to " + target_name)
            self.stalker_logs.append("[*] Attempting to connect to " + target_name)
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.connect((target_mac, 1))
            self.socket_connections.append((sock, target_mac))
            print("[*] Connected to " + target_name)
            self.stalker_logs.append("[*] Connected to " + target_name)
            if not self.targets[target_mac]['present']:
                self.targets[target_mac]['updated_at'] = time.time()
            self.targets[target_mac]['present'] = True
            self.targets[target_mac]['stable'] = True

            self.total_devices_detected += 1
        except bluetooth.btcommon.BluetoothError as e:
            if str(e) == "[Errno 111] Connection refused":
                print(f"[!] {target_name} refused connection")
                self.stalker_logs.append(f"[*] {target_name} refused connection but is present")
                self.targets[target_mac]['present'] = True
                self.targets[target_mac]['stable'] = False
                self.total_devices_detected += 1
            else:
                print("[!] Failed to connect to " + target_name)
                self.stalker_logs.append(f"[!] Failed to connect to {target_name} because {e}")
                if self.targets[target_mac]['present'] is not False:
                    self.targets[target_mac]['updated_at'] = time.time()
                self.targets[target_mac]['present'] = False
                self.targets[target_mac]['stable'] = False
        except OSError as e:
            print("[!] Failed to connect to " + target_name)
            self.stalker_logs.append(f"[!] Failed to connect to {target_name} because {e}")
            if self.targets[target_mac]['present'] is not False:
                self.targets[target_mac]['updated_at'] = time.time()
            self.targets[target_mac]['present'] = False
            self.targets[target_mac]['stable'] = False

    def background_stalk(self):
        if not self.already_stalking:
            self.already_stalking = True
            threading.Thread(target=self.stalk, daemon=True).start()

    def stalk(self):
        self.stalker_logs = []
        print("[*] Starting stalk")
        self.stalker_logs.append(f"[*] Starting stalk: {datetime.datetime.now()}")
        self.stalker_logs.append(f"[*] Targets: {self.targets}")
        print(f"[*] Targets: {self.targets}")
        self.stalker_logs.append(f"[*] Temp Targets: {self.temp_targets}")
        print(f"[*] Temp Targets: {self.temp_targets}")
        self.ready = True
        try:
            self.stalk_error = False
            self.total_devices_detected = 0
            search_threads = []
            # Find devices in self.targets that don't have a connection in self.socket_connections
            for target_name, target_mac in self.target_devices:
                already_connected = False
                for sock, mac_address in self.socket_connections:
                    if mac_address == target_mac:
                        self.stalker_logs.append(f"[*] {mac_address}: {target_name} is already connected")
                        self.targets[target_mac]['present'] = True
                        self.targets[target_mac]['stable'] = True
                        already_connected = True
                        self.total_devices_detected += 1
                        continue
                if not already_connected:
                    self.stalker_logs.append(f"[*] {target_mac}: {target_name} is not connected, starting seek thread")
                    search_threads.append(threading.Thread(target=self.seek_device, args=(target_name, target_mac), daemon=True))

            for thread in search_threads:
                thread.start()

            for thread in search_threads:
                thread.join()

            if self.total_devices_detected > 0:
                self.room_occupied = True
                self.failed_attempts = 0
            else:
                self.failed_attempts += 1
                if self.failed_attempts > 2:
                    self.room_occupied = False
            self.stalker_logs.append(f"[*] {self.total_devices_detected} devices detected")
            self.stalker_logs.append(f"[*] Stalk Completed {datetime.datetime.now()}")
            self.already_stalking = False
        except Exception as e:
            print(f"[!] Failed to stalk because {e}\n{traceback.format_exc()}")
            self.stalk_error = True
            self.already_stalking = False
            self.room_occupied = True
            self.stalker_logs.append(f"[!] Failed to stalk because {e}\n{traceback.format_exc()}")
