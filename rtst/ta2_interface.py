import time
import socket
import threading
import logging
import json

from controller_if import ControllerInterface

##########################################################################################################
## TA2 Test Automation Interface
##########################################################################################################
class Ta2InterfaceHost:
    VERSION = "2024.01.02.1"
    LOCALHOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    TA2_INTERFACE_PORT = 35892  # Port to listen on (non-privileged ports are > 1023)

    def __init__(self, controller_interface:ControllerInterface, key_cb_func) -> None:
        self.controller_interface = controller_interface
        self.key_cb = key_cb_func
        self.fsc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.fsc_listener_thread = threading.Thread(target=self._ta2_listener_thread, daemon=True)
        self.logger = logging.getLogger('RTST.TA2')

        self.last_packet_number = 0
        self.data = None

        # try to open interface socket - can raise exception if socket already bound
        try:
            self.fsc_socket.bind((self.LOCALHOST, self.TA2_INTERFACE_PORT))
            self.fsc_listener_thread.start()
        except OSError:
            self.logger.warning('Failed to bind socket. Check if interface is already open.')
            raise Exception('Failed to bind socket.')

    def _ta2_listener_thread(self):
        while True:
            self.fsc_socket.listen()
            conn, addr = self.fsc_socket.accept()
            with conn:
                self.logger.info((f"interface connected to by {addr}"))
                while True:
                    received = conn.recv(1024)
                    # if we receive None, close conn
                    if not received:
                        break

                    message = received.decode()
                    # GET command requests controller data
                    if message == 'GET':
                        self.wait_for_new_data()
                        # encode data dict to json
                        response = json.dumps(self.data)
                        conn.sendall(response.encode())
                        
                    # SET: command changes RTST settings using key_cb
                    elif message.startswith('KEY:'):
                        chars = message[4:]
                        self.key_cb(KeyStroke(chars))
                        self.logger.info(f'executing key_cb({chars})')
                        time.sleep(.5) # wait for setting to take effect
                        conn.sendall('ACK'.encode())

                    elif message.startswith('SET:'):
                        try:
                            setting_num, setting_val = message[4:].split(',')
                            self.controller_interface.set_setting(int(setting_num), int(setting_val))
                            time.sleep(.5) # wait for setting to take effect
                            conn.sendall('ACK'.encode())
                        except ValueError as e:
                            self.logger.info(f'failed to set setting from message: {message}    error: {e}')
                            conn.sendall('NAK'.encode())

                    elif message.startswith('DEBUG:'):
                        setting = int(message[6])
                        self.logger.info(f'setting debug output select to ({setting})')
                        self.controller_interface.set_setting(67, setting)
                        time.sleep(.5) # wait for setting to take effect
                        conn.sendall('ACK'.encode())

                    elif message == ('FSC'):
                        self.logger.info(f'setting up for FSC test')
                        # disable lockouts so we can have trackpad pressure even if touch not detected
                        self.controller_interface.set_control_lockouts(0)
                        # make sure we are using raw pressure settings
                        self.controller_interface.pressure_set_raw_mode(1)
                        # disable haptics
                        self.controller_interface.haptic_enable(0)
                        time.sleep(.5) # wait for setting to take effect
                        conn.sendall('ACK'.encode())

                    elif message == 'TPD': # depricated, use DEBUG:
                        self.logger.info('setting TP debug mode 4')
                        self.controller_interface.set_setting(67, 4)
                        time.sleep(.5) # wait for setting to take effect
                        conn.sendall('ACK'.encode())
                        
                    elif message == 'META':
                        self.wait_for_new_data()
                        # encode data dict to json
                        response = json.dumps(self.get_metadata())
                        conn.sendall(response.encode())
                    
                    elif message == 'VERSION':
                        conn.sendall(self.VERSION.encode())
                    
                    else:
                        self.logger.warn(f'ta2 request: {message} could not be parsed!')
                        conn.sendall('NAK'.encode())

            self.logger.info((f"ta2 interface disconnected"))        

    # if we've already sent the current packet, wait for fresh data
    # TODO: is this too slow? check for missed packets
    def wait_for_new_data(self):
        while True:
            data = self.controller_interface.get_data()
            packet_number = data['last_packet_num']

            if packet_number != self.last_packet_number:
                self.data = data
                self.last_packet_number = packet_number
                break
            else:
                continue

    def get_metadata(self):
        metadata = self.controller_interface.get_attributes()
        return metadata
        
# input tkinter <key> callback function
class KeyStroke:
    def __init__(self, key:str) -> None:
        self.char = key
        # need to include a code to avoid key_cb errors
        # currently, only char commands can be executed
        self.keycode = 666 
