import io
import os
import statistics
import time
import sys
import datetime
import traceback
import psutil

import OpenWeatherWrapper as Api
import WebcamStream
from AlexaIntegration import AlexaIntegration
from CurrentWeather import CurrentWeather
from LoadingScreen import LoadingScreen
from ForecastEntry import ForecastEntry
from WeatherAlert import WeatherAlert

import pygame
from pygame.locals import *
from urllib.request import urlopen
import logging as log

py = os.getcwd() != r"C:\Users\Aidan\PycharmProjects\raspberryPiWeather\modules"

if py:
    # os.system("export DISPLAY=:0")
    os.chdir("/home/pi/Downloads/modules")
    log.basicConfig(filename="../weatherLogs.txt",
                    level=log.INFO, format="%(levelname)s: %(asctime)s - %(message)s")
else:
    log.basicConfig(filename="../weatherLogs.txt", level=log.DEBUG, format="%(levelname)s: %(asctime)s - %(message)s")

no_image = pygame.image.load(os.path.join(f"Assets/No_image.png"))
husky = pygame.image.load(os.path.join(f"Assets/Husky.png"))
empty_image = pygame.image.load(os.path.join(f"Assets/Empty.png"))
icon = pygame.image.load(os.path.join("Assets/Icon.png"))
splash = pygame.image.load(os.path.join("Assets/splash_background2.jpg"))
no_mouse_icon = pygame.image.load(os.path.join("Assets/NoMouse.png"))
weather_alert = pygame.image.load(os.path.join("Assets/alert.png"))
no_fan_icon = pygame.image.load(os.path.join("Assets/No_fan.png"))
log.getLogger().addHandler(log.StreamHandler(sys.stdout))
log.captureWarnings(True)

current_icon = None
pygame.mixer.quit()

pallet_one = (255, 206, 0)
pallet_two = (255, 206, 0)
pallet_three = (255, 255, 255)
pallet_four = (0, 0, 0)

refresh_forecast = True
screen_dimmed = False
raincheck = False
no_mouse = False
weather_alert_display = None
weather_alert_number = 0

fps = 18
forecast = []
cpu_averages = []
loading_hour = 1
slot_position = 1
max_loading_hour = 48
selected_loading_hour = 1
icon_cache = {}

last_forecast_update = 0
last_current_update = 0
failed_current_updates = 0

weatherAPI = Api.OpenWeatherWrapper(log)
webcams = WebcamStream.CampusCams(log, (no_image, husky, empty_image), not py)
room_control = AlexaIntegration(log)
current_weather = CurrentWeather(weatherAPI, icon_cache, icon)
loading_screen = LoadingScreen(weatherAPI, icon_cache, forecast, (no_image, husky, empty_image, splash), (webcams, current_weather))
# radar = RadarViewer.Radar(log, weatherAPI)

display_mode = "init"
room_button = pygame.Rect(120, 450, 100, 40)
room_button_text = "Room Control"
webcam_button = pygame.Rect(10, 450, 100, 40)
webcam_button_text = "Webcams"
home_button = pygame.Rect(10, 450, 100, 40)
home_button_text = "Home"


def uncaught(exctype, value, tb):
    log.critical(f"Uncaught Error\nType:{exctype}\nValue:{value}\nTraceback: {traceback.print_tb(tb)}")
    if exctype is not KeyboardInterrupt:
        if py:
            log.warning("Attempting to restart from uncaught error...")
            time.sleep(30)
            # response = os.system("nohup /home/pi/weather.sh &")
            # log.warning(f"Response: ({response})")


sys.excepthook = uncaught


