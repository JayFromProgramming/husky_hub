import json
import os
import threading
import time
import traceback

api_file = "../APIKey.json"
temp_file = "Caches/Room_Coordination.json"


def celsius_to_fahrenheit(fahrenheit):
    return (fahrenheit - 32) * 5 / 9


def fahrenheit_to_celsius(celsius):
    return (celsius * 9 / 5) + 32


class NoCoordinatorConnection(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"Coordinator connection error: {self.message}"


class CoordinatorHost:

    def __init__(self):
        """
        Initialize the local thermostat reader and server
        """
        self.data = {
            "temperature": 0,
            "humidity": -1,
            "temp_set_point": 999999,
            "humid_set_point": 0,
            "last_update": time.time(),
            "last_read": 0.,
            "big_wind_state": -1,
            "room_lights_state": [
                -1,
                -1,
            ],
            "bed_lights_state": [
                -1,
                -1,
            ],
            "big_humid_state": True,
            "bed_fan_state": True,
            "errors": []
        }

        self._load_data()
        self.data['errors'] = []
        try:
            import smbus2

            self.address = 0x5C  # device I2C address
            self.bus = smbus2.SMBus(1)
        except Exception as e:
            self.data['errors'].append(f"Init error: {str(e)}")
        self._save_data()

    def read_data(self):
        """
        Start a thread to read the data from the local thermostat
        :return:
        """
        thread = threading.Thread(target=self._read_data, args=()).start()

    def _read_data(self):
        """
        Read the data from the local thermostat
        :return:
        """
        print("Reading data from local thermostat, saving to file")
        self._load_data()
        try:
            # read 5 bytes of data from the device address (0x05C) starting from an offset of zero
            data = self.bus.read_i2c_block_data(self.address, 0x00, 5)

            self.data['temperature'] = celsius_to_fahrenheit(int(f"{data[2]}.{data[3]}"))
            self.data['humidity'] = celsius_to_fahrenheit(int(f"{data[0]}.{data[1]}"))

            self.data['last_read'] = time.time()

        except Exception as e:
            self.data['errors'].append(f"{str(e)}; Traceback: {traceback.format_exc()}")
            if len(self.data['errors']) > 10:
                self.data['temperature'] = -9999
                self.data['humidity'] = -1
                self.data['errors'] = self.data['errors'][-10:]
        finally:
            self._save_data()

    def _save_data(self):
        """
        Save the thermostat data to a file to be read by remote thermostats
        :return:
        """
        self.data['last_update'] = time.time()
        with open(temp_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def _load_data(self):
        """
        Load the thermostat data from the file that was updated by remote thermostats
        :return:
        """
        if os.path.isfile(temp_file):
            with open(temp_file) as f:
                # Merge the data from the file with the local data
                self.data = {**self.data, **json.load(f)}

    def set_big_wind_state(self, state):
        """
        Set the state of the big wind fan
        :param state: The state of the big wind fan
        :return:
        """
        self._load_data()
        self.data['big_wind_state'] = state
        self._save_data()

    def set_big_humid_state(self, state):
        """
        Set the state of the big humid fan
        :param state: The state of the big humid fan
        :return:
        """
        self._load_data()
        self.data['big_humid_state'] = state
        self._save_data()

    def set_bed_fan_state(self, state):
        """
        Set the state of the bed fan
        :param state: The state of the bed fan
        :return:
        """
        self._load_data()
        self.data['bed_fan_state'] = state
        self._save_data()

    def set_room_lights_state(self, brightness=None, color=None):
        """
        Set the state of the room lights
        :param brightness: The brightness of the lights
        :param color: The color of the lights
        :return:
        """
        self._load_data()
        if brightness is not None:
            self.data['room_lights_state'][0] = brightness
        if color is not None:
            self.data['room_lights_state'][1] = color
        self._save_data()

    def set_bed_lights_state(self, brightness=None, color=None):
        """
        Set the state of the bed lights
        :param brightness: The brightness of the lights
        :param color: The color of the lights
        :return:
        """
        self._load_data()
        if brightness is not None:
            self.data['bed_lights_state'][0] = brightness
        if color is not None:
            self.data['bed_lights_state'][1] = color
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
        if update:
            self._load_data()
        return self.data['big_wind_state']

    def get_big_humid_state(self, update=False):
        """
        Get the state of the big humid fan
        :return: The state of the big humid fan
        """
        if update:
            self._load_data()
        return self.data['big_humid_state']

    def get_bed_fan_state(self, update=False):
        """
        Get the state of the bed fan
        :return: The state of the bed fan
        """
        if update:
            self._load_data()
        return self.data['bed_fan_state']

    def get_room_lights_state(self, update=False):
        """
        Get the state of the room lights
        :return: The state of the room lights
        """
        if update:
            self._load_data()
        return self.data['room_lights_state']

    def get_bed_lights_state(self, update=False):
        """
        Get the state of the bed lights
        :return: The state of the bed lights
        """
        if update:
            self._load_data()
        return self.data['bed_lights_state']

    def maintain_temperature(self):
        """
        Maintain the temperature of the room
        :return: The action that should be taken to maintain the temperature
        """
        if self.data['temperature'] < self.data['temp_set_point'] - 2 and self.get_big_wind_state() != 0:
            self.set_big_wind_state(0)
            return "big-wind-off"
        elif self.data['temperature'] <= self.data['temp_set_point'] and self.get_big_wind_state() == 3:
            self.set_big_wind_state(1)
            return "big-wind-out"
        elif self.data['temperature'] > self.data['temp_set_point'] + 2 and self.get_big_wind_state() == 0:
            self.set_big_wind_state(3)
            return "big-wind-on"

    def maintain_humidity(self):
        """
        Maintain the humidity of the room
        :return: The action that should be taken to maintain the humidity
        """
        if self.data['humidity'] > self.data['humid_set_point'] + 2 and self.get_big_humid_state() != 0:
            self.set_big_humid_state(0)
            return "big-humid-off"
        elif self.data['humidity'] < self.data['humid_set_point'] - 2 and self.get_big_humid_state() != 1:
            self.set_big_humid_state(1)
            return "big-humid-on"

    def get_temperature(self):
        """
        Get the current temperature of the room
        :return: The current temperature of the room in Celsius
        """
        return self.data['temperature']

    def get_humidity(self):
        """
        Get the current humidity of the room
        :return: The current humidity of the room in relative humidity
        """
        return self.data['humidity']

    def set_temperature(self, temperature):
        """
        Set the thermostat set point
        :param temperature: Integer value of the temperature in Celsius
        :return: None
        """
        self.data['temp_set_point'] = temperature
        self._save_data()


# --------------------------------------- Remote Thermostat --------------------------------------- #


class CoordinatorClient:

    def __init__(self):
        """
        Initialize the remote thermostat
        """
        self.last_download = 0  # The time of the last download from the thermostat in seconds
        self.last_upload = 0  # The time of the last upload to the thermostat in seconds
        if os.path.isfile(api_file):
            with open(api_file) as f:
                data = json.load(f)
                self.thermostat_server = data['rPi_address']
                self.thermostat_server_password = data['rPi_password']
                self.thermostat_server_path = data['rPi_file_path']
        self.ssh = None
        self.sftp = None
        self.data = {
            "temperature": 0,
            "humidity": -1,
            "temp_set_point": 999999,
            "humid_set_point": 0,
            "last_update": time.time(),
            "last_read": 0.,
            "big_wind_state": -1,
            "room_lights_state": [
                -1,
                -1,
            ],
            "bed_lights_state": [
                -1,
                -1,
            ],
            "big_humid_state": True,
            "bed_fan_state": True,
            "errors": ["No data"]
        }

        self.read_data()

    def _establish_connection(self):
        """
        Establish a connection to the thermostat server
        :return: None
        """
        print("Establishing connection to thermostat server")
        import paramiko
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
            self.ssh.connect(self.thermostat_server, username="pi", password=self.thermostat_server_password)
            self.sftp = self.ssh.open_sftp()
            print("Connection established")
        except paramiko.ssh_exception.SSHException as e:
            print("Connection failed")
            raise NoCoordinatorConnection(e)
        except WindowsError as e:
            print("Connection failed")
            raise NoCoordinatorConnection(e)

    def _release_connection(self):
        """
        Release the connection to the thermostat server
        :return: None
        """
        self.sftp.close()
        self.ssh.close()

    def silent_read_data(self):
        """
        Read the data from the remote thermostat without updating the local data
        :return:
        """
        with open(temp_file, "r") as f:
            self.data = json.load(f)

    def read_data(self):
        """
        Start a thread to read the data from the remote thermostat and update the local data
        :return:
        """
        threading.Thread(target=self._download_data, args=()).start()

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
            self._download_data()
        return self.data['big_wind_state']

    def get_big_humid_state(self, update=True):
        """
        Get the state of the big humid fan
        :param update: Default True, if True, update the local data
        :return: The state of the big humid fan
        """
        if update:
            self._download_data()
        return self.data['big_humid_state']

    def get_bed_fan_state(self, update=True):
        """
        Get the state of the bed fan
        :param update: Default True, if True, update the local data
        :return: The state of the bed fan
        """
        if update:
            self._download_data()
        return self.data['bed_fan_state']

    def get_room_lights_state(self, update=True):
        """
        Get the state of the room lights
        :param update: Default True, if True, update the local data
        :return: The state of the room lights
        """
        if update:
            self._download_data()
        return self.data['room_lights_state']

    def get_bed_lights_state(self, update=True):
        """
        Get the state of the bed lights
        :param update: Default True, if True, update the local data
        :return: The state of the bed lights
        """
        if update:
            self._download_data()
        return self.data['bed_lights_state']

    def set_big_wind_state(self, state):
        """
        Set the state of the big wind fan
        :param state: The state of the big wind fan
        :return: None
        """
        # self.silent_read_data()
        self.data['big_wind_state'] = state
        self._save_data()

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
        self._save_data()

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
        self._save_data()

    def set_big_humid_state(self, state):
        """
        Set the state of the big humid fan
        :param state: The state of the big humid fan
        :return: None
        """
        self.silent_read_data()
        self.data['big_humid_state'] = state
        self._save_data()

    def set_bed_fan_state(self, state):
        """
        Set the state of the bed fan
        :param state: The state of the bed fan
        :return: None
        """
        self.silent_read_data()
        self.data['bed_fan_state'] = state
        self._save_data()

    def get_temperature(self):
        """
        Get the current temperature of the room
        :return: The current temperature of the room in Celsius
        """
        return self.data['temperature']

    def get_humidity(self):
        """
        Get the current humidity of the room
        :return: The current humidity of the room in relative humidity
        """
        return self.data['humidity']

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
        with open(temp_file, "w") as f:
            json.dump(self.data, f, indent=2)
        self._upload_data()

    def _upload_data(self):
        """
        Upload the data to the local thermostat
        :return: False if the upload is rate limited, None otherwise
        """
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
            data = json.load(f)
            self.data.update(data)

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
