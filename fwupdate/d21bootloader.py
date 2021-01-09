#!/usr/bin/env python3
import sys
import hid
import time
import struct
import math
import crcmod
import click
import errno
import datetime

import progressbar

ID_GET_ATTRIBUTES_VALUES    = 0x83
ID_REBOOT_INTO_ISP          = 0x90
ID_FIRMWARE_UPDATE_START    = 0x91
ID_FIRMWARE_UPDATE_DATA     = 0x92
ID_FIRMWARE_UPDATE_COMPLETE = 0x93
ID_FIRMWARE_UPDATE_ACK      = 0x94
ID_FIRMWARE_UPDATE_REBOOT   = 0x95

HID_ATTRIB_PRODUCT_ID          = 1
HID_ATTRIB_FIRMWARE_BUILD_TIME = 4
HID_ATTRIB_BOARD_REVISION      = 9

ID_ALL_COMMANDS = (ID_GET_ATTRIBUTES_VALUES,
                   ID_REBOOT_INTO_ISP,
                   ID_FIRMWARE_UPDATE_START,
                   ID_FIRMWARE_UPDATE_DATA,
                   ID_FIRMWARE_UPDATE_COMPLETE,
                   ID_FIRMWARE_UPDATE_ACK,
                   ID_FIRMWARE_UPDATE_REBOOT)

BLOB_ID_FIRMWARE            = 0
BLOB_ID_DEVICE_INFO_THIS    = 1
BLOB_ID_DEVICE_BLOB_THIS    = 2
BLOB_ID_FIRMWARE_CRC_THIS   = 3
BLOB_ID_FIRMWARE_OTHER      = 0x8 # Fake, currently not supported by the firmware
BLOB_ID_DEVICE_INFO_OTHER   = 0x8 + BLOB_ID_DEVICE_INFO_THIS
BLOB_ID_DEVICE_BLOB_OTHER   = 0x8 + BLOB_ID_DEVICE_BLOB_THIS
BLOB_ID_FIRMWARE_CRC_OTHER  = 0x8 + BLOB_ID_FIRMWARE_CRC_THIS

UPDATE_STATUS_OK            = 0
UPDATE_STATUS_ERROR         = 1
UPDATE_STATUS_BUSY          = 2
DEBUG_SET_SINGLETON_MODE    = 0x8004
DEBUG_BOOTLOADER_LOCK       = 0x8007
DEBUG_BOOTLOADER_UNLOCK     = 0x8008
DEBUG_READ_HID_THIS         = 0x8009
DEBUG_READ_HID_OTHER        = 0x800A
DEBUG_READ_32B_THIS         = 0x800D
DEBUG_READ_32B_OTHER        = 0x800E
DEBUG_SET_FORCE_CRC_CHECK   = 0x800F

DEBUG_ALL                   = (DEBUG_SET_SINGLETON_MODE,
                               DEBUG_BOOTLOADER_LOCK,
                               DEBUG_BOOTLOADER_UNLOCK,
                               DEBUG_READ_HID_THIS,
                               DEBUG_READ_HID_OTHER,
                               DEBUG_READ_32B_THIS,
                               DEBUG_READ_32B_OTHER,
                               DEBUG_SET_FORCE_CRC_CHECK)

CRC_DATA_LEN                = 16
FIRMWARE_UPDATE_DATA_LEN    = 50
MAX_SERIAL_LENGTH           = 32
DEVICE_INFO_MAGIC	    = 0xBEEFFACE
DEVICE_HEADER_VERSION       = 1


FIRMWARE_PAGE_SIZE          = 64
HID_EP_SIZE                 = 64  # TODO: Can this be read from report descriptor?
FLASH_SIZE                  = 256 * 1024
FLASH_ERASE_SIZE            = 256
APP_FW_START                = 8 * 1024
APP_FW_END                  = FLASH_SIZE - 4 * 1024
APP_FW_INFO                 = APP_FW_END - 4
APP_FW_LENGTH               = APP_FW_INFO- APP_FW_START


JUPITER_BOOTLOADER_USB_VID  = 0x28de
JUPITER_BOOTLOADER_USB_PID  = 0x1003
JUPITER_USB_PID             = 0x1204
JUPITER_USB_INTERFACE       = 2

CRCFUN   = crcmod.mkCrcFun(0x104C11DB7)
CRCALIGN = 4

