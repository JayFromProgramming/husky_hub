import os
import platform
import statistics
import threading
import time
import sys
import datetime
import traceback
import psutil

import Coordinator
from OpenWeatherWrapper import OpenWeatherWrapper
from Radar import Radar
from Utils import buttonGenerator
from Utils import dataLogger
from Utils import coprocessors
from WebcamStream import CampusCams as WebcamStream
from AlexaIntegration import AlexaIntegration
from CurrentWeather import CurrentWeather
from LoadingScreen import LoadingScreen
from ForecastEntry import ForecastEntry
from WeatherAlert import WeatherAlert
from RoomStateDisplay import Occupancy_display
import pygame
from pygame.locals import *
import logging as log

################################################################################

py = 'Linux' in platform.platform()
windows = 'Windows' in platform.platform()

tablet = False

if windows:
    if platform.machine() == "AMD64":
        tablet = False
    else:
        tablet = True

if py:
    # os.chdir("/home/pi/Downloads/modules")
    log.basicConfig(filename="../weatherLogs.txt",
                    level=log.INFO, format="%(levelname)s: %(asctime)s - %(message)s")
    base_fps = 14
    width, height = 800, 480
elif tablet:
    log.basicConfig(filename="../weatherLogs.txt",
                    level=log.INFO, format="%(levelname)s: %(asctime)s - %(message)s")
    base_fps = 14
    width, height = 800, 480

else:
    log.basicConfig(filename="../weatherLogs.txt", level=log.INFO, format="%(levelname)s: %(asctime)s - %(message)s")
    base_fps = 30
    width, height = 800, 480

arguments = sys.argv
headless = False
if len(arguments) > 1:
    if arguments[1] == 'headless':
        log.info("Running in headless mode")
        headless = True

screen = None
pygame.init()
pygame.font.init()

if pygame.image.get_extended() == 0:
    raise Exception("Extended image formats not supported!")


################################################################################

def graceful_exit(fatal=False):
    """Soft shutdown"""
    log.info("Attempting to close gracefully")
    webcams.close_multicast()
    coordinator.coordinator.close_server()
    if not fatal:
        coprocessor.display(upper_line="Shutting down", lower_line="Disconnected", immediately=True)
    coprocessor.close_all()
    time.sleep(0.30)
    pygame.quit()
    log.info(f"There are currently {threading.active_count()} active threads")
    for thread in threading.enumerate():
        if thread.name != "MainThread":
            log.info(f"Thread {thread.name} is still active! Attempting to terminate...")
    log.info("Graceful closure complete, attempting to exit")
    sys.exit(1)


def make_screen():
    """Create the screen and set the background"""
    global no_mouse, screen
    if headless:
        pygame.display.init()
    elif py:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.ASYNCBLIT)
        if pygame.mouse.get_pos() == (0, 0):
            log.warning("Touch screen is not properly calibrated, attempting to recalibrate")
            pygame.mouse.set_pos(400, 230)
            no_mouse = True
        pygame.display.get_wm_info()
    elif tablet:
        screen = pygame.display.set_mode((width, height), pygame.HWSURFACE | pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.ASYNCBLIT)
        # pygame.display.set_allow_screensaver(True)
    else:
        screen = pygame.display.set_mode((width, height), pygame.DOUBLEBUF | pygame.RESIZABLE | pygame.ASYNCBLIT)
        pygame.display.set_caption("Initializing...")
        pygame.display.get_wm_info()


make_screen()
# This is where the icons are loaded
if not headless:
    no_image = pygame.image.load(os.path.join(f"Assets/Images/No_image.png")).convert_alpha()
    husky = pygame.image.load(os.path.join(f"Assets/Images/Husky.png")).convert_alpha()
    empty_image = pygame.image.load(os.path.join(f"Assets/Images/Empty.png")).convert_alpha()
    icon = pygame.image.load(os.path.join("Assets/Images/Icon.png")).convert_alpha()
    splash = pygame.image.load(os.path.join("Assets/Images/splash_background2.jpg")).convert_alpha()
    no_mouse_icon = pygame.image.load(os.path.join("Assets/Images/NoMouse.png")).convert_alpha()
    weather_alert = pygame.image.load(os.path.join("Assets/Images/alert.png")).convert_alpha()
    no_fan_icon = pygame.image.load(os.path.join("Assets/Images/No_fan.png")).convert_alpha()
    overheat_icon = pygame.image.load(os.path.join("Assets/Images/overheat.png")).convert_alpha()
    down_only_icon = pygame.image.load(os.path.join("Assets/Images/download_only.png")).convert_alpha()
    up_only_icon = pygame.image.load(os.path.join("Assets/Images/upload_only.png")).convert_alpha()
    up_down_icon = pygame.image.load(os.path.join("Assets/Images/up_down.png")).convert_alpha()
    net_error_icon = pygame.image.load(os.path.join("Assets/Images/net_error.png")).convert_alpha()
    net_normal_icon = pygame.image.load(os.path.join("Assets/Images/net_standby.png")).convert_alpha()
    blue_idle = pygame.image.load(os.path.join("Assets/Images/blueIdle.png")).convert_alpha()
    blue_scan = pygame.image.load(os.path.join("Assets/Images/blueScan.png")).convert_alpha()
    blue_found = pygame.image.load(os.path.join("Assets/Images/blueFound.png")).convert_alpha()
    blue_error = pygame.image.load(os.path.join("Assets/Images/blueError.png")).convert_alpha()
    unoccupied_green = pygame.image.load(os.path.join("Assets/Images/Unoccupied_green.png")).convert()
    unoccupied_red = pygame.image.load(os.path.join("Assets/Images/Unoccupied_red.png")).convert_alpha()
    occupied_green = pygame.image.load(os.path.join("Assets/Images/Occupied_green.png")).convert()
    occupied_yellow = pygame.image.load(os.path.join("Assets/Images/Occupied_yellow.png")).convert()
    net_status: pygame.Surface = None
    blue_status: pygame.Surface = None
    pygame.display.set_icon(icon)
