from functools import partial
import os
import sys
import tkinter as Tk
from tkinter.messagebox import showinfo
import argparse
from tkinter import Text
import logging
from time import sleep


from ui import UIRoot
from  controller_if import ControllerInterface
from valve_message_handler import ValveMessageHandler

__version__ = "$Revision: #32 $"
__date__ = "$DateTime: 2021/02/08 09:42:51 $"

color_pallete = [
    "#b3ffe0", # bg
    "#000000", # boxes
    "#000066", # text
    "#b30000", # lines
    ]

mouse_kbd_on = False
controller_debug_mode_state = False
debug_mode = False

# The device number specifies the offset in the enumerated devices to connect to.
# Starts at 1
max_dev_num = 3
dev_num = 1

# Device endpoint filter lists (Name, (VID, PID))
ep_lists = (
    (
        'Wired',
        (
            (0x28DE, 0x1102),	#d0g
            (0x28DE, 0x1201),	#headcrab
            (0x28DE, 0x1203),	#Win: Steampal Neptune
            (0x28DE, 0x1204),	#Win: Steampal D21 / Jupiter
        )
    ),
    (
        'Wireless',
        (
            (0x28DE, 0x1142),
            (0x28DE, 0x1201), #headcrab
        )
    ),
)

# Index of the currently selected device endpoint filter list.
current_ep = 0

def get_next_device_number():
    global max_dev_num, dev_num
    dev_num = (dev_num + 1) % (max_dev_num + 1)
    if dev_num == 0:
        dev_num  = 1
    ui_root.set_dev_num(dev_num)
    return dev_num

def set_next_ep():
    '''
    Selects the next available device endpoint filter list.
    '''
    global current_ep, ep_lists
    current_ep = (current_ep + 1) % len(ep_lists)
    ui_root.set_current_ep(current_ep)
    return current_ep

def get_current_ep_selection():
    '''
    Returns the tuple (Name, selection number) for the currectly selected device endpoint filter list.
    '''
    global current_ep, ep_lists
    return (ep_lists[current_ep][0], current_ep)

def get_current_ep_list():
    '''
    Returns the currently selected device endpoint filter list.
    '''
    global current_ep, ep_lists
    return ep_lists[current_ep][1]


def display_help_dialog():
    help_txt = \
'''
Version:
  jupiter_realtime_status:
    %s - %s

Hotkeys:

 TESTING

 LOGGING
  l\tenable logging
  c\tenable log compression

 DISPLAY ACTIVITY TRIGGERING
  H\tToggle Limit Triggering
  ^d\tToggle 'Debug' Mode

 USB
   m\tToggle HID Mouse / Kbd messages
   D\tCycle through trackpad debug modes (Off, L Pad, R Pad)

 TRACKPAD
  u\tDecrease frame rate
  U\tIncrease frame rate
  i\tToggle trackpad clipping
  I\tChange Sensor IIR filter [0-5]
  C\tChange Centroid IIR filter [0-5]
  V\tToggle movement gating
  +\tPerf mode (6ms frames, no freq. hopping,
  s\tDecrease touch threshold
  S\tIncrease touch threshold
  o\tDecrease centroid threshold
  O\tIncrease centroid threshold
  /\tDecrease hysteresis
  ?\tIncrease hysteresis
  a\tCalibrate trackpads
  A\tDisplay trackpad calibration (Not implemented)
  ^\tDecrease touch frequency [0-15]. Not w FREQ_HOPPING
  &\tIncrease touch frequency [0-15]. Not w FREQ_HOPPING
  *\tToggle Frequency Hopping mode

 HAPTICS
  f\tenable haptics
  F\ttoggle haptics mode
  w\tChange haptics on us
  W\tChange haptics off us
  e\tChange haptics repeat count
  E\tChange haptics loop interval
  y\tToggle haptic mode

 IMU
  g\tIncrement IMU mode
  G\tRun IMU calibration

 JOYSTICK
  j\tThumbstick:  Raw mode toggle
  J\tThumbstick:  Calibration (3 steps)
  ^j\tThumbstick: Cancel calibration

 TRIGGER
  t\tTrigger: Raw mode toggle
  T\tTrigger: Calibration (3 steps)
  ^t\tTrigger: Cancel calibration
  K\tTrigger:Increase threshold
  k\tTrigger: Decrease threshold
 
 PRESSURE
  p\tPressure: Raw mode toggle
  P\tPressure: Calibration (3 steps)
  ^p\tPressure: Cancel calibration

 WATCHDOG (UNSUPPORTED)
  X\tTest the NXP watchdog timer 
  R\tTest the nRF watchdog timer

 SYSTEM
  d\tSelect connected controllers (current limit 2)
  v\ttoggle device type filter
  r\trestart connection
  b\treboot connected device
  B\treboot connected device into bootloader
  q\tquit
'''
    showinfo('Help', help_txt % (__version__, __date__))

