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

__version__ = "$Revision: #19 $"
__date__ = "$DateTime: 2022/06/29 11:08:41 $"

color_pallete = [
    "#b3ffe0", # bg
    "#000000", # boxes
    "#000066", # text
    "#b30000", # lines
    ]

mouse_kbd_on = False
controller_debug_mode_state = False
debug_mode = False

haptic_intensity_idx = 0
haptic_intenisty = [ 16000, 8000, 1000, 320, 200, 100, 60, 16 ]

# The device number specifies the offset in the enumerated devices to connect to.
# Starts at 1
max_dev_num = 3
dev_num = 1

test_wub_freq = 170
semi_tone = 2**(1/12)

deadzone_on = 1
# Device endpoint filter lists (Name, (VID, PID))
ep_lists = (
    (
        'Wired',
        (
            (0x28DE, 0x1102),	#d0g
            (0x28DE, 0x1201),	#headcrab
            (0x28DE, 0x1203),	#Win: Steampal Neptune
            (0x28DE, 0x1204),	#Win: Steampal D21 / Jupiter
            (0x28DE, 0x1205),	#Win: Jupiter2
            (0x28DE, 0x1206),	#Win: Jupiter3
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

 LOGGING
  l\tEnable logging
  c\tEnable log compression

 DISPLAY ACTIVITY TRIGGERING
  H\tToggle Limit Triggering
  ^d\tToggle 'Debug' Mode
  '`'\tToggle Control Lockout
  '~'\tToggle Threshold Shift 

 USB
   m\tToggle HID Mouse / Kbd messages
   D\tCycle through trackpad debug modes (Off, L Pad, R Pad)

 TRACKPAD
  u / U \tDecrease / Increase frame rate
  i\tToggle trackpad clipping
  $ Turn off Rushmore freq hoppin (sets noise threshold to 0)
  o / O \tDecrease / increase centroid threshold
  / / ?\tDecrease / increase hysteresis
  a\tCalibrate trackpads
  A\tDisplay trackpad calibration (Not implemented)

 RUSHMORE CAPSENSE
  n / N\t Decrease / increase Rushmore touch threshold
  o / O\t Decrease / increase Rushmore no touch threshold
  y / Y\t Decrease / increase Rushmroe noise floor (for centroid)
  s / S\tDecrease / increase Rushmore noise threshold
  M\t Dump Rushmore trackpad calibration data
  ! / @\tDecrease / increase EF index left
  ^ / %%\tDecrease / increase EF index right
  $\t Toggle Rushmore frequency hopping

 D21 CAPSENSE
  *\tToggle Frequency Hopping mode

 HAPTICS
  f\tEnable haptics
  F\tSwitch haptics Left / Right
  w/W\tDecrease / increase haptic frequency
  e/E\tIncrement haptics repeat count
  z/Z\tDecrement / increment duty cycle percent
  E\tIncrement haptics loop interval
  L\tStop all haptics
  0\tStop all haptics
  &\tChange UI-type haptic intensity
  [ / ]\tDecrease / increase DAC haptic gain (dB)

 IMU
  g\tIncrement IMU mode
  G\tRun IMU calibration (Bosch Only)

 JOYSTICK
  j\tThumbstick:  Raw mode toggle
  J\tThumbstick:  Calibration (3 steps)
  ^j\tThumbstick: Cancel calibration
  < / >\tThumbstick touch threshold up / down

 TRIGGER
  t\tTrigger: Raw mode toggle
  T\tTrigger: Calibration (3 steps)
  ^t\tTrigger: Cancel calibration
  k / K\tTrigger:Decrease / increase threshold
 
 PRESSURE
  p\tPressure: Raw mode toggle
  P\tPressure: Calibration (3 steps)
  ^p\tPressure: Cancel calibration

 SYSTEM
  d\tSelect connected controllers (current limit 2)
  v\tToggle device type filter
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
    global mouse_kbd_on

# Thumbstick Threshold
    if event.char == '<':
        ui_root.thumbstick_touch_threshold -= 1
        if ui_root.thumbstick_touch_threshold < 10:
            ui_root.thumbstick_touch_threshold = 10
        cntrlr_mgr.set_setting(77, ui_root.thumbstick_touch_threshold )

    elif event.char == '>':
        ui_root.thumbstick_touch_threshold += 1
        if ui_root.thumbstick_touch_threshold > 40:
            ui_root.thumbstick_touch_threshold = 40
        cntrlr_mgr.set_setting(77, ui_root.thumbstick_touch_threshold )

# Logging
    elif event.char == 'l':
        ui_root.set_logging_state(not ui_root.get_logging_state())

    elif event.char == 'c':
        ui_root.log_compression = not ui_root.log_compression

# System
    elif event.char == 'd':
        cntrlr_mgr.set_device_number(get_next_device_number())

    elif event.char == 'v':
        set_next_ep()
        cntrlr_mgr.set_endpoint_list(get_current_ep_list())

# Control Lockout
    elif event.char == '`':
        ui_root.control_lockout = not ui_root.control_lockout
        cntrlr_mgr.set_control_lockouts(ui_root.control_lockout)
        ui_root.test_control = cntrlr_mgr.get_test_control()

# Trackpad Threshold shift control (automatic)
    elif event.char == '~':
        ui_root.trackpad_threshold_shift = not ui_root.trackpad_threshold_shift
        cntrlr_mgr.set_touch_threshold_shift(ui_root.trackpad_threshold_shift)
        ui_root.test_control = cntrlr_mgr.get_test_control()

# Haptic change of volume on touch (Duck when no touch)
    elif event.char == '=':
        filter = cntrlr_mgr.get_trackpad_filter_control()
        filter = not filter
        if filter:
            logger.info('filter on')
        else:
            logger.info('filter off')
        cntrlr_mgr.set_trackpad_filter_control(filter)

        #ui_root.trackpad_threshold_shift = not ui_root.trackpad_threshold_shift

        #cntrlr_mgr.set_haptic_touch_duck(ui_root.trackpad_threshold_shift)
        #ui_root.test_control = cntrlr_mgr.get_test_control()

# Debug
    elif event.char == 'D':
        ui_root.raw_trackpad_mode += 1
        if ui_root.raw_trackpad_mode > 2:
            ui_root.raw_trackpad_mode = 0
        cntrlr_mgr.trackpad_set_raw_data_mode(ui_root.raw_trackpad_mode)

# Trackpad Calibration
    elif event.char == 'a':
        if not debug_mode: 
            logger.info("Not allowed if not in DEBUG mode (^d)");
            return
        cntrlr_mgr.capsense_calibrate(0, 0)
        cntrlr_mgr.capsense_calibrate(1, 0)

    elif event.char == 'A':
    	logger.info(cntrlr_mgr.capsense_get_all_thumbstick_FSC_cc_vals())

# Haptic
    elif event.char == 'f':
        ui_root.set_ticking_state(not ui_root.get_ticking_state())
    elif event.char == 'F':
        side = ui_root.get_tick_side() + 1
        if side > 3:
            side = 0
   
        ui_root.set_tick_side(side)

    elif event.char == 'w':
        ui_root.haptic_freq -= 1
        if ui_root.haptic_freq < 50: 
            ui_root.haptic_freq = 50
    elif event.char == 'W':
        ui_root.haptic_freq += 1
        if ui_root.haptic_freq > 1000:
            ui_root.haptic_freq = 1000

    elif event.char == 'z':
        ui_root.haptic_duty_percent -= 5
        if ui_root.haptic_duty_percent < 0: 
            ui_root.haptic_duty_percent = 0

    elif event.char == 'Z':
        ui_root.haptic_duty_percent += 5
        if ui_root.haptic_duty_percent > 100:
            ui_root.haptic_duty_percent = 100

    elif event.char == 'e':
        ui_root.increment_tick_repeat()
    elif event.char == 'E':
        ui_root.increment_tick_interval()

     
# System Framerate
        
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
    elif event.char == 'M':       
       cal =  cntrlr_mgr.rushmore_get_factory_cal(0)
       logger.info('Factory Cal' + os.linesep + cntrlr_mgr.rushmore_cal_to_str(cal))

       cal =  cntrlr_mgr.rushmore_get_factory_cal(1)
       logger.info('Factory Cal' + os.linesep + cntrlr_mgr.rushmore_cal_to_str(cal))
       
       cal = cntrlr_mgr.rushmore_get_current_cal(0)
       logger.info('Current Cal' + os.linesep + cntrlr_mgr.rushmore_cal_to_str(cal))
       
       cal = cntrlr_mgr.rushmore_get_current_cal(1)
       logger.info('Current Cal' + os.linesep + cntrlr_mgr.rushmore_cal_to_str(cal))

    elif event.char == '0':
        cntrlr_mgr.haptic_off(2)
    
    elif event.char == '1':
        cntrlr_mgr.haptic_tick(2, 1, 0)

    elif event.char == '2':
        cntrlr_mgr.haptic_tick(2, 2, 0)

    elif event.char == '3':
        cntrlr_mgr.haptic_tick(2, 3, 0)

        #global haptic_ri
        #haptic_ri += 1
        #if haptic_ri > 16:
        #    haptic_ri = 4
        #logger.info("Haptic ri to " + str(haptic_ri))

        #cntrlr_mgr.haptic_noise(1, haptic_ri, -3, 10000)
    
    elif event.char == '4':
        cntrlr_mgr.haptic_tick(2, 4, 0)
    
    elif event.keycode == 49:
        cntrlr_mgr.haptic_click(2, 1, 0);
    elif event.keycode == 50:
        cntrlr_mgr.haptic_click(2, 2, 0);
    elif event.keycode == 51:
        cntrlr_mgr.haptic_click(2, 3, 0);
    elif event.keycode == 52:
        cntrlr_mgr.haptic_click(2, 4, 0);

    elif event.char == '5':
        tone1_len = 250
        cntrlr_mgr.haptic_tone(2, 0, ui_root.haptic_freq, int( tone1_len))        
        logger.info('FREQ: ' + str(ui_root.haptic_freq))

        ui_root.haptic_freq *= semi_tone
        ui_root.haptic_freq = int(ui_root.haptic_freq)

        if (ui_root.haptic_freq > 2000 ):
            ui_root.haptic_freq = 50    

    elif event.char == '6':
        intensity = 32000
        freql = freqr = 10000
        cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)
        sleep(0.4)
        cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)
        sleep(0.4)
        cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)
        sleep(0.4)
        cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)   
        
    elif event.char == '7':
        intensity = 1000
        freql = freqr = 10000

        cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)
        sleep(0.4)
        cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)
        sleep(0.4)
        cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)
        sleep(0.4)
        cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)

    elif event.char == '8':
        global haptic_intenisty, haptic_intensity_idx
        intensity = haptic_intenisty[haptic_intensity_idx]
        logger.info("Haptic Intensity: {}".format(haptic_intenisty[haptic_intensity_idx]))

        haptic_intensity_idx += 1
        if haptic_intensity_idx > 7:
            haptic_intensity_idx = 0
        freql = freqr = 20000
        for i in range(5):
            cntrlr_mgr.haptic_simple_rumble(0, intensity, freql, freqr)
            sleep(0.4)
    
    elif event.char == '9':
        cntrlr_mgr.haptic_script( 2, 1, 0)

    elif event.keycode == 112:  # F1
        logger.info(cntrlr_mgr.imu_selftest())
    
    elif event.keycode == 113:
        global deadzone_on
        deadzone_on = 1 - deadzone_on
        if deadzone_on:
            cntrlr_mgr.set_stick_deadzone(4000)
        else:
            cntrlr_mgr.set_stick_deadzone(0)

    elif event.keycode == 114:
        logger.info(cntrlr_mgr.get_device_info(1))


    elif event.char == ';':