log.getLogger().addHandler(log.StreamHandler(sys.stdout))
log.captureWarnings(True)

clock_font = pygame.font.Font(os.path.join("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf"), 55)
sys_info_font = pygame.font.Font(os.path.join("Assets/Fonts/Jetbrains/JetBrainsMono-Regular.ttf"), 14)
# button_font = pygame.font.Font(os.path.join("Assets/Fonts/Jetbrains/JetBrainsMono-Regular.ttf"), 14)
button_font = sys_info_font

current_icon = None
pygame.mixer.quit()

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)
pallet_four = (0, 0, 0)

# This is where some flags are set
refresh_forecast = True
focused_forecast = None
screen_dimmed = 0
no_mouse = False
overheat_halt = False
weather_alert_display = None
was_focused = True
low_refresh = time.time()
weather_alert_number = 0
display_mode = "init"

# room_button = pygame.Rect(120, 450, 100, 40)
room_button_text = "Room Control"
# webcam_button = pygame.Rect(10, 450, 100, 40)
webcam_button_text = "Webcams"
# home_button = pygame.Rect(10, 450, 100, 40)
home_button_text = "Home"
# forecast_button = pygame.Rect(120, 450, 100, 40)
forecast_button_text = "Live"
alert_collider = pygame.Rect(100, 0, 200, 40)
radar_collider = pygame.Rect(0, 0, 75, 75)
occupancy_collider = pygame.Rect(760, 0, 75, 75)

forecast = []
cpu_averages = []
loading_hour = 1
slot_position = 1
max_loading_hour = 100
selected_loading_hour = 1
icon_cache = {}

last_forecast_update = 0
last_current_update = 0
failed_current_updates = 0
fps = 0

# This is where all the support modules are loaded
weatherAPI = OpenWeatherWrapper(log)
coordinator = Coordinator.Coordinator(py)  # If coordinator is True, it will behave as the room controller
data_log = dataLogger.dataLogger("data", coordinator, weatherAPI)
coprocessor = coordinator.coprocessor

if not headless:
    webcams = WebcamStream(log, (no_image, husky, empty_image), not py and not tablet, False, py)
    room_control = AlexaIntegration(log, coordinator.coordinator)
    current_weather = CurrentWeather(weatherAPI, icon_cache, icon, coordinator)
    loading_screen = LoadingScreen(weatherAPI, icon_cache, forecast, (no_image, husky, empty_image, splash), (webcams, current_weather), screen)
    radar = Radar(log, weatherAPI)
    occupancy_info_display = Occupancy_display(coordinator.coordinator)
    # This is where the buttons are created
    room_button_render = buttonGenerator.Button(button_font, (120, 430, 100, 35), room_button_text, [255, 206, 0], pallet_four)
    webcam_button_render = buttonGenerator.Button(button_font, (10, 430, 100, 35), webcam_button_text, [255, 206, 0], pallet_four)
    home_button_render = buttonGenerator.Button(button_font, (10, 430, 100, 35), home_button_text, [255, 206, 0], pallet_four)
    forecast_button_render = buttonGenerator.Button(button_font, (120, 430, 100, 35), forecast_button_text, [255, 206, 0], pallet_four)