def compute_crc(data, total_size=APP_FW_LENGTH):
    l = len(data)
    data = bytes(data) + bytes(0xFF for _ in range(0, total_size - len(data)))
    return CRCFUN(data, 0)

class DogBootloaderBadReply(Exception):
    pass

class DogBootloaderUpdateError(Exception):
    pass

class DogBootloaderTimeout(Exception):
    pass

class DogBootloaderVerifyError(Exception):
    pass

class MsgBadReply(Exception):
    pass

class Msg:
    def __init__(self, _id, _length):
        self.id     = _id
        self.length = _length

    def __bytes__(self):
        return bytes([self.id, self.length])

class MsgGetAttributes(Msg):
    def __init__(self, reply=None):
        self.id = ID_GET_ATTRIBUTES_VALUES
        self.length = 0

        if reply:
            attrib_layout = '<BI'
            header_layout = '<BB'
            header_len = struct.calcsize(header_layout)
            attrib_len = struct.calcsize(attrib_layout)

            self.id, self.length = struct.unpack(header_layout, reply[:header_len])
            self.attribs = []

            reply = reply[header_len:]
            for off in range(0, self.length, attrib_len):
                tag, value = struct.unpack(attrib_layout, reply[off:off + attrib_len])
                self.attribs += [(tag, value)]

class MsgRebootIntoISP(Msg):
    def __init__(self):
        self.id     = ID_REBOOT_INTO_ISP
        self.length = 4

class MsgUpdateStart(Msg):
    def __init__(self, blob_id=BLOB_ID_FIRMWARE):
        self.id = ID_FIRMWARE_UPDATE_START

        if blob_id == BLOB_ID_FIRMWARE:
            self.length = 0
            self.blob_id = b''
        else:
            self.length = struct.calcsize('<B')
            self.blob_id = struct.pack('<B', blob_id)

    def __bytes__(self):
        return Msg.__bytes__(self) + bytes(self.blob_id)


class MsgUpdateData(Msg):
    def __init__(self, data):
        self.id     = ID_FIRMWARE_UPDATE_DATA
        self.length = len(data)
        self.data   = data

    def __bytes__(self):
        return Msg.__bytes__(self) + bytes(self.data)

class MsgUpdateComplete(Msg):
    def __init__(self, crc):
        self.id     = ID_FIRMWARE_UPDATE_COMPLETE
        self.length = CRC_DATA_LEN
        self.crc    = struct.pack('<I', crc)

    def __bytes__(self):
        return Msg.__bytes__(self) + bytes(self.crc) + bytes(0x00 for i in range(4, CRC_DATA_LEN))

class MsgUpdateAck(Msg):
    def __init__(self, code=None, reply=None, offset=0):
        self.layout = '<BBIH'
        header_len = struct.calcsize(self.layout)
        ack_len    = header_len - 2

        self.id     = ID_FIRMWARE_UPDATE_ACK
        self.length = ack_len
        self.code   = code
        self.offset = offset

        if reply:
            assert len(reply) == HID_EP_SIZE

            self.id, self.length, self.offset, self.code = struct.unpack(self.layout,
                                                                         reply[:header_len])
            if self.id != ID_FIRMWARE_UPDATE_ACK:
                raise MsgBadReply("Invalid Update ACK ID")

            if not ack_len <= self.length <= HID_EP_SIZE - header_len:
                raise MsgBadReply("Invalid Update ACK size")

            if not self.code in (UPDATE_STATUS_OK, UPDATE_STATUS_BUSY, UPDATE_STATUS_ERROR):
                raise MsgBadReply("Invalid Update ACK status")

            # self.side_channel_data = reply[header_len : self.length]

    def __bytes__(self):
        return struct.pack(self.layout, self.id, self.length, self.offset, self.code)

class DogBootloaderProgressBar:
    def __init__(self, verbose, widgets, max_value=None):
        self.verbose = verbose

        if self.verbose:
            self.bar = progressbar.ProgressBar(widgets=widgets, max_value=max_value)

    def start(self):
        if self.verbose:
            self.bar.start()

    def update(self, value):
        if self.verbose:
            self.bar.update(value)

    def finish(self):
        if self.verbose:
            self.bar.finish()

class DogBootloaderEraseSpinner(DogBootloaderProgressBar):
    def __init__(self, verbose):
        widgets=['Erasing: ', progressbar.AnimatedMarker()]
        super(DogBootloaderEraseSpinner, self).__init__(verbose, widgets)

