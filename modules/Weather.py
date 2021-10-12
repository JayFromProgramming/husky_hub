import os
import platform
import statistics
import time
import sys
import datetime
import traceback
import psutil

from OpenWeatherWrapper import OpenWeatherWrapper
from Radar import Radar
from WebcamStream import CampusCams as WebcamStream
from AlexaIntegration import AlexaIntegration
from CurrentWeather import CurrentWeather
from LoadingScreen import LoadingScreen
from ForecastEntry import ForecastEntry
from WeatherAlert import WeatherAlert

import pygame
from pygame.locals import *
import logging as log

py = platform.platform() == 'Linux-5.10.17-v7+-armv7l-with-debian-10.9'
# Yes i know this will break when i update my py, and i don't care

if py:
    # os.chdir("/home/pi/Downloads/modules")
    log.basicConfig(filename="../weatherLogs.txt",
                    level=log.INFO, format="%(levelname)s: %(asctime)s - %(message)s")
    fps = 14
else:
    log.basicConfig(filename="../weatherLogs.txt", level=log.INFO, format="%(levelname)s: %(asctime)s - %(message)s")
    fps = 30

pygame.init()
pygame.font.init()

width, height = 800, 475

if py:
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF | pygame.ASYNCBLIT)
    if pygame.mouse.get_pos() == (0, 0):
        log.warning("Touch screen is not properly calibrated, attempting to recalibrate")
        pygame.mouse.set_pos(400, 230)
        no_mouse = True
    pygame.display.get_wm_info()
else:
    screen = pygame.display.set_mode((width, height), pygame.DOUBLEBUF | pygame.RESIZABLE | pygame.ASYNCBLIT)
    pygame.display.set_caption("Initializing...")
    pygame.display.get_wm_info()

no_image = pygame.image.load(os.path.join(f"Assets/Images/No_image.png")).convert_alpha()
husky = pygame.image.load(os.path.join(f"Assets/Images/Husky.png")).convert_alpha()
empty_image = pygame.image.load(os.path.join(f"Assets/Images/Empty.png")).convert_alpha()
icon = pygame.image.load(os.path.join("Assets/Images/Icon.png"))
splash = pygame.image.load(os.path.join("Assets/Images/splash_background2.jpg")).convert()
no_mouse_icon = pygame.image.load(os.path.join("Assets/Images/NoMouse.png")).convert()
weather_alert = pygame.image.load(os.path.join("Assets/Images/alert.png")).convert_alpha()
no_fan_icon = pygame.image.load(os.path.join("Assets/Images/No_fan.png")).convert_alpha()
overheat_icon = pygame.image.load(os.path.join("Assets/Images/overheat.png")).convert_alpha()
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

refresh_forecast = True
focused_forecast = None
screen_dimmed = False
no_mouse = False
overheat_halt = False
weather_alert_display = None
weather_alert_number = 0
display_mode = "init"
room_button = pygame.Rect(120, 450, 100, 40)
room_button_text = "Room Control"
webcam_button = pygame.Rect(10, 450, 100, 40)
webcam_button_text = "Webcams"
home_button = pygame.Rect(10, 450, 100, 40)
home_button_text = "Home"
forecast_button = pygame.Rect(120, 450, 100, 40)
forecast_button_text = "Future"
alert_collider = pygame.Rect(100, 0, 200, 40)
radar_collider = pygame.Rect(0, 0, 75, 75)

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

weatherAPI = OpenWeatherWrapper(log)
webcams = WebcamStream(log, (no_image, husky, empty_image), not py, False, py)
room_control = AlexaIntegration(log)
current_weather = CurrentWeather(weatherAPI, icon_cache, icon)
loading_screen = LoadingScreen(weatherAPI, icon_cache, forecast, (no_image, husky, empty_image, splash), (webcams, current_weather))
radar = Radar(log, weatherAPI)

room_button_render = button_font.render(room_button_text, True, pallet_four).convert_alpha()
webcam_button_render = button_font.render(webcam_button_text, True, pallet_four).convert_alpha()
home_button_render = button_font.render(home_button_text, True, pallet_four).convert_alpha()
forecast_button_render = button_font.render(forecast_button_text, True, pallet_four).convert_alpha()


def uncaught(exctype, value, tb):
    log.critical(f"Uncaught Error\nType:{exctype}\nValue:{value}\nTraceback: {traceback.print_tb(tb)}")
    webcams.close_multicast()
    if exctype is not KeyboardInterrupt:
        pass
        # if py:
        #     log.warning("Attempting to restart from uncaught error...")
        #     time.sleep(30)
        #     # response = os.system("nohup /home/pi/weather.sh &")
        #     # log.warning(f"Response: ({response})"