def update(dt):
    global display_mode, selected_loading_hour, loading_hour, refresh_forecast, forecast, raincheck, weather_alert_display
    global weather_alert_number, slot_position
    # Go through events that are passed to the script by the window.
    if room_control.queued_routine:
        room_control.run_queued()

    if weather_alert_display:
        weather_alert_display.build_alert()

    # print(weatherAPI.current_weather.status if weatherAPI.current_weather else None)
    if weatherAPI.current_weather and weatherAPI.current_weather.status == "Rain" and not raincheck:
        log.info("Shutting off big wind due to rain")
        room_control.run_routine(
            "https://api.voicemonkey.io/trigger?access_token={access_token}&secret_token={secret_token}&monkey=big-wind-off")
        raincheck = True

    for event in pygame.event.get():
        # We need to handle these events. Initially the only one you'll want to care
        # about is the QUIT event, because if you don't handle it, your game will crash
        # whenever someone tries to exit.
        if event.type == QUIT:
            webcams.focus(None)
            pygame.quit()  # Opposite of pygame.init
            sys.exit()  # Not including this line crashes the script on Windows. Possibly
            # on other operating systems too, but I don't know for sure.
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                webcams.focus(None)
                pygame.quit()
                sys.exit(1)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos  # gets mouse position
            alert = weatherAPI.one_call.alerts
            # checks if mouse position is over the button
            if display_mode == "init":
                pass  # Don't do anything
            elif home_button.collidepoint(mouse_pos) and display_mode != "home":
                webcams.focus(None)
                webcams.page = 0
                display_mode = "home"

            elif room_button.collidepoint(mouse_pos) and display_mode == "home":
                webcams.focus(None)
                webcams.page = 0
                display_mode = "room_control"

            elif (current_weather.big_info.get_rect().collidepoint(mouse_pos) or weather_alert.get_rect().collidepoint(mouse_pos)) \
                    and display_mode == "home" and alert:
                weather_alert_display = WeatherAlert(1, len(alert), alert=alert[weather_alert_number])
                weather_alert_display.build_alert()
                display_mode = "weather_alert"

            elif display_mode == "weather_alert":

                if home_button.collidepoint(mouse_pos) or current_weather.big_info.get_rect().collidepoint(mouse_pos) or\
                        weather_alert.get_rect().collidepoint(mouse_pos):
                    display_mode = "home"
                    weather_alert_display = None

                if webcams.cycle_forward.collidepoint(mouse_pos):
                    weather_alert_display = WeatherAlert(weather_alert_number + 1, len(alert), alert=alert[weather_alert_number])
                    weather_alert_number += 1
                    if weather_alert_number >= len(alert):
                        weather_alert_number = 0

                if webcams.cycle_backward.collidepoint(mouse_pos):
                    weather_alert_display = WeatherAlert(weather_alert_number + 1, len(alert), alert=alert[weather_alert_number])
                    weather_alert_number -= 1
                    if weather_alert_number < 0:
                        weather_alert_number = 0

            elif display_mode == "webcams":
                if webcams.cycle_forward.collidepoint(mouse_pos):
                    webcams.cycle(1)
                if webcams.cycle_backward.collidepoint(mouse_pos):
                    webcams.cycle(-1)

                cam_id = 0
                for cam in webcams.image_frame_boxes:
                    if cam.collidepoint(mouse_pos):
                        if webcams.current_focus is None:
                            webcams.focus(cam_id)
                            break
                        else:
                            webcams.focus(None)
                            break
                    cam_id += 1

            elif display_mode == "home":
                if webcam_button.collidepoint(mouse_pos):
                    display_mode = "webcams"
                if webcams.cycle_forward.collidepoint(mouse_pos):
                    if selected_loading_hour + 9 < max_loading_hour:
                        selected_loading_hour += 9
                        slot_position = 1
                        loading_hour = selected_loading_hour
                        forecast = []
                        refresh_forecast = True
                elif webcams.cycle_backward.collidepoint(mouse_pos):
                    if selected_loading_hour - 9 >= 1:
                        selected_loading_hour -= 9
                        slot_position = 1
                        loading_hour = selected_loading_hour
                        forecast = []
                        refresh_forecast = True

            elif display_mode == "room_control":
                response = room_control.check_click(mouse_pos)
                # if response:
                #     room_control.run_routine(response)

        # Handle other events as you wish.


