import socket as socket_module
import struct
import os

if not hasattr(socket_module, 'CAN_ISOTP'):
    if os.name == 'nt':
        raise NotImplementedError("This module cannot be used on Windows")
    else:
        raise NotImplementedError("Your version of Python does not offer support for CAN ISO-TP protocol. Support have been added since Python 3.7 on Linux build > 2.6.15.")

def assert_is_socket(s):
    if not isinstance(s, socket_module.socket):
        raise ValueError("Given value is not a socket.")

mtu=4095

class socket:
    def __init__(self, timeout=0.1):
        self.interface = None
        self.rxid = None
        self.txid = None
        self.bound = False
        self.closed = False
        self._socket = socket_module.socket(socket_module.AF_CAN, socket_module.SOCK_DGRAM,socket_module.CAN_ISOTP)
        if timeout is not None and timeout>0:
            self._socket.settimeout(timeout)

    def send(self, *args, **kwargs):
        if not self.bound:
            raise RuntimeError("bind() must be called before using the socket")
        return self._socket.send(*args, **kwargs)

    def recv(self, n=mtu):
        if not self.bound:
            raise RuntimeError("bind() must be called before using the socket")
        try:
            return self._socket.recv(n)
        except socket_module.timeout:
            return None
        except:
            raise

    def set_ll_opts(self, n):
        if self.bound:
            raise RuntimeError("Options must be set before calling bind()")
        return opts.linklayer.write(self._socket, *args, **kwargs)

    def set_opts(self, *args, **kwargs):
        if self.bound:
            raise RuntimeError("Options must be set before calling bind()")
        return opts.general.write(self._socket, *args, **kwargs)

    def set_fc_opts(self, *args, **kwargs):
        if self.bound:
            raise RuntimeError("Options must be set before calling bind()")
        return opts.flowcontrol.write(self._socket, *args, **kwargs)

    def bind(self, interface, rxid, txid):
        self.interface=interface
        self.rxid=rxid
        self.txid=txid
        self._socket.bind((interface, rxid, txid))
        self.bound=True

    def fileno(self):
        return self._socket.fileno()

    def close(self, *args, **kwargs):
        v = self._socket.close(*args, **kwargs)
        self.bound = False
        self.closed = True
        return v

    def __delete__(self):
        if isinstance(_socket, socket_module.socket):
            self._socket.close()
            self._socket = None

    def __repr__(self):
        if self.bound:
            return "<ISO-TP Socket: %s, Rx:0x%x - Tx:0x%x>" % (self.interface, self.rxid, self.txid)
        else:
            status = "Closed" if self.closed else "Unbound"
            return "<%s ISO-TP Socket at 0x%s>" % (status, hex(id(self)))


