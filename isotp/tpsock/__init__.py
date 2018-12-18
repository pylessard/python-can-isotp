import socket as socket_module
import os

mtu=4095

def check_support():
    if not hasattr(socket_module, 'CAN_ISOTP'):
        if os.name == 'nt':
            raise NotImplementedError("This module cannot be used on Windows")
        else:
            raise NotImplementedError("Your version of Python does not offer support for CAN ISO-TP protocol. Support have been added since Python 3.7 on Linux build > 2.6.15.")

class socket:

    def __init__(self, timeout=0.1):
        check_support()
        from . import opts
        self.interface = None
        self.rxid = None
        self.txid = None
        self.bound = False
        self.closed = False
        self._socket = socket_module.socket(socket_module.AF_CAN, socket_module.SOCK_DGRAM, socket_module.CAN_ISOTP)
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

    def set_ll_opts(self, *args, **kwargs):
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

    def bind(self, interface, rxid, txid, extended_id=None):
        self.interface=interface
        if extended_id == True or extended_id is None and rxid > 0x7FF:
            self.rxid = rxid | socket_module.CAN_EFF_FLAG
        else:
            self.rxid = rxid & ~socket_module.CAN_EFF_FLAG

        if extended_id == True or extended_id is None and txid > 0x7FF:
            self.txid = txid | socket_module.CAN_EFF_FLAG
        else:
            self.txid = txid & ~socket_module.CAN_EFF_FLAG

        self._socket.bind((interface, self.rxid, self.txid))
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