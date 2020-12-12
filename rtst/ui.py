import tkinter as Tk
import time
import logging
import gzip

__version__ = "$Revision: #23 $"
__date__ = "$DateTime: 2020/11/10 12:28:34 $"

highlight = False
color_pallete = []

button_masks = {
    'trigger_right':			0x0000000000000001,
    'trigger_left':				0x0000000000000002,
    'bumper_right':				0x0000000000000004,
    'bumper_left':				0x0000000000000008,
    'y':						0x0000000000000010,
    'b':						0x0000000000000020,
    'x':						0x0000000000000040,
    'a':						0x0000000000000080,
    'up':						0x0000000000000100,
    'right':					0x0000000000000200,
    'left':						0x0000000000000400,
    'down':						0x0000000000000800,
    'select':					0x0000000000001000,
    'steam':					0x0000000000002000,
    'start':					0x0000000000004000,
    'grip_left':				0x0000000000008000,
    'grip_right':				0x0000000000010000,
    'grip2_left':				0x0000000000000200,
    'grip2_right':				0x0000000000000400,
    'padclick_left':			0x0000000000020000,
    'padclick_right':			0x0000000000040000,
    'finger_present_left':		0x0000000000080000,
    'finger_present_right':		0x0000000000100000,
    'battery_low':				0x0000000000200000,
    'thumbstick_left_button':	0x0000000000400000,
    'thumbstick_right_button':	0x0000000004000000,

# Below here are the button1 (32-bit upper bits) masks.
    'thumbstick_left_touch':	0x00004000,
    'thumbstick_right_touch':	0x00008000,	
    'alt_guide':				0x00040000,
    }

ui_scale = 2
ui_fonts = {
    "vlt_data":   ('Arial', str(4 * ui_scale)),
    "vlt_label":  ('Arial', str(4 * ui_scale)),
    "xyp_label":  ('Arial', str(4 * ui_scale)),
    "xyp_header": ('Arial', str(5 * ui_scale), 'bold'),
    "bg_header":  ('Arial', str(5 * ui_scale), 'bold'),
    "twl_label":  ('Arial', str(4 * ui_scale)),
    "twl_text":   ('Arial', str(4 * ui_scale)),
}

ui_dimensions = {
    "ValueLineWidth":35 * ui_scale,
    "ValueLineHeight":6 * ui_scale,

    "ValueLineWithTextAndLabelLineOffsetX":5 * ui_scale,
    "ValueLineWithTextAndLabelLineOffsetY":8 * ui_scale,

    "ValueLineWithTextTextOffsetX":64 * ui_scale,
    "ValueLineWithTextTextOffsetY":-1 * ui_scale,

    "LineGroupYSpacing":15 * ui_scale,

    "LineGroupYOffset":8 * ui_scale,
    "LineGroupWidth":74 * ui_scale,
    "LineGroupYBoxPad":2 * ui_scale,

    "GroupColumnXOffset":5 * ui_scale,
    "GroupColumnYOffset":5 * ui_scale,
    "GroupColumnYPad":4 * ui_scale,

    "XYPlotWidth":35 * ui_scale,
    "XYPlotHeight":35 * ui_scale,

    "XYPlotSize":35 * ui_scale,

    "XYPlotWithTextAndLabelLineOffsetX":5 * ui_scale,
    "XYPlotWithTextAndLabelLineOffsetY":8 * ui_scale,

    "XYPlotGroupYSpacing":54 * ui_scale,

    "XYPlotGroupYOffset":8 * ui_scale,
    "XYPlotGroupWidth":74 * ui_scale,
    "XYPlotGroupYBoxPad":6 * ui_scale,
}


