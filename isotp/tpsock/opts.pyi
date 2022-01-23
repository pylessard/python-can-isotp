from . import check_support as check_support, socket as socket
from typing import Any, Optional
from isotp.tpsock.opts import socket

flags: Any

def assert_is_socket(s: socket) -> None: ...

SOL_CAN_BASE: int
SOL_CAN_ISOTP: Optional[int]
CAN_ISOTP_OPTS: int
CAN_ISOTP_RECV_FC: int
CAN_ISOTP_TX_STMIN: int
CAN_ISOTP_RX_STMIN: int
CAN_ISOTP_LL_OPTS: int

class general:
    struct_size: Any
    optflag: Any
    frame_txtime: Any
    ext_address: Any
    txpad: Any
    rxpad: Any
    rx_ext_address: Any
    def __init__(self) -> None: ...
    @classmethod
    def read(cls,
             s: socket) -> general: ...
    @classmethod
    def write(cls,
              s: socket,
              optflag: Optional[Any] = ...,
              frame_txtime: Optional[Any] = ...,
              ext_address: Optional[Any] = ...,
              txpad: Optional[Any] = ...,
              rxpad: Optional[Any] = ...,
              rx_ext_address: Optional[Any] = ...,
              tx_stmin: Optional[Any] = ...) -> general: ...

class flowcontrol:
    struct_size: int
    stmin: Any
    bs: Any
    wftmax: Any
    def __init__(self) -> None: ...
    @classmethod
    def read(cls,
             s: socket) -> flowcontrol: ...
    @classmethod
    def write(cls,
              s: socket,
              bs: Optional[Any] = ...,
              stmin: Optional[Any] = ...,
              wftmax: Optional[Any] = ...) -> flowcontrol: ...

class linklayer:
    struct_size: int
    mtu: Any
    tx_dl: Any
    tx_flags: Any
    def __init__(self) -> None: ...
    @classmethod
    def read(cls,
             s: socket) -> linklayer: ...
    @classmethod
    def write(cls,
              s: socket,
              mtu: Optional[Any] = ...,
              tx_dl: Optional[Any] = ...,
              tx_flags: Optional[Any] = ...) -> linklayer: ...
