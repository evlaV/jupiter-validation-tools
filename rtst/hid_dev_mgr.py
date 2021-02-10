import threading
import hid
import ctypes
import struct
import array
import copy
import os
import sys
import logging

__version__ = "$Revision: #20 $"
__date__ = "$DateTime: 2020/10/30 11:48:45 $"

class HidDeviceManager:
	def __init__(self, vid_pid_endpoint_list, connect_cb, msg_handler=None, dev_num=1):
		self.last_data = {}
		self.thread_lock = threading.Lock()
		self.device = None
		self.run_read_thread = False
		self.read_thread = None

		self.logger = logging.getLogger('RTST.HID')

		self.msg_handler = msg_handler
		self.vid_pid_endpoint_list = vid_pid_endpoint_list
		self.connect_cb = connect_cb

		# Set to connect to the nth enumerated device.
		self.dev_num = dev_num

		self.start_hotplug_thread()

##########################################################################################################
## System methods
##########################################################################################################
	def set_debug_mode(self, mode):
		# Vestigial, but might be useful at some point
		self.debug_mode = mode

	def is_open(self):
		if self.device:
			return True
		else:
			return False

	def sample_handler(self, data):
		if not self.msg_handler:
			return

		self.thread_lock.acquire()
		self.last_data = self.msg_handler(data)
		self.thread_lock.release()

	def set_connect_cb(self, cb):
		self.connect_cb = cb

	def start_hotplug_thread(self):
		# start a timer to check for active devices
		self.hotplug_timer = threading.Timer(.25, self.update_active_device)
		self.hotplug_timer.start()
		self.should_reinstate_hotplug_thread = True

	def __do_read_thread(self):
		try:
			while self.run_read_thread:
				self.sample_handler(self.device.read(64))
		except hid.HIDException as e:
			if e.args[0] != 'The device is not connected.':
				raise e

	def start_read_thread(self):
		self.thread_lock.acquire()
		if self.device:
			self.logger.info("Opening device")
			sys.stdout.flush()
			# self.device.open()

			if self.connect_cb:
				self.connect_cb(self)

			sys.stdout.flush()
			self.run_read_thread = True
			self.read_thread = threading.Thread(target=self.__do_read_thread)
			self.read_thread.start()
		self.thread_lock.release()

	def shutdown(self):
		self.stop_hotplug_thread()
		self.stop_read_thread()

	def restart(self):
		self.logger.info('Restarting device manager')
		self.shutdown()
		self.start_hotplug_thread()

	def stop_hotplug_thread(self):
		# shutdown the find thread
		self.should_reinstate_hotplug_thread = False

		if self.hotplug_timer:
			self.hotplug_timer.cancel()
			self.hotplug_timer = None

	def stop_read_thread(self):
		if self.read_thread:

			self.run_read_thread = False
			self.read_thread.join()

			self.clear_data()
			self.read_thread = None
			self.device = None

	def device_is_plugged(self):
		for dev in hid.enumerate(self.device_vendor_id,self.device_product_id):
			if self.device_path == dev['path']:
				return True
		return False

	def update_active_device(self):
		if not self.should_reinstate_hotplug_thread:
			return
		if self.device:
			if self.device_is_plugged() == False:
				self.logger.info('Device unplugged')
				sys.stdout.flush()
				self.stop_read_thread()
		else:
			# check for new devices
			self.find_device()

		# reinstall the timer
		self.hotplug_timer = threading.Timer(.5, self.update_active_device)
		self.hotplug_timer.start()

	def find_device(self):
		self.device = None
		devs_found = 0

		for (vid, pid) in self.vid_pid_endpoint_list:
			connected_controllers = hid.enumerate(vid, pid)

			for dev in connected_controllers:
				# check for specific endpoint if desired
				found = False
				if sys.platform == 'win32':
					if dev['usage_page'] >= 0xFF00:
						found = True
				else:
					if dev['interface_number'] == 2:
						found = True    


				# Connect only to the specified nth found device.
				if found:
					devs_found += 1
				if devs_found < self.dev_num:
					continue
				
				self.logger.info('HID Mgr: Found match for endpoint w/ VID: {} PID: {}'.format(hex(vid), hex(pid)))

				self.device = hid.Device(path=dev['path'])
				self.device_vendor_id = vid
				self.device_product_id = pid
				self.device_path = dev['path']
				self.start_read_thread()
				return

	def get_device(self):
		return self.device

	def set_device_number(self, device_number):
		self.dev_num = device_number
		self.restart()

	def set_endpoint_list(self, endpoint_list):
		self.vid_pid_endpoint_list = endpoint_list
		self.restart()

##########################################################################################################
## Data methods
##########################################################################################################
	def get_data(self):
		self.thread_lock.acquire()
		data_copy = copy.copy(self.last_data)
		self.thread_lock.release()
		return data_copy

	def clear_data(self):
		self.last_data = {}

		# If the registered message handler has a clear_data() method
		# then call it.
		if callable(getattr(self.msg_handler, 'clear_data', None)):
			self.msg_handler.clear_data()

##########################################################################################################
## Comms methods
##########################################################################################################
	def send_feature_report(self, feature_report_type, report_bytes):
		if not self.is_open():
			return False

		if isinstance(report_bytes, str):
			report_bytes = report_bytes.encode()

		# First byte is Feature Report type.  We'll stills end 64B of payload, but
		# need this value prepended for PyHid
		feature_report = struct.pack('=BBB', 0, feature_report_type, len(report_bytes)) + report_bytes
		
		hid_len = 64		
		# pack the remainder of the hid_len + 1 bytes w/ 0's
		feature_report += b'\0' * (hid_len + 1 - len(feature_report))
		
		try:
			return (self.device.send_feature_report(feature_report) > 0)
		except:
			self.logger.info('Lost connection -- Restarting')
			self.restart()
			return 0

	def get_feature_report(self):
		if not self.is_open():
			return (0, 0, '')

		hid_len = 64
		
		try:
			report = self.device.get_feature_report(0, hid_len + 1)
			report_type = report[1]
			report_length = report[2]
			report_bytes = report[3: 3 + report_length]
			return (report_type, report_length, report_bytes)
		except:
			self.logger.info('Lost connection -- Restarting')
			self.restart()
			return 0
		