def error_renderer(exctype, value, tb):
    font = pygame.font.Font(os.path.join("Assets/Fonts/Jetbrains/JetBrainsMono-Regular.ttf"), 14)
    font2 = pygame.font.Font(os.path.join("Assets/Fonts/Jetbrains/JetBrainsMono-Bold.ttf"), 22)
    font3 = pygame.font.Font(os.path.join("Assets/Fonts/Jetbrains/JetBrainsMono-Regular.ttf"), 18)
    hour = str(time.localtime().tm_hour).zfill(2)
    minute = str(time.localtime().tm_min).zfill(2)
    exec_type = str(exctype).strip('< >').strip("class")[2:].strip("'")
    coprocessor.display(f"Fatal Error!{hour}{minute}", exec_type, immediately=True)
    error_type = font2.render(f"Uncaught error: {exec_type}", True, pallet_one, pallet_four)
    error_message = font3.render(f"{value}", True, pallet_one, pallet_four)
    pygame.display.set_caption(f"Something went wrong! {exec_type}")
    traceback_text = []
    for trace in traceback.format_tb(tb):
        for line in trace.split("\n"):
            # Make sure the line is not longer than the screen
            if len(line) == 0:
                continue
            if len(line) > 98:
                traceback_text.append(font.render(line[:98], True, pallet_one, pallet_four))
                blit_error(error_type, error_message, traceback_text)
                time.sleep(0.2)
                traceback_text.append(font.render(line[98:], True, pallet_one, pallet_four))
                blit_error(error_type, error_message, traceback_text)
                time.sleep(0.2)
            else:
                traceback_text.append(font.render(line, True, pallet_one, pallet_four))
                blit_error(error_type, error_message, traceback_text)
                time.sleep(0.2)
    screen.fill(pallet_four)
    blit_error(error_type, error_message, traceback_text)


def blit_error(error_type, error_message, traceback_text):
    screen.blit(error_type, (10, 5))
    screen.blit(error_message, (10, 35))
    for i in range(len(traceback_text)):
        screen.blit(traceback_text[i], (10, 70 + (i * 20)))
    pygame.display.flip()


def uncaught(exctype, value, tb):
    if isinstance(exctype, KeyboardInterrupt):
        graceful_exit()
    log.critical(f"Uncaught Error\nType:{exctype}\nValue:{value}\n{traceback.print_tb(tb)}")
    if not headless:
        try:
            pygame.display.flip()
            error_renderer(exctype, value, tb)
            pygame.display.flip()
        except Exception as e:
            log.critical(f"Error in error_renderer: {e}\n{traceback.format_exc()}")
    time.sleep(7.5)
    graceful_exit(fatal=True)


sys.excepthook = uncaught


def resize(screen):
    global alert_collider, radar_collider, occupancy_collider
    # This function is called when the screen is resized.
    room_button_render.move(120, screen.get_height() - 35)
    forecast_button_render.move(120, screen.get_height() - 35)
    webcam_button_render.move(10, screen.get_height() - 35)
    home_button_render.move(10, screen.get_height() - 35)
    webcams.resize(screen)
    webcams.cycle_forward = pygame.Rect(screen.get_width() - 110, screen.get_height() - 35, 100, 35)
    webcams.cycle_backward = pygame.Rect(screen.get_width() - 220, screen.get_height() - 35, 100, 35)
    radar.update_radar()
    alert_collider = pygame.Rect(100, 0, 200, 40)
    radar_collider = pygame.Rect(0, 0, 75, 75)
    occupancy_collider = pygame.Rect(screen.get_width() - 70, 0, abs(70 - screen.get_width()), 50)
    # for fore in forecast:
    #     fore.resize(screen)