class DogBootloaderProgressBar(DogBootloaderProgressBar):
    def __init__(self, name, verbose, max_value):
        widgets=[name,
                 progressbar.Bar(left='[', right=']'),
                 ' ',
                 progressbar.DataSize(),
                 ' ',
                 progressbar.Percentage()
        ]
        super(DogBootloaderProgressBar, self).__init__(verbose, widgets, max_value)

if sys.platform == 'win32':
    def dog_enumerate(pid=JUPITER_USB_PID):
        return [d for d in hid.enumerate(JUPITER_BOOTLOADER_USB_VID, pid)
                if d['usage_page'] >= 0xFF00]
else:
    def dog_enumerate(pid=JUPITER_USB_PID):
        devs = hid.enumerate(JUPITER_BOOTLOADER_USB_VID, pid)

        if len(devs) > 1:
            devs = [d for d in devs if
                    d['interface_number'] == JUPITER_USB_INTERFACE]

        return devs

def dog_wait(pid, message):
    spinner = progressbar.ProgressBar(widgets=[message, progressbar.AnimatedMarker()])
    spinner.start()

    timeout = 10    # seconds
    delay   = 0.1
    dev     = None
    for i in range(int(timeout / delay)):
        dev = dog_enumerate(pid=pid)
        spinner.update(i)
        if dev:
            break;

        time.sleep(delay)

    spinner.finish()
    return dev