##########################################################################################################
## Key stroke Callback
##########################################################################################################
def key_cb(event):
    global logger

# Logging
    if event.char == 'l':
        ui_root.set_logging_state(not ui_root.get_logging_state())

    elif event.char == 'c':
        ui_root.log_compression = not ui_root.log_compression

# System
    elif event.char == 'd':
        cntrlr_mgr.set_device_number(get_next_device_number())

    elif event.char == 'v':
        set_next_ep()
        cntrlr_mgr.set_endpoint_list(get_current_ep_list())

# Debug
    elif event.char == 'D':
        ui_root.raw_trackpad_mode += 1
        if ui_root.raw_trackpad_mode > 2:
            ui_root.raw_trackpad_mode = 0
        cntrlr_mgr.trackpad_set_raw_data_mode(ui_root.raw_trackpad_mode)

    elif event.char == '@':
        cntrlr_mgr.trackpad_set_raw_data_mode(0x0A)

# Trackpad Calibration
    elif event.char == 'a':
        if not debug_mode: 
            return
        cntrlr_mgr.capsense_calibrate(0, 0)
        cntrlr_mgr.capsense_calibrate(1, 0)

    elif event.char == 'A':
    #	logger.info(cntrlr_mgr.capsense_get_all_trackpad_cc_vals())
        logger.info(cntrlr_mgr.capsense_get_all_thumbstick_FSC_vals())


    elif event.char >= '0' and event.char <= '9':
        audio_file = int(event.char)
        logger.info('Playing file: {}'.format(audio_file) )
        cntrlr_mgr.play_audio(audio_file)

# WDT (Unimplemented)
    elif event.char == 'R':
        cntrlr_mgr.test_nrf_watchdog()

    elif event.char == 'X':
        cntrlr_mgr.test_nxp_watchdog()

# Haptic
    elif event.char == 'f':
        ui_root.set_ticking_state(not ui_root.get_ticking_state())
    elif event.char == 'F':
        ui_root.set_tick_side(not ui_root.get_tick_side())
    elif event.char == 'w':
        ui_root.increment_tick_on_us()
    elif event.char == 'W':
        ui_root.increment_tick_off_us()
    elif event.char == 'e':
        ui_root.increment_tick_repeat()
    elif event.char == 'E':
        ui_root.increment_tick_interval()

    elif event.char == 'y':
        ui_root.haptic_mode = 1 - ui_root.haptic_mode
        cntrlr_mgr.haptic_set_mode(ui_root.haptic_mode)
        
    elif event.char == 'u':
        ui_root.trackpad_framerate = ui_root.trackpad_framerate - 1	
        if ui_root.trackpad_framerate < 1:
            ui_root.trackpad_framerate = 1

        logger.info('Setting framerate to: {}'.format(ui_root.trackpad_framerate))
        cntrlr_mgr.sys_set_framerate(ui_root.trackpad_framerate)


    elif event.char == 'U':
        ui_root.trackpad_framerate = ui_root.trackpad_framerate + 1
        logger.info('Setting framerate to: {}'.format(ui_root.trackpad_framerate))
        cntrlr_mgr.sys_set_framerate(ui_root.trackpad_framerate)