sys.excepthook = uncaught


def update(dt, screen):
    global display_mode, selected_loading_hour, loading_hour, refresh_forecast, forecast, weather_alert_display
    global weather_alert_number, slot_position, focused_forecast
    global room_button, room_button_text, webcam_button, webcam_button_text, home_button, home_button_text, forecast_button
    # Go through events that are passed to the script by the window.

    if room_control.queued_routine:
        room_control.run_queued()

    if weather_alert_display:
        weather_alert_display.build_alert()

    # print(weatherAPI.current_weather.status if weatherAPI.current_weather else None)
    if weatherAPI.current_weather and weatherAPI.current_weather.status == "Rain" and not room_control.raincheck:
        log.info("Shutting off big wind due to rain")
        room_control.run_routine("f", "big-wind-off")
        room_control.raincheck = True

    for event in pygame.event.get():
        # We need to handle these events. Initially the only one you'll want to care
        # about is the QUIT event, because if you don't handle it, your game will crash
        # whenever someone tries to exit.
        if event.type == QUIT:
            webcams.close_multicast()
            webcams.focus(None)
            pygame.quit()  # Opposite of pygame.init
            sys.exit()  # Not including this line crashes the script on Windows. Possibly
            # on other operating systems too, but I don't know for sure.
        elif event.type == pygame.VIDEORESIZE:
            room_button = pygame.Rect(120, screen.get_height() - 25, 100, 40)
            forecast_button = pygame.Rect(120, screen.get_height() - 25, 100, 40)
            webcam_button = pygame.Rect(10, screen.get_height() - 25, 100, 40)
            home_button = pygame.Rect(10, screen.get_height() - 25, 100, 40)
            webcams.resize(screen)
            webcams.cycle_forward = pygame.Rect(screen.get_width() - 110, screen.get_height() - 25, 100, 40)
            webcams.cycle_backward = pygame.Rect(screen.get_width() - 220, screen.get_height() - 25, 100, 40)
            # for fore in forecast:
            #     fore.resize(screen)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                webcams.focus(None)
                pygame.quit()
                sys.exit(1)
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
            if event.key == pygame.K_c and pygame.key.get_mods() & pygame.KMOD_CTRL:
                log.info("Saved Screenshot")
                pygame.image.save(screen, "../screenshot.png")
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos  # gets mouse position
            alert = weatherAPI.one_call.alerts if weatherAPI.one_call else None
            if focused_forecast:
                focused_forecast = None
                forecast = []
                refresh_forecast = True
            # checks if mouse position is over the button
            if display_mode == "init":
                pass  # Don't do anything
            elif home_button.collidepoint(mouse_pos) and display_mode != "home":
                webcams.focus(None)
                webcams.page = 0
                display_mode = "home"
                room_control.open_since = 0

            elif room_button.collidepoint(mouse_pos) and display_mode == "home":
                webcams.focus(None)
                webcams.page = 0
                display_mode = "room_control"
                room_control.open_since = time.time()

            elif alert_collider.collidepoint(mouse_pos) and display_mode == "home" and alert:
                weather_alert_display = WeatherAlert(1, len(alert), alert=alert[weather_alert_number])
                weather_alert_display.build_alert()
                display_mode = "weather_alert"

            elif display_mode == "weather_alert":

                if home_button.collidepoint(mouse_pos) or current_weather.big_info.get_rect().collidepoint(mouse_pos) or \
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
            elif display_mode == "radar":
                if webcams.cycle_forward.collidepoint(mouse_pos):
                    radar.play_pause()
                if webcams.cycle_backward.collidepoint(mouse_pos):
                    radar.jump_too_now()
                if forecast_button.collidepoint(mouse_pos):
                    if len(radar.v2_layers) == 0:
                        radar.v1_layers = []
                        radar.v2_layers = [("PR0", 5800, ""), ("CL", 5800, "")]
                        weatherAPI._last_radar_refresh = 0
                        radar.radar_display = False
                        radar.update_radar()
                    else:
                        radar.v1_layers = ["clouds_new"]
                        radar.v2_layers = []
                        weatherAPI._last_radar_refresh = 0
                        radar.radar_display = True
                        radar.update_radar()

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
                elif radar_collider.collidepoint(mouse_pos):
                    display_mode = "radar"
                    radar.update_radar()
                for hour in forecast:
                    hour.check_click(mouse_pos)

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
            forecast.append(ForecastEntry(screen, (x + (slot_position * 85), y - 10), weather[loading_hour], loading_hour, icon_cache, icon))
        loading_hour += 1
        slot_position += 1