class DogBootloader:
    BOOTLOADER_REASON = {
        0x01 : "magic key combo",
        0x02 : "requested by the app",
        0x03 : "left/right handshake",
        0x0B : "bad app start address",
        0x0C : "bad app stack address",
        0x0D : "bad app CRC",
    }

    STATE = {
        0  : "idle",
        1  : "erasing",
        2  : "programming",
        3  : "programming CRC",
        4  : "error",
        5  : "resetting",
        6  : "CRC-ing",
        7  : "waiting OTHER",
        8  : "waiting OTHER CRC",
        9  : "resetting into ISP",
        10 : "reading blob OTHER",
        11 : "SPI loss of sync",
        12 : "get attributes",

        0xFE : "unknown",
        0xFF : "disconnected",
    }

    def __init__(self, verbose=False, minimal_init=False):
        if minimal_init:
            self.hiddev = hid.Device(JUPITER_BOOTLOADER_USB_VID,
                                     JUPITER_BOOTLOADER_USB_PID)
        else:
            #
            # App firmware would have three HID interfaces,
            # so we need to select the right one. Ours is the one with
            # vendor usage page, so select it.
            #

            dev = dog_enumerate()
            if dev:
                print('Looks like we are running an app.')

                with hid.Device(path=dev[0]['path']) as self.hiddev:
                    self._reboot_into_isp()

                dog_wait(pid=JUPITER_BOOTLOADER_USB_PID,
                         message='Switching to ISP mode: ')

                self.hiddev = hid.Device(JUPITER_BOOTLOADER_USB_VID,
                                         JUPITER_BOOTLOADER_USB_PID)

            else:
                self.hiddev = hid.Device(JUPITER_BOOTLOADER_USB_VID,
                                         JUPITER_BOOTLOADER_USB_PID)
                self.reset()
                time.sleep(1)

        self.verbose = verbose

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def close(self):
        self.hiddev.close()

    def reset(self):
        #
        # If device is already in the bootloader, sending
        # ID_REBOOT_INTO_ISP will reset its state similar to USB
        # reset.
        #
        # Not using libusb to issue a reset because:
        #
        #  1. It doesn't work on Windows. You can use libusb on
        #  Windows, but it requires dissociateing the device from hid
        #  driver, which we can't do
        #
        #  2. USB reset can't be used with libhidapi-libusb variant
        #  since libusb has no mechanism to be notified of external
        #  (to libhidapi-libusb internals) USB resets which break any
        #  outstanding USB deivce structs that were created prior.
        #
        self._reboot_into_isp()

    def info(self):
        print('Found a D21 bootloader device')
        print('----------------------------')
        info = hid.enumerate(JUPITER_BOOTLOADER_USB_VID,
                             JUPITER_BOOTLOADER_USB_PID)[0]

        print('Path: {}'.format(info['path'].decode()))
        print('VID: 0x{:x}'.format(info['vendor_id']))
        print('PID: 0x{:x}'.format(info['product_id']))
        print('Firmware Build Time: 0x{:x} ({} UTC)' \
              .format(self.firmware_build_time,
                      datetime.datetime.utcfromtimestamp(self.firmware_build_time)))

        for i, position in enumerate(['Primary', 'Secondary']):
            print('\n ** {} Unit **'.format(position))
            print('Stored unit serial: {}'.format(self.unit_serial[i]))
            print('Stored hardware ID: {}'.format(self.hardware_id[i]))
            print('MCU unique ID: {:08X} {:08X} {:08X} {:08X}'
                  .format(# BE ordering
                          self.unique_id[i][0],
                          self.unique_id[i][1],
                          self.unique_id[i][2],
                          self.unique_id[i][3]))
            print('MCU user row: {:02X} {:02X} {:02X} {:02X} {:02X} {:02X} {:02X} {:02X}'
                  .format(*self.user_row[i]))

            print('MCU bootloader mode reason: {}'.format(self.bootloader_reason[i]))
            print('MCU state: {}'.format(self.state[i]))

        print('----------------------------')


    def send(self, msg):
        msg   = bytes(msg)
        zeros = bytes(0x00 for i in range(len(msg), HID_EP_SIZE))

        self.hiddev.send_feature_report(bytes([0x00]) + msg + zeros)

    def recv(self):
        msg = self.hiddev.get_feature_report(0x00, HID_EP_SIZE + 1)
        if msg[0] != 0x00 or len(msg) != HID_EP_SIZE + 1:
            raise DogBootloaderBadReply("Invalid report ID")

        if msg[1] == ID_FIRMWARE_UPDATE_ACK:
            return MsgUpdateAck(reply=msg[1:])

        return MsgGetAttributes(reply=msg[1:])

    def wait(self, retries=50000):
        for _ in range(0, retries):
            ack = self.recv()

            if ack.code == UPDATE_STATUS_OK:
                return
            if ack.code == UPDATE_STATUS_ERROR:
                raise DogBootloaderUpdateError()
        else:
            raise DogBootloaderTimeout('ACK timeout')

    def _send_feature_report(self, msg):
        zeros = [0] * (64 - len(msg))
        self.hiddev.send_feature_report(bytes([0x00] + msg + zeros))

    def _get_feature_report(self):
        return self.hiddev.get_feature_report(0x00, 65)

    def _poll_ack(self):
        retries = 20000
        max_len = 2

        spinner = DogBootloaderEraseSpinner(self.verbose)
        try:
            spinner.start()

            for i in range(0, retries):
                spinner.update(i)

                report = self._get_feature_report()

                if len(report) < 3:
                    raise DogBootloaderBadReply("Invalid length")

                len_  = report[2]

                if len_ != 6 or len(report) < len_ + 3: #FIXME magic numbers
                    raise DogBootloaderBadReply("Invalid length")

                id_   = report[0]
                type_ = report[1]

                if id_ != 0x00:
                    raise DogBootloaderBadReply("Invalid report ID")


                _, code = struct.unpack('<IH', bytes(report[3:3 + len_]))

                if type_ == ID_FIRMWARE_UPDATE_ACK:
                    if   code == UPDATE_STATUS_OK:
                        break
                    elif code == UPDATE_STATUS_BUSY:
                        continue
                    elif code == UPDATE_STATUS_ERROR:
                        raise DogBootloaderUpdateError()
                    else:
                        raise DogBootloaderBadReply("Invalid update status")
                else:
                    raise DogBootloaderBadReply("Invalid header type")
            else:
                raise DogBootloaderTimeout('ACK timeout')
        finally:
            spinner.finish()

    def _send_data(self, data):
        msg = [
            ID_FIRMWARE_UPDATE_DATA,
            len(data)
        ] + data

        self._send_feature_report(msg)

    def _complete_update(self, crc):
        filler = [0x5a] * (CRC_DATA_LEN - 4)
        msg = [
            ID_FIRMWARE_UPDATE_COMPLETE,
            CRC_DATA_LEN
        ] + list(struct.pack('<I', crc)) + filler

        self._send_feature_report(msg)

    def _reboot_into_isp(self):
        self._send_feature_report([ID_REBOOT_INTO_ISP,
                                   0x04,
                                   0x00,
                                   0x00,
                                   0x00,
                                   0x00])

    def _read_debug_data(self, code, size=APP_FW_LENGTH, offset=0, verbose=False):

        bar = DogBootloaderProgressBar('Verifying:   '.format(size), verbose, size)

        self._send_feature_report([ID_FIRMWARE_UPDATE_ACK,
                                   6,
                                   *list(struct.pack('<I', offset)),
                                   *list(struct.pack('<H', code))])
        off_ = 3 + 6
        data = bytes()
        read = 0
        while True:
            report = self._get_feature_report()

            len_   = report[2] - 6
            id_    = report[0]
            type_  = report[1]

            if not len_:
                break

            chunk = min(len_, size)
            size -= chunk
            read += chunk
            data += report[off_ : off_ + chunk]
            bar.update(read)

            if not size:
                break

        bar.finish()

        return data

    def set_singleton_mode(self):
        msg = MsgUpdateAck(code=DEBUG_SET_SINGLETON_MODE)
        self.send(msg)

    def set_force_crc_check(self, on=True):
        msg = MsgUpdateAck(code=DEBUG_SET_FORCE_CRC_CHECK, offset=int(on))
        self.send(msg)

    def do_crc_fixup(self, valid=True):
        if valid:
            crc = 0x00000000
            blobs = [BLOB_ID_FIRMWARE_CRC_THIS, BLOB_ID_FIRMWARE_CRC_OTHER]
        else:
            #
            # When breaking CRC we only care about the primary
            #
            crc = 0xFFFFFFFF
            blobs = [BLOB_ID_FIRMWARE_CRC_THIS]

        for blob_id in blobs:
            blob = self.download_blob(blob_id)
            self.upload_blob(blob_id, blob, crc=crc)

    def do_bootloader_lock(self, on):
        if on:
            msg = MsgUpdateAck(code=DEBUG_BOOTLOADER_LOCK)
        else:
            msg = MsgUpdateAck(code=DEBUG_BOOTLOADER_UNLOCK)
        self.send(msg)

    def parse_hid(self, blob):
        fmt = '<BBIIIIIB'
        size = struct.calcsize(fmt)
        uid = [0, 0, 0, 0]

        epoch, state, crc, *uid, reason = struct.unpack(fmt, blob[:size])
        user_row = blob[size : size + 8]

        return epoch, state, crc, uid, reason, user_row

    @property
    def state(self):
        h = self._read_debug_data(DEBUG_READ_HID_THIS)
        _, state_this, _, _, _, _ = self.parse_hid(h)

        h = self._read_debug_data(DEBUG_READ_HID_OTHER)
        _, state_other, _, _, _, _ = self.parse_hid(h)

        return self.STATE[state_this], self.STATE[state_other]

    @property
    def unique_id(self):
        h = self._read_debug_data(DEBUG_READ_HID_THIS)
        _, _, _, uid_this, _, _ = self.parse_hid(h)

        h = self._read_debug_data(DEBUG_READ_HID_OTHER)
        _, _, _, uid_other, _, _ = self.parse_hid(h)

        return uid_this, uid_other

    @property
    def user_row(self):
        h = self._read_debug_data(DEBUG_READ_HID_THIS)
        _, _, _, _, _, user_row_this = self.parse_hid(h)

        h = self._read_debug_data(DEBUG_READ_HID_OTHER)
        _, _, _, _, _, user_row_other = self.parse_hid(h)

        return user_row_this, user_row_other

    @property
    def bootloader_reason(self):
        h = self._read_debug_data(DEBUG_READ_HID_THIS)
        _, _, _, _, code, _ = self.parse_hid(h)
        reason_this = self.BOOTLOADER_REASON.get(code, "unknown")

        h = self._read_debug_data(DEBUG_READ_HID_OTHER)
        _, _, _, _, code, _ = self.parse_hid(h)
        reason_other = self.BOOTLOADER_REASON.get(code, "unknown")

        return reason_this, reason_other

    def parse_device_info_blob(self, blob):
        fmt = '<IIII'
        size = struct.calcsize(fmt)
        crc, magic, ver, hw_id = struct.unpack(fmt, blob[:size])
        if magic != DEVICE_INFO_MAGIC or ver != DEVICE_HEADER_VERSION:
            return crc, magic, ver, hw_id, 'None'
        blob = blob[size:]

        serial_bytes = blob[:MAX_SERIAL_LENGTH]
        if serial_bytes.find(b'\00') != -1:
            try:
                serial = serial_bytes.split(b'\x00')[0].decode('ascii')
            except:
                serial = None
        else:
            serial = None

        return crc, magic, ver, hw_id, serial

    @property
    def firmware_build_time(self):
        msg = MsgGetAttributes()
        self.send(msg)

        report = self.recv()

        assert isinstance(report, MsgGetAttributes)

        for tag, value in report.attribs:
            if tag == HID_ATTRIB_FIRMWARE_BUILD_TIME:
                return value

        return None

