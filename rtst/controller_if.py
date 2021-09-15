import hid
import struct
import logging
import math
import os
from time import sleep

logger = logging.getLogger('RTST.CNTRLR')

from hid_dev_mgr import HidDeviceManager
from valve_message_handler import ValveMessageHandler

class ControllerInterface:

    SIDE_LEFT = 0
    SIDE_RIGHT =1
    ## Requires a vid_pid pairs list, and an optional Callback on conneciton
    def __init__(self, vid_pid_endpoint_list, connect_cb ):
        self.logger = logging.getLogger('RTST.CNTRLR')
        self.hid_dev_mgr =  HidDeviceManager(vid_pid_endpoint_list, connect_cb, ValveMessageHandler())
    
    ##########################################################################################################
    ## System Utility Commands
    ##########################################################################################################
    # Controller connected?
    def is_open(self):
        if self.hid_dev_mgr.is_open():
            return True
        else:
            return False

    # Get curretn VID / PID
    def get_hid_vid_pid(self):
        return (self.hid_dev_mgr.device_vendor_id, self.hid_dev_mgr.device_product_id);

    # Get the current data set from last Input Report
    def get_data(self):
        return self.hid_dev_mgr.get_data()

    # Clear the stored data set
    def clear_data(self):
        return self.hid_dev_mgr.clear_data()

    def restart(self):
        return self.hid_dev_mgr.restart()
    
    def shutdown(self):
        return self.hid_dev_mgr.shutdown()

    # if more than 1 device of matching VID / PID is attached, switch devices.
    def set_device_number(self, device_number):
        self.hid_dev_mgr.dev_num = device_number
        self.hid_dev_mgr.restart()

    # Switch the HID manager's enpoint point list
    def set_endpoint_list(self, endpoint_list):
        self.hid_dev_mgr.vid_pid_endpoint_list = endpoint_list
        self.hid_dev_mgr.restart()

    # Send Reboot commands to controller reboot_type(0 = application,  1 = Bootloader)
    def reboot_controller(self, reboot_type):
        if not self.hid_dev_mgr.is_open():
            return False
        report_bytes = struct.pack('')
        
        if (reboot_type == 1):
            self.hid_dev_mgr.send_feature_report(0x90, report_bytes)     
        elif (reboot_type == 0):
            self.hid_dev_mgr.send_feature_report(0x95, report_bytes)

    # Enable / Disable HID mouse / kbd USB reports
    def mouse_kbd_control(self, on):
        self.set_setting(9, on)

    # Enable / disable control lockouts
    def set_control_lockouts(self, on):
        self.set_setting(75, on)

    # Set the system framerate
    def sys_set_framerate(self, framerate):
         self.set_setting(64, framerate)

    # Enable / Disable Steam Watchdog (Will reset default settings after 10s if no Steam)
    def sys_steamwatchdog(self, on):
        self.set_setting(71, on)

    # WDT Stuff (Not supported -- DO NOT USE)
    def test_nrf_watchdog(self):
        feature_report_type = 0xd4
        report_bytes = struct.pack('')
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    ##########################################################################################################
    ## Get Timestamp
    ##########################################################################################################
    def get_last_packet_num (self):
        data = self.get_data()
        return ( data.get('last_packet_num'))

    ##########################################################################################################
    ## Haptic 
    ##########################################################################################################		
    # Haptic side translation

    # Haptic Pulse - Generate a legacy haptic pulse train
    def haptic_pulse(self, side, on_us=1000, off_us=100, repeat_count=0, dBgain=0):
        if self.hid_dev_mgr.is_open():
            feature_report_type = 143

            if side > 2:
                return

            if side == 0:
                side = 1
            elif side == 1:
                side = 0


            report_bytes = struct.pack('=BHHHh', side, on_us, off_us, repeat_count, dBgain)
            self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    # Stop all Haptic output
    def haptic_stop_all(self):
        self.haptic_pulse(0, 0, 0, 0, 0)
        self.haptic_pulse(1, 0, 0, 0, 0 )

    
    # Haptic enabnle: 0 = Off, 1 = On, 2 = Only via USB API
    def haptic_enable(self, enable ):
        self.set_setting( 70, enable)
    
    # New Haptic ControllerInterface
    def haptic_off(self, side):
        if self.hid_dev_mgr.is_open():
            feature_report_type = 0xEA

            report_bytes = struct.pack('=BB', side, 0)
            self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def haptic_cmd(self, side, cmd, intensity, gain):
        if self.hid_dev_mgr.is_open():
            feature_report_type = 0xEA

            report_bytes = struct.pack('=BBBb', side, cmd, intensity, gain)
            self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)
    
    def haptic_tone(self, side, gain, freq, dur_ms):
        if self.hid_dev_mgr.is_open():
            feature_report_type = 0xEA

            report_bytes = struct.pack('=3BbHhH', side, 3, 0, gain, freq, dur_ms, 0)
            self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)            
    
    def haptic_rumble(self, side, rumble_intensity, gain, dur_ms):
        if self.hid_dev_mgr.is_open():
            feature_report_type = 0xEA

            report_bytes = struct.pack('=3BbHhH', side, 4, 0, gain, 0, dur_ms, rumble_intensity)
            self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)            


    ##########################################################################################################
    ## Capsense (Trackpad, FSC/ Thumbstick 
    ##   This returns 2x 16-bit valuse.  
    ##   1 Thumbstick Touch
    ##   2 FSC Sensor
    ##########################################################################################################
    # Get compensation capacitance values for D21 sensors on a side 
    def capsense_get_cc_vals(self, side):
        op = 0xE3
        # left = 0, right = 1
        report_bytes = struct.pack('=2B', side, 0)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
        # Retrieve and parse the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()

        if not report_length or report_type != op:
                return None

        side, valid = struct.unpack('=2B', report_bytes[0:2])
        cc_vals = struct.unpack('=2H', report_bytes[2:])

        return valid, cc_vals

    # Run a re-calibration (side = L/R, type = 0/trackpad 1/thumbstick & FSC
    def capsense_calibrate(self, side, type):
        feature_report_type = 0xa7
        report_bytes = struct.pack('=2H', side, type)
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    # Get Thumbstick and FSC
    def capsense_get_all_thumbstick_FSC_cc_vals(self):
        valid0, cc_vals_0 = self.capsense_get_cc_vals(self.SIDE_LEFT)
        valid1, cc_vals_1 = self.capsense_get_cc_vals(self.SIDE_RIGHT)
        if not valid0 or not valid1:
            return ()
        return (cc_vals_0, cc_vals_1)

    # Capsense Calibrate FSC Thumb
    def capsense_calibrate_fsc_thumb(self, side):
        self.capsense_calibrate(side, 1) 

    # Capsense Calibrate Trackpad
    def capsense_calibrate_trackpad(self, side):
        self.capsense_calibrate(side, 0) 
        
    ##########################################################################################################
    ## Trackpad 
    ##########################################################################################################
    # Trackpad Noise Threshold for frequency hopping
    def rushmore_set_noise_threshold(self, threshold):
        self.set_setting(51, threshold)

    def rushmore_get_noise_threshold(self):
        return (self.get_setting(51))

    # Trackpad hysteresis for touch detection
    def trackpad_set_hysteresis(self, hyst):
        self.set_setting(69, hyst)

    # Trackpad data debug mode 0x00 = OFF, 0x01 side L, 0x02 = side R
    # 0x04 Side L ref, 0x08 Side R ref
    def trackpad_set_raw_data_mode(self, mode):
        self.set_setting(6, mode)

    # Trackpad Truncation cal
    def trackpad_get_cal(self, side):
        op = 0xDB
        # left = 0, right = 1
        report_bytes = struct.pack('B', side)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
        # Retrieve and parse the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()

        if not report_length or report_type != op:
                return None

        (side, threshold, x_min, x_max, y_min, y_max) = struct.unpack('=Bb4H', report_bytes)
        return side, threshold, x_min, x_max, y_min, y_max

    def trackpad_set_cal(self, side, threshold, x_min, x_max, y_min, y_max):
        op = 0xDC
        report_bytes = struct.pack('=Bb4H', side, threshold, x_min, x_max, y_min, y_max)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
       
    def rushmore_get_current_cal( self, side ):
        op = 0xAA
        fulldata = []
        for rowset in range (0, 4):
            report_bytes = struct.pack('2B', side, rowset)
            self.hid_dev_mgr.send_feature_report(op, report_bytes)

            # Retrieve and parse the result.
            report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()

            if not report_length or report_type != op:
                return None

            (reported_side, rowset) = struct.unpack('=2B', report_bytes[0:2])
            rowdata = struct.unpack('=16H', report_bytes[2:])
            fulldata += rowdata
       
        # Returned data is complete backwards and transposed. 
        fulldata = fulldata[::-1] 
        fulldata = self.transpose( fulldata, 8 )
        return reported_side, fulldata

    def transpose( self, list, rank ):
        out = [None] * (rank * rank)
        for row in range(0, rank):
            for col in range(0, rank):
                index = col * rank + row
                out[index] = list[row * rank + col]
        return out

    def rushmore_get_factory_cal( self, side ):
        op = 0xAB
        fulldata = []
        for rowset in range (0, 4):
            report_bytes = struct.pack('2B', side, rowset)
            self.hid_dev_mgr.send_feature_report(op, report_bytes)

            # Retrieve and parse the result.
            report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()

            if not report_length or report_type != op:
                return None

            (reported_side, rowset) = struct.unpack('=2B', report_bytes[0:2])
            rowdata = struct.unpack('=16H', report_bytes[2:])
            fulldata += rowdata
        # Returned data is complete backwards and transposed. 
        fulldata = fulldata[::-1] 
        fulldata = self.transpose( fulldata, 8 )
        return reported_side, fulldata

    def rushmore_cal_to_str( self, cal):
      #  if cal[0] == 255:
      #      return 'Uncalibrated'

        big_str='Side: {}'.format(cal[0]) + os.linesep
        cal = cal[1]            # remove the 'side' element of the tuple

        for row in range(0, 8):
            start = row * 8
            row_str = ''.join(str(cal[start:start+8])) + ',' + os.linesep
            big_str = big_str + row_str
        return big_str

    def rushmore_get_z_values(self):
        self.set_debug_output_mode(1)
        data = self.get_data()
        return ( data.get('left_debug'), data.get('right_debug')) 

    ##########################################################################################################
    ## IMU 
    ##########################################################################################################
    def set_imu_mode(self, mode):
        self.set_setting(48, mode)

    # IMU Calibration
    def imu_calibrate(self):
        feature_report_type = 0xb5
        report_bytes = struct.pack('')
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    # IMU Self trest results (usually takes 0.5 - 1s to stabilize) Reselts below. Unknown until self test is triggered
    #	SELF_TEST_RESULT_PASS_ACC	= 0x0001
    #	SELF_TEST_RESULT_PASS_GYRO	= 0x0002
    #	SELF_TEST_RESULT_PENDING	= 0x0100,
    #	SELF_TEST_RESULT_UNKNOWN	= 0x8000,
    def imu_get_selftest_results(self):
        op = 0xE4
        report_bytes = struct.pack('')

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
        # Retrieve and parse the result.
        report_type, report_length, report_bytes =  self.hid_dev_mgr.get_feature_report()
        if not report_length or report_type != op:
            return None

        result = struct.unpack('=H', report_bytes)[0]
        return result

    # IMU Selftest
    #  Trigger an IMU self test.  This takes a few hundred ms.
    def imu_selftest(self):
        feature_report_type = 0xe8
        report_bytes = struct.pack('')
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

        sleep(2)
        return self.imu_get_selftest_results()

    # IMU Get temp
    def imu_get_temp(self):
        # Ensure that we're running first in 'normal' mode.
        self.set_imu_mode(1)
        self.set_setting(67, 5)  # Set to IMU temp mode
        sleep(0.02)
        data = self.get_data()
        return (data.get('right_debug'))

    def imu_get_full_cal(self):
        op = 0xE6
        report_bytes = struct.pack('')

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
        # Retrieve and parse the result.
        report_type, report_length, report_bytes =  self.hid_dev_mgr.get_feature_report()

        if not report_length or report_type != op:
            return None

        (side, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, imu_type) = struct.unpack('=B3b3hb', report_bytes)
        return side, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, imu_type
    
    def imu_get_cal(self):
        (side, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, _) = self.imu_get_full_cal()
        return side, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z

    def imu_set_full_cal(self, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, imu_type):
        op = 0xE7
        report_bytes = struct.pack('=4b3hb', 1, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, imu_type)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)     

    def imu_set_cal(self, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z):
        (_, _, _, _, _, _, imu_type) = self.imu_get_full_cal()
        self.imu_set_full_cal (acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, imu_type)

    def imu_get_type(self):
        (_, _, _, _, _, _, _, imu_type) = self.imu_get_full_cal()
        return imu_type, 'Invensense' if imu_type ==1 else 'Bosch'

    def imu_set_type(self, imu_type):
        (_, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, _) = self.imu_get_full_cal()
        self.imu_set_full_cal (acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z, imu_type)

    ##########################################################################################################
    ## Thumbstick 
    ##########################################################################################################
    def thumbstick_set_raw(self, on):
        self.set_setting(0x2E, on)

    # Thumbstick Calibration
    def thumbstick_cancel_cal(self):
        feature_report_type = 0xd8
        report_bytes = struct.pack('BB', 0, 0)
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def thumbstick_cal_step(self, step):
        feature_report_type = 0xd8
        report_bytes = struct.pack('BB', 0, step)
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def thumbstick_get_cal(self, side):
        op = 0xD9
        # left = 0, right = 1
        report_bytes = struct.pack('B', side)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
        # Retrieve and parse the result.
        report_type, report_length, report_bytes =  self.hid_dev_mgr.get_feature_report()

        if not report_length or report_type != op:
            return None

        (side, x_full_min, x_full_max, x_center_min, x_center_max, y_full_min, y_full_max, y_center_min, y_center_max) = struct.unpack('=B8H', report_bytes)
        return side, x_center_min, x_center_max, x_full_min, x_full_max, y_center_min, y_center_max, y_full_min, y_full_max

    def thumbstick_set_cal(self, side, x_center_min, x_center_max, x_full_min, x_full_max, y_center_min, y_center_max, y_full_min, y_full_max):
        op = 0xDA
        report_bytes = struct.pack('=B8H', side, x_full_min, x_full_max, x_center_min, x_center_max, y_full_min, y_full_max, y_center_min, y_center_max)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)

    ##########################################################################################################
    ## Trigger 
    ##########################################################################################################
    def trigger_set_raw(self, on):
        self.set_setting(62, on)

    # Trigger Calibration
    
    def trigger_cancel_cal(self):
        feature_report_type = 0xC0
        report_bytes = struct.pack('B', 0)
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def trigger_cal_step(self, step):
        feature_report_type = 0xc0
        report_bytes = struct.pack('B', step)
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def trigger_get_cal(self, side):
        op = 0xDE
        report_bytes = struct.pack('B', side)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
        # Retrieve and parse the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()

        if not report_length or report_type != op:
                return None

        (side, max, min, neg) = struct.unpack('=B2HB', report_bytes)
        return side, max, min, neg

    def trigger_set_cal(self, side, max, min, negative_range):
        op = 0xDF
        report_bytes = struct.pack('=B2HB', side, max, min, negative_range)
        self.hid_dev_mgr.send_feature_report(op, report_bytes)

    ##########################################################################################################
    ## Pressure 
    ##########################################################################################################
    def pressure_set_raw(self, on):
        self.set_setting(60, on)

    # Pressure Calibration
    def pressure_cancel_cal(self):
        feature_report_type = 0xC3
        report_bytes = struct.pack('B', 0)
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def pressure_cal_step(self, step):
        feature_report_type = 0xC3
        report_bytes = struct.pack('B', step)
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def pressure_get_cal(self, side):
        op = 0xE0
        # left = 0, right = 1
        report_bytes = struct.pack('B', side)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
        # Retrieve and parse the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()

        if not report_length or report_type != op:
                return None

        (side, min, max, grams) = struct.unpack('=B3H', report_bytes)
