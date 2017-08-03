import socket
import struct
import os

if not hasattr(socket, 'CAN_ISOTP'):
    if os.name == 'nt':
        raise NotImplementedError("This module cannot be used on Windows")
    else:
        raise NotImplementedError("Your version of Python does not offer support for CAN ISO-TP protocol. Support have been added since Python 3.7 on Linux build > 2.6.15.")

def check_is_socket(s):
    if not isinstance(s, socket.socket):
        raise ValueError("Given value is not a socket.")

class opts:
    SOL_CAN_ISOTP       = socket.SOL_CAN_BASE + socket.CAN_ISOTP
    CAN_ISOTP_OPTS      = 1
    CAN_ISOTP_RECV_FC   = 2
    CAN_ISOTP_TX_STMIN  = 3
    CAN_ISOTP_RX_STMIN  = 4
    CAN_ISOTP_LL_OPTS   = 5

    class flags:
        LISTEN_MODE     = 0x001
        EXTEND_ADDR     = 0x002
        TX_PADDING      = 0x004
        RX_PADDING      = 0x008
        CHK_PAD_LEN     = 0x010
        CHK_PAD_DATA    = 0x020
        HALF_DUPLEX     = 0x040
        FORCE_TXSTMIN   = 0x080
        FORCE_RXSTMIN   = 0x100
        RX_EXT_ADDR     = 0x200

    class recv_fc:
        stmin = None;
        bs = None;
        wftmax = None;

        @classmethod
        def read(cls, s):
            check_is_socket(s)
            o = cls()
            opt = s.getsockopt(opts.SOL_CAN_ISOTP, opts.CAN_ISOTP_RECV_FC,3)

            (o.bs, o.stmin, o.wftmax) = struct.unpack("=BBB", opt)
            return o

        @classmethod
        def write(cls, s, bs=None, stmin=None, wftmax=None):
            check_is_socket(s)
            o = cls.read(s);
            if bs != None:
                if not isinstance(bs, int) or bs<0 or bs>0xFF:
                    raise ValueError("bs must be a valid interger between 0 and 255")
                o.bs = bs

            if stmin != None:
                if not isinstance(stmin, int) or stmin<0 or stmin>0xFF:
                    raise ValueError("stmin must be a valid interger between 0 and 255")
                o.stmin = stmin

            if wftmax != None:
                if not isinstance(wftmax, int) or wftmax<0 or wftmax>0xFF:
                    raise ValueError("wftmax must be a valid interger between 0 and 255")
                o.wftmax = wftmax

            opt = struct.pack("=BBB", o.bs, o.stmin, o.wftmax)
            s.setsockopt(opts.SOL_CAN_ISOTP, opts.CAN_ISOTP_RECV_FC, opt)
            return o

        def __repr__(self):
            return "<OPTS_RECV_FC: bs=%d, stmin=%d, wftmax=%d>" % (self.bs, self.stmin, self.wftmax)