#       cntrlr_mgr.set_stick_deadzone(2000)
#        logger.info(cntrlr_mgr.get_stick_deadzone())
#       logger.info(cntrlr_mgr.user_data_get())
        #cntrlr_mgr.haptic_tick(2, 2, 0)
#        cntrlr_mgr.haptic_enable(1);
#        cntrlr_mgr.haptic_cmd(0, 2, 2, 0 )
  
       logger.info(cntrlr_mgr.imu_get_type())
       logger.info(cntrlr_mgr.imu_get_cal())
   #     cntrlr_mgr.trackpad_set_raw_data_mode(0x4)
#        logger.info(cntrlr_mgr.get_raw_trackpad_data())



    elif event.char == '/':
        cntrlr_mgr.imu_set_type(0)

    elif event.char == ':':
        cntrlr_mgr.user_data_set(0x01, 0) # Version 0x01
        #cntrlr_mgr.haptic_enable(0);
        #cntrlr_mgr.imu_set_type(1)
#       cntrlr_mgr.trigger_set_cal( 1, 1234, 587, 0 );
#       cntrlr_mgr.pressure_set_cal( 1, 199, 1, 1000, 0x00 )
#        cntrlr_mgr.thumbstick_set_cal( 0, 111, 222, 333, 114, 55, 665, 777, 888 )
      # cntrlr_mgr.trigger_set_cal( 1, 433, 136, 1 );

    elif event.char == '"':
 #       cntrlr_mgr.persist_cal(0, 0x17)
 #       cntrlr_mgr.persist_cal(1, 0x17)
