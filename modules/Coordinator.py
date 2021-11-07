import json
import os
import threading
import time
import traceback

import socket

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


class CoordinatorHost:
    class WebServerHost:

        def __init__(self, host, port, auth, data: dict):
            self.host = host
            self.port = port
            self.data = data
            self.auth = auth
            self.run_server = True
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
                    print(f"Client {request['client']} has requested room state data")
                    conn.sendall(json.dumps(self.data).encode())
                    print(f"Client {request['client']} has been sent room state data")

                elif request['type'] == "upload_state":
                    print(f"Client {request['client']} is uploading new state data")
                    conn.sendall(b'ready')  # Let the client know that we are ready to receive data
                    data_buff = b''
                    while True:
                        data = conn.recv(1024)
                        print(data)
                        if not data:
                            break
                        data_buff += data
                    data: dict = json.loads(data_buff.decode())
                    # Update values that are matching in the updated data
                    for key in data.keys():
                        self.data[key] = data[key]
                    print(self.data)
                    print(f"Client {request['client']} has uploaded new room state data")
                    # conn.sendall(b'ack')  # Acknowledge the new state data was received and updated

                else:
                    print(f"Client {request['client']} has requested unknown action {request['type']}")
                    conn.sendall(b'404')  # Acknowledge the request was received but not understood
            print(f"Connection with client {request['client']} (action: {request['type']}) has been closed")

    def __init__(self):
        """
        Initialize the local thermostat reader and server
        """
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

        self.last_download = time.time()
        self.server = self.WebServerHost(self.coordinator_server, 47670, self.coordinator_server_password, self.data)
        self._load_data()
        self.data = self.server.data
        self.data['errors'] = []
        try:
            import Adafruit_DHT

            # self.address = 0x5C  # device I2C address
            # self.bus = smbus2.SMBus(1)
            self.sensor = Adafruit_DHT.DHT22

        except Exception as e:
            self.data['errors'].append(f"Init error: {str(e)}")
        self.read_data()
        self._save_data()

    def close_server(self):
        self.server.run_server = False

    def is_connected(self):
        return self.server.run_server

    def read_data(self):
        """
        Start a thread to read the data from the local thermostat
        :return:
        """
        self.last_download = time.time()
        thread = threading.Thread(target=self._read_thermostat, args=()).start()

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
            # read 5 bytes of data from the device address (0x05C) starting from an offset of zero
            # data = self.bus.read_i2c_block_data(self.address, 0x00, 5)
            #
            # self.server.data['temperature'] = celsius_to_fahrenheit(int(f"{data[2]}.{data[3]}"))
            # self.server.data['humidity'] = celsius_to_fahrenheit(int(f"{data[0]}.{data[1]}"))

            humidity, temp = Adafruit_DHT.read_retry(self.sensor, 4)
            if humidity is not None:
                self.server.data['humidity'] = humidity
                self.server.data['last_read'] = time.time()
            else:
                self.server.data['humidity'] = -1
                self.server.data['errors'].append("Failed to read humidity")
            if temp is not None:
                self.server.data['temperature'] = temp
                self.server.data['last_read'] = time.time()
            else:
                self.server.data['temperature'] = -9999
                self.server.data['errors'].append("Failed to read temperature")

        except Exception as e:
            self.data['errors'].append(f"{str(e)}; Traceback: {traceback.format_exc()}")
            if len(self.data['errors']) > 10:
                self.server.data['temperature'] = -9999
                self.server.data['humidity'] = -1
                self.server.data['errors'] = self.data['errors'][-10:]
        finally:
            self._save_data()

    def _save_data(self):
        """
        Save the thermostat data to a file to be read by remote thermostats
        :return:
        """
        self.server.data['last_update'] = time.time()
        with open(temp_file, "w") as f:
            json.dump(self.server.data, f, indent=2)

    def _load_data(self):
        """
        Load the room coordination data from a file for persistent state after a restart
        :return:
        """
        if os.path.isfile(temp_file):
            with open(temp_file) as f:
                # Merge the data from the file with the local data
                self.server.data = json.load(f)

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

    def set_object_states(self, object_name, states: dict):
        """
        Set the state of an object on the coordinator
        :param object_name: The name of the object
        :param states: The state to set
        :return:
        """
        for state in states:
            self.data[object_name][state] = states[state]
        self._save_data()

    def set_big_wind_state(self, state):
        """
        Set the state of the big wind fan
        :param state: The state of the big wind fan
        :return:
        """
        # self._load_data()
        self.server.data['big_wind_state'] = state
        self._save_data()

    def set_big_humid_state(self, state):
        """
        Set the state of the big humid fan
        :param state: The state of the big humid fan
        :return:
        """
        # self._load_data()
        self.server.data['big_humid_state'] = state
        self._save_data()

    def set_little_humid_state(self, state):
        """
        Set the state of the little humid fan
        :param state: The state of the little humid fan
        :return:
        """
        # self._load_data()
        self.server.data['little_humid_state'] = state
        self._save_data()

    def set_bed_fan_state(self, state):
        """
        Set the state of the bed fan
        :param state: The state of the bed fan
        :return:
        """
        # self._load_data()
        self.data['bed_fan_state'] = state
        self._save_data()

    def set_room_lights_state(self, brightness=None, color=None):
        """
        Set the state of the room lights
        :param brightness: The brightness of the lights
        :param color: The color of the lights
        :return:
        """
        # self._load_data()
        if brightness is not None:
            self.server.data['room_lights_state'][0] = brightness
        if color is not None:
            self.server.data['room_lights_state'][1] = color
        self._save_data()

    def set_bed_lights_state(self, brightness=None, color=None):
        """
        Set the state of the bed lights
        :param brightness: The brightness of the lights
        :param color: The color of the lights
        :return:
        """
        # self._load_data()
        if brightness is not None:
            self.server.data['bed_lights_state'][0] = brightness
        if color is not None:
            self.server.data['bed_lights_state'][1] = color
        self._save_data()

    def get_big_wind_state(self, update=False):
        """
        Get the state of the big wind fan
        -1: Error unknown state
        0 = All fans off
        1 = Exhaust fan only
        2 = Intake fan only
        3 = Both fans
        :return: The state of the big wind fan
        """
        # if update:
        #     self._load_data()
        return self.server.data['big_wind_state']

    def get_big_humid_state(self, update=False):
        """
        Get the state of the big humid fan
        :return: The state of the big humid fan
        """
        # if update:
        #     self._load_data()
        return self.server.data['big_humid_state']

    def get_little_humid_state(self, update=False):
        """
        Get the state of the little humid fan
        :return: The state of the little humid fan
        """
        # if update:
        #     self._load_data()
        if "little_humid_state" not in self.server.data:
            return None
        return self.server.data['little_humid_state']

    def get_bed_fan_state(self, update=False):
        """
        Get the state of the bed fan
        :return: The state of the bed fan
        """
        # if update:
        #     self._load_data()
        return self.server.data['bed_fan_state']

    def get_room_lights_state(self, update=False):
        """
        Get the state of the room lights
        :return: The state of the room lights
        """
        # if update:
        #     self._load_data()
        return self.server.data['room_lights_state']

    def get_bed_lights_state(self, update=False):
        """
        Get the state of the bed lights
        :return: The state of the bed lights
        """
        # if update:
        #     self._load_data()
        return self.server.data['bed_lights_state']

    def maintain_temperature(self):
        """
        Maintain the temperature of the room
        :return: The action that should be taken to maintain the temperature
        """
        if self.server.data['temp_set_point'] == 999999 or self.server.data['temperature'] == -9999:
            return
        if self.get_temperature() < self.server.data['temp_set_point'] - 2 and self.get_big_wind_state() != 0:
            self.set_big_wind_state(0)
            return "big-wind-off"
        elif self.get_temperature() <= self.server.data['temp_set_point'] and self.get_big_wind_state() == 3:
            self.set_big_wind_state(2)
            return "big-wind-out"
        elif self.get_temperature() > self.server.data['temp_set_point'] + 2 and self.get_big_wind_state() == 0:
            self.set_big_wind_state(3)
            return "big-wind-on"

    def maintain_humidity(self):
        """
        Maintain the humidity of the room
        :return: The action that should be taken to maintain the humidity
        """
        if self.server.data['humid_set_point'] == 0 or self.server.data['humidity'] == -1:
            return
        if self.server.data['humidity'] > self.server.data['humid_set_point'] + 2 and self.get_object_state("big_humid_state"):
            self.set_object_state("big_humid_state", False)
            self.set_object_state("little_humid_state", False)
            return "humid-off"
        elif self.server.data['humidity'] >= self.server.data['humid_set_point'] \
                and self.get_object_state("big_humid_state") and self.get_object_state("little_humid_state"):
            self.set_big_humid_state(True)
            self.set_object_state("little_humid_state", False)
            return "humid-half"
        elif self.server.data['humidity'] < self.server.data['humid_set_point'] - 2\
                and not self.get_object_state("big_humid_state") and not self.get_object_state("little_humid_state"):
            self.set_object_state("big_humid_state", True)
            self.set_object_state("little_humid_state", True)
            return "humid-full"

    def get_temperature(self):
        """
        Get the current temperature of the room
        :return: The current temperature of the room in Celsius
        """
        return celsius_to_fahrenheit(self.server.data['temperature'])

    def get_humidity(self):
        """
        Get the current humidity of the room
        :return: The current humidity of the room in relative humidity
        """
        return self.server.data['humidity']

    def set_temperature(self, temperature):
        """
        Set the thermostat set point
        :param temperature: Integer value of the temperature in Celsius
        :return: None
        """
        self.server.data['temp_set_point'] = temperature
        self._save_data()

    def set_humidity(self, humidity):
        """
        Set the humidity set point
        :param humidity: Integer value of the humidity in relative humidity
        :return: None
        """
        self.server.data['humid_set_point'] = humidity
        self._save_data()

    def get_temperature_setpoint(self):
        """
        Get the current temperature set point of the room
        :return: The current temperature set point of the room in Celsius
        """
        return self.server.data['temp_set_point']

    def get_humidity_setpoint(self):
        """
        Get the current humidity set point of the room
        :return: The current humidity set point of the room in relative humidity
        """
        return self.server.data['humid_set_point']


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
            print("Downloading state from coordinator webserver")
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
                self.download_in_progress = False
                self.coordinator_available = False
                self.data['temperature'] = -9999
                self.data['humidity'] = -1
                return self.data
            self.download_in_progress = False
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
                    s.sendall(json.dumps(state_data).encode())

            except Exception as e:
                print(f"Error uploading state change to coordinator webserver: {e}")
                self.upload_in_progress = False
                raise e
            finally:
                self.upload_in_progress = False

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
                self.webclient = self.WebserverClient(self.coordinator_server, 47670, "test", self.coordinator_server_auth,
                                                      self.coordinator_server_password, self.tablet, self.data)
        else:
            print("No API file found, configuring dummy server")
            self.webclient = self.WebserverClient("", 47670, "test", None, None, None, self.data)
            self.webclient.coordinator_available = False

        # self.data = self.webclient.download_state()

    # def _establish_connection(self):
    #     """
    #     Establish a connection to the thermostat server
    #     :return: None
    #     """
    #     print("Establishing connection to thermostat server")
    #     import paramiko
    #     try:
    #         self.ssh = paramiko.SSHClient()
    #         self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    #         self.ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
    #         self.ssh.connect(self.thermostat_server, username="pi", password=self.thermostat_server_password)
    #         self.sftp = self.ssh.open_sftp()
    #         print("Connection established")
    #     except paramiko.ssh_exception.SSHException as e:
    #         print("Connection failed")
    #         raise NoCoordinatorConnection(e)
    #     except WindowsError as e:
    #         print("Connection failed")
    #         raise NoCoordinatorConnection(e)

    # def _release_connection(self):
    #     """
    #     Release the connection to the thermostat server
    #     :return: None
    #     """
    #     self.sftp.close()
    #     self.ssh.close()

    def close_server(self):
        """
        Close the webserver connection
        :return: None
        """
        self.webclient.coordinator_available = False

    def silent_read_data(self):
        """
        Read the data from the coordinator file without updating the file data
        :return:
        """
        self.read_data()
        # self.webclient.download_state()
        # with open(temp_file, "r") as f:
        #     data = json.load(f)
        #     if len(data) == 0:
        #         raise NoCoordinatorData("No data from coordinator")
        #     self.data = json.load(f)

    def _read_data(self):
        """
        Read the data from the coordinator server
        :return: None
        """
        self.data = self.webclient.download_state()
        # self.data['last_read'] = time.time()

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
        return self.webclient.coordinator_available

    def attempt_restart(self, target):
        """
        Attempt to restart the coordinator server
        :return:
        """
        if target == "coordinator" or target == "all":
            self.webclient.command_coordinator_restart()
        elif target == "tablet" or target == "all":
            self.webclient.command_tablet_restart()

    def attempt_reboot(self, target):
        """
        Attempt to reboot the coordinator server
        :return:
        """
        if target == "coordinator" or target == "all":
            self.webclient.command_coordinator_reboot()
        elif target == "tablet" or target == "all":
            self.webclient.command_tablet_reboot()

    def get_object_state(self, object_name, update=True):
        """
        Get the state of an object from the coordinator
        :param object_name: The name of the object
        :param update: If True, update the data from the coordinator
        :return: The state of the object
        """
        if update:
            self.read_data()
        if object_name in self.data:
            return self.data[object_name]
        else:
            return None

    def set_object_state(self, object_name, state):
        """
        Set the state of an object on the coordinator
        :param object_name: The name of the object
        :param state: The state to set
        :return:
        """
        self.data[object_name] = state
        self.webclient.upload_state({object_name: self.data[object_name]})

    def set_object_states(self, object_name, states: dict):
        """
        Set the state of an object on the coordinator
        :param object_name: The name of the object
        :param states: The state to set
        :return:
        """
        for state in states:
            self.data[object_name][state] = states[state]
        self.webclient.upload_state(self.data[object_name])

    def get_big_wind_state(self, update=True):
        """
        Get the state of the big wind fan
        -1 = Error unknown state
        0 = All fans off
        1 = Exhaust fan only
        2 = Intake fan only
        3 = Both fans
        :param update: Default True. If True, update the data from the thermostat
        :return: The state of the big wind fan
        """
        if update:
            self.webclient.download_state()
        return self.data['big_wind_state']

    def get_big_humid_state(self, update=True):
        """
        Get the state of the big humid fan
        :param update: Default True, if True, update the local data
        :return: The state of the big humid fan
        """
        if update:
            self.webclient.download_state()
        return self.data['big_humid_state']

    def get_little_humid_state(self, update=True):
        """
        Get the state of the little humid fan
        :param update: Default True, if True, update the local data
        :return: The state of the little humid fan
        """
        if update:
            self.webclient.download_state()
        if "little_humid_state" not in self.data:
            return None
        return self.data['little_humid_state']

    def get_bed_fan_state(self, update=True):
        """
        Get the state of the bed fan
        :param update: Default True, if True, update the local data
        :return: The state of the bed fan
        """
        if update:
            self.webclient.download_state()
        return self.data['bed_fan_state']

    def get_room_lights_state(self, update=True):
        """
        Get the state of the room lights
        :param update: Default True, if True, update the local data
        :return: The state of the room lights
        """
        if update:
            self.webclient.download_state()
        return self.data['room_lights_state']

    def get_bed_lights_state(self, update=True):
        """
        Get the state of the bed lights
        :param update: Default True, if True, update the local data
        :return: The state of the bed lights
        """
        if update:
            self.webclient.download_state()
        return self.data['bed_lights_state']

    def set_big_wind_state(self, state):
        """
        Set the state of the big wind fan
        :param state: The state of the big wind fan
        :return: None
        """
        # self.silent_read_data()
        self.data['big_wind_state'] = state
        self.webclient.upload_state({"big_wind_state": self.data['big_wind_state']})

    def set_room_lights_state(self, brightness=None, color=None):
        """
        Set the state of the room lights
        :param brightness: The brightness of the lights
            -1 = Unknown brightness
            0 = Off
            1 = Low
            2 = Medium
            3 = High
        :param color: The color of the lights
            -1 = Unknown color
            0 = Off
            1 = Red
            2 = Green
            3 = Blue
        :return: None
        """
        # self.read_data()
        if brightness is not None:
            self.data['room_lights_state'][0] = brightness
        if color is not None:
            self.data['room_lights_state'][1] = color
        self.webclient.upload_state({"room_lights_state": self.data['room_lights_state']})

    def set_bed_lights_state(self, brightness=None, color=None):
        """
        Set the state of the bed lights
        :param brightness: The brightness of the lights
            - -1 = Unknown brightness
            - 0 = Off
            - 1 = Low
            - 2 = Medium
            - 3 = High
        :param color: The color of the lights
            - -1 = Unknown color
            - 0 = Off
            - 1 = Red
            - 2 = Green
            - 3 = Blue
        :return: None
        """
        # self.read_data()
        if brightness is not None:
            self.data['bed_lights_state'][0] = brightness
        if color is not None:
            self.data['bed_lights_state'][1] = color
        self.webclient.upload_state({"bed_lights_state": self.data['bed_lights_state']})

    def set_big_humid_state(self, state):
        """
        Set the state of the big humid fan
        :param state: The state of the big humid fan
        :return: None
        """
        self.data['big_humid_state'] = state
        self.webclient.upload_state({'big_humid_state': state})

    def set_little_humid_state(self, state):
        """
        Set the state of the little humid fan
        :param state: The state of the little humid fan
        :return: None
        """
        self.data['little_humid_state'] = state
        self.webclient.upload_state({'little_humid_state': state})

    def set_bed_fan_state(self, state):
        """
        Set the state of the bed fan
        :param state: The state of the bed fan
        :return: None
        """
        self.data['bed_fan_state'] = state
        self.webclient.upload_state({'bed_fan_state': state})

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

    def get_temperature_setpoint(self):
        """
        Get the current temperature setpoint of the room
        :return: The current temperature setpoint of the room in Celsius
        """
        return self.data['temp_set_point']

    def get_humidity_setpoint(self):
        """
        Get the current humidity setpoint of the room
        :return: The current humidity setpoint of the room in relative humidity
        """
        return self.data['humid_set_point']

    def set_temperature(self, temperature):
        """
        Set the thermostat set point
        :param temperature: Integer value of the temperature in Celsius
        :return:
        """
        self.silent_read_data()
        self.data['temp_set_point'] = temperature
        self._save_data()

    def set_humidity(self, humidity):
        """
        Set the humidity set point
        :param humidity: Integer value of the humidity in relative humidity
        :return: None
        """
        self.silent_read_data()
        self.data['humid_set_point'] = humidity
        self._save_data()

    def _save_data(self):
        """
        Save the data to the local file
        :return: None
        """
        # self._download_data()
        # with open(temp_file, "w") as f:
        #     json.dump(self.data, f, indent=2)
        self._upload_data()

    def _upload_data(self):
        """
        Upload the data to the local thermostat
        :return: False if the upload is rate limited, None otherwise
        """

        self.webclient.upload_state(self.data)

        return
        if self.last_upload + 1 > time.time():
            return False  # Don't upload too often so that the thermostat host doesn't get overloaded

        if self.ssh is None or self.sftp is None:
            print("Connection to coordinator never established, attempting to establish connection")
            self._establish_connection()
        # Check if the ssh connection is still alive
        elif not self.ssh.get_transport().is_active():
            self._release_connection()
            self._establish_connection()

        print("Uploading data to coordinator")

        self.sftp.put(temp_file, f"{self.thermostat_server_path}/Caches/Room_Coordination.json")

        self.last_upload = time.time()

    def _download_data(self):
        """
        Download the data from the remote thermostat
        :return: False if the download is rate limited, None otherwise
        """

        self.read_data()

        return
        if self.last_download + 1 > time.time():
            return False  # Don't download too often so that the thermostat host doesn't get overloaded

        # Check if the ssh connection is still alive
        if self.ssh is None or self.sftp is None:
            print("Connection to coordinator never established, attempting to establish connection")
            self._establish_connection()

        elif not self.ssh.get_transport().is_active():
            print("Connection lost, reconnecting")
            self._release_connection()
            self._establish_connection()

        print("Downloading data from coordinator")

        self.sftp.get(f"{self.thermostat_server_path}/Caches/Room_Coordination.json", temp_file)

        with open(temp_file, "r") as f:
            self.data = json.load(f)

        self.last_download = time.time()


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