def draw_forecast(screen):
    """Draw forecast"""
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
    global radar
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
    if len(cpu_averages) > 30 and display_mode != "webcams":
        cpu_averages.pop(0)

    alert = weatherAPI.one_call.alerts if weatherAPI.one_call else None

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
                if webcams.resize(screen):
                    display_mode = "home"
                    radar.update_radar()
                    room_control.build_routines(0)
                    last_current_update = time.time()
                    webcams.page = 0
                    del loading_screen

        # Draw Clock
        draw_clock(pallet_four)

    elif display_mode == "home":
        # Redraw screen here.
        pygame.display.set_caption("Weather")
        current_weather.draw_current(screen, (0, 0))
        draw_forecast(screen)
        build_forecast(screen, (-80, 125))

        # Draw Clock
        draw_clock(pallet_one)

        # radar_image = pygame.image.load(io.BytesIO(radar[0]))
        # screen.blit(radar_image, (200, 200))

        # Update Weather Info
        if last_current_update < time.time() - 45:
            log.debug("Requesting Update")
            if weatherAPI.update_current_weather():
                radar.update_radar()
                current_icon = None
                failed_current_updates = 0
                if weatherAPI.current_weather:
                    current_weather.update()
                    if datetime.datetime.now(tz=datetime.timezone.utc) > weatherAPI.current_weather.sunset_time(timeformat='date'):
                        # print("After sunset")
                        if py and not screen_dimmed:
                            os.system(f"sudo sh -c 'echo \"35\" > /sys/class/backlight/rpi_backlight/brightness'")
                            screen_dimmed = True
                    elif datetime.datetime.now(tz=datetime.timezone.utc) > weatherAPI.current_weather.sunrise_time(timeformat='date'):
                        # print("After sunrise")
                        if py:
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
        pygame.display.set_caption(("Streaming " if webcams.multi_cast else "Viewing ") +
                                   f"Campus Webcams-Page: {webcams.page + 1}/{len(webcams.cameras)}")
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
        if room_control.open_since < time.time() - 60:
            room_control.open_since = 0
            display_mode = "home"
    elif display_mode == "weather_alert":
        draw_clock(pallet_one)
        weather_alert_display.draw(screen, (10, 100))
        current_weather.draw_current(screen, (0, 0))
        pygame.draw.rect(screen, [255, 206, 0], home_button)
        webcams.draw_buttons(screen)
        pygame.display.set_caption("Weather Alert")
    elif display_mode == "radar":

        radar.draw(screen)
        pygame.draw.rect(screen, [255, 206, 0], home_button)
        screen.blit(home_button_render, home_button_render.get_rect(midbottom=home_button.center))
        webcams.draw_buttons(screen)
        pygame.display.set_caption("Radar")
        pygame.draw.rect(screen, [255, 206, 0], forecast_button)
        screen.blit(forecast_button_render, forecast_button_render.get_rect(midbottom=forecast_button.center))

    if py:
        temp = round(psutil.sensors_temperatures()['cpu_thermal'][0].current, 2)
    sys_info = sys_info_font.render(
        f"CPU:{str(round(cpu_average, 2)).zfill(5)}%, Mem:{str(round((1 - (avail / total)) * 100, 2)).zfill(5)}%"
        + (f", Temp:{temp}°C" if py else "") + f", {dt}FPS", True,
        pallet_one, pallet_four)
    screen.blit(sys_info, (sys_info.get_rect(midtop=(screen.get_width() / 2, screen.get_height() - 30))))

    if alert:
        screen.blit(weather_alert, weather_alert.get_rect(topright=(800, 2)))
    if room_control.raincheck:
        screen.blit(no_fan_icon, no_fan_icon.get_rect(topright=(763, 2)))
    if (py and temp > 70) or overheat_halt:
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
        if alert:
            screen.blit(no_mouse_icon, no_mouse_icon.get_rect(topright=(800, 37)))
        else:
            screen.blit(no_mouse_icon, no_mouse_icon.get_rect(topright=(800, 2)))

    # Flip the display so that the things we drew actually show up.
    pygame.display.flip()


def run():
    global fps, no_mouse
    # Initialise PyGame.

    # weatherAPI.update_weather_map()

    # Set up the clock. This will tick every frame and thus maintain a relatively constant framerate. Hopefully.
    fps_clock = pygame.time.Clock()

    # Set up the window.

    log.info(f"Starting piWeather, OnPi:{py}")

    # Main game loop.
    dt = 1 / fps  # dt is the time since last frame.
    while True:  # Loop forever!
        update(dt, screen)  # You can update/draw here, I've just moved the code for neatness.
        draw(screen, dt)

        fps_clock.tick(fps)
        dt = round(fps_clock.get_fps())


run()
