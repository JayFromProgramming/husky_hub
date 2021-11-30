import json
import os
import threading
import time

import socket

api_file = "../APIKey.json"
temp_file = "Caches/Room_Coordination.json"


def celsius_to_fahrenheit(celsius):
    return (float(celsius) * (9 / 5)) + 32


def fahrenheit_to_celsius(fahrenheit):
    return (float(fahrenheit) - 32) * (5 / 9)


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


# noinspection PyPackages,PyUnresolvedReferences
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

        def download_state(self, selected_state=None):
            # print("Downloading state from coordinator webserver")
            if self.download_in_progress:
                return self.data
            self.download_in_progress = True
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((self.address, self.port))
                    if selected_state is not None:
                        request = json.dumps({"client": self.client_name, "auth": self.auth, "type": "download_state", "state": selected_state})
                    else:
                        request = json.dumps({"client": self.client_name, "auth": self.auth, "type": "download_state"})
                    s.sendall(request.encode())
                    data_buff = b''
                    while True:
                        data = s.recv(1024)
                        if not data:
                            break
                        data_buff += data
                    data = json.loads(data_buff.decode())
                    # print(f"Downloaded state consists as follows {json.dumps(data, indent=2)}")
            except Exception as e:
                print(f"Error downloading state from coordinator webserver: {e}")
                self.download_in_progress = None
                self.coordinator_available = False
                self.data['temperature'] = -9999
                self.data['humidity'] = -1
                return self.data
            self.download_in_progress = None
            self.coordinator_available = True
            for key in data.keys():
                self.data[key] = data[key]
            return self.data

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

    def get_object_state(self, object_name, update=True, dameon=False):
        """
        Get the state of an object from the coordinator
        :param object_name: The name of the object
        :param update: If True, update the data from the coordinator
        :param dameon: If True, updating the data from the coordinator will be done in a daemon thread
        :return: The state of the object
        """
        if update:
            if dameon:
                self.read_data()
            else:
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