#        cntrlr_mgr.persist_cal( 1, 0x04 )  #Persist Pressure
#       cntrlr_mgr.persist_cal( 0, 0x02 )  #Persist Thumbstick
#      cntrlr_mgr.persist_cal( 1, 0x01 )  #Persist Trigger
#       cntrlr_mgr.persist_cal( 1, 0x10 )  #Persist IMU
       cntrlr_mgr.persist_cal( 1, 0x20 )  #Persist USER

    elif event.char == '\\':
        cntrlr_mgr.imu_set_cal( 1, 2, 3, 4, 5, 6)

    elif event.char == '{':
        cntrlr_mgr.user_data_set(0x01, 1)

    elif event.char == '}':
        cntrlr_mgr.user_data_set(0x01, 2)

    elif event.char == '&':
        ui_root.haptic_ui_intensity += 1
        if ui_root.haptic_ui_intensity > 4:
            ui_root.haptic_ui_intensity = 1
        cntrlr_mgr.set_setting(79, ui_root.haptic_ui_intensity)

# Touch Threshold (Rushmore)
    elif event.char == 'n':
        ui_root.rushmore_touch_threshold -= 10
        if ui_root.rushmore_touch_threshold < 0:
            ui_root.rushmore_touch_threshold = 0
        cntrlr_mgr.set_setting(19, ui_root.rushmore_touch_threshold)

    elif event.char == 'N':
        ui_root.rushmore_touch_threshold += 10
        if ui_root.rushmore_touch_threshold > 4000:
            ui_root.rushmore_touch_threshold = 4000
        cntrlr_mgr.set_setting(19, ui_root.rushmore_touch_threshold)# Rushmore Static Freq