def process_click(mouse_pos):
    global focused_forecast, display_mode, weather_alert_display, refresh_forecast, forecast, weather_alert_number, selected_loading_hour, \
        slot_position, loading_hour, max_loading_hour, last_forecast_update, last_current_update, failed_current_updates, fps, \
        low_refresh, was_focused, no_mouse, overheat_halt, weather_alert_number, weather_alert_display, current_icon, base_fps
    # This is where we handle mouse clicks.
    alert = weatherAPI.one_call.alerts if weatherAPI.one_call else None
    low_refresh = time.time()
    fps = base_fps
    if focused_forecast:
        for button in focused_forecast.focused_object.radar_buttons:
            if button.rect.collidepoint(mouse_pos):
                display_mode = "radar"
                radar.v1_layers = []
                radar.v2_layers = button.button_data
                radar.radar_display = False
                radar.playing = False
                radar.update_radar()
        focused_forecast = None
        forecast = []
        refresh_forecast = True
    # checks if mouse position is over the button
    if display_mode == "init":
        pass  # Don't do anything
    elif home_button_render.rect.collidepoint(mouse_pos) and display_mode != "home":
        # When the home button is clicked, go back to the home screen.
        webcams.focus(None)
        webcams.page = 0
        display_mode = "home"
        room_control.open_since = 0

    elif room_button_render.rect.collidepoint(mouse_pos) and display_mode == "home":
        # When the room button is clicked, go to the room control screen.
        webcams.focus(None)
        webcams.page = 0
        display_mode = "room_control"
        coordinator.coordinator.read_data()
        room_control.open_since = time.time()

    elif occupancy_collider.collidepoint(mouse_pos) and display_mode == "home":
        display_mode = "occupancy_info"
        occupancy_info_display.refresh()

    elif alert_collider.collidepoint(mouse_pos) and display_mode == "home" and alert:
        # When the alert button is clicked, go to the alert screen.
        weather_alert_display = WeatherAlert(1, len(alert), alert=alert[weather_alert_number])
        weather_alert_display.build_alert()
        display_mode = "weather_alert"

    elif display_mode == "weather_alert":
        # This is the weather alert mouse click handler.
        if home_button_render.rect.collidepoint(mouse_pos) or current_weather.big_info.get_rect().collidepoint(mouse_pos) or \
                weather_alert.get_rect().collidepoint(mouse_pos):
            # If the home button is clicked, go back to the home screen.
            display_mode = "home"
            weather_alert_display = None

        if webcams.cycle_forward.collidepoint(mouse_pos):
            # If the cycle forward button is clicked, cycle forward.
            weather_alert_number += 1
            if weather_alert_number >= len(alert):
                weather_alert_number = 0
            weather_alert_display = WeatherAlert(weather_alert_number + 1, len(alert), alert=alert[weather_alert_number])

        if webcams.cycle_backward.collidepoint(mouse_pos):
            # If the cycle backward button is clicked, cycle backward.
            weather_alert_number -= 1
            if weather_alert_number < 0:
                weather_alert_number = len(alert) - 1
            weather_alert_display = WeatherAlert(weather_alert_number + 1, len(alert), alert=alert[weather_alert_number])

    elif display_mode == "occupancy_info":
        if occupancy_info_display.maximize_collider.collidepoint(mouse_pos):
            occupancy_info_display.maximize_state = not occupancy_info_display.maximize_state
        elif occupancy_info_display.maximize_state:
            occupancy_info_display.maximize_state = False
        else:
            display_mode = "home"

    elif display_mode == "webcams":
        # This is the webcams mouse click handler.
        if webcams.cycle_forward.collidepoint(mouse_pos):
            # If the cycle forward button is clicked, cycle forward.
            webcams.cycle(1)
        if webcams.cycle_backward.collidepoint(mouse_pos):
            # If the cycle backward button is clicked, cycle backward.
            webcams.cycle(-1)

        cam_id = 0
        for cam in webcams.image_frame_boxes:
            # Checks if the mouse is over a webcam.
            if cam.collidepoint(mouse_pos):
                if webcams.current_focus is None:
                    # If the mouse is over a webcam and there is no webcam currently being focused, focus on the webcam.
                    webcams.focus(cam_id)
                    break
                else:
                    # If the mouse is over a webcam and there is a webcam currently being focused, unfocus the webcam.
                    webcams.focus(None)
                    break
            cam_id += 1
    elif display_mode == "radar":
        # This is the radar mouse click handler.
        if webcams.cycle_forward.collidepoint(mouse_pos):
            # If the next button is clicked, play/pause the radar.
            radar.play_pause()
        if webcams.cycle_backward.collidepoint(mouse_pos):
            # If the previous button is clicked, stop playback and jump to now
            radar.jump_too_now()
        if forecast_button_render.rect.collidepoint(mouse_pos):
            # If the live button is clicked, return to live radar.
            radar.v1_layers = []
            radar.v2_layers = [("CL", 0, "")]
            radar.radar_display = True
            radar.update_radar()

    elif display_mode == "home":
        # This is the home mouse click handler.
        if webcam_button_render.rect.collidepoint(mouse_pos):
            # If the webcam button is clicked, go to the webcams screen.
            display_mode = "webcams"
        if webcams.cycle_forward.collidepoint(mouse_pos):
            # If the cycle forward button is clicked, go to the next forecast page
            if selected_loading_hour + 9 < max_loading_hour:
                # If the selected loading hour is not the last forecast hour, go to the next forecast hour.
                selected_loading_hour += 9
                slot_position = 1
                loading_hour = selected_loading_hour
                forecast = []
                refresh_forecast = True
        elif webcams.cycle_backward.collidepoint(mouse_pos):
            # If the cycle backward button is clicked, go to the previous forecast page
            if selected_loading_hour - 9 >= 1:
                # If the selected loading hour is not the first forecast hour, go to the previous forecast hour.
                selected_loading_hour -= 9
                slot_position = 1
                loading_hour = selected_loading_hour
                forecast = []
                refresh_forecast = True
        elif radar_collider.collidepoint(mouse_pos):
            # If the radar button is clicked, go to the radar screen.
            display_mode = "radar"
            radar.update_radar()
        for hour in forecast:
            # Checks if the mouse is over a forecast hour.
            hour.check_click(mouse_pos)

    elif display_mode == "room_control":
        # This is the room control mouse click handler.
        response = room_control.check_click(mouse_pos)
        # if response:
        #     room_control.run_routine(response)