def build_forecast(screen, start_location):
    """Load todays hourly weather"""
    x, y = start_location
    global loading_hour, refresh_forecast, selected_loading_hour, slot_position

    # pygame.draw.line(screen, (255, 255, 255), (x+42, y), (x+42, y + 145))

    if loading_hour >= selected_loading_hour + 9:
        refresh_forecast = False
        loading_hour = selected_loading_hour
        slot_position = 1

    if weatherAPI.one_call is not None:
        weather = weatherAPI.one_call.forecast_hourly
    else:
        weather = [None for x in range(48)]

    if refresh_forecast:
        if loading_hour < len(weather):
            forecast.append(ForecastEntry(screen, (x + (slot_position * 85), y), weather[loading_hour], loading_hour, icon_cache, icon))
        loading_hour += 1
        slot_position += 1


def draw_forecast(screen):
    """Draw forecast"""
    for hour in forecast:
        hour.draw(screen)


def draw(screen):
    """
    Draw things to the window. Called once per frame.
    """
    global refresh_forecast, last_current_update, current_icon, forecast, loading_hour, fps, selected_loading_hour
    global failed_current_updates, screen_dimmed, display_mode, weather_alert_display
    screen.fill((0, 0, 0))  # Fill the screen with black.

    def draw_clock(pallet):
        font1 = pygame.font.SysFont('timesnewroman', 65)
        clock = font1.render(datetime.datetime.now().strftime("%I:%M:%S %p"), True, pallet)
        screen.blit(clock, (425, 40))

    sys_info_font = pygame.font.SysFont('timesnewroman', 14)
    total = psutil.virtual_memory()[0]
    avail = psutil.virtual_memory()[1]
    cpu_averages.append(psutil.cpu_percent())
    if len(cpu_averages) > 30:
        cpu_averages.pop(0)
    cpu_average = statistics.mean(cpu_averages)
    sys_info = sys_info_font.render(f"CPU: {str(round(cpu_average, 2)).zfill(5)}%,  Mem: {str(round((1 - (avail / total)) * 100, 2)).zfill(5)}%"
                                    + (f", Temp {round(psutil.sensors_temperatures()['cpu_thermal'][0].current, 2)}°C" if py else ""), True,
                                    pallet_one)
    screen.blit(sys_info, (sys_info.get_rect(midtop=(400, 445))))

    alert = weatherAPI.one_call.alerts if weatherAPI.one_call else None

    if alert:
        screen.blit(weather_alert, weather_alert.get_rect(topright=(800, 2)))
    if raincheck:
        screen.blit(no_fan_icon, no_fan_icon.get_rect(topright=(763, 2)))
    if no_mouse:
        if alert:
            screen.blit(no_mouse_icon, no_mouse_icon.get_rect(topright=(800, 37)))
        else:
            screen.blit(no_mouse_icon, no_mouse_icon.get_rect(topright=(800, 2)))

    button_font = pygame.font.SysFont('couriernew', 14)
    room_button_render = button_font.render(room_button_text, True, pallet_four)
    webcam_button_render = button_font.render(webcam_button_text, True, pallet_four)
    home_button_render = button_font.render(home_button_text, True, pallet_four)

    if display_mode == "init":

        loading_screen.draw_progress(screen, (100, 300), 600)

        if loading_screen.cache_icons():
            loading_screen.load_weather()
            current_weather.draw_current(screen, (0, 0))
            build_forecast(screen, (-80, 125))
            loading_screen.loading_percentage += \
                (loading_screen.loading_percent_bias['Forecast'] / 9)
            loading_screen.loading_status_strings.append(f"Building forecast hour ({loading_hour})")
            if refresh_forecast is False:
                loading_screen.loading_percentage += loading_screen.loading_percent_bias['Webcams'] / 4
                loading_screen.loading_status_strings.append(f"Loading webcam page ({webcams.page})")
                if webcams.update_all():
                    display_mode = "home"
                    room_control.build_routines(0)
                    last_current_update = time.time()
                    webcams.page = 0

        # Draw Clock
        draw_clock(pallet_four)

    elif display_mode == "home":
        # Redraw screen here.
        pygame.display.set_caption("Weather")
        current_weather.draw_current(screen, (0, 0))
        draw_forecast(screen)
        build_forecast(screen, (-80, 125))
        webcams.requested_fps = 30

        # Draw Clock
        draw_clock(pallet_one)

        # radar_image = pygame.image.load(io.BytesIO(radar[0]))
        # screen.blit(radar_image, (200, 200))

        # Update Weather Info
        if last_current_update < time.time() - 45:
            log.debug("Requesting Update")
            if weatherAPI.update_current_weather():
                current_icon = None
                failed_current_updates = 0
                if weatherAPI.current_weather:
                    if datetime.datetime.now(tz=datetime.timezone.utc) > weatherAPI.current_weather.sunset_time(timeformat='date'):
                        # print("After sunset")
                        if py and not screen_dimmed:
                            os.system(f"sudo sh -c 'echo \"35\" > /sys/class/backlight/rpi_backlight/brightness'")
                            screen_dimmed = True
                    elif datetime.datetime.now(tz=datetime.timezone.utc) > weatherAPI.current_weather.sunrise_time(timeformat='date'):
                        # print("After sunrise")
                        if py and screen_dimmed:
                            os.system(f"sudo sh -c 'echo \"255\" > /sys/class/backlight/rpi_backlight/brightness'")
                            screen_dimmed = False
            elif weatherAPI.update_current_weather() is False:
                failed_current_updates += 1
                if failed_current_updates >= 4:
                    weatherAPI.current_weather = None
            if weatherAPI.update_future_weather():
                forecast = []
                refresh_forecast = True
                selected_loading_hour = 1
                loading_hour = selected_loading_hour
            # webcams.update_all()
            last_current_update = time.time()

        pygame.draw.rect(screen, [255, 206, 0], webcam_button)
        screen.blit(webcam_button_render, webcam_button_render.get_rect(midbottom=webcam_button.center))
        webcams.draw_buttons(screen)
        pygame.draw.rect(screen, [255, 206, 0], room_button)
        screen.blit(room_button_render, room_button_render.get_rect(midbottom=room_button.center))
    elif display_mode == "webcams":
        pygame.display.set_caption("Campus Webcams")
        webcams.draw(screen)
        webcams.update()
        pygame.draw.rect(screen, [255, 206, 0], home_button)
        webcams.draw_buttons(screen)
        screen.blit(home_button_render, home_button_render.get_rect(midbottom=home_button.center))
        # fps = webcams.requested_fps
    elif display_mode == "room_control":
        room_control.draw_routine(screen, 0)
        pygame.display.set_caption("Room Control")
        pygame.draw.rect(screen, [255, 206, 0], home_button)
        screen.blit(home_button_render, home_button_render.get_rect(midbottom=home_button.center))
    elif display_mode == "weather_alert":
        draw_clock(pallet_one)
        weather_alert_display.draw(screen, (10, 100))
        current_weather.draw_current(screen, (0, 0))
        pygame.draw.rect(screen, [255, 206, 0], home_button)
        webcams.draw_buttons(screen)


    # Flip the display so that the things we drew actually show up.
    pygame.display.flip()


def run():
    global fps, no_mouse
    # Initialise PyGame.
    pygame.init()
    pygame.font.init()

    # weatherAPI.update_weather_map()

    # Set up the clock. This will tick every frame and thus maintain a relatively constant framerate. Hopefully.
    fps_clock = pygame.time.Clock()

    # Set up the window.
    width, height = 800, 475

    log.info(f"Starting piWeather, OnPi:{py}")
    if py:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        if pygame.mouse.get_pos() == (0, 0):
            log.warning("Touch screen is not properly calibrated, attempting to recalibrate")
            pygame.mouse.set_pos(400, 230)
            no_mouse = True
        pygame.display.get_wm_info()
    else:
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Initializing...")
        pygame.display.set_icon(icon)
        pygame.display.get_wm_info()

    # Main game loop.
    dt = 1 / fps  # dt is the time since last frame.
    while True:  # Loop forever!
        update(dt)  # You can update/draw here, I've just moved the code for neatness.
        draw(screen)

        dt = fps_clock.tick(fps)


run()
