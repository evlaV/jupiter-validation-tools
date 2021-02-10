import array
import struct
import copy
import math
import logging
import statistics
import collections

__version__ = "$Revision: #20 $"
__date__ = "$DateTime: 2021/02/08 09:42:51 $"

valve_messages = {

    # ID_CONTROLLER_STATE
    0x01 : ("3I4h2H11h7h", \
        ('packet_num', \
            'buttons_0', \
            'buttons_1', \
            'left_x', \
            'left_y', \
            'right_x', \
            'right_y', \
            'trigger_left', \
            'trigger_right', \
            'accel_x', \
            'accel_y', \
            'accel_z', \
            'gyro_x', \
            'gyro_y', \
            'gyro_z', \
            'gyro_quat_w', \
            'gyro_quat_x', \
            'gyro_quat_y', \
            'gyro_quat_z', \
            'gyro_steering_angle', \
            'trigger_raw_left', \
            'trigger_raw_right', \
            'stick_raw_x', \
            'stick_raw_y', \
            'real_left_x', \
            'real_left_y', \
            'battery_voltage')),

    # ID_CONTROLLER_DEBUG
    0x02: ("4B21h",
        ('pad_num', \
            'unused_0', \
            'unused_1', \
            'unused_2', \

            'pad_y_0', \
            'pad_y_1', \
            'pad_y_2', \
            'pad_y_3', \
            'pad_y_4', \
            'pad_y_5', \
            'pad_y_6', \
            'pad_y_7', \

            'pad_x_0', \
            'pad_x_1', \
            'pad_x_2', \
            'pad_x_3', \
            'pad_x_4', \
            'pad_x_5', \
            'pad_x_6', \
            'pad_x_7', \
            'pad_x_8', \
            'pad_x_9', \
            'pad_x_10', \
            'pad_x_11', \

            'noise',)),

    # ID_CONTROLLER_WIRELESS
    0x03: ("B",
        ('wireless_event',)),

    # ID_CONTROLLER_STATUS
    0x04 : ("I3HBB",
        ('last_packet_num',
            'event_code',
            'state_flags',
            'battery_voltage',
            'battery_level',
            'sensor0',)),

    # ID_CONTROLLER_DEBUG2
    0x05: ("4B21h",
        ('pad_num', \
            'unused_0', \
            'unused_1', \
            'unused_2', \

            'pad_raw_0', \
            'pad_raw_1', \
            'pad_raw_2', \
            'pad_raw_3', \
            'pad_raw_4', \
            'pad_raw_5', \
            'pad_raw_6', \
            'pad_raw_7', \
            'pad_raw_8', \
            'pad_raw_9', \
            'pad_raw_10', \
            'pad_raw_11', \
            'pad_raw_12', \
            'pad_raw_13', \
            'pad_raw_14', \
            'pad_raw_15', \
            'pad_raw_16', \
            'pad_raw_17', \
            'pad_raw_18', \
            'pad_raw_19', \

            'noise',)),

    # ID_CONTROLLER_SECONDARY_STATE
    0x06: ("I8H",
        ('last_packet_num', \
            'pressure_pad_left', \
            'pressure_pad_right', \
            'pressure_bumper_left', \
            'pressure_bumper_right', \
            'bumper_left_pos', \
            'bumper_left_z', \
            'bumper_right_pos', \
            'bumper_right_z',)),

    # ID_CONTROLLER_NEPTUNE
    0x08: ("3I14h2H4h6H",
        ('last_packet_num', \
            'buttons_0', \
            'buttons_1', \
            'left_x', \
            'left_y', \
            'right_x', \
            'right_y', \
            'accel_x', \
            'accel_y', \
            'accel_z', \
            'gyro_x', \
            'gyro_y', \
            'gyro_z', \
            'gyro_quat_w', \
            'gyro_quat_x', \
            'gyro_quat_y', \
            'gyro_quat_z', \
            'trigger_raw_left', \
            'trigger_raw_right', \
            'left_stick_x', \
            'left_stick_y', \
            'right_stick_x', \
            'right_stick_y', \
            'pressure_pad_left', \
            'pressure_pad_right', \
            'bumper_left_z', \
            'bumper_left_pos', \
            'bumper_right_z', \
            'bumper_right_pos',)),
    # ID_CONTROLLER_JUPITER
    0x09: (
        "3I14h2H4h4h",
        (
            'last_packet_num', \
            'buttons_0', \
            'buttons_1', \
            'left_x', \
            'left_y', \
            'right_x', \
            'right_y', \
            'accel_x', \
            'accel_y', \
            'accel_z', \
            'gyro_x', \
            'gyro_y', \
            'gyro_z', \
            'gyro_quat_w', \
            'gyro_quat_x', \
            'gyro_quat_y', \
            'gyro_quat_z', \
            'trigger_raw_left', \
            'trigger_raw_right', \
            'left_stick_x', \
            'left_stick_y', \
            'right_stick_x', \
            'right_stick_y', \
            'pressure_pad_left', \
            'pressure_pad_right', \
            'left_thumbstick_touch', \
            'right_thumbstick_touch', 
        )
    ),
    0x0A: ("1I4B18h",
        (
            'data_last_packet_num', \
            'pad', \
            'frame_rate', \
            'rank_x', \
            'rank_y', \
			'pad_raw_0', \
			'pad_raw_1', \
			'pad_raw_2', \
			'pad_raw_3', \
			'pad_raw_4', \
			'pad_raw_5', \
            'pad_raw_6', \
			'pad_raw_7', \
			'pad_raw_8', \
			'pad_raw_9', \
			'pad_raw_10', \
			'pad_raw_11', \
			'pad_raw_12', \
			'pad_raw_13', \
			'pad_raw_14', \
			'pad_raw_15', \
            'pad_raw_16', \
            'pad_raw_17', \
         )
    ),
    0x0B: ("1I4B18h",
        (
            'data_last_packet_num', \
            'pad', \
            'frame_rate', \
            'rank_x', \
            'rank_y', \
            'pad_ref_0', \
            'pad_ref_1', \
            'pad_ref_2', \
            'pad_ref_3', \
            'pad_ref_4', \
            'pad_ref_5', \
            'pad_ref_6', \
            'pad_ref_7', \
            'pad_ref_8', \
            'pad_ref_9', \
            'pad_ref_10', \
            'pad_ref_11', \
            'pad_ref_12', \
            'pad_ref_13', \
            'pad_ref_14', \
            'pad_ref_15', \
            'pad_raw_16', \
            'pad_raw_17', \
        )
    ),
}