###############################################################################
## Unit Serial
###############################################################################
    @property
    def unit_serial(self):
        blob = self.download_blob(BLOB_ID_DEVICE_INFO_THIS)
        _, _, _, _, serial_this = self.parse_device_info_blob(blob)

        blob = self.download_blob(BLOB_ID_DEVICE_INFO_OTHER)
        _, _, _, _, serial_other = self.parse_device_info_blob(blob)

        return serial_this, serial_other

    @unit_serial.setter
    def unit_serial(self, serial):
        if not isinstance(serial, tuple):
            serial = serial, serial

        for sn, blob_id in zip(serial, [BLOB_ID_DEVICE_INFO_THIS, BLOB_ID_DEVICE_INFO_OTHER]):
            if sn == None:
                continue

            assert len(sn) <= MAX_SERIAL_LENGTH
            blob = self.download_blob(blob_id)
            _, _, _, hw_id, _ = self.parse_device_info_blob(blob)
            blob = struct.pack('<IIII', 0, DEVICE_INFO_MAGIC,
                               DEVICE_HEADER_VERSION, hw_id) + sn.encode('ascii') + b'\x00'
            self.upload_blob(blob_id, blob)

###############################################################################
## HW ID
###############################################################################
    @property
    def hardware_id(self):
        blob = self.download_blob(BLOB_ID_DEVICE_INFO_THIS)
        _, _, _, hw_id_this, _ = self.parse_device_info_blob(blob)

        blob = self.download_blob(BLOB_ID_DEVICE_INFO_OTHER)
        _, _, _, hw_id_other, _ = self.parse_device_info_blob(blob)

        return hw_id_this, hw_id_other

    @hardware_id.setter
    def hardware_id(self, hw_id):
        if not isinstance(hw_id, tuple):
            hw_id = hw_id, hw_id

        for _id, blob_id in zip(hw_id, [BLOB_ID_DEVICE_INFO_THIS, BLOB_ID_DEVICE_INFO_OTHER]):
            blob = self.download_blob(blob_id)
            _, _, _, _, serial = self.parse_device_info_blob(blob)
            blob = struct.pack('<IIII', 0, DEVICE_INFO_MAGIC,
                               DEVICE_HEADER_VERSION, _id) + serial.encode('ascii') + b'\x00'
            self.upload_blob(blob_id, blob)

