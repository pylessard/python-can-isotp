__all__ = ['AddressingMode', 'TargetAddressType', 'Address']

from enum import Enum
from isotp import CanMessage

from typing import Optional, Any, List, Callable, Dict, Tuple, Union


class AddressingMode(Enum):
    Normal_11bits = 0
    Normal_29bits = 1
    NormalFixed_29bits = 2
    Extended_11bits = 3
    Extended_29bits = 4
    Mixed_11bits = 5
    Mixed_29bits = 6

    @classmethod
    def get_name(cls, num):
        return cls(num).name


class TargetAddressType(Enum):
    Physical = 0        # 1 to 1 communication
    Functional = 1      # 1 to n communication


class Address:
    """
    Represents the addressing information (N_AI) of the IsoTP layer. Will define what messages will be received and how to craft transmitted message to reach a specific party.

    Parameters must be given according to the addressing mode. When not needed, a parameter may be left unset or set to ``None``.

    Both the :class:`TransportLayer<isotp.TransportLayer>` and the :class:`isotp.socket<isotp.socket>` expects this address object

    :param addressing_mode: The addressing mode. Valid values are defined by the :class:`AddressingMode<isotp.AddressingMode>` class
    :type addressing_mode: int

    :param txid: The CAN ID for transmission. Used for these addressing mode: ``Normal_11bits``, ``Normal_29bits``, ``Extended_11bits``, ``Extended_29bits``, ``Mixed_11bits``
    :type txid: int or None

    :param rxid: The CAN ID for reception. Used for these addressing mode: ``Normal_11bits``, ``Normal_29bits``, ``Extended_11bits``, ``Extended_29bits``, ``Mixed_11bits``
    :type rxid: int or None

    :param target_address: Target address (N_TA) used in ``NormalFixed_29bits`` and ``Mixed_29bits`` addressing mode.
    :type target_address: int or None

    :param source_address: Source address (N_SA) used in ``NormalFixed_29bits`` and ``Mixed_29bits`` addressing mode.
    :type source_address: int or None

    :param physical_id: The CAN ID for physical (unicast) messages. Only bits 28-16 are used. Used for these addressing modes: ``NormalFixed_29bits``, ``Mixed_29bits``. Set to standard mandated value if None.
    :type: int or None

    :param functional_id: The CAN ID for functional (multicast) messages. Only bits 28-16 are used. Used for these addressing modes: ``NormalFixed_29bits``, ``Mixed_29bits``. Set to standard mandated value if None.
    :type: int or None

    :param address_extension: Address extension (N_AE) used in ``Mixed_11bits``, ``Mixed_29bits`` addressing mode
    :type address_extension: int or None
    """

    addressing_mode: AddressingMode
    target_address: Optional[int]
    source_address: Optional[int]
    address_extension: Optional[int]
    txid: Optional[int]
    rxid: Optional[int]
    is_29bits: bool
    tx_arbitration_id_physical: int
    tx_arbitration_id_functional: int
    rx_arbitration_id_physical: int
    rx_arbitration_id_functional: int
    tx_payload_prefix: bytes
    rx_prefix_size: int
    is_for_me: Callable[[CanMessage], bool]

    def __init__(self,
                 addressing_mode: AddressingMode = AddressingMode.Normal_11bits,
                 txid: Optional[int] = None,
                 rxid: Optional[int] = None,
                 target_address: Optional[int] = None,
                 source_address: Optional[int] = None,
                 physical_id: Optional[int] = None,
                 functional_id: Optional[int] = None,
                 address_extension: Optional[int] = None,
                 **kwargs
                 ):

        self.addressing_mode = addressing_mode
        self.target_address = target_address
        self.source_address = source_address
        self.address_extension = address_extension
        self.txid = txid
        self.rxid = rxid
        self.is_29bits = True if self.addressing_mode in [
            AddressingMode.Normal_29bits, AddressingMode.NormalFixed_29bits, AddressingMode.Extended_29bits, AddressingMode.Mixed_29bits] else False

        if self.addressing_mode == AddressingMode.NormalFixed_29bits:
            self.physical_id = 0x18DA0000 if physical_id is None else physical_id & 0x1FFF0000
            self.functional_id = 0x18DB0000 if functional_id is None else functional_id & 0x1FFF0000

        if self.addressing_mode == AddressingMode.Mixed_29bits:
            self.physical_id = 0x18CE0000 if physical_id is None else physical_id & 0x1FFF0000
            self.functional_id = 0x18CD0000 if functional_id is None else functional_id & 0x1FFF0000

        self.validate()

        # From here, input is good. Do some precomputing for speed optimization without bothering about types or values
        self.tx_arbitration_id_physical = self._get_tx_arbitraton_id(TargetAddressType.Physical)
        self.tx_arbitration_id_functional = self._get_tx_arbitraton_id(TargetAddressType.Functional)

        self.rx_arbitration_id_physical = self._get_rx_arbitration_id(TargetAddressType.Physical)
        self.rx_arbitration_id_functional = self._get_rx_arbitration_id(TargetAddressType.Functional)

        self.tx_payload_prefix = bytes()
        self.rx_prefix_size = 0

        if self.addressing_mode in [AddressingMode.Extended_11bits, AddressingMode.Extended_29bits]:
            assert self.target_address is not None
            self.tx_payload_prefix = bytes([self.target_address])
            self.rx_prefix_size = 1
        elif self.addressing_mode in [AddressingMode.Mixed_11bits, AddressingMode.Mixed_29bits]:
            assert self.address_extension is not None
            self.tx_payload_prefix = bytes([self.address_extension])
            self.rx_prefix_size = 1

        if self.addressing_mode in [AddressingMode.Normal_11bits, AddressingMode.Normal_29bits]:
            self.is_for_me = self._is_for_me_normal
        elif self.addressing_mode in [AddressingMode.Extended_11bits, AddressingMode.Extended_29bits]:
            self.is_for_me = self._is_for_me_extended
        elif self.addressing_mode == AddressingMode.NormalFixed_29bits:
            self.is_for_me = self._is_for_me_normalfixed
        elif self.addressing_mode == AddressingMode.Mixed_11bits:
            self.is_for_me = self._is_for_me_mixed_11bits
        elif self.addressing_mode == AddressingMode.Mixed_29bits:
            self.is_for_me = self._is_for_me_mixed_29bits
        else:
            raise RuntimeError('This exception should never be raised.')

    def validate(self):
        if self.addressing_mode not in [AddressingMode.Normal_11bits, AddressingMode.Normal_29bits, AddressingMode.NormalFixed_29bits, AddressingMode.Extended_11bits, AddressingMode.Extended_29bits, AddressingMode.Mixed_11bits, AddressingMode.Mixed_29bits]:
            raise ValueError('Addressing mode is not valid')

        if self.addressing_mode in [AddressingMode.Normal_11bits, AddressingMode.Normal_29bits]:
            if self.rxid is None or self.txid is None:
                raise ValueError('txid and rxid must be specified for Normal addressing mode (11 or 29 bits ID)')
            if self.rxid == self.txid:
                raise ValueError('txid and rxid must be different for Normal addressing mode')

        elif self.addressing_mode == AddressingMode.NormalFixed_29bits:
            if self.target_address is None or self.source_address is None:
                raise ValueError('target_address and source_address must be specified for Normal Fixed addressing (29 bits ID)')

        elif self.addressing_mode in [AddressingMode.Extended_11bits, AddressingMode.Extended_29bits]:
            if self.target_address is None or self.rxid is None or self.txid is None:
                raise ValueError('target_address, rxid and txid must be specified for Extended addressing mode (11 or 29 bits ID)')
            if self.rxid == self.txid:
                raise ValueError('txid and rxid must be different')

        elif self.addressing_mode == AddressingMode.Mixed_11bits:
            if self.rxid is None or self.txid is None or self.address_extension is None:
                raise ValueError('rxid, txid and address_extension must be specified for Mixed addressing mode (11 bits ID)')

        elif self.addressing_mode == AddressingMode.Mixed_29bits:
            if self.target_address is None or self.source_address is None or self.address_extension is None:
                raise ValueError('target_address, source_address and address_extension must be specified for Mixed addressing mode (29 bits ID)')

        if self.target_address is not None:
            if not isinstance(self.target_address, int):
                raise ValueError('target_address must be an integer')
            if self.target_address < 0 or self.target_address > 0xFF:
                raise ValueError('target_address must be an integer between 0x00 and 0xFF')

        if self.source_address is not None:
            if not isinstance(self.source_address, int):
                raise ValueError('source_address must be an integer')
            if self.source_address < 0 or self.source_address > 0xFF:
                raise ValueError('source_address must be an integer between 0x00 and 0xFF')

        if self.address_extension is not None:
            if not isinstance(self.address_extension, int):
                raise ValueError('source_address must be an integer')
            if self.address_extension < 0 or self.address_extension > 0xFF:
                raise ValueError('address_extension must be an integer between 0x00 and 0xFF')

        if self.txid is not None:
            if not isinstance(self.txid, int):
                raise ValueError('txid must be an integer')
            if self.txid < 0:
                raise ValueError('txid must be greater than 0')
            if not self.is_29bits:
                if self.txid > 0x7FF:
                    raise ValueError('txid must be smaller than 0x7FF for 11 bits identifier')

        if self.rxid is not None:
            if not isinstance(self.rxid, int):
                raise ValueError('rxid must be an integer')
            if self.rxid < 0:
                raise ValueError('rxid must be greater than 0')
            if not self.is_29bits:
                if self.rxid > 0x7FF:
                    raise ValueError('rxid must be smaller than 0x7FF for 11 bits identifier')

    def get_tx_arbitraton_id(self, address_type: TargetAddressType = TargetAddressType.Physical) -> int:
        if address_type == TargetAddressType.Physical:
            return self.tx_arbitration_id_physical
        else:
            return self.tx_arbitration_id_functional

    def get_rx_arbitraton_id(self, address_type: TargetAddressType = TargetAddressType.Physical) -> int:
        if address_type == TargetAddressType.Physical:
            return self.rx_arbitration_id_physical
        else:
            return self.rx_arbitration_id_functional

    def _get_tx_arbitraton_id(self, address_type: TargetAddressType) -> int:
        if self.addressing_mode in (AddressingMode.Normal_11bits,
                                    AddressingMode.Normal_29bits,
                                    AddressingMode.Extended_11bits,
                                    AddressingMode.Extended_29bits,
                                    AddressingMode.Mixed_11bits):
            assert self.txid is not None
            return self.txid
        elif self.addressing_mode in [AddressingMode.Mixed_29bits, AddressingMode.NormalFixed_29bits]:
            assert self.target_address is not None
            assert self.source_address is not None
            bits28_16 = self.physical_id if address_type == TargetAddressType.Physical else self.functional_id
            return bits28_16 | (self.target_address << 8) | self.source_address
        raise ValueError("Unsupported addressing mode")

    def _get_rx_arbitration_id(self, address_type: TargetAddressType = TargetAddressType.Physical) -> int:
        if self.addressing_mode in (AddressingMode.Normal_11bits,
                                    AddressingMode.Normal_29bits,
                                    AddressingMode.Extended_11bits,
                                    AddressingMode.Extended_29bits,
                                    AddressingMode.Mixed_11bits):
            assert self.rxid is not None
            return self.rxid
        elif self.addressing_mode in [AddressingMode.Mixed_29bits, AddressingMode.NormalFixed_29bits]:
            assert self.target_address is not None
            assert self.source_address is not None
            bits28_16 = self.physical_id if address_type == TargetAddressType.Physical else self.functional_id
            return bits28_16 | (self.source_address << 8) | self.target_address
        raise ValueError("Unsupported addressing mode")

    def _is_for_me_normal(self, msg: CanMessage) -> bool:
        if self.is_29bits == msg.is_extended_id:
            return msg.arbitration_id == self.rxid
        return False

    def _is_for_me_extended(self, msg: CanMessage) -> bool:
        if self.is_29bits == msg.is_extended_id:
            if msg.data is not None and len(msg.data) > 0:
                return msg.arbitration_id == self.rxid and int(msg.data[0]) == self.source_address
        return False

    def _is_for_me_normalfixed(self, msg: CanMessage) -> bool:
        if self.is_29bits == msg.is_extended_id:
            return (msg.arbitration_id & 0x1FFF0000 in [self.physical_id, self.functional_id]) and (msg.arbitration_id & 0xFF00) >> 8 == self.source_address and msg.arbitration_id & 0xFF == self.target_address
        return False

    def _is_for_me_mixed_11bits(self, msg: CanMessage) -> bool:
        if self.is_29bits == msg.is_extended_id:
            if msg.data is not None and len(msg.data) > 0:
                return msg.arbitration_id == self.rxid and int(msg.data[0]) == self.address_extension
        return False

    def _is_for_me_mixed_29bits(self, msg: CanMessage) -> bool:
        if self.is_29bits == msg.is_extended_id:
            if msg.data is not None and len(msg.data) > 0:
                return (msg.arbitration_id & 0x1FFF0000) in [self.physical_id, self.functional_id] and (msg.arbitration_id & 0xFF00) >> 8 == self.source_address and msg.arbitration_id & 0xFF == self.target_address and int(msg.data[0]) == self.address_extension
        return False

    def requires_extension_byte(self) -> bool:
        return True if self.addressing_mode in [AddressingMode.Extended_11bits, AddressingMode.Extended_29bits, AddressingMode.Mixed_11bits, AddressingMode.Mixed_29bits] else False

    def get_tx_extension_byte(self) -> Optional[int]:
        if self.addressing_mode in [AddressingMode.Extended_11bits, AddressingMode.Extended_29bits]:
            return self.target_address
        if self.addressing_mode in [AddressingMode.Mixed_11bits, AddressingMode.Mixed_29bits]:
            return self.address_extension
        return None

    def get_rx_extension_byte(self) -> Optional[int]:
        if self.addressing_mode in [AddressingMode.Extended_11bits, AddressingMode.Extended_29bits]:
            return self.source_address
        if self.addressing_mode in [AddressingMode.Mixed_11bits, AddressingMode.Mixed_29bits]:
            return self.address_extension
        return None

    def get_content_str(self) -> str:
        val_dict = {}
        keys = ['target_address', 'source_address', 'address_extension', 'txid', 'rxid']
        for key in keys:
            val = getattr(self, key)
            if val is not None:
                val_dict[key] = val
        vals_str = ', '.join(['%s:0x%02x' % (k, val_dict[k]) for k in val_dict])
        return '[%s - %s]' % (AddressingMode.get_name(self.addressing_mode), vals_str)

    def __repr__(self):
        return '<IsoTP Address %s at 0x%08x>' % (self.get_content_str(), id(self))