wireless_event_messages = ("Placeholder",
    "Disconnect (code 1)",
    "Connect (code 2)",
    "Pair (code 3)")

status_event_messages = ("Normal (code 0)",
    "Critical battery (code 1)",
    "Gyro init error (code 2)")

class ValveMessageHandler:
    def __init__(self):
        self.clear_data()
        self.logger = logging.getLogger('RTST.VMH')

        self.history_index = 0
        self.len_history = 128

        self.l_x_history = collections.deque(maxlen = self.len_history)
        self.l_y_history = collections.deque(maxlen = self.len_history)
        self.r_x_history = collections.deque(maxlen = self.len_history)
        self.r_y_history = collections.deque(maxlen = self.len_history)
        
        self.l_x_history.append(0)
        self.l_y_history.append(0)
        self.r_x_history.append(0)
        self.r_y_history.append(0)        
        self.l_x_history.append(0)
        self.l_y_history.append(0)
        self.r_x_history.append(0)
        self.r_y_history.append(0)

    def clear_data(self):
        self.last_data = {}
        self.first_packet_num = 0
        self.last_packet_num = 0
        self.first_read_count = 0
        self.last_missed = 0
        self.missed = []

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

    def __call__(self, data):
        # Must be > 1 + header.
        if len(data) < 5:
            return self.last_data

        # Data must be 64 bytes since the radio will not always send a full
        # state message, but Jupiter can send longer messages and needs
        # more room.  Pad with zeros.

        data += b'\0' * (128 - len(data))


        # Parse the message header.
        (msg_version, msg_type, msg_length) = struct.unpack('1H2B', data[0:4])
        if msg_version != 1:
            return self.last_data

       # self.logger.info(":".join("{:02x}".format(ord(c)) for c in data[0:16]))

        # The rest of the data is the payload.
        data = data[4:]

        # Get message parsing data for the message type.
        msg_desc = valve_messages.get(msg_type)
        if not msg_desc:
            return self.last_data
        (msg_format, msg_field_names) = msg_desc
        msg_length = struct.calcsize(msg_format)

        read_list = struct.unpack(msg_format, data[:msg_length])
        result = {}
        for i in range(len(msg_field_names)):
            result[msg_field_names[i]] = read_list[i]

        if msg_type == 9:
            q0 = result['gyro_quat_w'] / 32768.
            q1 = result['gyro_quat_x'] / 32768.
            q2 = result['gyro_quat_y'] / 32768.
            q3 = result['gyro_quat_z'] / 32768.

            (roll, pitch, yaw) = self.euler(q0, q1, q2, q3)

            result['roll'] = roll
            result['pitch'] = pitch
            result['yaw'] = yaw

            # The "thunk" noise isn't interesting for this analysis.  Ignore readings where it has popped back to zero zero.
            #if result['left_x'] != 0: 
            self.l_x_history.append(result['left_x'] )
            #if result['left_y'] != 0: 
            self.l_y_history.append(result['left_y'])
            #if result['right_x'] != 0: 
            self.r_x_history.append(result['right_x'] )
            #if result['right_y'] != 0: 
            self.r_y_history.append(result['right_y'])
            
            # The history index isn't necessary when using deques.  Remove?
            self.history_index += 1
            if self.history_index >= self.len_history / 8:
                self.history_index = 0
                result['l_x_stdev'] = round(math.log2(statistics.stdev(self.l_x_history)+1)*10)
                result['l_y_stdev'] = round(math.log2(statistics.stdev(self.l_y_history)+1)*10)
                result['r_x_stdev'] = round(math.log2(statistics.stdev(self.r_x_history)+1)*10)
                result['r_y_stdev'] = round(math.log2(statistics.stdev(self.r_y_history)+1)*10)