# noinspection PyGlobalUndefined
def update(dt, screen):
    global display_mode, selected_loading_hour, loading_hour, refresh_forecast, forecast, weather_alert_display
    global weather_alert_number, slot_position, focused_forecast, fps, low_refresh, screen_dimmed
    global room_button, room_button_text, webcam_button, webcam_button_text, home_button, home_button_text, forecast_button
    # Go through events that are passed to the script by the window.

    if weatherAPI.current_weather and weatherAPI.current_weather.status == "Rain" and not room_control.raincheck and py:
        # If the weather is raining, and the raincheck is not set, set it and turn off big wind.
        log.info("Shutting off big wind due to rain")
        room_control.run_routine("f", "big-wind-off")
        room_control.raincheck = True
        coordinator.coordinator.set_object_state("big_wind_state", -1)
        coordinator.coordinator.set_object_state("fan_auto_enable", False)

    if py:
        try:
            if coordinator.coordinator.is_occupied():
                room_control.change_occupancy(True)
            else:
                room_control.change_occupancy(False)
        except IndexError:
            log.info("Coordinator index error")
            pass  # This is a bug in the coordinator, I don't plan to fix it.

        sunset_time = weatherAPI.current_weather.sunset_time(timeformat='date')
        sunrise_time = weatherAPI.current_weather.sunrise_time(timeformat='date')

        if not coordinator.coordinator.get_object_state("room_occupancy_info", False)['room_occupied'] and screen_dimmed != 14:
            os.system(f"sudo sh -c 'echo \"14\" > /sys/class/backlight/rpi_backlight/brightness'")
            coprocessor.lcd_backlight(0)
            screen_dimmed = 14

        elif datetime.datetime.now(tz=datetime.timezone.utc) > sunset_time or datetime.datetime.now(tz=datetime.timezone.utc) < sunrise_time:
            # print("After sunset")
            if coordinator.coordinator.get_object_state("room_occupancy_info", False)['room_occupied']:
                if py and coordinator.coordinator.get_object_state("room_lights_state", False)['b'] <= 1 and screen_dimmed != 30:
                    os.system(f"sudo sh -c 'echo \"30\" > /sys/class/backlight/rpi_backlight/brightness'")
                    coprocessor.lcd_backlight(0)
                    screen_dimmed = 30
                elif py and coordinator.coordinator.get_object_state("room_lights_state", False)['b'] > 1 and screen_dimmed != 124:
                    os.system(f"sudo sh -c 'echo \"124\" > /sys/class/backlight/rpi_backlight/brightness'")
                    coprocessor.lcd_backlight(1)
                    screen_dimmed = 124

        elif datetime.datetime.now(tz=datetime.timezone.utc) > sunrise_time:
            # print("After sunrise")
            if coordinator.coordinator.get_object_state("room_occupancy_info", False)['room_occupied']:
                if py and screen_dimmed != 255:
                    coprocessor.lcd_backlight(1)
                    os.system(f"sudo sh -c 'echo \"255\" > /sys/class/backlight/rpi_backlight/brightness'")
                    screen_dimmed = 255

    if not headless:
        if room_control.queued_routine:
            # If room control has any queued routines, run them.
            room_control.run_queued()

        if weather_alert_display:
            # If the weather alert display is active, build it.
            weather_alert_display.build_alert()

        if display_mode == "home" or display_mode == "occupancy_info":
            # If the display mode is home, then we need to update the weather and the forecast.
            update_weather_data()

        if low_refresh < time.time() - 15 and ((webcams.current_focus is None and not webcams.multi_cast) or display_mode != 'webcams') \
                and (py or tablet):
            # After 15 seconds of inactivity, reduce the refresh rate to 1 frame per second
            fps = 1

        if tablet and psutil.sensors_battery()[0] < 30 and psutil.sensors_battery()[2] is False:
            # If the tablet battery is low, shut down tablet
            log.warning("Shutting down due to low battery")
            os.system("shutdown -f")

        # print(pygame.mouse.get_pos())  # 567

        if py:  # The mouse down event is no longer working on the raspberry pi for some reason.
            if pygame.mouse.get_pos() != (0, 0):  # So as a workaround, we check if the mouse is not at its parking position.
                process_click(pygame.mouse.get_pos())  # If it is not, then process the click.
                pygame.mouse.set_pos((0, 0))  # And set the mouse back to its parking position.

        for event in pygame.event.get():
            # This is the event handler.
            if event.type == QUIT:
                # If the user tries to close the window, close the window.
                graceful_exit()
                # on other operating systems too, but I don't know for sure.
            elif event.type == pygame.VIDEORESIZE:
                # If the user resizes the window, resize the window.
                resize(screen)
            elif event.type == pygame.KEYDOWN:
                # This is where we handle keypresses.
                low_refresh = time.time()
                fps = base_fps
                if event.key == pygame.K_ESCAPE:
                    # If escape is pressed, quit the program.
                    graceful_exit()
                if display_mode == 'webcams':
                    if event.key == pygame.K_l:
                        if webcams.multi_cast:
                            webcams.close_multicast()
                            webcams.multi_cast = False
                        else:
                            webcams.multi_cast = True
                            webcams.last_update = time.time() - webcams.update_rate
                            webcams.update()
                    elif event.key == pygame.K_LEFT:
                        webcams.cycle(-1)
                    elif event.key == pygame.K_RIGHT:
                        webcams.cycle(1)
                    elif event.key == pygame.K_a:
                        webcams.high_performance_enabled = not webcams.high_performance_enabled
                    elif event.key == pygame.K_p:
                        webcams.pause_multicast()
                if event.key == pygame.K_c and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    # If ctrl+c is pressed, save a screenshot.
                    log.info("Saved Screenshot")
                    pygame.image.save(screen, "../screenshot.png")
            elif event.type == pygame.MOUSEBUTTONDOWN:
                process_click(event.pos)


