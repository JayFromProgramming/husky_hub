import json
import os
import threading
import time
import traceback

api_file = "../APIKey.json"
temp_file = "Caches/Temperature.json"


def celsius_to_fahrenheit(fahrenheit):
    return (fahrenheit - 32) * 5 / 9


def fahrenheit_to_celsius(celsius):
    return (celsius * 9 / 5) + 32


class LocalThermostat:

    def __init__(self):
        """
        Initialize the local thermostat reader and server
        """
        self.data = {
            "temperature": 0,
            "humidity": 0,
            "temp_set_point": 99,
            "humid_set_point": 0,
            "last_update": time.time(),
            "last_read": 0.,
            "errors": []
        }

        self._load_data()
        self.current_fan_state = 0
        self.current_humid_state = 0
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
                self.data['temperature'] = 0
                self.data['humidity'] = 100
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
                self.data = json.load(f)

    def maintain_temperature(self):
        """
        Maintain the temperature of the room
        :return:
        """
        if self.data['temperature'] < self.data['temp_set_point'] - 2 and self.current_fan_state != 0:
            self.current_fan_state = 0
            return "big-wind-off"
        elif self.data['temperature'] <= self.data['temp_set_point'] and self.current_fan_state == 2:
            self.current_fan_state = 1
            return "big-wind-out"
        elif self.data['temperature'] > self.data['temp_set_point'] + 2 and self.current_fan_state == 0:
            self.current_fan_state = 2
            return "big-wind-on"

    def maintain_humidity(self):
        """
        Maintain the humidity of the room
        :return:
        """
        if self.data['humid_set_point'] - 2 < self.data['humidity']:
            return "big-humid-off"
        elif self.data['humid_set_point'] + 2 > self.data['humidity']:
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


class RemoteThermostat:

    def __init__(self):
        """
        Initialize the remote thermostat
        """
        if os.path.isfile(api_file):
            with open(api_file) as f:
                data = json.load(f)
                self.thermostat_server = data['rPi_address']
                self.thermostat_server_password = data['rPi_password']
                self.thermostat_server_path = data['rPi_file_path']

        self.data = {
            "last_update": 0,
            "last_read": 0,
            "temperature": 0,
            "humidity": 0,
            "temp_set_point": 99,
            "humid_set_point": 0,
            "errors": ["No data"]
        }

        self.read_data()

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
        :return:
        """
        self.silent_read_data()
        self.data['humid_set_point'] = humidity
        self._save_data()

    def _save_data(self):
        """
        Save the data to the local file
        :return:
        """
        with open(temp_file, "w") as f:
            json.dump(self.data, f, indent=2)
        self._upload_data()

    def _upload_data(self):
        """
        Upload the data to the local thermostat
        :return:
        """
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        ssh.connect(self.thermostat_server, username="pi", password=self.thermostat_server_password)
        sftp = ssh.open_sftp()
        sftp.put(temp_file, f"{self.thermostat_server_path}/Caches/Temperature.json")
        sftp.close()
        ssh.close()

    def _download_data(self):
        """
        Download the data from the remote thermostat
        :return:
        """
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        ssh.connect(self.thermostat_server, username="pi", password=self.thermostat_server_password)
        sftp = ssh.open_sftp()
        sftp.get(f"{self.thermostat_server_path}/Caches/Temperature.json", temp_file)
        sftp.close()
        ssh.close()

        with open(temp_file, "r") as f:
            self.data = json.load(f)


class Thermostat:

    def __init__(self, local):
        """
        Initialize the type of thermostat depending on if it is local or remote
        :param local: If the thermostat is local or remote
        """
        if local:
            print("Init Thermostat Host")
            self.thermostat = LocalThermostat()
        else:
            print("Init Remote Thermostat")
            self.thermostat = RemoteThermostat()