# Testing
    elif event.char == '\\':
        cntrlr_mgr.trackpad_set_raw_data_mode(0x80)

    elif event.char == ';':
        cntrlr_mgr.haptic_pulse(1 ,1000, 1000, 2000)

    #	logger.info(cntrlr_mgr.get_device_info( 1 ))
    #	cntrlr_mgr.get_device_info( 1 )
    #	cntrlr_mgr.thumbstick_get_cal( 0 )
    #	cntrlr_mgr.thumbstick_get_cal( 1 )
    #	cntrlr_mgr.trigger_get_cal( 0 )
    #    cntrlr_mgr.trigger_get_cal( 1 )
    #	cntrlr_mgr.pressure_get_cal( 0 )
    #    cntrlr_mgr.pressure_get_cal( 1 )
    #	cntrlr_mgr.trackpad_get_cal( 0 )
    #    cntrlr_mgr.trackpad_get_cal( 1 )
    
    elif event.char == ':':
        cntrlr_mgr.trigger_set_cal( 0, 444, 146, 1 );

        cntrlr_mgr.thumbstick_set_cal( 0, 333, 554, 345, 441, 55, 666, 777, 888 )
        cntrlr_mgr.pressure_set_cal( 1, 899, 411 )
        cntrlr_mgr.thumbstick_set_cal( 1, 111, 222, 333, 111, 55, 666, 777, 888 )

        cntrlr_mgr.trackpad_set_cal( 0, 33, 33, 4444, 400, 4222)
        cntrlr_mgr.persist_cal( 0, 0x08 )

        cntrlr_mgr.trackpad_set_cal( 0, 22, 200, 300, 400, 500)
        cntrlr_mgr.thumbstick_set_cal( 1, 444, 333, 222, 111, 55, 666, 777, 888 )

# Trackpad Static Freq
    elif event.char == '^':
        ui_root.static_touch_freq = ui_root.static_touch_freq - 1
        if ui_root.static_touch_freq < 0:
            ui_root.static_touch_freq = 15
        cntrlr_mgr.set_setting(72, ui_root.static_touch_freq)
    
    elif event.char == '&':
        ui_root.static_touch_freq = ui_root.static_touch_freq + 1
        if ui_root.static_touch_freq > 15:
            ui_root.static_touch_freq = 0
        cntrlr_mgr.set_setting(72, ui_root.static_touch_freq)

    elif event.char == '*':
        ui_root.freq_hop_mode = 1 - ui_root.freq_hop_mode
        cntrlr_mgr.set_setting(73, ui_root.freq_hop_mode)

# Trackpad Z Threshold
    elif event.char == 's':
        ui_root.trackpad_z_threshold = ui_root.trackpad_z_threshold - 5
        cntrlr_mgr.trackpad_set_z_threshold(ui_root.trackpad_z_threshold)

    elif event.char == 'S':
        ui_root.trackpad_z_threshold = ui_root.trackpad_z_threshold + 5
        cntrlr_mgr.trackpad_set_z_threshold(ui_root.trackpad_z_threshold)

# Trackpad Hysteresis
    elif event.char == '/':
        ui_root.trackpad_hysteresis = ui_root.trackpad_hysteresis - 1
        cntrlr_mgr.trackpad_set_hysteresis(ui_root.trackpad_hysteresis)

    elif event.char == '?':
        ui_root.trackpad_hysteresis = ui_root.trackpad_hysteresis + 1
        cntrlr_mgr.trackpad_set_hysteresis(ui_root.trackpad_hysteresis)

# Trackpad Centroid Threshold
    elif event.char == 'o':
        ui_root.trackpad_centroid_threshold = ui_root.trackpad_centroid_threshold - 1
        cntrlr_mgr.trackpad_set_centroid_threshold(ui_root.trackpad_centroid_threshold)

    elif event.char == 'O':
        ui_root.trackpad_centroid_threshold = ui_root.trackpad_centroid_threshold + 1
        cntrlr_mgr.trackpad_set_centroid_threshold(ui_root.trackpad_centroid_threshold)