class UIRoot:
    def __init__(self, cntrlr_mgr, root, canvas, colors):
        self.logger = logging.getLogger('RTST.UI')
        self.logger.info('init')

        global color_pallete
        color_pallete = colors

        # We have 9ms frames, but need at least 3-4ms buffer to ensure that the USB
        # data is actually present
        # when the interval fires off.
        # Legacy: self.tick_interval_ms = 9 - 4

        self.tick_interval_ms = 4
        self.dev_num = 1
        self.current_ep = 0

        self.cntrlr_mgr = cntrlr_mgr
        self.canvas = canvas
        self.root = root

        self.tick_job = self.root.after(self.tick_interval_ms, self.tick)

        ##########################################################################################################################################
        ## Far Left Group
        ##########################################################################################################################################
        self.far_left_groups = []
        self.left_groups = []
        self.middle_groups = []
        self.right_groups = []
        self.far_right_groups = []
        self.ass_end_groups = []

        device_control_group = {
            "title" : "Device Control",
            "type" : "LinesWithLabels",
            "labels" : (
                'Device Number',
                'Logging Enabled',
                'Log Compression',
                'Debug Mode'
            ),
            "ranges" :	None,
            "trigger_limits" : None,
            "data_xform_funcs" : (
                (lambda x: self.dev_num),
                (lambda x: self.get_logging_state()),
                (lambda x: self.log_compression),
                (lambda x: self.debug_mode),
            ),
            "data_fields" : (
                None,
                None,
                None,
                None,
            )
        }
    
        main_device_group = {
            "title" : "Main Device",
            "type" : "TextWithLabels",
            "labels" : (
                'Board HW ID',
                'Board Serial',
                'App Build Timestamp',
                'App Build Date',
                'BL Build Timestamp',
                'BL Build Date',
            ),
            "ranges" : None,
            "trigger_limits" : None,
            "data_xform_funcs" : (
                (lambda x: self.conv_board_rev(1)),
                (lambda x: self.get_board_serial(1)),
                (lambda x: self.get_hex_build_timestamp(1)),
                (lambda x: self.get_str_build_timestamp(1)),
                (lambda x: self.get_hex_boot_build_timestamp(1)),
                (lambda x: self.get_str_boot_build_timestamp(1)),
            ),
            "data_fields" : (
                None,
                None,
                None,
                None,
                None,
                None,
            )
        }
        
        secondary_device_group = {
            "title" : "Secondary Device",
            "type" : "TextWithLabels",
            "labels" : (
                'Board HW ID',
                'Board Serial',
                'App Build Timestamp',
                'App Build Date',
                'BL Build Timestamp',
                'BL Build Date'),
            "ranges" : None,
            "trigger_limits" : None,
            "data_xform_funcs" : (
                (lambda x: self.conv_board_rev(0)),
                (lambda x: self.get_board_serial(0)),
                (lambda x: self.get_hex_build_timestamp(0)),
                (lambda x: self.get_str_build_timestamp(0)),
                (lambda x: self.get_hex_boot_build_timestamp(0)),
                (lambda x: self.get_str_boot_build_timestamp(0)),
            ),
            "data_fields" : (
                None,
                None,
                None,
                None,
                None,
                None,
            )
        }

        status_group = {
            "title" : "Status",
            "type" : "LinesWithLabels",
            "labels" : (
                'Packet Number',
                'Missed Packets',
                'Avg. Missed/s',
                'Frame Rate',
            ),
            "ranges" : (
                (0, 256),
                (0, (2 ** 32) - 1),
                (0, 166),
                (0, 40),
            ),
            "trigger_limits" : (
                (0, 256),
                (0, (2 ** 32) - 1),
                (0, 166),
                (0, 0),
            ),
            "data_xform_funcs" : (
                (lambda x: x % 256),
                None,
                None,
                (lambda x: self.get_frame_rate()),
            ),
            "data_fields" : (
                'last_packet_num',
                'missed_packets',
                'missed_avg',
                None,
            )
        }
        
        self.far_left_groups.append(main_device_group)
        self.far_left_groups.append(secondary_device_group)
        self.far_left_groups.append(status_group)

        ##########################################################################################################################################
        ## Left Group
        ##########################################################################################################################################

        trackpad_data_group = {
            "title" : "Trackpad",
            "type" : "LinesWithLabels",
            "labels" : (
                'X Left',
                'Y Left',
                'X Right',
                'Y Right',
                'Pressure Left',
                'Pressure Right',
                'Finger Present L',
                'Finger Present R',
                'Click Left',
                'Click Right',
            ),
            "ranges" : (
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (0, 32767),
                (0, 32767),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
            ),
            "trigger_limits" : (
                (.1, .9),
                (.1, .9),
                (.1, .9),
                (.1, .9),
                (0, .9),
                (0, .9),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
            ),
            "data_xform_funcs" : (
                None,
                None,
                None,
                None,
                None,
                None,
                (lambda x: 1 if (x & button_masks['finger_present_left']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['finger_present_right']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['padclick_left']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['padclick_right']) > 0 else 0),
            ),
            "data_fields" : (
                'left_x',
                'left_y',
                'right_x',
                'right_y',
                'pressure_pad_left',
                'pressure_pad_right',
                'buttons_0',
                'buttons_0',
                'buttons_0',
                'buttons_0',
            )
        }    

        trackpad_plot_group = {
            "title" : "Trackpad Plots",
            "type" : "XYPlotsWithTrails",
            "labels" : ('Left', 'Right',),
            "ranges" : (
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
            ),
            "trigger_limits" : None,
            "data_xform_funcs" :
            (),
            "data_fields" : (
                'left_x',
                'left_y',
                'right_x',
                'right_y',
            ),
            "line_eqs" : (
                #( 0, 32767.0 * (( 510 - 80 ) - 300)/(700-300) ), # secondary slope,
                #y-intercept
                #( 0, 32767.0 * (( 510 + 80 ) - 300)/(700-300) ), # secondary slope,
                #y-intercept
                #( 9999.0, 32767.0 * (( 520 - 80 ) - 300)/(700-300) ), # secondary slope,
                #y-intercept
                #( 9999.0, 32767.0 * (( 520 + 80 ) - 300)/(700-300) ), # secondary slope,
                #y-intercept
            )
        }

        self.left_groups.append(trackpad_plot_group)
        self.left_groups.append(trackpad_data_group)

        ##########################################################################################################################################
        ## Middle Group
        ##########################################################################################################################################
        thumbstick_data_group = {
            "title" : "Thumbsticks",
            "type" : "LinesWithLabels",
            "labels" : (
                'L Stick X',
                'L Stick Y',
                'R Stick X',
                'R Stick Y',
                'L Stick Raw',
                'L Stick Touch',
                'L Stick Click',
                'R Stick Raw',
                'R Stick Touch',
                'R Stick Click',
            ),
            "ranges" : (
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (0, 100),
                (0, 1),
                (0, 1),
                (0, 100),
                (0, 1),
                (0, 1),
                ),
            "trigger_limits" : (
                (.30, .70),
                (.30, .70),
                (.30, .70),
                (.30, .70),
                (0, 20),
                (0, 1),
                (0, 1),
                (0, 20),
                (0, 1),
                (0, 1),
                ),
            "data_xform_funcs" : (
                None,
                None,
                None,
                None,
                None,
                (lambda x: 1 if (x & button_masks['thumbstick_left_touch']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['thumbstick_left_button']) > 0 else 0),
                None,
                (lambda x: 1 if (x & button_masks['thumbstick_right_touch']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['thumbstick_right_button']) > 0 else 0),
            ),
            "data_fields" : (
                'left_stick_x',
                'left_stick_y',
                'right_stick_x',
                'right_stick_y',
                'left_thumbstick_touch',
                'buttons_1',
                'buttons_0',
                'right_thumbstick_touch',
                'buttons_1',
                'buttons_0',
            )
        }

        thumbstick_plot_group = {
            "title" : "Thumbstick Plots",
            "type" : "XYPlotsWithTrails",
            "labels" : ('Left', 'Right',),
            "ranges" : (
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
            ),
            "trigger_limits" : None,
            "data_xform_funcs" :
                (),
            "data_fields" : (
                'left_stick_x',
                'left_stick_y',
                'right_stick_x',
                'right_stick_y',
            ),
            "line_eqs" : (
                #( 0, 32767.0 * (( 510 - 80 ) - 300)/(700-300) ), # secondary slope,
                #y-intercept
                #( 0, 32767.0 * (( 510 + 80 ) - 300)/(700-300) ), # secondary slope,
                #y-intercept
                #( 9999.0, 32767.0 * (( 520 - 80 ) - 300)/(700-300) ), # secondary slope,
                #y-intercept
                #( 9999.0, 32767.0 * (( 520 + 80 ) - 300)/(700-300) ), # secondary slope,
                #y-intercept
            )
        }

        analog_trigger_group = {
            "title" : "Analog Triggers",
            "type" : "LinesWithLabels",
            "labels" : (
                'trigger raw_left',
                'trigger left button',
                'trigger raw_right',
                'trigger right button',
                'trigger threshold',
                'bumper left button',
                'bumper right button',
            ),
            "ranges" : (
                (0, 32767),
                (0, 1),
                (0, 32767),
                (0, 1),
                (0, 100),
                (0, 1),
                (0, 1),
            ),
            "trigger_limits" : (
                (0, .9),
                (0, 1),
                (0, .9),
                (0, 1),
                (0, 40),
                (0, 1),
                (0, 1),
            ),
            "data_xform_funcs" : (
                None,
                (lambda x: 1 if (x & button_masks['trigger_left']) > 0 else 0),
                None,
                (lambda x: 1 if (x & button_masks['trigger_right']) > 0 else 0),
                (lambda x: self.get_trigger_threshold()),

                (lambda x: 1 if (x & button_masks['bumper_left']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['bumper_right']) > 0 else 0),
            ),
            "data_fields" : (
                'trigger_raw_left',
                'buttons_0',
                'trigger_raw_right',
                'buttons_0',
                None,
                'buttons_0',
                'buttons_0',
            )
        }

        self.middle_groups.append(thumbstick_plot_group)
        self.middle_groups.append(thumbstick_data_group)

        ##########################################################################################################################################
        ## Right Group
        ##########################################################################################################################################

        self.far_middle_groups = []

        accel_gyro_group = {
            "title" : "Accel/Gyro",
            "type" : "LinesWithLabels",
            "labels" : (
                'Accel X',
                'Accel Y',
                'Accel Z',
                'Gyro X',
                'Gyro Y',
                'Gyro Z',
            ),
            "ranges" : (
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
            ),
            "trigger_limits" : (
                (.3 , .7),
                (.3 , .7),
                (.3 , .7),
                (.4 , .6),
                (.4 , .6),
                (.4 , .6),
            ),
            "data_xform_funcs" :
            (),
            "data_fields" : (
                'accel_x',
                'accel_y',
                'accel_z',
                'gyro_x',
                'gyro_y',
                'gyro_z',
            )
        }
        
        quaternion_group = {
            "title" : "Orientation",
            "type" : "LinesWithLabels",
            "labels" : (
                'Quat W',
                'Quat X',
                'Quat Y',
                'Quat Z',
                'Pitch',
                'Roll',
                'Yaw',
            ),
            "ranges" : (
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-32767, 32767),
                (-180, 180),
                (-90, 90),
                (-180, 180),
            ),
            "trigger_limits" : (
                (.5 , .6),
                (.5 , .6),
                (.5 , .6),
                (.5 , .6),
                (.5 , .6),
                (.5 , .6),	
                (.5 , .6),
            ),
            "data_xform_funcs" :
            (),
            "data_fields" : (
                'gyro_quat_w',
                'gyro_quat_x',
                'gyro_quat_y',
                'gyro_quat_z',
                'pitch',
                'roll',
                'yaw',
            )
        }		

        haptic_group = {
            "title" : "Haptic",
            "type" : "LinesWithLabels",
            "labels" : ('Haptics Enabled',
                'Haptics On  usec',
                'Haptics Off usec',
                'Haptics Repeat Count',
                'Haptics Loop Time',
                'Haptic Mode',),
            "ranges" : (
                (0, 2),
                (0, 1000),
                (0, 200),
                (0, 10),
                (0, 40),
                (0, 1),
            ),
            "trigger_limits" : (
                (.5 , .6),
                (.5 , .6),
                (.5 , .6),
                (.5 , .6),
                (.5 , .6),
                (.5 , .6),	
                (.5 , .6),
            ),
            "data_xform_funcs" : (
                (lambda x: self.get_ticking_display()),
                (lambda x: self.get_tick_on_us()),
                (lambda x: self.get_tick_off_us()),
                (lambda x: self.get_tick_repeat()),
                (lambda x: self.get_tick_interval()),
                (lambda x: self.get_haptic_mode()),
            ),
            "data_fields" : (
                None,
                None,
                None,
                None,
                None,
                None,
            )
        }

        self.right_groups.append(accel_gyro_group)
        self.right_groups.append(quaternion_group)
        self.right_groups.append(analog_trigger_group)

        ##########################################################################################################################################
        ## Far Right Group
        ##########################################################################################################################################
            
        left_button_group = {
            "title" : "Left Buttons",
            "type" : "LinesWithLabels",
            "labels" : ('up',
                'right',
                'left',
                'down',
                'select',
                'steam',
            ),
            "ranges" : (
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
            ),
            "trigger_limits" : (
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
            ),
            "data_xform_funcs" : (
                (lambda x: 1 if (x & button_masks['up']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['right']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['left']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['down']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['select']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['steam']) > 0 else 0),
            ),
            "data_fields" : (
                'buttons_0',
                'buttons_0',
                'buttons_0',
                'buttons_0',
                'buttons_0',
                'buttons_0',
            )
        }

        right_button_group = {
            "title" : "Right Buttons",
            "type" : "LinesWithLabels",
            "labels" : ('y',
                'b',
                'x',
                'a',
                'start',
                'Alt'),
            "ranges" : (
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
            ),
            "trigger_limits" : (
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
            ),
            "data_xform_funcs" : (
                (lambda x: 1 if (x & button_masks['y']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['b']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['x']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['a']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['start']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['alt_guide']) > 0 else 0),
            ),
            "data_fields" : (
                'buttons_0',
                'buttons_0',
                'buttons_0',
                'buttons_0',
                'buttons_0',
                'buttons_1',
            )
        }

        grip_button_group = {
            "title" : "Grip Buttons",
            "type" : "LinesWithLabels",
            "labels" : (
                'Grip L Upper',
                'Grip L Lower',
                'Grip R Upper',
                'Grip R Lower',
            ),
            "ranges" : (
                (0, 1),
                (0, 1),				
                (0, 1),
                (0, 1),
            ),
            "trigger_limits" : (
                (0, 1),
                (0, 1),
                (0, 1),
                (0, 1),
            ),
            "data_xform_funcs" : (
                (lambda x: 1 if (x & button_masks['grip2_left']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['grip_left']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['grip2_right']) > 0 else 0),
                (lambda x: 1 if (x & button_masks['grip_right']) > 0 else 0),
            ),
            "data_fields" : (
                'buttons_1', # grip 2
                'buttons_0',
                'buttons_1', # grip 2
                'buttons_0',
            )
        }


        self.far_right_groups.append(left_button_group)
        self.far_right_groups.append(right_button_group)
        self.far_right_groups.append(grip_button_group)
    
        ##########################################################################################################################################
        ## Ass End Group
        ##########################################################################################################################################


    
        trackpad_config_group = {
            "title" : "Trackpad Config",
            "type" : "LinesWithLabels",
            "labels" : (
                'Trackpad Z Thresh',
                'Trackpad Cent Thresh',
                'Trackpad Clip',
                'Trackpad IIR',
                'Trackpad Hyst'
            ),
            "ranges" : (
                (0, 400),
                (0, 20),
                (0, 1),
                (0, 1),
                (0, 30)
            ),
            "trigger_limits" : (
                (0, 0),
                (0, 0),
                (0, 0),
                (0, 0),
                (0, 0),
            ),
            "data_xform_funcs" : (
                (lambda x: self.get_trackpad_z_threshold()),
                (lambda x: self.get_trackpad_centroid_threshold()),
                (lambda x: self.get_trackpad_clipping()),
                (lambda x: self.get_trackpad_iir()),
                (lambda x: self.get_trackpad_hysteresis()),
            ),
            "data_fields" : (
                None,
                None,
                None,
                None,
                None,
            )
        }

        cal_state_group = {
            "title" : "Calibration State",
            "type" : "LinesWithLabels",
            "labels" : (
                'Thumbsticks',
                'Triggers',
                'Pressure',
            ),
            "ranges" : (
                (0, 2),
                (0, 2),				
                (0, 2),
            ),
            "trigger_limits" : (
                (0, 0),
                (0, 0),
                (0, 0),
            ),
            "data_xform_funcs" : (
                (lambda x: self.get_thumbstick_cal_current_step()),
                (lambda x: self.get_trigger_cal_current_step()),
                (lambda x: self.get_pressure_cal_current_step()),

            ),
            "data_fields" : (
                None,
                None,
                None,
            )
        }
        self.ass_end_groups.append(device_control_group)
        self.ass_end_groups.append(trackpad_config_group)
        self.ass_end_groups.append(cal_state_group)
        self.ass_end_groups.append(haptic_group)



        ##########################################################################################################################################

        self.columns = []

        self.root_ui = self.create_ui()

        for col in self.columns:
            col.build_ui()

        self.trackpad_z_threshold = 50
        self.trackpad_framerate = 8
        self.trigger_threshold = 90

        # 1 is legacy mode
        self.haptic_mode = 1

        self.imu_mode = 0
        self.pressure_raw = 0
        self.trigger_raw = 0
        self.thumbstick_raw_mode = 0
        self.trackpad_clipping = 1
        self.trackpad_iir = 1
        self.trackpad_centroid_threshold = 0
        self.trackpad_hysteresis = 0
        self.debug_mode = 0

        # Cal steps 0 = none, 1 = deadzone, 2 = outer extents,3 write -> goes back to 0
        self.thumbstick_cal_current_step = 0 
        self.trigger_cal_current_step = 0 
        self.pressure_cal_current_step = 0 
        
        self.logfile = None
        self.log_compression = False
        self.prev_packet_num = 0

        self.ticking = 0
        self.tick_count = 0
        self.tick_interval = 20
        self.tick_side = 0
        self.tick_on_us = 3500
        self.tick_off_us = 2200
        self.tick_repeat = 3

        self.device_info = {}
        self.device_str_info = {}

        self.fast_scan = 0

        self.log_start_time = 0

        self.devinfo_hold_off_count = 0