#        self.logger.info('Pressure Cal Side: {}, MAX: {}, MIN: {}, CAL_WT: {}'.format(side, max, min, grams))
        return side, max, min, grams
        
    def pressure_set_cal(self, side, max, min, grams):
        op = 0xE1
        # left = 0, right = 1
        report_bytes = struct.pack('=1B3H', side, min, max, grams)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)

    def pressure_get_pressure_threshold(self, side):
        return self.get_setting(52 + side)

    ##########################################################################################################
    ## Persist calibration (bitmask per below) / side = 0=L, 1=R
    #		BITMASK_PERSIST_TRIGGER		0x01
    #		BITMASK_PERSIST_JOYSTICK	0x02
    #		BITMASK_PERSIST_PRESSURE	0x04
    #		BITMASK_PERSIST_TRACKPAD	0x08
    #		BITMASK_PERSIST_IMU			0x10
    ##########################################################################################################
    def persist_cal(self, side, bitmask):
        op = 0xE2
        report_bytes = struct.pack('=2B', side, bitmask)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)

    ##########################################################################################################
    # Controller Settings routines
    ##########################################################################################################
    def set_setting(self, setting_num, setting_val):
        feature_report_type = 0x87
        feature_report_length = 3 # we're only setting one setting at a time
        report_bytes = struct.pack('=Bh', setting_num, setting_val)

        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def get_setting(self, setting_num):
        feature_report_type = 0x89
        feature_report_length = 3
        report_bytes = struct.pack('=Bh', setting_num, 0)

        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

        # Retrieve and parse the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()
        if report_type != 0x89:
            return {}

        type, data = struct.unpack('=BH', report_bytes)
        return data

    ##########################################################################################################
    ## Usage 
    ##########################################################################################################
    def clear_usage( self, side):  
        feature_report_type = 0xE9
        feature_report_length = 2
        report_bytes = struct.pack('=BB', side, 1 )

        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)
 
    def get_usage(self, side):  
        feature_report_type = 0xE9
        feature_report_length = 4
        report_bytes = struct.pack('=BB', side, 0 )

        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

        # Retrieve and parse the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()
        if report_type != feature_report_type:
            return {}

        side, _, count, bit_count = struct.unpack('=2BIH', report_bytes)
        return count, bit_count
    ##########################################################################################################
    # Controller Attributes and Mappings
    ##########################################################################################################
    def clear_mappings(self):
        self.logger.info('clear mappings')
        feature_report_type = 0x81
        report_bytes = struct.pack('')
        self.hid_dev_mgr.send_feature_report(feature_report_type, report_bytes)

    def get_attributes(self):
        if not self.hid_dev_mgr.is_open():
            return {}

        # Send the GET_ATTRIBUTES_VALUES request.
        self.hid_dev_mgr.send_feature_report(0x83, '')

        # Retrieve and parse the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()
        if report_type != 0x83:
            return {}

        # Attributes are (tag[1 byte], value[4 bytes])
        num_attrs = report_length // 5
        if not num_attrs:
            return {}

        format_str = '=' + ('BL' * num_attrs)
        data = struct.unpack(format_str, report_bytes)

        attrs = {}
        for i in range(num_attrs):
            tag = data[i * 2]
            val = data[i * 2 + 1]

            # ATTRIB_UNIQUE_ID
            if tag == 0:
                attrs['unique_id'] = val
            # ATTRIB_PRODUCT_ID
            elif tag == 1:
                attrs['product_id'] = val
            # ATTRIB_CAPABILITIES
            elif tag == 2:
                attrs['capabilities'] = val
            # ATTRIB_FIRMWARE_BUILD_TIME
            elif tag == 4:
                attrs['build_timestamp'] = val
            # ATTRIB_RADIO_FIRMWARE_BUILD_TIME
            elif tag == 5:
                attrs['radio_build_timestamp'] = val
            # ATTRIB_BOARD_REVISION AKA HW_ID
            elif tag == 9:
                attrs['hw_id'] = val
            # ATTRIB_BOOTLOADER_BUILD_TIME
            elif tag == 10:
                attrs['boot_build_timestamp'] = val
            # ATTRIB_CONNECTION_INTERVAL_IN_US
            elif tag == 11:
                attrs['frame_rate'] = int(val / 1000)
            # ATTRIB_SECONDARY_FIRMWARE_BUILD_TIME
            elif tag == 12:
                attrs['secondary_build_timestamp'] = val
            # ATTRIB_SECONDARY_BOOTLOADER_BUILD_TIME
            elif tag == 13:
                attrs['secondary_boot_build_timestamp'] = val
            # ATTRIB_SECONDARY_HW_IDs
            elif tag == 14:
                attrs['secondary_hw_id'] = val
            # ATTRIB_STREAMING
            elif tag == 15:
                attrs['data_streaming'] = val
            # ATTRIB_TRACKPAD_ID
            elif tag == 16:
                attrs['trackpad_id'] = val                      
            # ATTRIB_SECONDARY_TRACKPAD_ID
            elif tag == 17:
                attrs['secondary_trackpad_id'] = val
        return attrs

    def get_str_attribute(self, attribute_number):
        if not self.hid_dev_mgr.is_open():
            return None

        op = 0xAE

        # Send the ID_GET_STRING_ATTRIBUTE request.
        self.hid_dev_mgr.send_feature_report(op, struct.pack('=b', attribute_number))

        # Retrieve the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()

        if not report_length or report_type != op or report_bytes[0] != attribute_number:
             return None

        # Extract string and strip nulls.
        return report_bytes[1:].strip(b'\x00').decode("utf-8")

    ##########################################################################################################
    ## Info Commands
    ##########################################################################################################
    def get_device_info(self, side):
        op = 0xA1
        # left = 0, right = 1
        report_bytes = struct.pack('B', side)

        self.hid_dev_mgr.send_feature_report(op, report_bytes)
        # Retrieve and parse the result.
        report_type, report_length, report_bytes = self.hid_dev_mgr.get_feature_report()

        if not report_length or report_type != op:
            return None

        (side,  reason, uid) = struct.unpack('=2B16s', report_bytes)

        # Swizzle UID
        uid1 = uid[0:4]
        uid1 = uid1[::-1].hex().upper()

        uid2 = uid[4:8]
        uid2 = uid2[::-1].hex().upper()

        uid3 = uid[8:12]
        uid3 = uid3[::-1].hex().upper()

        uid4 = uid[12:16]
        uid4 = uid4[::-1].hex().upper()

        uid_str = uid1 + ' ' + uid2 + ' ' + uid3 + ' ' + uid4
        return (side, reason, uid_str)

    ##########################################################################################################
    ## Get Bootloader build timestamp
    ##########################################################################################################
    def get_bootloader_timestamp(self):
        device_info = self.get_attributes()
        return ( device_info.get('secondary_boot_build_timestamp'), device_info.get('boot_build_timestamp') )

    ##########################################################################################################
    ## Get Application build timestamp
    ##########################################################################################################
    def get_application_timestamp(self):
        device_info = self.get_attributes()
        return ( device_info.get('secondary_build_timestamp'), device_info.get('build_timestamp') )

    ##########################################################################################################
    ## Get Reset Reason
    ##   Returned reset reason values are decoded as such.  First is Left -- Second is Right
    ##   	RESET_REASON_POR   = 1   Power On
    ##		RESET_REASON_BOD12 = 2   Brown Out Detected 1.2V
    ##   	RESET_REASON_BOD33 = 4   Brown Out Detected 3.3V
    ##   	RESET_REASON_EXT   = 16  External Reset Pin (normal for Secondary)
    ##   	RESET_REASON_WDT   = 32  Watch Dog Timer
    ##   	RESET_REASON_SYST  = 64  System reset (I.e. SW reset)
    ##########################################################################################################
    def get_reset_reason(self):
        (_, reason_0, _) = self.get_device_info(self.SIDE_LEFT)
        (_, reason_1, _) = self.get_device_info(self.SIDE_RIGHT)
        return (reason_0, reason_1)

    ##########################################################################################################
    ## Get UID
    ##########################################################################################################
    def get_uid(self):
        (_, _, uid_0) = self.get_device_info(self.SIDE_LEFT)
        (_, _, uid_1) = self.get_device_info(self.SIDE_RIGHT)
        return (uid_0, uid_1)

    ##########################################################################################################
    ## Get HWID
    ##########################################################################################################
    def get_hwid(self):
        device_info = self.get_attributes()
        return ( device_info.get('secondary_hw_id'), device_info.get('hw_id') )

    ##########################################################################################################
    ## Get HWID
    ##########################################################################################################
    def get_tp_id(self):
        device_info = self.get_attributes()
        return ( device_info.get('secondary_tp_id'), device_info.get('tp_id') )

    ##########################################################################################################
    ## Get Button State
    ##   Returns 2 32-bit ints for the 64-bit button vector (see steamcontrollerpublic.h for mapping)
    ##########################################################################################################
    def get_button_state(self):
        data = self.get_data()
        return ( data.get('buttons_1'), data.get('buttons_0'))
    
    ##########################################################################################################
    ## Get Trackpad Values 
    ##########################################################################################################
    def get_trackpad_values(self):
        data = self.get_data()
        return ( data.get('left_x'), data.get('left_y'),  data.get('right_x'), data.get('right_y'))

    ##########################################################################################################
    ## Get Thumbstick Values 
    ##########################################################################################################
    def get_thumbstick_values(self, raw):
        self.thumbstick_set_raw( raw )
        sleep(.02)  # Let that command process
        data = self.get_data()
        return ( data.get('left_stick_x'), data.get('left_stick_y'),  data.get('right_stick_x'), data.get('right_stick_y'))
    
    ##########################################################################################################
    ## Get Thumbstick Capsense Values 
    ##########################################################################################################
    def get_thumbstick_capsense_values(self):
        self.set_setting(67, 0)  #Set to thumbstick touch mode
        sleep(0.02)
        data = self.get_data()
        return ( data.get('left_debug'), data.get('right_debug'))

    ##########################################################################################################
    ## Get Trigger Values 
    ##########################################################################################################
    def get_trigger_values(self, raw):
        self.trigger_set_raw(raw)
        sleep(.02)  # Let that command process
        data = self.get_data()
        return ( data.get('trigger_raw_left'), data.get('trigger_raw_right'))
    
    def trigger_set_threshold(self, val):
        self.set_setting(68, val)

    ##########################################################################################################
    ## Get Pressure Values 
    ##########################################################################################################
    def get_pressure_values(self, raw):
        self.pressure_set_raw(raw)
        sleep(.02)  # Let that command process
        data = self.get_data()
        return ( data.get('pressure_pad_left'), data.get('pressure_pad_right'))
    
    ##########################################################################################################
    ## Get IMU Values 
    ##########################################################################################################
    def get_imu_values(self):
        self.set_imu_mode(1)

        sleep(.02)  # Let that command process
        data = self.get_data()
        return ( data.get('accel_x'), data.get('accel_y'), data.get('accel_z'), \
                 data.get('gyro_x'), data.get('gyro_y'), data.get('gyro_z'),     \
                 data.get('gyro_quat_w'), data.get('gyro_quat_x'), data.get('gyro_quat_y'), data.get('gyro_quat_z') )

    ##########################################################################################################
    ## Get Euler Angles 
    ##########################################################################################################
    def euler(self, q0, q1, q2, q3):
        y = 2 * (q0 * q1 + q2 * q3)
        x = 1 - 2 * (q1 * q1 + q2 * q2)
        pitch = round(360. / (2 * math.pi) * math.atan2(y, x), 2)

        y = 2 * (q0 * q2 - q3 * q1)
        if y >= 1:
            roll = 90.
        elif y <= -1:
            roll = -90.
        else:
            roll = round(360. / (2 * math.pi) * math.asin(y), 2)

        y = 2 * (q0 * q3 + q1 * q2)
        x = 1 - 2 * (q2 * q2 + q3 * q3)
        yaw = round(360. / (2 * math.pi) * math.atan2(y, x), 2)

        return (roll, pitch, yaw)
    
    def get_euler_angles(self):
        self.set_imu_mode(1)
        sleep(.02)  # Let that command process

        data = self.get_data()
        q0 = data.get('gyro_quat_w') / 32768.
        q1 = data.get('gyro_quat_x') / 32768.
        q2 = data.get('gyro_quat_y') / 32768.
        q3 = data.get('gyro_quat_z') / 32768.
        self.logger.info(q0, q1, q2, q3)
        (roll, pitch, yaw) =self.euler( q0, q1, q2, q3)

        return roll, pitch, yaw

    ##########################################################################################################
    ## Trigger Cal
    ##########################################################################################################
    def get_trigger_cal(self):
        _, max_0, min_0, neg_0 = self.trigger_get_cal(self.SIDE_LEFT)
        _, max_1, min_1, neg_1 = self.trigger_get_cal(self.SIDE_RIGHT)

        return max_0, min_0, neg_0, max_1, min_1, neg_1

    def set_trigger_cal(self, max_0, min_0, neg_0, max_1, min_1, neg_1):
        self.trigger_set_cal(0, max_0, min_0, neg_0)
        self.trigger_set_cal(1, max_1, min_1, neg_1)

    ##########################################################################################################
    ## Pressure Cal
    ##########################################################################################################
    def get_pressure_cal(self):
        _, max_0, min_0, grams_0 = self.pressure_get_cal(self.SIDE_LEFT)
        _, max_1, min_1, grams_1 = self.pressure_get_cal(self.SIDE_RIGHT)

        return max_0, min_0, grams_0, max_1, min_1, grams_1
    
    def set_pressure_cal(self, max_0, min_0, max_1, min_1):
        self.pressure_set_cal(0, max_0, min_0)
        self.pressure_set_cal(1, max_1, min_1)

    ##########################################################################################################
    ## Thumbstick Cal
    ##########################################################################################################
    def get_thumbstick_cal(self):
        _, x_center_min_0, x_center_max_0, x_full_min_0, x_full_max_0, y_center_min_0, y_center_max_0, y_full_min_0, y_full_max_0 = self.thumbstick_get_cal(0)
        _, x_center_min_1, x_center_max_1, x_full_min_1, x_full_max_1, y_center_min_1, y_center_max_1, y_full_min_1, y_full_max_1 = self.thumbstick_get_cal(1)

        return x_center_min_0, x_center_max_0, x_full_min_0, x_full_max_0, y_center_min_0, y_center_max_0, y_full_min_0, y_full_max_0, \
                x_center_min_1, x_center_max_1, x_full_min_1, x_full_max_1, y_center_min_1, y_center_max_1, y_full_min_1, y_full_max_1

    def set_thumbstick_cal(self, x_center_min_0, x_center_max_0, x_full_min_0, x_full_max_0, y_center_min_0, y_center_max_0, y_full_min_0, y_full_max_0, \
                x_center_min_1, x_center_max_1, x_full_min_1, x_full_max_1, y_center_min_1, y_center_max_1, y_full_min_1, y_full_max_1 ):

        self.thumbstick_set_cal(self.SIDE_LEFT, x_center_min_0, x_center_max_0, x_full_min_0, x_full_max_0, y_center_min_0, y_center_max_0, y_full_min_0, y_full_max_0)
        self.thumbstick_set_cal(self.SIDE_RIGHT, x_center_min_1, x_center_max_1, x_full_min_1, x_full_max_1, y_center_min_1, y_center_max_1, y_full_min_1, y_full_max_1)

    ##########################################################################################################
    ## Debug Data Output (modes setting for what's sent w/ normal packets in debug values
    ## Mode: 0  Thumbstick Touch Counts (L, R) [Default]
    ## Mode: 1  Rushmore Z values (amount of touch) (L, R)
    ## Mode: 2  Rushmore EF indices (L, R)
    ## Mode: 3  Rushmore Noise levels (L, R)
    ##########################################################################################################
    def set_debug_output_mode(self, mode):
        self.set_setting(67, mode)

    ##########################################################################################################
    ## Get Raw Trackpad Data
    ##########################################################################################################
    def enable_debug_data(self, side):
        if side == self.SIDE_LEFT:
            self.trackpad_set_raw_data_mode(0x01)
        elif side == self.SIDE_RIGHT:
            self.trackpad_set_raw_data_mode(0x02)

    def disable_debug_data(self):
        self.trackpad_set_raw_data_mode(0x00)

    def get_raw_trackpad_data(self):
        data = self.get_data()
        if 'pad_raw_0' in data:
            y_raw = [ data['pad_raw_0'], data['pad_raw_1'], data['pad_raw_2'], data['pad_raw_3'], data['pad_raw_4'], data['pad_raw_5'], data['pad_raw_6'], data['pad_raw_7'] ]
            x_raw = [ data['pad_raw_8'], data['pad_raw_9'], data['pad_raw_10'], data['pad_raw_11'], data['pad_raw_12'], data['pad_raw_13'], data['pad_raw_14'], data['pad_raw_15'] ]
            return (y_raw, x_raw )
        else:
            return (None, None)

    def get_raw_trackpad_ref(self):
        data = self.get_data()
        if 'pad_ref_0' in data:
            y_ref = [ data['pad_ref_0'], data['pad_ref_1'], data['pad_ref_2'], data['pad_ref_3'], data['pad_ref_4'], data['pad_ref_5'], data['pad_ref_6'], data['pad_ref_7'] ]
            x_ref = [ data['pad_ref_8'], data['pad_ref_9'], data['pad_ref_10'], data['pad_ref_11'], data['pad_ref_12'], data['pad_ref_13'], data['pad_ref_14'], data['pad_ref_15'] ]
            return ( y_ref, x_ref )
        else:
            return (None, None)

  