# NO Touch Threshold (Rushmore)
    elif event.char == 'o':
        ui_root.rushmore_notouch_threshold -= 10
        if ui_root.rushmore_notouch_threshold < 0:
            ui_root.rushmore_notouch_threshold = 0
        cntrlr_mgr.set_setting(20, ui_root.rushmore_notouch_threshold)

    elif event.char == 'O':
        ui_root.rushmore_notouch_threshold += 10
        if ui_root.rushmore_notouch_threshold > 4000:
            ui_root.rushmore_notouch_threshold = 4000
        cntrlr_mgr.set_setting(20, ui_root.rushmore_notouch_threshold)# Rushmore Static Freq

# Rushmore Noise Floor
    elif event.char == 'y':
        ui_root.rushmore_noise_floor = ui_root.rushmore_noise_floor - 5
        if (ui_root.rushmore_noise_floor < 0):
            ui_root.rushmore_noise_floor = 0
        cntrlr_mgr.set_setting(63, ui_root.rushmore_noise_floor )

    elif event.char == 'Y':
        ui_root.rushmore_noise_floor = ui_root.rushmore_noise_floor + 5
        if (ui_root.rushmore_noise_floor > 300):
            ui_root.rushmore_noise_floor = 300
        cntrlr_mgr.set_setting(63, ui_root.rushmore_noise_floor )

    elif event.char == '!':
        ui_root.rushmore_l_ef_index = ui_root.rushmore_l_ef_index - 1
        if ui_root.rushmore_l_ef_index < 0:
            ui_root.rushmore_l_ef_index = 1
        cntrlr_mgr.set_setting(72, ui_root.rushmore_l_ef_index)
    
    elif event.char == '@':
        ui_root.rushmore_l_ef_index = ui_root.rushmore_l_ef_index + 1
        if ui_root.rushmore_l_ef_index > 1:
            ui_root.rushmore_l_ef_index = 0
        cntrlr_mgr.set_setting(72, ui_root.rushmore_l_ef_index)

    elif event.char == '^':
        ui_root.rushmore_r_ef_index = ui_root.rushmore_r_ef_index - 1
        if ui_root.rushmore_r_ef_index < 0:
            ui_root.rushmore_r_ef_index = 1
        cntrlr_mgr.set_setting(73, ui_root.rushmore_r_ef_index)
    
    elif event.char == '%':
        ui_root.rushmore_r_ef_index = ui_root.rushmore_r_ef_index + 1
        if ui_root.rushmore_r_ef_index > 1:
            ui_root.rushmore_r_ef_index = 0
        cntrlr_mgr.set_setting(73, ui_root.rushmore_r_ef_index)

    elif event.char == '$':
        ui_root.rushmore_freq_hopping = 1 - ui_root.rushmore_freq_hopping
        cntrlr_mgr.set_setting(69, ui_root.rushmore_freq_hopping)