def update_weather_data():
    # This function is called every half minute to update the weather data.
    global last_current_update, last_forecast_update, screen_dimmed, failed_current_updates, forecast, refresh_forecast, selected_loading_hour
    global loading_hour, data_log
    # Update Weather Info
    if last_current_update < time.time() - 30:
        log.debug("Requesting Update")

        coordinator.coordinator.read_data()
        # coprocessor.update_sensors()
        occupancy_info_display.refresh()
        # stalker.background_stalk()
        if py:
            data_log.log()
            temp = coordinator.coordinator.maintain_temperature()
            if temp:
                room_control.run_routine(None, temp)
            humid = coordinator.coordinator.maintain_humidity()
            if humid:
                room_control.run_routine(None, humid)

        if weatherAPI.update_current_weather():
            radar.update_radar()
            failed_current_updates = 0
            if weatherAPI.current_weather:
                current_weather.update()
        elif weatherAPI.update_current_weather() is False:
            failed_current_updates += 1
            if failed_current_updates >= 4:
                weatherAPI.current_weather = None
        if weatherAPI.update_forecast_weather():
            forecast = []
            refresh_forecast = True
            selected_loading_hour = 1
            loading_hour = selected_loading_hour
        # webcams.update_all()
        last_current_update = time.time()


def build_forecast(screen, start_location):
    """Load todays hourly weather data and build the forecast"""
    x, y = start_location
    global loading_hour, refresh_forecast, selected_loading_hour, slot_position, fps

    # pygame.draw.line(screen, (255, 255, 255), (x+42, y), (x+42, y + 145))

    if loading_hour >= selected_loading_hour + 9:
        refresh_forecast = False
        loading_hour = selected_loading_hour
        slot_position = 1

    if weatherAPI.one_call is not None:
        weather = weatherAPI.one_call.forecast_hourly + weatherAPI.weather_forecast[48:]
    else:
        weather = [None for x in range(48)]

    if refresh_forecast:
        fps = base_fps
        if loading_hour < len(weather):
            forecast.append(ForecastEntry(screen, (x + (slot_position * 85), y - 10), weather[loading_hour], loading_hour, icon_cache, icon))
        loading_hour += 1
        slot_position += 1


def draw_forecast(screen):
    """Draw forecast to screen"""
    global focused_forecast, forecast, refresh_forecast
    if not focused_forecast:
        for hour in forecast[::-1]:
            if hour.focused:
                focused_forecast = hour
            hour.draw(screen)
    else:
        if focused_forecast.focused:
            focused_forecast.draw(screen)
        else:
            focused_forecast = None
            forecast = []
            refresh_forecast = True