#	def toggle_thumbstick_raw_mode ( self ):
#		self.thumbstick_raw_mode = not self.thumbstick_raw_mode

#	def get_thumbstick_raw_mode ( self ):
#		return self.thumbstick_raw_mode

    def toggle_highlight(self):
        global highlight
        highlight = not highlight

    def get_logging_state(self):
        if self.logfile is not None:
            return True
        else:
            return False

    def set_logging_state(self, state):
        if state and not self.logfile:
            if self.log_compression:
                self.logfile = gzip.open("jupiter_log.txt.gz", 'w')
            else:
                try:
                    self.logfile = open("jupiter_log.csv", 'w')
                
                except OSError:
                    self.logger.info("Error: Couldn't open log file")
                    return

#			// Headers for columns
            data = self.cntrlr_mgr.get_data()
            sorted_keys = list(data.keys())
#			sorted_keys.sort()

            for entry in sorted_keys:
                self.logfile.write("{0}, ".format(entry))
            self.logfile.write('\n')


        elif not state and self.logfile:
            self.logfile.close()
            self.logfile = None

    def log_data(self, data):
        if self.logfile is None:
            return False

        # Check if we've come around too soon and the packet hasn't updated. If so, then ignore. 
        # Return True to indicate that we're still in logging state.
        if data['last_packet_num'] == self.prev_packet_num:
            return True

        self.prev_packet_num = data['last_packet_num']

        sorted_keys = list(data.keys())