###############################################################################
## MTE Blob
###############################################################################
    @property
    def mte_blob(self):
        blob = self.download_blob(BLOB_ID_DEVICE_BLOB_THIS)
        mte_blob_this = self.parse_mte_blob(blob)

        blob = self.download_blob(BLOB_ID_DEVICE_BLOB_OTHER)
        mte_blob_other = self.parse_mte_blob(blob)

        return mte_blob_this, mte_blob_other

    @mte_blob.setter
    def mte_blob(self, mte_blob_strs):
        if not isinstance(mte_blob_strs, tuple):
            mte_blob_strs = mte_blob_strs, mte_blob_strs

        for mte_blob_str, blob_id in zip(mte_blob_strs, [BLOB_ID_DEVICE_BLOB_THIS, BLOB_ID_DEVICE_BLOB_OTHER]):
            if mte_blob_str != None:
                blob_bytes = mte_blob_str.encode('ascii')
                dummy_crc = b'\xFF\xFF\xFF\xFF'
                 # First byte is 0 if blob data is present.  Add null termination
                blob_bytes = dummy_crc + b'\x00' + blob_bytes + b'\x00'

                self.upload_blob(blob_id, blob_bytes)

    def erase(self, blob_id=BLOB_ID_FIRMWARE):
        msg = MsgUpdateStart(blob_id)
        self.send(msg)
        self._poll_ack()

    def upload_blob(self, blob_id, data, crc=None):
        assert blob_id != BLOB_ID_FIRMWARE

        data = list(data)
        self.erase(blob_id=blob_id)

        if blob_id == BLOB_ID_FIRMWARE_CRC_THIS or \
           blob_id == BLOB_ID_FIRMWARE_CRC_OTHER:
            data = data[:-4]
        else:
            #
            # Clear any CRC data
            #
            data[0] = 0xff
            data[1] = 0xff
            data[2] = 0xff
            data[3] = 0xff

        off   = 0
        chunk = data[off : off + FIRMWARE_UPDATE_DATA_LEN]
        while chunk:
            self._send_data(list(chunk))
            off  += FIRMWARE_UPDATE_DATA_LEN
            chunk = data[off : off + FIRMWARE_UPDATE_DATA_LEN]

        self._complete_update(compute_crc(data[4:], FLASH_ERASE_SIZE - 4) \
                              if crc is None else crc)

    def download_blob(self, blob_id, size=FLASH_ERASE_SIZE):
        if blob_id == BLOB_ID_FIRMWARE or \
           blob_id == BLOB_ID_FIRMWARE_OTHER:
            offset = APP_FW_START
            verbose = self.verbose
        elif blob_id == BLOB_ID_FIRMWARE_CRC_THIS or \
             blob_id == BLOB_ID_FIRMWARE_CRC_OTHER:
            offset = APP_FW_END - FLASH_ERASE_SIZE
            verbose = False
        else:
            offset = APP_FW_END
            verbose = False

        if blob_id == BLOB_ID_DEVICE_INFO_OTHER  or \
           blob_id == BLOB_ID_DEVICE_BLOB_OTHER  or \
           blob_id == BLOB_ID_FIRMWARE_CRC_OTHER or \
           blob_id == BLOB_ID_FIRMWARE_OTHER:
            cmd = DEBUG_READ_32B_OTHER
        else:
            cmd = DEBUG_READ_32B_THIS

        if blob_id == BLOB_ID_DEVICE_BLOB_THIS or \
           blob_id == BLOB_ID_DEVICE_BLOB_OTHER:
            # Blob is right after device info
            offset += FLASH_ERASE_SIZE

        data = b''
        for off in range(0, size, 32):
            data += self._read_debug_data(cmd, size=32, offset=offset + off,
                                          verbose=verbose)

        return data

    def upload_firmware(self, name, verify=False):
        with open(name, "rb") as f:
            blob = f.read()

        with open(name, "rb") as f:
            self.erase()

            bar = DogBootloaderProgressBar('Programming: ', self.verbose, len(blob))
            chunk = f.read(FIRMWARE_UPDATE_DATA_LEN)
            l = 0

            while chunk:
                self._send_data(list(chunk))
                l += len(chunk)
                bar.update(l)
                chunk = f.read(FIRMWARE_UPDATE_DATA_LEN)

            self._complete_update(compute_crc(blob))

            bar.finish()

        if verify:
            programmed = self.download_firmware(len(blob))
            if programmed != blob:
                raise DogBootloaderVerifyError()

    def download_firmware(self, size=APP_FW_LENGTH):
        data = self.download_blob(BLOB_ID_FIRMWARE, size)
        return data[:size]

    def reboot(self):
        msg = [
            ID_FIRMWARE_UPDATE_REBOOT,
        ]

        self._send_feature_report(msg)

    def parse_mte_blob(self, blob_data):

        fmt = '<I'
        size = struct.calcsize(fmt)
        crc = struct.unpack(fmt, blob_data[:size])[0]

        blob_data = blob_data[size:]
        valid = blob_data[0] == 0

        computed_crc = compute_crc(blob_data, total_size=len(blob_data))

        if crc != computed_crc or not valid:
            return None
        else:
            return blob_data[1:].split(b'\x00')[0].decode('ascii')

    def set_mte_blob(self, blob_id, blob_str):
        blob_bytes = blob_str.encode('ascii')
        dummy_crc = b'\xFF\xFF\xFF\xFF'
        # First byte is 0 if blob data is present.  Add null termination
        blob_bytes = dummy_crc + b'\x00' + blob_bytes + b'\x00'

        self.upload_blob(blob_id, blob_bytes)