def draw(screen, dt):
    """
    Draw things to the window. Called once per frame.
    """
    global refresh_forecast, last_current_update, current_icon, forecast, loading_hour, fps, selected_loading_hour
    global failed_current_updates, screen_dimmed, display_mode, weather_alert_display, overheat_halt, loading_screen
    global radar, net_status
    screen.fill((0, 0, 0))  # Fill the screen with black.

    def draw_clock(pallet):
        clock = clock_font.render(datetime.datetime.now().strftime("%I:%M:%S%p"), True, pallet)
        screen.blit(clock, clock.get_rect(topright=(screen.get_width() - 6, 40)))

    total = psutil.virtual_memory()[0]
    avail = psutil.virtual_memory()[1]
    if display_mode != "webcams":
        cpu_averages.append(psutil.cpu_percent())
        cpu_average = statistics.mean(cpu_averages)
    else:
        cpu_average = psutil.cpu_percent()
    if len(cpu_averages) > fps and display_mode != "webcams":
        cpu_averages.pop(0)
    mem = (1 - (avail / total)) * 100

    alert = weatherAPI.one_call.alerts if weatherAPI.one_call else None

    if display_mode == "init":
        # This the loading screen method
        loading_screen.draw_progress(screen, (100, 300), 600)
        occupancy_icon = unoccupied_green
        coprocessor.display_splash(line1="Dorminator", line2="Ver: 1.0")
        if loading_screen.cache_icons():
            occupancy_icon = occupied_yellow
            loading_screen.load_weather()
            current_weather.update()
            current_weather.draw_current(screen, (0, 0))
            build_forecast(screen, (-80, 125))
            loading_screen.loading_percentage += \
                (loading_screen.loading_percent_bias['Forecast'] / 9)
            loading_screen.loading_status_strings.append(f"Building forecast hour ({loading_hour})")
            # coordinator.coprocessor.set_data_slot_state(5, 1)
            if refresh_forecast is False:
                occupancy_icon = unoccupied_red
                loading_screen.loading_percentage += loading_screen.loading_percent_bias['Webcams'] / 4
                loading_screen.loading_status_strings.append(f"Loading webcam page ({webcams.page})")
                if webcams.resize(screen):
                    occupancy_icon = occupied_green
                    data_log.condense()
                    if py:
                        pass
                        # data_log.condense()
                        # stalker.background_stalk()
                    if not py and not tablet:
                        data_log.export()
                    # coordinator.coordinator.read_data()
                    display_mode = "home"
                    # coordinator.coprocessor.set_data_slot_state(5, 0)
                    radar.update_radar()
                    room_control.build_routines()
                    last_current_update = time.time()
                    coprocessor.start_refresh()
                    webcams.page = 0
                    del loading_screen

        # Draw Clock
        draw_clock(pallet_four)

    elif display_mode == "home":
        # This is where the home screen is drawn
        pygame.display.set_caption("Weather")
        current_weather.draw_current(screen, (0, 0))
        draw_forecast(screen)
        build_forecast(screen, (-80, 125))
        # coprocessor.display_loading_bar("Test loading bar", time.time() % 100)
        # Draw Clock
        draw_clock(pallet_one)

        # radar_image = pygame.image.load(io.BytesIO(radar[0]))
        # screen.blit(radar_image, (200, 200))

        webcam_button_render.blit(screen)
        webcams.draw_buttons(screen)
        room_button_render.blit(screen)
        # screen.blit(room_button_render, room_button_render.get_rect(midbottom=room_button.center))
    elif display_mode == "webcams":

        pygame.display.set_caption(("Streaming " if webcams.multi_cast else "Viewing ") +
                                   f"Campus Webcams-Page: {webcams.page + 1}/{len(webcams.cameras)}")
        webcams.draw(screen)
        webcams.update()
        # pygame.draw.rect(screen, [255, 206, 0], home_button)
        webcams.draw_buttons(screen)
        home_button_render.blit(screen)
        # fps = webcams.requested_fps
    elif display_mode == "room_control":
        # This is where the room control screen is drawn
        room_control.draw_routine(screen, -10)
        pygame.display.set_caption("Room Control")
        # pygame.draw.rect(screen, [255, 206, 0], home_button)
        home_button_render.blit(screen)
        if room_control.open_since < time.time() - 100:
            room_control.open_since = 0
            display_mode = "home"
    elif display_mode == "weather_alert":
        # This is where the weather alert screen is drawn
        draw_clock(pallet_one)
        weather_alert_display.draw(screen, (10, 100))
        current_weather.draw_current(screen, (0, 0))
        # pygame.draw.rect(screen, [255, 206, 0], home_button)
        webcams.draw_buttons(screen)
        pygame.display.set_caption("Weather Alert")
    elif display_mode == "occupancy_info":
        draw_clock(pallet_one)
        occupancy_info_display.draw(screen, (10, 100))
        current_weather.draw_current(screen, (0, 0))
        # pygame.draw.rect(screen, [255, 206, 0], home_button)
        webcams.draw_buttons(screen)
        pygame.display.set_caption("Occupancy Info")
    elif display_mode == "radar":
        # This is where the radar screen is drawn
        radar.draw(screen)
        home_button_render.blit(screen)
        webcams.draw_buttons(screen)
        pygame.display.set_caption("Radar")
        forecast_button_render.blit(screen)

    if display_mode != "init":
        temperature = round(float(coordinator.coordinator.get_object_state('temperature', False)) * (9 / 5) + 32)
        humidity = round(coordinator.coordinator.get_object_state('humidity', False))
        hour = time.localtime().tm_hour % 12
        minute = time.localtime().tm_min
        # 1:  2: 3: 4: 5: 6: 7: 8:
        coprocessor.display(
            upper_line=f"CPU:{str(round(cpu_average)).zfill(2)}% T:{str(temperature).zfill(2) if -9 < temperature < 99 else '??'}F",
            lower_line=f"MEM:{str(round(mem)).zfill(2)}% H:{str(humidity).zfill(2) if humidity != -1 else '??'}%", )

    if py:
        temp = round(psutil.sensors_temperatures()['cpu_thermal'][0].current, 2)
    sys_info = sys_info_font.render(
        f"CPU:{str(round(cpu_average, 2)).zfill(5)}%, Mem:{str(round(mem, 2)).zfill(5)}%"
        + (f", Temp:{temp}°C" if py else "")
        + f", {dt}FPS" + (f", Battery:{datetime.timedelta(seconds=psutil.sensors_battery()[1]) if not True else ''}"
                          f" {psutil.sensors_battery()[0]}%" if not py else ""), True,
        pallet_one, pallet_four)
    screen.blit(sys_info, (sys_info.get_rect(midtop=(screen.get_width() / 2, screen.get_height() - 30))))

    if not coordinator.coordinator.net_client.coordinator_available:
        net_status = net_error_icon
    elif coordinator.coordinator.net_client.download_in_progress is not False and coordinator.coordinator.net_client.upload_in_progress is not False:
        net_status = up_down_icon
    elif coordinator.coordinator.net_client.download_in_progress is not False:
        net_status = down_only_icon
    elif coordinator.coordinator.net_client.upload_in_progress is not False:
        net_status = up_only_icon
    else:
        net_status = net_normal_icon
    occupancy_info = coordinator.coordinator.get_object_state('room_occupancy_info', False)

    if display_mode != 'init':
        if occupancy_info['room_occupied'] is None or not coordinator.coordinator.net_client.coordinator_available:
            occupancy_icon = unoccupied_red
        elif occupancy_info['room_occupied']:
            occupancy_icon = occupied_yellow
            for info in dict(occupancy_info['occupants']).values():
                if info['present']:
                    occupancy_icon = occupied_green
                    break
        else:
            occupancy_icon = unoccupied_green

    if coordinator.coordinator.net_client.upload_in_progress is None:
        coordinator.coordinator.net_client.upload_in_progress = False
    if coordinator.coordinator.net_client.download_in_progress is None:
        coordinator.coordinator.net_client.download_in_progress = False

    if display_mode != "webcams" and display_mode != "radar":
        screen.blit(net_status, net_status.get_rect(topright=(screen.get_width() - 5, 2)))
        if display_mode != "room_control":
            screen.blit(occupancy_icon, occupancy_icon.get_rect(topright=(screen.get_width() - 35, 2)))
        else:
            screen.blit(occupancy_icon, occupancy_icon.get_rect(topleft=(5, 2)))
    if display_mode == "home":
        if alert:
            # If a weather alert is active, draw the alert icon
            screen.blit(weather_alert, weather_alert.get_rect(topleft=(25, 65)))
        if room_control.raincheck:
            # If a raincheck is active, draw the raincheck icon
            screen.blit(no_fan_icon, no_fan_icon.get_rect(topright=(723 - 40, 2)))
        if (py and temp > 70) or overheat_halt:
            # If the CPU is too hot, draw the overheat icon
            screen.blit(overheat_icon, overheat_icon.get_rect(topright=(763, 2)))
            overheat_halt = True
            fps = 7
            if temp < 60:
                overheat_halt = False
                fps = 14
            if display_mode == "webcams" and temp > 70:
                # webcams.focus(None)
                fps = 0.5
        if no_mouse:
            # If the mouse is not detected, draw the mouse icon
            if alert:
                screen.blit(no_mouse_icon, no_mouse_icon.get_rect(topright=(800, 37)))
            else:
                screen.blit(no_mouse_icon, no_mouse_icon.get_rect(topright=(800, 2)))

    # Flip the display so that the things we drew actually show up.
    pygame.display.flip()


def run():
    global base_fps, fps, no_mouse, was_focused
    # Initialise PyGame.

    # weatherAPI.update_weather_map()

    # Set up the clock. This will tick every frame and thus maintain a relatively constant framerate. Hopefully.
    fps_clock = pygame.time.Clock()

    # Set up the window.

    log.info(f"Starting piWeather, Platform: {platform.platform()}; OnTablet:{tablet}, OnPi:{py}"
             f"\nExtended images supported?{pygame.image.get_extended()}")

    # Main game loop.
    fps = base_fps
    dt = 1 / fps  # dt is the time since last frame.
    if not headless:
        resize(screen)
    while True:  # Loop forever!
        update(dt, screen)  # You can update/draw here, I've just moved the code for neatness.
        if pygame.display.get_active() and not headless:
            draw(screen, dt)
            was_focused = True
        elif not pygame.display.get_active() and was_focused:
            was_focused = False
        elif pygame.display.get_active() and not was_focused and tablet:
            make_screen()
            update_weather_data()
        elif pygame.display.get_active() and not was_focused and not tablet:
            update_weather_data()

        fps_clock.tick(fps)
        dt = round(fps_clock.get_fps())


run()