#		sorted_keys.sort()

        for entry in sorted_keys:
            if (entry == 'buttons_0' or entry == 'buttons_1'):
                self.logfile.write("{0}, ".format("0x{:08x}".format(data[entry])))
            else:
                self.logfile.write("{0}, ".format(data[entry]))
        self.logfile.write('\n')
        return True

    def get_thumbstick_cal_current_step(self):
        return self.thumbstick_cal_current_step

    def set_thumbstick_cal_current_step(self, step):
        self.thumbstick_cal_current_step = step

    def get_trigger_cal_current_step(self):
        return self.trigger_cal_current_step

    def set_trigger_cal_current_step(self, step):
        self.trigger_cal_current_step = step
        
    def get_pressure_cal_current_step(self):
        return self.pressure_cal_current_step

    def set_pressure_cal_current_step(self, step):
        self.pressure_cal_current_step = step

    def get_ticking_state(self):
        return self.ticking

    def get_tick_side(self):
        return self.tick_side

    def get_ticking_display(self):
        if not self.get_ticking_state():
            return "Off", 0
        elif self.get_tick_side():
            return "Left", 1
        else:
            return "Right", 2

    def get_tick_on_us(self):
        return self.tick_on_us

    def get_tick_off_us(self):
        return self.tick_off_us

    def get_tick_repeat(self):
        return self.tick_repeat

    def get_tick_interval(self):
        return self.tick_interval

    def increment_tick_on_us(self):
        self.tick_on_us += 100
        if self.tick_on_us > 5000:
            self.tick_on_us = 0

    def increment_tick_off_us(self):
        self.tick_off_us += 100
        if self.tick_off_us > 5000:
            self.tick_off_us = 0

    def increment_tick_repeat(self):
        self.tick_repeat += 1
        if self.tick_repeat > 10:
            self.tick_repeat = 0

    def increment_tick_interval(self):
        self.tick_interval += 2
        if self.tick_interval > 40:
            self.tick_interval = 2

    def get_trackpad_z_threshold(self):
        return self.trackpad_z_threshold
    
    def get_trackpad_centroid_threshold(self):
        return self.trackpad_centroid_threshold
    
    def get_trackpad_clipping(self):
        return self.trackpad_clipping
    
    def get_trackpad_iir(self):
        return self.trackpad_iir
    
    def get_trackpad_hysteresis(self):
        return self.trackpad_hysteresis

    def get_trackpad_framerate(self):
        return self.trackpad_framerate	

    def get_haptic_mode(self):
        return self.haptic_mode

    def get_dev_info(self, field):
        if self.cntrlr_mgr.is_open() and not self.device_info:
            self.devinfo_hold_off_count += 1
            if self.devinfo_hold_off_count >= 10:
                self.devinfo_hold_off_count = 0
                self.device_info = self.cntrlr_mgr.get_attributes()
                self.trackpad_z_threshold = self.cntrlr_mgr.get_setting(63)
                self.trackpad_centroid_threshold = self.cntrlr_mgr.get_setting(67)
                self.trackpad_framerate = self.cntrlr_mgr.get_setting(64)
                self.trackpad_iir = self.cntrlr_mgr.get_setting(65)
                self.trigger_threshold = self.cntrlr_mgr.get_setting(68)
                self.trackpad_hysteresis = self.cntrlr_mgr.get_setting(69)


        return self.device_info.get(field)

    def get_trigger_threshold(self):
        return self.trigger_threshold

    def get_unique_id(self):
        return self.get_dev_info('unique_id')

    def get_board_serial(self, unit):
        if unit == 1:
            cached = self.device_str_info.get('board_serial')
            if cached == None and self.cntrlr_mgr.is_open():
                cached = self.cntrlr_mgr.get_str_attribute(0)
                self.device_str_info['board_serial'] = cached
        else:
            cached = self.device_str_info.get('secondary_board_serial')
            if cached == None and self.cntrlr_mgr.is_open():
                cached = self.cntrlr_mgr.get_str_attribute(2)
                self.device_str_info['secondary_board_serial'] = cached

        if not cached:
            cached = None
        return cached

    def get_str_boot_build_timestamp(self, unit):
        if unit == 1:
            timestamp = self.get_dev_info('boot_build_timestamp')
        else:
            timestamp = self.get_dev_info('secondary_boot_build_timestamp')

        if timestamp:
            return time.strftime('%x %X %z', time.gmtime(timestamp))

    def get_hex_boot_build_timestamp(self, unit):
        if unit == 1:
            timestamp = self.get_dev_info('boot_build_timestamp')
        else:
            timestamp = self.get_dev_info('secondary_boot_build_timestamp')

        if timestamp:
            return '0x%08x' % timestamp

    def get_str_build_timestamp(self, unit):
        if unit == 1:
            timestamp = self.get_dev_info('build_timestamp')
        else:
            timestamp = self.get_dev_info('secondary_build_timestamp')

        if timestamp:
            return time.strftime('%x %X %z', time.gmtime(timestamp))

    def get_hex_build_timestamp(self, unit):
        if unit == 1:
            timestamp = self.get_dev_info('build_timestamp')
        else:
            timestamp = self.get_dev_info('secondary_build_timestamp')

        if timestamp:
            return '0x%08x' % timestamp

    def get_frame_rate(self):
        return self.get_trackpad_framerate()

    def conv_board_rev(self, unit):
        if unit == 1:
            hw_id = self.get_dev_info('hw_id')
        else:
            hw_id = self.get_dev_info('secondary_hw_id')

        name = 'Unknown'
        if hw_id == 1:
            name = 'D0G'
        elif hw_id == 2:
            names = 'FREEMAN'
        elif hw_id == 3:
            name = 'ELI'
        elif hw_id == 4:
            name = 'HEAVY'
        elif hw_id == 5:
            name = 'INVOKER'
        elif hw_id == 6:
            name = 'INVOKER_R4'
        elif hw_id == 7:
            name = 'JUGGERNAUT'
        elif hw_id == 8:
            name = 'JUGGERNAUT_R4'
        elif hw_id == 9:
            name = 'KUNKKA'
        elif hw_id == 10:
            name = 'LUNA'
        elif hw_id == 11:
            name = 'MIRANA'
        elif hw_id == 13:
            name = 'NIGHTSTALKER'
        elif hw_id == 16:
            name = 'JUPITER_NFF'
        elif hw_id == 17:
            name = 'NEVADA'
        elif hw_id == 18:
            name = 'JUPITER_NFF_V2'
        elif hw_id == 19:
            name = 'Quanta-BUB'
        elif hw_id == 20:
            name = 'NEVADA V2'
        elif hw_id:
            name = 'Unknown (%d)' % hw_id
        return name

    def set_ticking_state(self, state):
        self.ticking = state

    def set_tick_side(self, side):
        self.tick_side = side

    def set_debug_mode(self, mode):
        self.debug_mode = mode
    
    def get_debug_mode(self):
        return self.debug_mode
        
    def create_ui(self):
        self.all_column_data = (self.far_left_groups, self.left_groups, self.middle_groups, self.right_groups, self.far_right_groups, self.ass_end_groups)

        for column_data in self.all_column_data:
            new_column = GroupColumn(self.canvas)

            # add up the widths of the previous columns to set the origin for the next
            x_base = 0
            for c in self.columns:
                x_base = x_base + c.get_size()[0]

            self.columns.append(new_column)

            new_column.set_origin(x_base, 0)

            # populate the column
            for group in column_data:
                # "line_eqs" are optional
                line_eqs = None
                if "line_eqs" in group:
                    line_eqs = group["line_eqs"]

                if group["type"] == "LinesWithLabels":
                    new_column.add_line(LineGroup(self.canvas, group["title"], group["labels"], group["ranges"], group["trigger_limits"], group["data_xform_funcs"], line_eqs))
                elif group["type"] == "TextWithLabels":
                    new_column.add_line(TextGroup(self.canvas, group["title"], group["labels"], group["ranges"], group["trigger_limits"], group["data_xform_funcs"], line_eqs))
                elif group["type"] == "XYPlots":
                    new_column.add_line(XYPlotGroup(self.canvas, group["title"], group["labels"], group["ranges"], group["trigger_limits"], group["data_xform_funcs"], line_eqs))
                elif group["type"] == "XYPlotsWithTrails":
                    new_column.add_line(XYPlotGroup(self.canvas, group["title"], group["labels"], group["ranges"], group["trigger_limits"], group["data_xform_funcs"], line_eqs, trails=True))

    def update_column(self, data, groups, column):
        data_groups = []

        # build up the list of data requried for each UI group in this column
        for group in groups:
            data_list = []
            for data_entry in group["data_fields"]:
                if data_entry in data:
                    data_list.append(data[data_entry])
                else:
                    data_list.append(0)
            data_groups.append(data_list)

        # update the column using the accumulated data
        column.update(data_groups)

    def clear_data(self):
        group_column_list = zip(self.all_column_data, self.columns)

        for group_column in group_column_list:
        # Update columns with NULL data.
            self.update_column({}, group_column[0], group_column[1])

        # clear cached device info
        self.device_info = {}
        self.device_str_info = {}

        self.cntrlr_mgr.clear_data()

        self.fast_scan = 0


    def tick(self):
        data = self.cntrlr_mgr.get_data()
        if data == None:
            return

        if not self.cntrlr_mgr.is_open():
            self.clear_data()
            self.tick_job = self.root.after(self.tick_interval_ms, self.tick)
            return

        if not self.log_data(data):

            group_column_list = zip(self.all_column_data, self.columns)

            for group_column in group_column_list:
                # Update columns with NULL data.
                self.update_column(data, group_column[0], group_column[1])


            if self.ticking:
                self.tick_count += 1
                if self.tick_count >= self.tick_interval:
                    if self.tick_side:
                        self.cntrlr_mgr.haptic_pulse(0, self.tick_on_us, self.tick_off_us, self.tick_repeat)
                    else:
                        self.cntrlr_mgr.haptic_pulse(1, self.tick_on_us, self.tick_off_us, self.tick_repeat)

                    self.tick_count = 0
