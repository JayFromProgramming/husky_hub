import json
import os
import threading
import time
# import watchdog

api_file = "../APIKey.json"
temp_file = "Caches/Temperature.json"


class LocalThermostat:

    def __init__(self):
        self.data = {
            "temperature": 0,
            "humidity": 0,
            "set point": 99,
            "last_update": time.time(),
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
        thread = threading.Thread(target=self._read_data, args=()).start()

    def _read_data(self):
        print("Reading data from local thermostat, saving to file")
        try:
            # read 5 bytes of data from the device address (0x05C) starting from an offset of zero
            data = self.bus.read_i2c_block_data(self.address, 0x00, 5)

            self.data['temperature'] = int(f"{data[2]}.{data[3]}")
            self.data['humidity'] = int(f"{data[0]}.{data[1]}")

        except Exception as e:
            self.data['errors'].append(str(e))
        finally:
            self._save_data()

    def _save_data(self):
        with open(temp_file, "w") as f:
            json.dump(self.data, f, indent=2)

    def _load_data(self):
        if os.path.isfile(temp_file):
            with open(temp_file) as f:
                self.data = json.load(f)


class RemoteThermostat:

    def __init__(self):
        if os.path.isfile(api_file):
            with open(api_file) as f:
                data = json.load(f)
                self.thermostat_server = data['rPi_address']
                self.thermostat_server_password = data['rPi_password']
                self.thermostat_server_path = data['rPi_file_path']

        self.data = {
            "temperature": 0,
            "humidity": 0,
            "set point": 99,
            "errors": ["No data"]
        }

    def read_data(self):
        thread = threading.Thread(target=self._read_data, args=()).start()

    def _read_data(self):
        print("Reading data from remote thermostat server")
        import paramiko

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        ssh.connect(self.thermostat_server, username="pi", password=self.thermostat_server_password)
        sftp = ssh.open_sftp()
        sftp.get(f"{self.thermostat_server_path}/Caches/Temperature.json", temp_file)
        sftp.close()
        ssh.close()


class Thermostat:

    def __init__(self, local):
        if local:
            print("Init Thermostat Host")
            self.thermostat = LocalThermostat()
        else:
            print("Init Remote Thermostat")
            self.thermostat = RemoteThermostat()