# Trackpad Middle Out Percentage
    elif event.char == '(':
        ui_root.middle_out_percentage = ui_root.middle_out_percentage - 5
        if ui_root.middle_out_percentage < 0:
            ui_root.middle_out_percentage = 0
        cntrlr_mgr.trackpad_set_middle_out_percentage(ui_root.middle_out_percentage)

    elif event.char == ')':
        ui_root.middle_out_percentage = ui_root.middle_out_percentage + 5
        if ui_root.middle_out_percentage > 95:
            ui_root.middle_out_percentage = 95
        cntrlr_mgr.trackpad_set_middle_out_percentage(ui_root.middle_out_percentage)


# IMU
    elif event.char == 'g':
        ui_root.imu_mode = 1 + ui_root.imu_mode
        if ui_root.imu_mode > 1:
            ui_root.imu_mode = 0

        logger.info('Setting IMU mode to: {}'.format(ui_root.imu_mode))
        cntrlr_mgr.set_imu_mode(ui_root.imu_mode)

    elif event.char == 'G':
        cntrlr_mgr.imu_calibrate()

# Pressure Commands
    elif event.char == 'p':
        ui_root.pressure_raw = 1 - ui_root.pressure_raw
        cntrlr_mgr.pressure_set_raw(ui_root.pressure_raw)

    elif event.char == 'P':
        if not debug_mode: 
            return
        
        step = ui_root.get_pressure_cal_current_step() + 1

        logger.info('Pressure cal step: {}'.format(step) )
        cntrlr_mgr.pressure_cal_step(step)

        if step >= 3:
            step = 0
        ui_root.set_pressure_cal_current_step(step)

# Trigger Commands
    elif event.char == 't':
        ui_root.trigger_raw = 1 - ui_root.trigger_raw
        cntrlr_mgr.trigger_set_raw(ui_root.trigger_raw)

    elif event.char == 'T':
        if not debug_mode: 
            return
        
        step = ui_root.get_trigger_cal_current_step() + 1

        logger.info('Trigger cal step: {}'.format(step) )
        cntrlr_mgr.trigger_cal_step(step)

        if step >= 3:
            step = 0
        ui_root.set_trigger_cal_current_step(step)

    elif event.char == 'K':
        ui_root.trigger_threshold = 1 +  ui_root.trigger_threshold
        cntrlr_mgr.trigger_set_threshold(ui_root.trigger_threshold)
    
    elif event.char == 'k':
        ui_root.trigger_threshold = -1 +  ui_root.trigger_threshold
        cntrlr_mgr.trigger_set_threshold(ui_root.trigger_threshold)

# Thumbstick Command
    elif event.char == 'j':
        ui_root.thumbstick_raw_mode = 1 - ui_root.thumbstick_raw_mode
        cntrlr_mgr.thumbstick_set_raw(ui_root.thumbstick_raw_mode)

    elif event.char == 'J':
        if not debug_mode: 
            return
        step = ui_root.get_thumbstick_cal_current_step() + 1

        logger.info('Thumbstick cal step: {}'.format(step) )
        cntrlr_mgr.thumbstick_cal_step(step)

        if step >= 3:
            step = 0
        ui_root.set_thumbstick_cal_current_step(step)

# System
    elif event.char == 'r':
        cntrlr_mgr.restart()

    elif event.char == 'h':
        display_help_dialog()

    elif event.char == 'q':
        root.destroy()

    elif event.char == 'H':
        ui_root.toggle_highlight()

    elif event.char == 'B':
        cntrlr_mgr.reboot_controller(1)

    elif event.char == 'b':
        cntrlr_mgr.reboot_controller(0) 