class opts:
    SOL_CAN_BASE        = socket_module.SOL_CAN_BASE if hasattr(socket_module, 'SOL_CAN_BASE') else 100
    SOL_CAN_ISOTP       =  SOL_CAN_BASE + socket_module.CAN_ISOTP
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


    class general:
        struct_size = 4+4+1+1+1+1

        def __init__(self):
            self.optflag = None
            self.frame_txtime = None
            self.ext_address = None
            self.txpad = None
            self.rxpad = None
            self.rx_ext_address = None

        
        @classmethod
        def read(cls, s):
            assert_is_socket(s)
            o = cls()
            opt = s.getsockopt(opts.SOL_CAN_ISOTP, opts.CAN_ISOTP_OPTS,cls.struct_size)

            (o.optflag, o.frame_txtime, o.ext_address, o.txpad, o.rxpad, o.rx_ext_address) = struct.unpack("=LLBBBB", opt)
            return o


        @classmethod
        def write(cls, s, optflag=None, frame_txtime=None, ext_address=None, txpad=None, rxpad=None, rx_ext_address=None,   ):
            assert_is_socket(s)
            o = cls.read(s);

            if optflag != None:
                if not isinstance(optflag, int) or optflag<0 or optflag>0xFFFFFFFF:
                    raise ValueError("optflag must be a valid 32 unsigned integer")
                o.optflag = optflag

            if frame_txtime != None:
                if not isinstance(frame_txtime, int) or frame_txtime<0 or frame_txtime>0xFFFFFFFF:
                    raise ValueError("frame_txtime must be a valid 32 unsigned integer")
                o.frame_txtime = frame_txtime

            if ext_address != None:
                if not isinstance(ext_address, int) or ext_address<0 or ext_address>0xFF:
                    raise ValueError("ext_address must be a an integer between 0 and FF")
                o.ext_address = ext_address

            if txpad != None:
                if not isinstance(txpad, int) or txpad<0 or txpad>0xFF:
                    raise ValueError("txpad must be a an integer between 0 and FF")
                o.txpad = txpad
                o.optflag |= opts.flags.TX_PADDING

            if rxpad != None:
                if not isinstance(rxpad, int) or rxpad<0 or rxpad>0xFF:
                    raise ValueError("rxpad must be a an integer between 0 and FF")
                o.rxpad = rxpad
                o.optflag |= opts.flags.RX_PADDING

            if rx_ext_address != None:
                if not isinstance(rx_ext_address, int) or rx_ext_address<0 or rx_ext_address>0xFF:
                    raise ValueError("rx_ext_address must be a an integer between 0 and FF")
                o.rx_ext_address = rx_ext_address

            opt = struct.pack("=LLBBBB", o.optflag, o.frame_txtime, o.ext_address, o.txpad, o.rxpad, o.rx_ext_address)
            s.setsockopt(opts.SOL_CAN_ISOTP, opts.CAN_ISOTP_OPTS, opt)
            return o

        def __repr__(self):
            optflag_str = '[undefined]' if self.optflag is None else '0x%x' % (self.optflag)
            frame_txtime_str = '[undefined]' if self.frame_txtime is None else '0x%x' % (self.frame_txtime)
            ext_address_str = '[undefined]' if self.ext_address is None else '0x%x' % (self.ext_address)
            txpad_str = '[undefined]' if self.txpad is None else '0x%x' % (self.txpad)
            rxpad_str = '[undefined]' if self.rxpad is None else '0x%x' % (self.rxpad)
            rx_ext_address_str = '[undefined]' if self.rx_ext_address is None else '0x%x' % (self.rx_ext_address)

            return "<OPTS_GENERAL: optflag=%s, frame_txtime=%s, ext_address=%s, txpad=%s, rxpad=%s, rx_ext_address=%s>" % (optflag_str, frame_txtime_str, ext_address_str, txpad_str, rxpad_str, rx_ext_address_str)

    class flowcontrol:
        struct_size = 3
        
        def __init__(self):
            self.stmin = None;
            self.bs = None;
            self.wftmax = None;

        @classmethod
        def read(cls, s):
            assert_is_socket(s)
            o = cls()
            opt = s.getsockopt(opts.SOL_CAN_ISOTP, opts.CAN_ISOTP_RECV_FC,cls.struct_size)

            (o.bs, o.stmin, o.wftmax) = struct.unpack("=BBB", opt)
            return o

        @classmethod
        def write(cls, s, bs=None, stmin=None, wftmax=None):
            assert_is_socket(s)
            o = cls.read(s);
            if bs != None:
                if not isinstance(bs, int) or bs<0 or bs>0xFF:
                    raise ValueError("bs must be a valid interger between 0 and FF")
                o.bs = bs

            if stmin != None:
                if not isinstance(stmin, int) or stmin<0 or stmin>0xFF:
                    raise ValueError("stmin must be a valid interger between 0 and FF")
                o.stmin = stmin

            if wftmax != None:
                if not isinstance(wftmax, int) or wftmax<0 or wftmax>0xFF:
                    raise ValueError("wftmax must be a valid interger between 0 and FF")
                o.wftmax = wftmax

            opt = struct.pack("=BBB", o.bs, o.stmin, o.wftmax)
            s.setsockopt(opts.SOL_CAN_ISOTP, opts.CAN_ISOTP_RECV_FC, opt)
            return o

        def __repr__(self):
            bs_str = '[undefined]' if self.bs is None else '0x%x' % (self.bs)
            stmin_str = '[undefined]' if self.stmin is None else '0x%x' % (self.stmin)
            wftmax_str = '[undefined]' if self.wftmax is None else '0x%x' % (self.wftmax)
            return "<OPTS_RECV_FC: bs=%s, stmin=%s, wftmax=%s>" % (bs_str, stmin_str, wftmax_str)

    class linklayer:
        struct_size = 3
        
        def __init__(self):
            self.mtu = None;
            self.tx_dl = None;
            self.tx_flags = None;

        @classmethod
        def read(cls, s):
            assert_is_socket(s)
            o = cls()
            opt = s.getsockopt(opts.SOL_CAN_ISOTP, opts.CAN_ISOTP_LL_OPTS,cls.struct_size)

            (o.mtu, o.tx_dl, o.tx_flags) = struct.unpack("=BBB", opt)
            return o

        @classmethod
        def write(cls, s, mtu=None, tx_dl=None, tx_flags=None):
            assert_is_socket(s)
            o = cls.read(s);
            if mtu != None:
                if not isinstance(mtu, int) or mtu<0 or mtu>0xFF:
                    raise ValueError("mtu must be a valid interger between 0 and FF")
                o.mtu = mtu

            if tx_dl != None:
                if not isinstance(tx_dl, int) or tx_dl<0 or tx_dl>0xFF:
                    raise ValueError("tx_dl must be a valid interger between 0 and FF")
                o.tx_dl = tx_dl

            if tx_flags != None:
                if not isinstance(tx_flags, int) or tx_flags<0 or tx_flags>0xFF:
                    raise ValueError("tx_flags must be a valid interger between 0 and FF")
                o.tx_flags = tx_flags

            opt = struct.pack("=BBB", o.mtu, o.tx_dl, o.tx_flags)
            s.setsockopt(opts.SOL_CAN_ISOTP, opts.CAN_ISOTP_LL_OPTS, opt)
            return o

        def __repr__(self):
            mtu_str = '[undefined]' if self.mtu is None else '0x%x' % (self.mtu)
            tx_dl_str = '[undefined]' if self.tx_dl is None else '0x%x' % (self.tx_dl)
            tx_flags_str = '[undefined]' if self.tx_flags is None else '0x%x' % (self.tx_flags)
            return "<OPTS_LL: mtu=%s, tx_dl=%s, tx_flags=%s>" % (mtu_str, tx_dl_str, tx_flags_str)