@click.group()
def cli():
    pass

@cli.command()
@click.argument('firmware', type=click.Path(exists=True,
                                            dir_okay=False))
@click.option('--verify/--no-verify', default=False,
              help='Read programmed image back and verify it')
@click.option('--singleton-mode/--no-singleton-mode', default=False,
              help='Ignore secondary MCU when using the device')
def program(firmware, verify, singleton_mode):
    with DogBootloader(verbose=True) as bootloader:
        if singleton_mode:
            bootloader.set_singleton_mode()

        bootloader.upload_firmware(firmware, verify=verify)
        bootloader.reboot()

    if dog_wait(pid=JUPITER_USB_PID,
                message='Waiting for app to enumerate: '):
        print('SUCCESS')
    else:
        print('TIMEOUT')


@cli.command()
@click.option('--singleton-mode/--no-singleton-mode', default=False,
              help='Ignore secondary MCU when using the device')
def erase(singleton_mode):
    with DogBootloader(verbose=True) as bootloader:
        if singleton_mode:
            bootloader.set_singleton_mode()

        bootloader.erase()
    print('SUCCESS')

@cli.command()
def addcrc():
    with DogBootloader(verbose=True) as bootloader:
        bootloader.do_crc_fixup(valid=True)
    print('SUCCESS')