#       if msg_type == 0x0A:
#           y_raw = [ result['pad_raw_0'], result['pad_raw_1'], result['pad_raw_2'], result['pad_raw_3'], result['pad_raw_4'], result['pad_raw_5'], result['pad_raw_6'], result['pad_raw_7'] ]
#            x_raw = [ result['pad_raw_8'], result['pad_raw_9'], result['pad_raw_10'], result['pad_raw_11'], result['pad_raw_12'], result['pad_raw_13'], result['pad_raw_14'], result['pad_raw_15'] ]
#            result['y_raw'] = y_raw
#            result['x_raw'] = x_raw

#		if msg_type == 0x0B:
#			y_ref = [ result['pad_ref_0'], result['pad_ref_1'], result['pad_ref_2'], result['pad_ref_3'], result['pad_ref_4'], result['pad_ref_5'], result['pad_ref_6'], result['pad_ref_7'] ]
#			x_ref = [ result['pad_ref_8'], result['pad_ref_9'], result['pad_ref_10'], result['pad_ref_11'], result['pad_ref_12'], result['pad_ref_13'], result['pad_ref_14'], result['pad_ref_15'] ]
#			result['y_ref'] = y_ref
#			result['x_ref'] = x_ref
#			self.logger.debug('Pad: {} {:3x} {:3x} {:3x} {:3x} {:3x} {:3x} {:3x} {:3x}'.format(result['pad'], result['pad_raw_0'], result['pad_raw_1'], result['pad_raw_2'], result['pad_raw_3'], result['pad_raw_4'], result['pad_raw_5'], result['pad_raw_6'], result['pad_raw_7']))
#			self.logger.debug('Pad: {} {:3x} {:3x} {:3x} {:3x} {:3x} {:3x} {:3x} {:3x}\n'.format(result['pad'], result['pad_raw_8'], result['pad_raw_9'], result['pad_raw_10'], result['pad_raw_11'], result['pad_raw_12'], result['pad_raw_13'], result['pad_raw_14'], result['pad_raw_15']))


        # Filter out some bad results.
        if 'battery_voltage' in result and result['battery_voltage'] == 0:
            del result['battery_voltage']

        if msg_type == 3:
            code = result['wireless_event']
            self.logger.info('Wireless Event:', wireless_event_messages[code])
        elif msg_type == 4 and result['event_code']:
            code = result['event_code']
            if code < len(status_event_messages):
                self.logger.info('Event code:', status_event_messages[code])
            else:
                self.logger.info('Unknown event code: ', hex(code))

        self.update_last_data(msg_type, result)
        self.update_missed_packets()

        return self.last_data

    def update_last_data(self, msg_type, new_data):
        # merge new with old.
        self.last_data.update(new_data)

        # init read_count first time reading this device
        if not 'read_count' in self.last_data:
            self.last_data['read_count'] = 0
        elif msg_type != 3:
            self.last_data['read_count'] += 1

    def update_missed_packets(self):
        if 'last_packet_num' not in self.last_data:
            return 0

        if not self.last_packet_num:
            self.total_packets = 0
            self.index_per = 0
            self.total_missed_per = [0, 0]
            self.total_packets_per = [0, 0]
            self.packet_per = 0.
            self.last_packet_num = self.last_data['last_packet_num']
            return 0

        if self.last_packet_num != self.last_data['last_packet_num']:
            num_packets = self.last_data['last_packet_num'] - self.last_packet_num

            # Weird stuff sometimes happens, guard against them.
            if num_packets < 0 or num_packets > 1000:
                return 0

            self.total_packets += num_packets
            self.total_packets_per[0] += num_packets
            self.total_packets_per[1] += num_packets

            self.last_packet_num = self.last_data['last_packet_num']

            if not self.first_packet_num:
                self.first_packet_num = self.last_packet_num
            if not self.first_read_count:
                self.first_read_count = self.last_data['read_count']

            missed = self.last_packet_num - self.first_packet_num
            missed -= self.last_data['read_count'] - self.first_read_count
            self.last_data['missed_packets'] = missed

            missed_step = missed - self.last_missed
            self.total_missed_per[0] += missed_step
            self.total_missed_per[1] += missed_step
            self.last_missed = missed

            per = float(self.total_missed_per[self.index_per])
            per /= self.total_packets_per[self.index_per]

            self.packet_per += .01 * (per - self.packet_per)

            buffer_index = 1 - self.index_per
            if self.total_packets_per[buffer_index] > 4000:
                self.total_packets_per[self.index_per] = 0
                self.total_missed_per[self.index_per] = 0
                self.index_per = buffer_index

            self.last_data['total_packets'] = self.total_packets
            self.last_data['packet_error_rate'] = self.packet_per * 100.
