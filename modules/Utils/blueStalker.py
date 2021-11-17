import datetime
import random
import threading
import traceback

import bluetooth


class BlueStalker:

    def __init__(self, targets: list):
        self.targets = targets
        self.failed_attempts = 0
        self.total_devices_detected = 0
        self.room_occupied = True
        self.targets_present = []
        self.socket_connections = []
        self.already_stalking = False
        self.stalk_error = False
        self.stalker_logs = []

    def background_stalk(self):
        if not self.already_stalking:
            self.already_stalking = True
            threading.Thread(target=self.stalk).start()

    def stalk(self):
        self.stalker_logs = []
        print("[*] Starting stalk")
        self.stalker_logs.append(f"[*] Starting stalk: {datetime.datetime.now()}")
        try:
            self.stalk_error = False
            self.total_devices_detected = 0
            targets_found = []

            for sock, mac_address in self.socket_connections:
                try:
                    self.stalker_logs.append(f"[*] Checking if {mac_address} is still connected")
                    sock.getpeername()  # Check if the socket is alive
                    # self.stalker_logs.append(f"[*] {mac_address} is still connected")
                except bluetooth.BluetoothError:  # If not, remove it from the connected socket list
                    self.stalker_logs.append(f"[!] {mac_address} is not connected anymore")
                    self.socket_connections.remove((sock, mac_address))

            # Find devices in self.targets that don't have a connection in self.socket_connections
            for target_name, target_mac in self.targets:
                already_connected = False
                for sock, mac_address in self.socket_connections:
                    if mac_address == target_mac:
                        self.stalker_logs.append(f"[*] {mac_address}: {target_name} is already connected")
                        targets_found.append(target_name)
                        already_connected = True
                        continue
                if not already_connected:
                    try:
                        print("[*] Attempting to connect to " + target_name)
                        self.stalker_logs.append("[*] Attempting to connect to " + target_name)
                        sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
                        sock.connect((target_mac, 1))
                        self.socket_connections.append((sock, target_mac))
                        print("[*] Connected to " + target_name)
                        self.stalker_logs.append("[*] Connected to " + target_name)
                        targets_found.append(target_name)
                    except bluetooth.btcommon.BluetoothError as e:
                        if str(e) == "[Errno 111] Connection refused":
                            self.stalker_logs.append(f"[*] {target_name} refused connection but is present")
                            targets_found.append(target_name)
                        else:
                            print("[!] Failed to connect to " + target_name)
                            self.stalker_logs.append(f"[!] Failed to connect to {target_name} because {e}")

            self.targets_present = targets_found

            if len(targets_found) > 0:
                self.room_occupied = True
                self.failed_attempts = 0
            else:
                self.failed_attempts += 1
                if self.failed_attempts > 2:
                    self.room_occupied = False
            self.stalker_logs.append(f"[*] {len(targets_found)} devices detected")
            self.stalker_logs.append(f"[*] Stalk Completed {datetime.datetime.now()}")
            self.already_stalking = False
        except Exception as e:
            self.stalk_error = True
            self.already_stalking = False
            self.targets_present = str(e)
            self.stalker_logs.append(f"[*] Failed to stalk because {e}\nTraceback: {traceback.format_exc()}")
