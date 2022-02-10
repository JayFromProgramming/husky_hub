import json
import logging
import os
import threading
import time
import traceback
import datetime
import socket

import psutil

try:
    import Adafruit_DHT
    import RPi.GPIO as GPIO
except ImportError:
    pass

api_file = "../APIKey.json"
save_file = "Caches/Room_Coordination.json"
backup_file = "Caches/Room_Coordination_Backup.json"

log = logging.getLogger(__name__)


def c_f(celsius):
    return (float(celsius) * (9 / 5)) + 32


def fahrenheit_to_celsius(fahrenheit):
    return (float(fahrenheit) - 32) * (5 / 9)


def time_delta_to_str(td: int):
    days = round(td // 86400)
    hours = round(td // 3600 % 24)
    minutes = round((td // 60) % 60)
    seconds = round(td % 60)
    if days > 0:
        return '{} days {} hours {} minutes'.format(days, hours, minutes, seconds)
    elif hours > 0:
        return '{} hours {} minutes'.format(hours, minutes, seconds)
    elif minutes > 0:
        return '{}min {}sec'.format(minutes, seconds)
    else:
        return '{} seconds'.format(seconds)


class NoCoordinatorConnection(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        log.warning(f"Coordinator connection error: {self.message}")
        return f"Coordinator connection error: {self.message}"


class NoCoordinatorData(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        log.warning(f"No coordinator data error: {self.message}")
        return f"Coordinator data error: {self.message}"


class UnknownObjectError(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        log.warning(f"Unknown object error: {self.message}")
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
    log.info(f"Hosting coordinator on {IP}")
    return IP


# noinspection PyPackages,PyUnresolvedReferences
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
                log.warning(f"Coordinator IP address is {ip} but {self.host} was specified in the config file")
                self.host = ip
                self.thread = threading.Thread(target=self.run, daemon=True).start()
                # self.coordinator_available = False
            else:
                self.thread = threading.Thread(target=self.run, daemon=True).start()

        def run(self):
            log.debug(f"Starting Coordinator Websocket on {self.host}:{self.port}")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.host, self.port))
                log.debug(f"Coordinator Websocket on {self.host}:{self.port} started")
                while self.run_server:
                    s.listen()
                    conn, addr = s.accept()
                    threading.Thread(target=self.connect, args=(conn, addr)).start()

        def connect(self, conn, addr):
            with conn:
                log.debug('Connected by', addr)
                raw_request = conn.recv(1024)
                log.debug(f"Request: {raw_request}")
                request = json.loads(raw_request.decode())
                if request["auth"] == self.auth:
                    log.debug(f"Client {request['client']} has connected and been authenticated")
                else:
                    log.debug(f"Client {request['client']} has connected but has not been authenticated")
                    conn.sendall(b'Forbidden: 403')
                    return

                if request['type'] == "download_state":
                    self.upload_in_progress = True
                    if "state" in request.keys():
                        if request["state"] in self.data.keys():
                            conn.sendall(json.dumps({request["state"]: self.data[request["state"]]}).encode())
                        else:
                            conn.sendall(b'No state found')
                    else:
                        conn.sendall(json.dumps(self.data).encode())
                    self.upload_in_progress = None
                elif request['type'] == "upload_state":
                    self.download_in_progress = True
                    log.debug(f"Client {request['client']} is uploading new state data")
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
                        log.debug(f"Client {request['client']} has uploaded new room state data")
                        # conn.sendall(b'ack')  # Acknowledge the new state data was received and updated
                    except Exception as e:
                        log.warning(f"Client {request['client']} has failed to upload proper room state data")
                        log.warning(e)
                        # conn.sendall(b'503: ' + bytes(str(e)))  # Let the client know that the new state data was received but not understood
                    finally:
                        self.download_in_progress = None
                elif request['type'] == "preform_action":
                    self.download_in_progress = True
                    log.debug(f"Client {request['client']} is requesting an action to be preformed")
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
                        log.debug(f"Client {request['client']} has requested action {action['name']} be preformed")
                        if action['action_type'] == "internal_code_execution":
                            code = ""
                            for line in action['code']:
                                code += line + "\n"
                            exec(code)
                else:
                    log.warning(f"Client {request['client']} has requested unknown action {request['type']}")
                    conn.sendall(b'404')  # Acknowledge the request was received but not understood

            log.debug(f"Connection with client {request['client']} (action: {request['type']}) has been closed")

    def __init__(self, coprocessor):
        """
        Initialize the local thermostat reader and server
        """
        self.start_time = time.time()
        from . import occupancyDetector
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
        self.last_download = time.time()
        self.net_client = self.WebServerHost(self.coordinator_server, 47670, self.coordinator_server_password,
                                             self.data)
        self._load_data()
        self.coprocessor = coprocessor
        self.data = self.net_client.data
        self.data['errors'] = []
        self.channel = 11
        log.info("Setting up GPIO to enable power to DHT22 sensor")
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.channel, GPIO.OUT)
        GPIO.output(self.channel, GPIO.HIGH)
        self.sensor_powered = True
        self.sensor_restart_time = time.time()
        if os.path.isfile(os.path.join("Configs/occupants.json")):
            with open(os.path.join("Configs/occupants.json"), "r") as f:
                self.occupancy_detector = occupancyDetector.OccupancyDetector(json.load(f), 24, self)
        try:
            import Adafruit_DHT
            self.sensor = Adafruit_DHT.DHT22
        except Exception as e:
            self.data['errors'].append(f"Init error: {str(e)}")
        self.last_save = 0
        self.read_data()
        self._save_data()

    def close_server(self):
        self.net_client.run_server = False

    def is_connected(self):
        return self.net_client.run_server

    def is_occupied(self):

        if not self.occupancy_detector.is_ready():
            return False

        def decode(vals, sensor):
            return vals[sensor].decode('utf-8')

        def decode_num(vals, sensor):
            try:
                return float(vals[sensor].decode('utf-8'))
            except ValueError:
                return -9999

        data = self.coprocessor.get_data(target_arduino=0)
        data_2 = self.coprocessor.get_data(target_arduino=1)
        state = self.coprocessor.get_state(target_arduino=0)
        state_2 = self.coprocessor.get_state(target_arduino=1)

        self.set_object_states("room_sensor_data_displayable", CSERV_uptime=time_delta_to_str(round(time.time() - self.start_time)),
                               Pi_uptime=time_delta_to_str(int(time.time() - psutil.boot_time())), room_air_sensor_power=self.sensor_powered)

        if self.get_object_state("tablet_battery_state") is not None \
                and self.get_object_state("tablet_last_update") + 120 > time.time():
            self.set_object_states("room_sensor_data_displayable",
                                   tablet_battery=self.get_object_state("tablet_battery_state"))
        else:
            self.set_object_states("room_sensor_data_displayable",
                                   tablet_battery=f"Offline- {time_delta_to_str(time.time() - self.get_object_state('tablet_last_update'))} ago")

        if self.coprocessor.connected[0] and len(data) > 1:
            self.set_object_states("room_sensor_data_displayable",
                                   # room_air_sensor=f"T:{str(room_temp).zfill(5)}°F | H:{str(room_humidity).zfill(4)}%",
                                   carbon_monoxide_sensor=f"{data[1].decode('utf-8')} ppm {'- High!' if float(decode_num(data, 2)) > 25 else ''}",
                                   gas_smoke_sensor=f"{decode(data, 2)} ppm {'- High!' if float(decode_num(data, 2)) > 25 else ''}",
                                   combustible_gas_sensor=f"{decode(data, 3)} ppm {'- High!' if float(decode_num(data, 3)) > 5 else ''}",
                                   motion_sensor=True if data[4].decode('utf-8') == "1" else False,
                                   light_sensor=f"{data[0].decode('utf-8')}%",
                                   lcd_backlight="On" if state[4] != 0 else "Off")
        else:
            # self.set_object_state("temperature", -9999)
            # self.set_object_state("humidity", -1)
            self.set_object_states("room_sensor_data_displayable", room_air_sensor=None, carbon_monoxide_sensor=None,
                                   gas_smoke_sensor=None,
                                   buzzer_alarm=None, light_sensor=None, combustible_gas_sensor=None,
                                   motion_sensor=None, lcd_backlight=None)

        if self.coprocessor.connected[1] and len(data_2) > 1:
            radiator_temp = c_f(data_2[0].decode('utf-8')) if data_2[0].decode('utf-8') != "Error" else None
            wind_temp = c_f(data_2[1].decode('utf-8')) if data_2[1].decode('utf-8') != "Error" else None
            self.set_object_states("room_sensor_data_displayable",
                                   radiator_temperature=f"T:{radiator_temp if not isinstance(radiator_temp, float) else round(radiator_temp, 3)}°F",
                                   window_air_sensor=f"T:{wind_temp if not isinstance(wind_temp, float) else str(round(wind_temp, 2)).zfill(5)}°F"
                                                     f" | H:ERROR%",
                                   infrared_sensor=f"{data_2[3].decode('utf-8')}% - Floating",
                                   vibration_sensor=f"{False if decode_num(data_2, 4) != 0 else True} - Floating",
                                   sound_sensor=f"{False if decode_num(data_2, 5) != 0 else True} - Floating",
                                   voltage_sensor=f"{data_2[6].decode('utf-8')}V - Floating")
            # {str((data_2[2].decode('utf-8')).split('.')[0])}
        else:
            self.set_object_states("room_sensor_data_displayable", radiator_temperature=None, window_air_sensor=None,
                                   sensors_on_bus_b=None,
                                   infrared_sensor=None, vibration_sensor=None, sound_sensor=None, voltage_sensor=None)

        if self.coprocessor.connected[0] and len(data) > 1 and self.coprocessor.connected[1] and len(data_2) > 1:
            self.set_object_states("room_sensor_data_displayable", arduino_connections=f"All Online")
        elif self.coprocessor.connected[0] and len(data) > 1:
            self.set_object_states("room_sensor_data_displayable", arduino_connections=f"Arduino B Offline")
        elif self.coprocessor.connected[1] and len(data_2) > 1:
            self.set_object_states("room_sensor_data_displayable", arduino_connections=f"Arduino A Offline")
        else:
            self.set_object_states("room_sensor_data_displayable", arduino_connections=f"All Offline")

        motion_time_delta = time.time() - self.occupancy_detector.last_motion_time
        # print(f"Motion time delta: {motion_time_delta}")
        if self.occupancy_detector.last_motion_time == 0:
            self.set_object_states("room_sensor_data_displayable", last_motion="Unknown")
        else:
            self.set_object_states("room_sensor_data_displayable",
                                   last_motion=f"{time_delta_to_str(motion_time_delta)} ago")

        if motion_time_delta < 30:
            self.coprocessor.update_lcd_backlight_state(override=True, override_state=1)
        else:
            self.coprocessor.update_lcd_backlight_state()

        if self.occupancy_detector.is_occupied():
            self.set_object_states("room_occupancy_info", room_occupied=True,
                                   last_motion=self.occupancy_detector.last_motion_time,
                                   bt_error=self.occupancy_detector.is_errored(),
                                   occupants=self.occupancy_detector.occupancy_info(),
                                   logs=self.occupancy_detector.stalker.stalker_logs)
            return True
        else:
            self.set_object_states("room_occupancy_info", room_occupied=False,
                                   last_motion=self.occupancy_detector.last_motion_time,
                                   bt_error=self.occupancy_detector.is_errored(),
                                   occupants=self.occupancy_detector.occupancy_info(),
                                   logs=self.occupancy_detector.stalker.stalker_logs)
            return False

    def read_data(self):
        """
        Start a thread to read the data from the local thermostat
        :return:
        """
        self.last_download = time.time()
        thread = threading.Thread(target=self._read_thermostat, args=(), daemon=True).start()
        self.occupancy_detector.check_inventory()
        if time.time() - self.occupancy_detector.last_motion_time < 30 or self.occupancy_detector.last_motion_time == 0:
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
        log.debug("Reading data from local thermostat, saving to file")
        # self._load_data()
        self.coprocessor.update_sensors()
        if not self.sensor_powered and self.sensor_restart_time + 10 < time.time():
            log.info("Sensor is not powered, restarting")
            GPIO.output(self.channel, GPIO.HIGH)
            self.sensor_restart_time = time.time()
            self.sensor_powered = True
        # self._save_data()
        try:
            humidity1, temp1 = Adafruit_DHT.read_retry(self.sensor, 4)
            humidity2, temp2 = Adafruit_DHT.read_retry(self.sensor, 4)
            if humidity1 is not None and humidity2 is not None:
                humidity = (humidity1 + humidity2) / 2
                if abs(humidity1 - humidity2) > 2:
                    log.warning("Humidity difference is too large")
                    humidity = None
                if humidity > 100:
                    log.warning("Humidity off scale high")
                elif humidity < 0:
                    log.warning("Humidity off scale low")
                else:
                    self.net_client.data['humidity'] = humidity
                    self.net_client.data['last_read'] = time.time()
            else:
                self.net_client.data['humidity'] = -1
                log.error("Failed to read humidity")
                if self.sensor_powered and self.sensor_restart_time + 10 < time.time():
                    log.warning("Powering off the sensor")
                    GPIO.output(self.channel, GPIO.LOW)  # Kill power to the sensor to reset it
                    self.sensor_powered = False
                    self.sensor_restart_time = time.time()
            if temp1 is not None and temp2 is not None:
                temp = (temp1 + temp2) / 2
                if abs(temp1 - temp2) > 2:
                    log.warning("Temperature difference is too large")
                    temp = None
                self.net_client.data['temperature'] = temp
                self.net_client.data['last_read'] = time.time()
            else:
                self.net_client.data['temperature'] = -9999
                log.error("Failed to read temperature")
                if self.sensor_powered and self.sensor_restart_time + 10 < time.time():
                    log.warning("Powering off the sensor")
                    GPIO.output(self.channel, GPIO.LOW)  # Kill power to the sensor to reset it
                    self.sensor_powered = False
                    self.sensor_restart_time = time.time()
        except Exception as e:
            log.error("Failed to read data from local thermostat: {}".format(e))
            # GPIO.output(self.channel, GPIO.LOW)
            # GPIO.output(self.channel, GPIO.HIGH)
        finally:
            self._save_data()

    def _save_data(self):
        """
        Save the thermostat data to a file to be read by remote thermostats
        :return:
        """
        if not self.last_save + 30 < time.time():
            return
        self.net_client.data['last_update'] = time.time()
        # Move the last save file to a backup folder
        log.debug("Preforming save of room state data...")
        if os.path.isfile(save_file):
            try:
                os.renames(os.path.join("/home/pi/Downloads/modules", save_file),
                           os.path.join("/home/pi/Downloads/modules", backup_file))
            except Exception as e:
                log.error(f"Failed to rename {save_file} to {backup_file}: {e}")
        else:
            log.warning("Main coordination save file missing, cannot backup missing file")
        with open(save_file, "w") as f:
            json.dump(self.net_client.data, f, indent=2)
        self.last_save = time.time()

    def _load_data(self):
        """
        Load the room coordination data from a file for persistent state after a restart
        :return:
        """
        if os.path.isfile(save_file):
            with open(save_file) as f:
                try:
                    self.net_client.data = json.load(f)
                    log.info("Loaded data from main save file")
                except json.JSONDecodeError:
                    log.warning("Failed to load data from file, corrupt file or empty file attempting to load backup")
                    if os.path.isfile(backup_file):
                        try:
                            with open(backup_file) as f2:
                                self.net_client.data = json.load(f2)
                                log.info("Loaded backup file")
                        except json.JSONDecodeError:
                            log.error("Failed to load backup file, corrupt file or empty file")
                            log.warning("Rebuilding room data from scratch")
        elif os.path.isfile(backup_file):
            log.warning("No save file found, attempting to load backup")
            with open(backup_file) as f:
                try:
                    self.net_client.data = json.load(f)
                    log.info("Loaded backup file")
                except json.JSONDecodeError:
                    log.error("Failed to load data from backup file, corrupt file or empty file")
                    log.warning("Rebuilding room data from scratch")
        else:
            log.error("No primary or backup file found, creating new file")

    def get_object_state(self, object_name, update=True, dameon=False):
        """
        Get the state of an object from the coordinator
        :param object_name: The name of the object
        :param update: If True, update the data from the coordinator
        :param dameon: Unused in this implementation
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
        if self.get_temperature() <= self.net_client.data['temp_set_point'] - 0.75 and self.get_object_state(
                "big_wind_state") != 0:
            self.set_object_state("big_wind_state",
                                  0)  # If the temperature is 1 degrees below the set point, turn off both fans
            return "big-wind-off"
        elif self.get_temperature() <= self.net_client.data['temp_set_point'] and self.get_object_state(
                "big_wind_state") == 3:
            self.set_object_state("big_wind_state",
                                  2)  # If the temperature is 0.75 degrees below the set point, turn off the intake fan
            return "big-wind-out"
        elif self.get_temperature() >= self.net_client.data['temp_set_point'] + 1.5 and self.get_object_state(
                "big_wind_state") != 3:
            self.set_object_state("big_wind_state",
                                  3)  # If the temperature is 1.5 degrees above the set point, turn on both fans
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
        if self.net_client.data['humid_set_point'] == 0:
            return
        if self.net_client.data['humidity'] == -1 and self.net_client.data['humid_set_point'] != 0:
            if self._calculate_humid_state() != 1:
                self.set_object_state("big_humid_state", True)
                self.set_object_state("little_humid_state", False)
        elif self.net_client.data['humidity'] > self.net_client.data['humid_set_point'] + 2:
            if self._calculate_humid_state() != 0:
                self.set_object_state("big_humid_state", False)
                self.set_object_state("little_humid_state", False)
                return "humid-off"
        elif self.net_client.data['humid_set_point'] <= self.net_client.data['humidity'] <= self.net_client.data[
            'humid_set_point'] + 2:
            if self._calculate_humid_state() != 1 and self._calculate_humid_state() != 0:
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
        return c_f(self.net_client.data['temperature']) if self.net_client.data['temperature'] != -9999 else -9999

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