#		Would like to update something, but that leads to lost frames currently
#		else:
#			self.update_column(data, self.far_left_groups, self.columns[0])

            
        self.tick_job = self.root.after(self.tick_interval_ms, self.tick)


    def get_size(self):
        # add up the widths of the previous columns to set the origin for the next
        x_sum = 0
        y_max = 0
        for c in self.columns:
            x_sum = x_sum + c.get_size()[0]
            if c.get_size()[1] > y_max:
                y_max = c.get_size()[1]

        return	(x_sum, y_max)
    
    def set_dev_num(self, dn):
        self.logger.info('dev # set to: {}'.format(dn))
        self.dev_num = dn

    def set_current_ep(self, ep):
        self.current_ep = ep

        
##########################################################################################################################################
## Widgets
##########################################################################################################################################
class ValueLine:
    def __init__(self, canvas):
        self.range = (0, 32767)
        self.trigger_limits = (0, 1)
        self.label = "test"
        self.x_origin = 0
        self.y_origin = 0

        self.elements = {}

        self.canvas = canvas

        self.widgets = {}

        self.xform_func = None

        self.highlighted = False
        self.triggered_low = False
        self.triggered_high = False

    def build_ui(self):
        global color_pallete
        self.widgets['box'] = self.canvas.create_rectangle(self.x_origin, self.y_origin,
                                                            self.x_origin + ui_dimensions["ValueLineWidth"], self.y_origin + ui_dimensions["ValueLineHeight"],
                                                            fill=None, outline=color_pallete[1])
        self.widgets['line'] = self.canvas.create_rectangle(self.x_origin + 1, self.y_origin + 1,
                                                             self.x_origin + ui_dimensions["ValueLineWidth"] / 2, self.y_origin + ui_dimensions["ValueLineHeight"],
                                                             fill=color_pallete[3], outline=None, width=0)

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def set_range(self, line_range):
        self.range = line_range

    def set_trigger_limits(self, trigger_limits):
        self.trigger_limits = trigger_limits

    def set_xform_func(self, xform_func):
        self.xform_func = xform_func

    def clear_highlighting(self):
        self.highlighted = False
        self.triggered_low = False
        self.triggered_high = False
        self.canvas.itemconfigure(self.widgets['line'], fill=color_pallete[3])

    def trigger_highlight(self, valf):
        if valf <= self.trigger_limits[0]:
            self.triggered_low = True

        if valf >= self.trigger_limits[1]:
            self.triggered_high = True

        if self.triggered_low and self.triggered_high and not self.highlighted:
            return True
        else:
            return False

    def update(self, value):
        global highlight

        if not highlight:
            self.clear_highlighting()

        if highlight and self.highlighted:
            return

        if self.xform_func:
            value = self.xform_func(value)

        valf = float(value - self.range[0]) / float(self.range[1] - self.range[0])

        if(valf > 1.0): valf = 1.0
        if(valf < 0.0): valf = 0.0

        bar_edge = valf * ui_dimensions["ValueLineWidth"]

        coords = self.canvas.coords(self.widgets['line'])

        self.canvas.coords(self.widgets['line'], self.x_origin + 1, self.y_origin + 1, self.x_origin + bar_edge, self.y_origin + ui_dimensions["ValueLineHeight"])

        if  highlight:
            if self.trigger_highlight(valf):
                self.highlighted = True
                self.canvas.itemconfigure(self.widgets['line'], fill='#FF00FF')
                self.canvas.coords(self.widgets['line'], self.x_origin + 1, self.y_origin + 1, self.x_origin + ui_dimensions["ValueLineWidth"], self.y_origin + ui_dimensions["ValueLineHeight"])


    def get_size(self):
        return (ui_dimensions["ValueLineWidth"], ui_dimensions["ValueLineHeight"])
    