##########################################################################################################
## Turn off HID mouse / kbd
##########################################################################################################
    elif event.char == 'm':
        global mouse_kbd_on
        mouse_kbd_on = not mouse_kbd_on
        cntrlr_mgr.mouse_kbd_control(mouse_kbd_on)

# Toggle trackpad clipper
    elif event.char == 'i':
        ui_root.trackpad_clipping = 1 - ui_root.trackpad_clipping
        cntrlr_mgr.set_setting(66, ui_root.trackpad_clipping)

# Return to fast settings
    elif event.char == '+':
        trackpad_filt = 0x103  # Sensor IIR to 8, Centroid IIR to 0 Gate on
        ui_root.trackpad_filtering = trackpad_filt
        cntrlr_mgr.set_setting(65, trackpad_filt)

        ui_root.freq_hop_mode = 0
        cntrlr_mgr.set_setting(73, ui_root.freq_hop_mode)
        
        ui_root.static_touch_freq = 1
        cntrlr_mgr.set_setting(72, ui_root.static_touch_freq)

        ui_root.static_touch_freq = 0
        cntrlr_mgr.set_setting(72, ui_root.static_touch_freq)

        ui_root.trackpad_framerate = 6
        cntrlr_mgr.sys_set_framerate(ui_root.trackpad_framerate)



# Change trackpad Sensor IIR
    elif event.char == 'I':
        sensor_iir = ui_root.get_trackpad_sensor_iir() + 1
        if sensor_iir > 0x5:
            sensor_iir = 0
        value = cntrlr_mgr.get_setting(65)
        value = value & 0xFFF0
        value = value | sensor_iir

        ui_root.trackpad_filtering = value
        cntrlr_mgr.set_setting(65, value)

# Change trackpad Centroid IIR
    elif event.char == 'C':
        centroid_iir = ui_root.get_trackpad_centroid_iir() + 1
        if centroid_iir > 0x5:
            centroid_iir = 0

        value = cntrlr_mgr.get_setting(65)
        value = value & 0xFF0F
        value = value | ( centroid_iir << 4 )
        ui_root.trackpad_filtering = value
        cntrlr_mgr.set_setting(65, value)

# Toggle trackpad centroid movement gate
    elif event.char == 'V':
        gate_mode = 1 - ui_root.get_trackpad_gate_mode();

        value = cntrlr_mgr.get_setting(65)
        value = value & 0x0FEFF
        value = value | ( gate_mode << 8 )
        ui_root.trackpad_filtering = value
        cntrlr_mgr.set_setting(65, value)

# Toggle trackpad experimental
    elif event.char == '#':
        expr =  1 + ui_root.get_trackpad_expr();
        if expr > 2:
            expr = 0

        value = cntrlr_mgr.get_setting(65)
        value = value & 0xF9FF
        value = value | ( expr << 9 )
        ui_root.trackpad_filtering = value
        cntrlr_mgr.set_setting(65, value)

    elif event.char == 'x':
        logger.info(cntrlr_mgr.imu_get_temp())
    
    elif event.char == '[':
#	    cntrlr_mgr.imu_selftest()
#		logger.info(cntrlr_mgr.thumbstick_get_cal(0))

        cntrlr_mgr.trackpad_set_raw_data_mode(0x0A)
        logger.info(cntrlr_mgr.get_raw_trackpad_data())
        logger.info(cntrlr_mgr.get_raw_trackpad_ref()) 
#	cntrlr_mgr.haptic_enable(1)
#	logger.info(cntrlr_mgr.get_hwid())
#	cntrlr_mgr.set_imu_mode(32)
#	logger.info(cntrlr_mgr.imu_get_cal())
#	cntrlr_mgr.print_pin_test_errors()
#	(vid, pid ) = cntrlr_mgr.get_hid_vid_pid();
#	cntrlr_mgr.imu_selftest()
#	logger.info(cntrlr_mgr.capsense_get_cc_vals(0))
#	logger.info(cntrlr_mgr.capsense_get_all_thumbstick_FSC_vals())
#	logger.info(res)

    elif event.char == ']':
        cntrlr_mgr.trackpad_set_raw_data_mode(0x0A)
