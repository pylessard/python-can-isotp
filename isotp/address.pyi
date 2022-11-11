from typing import Optional, Dict, Any


class AddressingMode:
    Normal_11bits: int
    Normal_29bits: int
    NormalFixed_29bits: int
    Extended_11bits: int
    Extended_29bits: int
    Mixed_11bits: int
    Mixed_29bits: int
    @classmethod
    def get_name(cls,
                 num: int) -> str: ...

class TargetAddressType:
    Physical: int
    Functional: int

class Address:
    addressing_mode: int
    target_address: Optional[int]
    source_address: Optional[int]
    address_extension: Optional[int]
    txid: Optional[int]
    rxid: Optional[int]
    is_29bits: bool
    tx_arbitration_id_physical: Optional[int]
    tx_arbitration_id_functional: Optional[int]
    rx_arbitration_id_physical: Optional[int]
    rx_arbitration_id_functional: Optional[int]
    tx_payload_prefix: bytearray
    rx_prefix_size: int
    is_for_me: bool
    def __init__(self,
                 addressing_mode: int=...,
                 txid: Optional[int] = ...,
                 rxid: Optional[int] = ...,
                 target_address: Optional[int] = ...,
                 source_address: Optional[int] = ...,
                 address_extension: Optional[int] = ...,
                 **kwargs: Dict[Any, Any]) -> None: ...
    def validate(self) -> None: ...
    def get_tx_arbitraton_id(self,
                             address_type:TargetAddressType=...) -> Optional[int]: ...
    def get_rx_arbitraton_id(self,
                             address_type:TargetAddressType=...) -> Optional[int]: ...
    def requires_extension_byte(self) -> bool: ...
    def get_tx_extension_byte(self) -> Optional[int]: ...
    def get_rx_extension_byte(self) -> Optional[int]: ...
    def get_content_str(self) -> str: ...
