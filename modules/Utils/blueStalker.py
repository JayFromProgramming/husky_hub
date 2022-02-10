import datetime
import logging
import random
import threading
import time
import traceback

import bluetooth

logging.getLogger(__name__)


class BlueStalker:

    def __init__(self, target_devices: list, targets: dict):
        self.target_devices = target_devices
        self.non_priority_devices = []
        for target in self.target_devices:
            if target[2] is False:
                self.non_priority_devices.append(target)
        self.failed_attempts = 0
        self.ready = False
        self.total_devices_detected = 0
        self.seek_offset = 0
        self.max_seek = 2
        self.room_occupied = True
        self.targets = targets.copy()
        self.temp_targets = targets
        for target in target_devices:
            if target[1] not in self.targets.keys():
                self.targets[target[1]] = {"name": target[0], "updated_at": 0, "present": None, "stable": None, "mac": target[1],
                                           "priority": target[2]}
        self.socket_connections = []
        self.already_stalking = False
        self.stalk_error = False
        self.stalker_logs = []

    def check_inventory(self):
        for sock, mac_address in self.socket_connections:
            try:
                logging.debug(f"[*] Checking if {mac_address} is still connected")
                sock.getpeername()  # Check if the socket is alive
                # self.stalker_logs.append(f"[*] {mac_address} is still connected")
            except bluetooth.BluetoothError:  # If not, remove it from the connected socket list
                logging.info(f"[!] {mac_address} is not connected anymore")
                self.socket_connections.remove((sock, mac_address))
                if self.targets[mac_address]['present'] is not False:
                    self.targets[mac_address]['updated_at'] = time.time()
                self.targets[mac_address]['present'] = False
                self.targets[mac_address]['stable'] = False

        if len(self.socket_connections) > 0:
            self.room_occupied = True
            self.failed_attempts = 0
        else:
            self.room_occupied = False

    def seek_device(self, target_name: str, target_mac: str):
        try:
            print("[*] Attempting to connect to " + target_name)
            logging.debug("[*] Attempting to connect to " + target_name)
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.connect((target_mac, 1))
            self.socket_connections.append((sock, target_mac))
            print("[*] Connected to " + target_name)
            logging.info("[*] Connected to " + target_name)
            if not self.targets[target_mac]['present']:
                self.targets[target_mac]['updated_at'] = time.time()
            self.targets[target_mac]['present'] = True
            self.targets[target_mac]['stable'] = True

            self.total_devices_detected += 1
        except bluetooth.btcommon.BluetoothError as e:
            if str(e) == "[Errno 111] Connection refused":
                print(f"[!] {target_name} refused connection")
                logging.debug(f"[*] {target_name} refused connection but is present")
                self.targets[target_mac]['present'] = True
                self.targets[target_mac]['stable'] = False
                self.total_devices_detected += 1
            else:
                print("[!] Failed to connect to " + target_name)
                logging.debug(f"[!] Failed to connect to {target_name} because {e}")
                if self.targets[target_mac]['present'] is not False:
                    self.targets[target_mac]['updated_at'] = time.time()
                self.targets[target_mac]['present'] = False
                self.targets[target_mac]['stable'] = False
        except OSError as e:
            print("[!] Failed to connect to " + target_name)
            logging.debug(f"[!] Failed to connect to {target_name} because {e}")
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
        logging.info(f"[*] Starting stalk: {datetime.datetime.now()}")
        logging.debug(f"[*] Targets: {self.targets}")
        logging.debug(f"[*] Temp Targets: {self.temp_targets}")
        self.ready = True
        try:
            self.stalk_error = False
            self.total_devices_detected = 0
            search_threads = []
            seeked_this_round = 0
            # Find devices in self.targets that don't have a connection in self.socket_connections
            index = 0
            self.seek_offset += 1
            for target_name, target_mac, priority in self.target_devices:
                already_connected = False
                for sock, mac_address in self.socket_connections:
                    if mac_address == target_mac:
                        logging.debug(f"[*] {mac_address}: {target_name} is already connected")
                        self.targets[target_mac]['present'] = True
                        self.targets[target_mac]['stable'] = True
                        already_connected = True
                        self.total_devices_detected += 1
                        continue
                if not already_connected:
                    if priority:
                        logging.debug(f"[*] {target_mac}: {target_name} is not connected, starting seek thread")
                        search_threads.append(threading.Thread(target=self.seek_device, args=(target_name, target_mac), daemon=True))
                        seeked_this_round += 1
                    else:
                        index += 1
                        target_name, target_mac, priority = \
                            self.non_priority_devices[(index + self.seek_offset) % len(self.non_priority_devices)]
                        if seeked_this_round < self.max_seek:
                            logging.debug(f"[*] {target_mac}: {target_name} is not connected, starting seek thread")
                            search_threads.append(threading.Thread(target=self.seek_device, args=(target_name, target_mac), daemon=True))
                            seeked_this_round += 1
                        else:
                            logging.debug(f"[*] {target_mac}: {target_name} is not connected, skipping seek thread due to max_seek")

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
            logging.debug(f"[*] {self.total_devices_detected} devices detected")
            logging.debug(f"[*] Stalk Completed {datetime.datetime.now()}")
            self.already_stalking = False
        except Exception as e:
            self.stalk_error = True
            self.already_stalking = False
            self.room_occupied = True
            logging.error(f"[!] Failed to stalk because {e}\n{traceback.format_exc()}")
