# coding: utf-8
# TODO better documentation
# TODO better documentation for rst doc
"""
Name:        slcan.py
Purpose:     Interface for slcan compatible interfaces (win32/linux).
             Note: Linux users can use slcand/socketcan as well.

Copyright:   2017 Eduard Bröcker
             2017 - 2018 Felix Divo
             2018 Brian Thorne
             2018 Boris Wenzlaff

This file is part of python-can <https://github.com/hardbyte/python-can/>.

python-can is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
any later version.

python-can is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with python-can. If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import absolute_import

import time
import logging

import io
import serial

from can import BusABC, Message

logger = logging.getLogger(__name__)


class SlcanBus(BusABC):
    # TODO better documentation
    """
    slcan interface
    """

    # the supported bitrates and their commands
    _BITRATES = {
        10000:      'S0',
        20000:      'S1',
        50000:      'S2',
        100000:     'S3',
        125000:     'S4',
        250000:     'S5',
        500000:     'S6',
        750000:     'S7',
        1000000:    'S8',
        83300:      'S9'
    }

    # TODO set back to 2 sec.
    # sleep time after initialization of the serial interface in seconds.
    _SLEEP_AFTER_SERIAL_OPEN = 0

    def __init__(self, channel, serial_baudrate=115200, timeout=0.1, bitrate=10000, **kwargs):
        """
        :param string channel:
            The serial device to open. For example "/dev/ttyS1" or
            "/dev/ttyUSB0" on Linux or "COM1" on Windows systems.

        :param int serial_baudrate:
            Baud rate of underlying serial or usb device in bit/s (default 115200).

            .. note:: Some serial port implementations don't care about the baud
                      rate.

        :param float timeout:
            Timeout for the serial device in seconds (default 0.1). The
            timeout will be used for sending and receiving.

            .. note:: The receiving timeout isn't implemented correctly.

        :param int bitrate:
            Bitrate in bits/s for the CAN communication (default 10000).
        """

        if not channel:
            raise ValueError("Must specify a serial port.")

        self.channel_info = "SLCAN interface on: " + channel
        self.serial_timeout = timeout
        self.bitrate = bitrate

        if not (self.bitrate in self._BITRATES):
            raise ValueError("Invalid bitrate for CAN communication, choose one of " +
                             (', '.join(self._BITRATES)) + '.')

        self.ser = serial.Serial(port=channel, baudrate=serial_baudrate, timeout=self.serial_timeout,
                                 write_timeout=self.serial_timeout)
        self.serial_port = io.TextIOWrapper(io.BufferedRWPair(self.ser, self.ser, 1), newline='\r', line_buffering=True)
        time.sleep(self._SLEEP_AFTER_SERIAL_OPEN)
        self.__init_can_device()
        super(SlcanBus, self).__init__(channel, **kwargs)

    def __write(self, msg, timeout=None):
        # TODO implement timeout
        # TODO exception handling -> can.CanError
        if not msg.endswith('\r'):
            msg += '\r'
        self.serial_port.write(msg)

    def __init_can_device(self):
        # TODO init procedure, set bitrate open chennel, clean buffer
        self.__write('O')

    def shutdown(self):
        """
        Close the serial interface and the CAN channel on the device.
        """
        self.__write('C')
        self.ser.close()

    # TODO implement SerialTimeoutException -> CanError
    # TODO implement timeout correctly
    def send(self, msg, timeout=None):
        """
        Send a message over the serial device.

        :param can.Message msg:
            Message to send.

        :param float timeout:
            Timeout for sending messages in seconds, if no timeout is set the default from the constructor will be used.

        :raises: CanError: Will be raised on timeout while sending.
        """

        if msg.is_remote_frame:
            if msg.is_extended_id:
                send_msg = "R%08X0" % (msg.arbitration_id)
            else:
                send_msg = "r%03X0" % (msg.arbitration_id)
        else:
            if msg.is_extended_id:
                send_msg = "T%08X%d" % (msg.arbitration_id, msg.dlc)
            else:
                send_msg = "t%03X%d" % (msg.arbitration_id, msg.dlc)

            for i in range(0, msg.dlc):
                send_msg += "%02X" % msg.data[i]
        self.__write(send_msg, timeout)

    # TODO implement timeout on receive
    # TODO fix BUG with timeout, no reset of the timeout is implmented
    def recv(self, timeout=None):
        """
        Read a message from the serial device.

            .. note:: The message timestamp will be set by the framework, timestamps of the protocol are not supported.

        :param timeout:
            Timeout for receiving a message in seconds. If the timeout parameter not set,
            the default value from the constructor will be used. With timeout = None it
            will block until a message is read.

        :returns:
            Received message.

        :rtype:
            can.Message
        """

        if timeout is not None:
            self.ser.timeout = timeout

        can_id = None
        remote = False
        extended = False
        frame = []
        read_line = self.serial_port.readline()
        if not read_line:
            return None
        else:
            if read_line[0] == 'T':
                # extended frame
                can_id = int(read_line[1:9], 16)
                dlc = int(read_line[9])
                extended = True
                for i in range(0, dlc):
                    frame.append(int(read_line[10 + i * 2:12 + i * 2], 16))
            elif read_line[0] == 't':
                # normal frame
                can_id = int(read_line[1:4], 16)
                dlc = int(read_line[4])
                for i in range(0, dlc):
                    frame.append(int(read_line[5 + i * 2:7 + i * 2], 16))
            elif read_line[0] == 'r':
                # remote frame
                can_id = int(read_line[1:4], 16)
                remote = True
            elif read_line[0] == 'R':
                # remote extended frame
                can_id = int(read_line[1:9], 16)
                extended = True
                remote = True

            if can_id is not None:
                return Message(arbitration_id=can_id,
                               extended_id=extended,
                               timestamp=time.time(),   # Better than nothing...
                               is_remote_frame=remote,
                               dlc=dlc,
                               data=frame)
            else:
                return None
