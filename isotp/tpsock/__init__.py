import socket as socket_module
import os
import isotp.address

mtu=4095

def check_support():
    if not hasattr(socket_module, 'CAN_ISOTP'):
        if os.name == 'nt':
            raise NotImplementedError("This module cannot be used on Windows")
        else:
            raise NotImplementedError("Your version of Python does not offer support for CAN ISO-TP protocol. Support have been added since Python 3.7 on Linux build > 2.6.15.")

class flags:

    LISTEN_MODE     = 0x001
    """Puts the socket in Listen mode, which prevents transmission of data"""

    EXTEND_ADDR     = 0x002
    """When set, an address extension byte (set in socket general options) will be added to each payload sent. Unless RX_EXT_ADDR is also set, this value will be expected for reception as well"""

    TX_PADDING      = 0x004
    """Enables padding of transmitted data with a byte set in the socket general options"""

    RX_PADDING      = 0x008
    """ Indicates that data padding is possible in reception. Must be set for CHK_PAD_LEN and CHK_PAD_DATA to have an effect"""

    CHK_PAD_LEN     = 0x010
    """ Makes the socket validate the padding length of the CAN message"""

    CHK_PAD_DATA    = 0x020
    """ Makes the socket validate the padding bytes of the CAN message"""

    HALF_DUPLEX     = 0x040
    """ Sets the socket in half duplex mode, forcing transmission and reception to happen sequentially """

    FORCE_TXSTMIN   = 0x080
    """Forces the socket to use the separation time sets in general options, overriding stmin value received in flow control frames."""

    FORCE_RXSTMIN   = 0x100
    """ Forces the socket to ignore any message received faster than stmin given in the flow control frame"""

    RX_EXT_ADDR     = 0x200
    """ When sets, a different extended address can be used for reception than for transmission."""

class LinkLayerProtocol:
    CAN = 16
    """ Internal structure size of a CAN 2.0 frame"""

    CAN_FD = 72
    """ Internal structure size of a CAN FD frame"""

class socket:
    """
    A IsoTP socket wrapper for easy configuration

    :param timeout: The underlying socket timeout set with ``settimeout``. Makes the reception thread sleep
    :type timeout: int

    """

    # We want that syntax isotp.socket.flags and isotp.socket.mtu
    # This is a workaround for sphinx autodoc that fails to load docstring for nested-class members
    flags = flags   
    LinkLayerProtocol = LinkLayerProtocol

    def __init__(self, timeout=0.1):
        check_support()
        from . import opts
        self.interface = None
        self.address = None
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

    def get_ll_opts(self, *args, **kwargs):
        return opts.linklayer.read(self._socket, *args, **kwargs)

    def get_opts(self, *args, **kwargs):
        return opts.general.read(self._socket, *args, **kwargs)

    def get_fc_opts(self, *args, **kwargs):
        return opts.flowcontrol.read(self._socket, *args, **kwargs)

    def bind(self, interface, *args, **kwargs):
        """
        Binds the socket to an address. 
        If no address is provided, all additional parameters will be used to create an address. This is mainly to allow a syntax such as ``sock.bind('vcan0', rxid=0x123, txid=0x456)`` for backward compatibility.

        :param interface: The network interface to use
        :type interface: string

        :param address: The address to bind to. 
        :type: :class:`isotp.Address<isotp.Address>`
        """
        self.interface=interface

        # == This is for syntax flexibility and also backward compatibility
        address = None
        if 'address' in kwargs:
            address = kwargs['address']

        for arg in args:
            if isinstance(arg, isotp.address.Address) and address is None:
                address = arg
                break

        if address is None:
            address = isotp.address.Address(*args, **kwargs)
        # == 
        self.address = address

        # IsoTP sockets doesn't provide an interface to modify the target address type. We asusme physical.
        # If functional is required, it Ids can be manually crafted in Normal / extended mode
        rxid = self.address.get_rx_arbitraton_id(isotp.TargetAddressType.Physical)
        txid = self.address.get_tx_arbitraton_id(isotp.TargetAddressType.Physical)

        if self.address.is_29bits == True:
            rxid = (rxid & socket_module.CAN_EFF_MASK) | socket_module.CAN_EFF_FLAG
        else:
            rxid = rxid & socket_module.CAN_SFF_MASK

        if self.address.is_29bits == True:
            txid = (txid & socket_module.CAN_EFF_MASK) | socket_module.CAN_EFF_FLAG
        else:
            txid = txid & socket_module.CAN_SFF_MASK

        if self.address.requires_extension_byte():
            o = self.get_opts()
            o.optflag |= self.flags.EXTEND_ADDR | self.flags.RX_EXT_ADDR
            self.set_opts(optflag = o.optflag, ext_address = self.address.get_tx_extension_byte(), rx_ext_address=self.address.get_rx_extension_byte())

        self._socket.bind((interface, rxid, txid))
        self.bound=True

    def fileno(self):
        return self._socket.fileno()

    def close(self, *args, **kwargs):
        v = self._socket.close(*args, **kwargs)
        self.bound = False
        self.closed = True
        self.address = None
        return v

    def __delete__(self):
        if isinstance(_socket, socket_module.socket):
            self._socket.close()
            self._socket = None

    def __repr__(self):
        if self.bound:
            return "<ISO-TP Socket: %s, %s>" % (self.interface, self.address.get_content_str())
        else:
            status = "Closed" if self.closed else "Unbound"
            return "<%s ISO-TP Socket at 0x%s>" % (status, hex(id(self)))