# Trackpad Noise Threshold
    elif event.char == 's':
        ui_root.rushmore_noise_threshold -= 5
        if ui_root.rushmore_noise_threshold < 0:
            ui_root.rushmore_noise_threshold = 0
        cntrlr_mgr.rushmore_set_noise_threshold(ui_root.rushmore_noise_threshold)

    elif event.char == 'S':
        ui_root.rushmore_noise_threshold +=  5
        if ui_root.rushmore_noise_threshold > 400:
            ui_root.rushmroe_noise_threshold = 400
        cntrlr_mgr.rushmore_set_noise_threshold(ui_root.rushmore_noise_threshold)

    
    elif event.char == '|':
        zoom = ui_root.get_trackpad_zoom()
        if zoom == 1:
            ui_root.set_trackpad_zoom( 2 )
        else:
            ui_root.set_trackpad_zoom( 1 )

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
        if ui_root.thumbstick_raw_mode:
            cntrlr_mgr.set_stick_deadzone(0)
            ui_root.set_thumbstick_zoom(16)
            ui_root.set_thumbstick_offset(-2048)
        else:
            cntrlr_mgr.set_stick_deadzone(4000)
            ui_root.set_thumbstick_zoom(1)
            ui_root.set_thumbstick_offset(0)


    elif event.char == 'J':
        if not debug_mode: 
            return
        step = ui_root.get_thumbstick_cal_current_step() + 1

        logger.info('Thumbstick cal step: {}'.format(step) )
        cntrlr_mgr.thumbstick_cal_step(step)

        if step >= 3:
            step = 0
        ui_root.set_thumbstick_cal_current_step(step)

# Debug display mode control
    elif event.char == '_':
        mode = ui_root.debug_display_mode + 1
        if (mode > 5):
            mode = 0
        logger.info('Debug Mode set to: {}'.format(mode))
        ui_root.debug_display_mode = mode
        cntrlr_mgr.set_setting(67, mode)

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
        mouse_kbd_on = not mouse_kbd_on
        cntrlr_mgr.mouse_kbd_control(mouse_kbd_on)

# Toggle trackpad clipper
    elif event.char == 'i':
        ui_root.trackpad_clipping = 1 - ui_root.trackpad_clipping
        cntrlr_mgr.set_setting(66, ui_root.trackpad_clipping)

# Toggle trackpad filter
    elif event.char == 'I':
        ui_root.trackpad_filt = 1 - ui_root.trackpad_filt
        cntrlr_mgr.set_setting(65, ui_root.trackpad_filt)