class XYPlot:
    def __init__(self, canvas, trails_enabled = False):
        self.rangeX = (0, 32767)
        self.rangeY = (0, 32767)
        self.label = "test"
        self.x_origin = 0
        self.y_origin = 0

        self.elements = {}

        self.canvas = canvas

        self.widgets = {}

        self.xform_func = None

        self.dot_size = 6

        self.line_eqs = []

        self.max_lines = 2

        self.trails_enabled = trails_enabled

        self.trail_count = 50

        self.trails = []
        self.trail_pos = []

    def lerp(self, a, a0, a1, b0, b1):
        i = (float(a) - a0) / (a1 - a0)
        return i * (b1 - b0) + b0

    def build_ui(self):
        self.widgets['box'] = self.canvas.create_rectangle(self.x_origin, self.y_origin,
                                                            self.x_origin + ui_dimensions["XYPlotSize"], self.y_origin + ui_dimensions["XYPlotSize"],
                                                            fill=None, outline=color_pallete[1])
        self.widgets['dot'] = self.canvas.create_oval(0, 0, 0, 0, outline=color_pallete[1], fill=color_pallete[3])

        if self.trails_enabled:
            for i in range(self.trail_count):
                scale = float(self.trail_count - i) / self.trail_count
                outline_color_r = int(color_pallete[1][1:3], 16)
                outline_color_g = int(color_pallete[1][3:5], 16)
                outline_color_b = int(color_pallete[1][5:7], 16)

                bg_color_r = int(color_pallete[0][1:3], 16)
                bg_color_g = int(color_pallete[0][3:5], 16)
                bg_color_b = int(color_pallete[0][5:7], 16)

                blend_color_r = int(self.lerp(scale, 0, 1, outline_color_r, bg_color_r))
                blend_color_g = int(self.lerp(scale, 0, 1, outline_color_g, bg_color_g))
                blend_color_b = int(self.lerp(scale, 0, 1, outline_color_b, bg_color_b))

                color_str = "#%02x%02x%02x" % (blend_color_r, blend_color_g, blend_color_b)

                self.trails.append(self.canvas.create_oval(0, 0, 0, 0, outline=color_str, fill=color_str))

        self.lines = []
        for i in range(self.max_lines):
            self.lines.append(self.canvas.create_line(0, 0, 0, 0, fill=color_pallete[3]))

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def set_range(self, rangeX, rangeY):
        self.rangeX = rangeX
        self.rangeY = rangeY

    def set_trigger_limits(self, trigger_limits):
        self.trigger_limits = trigger_limits


    def set_xform_func(self, xform_func):
        self.xform_func = xform_func

    def update(self, valueX, valueY):
        x_val = float(valueX - self.rangeX[0]) / float(self.rangeX[1] - self.rangeX[0])
        y_val = 1.0 - float(valueY - self.rangeY[0]) / float(self.rangeY[1] - self.rangeY[0])

        x_center = self.x_origin + x_val * ui_dimensions["XYPlotSize"]
        y_center = self.y_origin + y_val * ui_dimensions["XYPlotSize"]

        self.canvas.coords(self.widgets['dot'], x_center - self.dot_size / 2, y_center - self.dot_size / 2, x_center + self.dot_size / 2, y_center + self.dot_size / 2)

        if self.trails_enabled:
            self.trail_pos.append((x_center, y_center))
            if len(self.trail_pos) == self.trail_count:
                self.trail_pos.pop(0)

            for i in range(len(self.trail_pos)):
                trail_x = self.trail_pos[i][0]
                trail_y = self.trail_pos[i][1]
                self.canvas.coords(self.trails[i], trail_x - self.dot_size / 4, trail_y - self.dot_size / 4, trail_x + self.dot_size / 4, trail_y + self.dot_size / 4)



    def get_size(self):
        return (ui_dimensions["XYPlotSize"], ui_dimensions["XYPlotSize"])

    def add_reference_line(self, line_eq):
        self.line_eqs.append(line_eq)

        for i in range(len(self.line_eqs)):
            if i == self.max_lines:
                break

            line_eq = self.line_eqs[i]

            slope = line_eq[0]
            y_int = line_eq[1]

            # solve for the points that intersect the box

            # x = 0
            x0 = 0.0
            y0 = slope * x0 + y_int

            if y0 < 0:
                y0 = 0
                x0 = (y0 - y_int) / slope

            if y0 > 32767:
                y0 = 32767
                x0 = (y0 - y_int) / slope

            x0 = self.x_origin + x0 * ui_dimensions["XYPlotSize"] / 32767 # normalize
            y0 = self.y_origin + (32767 - y0) * ui_dimensions["XYPlotSize"] / 32767 # normalize



            x1 = 32767
            y1 = slope * x1 + y_int

            if y1 < 0:
                y1 = 0
                x1 = (y1 - y_int) / slope

            if y1 > 32767:
                y1 = 32767
                x1 = (y1 - y_int) / slope

            x1 = self.x_origin + x1 * ui_dimensions["XYPlotSize"] / 32767 # normalize
            y1 = self.y_origin + (32767 - y1) * ui_dimensions["XYPlotSize"] / 32767 # normalize

            self.canvas.coords(self.lines[i], x0, y0, x1, y1)

class ValueLineWithText:
    def __init__(self, canvas):
        self.canvas = canvas
        self.x_origin = 0
        self.y_origin = 0

        self.widgets = {}

        self.value_line = ValueLine(self.canvas)

        self.xform_func = None

    def build_ui(self):
        self.value_line.set_origin(self.x_origin, self.y_origin)
        self.value_line.build_ui()

        x = self.x_origin + ui_dimensions["ValueLineWithTextTextOffsetX"]
        y = self.y_origin + ui_dimensions["ValueLineWithTextTextOffsetY"]
        self.widgets['label'] = self.canvas.create_text(x, y, anchor=Tk.NE, text="0", fill=color_pallete[2], font=ui_fonts['vlt_data'])

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def set_range(self, line_range):
        self.value_line.set_range(line_range)

    def set_trigger_limits(self, trigger_limits):
        self.value_line.set_trigger_limits(trigger_limits)

    def set_xform_func(self, xform_func):
        self.xform_func = xform_func

    def update(self, value):
        if self.xform_func:
            value = self.xform_func(value)

        # A tuple indicates that the returned value is more complex than a simple
        # number or boolean.
        # tuple[0] = text
        # tuple[1] = value passed into ValueLine class
        if type(value) == tuple:
            value_text = str(value[0])
            value = value[1]
        else:
            value_text = str(value)

        self.value_line.update(value)

        self.canvas.itemconfig(self.widgets['label'] , text=value_text)

    def get_size(self):
        ls = self.value_line.get_size()
        return  (ls[0], ls[1] + ui_dimensions["ValueLineWithTextTextOffsetY"])

