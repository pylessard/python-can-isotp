from typing import Optional, Callable, Dict, Tuple, Union, Any
from logging import Logger
from queue import Queue

from .address import Address, TargetAddressType


class CanMessage:
    arbitration_id: int
    dlc: int
    data: bytearray
    is_extended_id: bool
    is_fd: bool
    bitrate_switch: bool
    def __init__(self,
                 arbitration_id: Optional[int] = ...,
                 dlc: Optional[int] = ...,
                 data: Optional[bytearray] = ...,
                 extended_id: bool = ...,
                 is_fd: bool = ...,
                 bitrate_switch: bool = ...) -> None: ...

class TransportLayer:
    LOGGER_NAME: str
    class Params:
        stmin: int
        blocksize: int
        squash_stmin_requirement: bool
        rx_flowcontrol_timeout: int
        rx_consecutive_frame_timeout: int
        tx_padding: Optional[int]
        wftmax: int
        tx_data_length: int
        tx_data_min_length: Optional[int]
        max_frame_size: int
        can_fd: bool
        bitrate_switch: bool
        target_address_type: Optional[TargetAddressType]
        def __init__(self) -> None: ...
        def set(self,
                key: Optional[str],
                val: Optional[str],
                validate: bool = ...) -> None: ...
        def validate(self) -> None: ...
    class Timer:
        start_time: Optional[float]
        def __init__(self,
                     timeout: Optional[float | int]) -> None: ...
        timeout: Optional[float | int]
        def set_timeout(self,
                        timeout: Optional[float | int]) -> None: ...
        def start(self, timeout: Optional[float | int] = ...) -> None: ...
        def stop(self) -> None: ...
        def elapsed(self) -> Union[float, int]: ...
        def is_timed_out(self) -> bool: ...
        def is_stopped(self) -> bool: ...
    class RxState:
        IDLE: int
        WAIT_CF: int
    class TxState:
        IDLE: int
        WAIT_FC: int
        TRANSMIT_CF: int
    params: Dict[Any, Any]
    logger: Logger
    remote_blocksize: Optional[int]
    rxfn: Callable[[], Optional[CanMessage]]
    txfn: Callable[[CanMessage], None]
    tx_queue: Queue[bytearray]
    rx_queue: Queue[bytearray]
    rx_state: int
    tx_state: int
    rx_block_counter: int
    last_seqnum: int
    rx_frame_length: int
    tx_frame_length: int
    last_flow_control_frame: Optional[object]
    tx_block_counter: int
    tx_seqnum: int
    wft_counter: int
    pending_flow_control_tx: bool
    timer_tx_stmin: Timer
    timer_rx_fc: Timer
    timer_rx_cf: Timer
    error_handler: Callable[[Any], None]
    actual_rxdl: Optional[int]
    timings: Dict[Tuple[int, int], float]
    def __init__(self,
                 rxfn: Optional[Callable[[], Optional[CanMessage]]],
                 txfn: Optional[Callable[[CanMessage], None]],
                 address: Optional[Address] = ...,
                 error_handler: Optional[Callable[[Any], None]] = ...,
                 params: Union[Dict[Any, Any], None] =
    ...) -> None: ...
    def send(self,
             data: bytearray,
             target_address_type: Optional[TargetAddressType] = ...) -> None: ...
    def recv(self) -> Optional[bytearray]: ...
    def available(self) -> bool: ...
    def transmitting(self) -> bool: ...
    def process(self) -> None: ...
    def check_timeouts_rx(self) -> None: ...
    def process_rx(self,
                   msg: CanMessage) -> None: ...
    tx_buffer: bytearray
    def process_tx(self) -> None: ...
    def set_sleep_timing(self,
                         idle: int,
                         wait_fc: int) -> None: ...
    address: Address
    def set_address(self,
                    address: Address) -> None: ...
    def pad_message_data(self,
                         msg_data: bytearray) -> None: ...
    rx_buffer: bytearray
    def empty_rx_buffer(self) -> None: ...
    def empty_tx_buffer(self) -> None: ...
    def start_rx_fc_timer(self) -> None: ...
    def start_rx_cf_timer(self) -> None: ...
    def append_rx_data(self,
                       data: bytearray) -> None: ...
    pending_flowcontrol_status: int
    def request_tx_flowcontrol(self, status: int=...) -> None: ...
    def stop_sending_flow_control(self) -> None: ...
    def make_tx_msg(self,
                    arbitration_id: int,
                    data: bytearray) -> CanMessage: ...
    def get_dlc(self,
                data: bytearray,
                validate_tx: bool = ...) -> None: ...
    def get_nearest_can_fd_size(self,
                                size: int) -> int: ...
    def make_flow_control(self,
                          flow_status: int=...,
                          blocksize: Optional[int] = ...,
                          stmin: Optional[int] = ...) -> CanMessage: ...
    must_wait_for_flow_control: bool
    def request_wait_flow_control(self) -> None: ...
    def stop_sending(self) -> None: ...
    def stop_receiving(self) -> None: ...
    def start_reception_after_first_frame_if_valid(self,
                                                   pdu: object) -> None: ...
    def trigger_error(self, error: Any) -> None: ...
    def reset(self) -> None: ...
    def sleep_time(self) -> float: ...

class CanStack(TransportLayer):
    def rx_canbus(self) -> Optional[CanMessage]: ...
    tx_canbus: Callable[[CanMessage], None]
    def __init__(self,
                 bus: object,  # BusABC
                 *args: Tuple[Any],
                 **kwargs: Dict[Any, Any]) -> None: ...
    bus: object  # BusABC
    def set_bus(self,
                bus: object) -> None: ...
