from typing import Any, Optional, Tuple, Dict

from isotp.address import Address
from isotp.tpsock.opts import linklayer, general, flowcontrol

mtu: int

def check_support() -> None: ...

class flags:
    LISTEN_MODE: int
    EXTEND_ADDR: int
    TX_PADDING: int
    RX_PADDING: int
    CHK_PAD_LEN: int
    CHK_PAD_DATA: int
    HALF_DUPLEX: int
    FORCE_TXSTMIN: int
    FORCE_RXSTMIN: int
    RX_EXT_ADDR: int
    WAIT_TX_DONE: int

class LinkLayerProtocol:
    CAN: int
    CAN_FD: int

class socket:
    flags: flags
    LinkLayerProtocol: LinkLayerProtocol
    interface: Optional[str]
    address: Optional[Address]
    bound: bool
    closed: bool
    def __init__(self,
                 timeout: float = ...) -> None: ...
    def send(self,
             *args: Tuple[Any],
             **kwargs: Dict[Any, Any]) -> int: ...
    def recv(self,
             n:int=...) -> Optional[bytes]: ...
    def set_ll_opts(self,
                    *args: Tuple[Any],
                    **kwargs: Dict[Any, Any]) -> linklayer: ...
    def set_opts(self,
                 *args: Tuple[Any],
                 **kwargs: Dict[Any, Any]) -> general: ...
    def set_fc_opts(self,
                    *args: Tuple[Any],
                    **kwargs: Dict[Any, Any]) -> flowcontrol: ...
    def get_ll_opts(self,
                    *args: Tuple[Any],
                    **kwargs: Dict[Any, Any]) -> linklayer: ...
    def get_opts(self,
                 *args: Tuple[Any],
                 **kwargs: Dict[Any, Any]) -> general: ...
    def get_fc_opts(self,
                    *args: Tuple[Any],
                    **kwargs: Dict[Any, Any]) -> flowcontrol: ...
    def bind(self,
             interface: str,
             *args: Tuple[Any],
             **kwargs: Dict[Any, Any]) -> None: ...
    def fileno(self) -> int: ...
    def close(self,
              *args: Tuple[Any],
              **kwargs: Dict[Any, Any]) -> None: ...
    def __delete__(self) -> None: ...