class ValueLineWithTextAndLabel:
    def __init__(self, canvas, label_text):
        self.canvas = canvas
        self.x_origin = 0
        self.y_origin = 0
        self.label_text = label_text

        self.widgets = {}

        self.value_line = ValueLineWithText(self.canvas)

    def build_ui(self):
        self.value_line.set_origin(self.x_origin + ui_dimensions["ValueLineWithTextAndLabelLineOffsetX"], self.y_origin + ui_dimensions["ValueLineWithTextAndLabelLineOffsetY"])
        self.value_line.build_ui()

        x = self.x_origin + ui_dimensions["ValueLineWithTextAndLabelLineOffsetX"]
        y = self.y_origin + ui_dimensions["ValueLineWithTextAndLabelLineOffsetY"]
        self.widgets['label'] = self.canvas.create_text(x, y, anchor=Tk.SW, text=self.label_text, fill=color_pallete[2], font=ui_fonts['vlt_label'])

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def set_range(self, line_range):
        self.value_line.set_range(line_range)

    def set_trigger_limits(self, trigger_limits):
        self.value_line.set_trigger_limits(trigger_limits)

    def set_xform_func(self, xform_func):
        self.value_line.set_xform_func(xform_func)

    def update(self, value):
        self.value_line.update(value)

    def get_size(self):
        ls = self.value_line.get_size()
        return  (ls[0] + ui_dimensions["ValueLineWithTextAndLabelLineOffsetX"], ls[1] + ui_dimensions["ValueLineWithTextTextOffsetY"])

class XYPlotWithTextAndLabel:
    def __init__(self, canvas, label_text, trails_enabled=False):
        self.canvas = canvas
        self.x_origin = 0
        self.y_origin = 0
        self.label_text = label_text
        self.widgets = {}

        self.xyplot = XYPlot(self.canvas, trails_enabled)

    def build_ui(self):
        self.xyplot.set_origin(self.x_origin + ui_dimensions["XYPlotWithTextAndLabelLineOffsetX"], self.y_origin + ui_dimensions["XYPlotWithTextAndLabelLineOffsetY"])
        self.xyplot.build_ui()

        x = self.x_origin + ui_dimensions["XYPlotWithTextAndLabelLineOffsetX"]
        y = self.y_origin + ui_dimensions["XYPlotWithTextAndLabelLineOffsetY"]
        self.widgets['label'] = self.canvas.create_text(x, y, anchor=Tk.SW, text=self.label_text, fill=color_pallete[2], font=ui_fonts['xyp_label'])

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def set_range(self, rangeX, rangeY):
        self.xyplot.set_range(rangeX, rangeY)

    def set_trigger_limits(self, trigger_limits):
        self.trigger_limits = trigger_limits

    def set_xform_func(self, xform_func):
        self.xyplot.set_xform_func(xform_func)

    def update(self, value1, value2):
        self.xyplot.update(value1, value2)

        # label = ""
        # if value1:
            # label = str( math.atan2(value2,value1) )

        # self.canvas.itemconfig( self.widgets['label'] , text=label )

    def get_size(self):
        ls = self.xyplot.get_size()
        return  (ls[0] + ui_dimensions["XYPlotWithTextAndLabelLineOffsetX"], ls[1] + ui_dimensions["XYPlotWithTextAndLabelLineOffsetY"])

    def add_reference_line(self, line_eq):
        if self.xyplot:
            self.xyplot.add_reference_line(line_eq)