@cli.command()
def lock():
    with DogBootloader(verbose=True) as bootloader:
        bootloader.do_bootloader_lock(on=True)
    print('SUCCESS')

@cli.command()
def unlock():
    with DogBootloader(verbose=True) as bootloader:
        bootloader.do_bootloader_lock(on=False)
    print('SUCCESS')

@cli.command(name='getinfo')
def info():
    with DogBootloader(verbose=True) as bootloader:
        bootloader.info()
    print('SUCCESS')

@cli.command(name='gethwid')
@click.option('--primary/--secondary', default=True)
def get_hwid(primary):
    with DogBootloader(verbose=True) as bootloader:
        if primary:
            print ('HW ID: {}'.format(bootloader.hardware_id[0]))
        else:
            print ('HW ID: {}'.format(bootloader.hardware_id[1]))

    print('SUCCESS')

@cli.command(name='sethwid')
@click.option('--primary/--secondary', default=True)
@click.argument('hardware_id', type=int)
def set_hardware_id(primary, hardware_id):
    with DogBootloader(verbose=True) as bootloader:
        hwid_primary, hwid_secondary = bootloader.hardware_id

        if primary:
            hwid_primary = hardware_id
        else:
            hwid_secondary = hardware_id

        bootloader.hardware_id = (hwid_primary, hwid_secondary)
    print('SUCCESS')

@cli.command(name='getserial')
@click.option('--primary/--secondary', default=True)
def get_serial(primary):
    with DogBootloader(verbose=True) as bootloader:
        if primary:
            print ('Serial: {}'.format(bootloader.unit_serial[0]))
        else:
            print ('Serial: {}'.format(bootloader.unit_serial[1]))

    print('SUCCESS')

@cli.command(name='setserial')
@click.option('--primary/--secondary', default=True)
@click.argument('serial', type=str)
def set_serial(primary, serial):
    with DogBootloader(verbose=True) as bootloader:
        serial_primary, serial_secondary = bootloader.unit_serial
        if primary:
            serial_primary = serial
        else:
            serial_secondary = serial
        bootloader.unit_serial = (serial_primary, serial_secondary)
    print('SUCCESS')

@cli.command()
@click.option('--primary/--secondary', default=True)
def getblob(primary):
    with DogBootloader(verbose=True) as bootloader:
        if primary:
            blob_str = bootloader.mte_blob[0]
        else:
            blob_str = bootloader.mte_blob[1]

    print('BLOB DATA: "{}"'.format(blob_str))
    print('SUCCESS')

@cli.command()
@click.option('--primary/--secondary', default=True)
@click.argument('blob_str', type=str)
def setblob(primary, blob_str):
    with DogBootloader(verbose=True) as bootloader:
        mte_blob_str_this, mte_blob_str_other = bootloader.mte_blob

        if primary:
            mte_blob_str_this = blob_str
        else:
            mte_blob_str_other = blob_str

        bootloader.mte_blob = (mte_blob_str_this, mte_blob_str_other)
    print('SUCCESS')

@cli.command(name='reset')
def cmd_reset():
    with DogBootloader(verbose=True) as bootloader:
        bootloader.reboot()
    print('SUCCESS')

if __name__ == '__main__':
    try:
        cli()
    except hid.HIDException as e:
        print(e)
    except DogBootloaderTimeout:
        print('Timeout waiting for Flash erase')
    except DogBootloaderVerifyError:
        print('Programmed data mismatch')
