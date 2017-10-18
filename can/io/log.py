from can.listener import Listener
import datetime
import time
from can.message import Message

CAN_MSG_EXT = 0x80000000


class canutilsLogReader(object):
    """
    Iterator of CAN messages from a .log Logging File (candump -L).

    Only CAN messages are supported (no Errorframes).
    """

    def __init__(self, filename):
        self.fp = open(filename, "r")

    def __iter__(self):
        for line in self.fp:
            temp = line.strip()
            if len(temp) > 0:
                (timestamp, bus, frame) = temp.split()
                timestamp = float(timestamp[1:-1])
                (canId, data) = frame.split("#")
                canId = int(canId, 16)
                dlc = len(data) / 2
                dataBin = bytearray()
                for i in range(0, dlc):
                    dataBin.append(int(data[i * 2:(i + 1) * 2], 16))

                msg = Message(timestamp=timestamp, arbitration_id=canId & 0x1FFFFFFF,
                              extended_id=bool(canId & CAN_MSG_EXT), is_remote_frame=False, dlc=dlc, data=dataBin)
                yield msg


class canutilsLogWriter(Listener):
    """Logs CAN data to an ASCII log file (.log)
    compatible to candump -L """

    def __init__(self, filename, channel="vcan0"):
        self.channel = channel
        self.started = time.time()
        self.log_file = open(filename, "w")

    def stop(self):
        """Stops logging and closes the file."""
        if self.log_file is not None:
            self.log_file.close()
            self.log_file = None

    def on_message_received(self, msg):
        if msg.is_error_frame:
            return

        timestamp = msg.timestamp
        if timestamp >= self.started:
            timestamp -= self.started

        if self.log_file is not None:
            if msg.is_remote_frame:
                data = []
            else:
                data = ["{:02X}".format(byte) for byte in msg.data]
            if msg.is_extended_id:
                self.log_file.write("(%f)\tvcan0\t%07X#%s\n" % (msg.timestamp, msg.arbitration_id, "".join(data)))
            else:
                self.log_file.write("(%f)\tvcan0\t%03X#%s\n" % (msg.timestamp, msg.arbitration_id, "".join(data)))