# Dump all calibration
    elif event.char == 'C':
        logger.info('IMU Type:         ' + str(cntrlr_mgr.imu_get_type()))
        logger.info('IMU Cal:          ' + str(cntrlr_mgr.imu_get_full_cal()))

        logger.info('Pressure L Cal:   ' + str(cntrlr_mgr.pressure_get_cal(0)))
        logger.info('Pressure R Cal:   ' + str(cntrlr_mgr.pressure_get_cal(1)))

        logger.info('Thumbstick L Cal: ' + str(cntrlr_mgr.thumbstick_get_cal(0)))
        logger.info('Thumbstick R Cal: ' + str(cntrlr_mgr.thumbstick_get_cal(1)))

        logger.info('Trigger L Cal:    ' + str(cntrlr_mgr.trigger_get_cal(0)))
        logger.info('Trigger R Cal:    ' + str(cntrlr_mgr.trigger_get_cal(1)))

    elif event.char == 'x':
        logger.info(cntrlr_mgr.imu_get_temp())

    elif event.char == 'X':
        status = cntrlr_mgr.get_system_status()
        if not status:
            return

        secondary_status, imu_type, rushmore_fail, imu_fail, sensor_cal_fail = cntrlr_mgr.get_system_status()
        logger.info('Secondary Status:     '    + str(secondary_status) )
        logger.info('IMU Type:             '    + str(imu_type) )
        logger.info('Rushmore Failure:     '    + str(rushmore_fail) )
        logger.info('IMU Failure:          '    + str(imu_fail) )
        logger.info('Sensor Cal Failure:   0x{:02X}'.format(sensor_cal_fail))
    
    elif event.char == '[':
        ui_root.haptic_gain -= 1
        if ui_root.haptic_gain < -24:
            ui_root.haptic_gain = -24
        cntrlr_mgr.set_setting(76, ui_root.haptic_gain)

    elif event.char == ']':
        ui_root.haptic_gain += 1
        if ui_root.haptic_gain > 6:
            ui_root.haptic_gain = 6
        cntrlr_mgr.set_setting(76, ui_root.haptic_gain)

    elif event.keycode == 114: #F3 
        logger.info(cntrlr_mgr.imu_get_full_cal())

    else:
        logger.info('Got keycode: ' + str(event.keycode))

##########################################################################################################
## BEGIN HELPER METHODS
##########################################################################################################
def thumbstick_cancel_cal_cb(event):
    global thumbstick_cal_current_step
    thumbstick_cal_current_step = 0
    cntrlr_mgr.thumbstick_cancel_cal()
    ui_root.set_thumbstick_cal_current_step(thumbstick_cal_current_step)
    logger.info("Thumbstick cal canceled")

def pressure_cancel_cal_cb(event):
    global pressure_cal_current_step
    pressure_cal_current_step = 0
    cntrlr_mgr.pressure_cancel_cal()	
    ui_root.set_pressure_cal_current_step(pressure_cal_current_step)
    logger.info("Pressure cal canceled")

def trigger_cancel_cal_cb(event):
    global trigger_cal_current_step
    trigger_cal_current_step = 0
    cntrlr_mgr.trigger_cancel_cal()
    ui_root.set_trigger_cal_current_step(trigger_cal_current_step)
    logger.info("Trigger cal canceled")

def toggle_debug_mode_cb(event):
    global debug_mode
    debug_mode = 1 - debug_mode
    ui_root.debug_mode = debug_mode
#    ui_root.toggle_debug_trails()  # useful for trackpad testing, but confusing for users.
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
    cntrlr_mgr.sys_steamwatchdog(0)

    # Disable Mouse mode
    cntrlr_mgr.mouse_kbd_control(mouse_kbd_on)

    # Enable status messages
    cntrlr_mgr.set_setting(49, 2)
    
    # Tell UI that a new conjnection has occured
    ui_root.connected()
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

log_file_path = os.path.expanduser('~/RTST.log')

# If the file can't be opened (permissions?) then delete it and re-open
fh = None
try:
    fh = logging.FileHandler(log_file_path)
except Exception as e:
    os.remove(log_file_path)

if fh is None:
    fh=logging.FileHandler(log_file_path)

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


haptic_channel = 0
tmp_tone = 10
tmp_delta = 1
haptic_ri = 4
##########################################################################################################
## UI SETUP
##########################################################################################################
root = Tk.Tk()
truncated_version = __version__[12:-1]
root.wm_title("Jupiter Real-Time Status Tool - vB" + truncated_version)
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

logger.info("Exiting")
cntrlr_mgr.mouse_kbd_control(1)
cntrlr_mgr.sys_steamwatchdog(1)

cntrlr_mgr.shutdown()
