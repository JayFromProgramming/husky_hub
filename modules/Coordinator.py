import json
import os
import threading
import time
import traceback

import socket
import typing

api_file = "../APIKey.json"
temp_file = "Caches/Room_Coordination.json"


def celsius_to_fahrenheit(celsius):
    return (celsius * (9 / 5)) + 32


def fahrenheit_to_celsius(fahrenheit):
    return (fahrenheit - 32) * (5 / 9)


class NoCoordinatorConnection(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"Coordinator connection error: {self.message}"


class NoCoordinatorData(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"Coordinator data error: {self.message}"


class UnknownObjectError(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"Unknown object error: {self.message}"


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


class CoordinatorHost:
    class WebServerHost:

        def __init__(self, host, port, auth, data: dict):
            self.host = host
            self.port = port
            self.data = data
            self.auth = auth
            self.download_in_progress = False
            self.upload_in_progress = False
            self.coordinator_available = True
            self.approved_actions = {}
            if os.path.isfile(os.path.join("Configs/approved_actions.json")):
                with open(os.path.join("Configs/approved_actions.json"), "r") as f:
                    self.approved_actions = json.load(f)
            self.run_server = True
            ip = get_ip()
            if ip != self.host:
                print("Coordinator IP not valid")
                self.coordinator_available = False
            else:
                self.thread = threading.Thread(target=self.run).start()

        def run(self):
            print(f"Starting Coordinator Websocket on {self.host}:{self.port}")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.host, self.port))
                print(f"Coordinator Websocket on {self.host}:{self.port} started")
                while self.run_server:
                    s.listen()
                    conn, addr = s.accept()
                    threading.Thread(target=self.connect, args=(conn, addr)).start()

        def connect(self, conn, addr):
            with conn:
                print('Connected by', addr)
                raw_request = conn.recv(1024)
                print(f"Request: {raw_request}")
                request = json.loads(raw_request.decode())
                if request["auth"] == self.auth:
                    print(f"Client {request['client']} has connected and been authenticated")
                else:
                    print(f"Client {request['client']} has connected but has not been authenticated")
                    conn.sendall(b'Forbidden: 403')
                    return

                if request['type'] == "download_state":
                    self.upload_in_progress = True
                    conn.sendall(json.dumps(self.data).encode())
                    self.upload_in_progress = None
                elif request['type'] == "upload_state":
                    self.download_in_progress = True
                    print(f"Client {request['client']} is uploading new state data")
                    conn.sendall(b'up-ready')  # Let the client know that we are ready to receive data
                    data_buff = b''
                    try:
                        while True:
                            data = conn.recv(1024)
                            if not data:
                                break
                            data_buff += data
                        data: dict = json.loads(data_buff.decode())
                        # Update values that are matching in the updated data
                        for key in data.keys():
                            self.data[key] = data[key]
                        # print(self.data)
                        print(f"Client {request['client']} has uploaded new room state data")
                        # conn.sendall(b'ack')  # Acknowledge the new state data was received and updated
                    except Exception as e:
                        print(f"Client {request['client']} has failed to upload proper room state data")
                        print(e)
                        # conn.sendall(b'503: ' + bytes(str(e)))  # Let the client know that the new state data was received but not understood
                    finally:
                        self.download_in_progress = None
                elif request['type'] == "preform_action":
                    self.download_in_progress = True
                    print(f"Client {request['client']} is requesting an action to be preformed")
                    conn.sendall(b'command-ready')
                    data_buff = b''
                    while True:
                        data = conn.recv(1024)
                        if not data:
                            break
                        data_buff += data
                    data: dict = json.loads(data_buff.decode())
                    action = self.approved_actions(data['action'])
                    if data['auth'] == action['auth']:
                        print(f"Client {request['client']} has requested action {action['name']} be preformed")
                        if action['action_type'] == "internal_code_execution":
                            code = ""
                            for line in action['code']:
                                code += line + "\n"
                            exec(code)
                else:
                    print(f"Client {request['client']} has requested unknown action {request['type']}")
                    conn.sendall(b'404')  # Acknowledge the request was received but not understood

            print(f"Connection with client {request['client']} (action: {request['type']}) has been closed")

    def __init__(self):
        """
        Initialize the local thermostat reader and server
        """
        from Utils import occupancyDetector
        if os.path.isfile("Configs/states_template.json"):
            with open("Configs/states_template.json") as f:
                self.data = json.load(f)
        else:
            self.data = {}
        if os.path.isfile(api_file):
            with open(api_file) as f:
                data = json.load(f)
                self.coordinator_server = data['rPi_address']
                self.coordinator_server_password = data['rPi_password']
                self.thermostat_server_path = data['rPi_file_path']
        self.occupancyDetector = None
        if os.path.isfile(os.path.join("Configs/occupants.json")):
            with open(os.path.join("Configs/occupants.json"), "r") as f:
                self.occupancy_detector = occupancyDetector.OccupancyDetector(json.load(f), 24)

        self.last_download = time.time()
        self.net_client = self.WebServerHost(self.coordinator_server, 47670, self.coordinator_server_password, self.data)
        self._load_data()
        self.data = self.net_client.data
        self.data['errors'] = []
        try:
            import Adafruit_DHT
            self.sensor = Adafruit_DHT.DHT22
        except Exception as e:
            self.data['errors'].append(f"Init error: {str(e)}")
        self.read_data()
        self._save_data()

    def close_server(self):
        self.net_client.run_server = False

    def is_connected(self):
        return self.net_client.run_server

    def is_occupied(self):
        if self.occupancy_detector.is_occupied():
            self.set_object_states("room_occupancy_info", room_occupied=True, last_motion=self.occupancy_detector.last_motion_time,
                                   occupants=self.occupancy_detector.which_targets_present())
            return True
        else:
            self.set_object_states("room_occupancy_info", room_occupied=False, last_motion=self.occupancy_detector.last_motion_time,
                                   occupants=self.occupancy_detector.which_targets_present())
            return False

    def read_data(self):
        """
        Start a thread to read the data from the local thermostat
        :return:
        """
        self.last_download = time.time()
        thread = threading.Thread(target=self._read_thermostat, args=()).start()
        self.occupancy_detector.run_stalk()

    def read_states(self):
        """
        Read the state of the big wind fan
        :return:
        """
        self.last_download = time.time()

    def _read_thermostat(self):
        """
        Read the data from the local thermostat
        :return:
        """
        print("Reading data from local thermostat, saving to file")
        # self._load_data()
        try:
            import Adafruit_DHT

            humidity1, temp1 = Adafruit_DHT.read_retry(self.sensor, 4)
            humidity2, temp2 = Adafruit_DHT.read_retry(self.sensor, 4)

            if humidity1 is not None and humidity2 is not None:
                humidity = (humidity1 + humidity2) / 2
                if abs(humidity1 - humidity2) > 2:
                    self.net_client.data['errors'].append("Humidity difference is too large")
                    humidity = None
                if humidity > 100:
                    self.net_client.data['errors'].append("Humidity off scale high")
                elif humidity < 0:
                    self.net_client.data['errors'].append("Humidity off scale low")
                else:
                    self.net_client.data['humidity'] = humidity
                    self.net_client.data['last_read'] = time.time()
            else:
                self.net_client.data['humidity'] = None
                self.net_client.data['errors'].append("Failed to read humidity")
            if temp1 is not None and temp2 is not None:
                temp = (temp1 + temp2) / 2
                if abs(temp1 - temp2) > 2:
                    self.net_client.data['errors'].append("Temperature difference is too large")
                    temp = None
                self.net_client.data['temperature'] = temp
                self.net_client.data['last_read'] = time.time()
            else:
                self.net_client.data['temperature'] = None
                self.net_client.data['errors'].append("Failed to read temperature")

            if len(self.data['errors']) > 10:
                self.net_client.data['errors'] = self.data['errors'][-10:]

        except Exception as e:
            self.data['errors'].append(f"{str(e)}; Traceback: {traceback.format_exc()}")
            if len(self.data['errors']) > 10:
                self.net_client.data['temperature'] = -9999
                self.net_client.data['humidity'] = -1
                self.net_client.data['errors'] = self.data['errors'][-10:]
        finally:
            self._save_data()

    def _save_data(self):
        """
        Save the thermostat data to a file to be read by remote thermostats
        :return:
        """
        self.net_client.data['last_update'] = time.time()
        with open(temp_file, "w") as f:
            json.dump(self.net_client.data, f, indent=2)

    def _load_data(self):
        """
        Load the room coordination data from a file for persistent state after a restart
        :return:
        """
        if os.path.isfile(temp_file):
            with open(temp_file) as f:
                # Merge the data from the file with the local data
                self.net_client.data = json.load(f)

    def get_object_state(self, object_name, update=True):
        """
        Get the state of an object from the coordinator
        :param object_name: The name of the object
        :param update: If True, update the data from the coordinator
        :return: The state of the object
        """
        if object_name in self.data:
            return self.data[object_name]
        else:
            return None

    def set_object_state(self, object_name, object_state):
        """
        Set the state of an object on the coordinator
        :param object_name: The name of the object
        :param object_state: The state of the object
        :return:
        """
        self.data[object_name] = object_state
        self._save_data()

    def set_object_states(self, object_name, **kwargs):
        """
        Set the state of an object on the coordinator
        :param object_name: The name of the object
        :param kwargs: The state of the object via keyword arguments
        :return:
        """
        if object_name not in self.data:
            self.data[object_name] = {}
        for key, value in kwargs.items():
            self.data[object_name][key] = value
        self._save_data()

    def maintain_temperature(self):
        """
        Maintain the temperature of the room
        :return: The action that should be taken to maintain the temperature
        """
        if self.net_client.data['temp_set_point'] is None or self.net_client.data['temperature'] == -9999 \
                or not self.get_object_state("fan_auto_enable"):
            return
        if self.get_temperature() <= self.net_client.data['temp_set_point'] - 1 and self.get_object_state("big_wind_state") != 0:
            self.set_object_state("big_wind_state", 0)  # If the temperature is 1 degrees below the set point, turn off both fans
            return "big-wind-off"
        elif self.get_temperature() <= self.net_client.data['temp_set_point'] - 0.75 and self.get_object_state("big_wind_state") == 3:
            self.set_object_state("big_wind_state", 2)  # If the temperature is 0.75 degrees below the set point, turn off the intake fan
            return "big-wind-out"
        elif self.get_temperature() >= self.net_client.data['temp_set_point'] + 1.5 and self.get_object_state("big_wind_state") != 3:
            self.set_object_state("big_wind_state", 3)  # If the temperature is 1.5 degrees above the set point, turn on both fans
            return "big-wind-on"

    def _calculate_humid_state(self):
        """
        Convert the states of the humidifiers into a single int value
        :return:
        """
        if self.get_object_state("big_humid_state") and self.get_object_state("little_humid_state"):
            return 3
        elif not self.get_object_state("big_humid_state") and self.get_object_state("little_humid_state"):
            return 2
        elif self.get_object_state("big_humid_state") and not self.get_object_state("little_humid_state"):
            return 1
        else:
            return 0

    def maintain_humidity(self):
        """
        Maintain the humidity of the room
        :return: The action that should be taken to maintain the humidity
        """
        if self.net_client.data['humid_set_point'] == 0 or self.net_client.data['humidity'] == -1:
            return
        if self.net_client.data['humidity'] > self.net_client.data['humid_set_point'] + 2:
            if self._calculate_humid_state() != 0:
                self.set_object_state("big_humid_state", False)
                self.set_object_state("little_humid_state", False)
                return "humid-off"
        elif self.net_client.data['humid_set_point'] <= self.net_client.data['humidity'] <= self.net_client.data['humid_set_point'] + 2:
            if self._calculate_humid_state() != 1:
                self.set_object_state("big_humid_state", True)
                self.set_object_state("little_humid_state", False)
                return "humid-half"
        elif self.net_client.data['humidity'] < self.net_client.data['humid_set_point'] - 2:
            if self._calculate_humid_state() != 3:
                self.set_object_state("big_humid_state", True)
                self.set_object_state("little_humid_state", True)
                return "humid-full"

    def get_temperature(self):
        """
        Get the current temperature of the room
        :return: The current temperature of the room in Celsius
        """
        return celsius_to_fahrenheit(self.net_client.data['temperature']) if self.net_client.data['temperature'] != -9999 else -9999

    def get_humidity(self):
        """
        Get the current humidity of the room
        :return: The current humidity of the room in relative humidity
        """
        return self.net_client.data['humidity']

    def set_temperature(self, temperature):
        """
        Set the thermostat set point
        :param temperature: Integer value of the temperature in Celsius
        :return: None
        """
        self.net_client.data['temp_set_point'] = temperature
        self._save_data()

    def set_humidity(self, humidity):
        """
        Set the humidity set point
        :param humidity: Integer value of the humidity in relative humidity
        :return: None
        """
        self.net_client.data['humid_set_point'] = humidity
        self._save_data()

    def get_temperature_setpoint(self, update=False):
        """
        Get the current temperature set point of the room
        :return: The current temperature set point of the room in Celsius
        """
        return self.net_client.data['temp_set_point']

    def get_humidity_setpoint(self, update=False):
        """
        Get the current humidity set point of the room
        :return: The current humidity set point of the room in relative humidity
        """
        return self.net_client.data['humid_set_point']


# --------------------------------------- Remote Thermostat --------------------------------------- #


class CoordinatorClient:
    class WebserverClient:

        def __init__(self, address, port, client_name, auth, password, tablet, data: dict):
            self.address = address
            self.port = port
            self.data = data
            self.client_name = client_name
            self.auth = auth
            self.password = password
            self.tablet = tablet
            self.coordinator_available = False
            self.download_in_progress = False
            self.upload_in_progress = False

        def command_coordinator_restart(self):
            """
            Restart the coordinator
            :return: None
            """
            if self.upload_in_progress:
                raise ConnectionAbortedError("Connection in progress")
            result = os.system(f"plink pi@{self.address} -pw {self.password} -m Configs/Commands/restart_pi_commands.command")
            if result != 0:
                raise ConnectionError("Connection failed")
            self.coordinator_available = False

        def command_coordinator_reboot(self):
            """
            Reboot the coordinator
            :return: None
            """
            if self.upload_in_progress:
                raise ConnectionAbortedError("Connection in progress")
            result = os.system(f"plink pi@{self.address} -pw {self.password} -m Configs/Commands/reboot_pi_commands.command")
            if result != 0:
                raise ConnectionError("Connection failed")
            self.coordinator_available = False

        def command_tablet_reboot(self):
            """
            Reboot the tablet
            :return: None
            """
            address, password = self.tablet
            if self.upload_in_progress:
                raise ConnectionAbortedError("Connection in progress")
            result = os.system(f"plink weather@{address} -pw {password} -m Configs/Commands/reboot_tablet_commands.command")
            if result != 0:
                raise ConnectionError("Connection failed")
            self.coordinator_available = False

        def download_state(self):
            # print("Downloading state from coordinator webserver")
            if self.download_in_progress:
                return self.data
            self.download_in_progress = True
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((self.address, self.port))
                    request = json.dumps({"client": self.client_name, "auth": self.auth, "type": "download_state"})
                    s.sendall(request.encode())
                    data_buff = b''
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break
                        data_buff += data
                    data = json.loads(data_buff.decode())
                    print(f"Downloaded state consists as follows {json.dumps(data, indent=2)}")
            except Exception as e:
                print(f"Error downloading state from coordinator webserver: {e}")
                self.download_in_progress = None
                self.coordinator_available = False
                self.data['temperature'] = -9999
                self.data['humidity'] = -1
                return self.data
            self.download_in_progress = None
            self.coordinator_available = True
            self.data = data
            return data

        def upload_state(self, state_data):
            print("Uploading state change to coordinator webserver")
            if self.upload_in_progress:
                raise ConnectionAbortedError("Upload already in progress")
            if not self.coordinator_available:
                raise ConnectionError("Coordinator not available")
            self.upload_in_progress = True
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((self.address, self.port))
                    request = json.dumps({"client": self.client_name, "auth": self.auth, "type": "upload_state"})
                    s.sendall(request.encode())
                    response = s.recv(1024)
                    print(f"Response from coordinator: {response.decode()}")
                    s.sendall(json.dumps(state_data).encode())
                    # response = s.recv(1024)
                    # print(f"Uploaded state change to coordinator, response: {response.decode()}")

            except Exception as e:
                print(f"Error uploading state change to coordinator webserver: {e}")
                self.upload_in_progress = None
                raise e
            finally:
                self.upload_in_progress = None

    def __init__(self):
        """
        Initialize the remote thermostat
        """
        self.last_download = 0  # The time of the last download from the thermostat in seconds
        self.last_upload = 0  # The time of the last upload to the thermostat in seconds
        if os.path.isfile("Configs/states_template.json"):
            with open("Configs/states_template.json") as f:
                self.data = json.load(f)
        else:
            self.data = {}
        if os.path.isfile(api_file):
            with open(api_file) as f:
                data = json.load(f)
                self.coordinator_server = data['rPi_address']
                self.coordinator_server_auth = data['rPi_auth']
                self.thermostat_server_path = data['rPi_file_path']
                self.coordinator_server_password = data['rPi_password']
                tablet_ip = data['tablet_ip']
                tablet_password = data['tablet_password']
                self.tablet = tablet_ip, tablet_password
                self.net_client = self.WebserverClient(self.coordinator_server, 47670, "test", self.coordinator_server_auth,
                                                       self.coordinator_server_password, self.tablet, self.data)
        else:
            print("No API file found, configuring dummy server")
            self.net_client = self.WebserverClient("", 47670, "test", None, None, None, self.data)
            self.net_client.coordinator_available = False

        # self.data = self.webclient.download_state()

    def close_server(self):
        """
        Close the webserver connection
        :return: None
        """
        self.net_client.coordinator_available = False

    def silent_read_data(self):
        """
        Read the data from the coordinator file without updating the file data
        :return:
        """
        self.read_data()

    def _read_data(self):
        """
        Read the data from the coordinator server
        :return: None
        """
        self.data = self.net_client.download_state()

    def read_data(self):
        """
        Start a thread to read the data from the room coordinator and update the local data
        :return:
        """
        threading.Thread(target=self._read_data, args=()).start()

    def read_states(self):
        """
        Also read the states of the room coordinator, but if client is room coordinator, then ignore the thermostat
        :return:
        """
        self.read_data()
        self.last_download = time.time()

    def is_connected(self):
        """
        Check if the coordinator server is available
        :return: True if connected, False otherwise
        """
        return self.net_client.coordinator_available

    def attempt_restart(self, target):
        """
        Attempt to restart the coordinator server
        :return:
        """
        if target == "coordinator" or target == "all":
            self.net_client.command_coordinator_restart()
        elif target == "tablet" or target == "all":
            self.net_client.command_tablet_restart()

    def attempt_reboot(self, target):
        """
        Attempt to reboot the coordinator server
        :return:
        """
        if target == "coordinator" or target == "all":
            self.net_client.command_coordinator_reboot()
        elif target == "tablet" or target == "all":
            self.net_client.command_tablet_reboot()

    def get_object_state(self, object_name, update=True):
        """
        Get the state of an object from the coordinator
        :param object_name: The name of the object
        :param update: If True, update the data from the coordinator
        :return: The state of the object
        """
        if update:
            self.net_client.download_state()
        if object_name in self.data:
            return self.data[object_name]
        else:
            raise UnknownObjectError(object_name)

    def set_object_state(self, object_name, state):
        """
        Set the state of an object on the coordinator
        :param object_name: The name of the object
        :param state: The state to set
        :return:
        """
        self.data[object_name] = state
        self.net_client.upload_state({object_name: self.data[object_name]})

    def set_object_states(self, object_name, **kwargs):
        """
        Set the state of an object on the coordinator
        :param object_name: The name of the object
        :param states: The state to set
        :return:
        """
        if not isinstance(self.data[object_name], dict):
            self.data[object_name] = {}
        for key, value in kwargs.items():
            self.data[object_name][key] = value
        self.net_client.upload_state({object_name: self.data[object_name]})

    def set_big_humid_state(self, state):
        """
        Set the state of the big humid fan
        :param state: The state of the big humid fan
        :return: None
        """
        self.data['big_humid_state'] = state
        self.net_client.upload_state({'big_humid_state': state})

    def get_temperature(self):
        """
        Get the current temperature of the room
        :return: The current temperature of the room in Celsius
        """
        return celsius_to_fahrenheit(float(self.data['temperature'])) if self.data['temperature'] != -9999 else -9999

    def get_humidity(self):
        """
        Get the current humidity of the room
        :return: The current humidity of the room in relative humidity
        """
        return self.data['humidity']

    def get_temperature_setpoint(self, update=True):
        """
        Get the current temperature setpoint of the room
        :return: The current temperature setpoint of the room in Celsius
        """
        if update:
            self.net_client.download_state()
        return self.data['temp_set_point']

    def get_humidity_setpoint(self, update=True):
        """
        Get the current humidity setpoint of the room
        :return: The current humidity setpoint of the room in relative humidity
        """
        if update:
            self.net_client.download_state()
        return self.data['humid_set_point']

    def set_temperature(self, temperature):
        """
        Set the thermostat set point
        :param temperature: Integer value of the temperature in Celsius
        :return:
        """
        # self.silent_read_data()
        self.data['temp_set_point'] = temperature
        self._save_data()

    def set_humidity(self, humidity):
        """
        Set the humidity set point
        :param humidity: Integer value of the humidity in relative humidity
        :return: None
        """
        # self.silent_read_data()
        self.data['humid_set_point'] = humidity
        self._save_data()

    def _save_data(self):
        """
        Save the data to the local file
        :return: None
        """
        self._upload_data()

    def _upload_data(self):
        """
        Upload the data to the local thermostat
        :return: False if the upload is rate limited, None otherwise
        """

        self.net_client.upload_state(self.data)

    def _download_data(self):
        """
        Download the data from the remote thermostat
        :return: False if the download is rate limited, None otherwise
        """

        self.read_data()


class Coordinator:

    def __init__(self, local):
        """
        Initialize the type of thermostat depending on if it is local or remote
        :param local: If the thermostat is local or remote
        """
        if local:
            print("Init Thermostat Host")
            self.coordinator = CoordinatorHost()
        else:
            print("Init Remote Thermostat")
            self.coordinator = CoordinatorClient()
