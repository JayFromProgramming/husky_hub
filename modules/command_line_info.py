# Display Room Information over the Command Line
import datetime
import sys
import json
import os
import time
import socket


def c_f(celsius):
    return (float(celsius) * (9 / 5)) + 32


def room_state_string(room_state):
    if room_state == 1:
        return "Normal"
    elif room_state == 2:
        return "Away"
    elif room_state == 3:
        return "Sleep"
    elif room_state == -1:
        return "Unknown"


def fan_state_string(fan_state, fan_auto, target):
    power = "Unknown"
    if fan_state == 0 and not fan_auto:
        power = "Off"
    elif fan_state == 0 and fan_auto:
        power = "Idle"
    elif fan_state == 1:
        power = "Intake"
    elif fan_state == 2:
        power = "Exhaust"
    elif fan_state == 3:
        power = "Full"

    if fan_auto:
        return f"{power} -- Auto: {target}F"
    else:
        return f"{power}"


def humid_state_string(big_humid, little_humid, target):
    power = "Unknown"
    if not big_humid and not little_humid and target == 0:
        power = "Off"
    elif not big_humid and not little_humid:
        power = "Idle"
    elif big_humid and not little_humid:
        power = "Maintaining"
    elif not big_humid and little_humid:
        power = "Half Power"
    elif big_humid and little_humid:
        power = "Maximum"

    if target != 0:
        return f"{power} -- Auto: {target}%"
    else:
        return power


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


sys.wk_dir = os.path.dirname(os.path.realpath(__file__))

if len(sys.argv) < 2:
    print("Usage: python3 command_line_info.py <requested_mode> [arguments]")
    sys.exit(1)

requested_info = sys.argv[1]


room_info = json.load(open('Configs/states_template.json'))
try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(("141.219.250.6", 47670))
        request = json.dumps({"client": "Command Line Utility", "auth": "qg8Rf68gB2n8reTNDxoQbp8kWmdA^Yp%VxgHA&xS&", "type": "download_state"})
        s.sendall(request.encode())
        data_buff = b''
        while True:
            data = s.recv(1024)
            if not data:
                break
            data_buff += data
        data = json.loads(data_buff.decode())
        for key in data.keys():
            room_info[key] = data[key]
except Exception as e:
    print("Failed to establish connection to the WOPR service.\n")
    os.system("sudo systemctl restart weather.service")
    print("Restarting the service...")
    exit(1)
if requested_info == "all":
    occupancy = room_info['room_occupancy_info']
    room_state = room_info['room_sensor_data_displayable']
    present = [occupant for occupant in occupancy['occupants'].values() if occupant['present'] is True]
    absent = [occupant for occupant in occupancy['occupants'].values() if occupant['present'] is False]
    # max_present_rjust = max([len(occupant['name']) for occupant in present] if len(present) > 0 else [0])
    # max_absent_rjust = max([len(occupant['name']) for occupant in absent] if len(absent) > 0 else [0])
    print("-" * 10 + "Room Data" + "-" * 10)
    print(f"Room Air Sensor: T: {round(c_f(room_info['temperature']), 2)}F | H: {round(room_info['humidity'], 2)}%")
    print(f"Window Air Sensor: {room_state['window_air_sensor']}")
    print(f"Radiator Temp: {room_state['radiator_temperature']}")
    print(f"Room State: {room_state_string(room_info['room_state'])}")
    print(f"Fan State: {fan_state_string(room_info['big_wind_state'], room_info['fan_auto_enable'], room_info['temp_set_point'])}")
    print(f"Humidifier State: {humid_state_string(room_info['big_humid_state'], room_info['little_humid_state'], room_info['humid_set_point'])}")
    print("-" * 10 + "Occupancy Info" + "-" * 10)
    print(f"Last Motion: {time_delta_to_str(time.time() - occupancy['last_motion'])} ago")
    print("Currently Present")
    for occupant in present:
        print(f"{occupant['name']}: Arrived at "
              f"{datetime.datetime.fromtimestamp(occupant['updated_at']).strftime('%I:%M:%S%p-%m/%d/%y')}")
    print("Not Present")
    for occupant in absent:
        print(f"{occupant['name']}: Last seen at "
              f"{datetime.datetime.fromtimestamp(occupant['updated_at']).strftime('%I:%M:%S%p-%m/%d/%y')}")
    print("")
    print("Last updated:", datetime.datetime.fromtimestamp(room_info['last_update']).strftime('%I:%M:%S%p-%m/%d/%y'), end="")