class XYPlotGroup:
    def __init__(self, canvas, title, labels, ranges=None, trigger_limits=None, xform_funcs=None, line_eqs=None, trails=False):
        self.canvas = canvas
        self.x_origin = 0
        self.y_origin = 0

        self.line_eqs = line_eqs

        self.title = title

        self.widgets = {}

        self.labels = labels
        self.title = title

        self.lines = []
        self.ranges = ranges
        self.trigger_limits = trigger_limits

        self.xform_funcs = xform_funcs

        self.trails_enabled = trails

    def build_ui(self):
        for i in range(len(self.labels)):

            new_line = XYPlotWithTextAndLabel(self.canvas, self.labels[i], self.trails_enabled)
            x = self.x_origin
            y = \
                self.y_origin + \
                i * (ui_dimensions["XYPlotGroupYOffset"] + ui_dimensions["XYPlotSize"]) + \
                ui_dimensions["XYPlotGroupYBoxPad"] + \
                ui_dimensions["XYPlotGroupYBoxPad"]

            new_line.set_origin(x, y)

            if self.ranges:
                if len(self.ranges) > i * 2 + 1:
                    new_line.set_range(self.ranges[i * 2], self.ranges[i * 2 + 1])

            if self.xform_funcs:
                if len(self.xform_funcs) == len(self.labels):
                    new_line.set_xform_func(self.xform_funcs[i])

            new_line.build_ui()

            if self.line_eqs:
                for line in self.line_eqs:
                    new_line.add_reference_line(line)

            self.lines.append(new_line)

        x = self.x_origin
        y = self.y_origin + ui_dimensions["XYPlotGroupYOffset"]
        self.widgets['label'] = self.canvas.create_text(x, y, anchor=Tk.SW, text=self.title, fill=color_pallete[2], font=ui_fonts['xyp_header'])

        self.widgets['box'] = self.canvas.create_rectangle(self.x_origin, self.y_origin + ui_dimensions["XYPlotGroupYOffset"],
                                                            self.x_origin + ui_dimensions["XYPlotGroupWidth"],
                                                            self.y_origin + len(self.labels) * (ui_dimensions["XYPlotGroupYOffset"] + ui_dimensions["XYPlotSize"]) + 2 * ui_dimensions["XYPlotGroupYBoxPad"] + ui_dimensions["XYPlotGroupYBoxPad"],
                                                            fill=None, outline=color_pallete[1])

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def update(self, values):
        if len(values) / 2 != len(self.lines):
            self.logger.info("XYPlotGroup::update: wrong number of values vs plots")
            return

        for i in range(len(values) // 2):
            self.lines[i].update(values[2 * i], values[2 * i + 1])

    def get_size(self):
        sum = (0,0)
        for line in self.lines:
            ls = line.get_size()
            sum = (sum[0] + ls[0], sum[1] + ls[1])

        x = ui_dimensions["XYPlotGroupWidth"]
        y = len(self.labels) * (ui_dimensions["XYPlotGroupYOffset"] + ui_dimensions["XYPlotSize"]) + 3 * ui_dimensions["XYPlotGroupYBoxPad"]
        return (x, y)

class BoxGroup:
    def __init__(self, canvas, title, labels, ranges=None, trigger_limits=None, xform_funcs=None, line_eqs=None):
        self.canvas = canvas
        self.x_origin = 0
        self.y_origin = 0

        self.title = title

        self.widgets = {}

        self.labels = labels
        self.title = title

        self.lines = []
        self.ranges = ranges
        self.trigger_limits = trigger_limits

        self.xform_funcs = xform_funcs

    def build_ui(self):
        for i in range(len(self.labels)):
            new_line = self.BoxClass(self.canvas, self.labels[i])
            x = self.x_origin
            y = self.y_origin + i * ui_dimensions["LineGroupYSpacing"] + ui_dimensions["LineGroupYOffset"] + ui_dimensions["LineGroupYBoxPad"]
            new_line.set_origin(x, y)

            if self.ranges:
                if len(self.ranges) == len(self.labels):
                    new_line.set_range(self.ranges[i])

            if self.trigger_limits:
                if len(self.trigger_limits) == len(self.labels):
                    new_line.set_trigger_limits(self.trigger_limits[i])

            if self.xform_funcs:
                if len(self.xform_funcs) == len(self.labels):
                    new_line.set_xform_func(self.xform_funcs[i])

            new_line.build_ui()

            self.lines.append(new_line)

        x = self.x_origin
        y = self.y_origin + ui_dimensions["LineGroupYOffset"]
        self.widgets['label'] = self.canvas.create_text(x, y, anchor=Tk.SW, text=self.title, fill=color_pallete[2], font=ui_fonts['bg_header'])

        self.widgets['box'] = self.canvas.create_rectangle(self.x_origin, self.y_origin + ui_dimensions["LineGroupYOffset"],
                                                            self.x_origin + ui_dimensions["LineGroupWidth"], self.y_origin + ui_dimensions["LineGroupYOffset"] + len(self.labels) * ui_dimensions["LineGroupYSpacing"] + 2 * ui_dimensions["LineGroupYBoxPad"],
                                                            fill=None, outline=color_pallete[1])

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def update(self, values):
        if len(values) != len(self.lines):
            return

        for i in range(len(values)):
            self.lines[i].update(values[i])

    def get_size(self):
        sum = (0,0)
        for line in self.lines:
            ls = line.get_size()
            sum = (sum[0] + ls[0], sum[1] + ls[1])

        x = ui_dimensions["LineGroupWidth"]
        y = len(self.labels) * ui_dimensions["LineGroupYSpacing"] + 2 * ui_dimensions["LineGroupYBoxPad"] + ui_dimensions["LineGroupYOffset"]
        return  (x, y)

class LineGroup(BoxGroup):
    BoxClass = ValueLineWithTextAndLabel

class GroupColumn:
    def __init__(self, canvas):
        self.canvas = canvas
        self.x_origin = 0
        self.y_origin = 0

        self.lines = []

    def add_line(self, line_group):
        self.lines.append(line_group)

    def build_ui(self):
        line_sum_y = 0

        for i in range(len(self.lines)):
            x = self.x_origin + ui_dimensions["GroupColumnXOffset"]
            y = self.y_origin + ui_dimensions["GroupColumnYOffset"]
            y += ui_dimensions["GroupColumnYPad"] * i + line_sum_y
            line_sum_y += self.lines[i].get_size()[1]
            self.lines[i].set_origin(x, y)
            self.lines[i].build_ui()

    def update(self, values):
        if len(values) != len(self.lines):
            return

        for i in range(len(values)):
            self.lines[i].update(values[i])

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def get_size(self):
        size = (0,0)

        if not len(self.lines):
            return size

        for line in self.lines:
            ls = line.get_size()
            size = (size[0], size[1] + ls[1])

        size = (size[0] + ls[0] + ui_dimensions["GroupColumnXOffset"] * 2, size[1] + ui_dimensions["GroupColumnYOffset"] * 2 + ui_dimensions["GroupColumnYPad"] * len(self.lines) - 1)

        return size

class TextWithLabel:
    def __init__(self, canvas, label_text):
        self.canvas = canvas
        self.x_origin = 0
        self.y_origin = 0
        self.label_text = label_text
        self.widgets = {}

    def build_ui(self):
        x = self.x_origin + ui_dimensions["ValueLineWithTextAndLabelLineOffsetX"]
        y = self.y_origin + ui_dimensions["ValueLineWithTextAndLabelLineOffsetY"]
        self.widgets['label'] = self.canvas.create_text(x, y, anchor=Tk.SW, text=self.label_text, fill=color_pallete[2], font=ui_fonts['twl_label'])

        x = self.x_origin + ui_dimensions["ValueLineWithTextAndLabelLineOffsetX"]
        y = self.y_origin + ui_dimensions["ValueLineWithTextAndLabelLineOffsetY"] * 2
        self.widgets['text'] = self.canvas.create_text(x, y, anchor=Tk.SW, text='', fill=color_pallete[3], font=ui_fonts['twl_text'])

    def set_origin(self, x, y):
        self.x_origin = x
        self.y_origin = y

    def set_xform_func(self, xform_func):
        self.xform_func = xform_func

    def update(self, value):
        if self.xform_func:
            value = self.xform_func(value)
        self.canvas.itemconfig(self.widgets['text'] , text=str(value))

    def get_size(self):
        return (ui_dimensions["ValueLineWidth"] + ui_dimensions["ValueLineWithTextAndLabelLineOffsetX"], ui_dimensions["ValueLineHeight"] + ui_dimensions["ValueLineWithTextAndLabelLineOffsetY"])

class TextGroup(BoxGroup):
    BoxClass = TextWithLabel

class ConsoleText(Tk.Text):
    '''A Tkinter Text widget that provides a scrolling display of console
    stderr and stdout.'''

    class IORedirector(object):
        '''A general class for redirecting I/O to this Text widget.'''
        def __init__(self,text_area):
            self.text_area = text_area

    class StdoutRedirector(IORedirector):
        '''A class for redirecting stdout to this Text widget.'''
        def write(self,str):
            self.text_area.write(str,False)

        def flush(self):
            pass

    class StderrRedirector(IORedirector):
        '''A class for redirecting stderr to this Text widget.'''
        def write(self,str):
            self.text_area.write(str,True)
        
        def flush(self):
            pass

    def __init__(self, master=None, cnf={}, **kw):
        '''See the __init__ for Tkinter.Text for most of this stuff.'''

        Tk.Text.__init__(self, master, cnf, **kw)

        self.started = False
        self.write_lock = threading.Lock()

        self.tag_configure('STDOUT',background='white',foreground='black')
        self.tag_configure('STDERR',background='white',foreground='red')

        self.config(state=Tk.DISABLED)
# Logging crap
    def start(self):

        if self.started:
            return

        self.started = True

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        stdout_redirector = ConsoleText.StdoutRedirector(self)
        stderr_redirector = ConsoleText.StderrRedirector(self)

        sys.stdout = stdout_redirector
        sys.stderr = stderr_redirector

    def stop(self):

        if not self.started:
            return

        self.started = False

        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def write(self,val,is_stderr=False):

        #Fun Fact: The way Tkinter Text objects work is that if they're
        #disabled,
        #you can't write into them AT ALL (via the GUI or programatically).
        #Since we want them
        #disabled for the user, we have to set them to NORMAL (a.k.a.
        #ENABLED), write to them,
        #then set their state back to DISABLED.
        #
        self.write_lock.acquire()
        self.config(state=Tk.NORMAL)

    #    self.insert('end',val,'STDERR' if is_stderr else 'STDOUT')
        self.see('end')

        self.config(state=Tk.DISABLED)
  
        self.write_lock.release()