#        logger.info(cntrlr_mgr.imu_get_cal())

#		cntrlr_mgr.capsense_calibrate(0, 0)
    #    cntrlr_mgr.thumbstick_set_cal(0, 1500, 1500, 1100, 2300, 1500, 1500, 1100, 2200)
    #	cntrlr_mgr.haptic_enable(2)

    #	logger.info(cntrlr_mgr.imu_get_selftest_results())
    #	cntrlr_mgr.imu_set_cal( 1, -2, 3, -4, 5, -6)

##########################################################################################################
## BEGIN HELPER METHODS
##########################################################################################################
def thumbstick_cancel_cal_cb(event):
    global thumbstick_cal_current_step
    thumbstick_cal_current_step = 0
    cntrlr_mgr.thumbstick_cancel_cal()
    logger.info("Thumbstick cal canceled")

def pressure_cancel_cal_cb(event):
    global pressure_cal_current_step
    pressure_cal_current_step = 0
    cntrlr_mgr.pressure_cancel_cal()	
    logger.info("Pressure cal canceled")

def trigger_cancel_cal_cb(event):
    global trigger_cal_current_step
    trigger_cal_current_step = 0
    cntrlr_mgr.trigger_cancel_cal()
    logger.info("Trigger cal canceled")

def toggle_debug_mode_cb(event):
    global debug_mode
    debug_mode = 1 - debug_mode
    ui_root.debug_mode = debug_mode
##########################################################################################################
## UI
##########################################################################################################
def resize(event):
    ui_scale = event.width / 564.0

def connect_cb(hid_dev_mgr):
    global logger
    global mouse_kbd_on
    logger.info("CONNECT")

    # set debug usb mode
    cntrlr_mgr.set_setting(6, 0)
    cntrlr_mgr.set_imu_mode(1)


    # Disable Mouse mode
    cntrlr_mgr.mouse_kbd_control(mouse_kbd_on)

    # Enable status messages
    cntrlr_mgr.set_setting(49, 2)		
##########################################################################################################
## MAIN ENTRY
##########################################################################################################
parser = argparse.ArgumentParser()
parser.add_argument('--chinese', '-c', action='store_true', default=False)
args = parser.parse_args()
##########################################################################################################
## LANGUAGE SETUP
##########################################################################################################
if args.chinese:
    language ='chi'
else:
    language = 'eng'

##########################################################################################################
## LOGGER SETUP
##########################################################################################################
logger=logging.getLogger('RTST')
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('RTST.log')
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)

# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

##########################################################################################################
## UI SETUP
##########################################################################################################
root = Tk.Tk()
truncated_version = __version__[12:-1]
root.wm_title("Jupiter Real-Time Status Tool - v" + truncated_version)
cntrlr_mgr = ControllerInterface( get_current_ep_list(), connect_cb)

top_frame = Tk.Frame(root, bg = color_pallete[0])
canvas = Tk.Canvas(top_frame, bg = color_pallete[0], bd=-2, highlightthickness=0)
#root.geometry("1100x700")

ui_root = UIRoot(cntrlr_mgr, root, canvas, color_pallete, language)

top_frame_size = ui_root.get_size()

top_frame.pack_propagate(0)
top_frame.pack(side = Tk.TOP)

canvas.config(width=top_frame_size[0], height=top_frame_size[1])
top_frame.config(width=top_frame_size[0], height=top_frame_size[1])

root.bind('<Configure>', resize)
root.bind("<Key>", key_cb)

root.bind('<Control-Key-j>', thumbstick_cancel_cal_cb)
root.bind('<Control-Key-p>', pressure_cancel_cal_cb)
root.bind('<Control-Key-t>', trigger_cancel_cal_cb)
root.bind('<Control-Key-d>', toggle_debug_mode_cb)

canvas.pack()
Tk.mainloop()

cntrlr_mgr.shutdown()
