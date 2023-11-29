__all__ = [
    'PDU',
    'RateLimiter',
    'TransportLayerLogic',
    'TransportLayer',
    'CanStack',
]

import queue
import logging
from copy import copy
import binascii
import time
import isotp.address
import isotp.errors
from isotp.can_message import CanMessage
import math
import enum
from dataclasses import dataclass
import threading
from isotp.tools import Timer
import inspect
import functools

from typing import Optional, Any, List, Callable, Dict, Tuple, Union, TYPE_CHECKING

try:
    import can
    _can_available = True
except ImportError:
    _can_available = False


def is_documented_by(original):
    def wrapper(target):
        target.__doc__ = original.__doc__
        return target
    return wrapper


class PDU:
    """
    Converts a CAN Message into a meaningful PDU such as SingleFrame, FirstFrame, ConsecutiveFrame, FlowControl

    :param msg: The CAN message
    :type msg: `isotp.protocol.CanMessage`
    """
    __slots__ = 'type', 'length', 'data', 'blocksize', 'stmin', 'stmin_sec', 'seqnum', 'flow_status', 'rx_dl', 'escape_sequence', 'can_dl'

    class Type:
        SINGLE_FRAME = 0
        FIRST_FRAME = 1
        CONSECUTIVE_FRAME = 2
        FLOW_CONTROL = 3

    class FlowStatus:
        ContinueToSend = 0
        Wait = 1
        Overflow = 2

    type: int
    length: Optional[int]
    data: bytes
    blocksize: Optional[int]
    stmin: Optional[int]
    stmin_sec: Optional[float]
    seqnum: Optional[int]
    flow_status: Optional[int]
    rx_dl: int
    escape_sequence: bool
    can_dl: int

    def __init__(self, msg: CanMessage, start_of_data: int = 0):

        self.data = bytes()
        self.length = None
        self.blocksize = None
        self.stmin = None
        self.stmin_sec = None
        self.seqnum = None
        self.flow_status = None
        self.escape_sequence = False

        if len(msg.data) < start_of_data:
            raise ValueError("Received message is missing data according to prefix size")

        self.can_dl = len(msg.data)
        self.rx_dl = max(8, self.can_dl)
        msg_data = msg.data[start_of_data:]
        datalen = len(msg_data)
        # Guarantee at least presence of byte #1
        if datalen > 0:
            hnb = (msg_data[0] >> 4) & 0xF
            if hnb > 3:
                raise ValueError('Received message with unknown frame type %d' % hnb)
            self.type = int(hnb)
        else:
            raise ValueError('Empty CAN frame')

        if self.type == self.Type.SINGLE_FRAME:
            length_placeholder = int(msg_data[0]) & 0xF
            if length_placeholder != 0:
                self.length = length_placeholder
                if self.length > datalen - 1:
                    raise ValueError("Received Single Frame with length of %d while there is room for %d bytes of data with this configuration" % (
                        self.length, datalen - 1))
                self.data = msg_data[1:][:self.length]

            else:  # Escape sequence
                if datalen < 2:
                    raise ValueError('Single frame with escape sequence must be at least %d bytes long with this configuration' % (2 + start_of_data))

                self.escape_sequence = True
                self.length = int(msg_data[1])
                if self.length == 0:
                    raise ValueError("Received Single Frame with length of 0 bytes")
                if self.length > datalen - 2:
                    raise ValueError("Received Single Frame with length of %d while there is room for %d bytes of data with this configuration" % (
                        self.length, datalen - 2))
                self.data = msg_data[2:][:self.length]

        elif self.type == self.Type.FIRST_FRAME:
            if datalen < 2:
                raise ValueError('First frame without escape sequence must be at least %d bytes long with this configuration' % (2 + start_of_data))

            length_placeholder = ((int(msg_data[0]) & 0xF) << 8) | int(msg_data[1])
            if length_placeholder != 0:  # Frame is maximum 4095 bytes
                self.length = length_placeholder
                self.data = msg_data[2:][:min(self.length, datalen - 2)]

            else:  # Frame is larger than 4095 bytes
                if datalen < 6:
                    raise ValueError('First frame with escape sequence must be at least %d bytes long with this configuration' % (6 + start_of_data))
                self.escape_sequence = True
                self.length = (msg_data[2] << 24) | (msg_data[3] << 16) | (msg_data[4] << 8) | (msg_data[5] << 0)
                self.data = msg_data[6:][:min(self.length, datalen - 6)]

        elif self.type == self.Type.CONSECUTIVE_FRAME:
            self.seqnum = int(msg_data[0]) & 0xF
            self.data = msg_data[1:]  # No need to check size as this will return empty data if overflow.

        elif self.type == self.Type.FLOW_CONTROL:
            if datalen < 3:
                raise ValueError('Flow Control frame must be at least %d bytes with the actual configuration' % (3 + start_of_data))

            self.flow_status = int(msg_data[0]) & 0xF
            if self.flow_status >= 3:
                raise ValueError('Unknown flow status')

            self.blocksize = int(msg_data[1])
            stmin_temp = int(msg_data[2])

            if stmin_temp >= 0 and stmin_temp <= 0x7F:
                self.stmin_sec = stmin_temp / 1000
            elif stmin_temp >= 0xf1 and stmin_temp <= 0xF9:
                self.stmin_sec = (stmin_temp - 0xF0) / 10000

            if self.stmin_sec is None:
                raise ValueError('Invalid StMin received in Flow Control')
            else:
                self.stmin = stmin_temp

        else:
            raise ValueError("Unsupported PDU type: %s" % self.type)

    @classmethod
    def craft_flow_control_data(cls, flow_status: int, blocksize: int, stmin: int) -> bytes:
        return bytes([(0x30 | (flow_status) & 0xF), blocksize & 0xFF, stmin & 0xFF])

    def name(self):
        if self.type is None:
            return "[None]"

        if self.type == self.Type.SINGLE_FRAME:
            return "SINGLE_FRAME"
        elif self.type == self.Type.FIRST_FRAME:
            return "FIRST_FRAME"
        elif self.type == self.Type.CONSECUTIVE_FRAME:
            return "CONSECUTIVE_FRAME"
        elif self.type == self.Type.FLOW_CONTROL:
            return "FLOW_CONTROL"
        else:
            return "Reserved"


class RateLimiter:
    TIME_SLOT_LENGTH = 0.005

    enabled: bool
    mean_bitrate: float
    window_size_sec: float
    error_reason: str
    burst_bitcount: List[int]
    burst_time: List[float]
    bit_total: int
    window_bit_max: float

    def __init__(self, mean_bitrate=None, window_size_sec=0.1):
        self.enabled = False
        self.mean_bitrate = mean_bitrate
        self.window_size_sec = window_size_sec
        self.error_reason = ''
        self.reset()

        if self.can_be_enabled():
            self.enable()

    def can_be_enabled(self) -> bool:
        try:
            float(self.mean_bitrate)
        except:
            self.error_reason = 'mean_bitrate is not numerical'
            return False

        if float(self.mean_bitrate) <= 0:
            self.error_reason = 'mean_bitrate must be greater than 0'
            return False

        try:
            float(self.window_size_sec)
        except:
            self.error_reason = 'window_size_sec is not numerical'
            return False

        if float(self.window_size_sec) <= 0:
            self.error_reason = 'window_size_sec must be greater than 0'
            return False

        return True

    def set_bitrate(self, mean_bitrate: float) -> None:
        self.mean_bitrate = mean_bitrate

    def enable(self) -> None:
        if self.can_be_enabled():
            self.mean_bitrate = float(self.mean_bitrate)
            self.window_size_sec = float(self.window_size_sec)
            self.enabled = True
            self.reset()
        else:
            raise ValueError('Cannot enable Rate Limiter.  \n %s' % self.error_reason)

    def disable(self) -> None:
        self.enabled = False

    def reset(self) -> None:
        self.burst_bitcount = []
        self.burst_time = []
        self.bit_total = 0
        self.window_bit_max = self.mean_bitrate * self.window_size_sec

    def update(self) -> None:
        if not self.enabled:
            self.reset()
            return

        t = time.monotonic()

        while len(self.burst_time) > 0:
            t2 = self.burst_time[0]
            if t - t2 > self.window_size_sec:
                self.burst_time.pop(0)
                n_to_remove = self.burst_bitcount.pop(0)
                self.bit_total -= n_to_remove
            else:
                break

    def allowed_bytes(self) -> int:
        no_limit = 0xFFFFFFFF

        if not self.enabled:
            return no_limit

        allowed_bits = max(self.window_bit_max - self.bit_total, 0)

        return math.floor(allowed_bits / 8)

    def inform_byte_sent(self, datalen: int) -> None:
        if self.enabled:
            bytelen = datalen * 8
            t = time.monotonic()
            self.bit_total += bytelen
            if len(self.burst_time) == 0:
                self.burst_time.append(t)
                self.burst_bitcount.append(bytelen)
            else:
                last_time = self.burst_time[-1]
                if t - last_time > self.TIME_SLOT_LENGTH:
                    self.burst_time.append(t)
                    self.burst_bitcount.append(bytelen)
                else:
                    self.burst_bitcount[-1] += bytelen


class TransportLayerLogic:
    """
    The IsoTP transport layer raw implementation. When using this class, the user is responsible of handling timings by calling the ``process()`` function
    as fast as possible, like the legacy V1 library was requiring. For an easier solution with less degrees of freedom, use the :ref:`TransportLayer<TransportLayer>`

    :param rxfn: Function to be called by the transport layer to read the CAN layer. Must return a :class:`isotp.CanMessage<isotp.CanMessage>` or None if no message has been received.
    :type rxfn: Callable : expected signature: ``my_txfn(msg:isotp.CanMessage) -> None``

    :param txfn: Function to be called by the transport layer to send a message on the CAN layer. This function should receive a :class:`isotp.CanMessage<isotp.CanMessage>`
    :type txfn: Callable : expected signature: ``my_rxfn(timeout:float) -> Optional[isotp.CanMessage]``

    :param address: The address information of CAN messages. Includes the addressing mode, txid/rxid, source/target address and address extension. 
        See :class:`isotp.Address<isotp.Address>` for more details.
    :type address: :class:`isotp.Address<isotp.Address>`

    :param error_handler: A function to be called when an error has been detected. An :class:`isotp.IsoTpError<isotp.IsoTpError>` (inheriting Exception class) 
        will be given as sole parameter. See the :ref:`Error section<Errors>`
    :type error_handler: Callable : Expected signature: ``my_error_handler(error:isotp.IsoTpError) -> None``

    :param params: List of parameters for the transport layer. See :ref:`the list of parameters<parameters>
    :type params: dict

    :param post_send_callback: An optional callback to be called right after a send request has been enqueued. The main purpose of this parameter is to allow 
        a facility to stop waiting for a message (if blocked in ``rxfn``) and start transmitting right away if possible.
        the function must have this signature : ``my_func(send_request)``  Where ``send_request`` is an instance of :ref:`SendRequest<TransportLayer.SendRequest>`
    :type post_send_callback: Callable
    """

    LOGGER_NAME = 'isotp'

    @dataclass(slots=True, init=False)
    class Params:
        stmin: int
        blocksize: int
        override_receiver_stmin: Optional[float]
        rx_flowcontrol_timeout: float
        rx_consecutive_frame_timeout: float
        tx_padding: Optional[int]
        wftmax: int
        tx_data_length: int
        tx_data_min_length: Optional[int]
        max_frame_size: int
        can_fd: bool
        bitrate_switch: bool
        default_target_address_type: isotp.TargetAddressType
        rate_limit_max_bitrate: int
        rate_limit_window_size: float
        rate_limit_enable: bool
        listen_mode: bool
        blocking_send: bool
        logger_name: str

        def __init__(self):
            self.stmin = 0
            self.blocksize = 8
            self.override_receiver_stmin = None
            self.rx_flowcontrol_timeout = 1000
            self.rx_consecutive_frame_timeout = 1000
            self.tx_padding = None
            self.wftmax = 0
            self.tx_data_length = 8
            self.tx_data_min_length = None
            self.max_frame_size = 4095
            self.can_fd = False
            self.bitrate_switch = False
            self.default_target_address_type = isotp.address.TargetAddressType.Physical
            self.rate_limit_max_bitrate = 100000000
            self.rate_limit_window_size = 0.2
            self.rate_limit_enable = False
            self.listen_mode = False
            self.blocking_send = False
            self.logger_name = TransportLayer.LOGGER_NAME

        def set(self, key: str, val: Any, validate: bool = True) -> None:
            param_alias: Dict[str, str] = {
            }
            if key in param_alias:
                key = param_alias[key]
            setattr(self, key, val)
            if validate:
                self.validate()

        def validate(self) -> None:
            if not isinstance(self.rx_flowcontrol_timeout, int):
                raise ValueError('rx_flowcontrol_timeout must be an integer')

            if self.rx_flowcontrol_timeout < 0:
                raise ValueError('rx_flowcontrol_timeout must be positive integer')

            if not isinstance(self.rx_consecutive_frame_timeout, int):
                raise ValueError('rx_consecutive_frame_timeout must be an integer')

            if self.rx_consecutive_frame_timeout < 0:
                raise ValueError('rx_consecutive_frame_timeout must be positive integer')

            if self.tx_padding is not None:
                if not isinstance(self.tx_padding, int):
                    raise ValueError('tx_padding must be an integer')

                if self.tx_padding < 0 or self.tx_padding > 0xFF:
                    raise ValueError('tx_padding must be an integer between 0x00 and 0xFF')

            if not isinstance(self.stmin, int):
                raise ValueError('stmin must be an integer')

            if self.stmin < 0 or self.stmin > 0xFF:
                raise ValueError('stmin must be positive integer between 0x00 and 0xFF')

            if not isinstance(self.blocksize, int):
                raise ValueError('blocksize must be an integer')

            if self.blocksize < 0 or self.blocksize > 0xFF:
                raise ValueError('blocksize must be and integer between 0x00 and 0xFF')

            if self.override_receiver_stmin is not None:
                if not isinstance(self.override_receiver_stmin, (int, float)) or isinstance(self.override_receiver_stmin, bool):
                    raise ValueError('override_receiver_stmin must be a float')
                self.override_receiver_stmin = float(self.override_receiver_stmin)

                if self.override_receiver_stmin < 0 or not math.isfinite(self.override_receiver_stmin):
                    raise ValueError('Invalid override_receiver_stmin')

            if not isinstance(self.wftmax, int):
                raise ValueError('wftmax must be an integer')

            if self.wftmax < 0:
                raise ValueError('wftmax must be and integer equal or greater than 0')

            if not isinstance(self.tx_data_length, int):
                raise ValueError('tx_data_length must be an integer')

            if self.tx_data_length not in [8, 12, 16, 20, 24, 32, 48, 64]:
                raise ValueError('tx_data_length must be one of these value : 8, 12, 16, 20, 24, 32, 48, 64 ')

            if self.tx_data_min_length is not None:
                if not isinstance(self.tx_data_min_length, int):
                    raise ValueError('tx_data_min_length must be an integer')

                if self.tx_data_min_length not in [1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64]:
                    raise ValueError('tx_data_min_length must be one of these value : 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64 ')

                if self.tx_data_min_length > self.tx_data_length:
                    raise ValueError('tx_data_min_length cannot be greater than tx_data_length')

            if not isinstance(self.max_frame_size, int):
                raise ValueError('max_frame_size must be an integer')

            if self.max_frame_size < 0:
                raise ValueError('max_frame_size must be a positive integer')

            if not isinstance(self.can_fd, bool):
                raise ValueError('can_fd must be a boolean value')

            if not isinstance(self.bitrate_switch, bool):
                raise ValueError('bitrate_switch must be a boolean value')

            if isinstance(self.default_target_address_type, int):
                self.default_target_address_type = isotp.TargetAddressType(self.default_target_address_type)

            if not isinstance(self.default_target_address_type, isotp.TargetAddressType):
                raise ValueError('default_target_address_type must be an integer or a TargetAddressType instance')

            if self.default_target_address_type not in [isotp.address.TargetAddressType.Physical, isotp.address.TargetAddressType.Functional]:
                raise ValueError('default_target_address_type must be either be Physical (%d) or Functional (%d)' %
                                 (isotp.address.TargetAddressType.Physical.value, isotp.address.TargetAddressType.Functional.value))

            if not isinstance(self.rate_limit_max_bitrate, int):
                raise ValueError('rate_limit_max_bitrate must be an integer')

            if self.rate_limit_max_bitrate <= 0:
                raise ValueError('rate_limit_max_bitrate must be greater than 0')

            if not (isinstance(self.rate_limit_window_size, float) or isinstance(self.rate_limit_window_size, int)):
                raise ValueError('rate_limit_window_size must be a float ')

            if self.rate_limit_window_size <= 0:
                raise ValueError('rate_limit_window_size must be greater than 0')

            if not isinstance(self.rate_limit_enable, bool):
                raise ValueError('rate_limit_enable must be a boolean value')

            if self.rate_limit_max_bitrate * self.rate_limit_window_size < self.tx_data_length * 8:
                raise ValueError(
                    'Rate limiter is so restrictive that a SingleFrame cannot be sent. Please, allow a higher bitrate or increase the window size. (tx_data_length = %d)' % self.tx_data_length)

            if not isinstance(self.listen_mode, bool):
                raise ValueError('listen_mode must be a boolean value')

            if not isinstance(self.blocking_send, bool):
                raise ValueError('blocking_send must be a boolean value')

            if not isinstance(self.logger_name, str):
                raise ValueError('logger_name must be a string')

    class RxState(enum.Enum):
        IDLE = 0
        WAIT_CF = 1

    class TxState(enum.Enum):
        IDLE = 0
        WAIT_FC = 1
        TRANSMIT_CF = 2
        TRANSMIT_SF_STANDBY = 3
        TRANSMIT_FF_STANDBY = 4

    @dataclass
    class SendRequest:
        """An object representing a call to `TransportLayer.send() by the user. Wraps the given parameter and associate with a completion event and a success flag`"""
        data: bytearray
        target_address_type: isotp.address.TargetAddressType
        complete_event: threading.Event
        success: bool

        def __init__(self, data: Union[bytearray, bytes], target_address_type: isotp.address.TargetAddressType):
            self.data = bytearray(data)
            self.target_address_type = target_address_type
            self.complete_event = threading.Event()
            self.success = False

        def complete(self, success: bool) -> None:
            self.success = success
            self.complete_event.set()

    @dataclass(slots=True, frozen=True)
    class ProcessStats:
        """Some statistics produced by every ``process`` called indicating how much has been accomplish during that iteration."""
        received: int
        received_processed: int
        sent: int
        frame_received: int

        def __repr__(self):
            return f'<{self.__class__.__name__} received:{self.received} (processed: {self.received_processed}, sent: {self.sent})>'

    @dataclass(slots=True, frozen=True)
    class ProcessRxReport:
        immediate_tx_required: bool
        frame_received: bool

    @dataclass(slots=True, frozen=True)
    class ProcessTxReport:
        msg: Optional[CanMessage]
        immediate_rx_required: bool

    RxFn = Callable[[Optional[float]], Optional[CanMessage]]
    TxFn = Callable[[CanMessage], None]
    PostSendCallback = Callable[[SendRequest], None]
    ErrorHandler = Callable[[Exception], None]

    params: Params
    logger: logging.Logger
    remote_blocksize: Optional[int]
    rxfn: RxFn
    txfn: TxFn
    tx_queue: "queue.Queue[SendRequest]"
    rx_queue: "queue.Queue[bytearray]"
    tx_standby_msg: Optional[CanMessage]
    rx_state: RxState
    tx_state: TxState
    rx_block_counter: int
    last_seqnum: int
    rx_frame_length: int
    tx_frame_length: int
    last_flow_control_frame: Optional[PDU]
    tx_block_counter: int
    tx_seqnum: int
    wft_counter: int
    pending_flow_control_tx: bool
    timer_tx_stmin: Timer
    error_handler: Optional[ErrorHandler]
    actual_rxdl: Optional[int]
    timings: Dict[Tuple[RxState, TxState], float]
    active_send_request: Optional[SendRequest]
    tx_buffer: bytearray
    rx_buffer: bytearray
    address: isotp.Address
    timer_rx_fc: Timer
    timer_rx_cf: Timer
    rate_limiter: RateLimiter
    blocking_rxfn: bool
    post_send_callback: Optional[PostSendCallback]

    def __init__(self,
                 rxfn: RxFn,
                 txfn: TxFn,
                 address: isotp.Address,
                 error_handler: Optional[ErrorHandler] = None,
                 params: Optional[Dict[str, Any]] = None,
                 post_send_callback: Optional[PostSendCallback] = None
                 ):
        self.post_send_callback = post_send_callback
        self.params = self.Params()
        self.logger = logging.getLogger(self.LOGGER_NAME)

        if params is not None:
            for k in params:
                self.params.set(k, params[k], validate=False)
        self.params.validate()

        self.logger = logging.getLogger(self.params.logger_name)

        self.remote_blocksize = None  # Block size received in Flow Control message

        # Backward compatibility. Handle rxfn with no params as non-blocking
        if len(inspect.signature(rxfn).parameters) < 1:
            self.rxfn = lambda x: rxfn()    # type: ignore
            self.blocking_rxfn = False
            self.logger.debug("Given rxfn is considered non-blocking")
        else:
            self.rxfn = rxfn 	# Function to call to receive a CAN message
            self.blocking_rxfn = True
            self.logger.debug("Given rxfn is considered blocking")

        self.txfn = txfn 	# Function to call to receive a CAN message

        self.set_address(address)

        self.tx_queue = queue.Queue()			# Layer Input queue for IsoTP frame
        self.rx_queue = queue.Queue()			# Layer Output queue for IsoTP frame
        self.tx_standby_msg = None              # Pending message when throttling is active
        self.active_send_request = None         # The user request for sending. Contains a synchronizing event for blocking send

        self.rx_state = self.RxState.IDLE		# State of the reception FSM
        self.tx_state = self.TxState.IDLE		# State of the transmission FSM

        self.last_rx_state = self.rx_state      # Used to log changes in states
        self.last_tx_state = self.tx_state      # Used to log changes in states

        self.rx_block_counter = 0               # Keeps track of how many block we've received. Used to determine when to send a flow control message
        self.last_seqnum = 0					# Consecutive frame Sequence number of previous message
        self.rx_frame_length = 0				# Length of IsoTP frame being received at the moment
        self.tx_frame_length = 0				# Length of the data that we are sending
        self.last_flow_control_frame = None		# When a FlowControl is received. Put here
        self.tx_block_counter = 0				# Keeps track of how many block we've sent. USed to determine when to wait for a flow control message
        self.tx_seqnum = 0						# Keeps track of the actual sequence number while sending
        self.wft_counter = 0 					# Keeps track of how many wait frame we've received

        self.pending_flow_control_tx = False    # Flag indicating that we need to transmit a flow control message. Set by Rx Process, Cleared by Tx Process
        self._empty_rx_buffer()
        self._empty_tx_buffer()

        self.timer_tx_stmin = Timer(timeout=0)

        self.error_handler = error_handler
        self.actual_rxdl = None                 # Length of the CAN messages during a reception. Set by the first frame. All consecutive frames must be identical

        # Legacy (v1.x) timing recommendation
        self.timings = {
            (self.RxState.IDLE, self.TxState.IDLE): 0.02,
            (self.RxState.IDLE, self.TxState.WAIT_FC): 0.005,
        }

        self.load_params()

    def load_params(self) -> None:
        self.params.validate()
        self.timer_rx_fc = Timer(timeout=float(self.params.rx_flowcontrol_timeout) / 1000)
        self.timer_rx_cf = Timer(timeout=float(self.params.rx_consecutive_frame_timeout) / 1000)

        self.rate_limiter = RateLimiter(mean_bitrate=self.params.rate_limit_max_bitrate, window_size_sec=self.params.rate_limit_window_size)
        if self.params.rate_limit_enable:
            self.rate_limiter.enable()

    def send(self,
             data: Union[bytes, bytearray],
             target_address_type: Optional[Union[isotp.address.TargetAddressType, int]] = None,
             send_timeout: float = 0):
        """
        Enqueue an IsoTP frame to be sent over CAN network.
        When performing a blocking send, this method returns only when the transmission is complete or raise an exception when a failure or a timeout occurs.
        See :ref:`blocking_send<param_blocking_send>`

        :param data: The data to be sent
        :type data: bytearray

        :param target_address_type: Optional parameter that can be Physical (0) for 1-to-1 communication or Functional (1) for 1-to-n. 
            See :class:`isotp.TargetAddressType<isotp.TargetAddressType>`.
            If not provided, parameter :ref:`default_target_address_type<param_default_target_address_type>` will be used (default to ``Physical``)
        :type target_address_type: int

        :param send_timeout: Timeout value for blocking send. Unused if :ref:`blocking_send<param_blocking_send>` is ``False``
        :type send_timeout: float

        :raises ValueError: Input parameter is not a bytearray or not convertible to bytearray
        :raises RuntimeError: Transmit queue is full
        :raises BlockingSendTimeout: When :ref:`blocking_send<param_blocking_send>` is set to ``True`` and the send operation does not complete in the given timeout.
        :raises BlockingSendFailure: When :ref:`blocking_send<param_blocking_send>` is set to ``True`` and the transmission failed for any reason (e.g. unexpected frame or bad timings), including a timeout. Note that 
            :class:`BlockingSendTimeout<BlockingSendTimeout>` inherits :class:`BlockingSendFailure<BlockingSendFailure>`.
        """

        if target_address_type is None:
            target_address_type = self.params.default_target_address_type
        else:
            target_address_type = isotp.address.TargetAddressType(target_address_type)

        if not isinstance(data, bytearray):
            try:
                data = bytearray(data)
            except:
                raise ValueError('data must be a bytearray')

        if self.tx_queue.full():
            raise RuntimeError('Transmit queue is full')

        if target_address_type == isotp.address.TargetAddressType.Functional:
            length_bytes = 1 if self.params.tx_data_length == 8 else 2
            maxlen = self.params.tx_data_length - length_bytes - len(self.address.tx_payload_prefix)

            if len(data) > maxlen:
                raise ValueError('Cannot send multi packet frame with Functional TargetAddressType')

        send_request = self.SendRequest(data=data, target_address_type=target_address_type)
        if self.params.blocking_send:
            send_request.complete_event.clear()

        self.logger.debug("Enqueuing a SendRequest for %d bytes and TAT=%s" % (len(send_request.data), target_address_type.name))
        self.tx_queue.put(send_request)
        if self.post_send_callback is not None:
            self.post_send_callback(send_request)

        if self.params.blocking_send:
            send_request.complete_event.wait(send_timeout)
            if not send_request.complete_event.is_set():
                raise isotp.errors.BlockingSendTimeout("Failed to send IsoTP frame in time")
            else:
                if not send_request.success:
                    isotp.errors.BlockingSendFailure("Error while sending IsoTP frame")

    # Receive an IsoTP frame. Output of the layer
    def recv(self, block: bool = False, timeout: Optional[float] = None) -> Optional[bytearray]:
        """
        Dequeue an IsoTP frame from the reception queue if available.

        :return: The next available IsoTP frame
        :rtype: bytearray or None
        """
        try:
            return self.rx_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def available(self) -> bool:
        """
        Returns ``True`` if an IsoTP frame is awaiting in the reception ``queue``. ``False`` otherwise
        """
        return not self.rx_queue.empty()

    def transmitting(self) -> bool:
        """
        Returns ``True`` if an IsoTP frame is being transmitted. ``False`` otherwise
        """
        return not self.tx_queue.empty() or self.tx_state != self.TxState.IDLE

    def process(self, rx_timeout: float = 0.0, do_rx: bool = True, do_tx: bool = True) -> ProcessStats:
        """
        Function to be called periodically, as fast as possible. 
        This function is expected to block only if the given rxfn performs a blocking read.
        """
        run_process = True
        msg_received = 0
        msg_received_processed = 0
        msg_sent = 0
        nb_frame_received = 0

        # Run as long as RxStateMachine or Tx StateMachine request the other state machine to immediatly do a pass.
        # Prevent useless latency in FSM processing
        while run_process:
            msg: Optional[CanMessage] = None
            run_process = False

            #  if we have data to send and nothing else in process. start by sending that data. Avoid blocking in rxfn for nothing.
            start_with_tx = do_tx \
                and not self.tx_queue.empty() \
                and self.rx_state == self.RxState.IDLE \
                and self.tx_state == self.TxState.IDLE

            if start_with_tx:
                run_process = True

            if do_rx and not start_with_tx:
                first_loop = True
                while msg is not None or first_loop:
                    first_loop = False
                    msg = self.rxfn(rx_timeout)
                    self._check_timeouts_rx()    # Check for every message because rxfn may be blocking since v2.x. Always execute, even if msg=None (issue #41)
                    if msg is not None:

                        msg_received += 1
                        for_me = self.address.is_for_me(msg)
                        if self.logger.isEnabledFor(logging.DEBUG):
                            addr = "%08X" % msg.arbitration_id if msg.is_extended_id else "%03X" % msg.arbitration_id
                            processed = 'p' if for_me else 'i'  # processed/ignored
                            self.logger.debug("Rx: <%s> (%02d) [%s]\t %s" % (addr,
                                                                             len(msg.data), processed, binascii.hexlify(msg.data).decode('ascii')))
                        if for_me:
                            msg_received_processed += 1
                            rx_result = self._process_rx(msg)
                            if rx_result.frame_received:
                                nb_frame_received += 1
                            if rx_result.immediate_tx_required:
                                break

            start_with_tx = False   # it's a one-time event

            self.rate_limiter.update()  # Only applies to transmission. Update after rxfn because it can be blocking.
            if do_tx:
                first_loop = True
                msg = None
                while msg is not None or first_loop:
                    first_loop = False
                    tx_result = self._process_tx()
                    msg = tx_result.msg
                    if msg is not None:
                        msg_sent += 1
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug("Tx: <%03X> (%02d) [ ]\t %s" % (msg.arbitration_id,
                                                                              len(msg.data), binascii.hexlify(msg.data).decode('ascii')))
                        self.txfn(msg)

                    if tx_result.immediate_rx_required:
                        run_process = True
                        break

            if self.logger.isEnabledFor(logging.DEBUG):
                if self.last_rx_state != self.rx_state or self.last_tx_state != self.tx_state:
                    self.logger.debug(f"TxState={self.tx_state.name} - RxState={self.rx_state.name}")
            self.last_tx_state = self.tx_state
            self.last_rx_state = self.rx_state

        return self.ProcessStats(
            received=msg_received,
            received_processed=msg_received_processed,
            sent=msg_sent,
            frame_received=nb_frame_received
        )

    def set_rxfn(self, rxfn: "TransportLayerLogic.RxFn"):
        """
        Allow post init change of rxfn. This is a trick to implement the threaded Transport Layer
        and keeping the ability to run the TransportLayerLogic without threads for backward compatibility
        with v1.x
        """
        self.rxfn = rxfn

    def _check_timeouts_rx(self) -> None:
        if self.timer_rx_cf.is_timed_out():
            self._trigger_error(isotp.errors.ConsecutiveFrameTimeoutError("Reception of CONSECUTIVE_FRAME timed out."))
            self._stop_receiving()

    def _process_rx(self, msg: CanMessage) -> ProcessRxReport:
        """Process the reception of a CAN message. Moves the reception state machine accordingly and optionally"""
        # Decoding of message into PDU
        try:
            pdu = PDU(msg, start_of_data=self.address.rx_prefix_size)
        except Exception as e:
            self._trigger_error(isotp.errors.InvalidCanDataError("Received invalid CAN frame. %s" % (str(e))))
            self._stop_receiving()
            return self.ProcessRxReport(immediate_tx_required=False, frame_received=False)

        # Process Flow Control message
        if pdu.type == PDU.Type.FLOW_CONTROL:
            self.last_flow_control_frame = pdu 	 # Given to _process_tx method. Queue of 1 message depth
            # Nothing else to be done with FlowControl. Return and run _process_tx right away
            return self.ProcessRxReport(immediate_tx_required=True, frame_received=False)

        frame_complete = False
        if pdu.type == PDU.Type.SINGLE_FRAME:
            if pdu.can_dl > 8 and pdu.escape_sequence == False:
                self._trigger_error(isotp.errors.MissingEscapeSequenceError(
                    'For SingleFrames conveyed on a CAN message with data length (CAN_DL) > 8, length should be encoded on byte #1 and byte #0 should be 0x00'))
                return self.ProcessRxReport(immediate_tx_required=False, frame_received=False)

        immediate_tx_msg_required = False

        # Process the state machine
        if self.rx_state == self.RxState.IDLE:
            self.rx_frame_length = 0
            self.timer_rx_cf.stop()
            if pdu.type == PDU.Type.SINGLE_FRAME:
                if pdu.data is not None:
                    frame_complete = True
                    self.rx_queue.put(bytearray(pdu.data))

            elif pdu.type == PDU.Type.FIRST_FRAME:
                started = self._start_reception_after_first_frame_if_valid(pdu)
                immediate_tx_msg_required = immediate_tx_msg_required or started
            elif pdu.type == PDU.Type.CONSECUTIVE_FRAME:
                self._trigger_error(isotp.errors.UnexpectedConsecutiveFrameError('Received a ConsecutiveFrame while reception was idle. Ignoring'))

        elif self.rx_state == self.RxState.WAIT_CF:
            if pdu.type == PDU.Type.SINGLE_FRAME:
                if pdu.data is not None:
                    frame_complete = True
                    self.rx_queue.put(bytearray(pdu.data))
                    self.rx_state = self.RxState.IDLE
                    self._trigger_error(isotp.errors.ReceptionInterruptedWithSingleFrameError(
                        'Reception of IsoTP frame interrupted with a new SingleFrame'))

            elif pdu.type == PDU.Type.FIRST_FRAME:
                started = self._start_reception_after_first_frame_if_valid(pdu)
                immediate_tx_msg_required = immediate_tx_msg_required or started
                self._trigger_error(isotp.errors.ReceptionInterruptedWithFirstFrameError(
                    'Reception of IsoTP frame interrupted with a new FirstFrame'))

            elif pdu.type == PDU.Type.CONSECUTIVE_FRAME:
                expected_seqnum = (self.last_seqnum + 1) & 0xF
                if pdu.seqnum == expected_seqnum:
                    bytes_to_receive = (self.rx_frame_length - len(self.rx_buffer))
                    if pdu.rx_dl != self.actual_rxdl and pdu.rx_dl < bytes_to_receive:
                        self._trigger_error(isotp.errors.ChangingInvalidRXDLError(
                            "Received a ConsecutiveFrame with RX_DL=%s while expected RX_DL=%s. Ignoring frame" % (pdu.rx_dl, self.actual_rxdl)))
                        return self.ProcessRxReport(immediate_tx_required=False, frame_received=False)

                    self._start_rx_cf_timer() 	# Received a CF message. Restart counter. Timeout handled above.
                    self.last_seqnum = pdu.seqnum
                    self._append_rx_data(pdu.data[:bytes_to_receive])  # Python handle overflow
                    if len(self.rx_buffer) >= self.rx_frame_length:
                        frame_complete = True
                        self.rx_queue.put(copy(self.rx_buffer))			# Data complete
                        self._stop_receiving() 							# Go back to IDLE. Reset all variables and timers.
                    else:
                        self.rx_block_counter += 1
                        if self.params.blocksize > 0 and (self.rx_block_counter % self.params.blocksize) == 0:
                            self._request_tx_flowcontrol(PDU.FlowStatus.ContinueToSend)  	 # Sets a flag to 1. _process_tx will send it for use.
                            # We stop the timer until the flow control message is gone. This timer is reactivated in the _process_tx().
                            self.timer_rx_cf.stop()
                            immediate_tx_msg_required = True
                else:
                    self._stop_receiving()
                    received = str(None)
                    if pdu.seqnum is not None:
                        received = "0x%02X" % pdu.seqnum
                    self._trigger_error(isotp.errors.WrongSequenceNumberError(
                        'Received a ConsecutiveFrame with wrong SequenceNumber. Expecting 0x%02X, Received %s' % (expected_seqnum, received)))

        if self.pending_flow_control_tx:
            immediate_tx_msg_required = True

        return self.ProcessRxReport(immediate_tx_required=immediate_tx_msg_required, frame_received=frame_complete)

    def _process_tx(self) -> ProcessTxReport:
        """Process the transmit state machine"""
        output_msg = None 	 # Value outputted.  If None, no subsequent call to _process_tx will be done.
        allowed_bytes = self.rate_limiter.allowed_bytes()

        # Sends flow control if _process_rx requested it
        if self.pending_flow_control_tx:
            self.pending_flow_control_tx = False
            if self.pending_flowcontrol_status == PDU.FlowStatus.ContinueToSend:
                self._start_rx_cf_timer()    # We tell the sending party that it can continue to send data, so we start checking the timeout again

            if not self.params.listen_mode:  # Inhibit Flow Control in listen mode.
                flow_control_msg = self._make_flow_control(flow_status=self.pending_flowcontrol_status)

                return self.ProcessTxReport(msg=flow_control_msg, immediate_rx_required=True)   # No need to wait. Needs to run _process_rx right away

        # Handle flow control reception
        flow_control_frame = self.last_flow_control_frame  # Reads the last message received and clears it. (Dequeue message)
        self.last_flow_control_frame = None

        if flow_control_frame is not None:
            if flow_control_frame.flow_status == PDU.FlowStatus.Overflow: 	# Needs to stop sending.
                self._stop_sending(success=False)
                self._trigger_error(isotp.errors.OverflowError('Received a FlowControl PDU indicating an Overflow. Stopping transmission.'))
                return self.ProcessTxReport(msg=None, immediate_rx_required=False)

            if self.tx_state == self.TxState.IDLE:
                self._trigger_error(isotp.errors.UnexpectedFlowControlError('Received a FlowControl message while transmission was Idle. Ignoring'))
            else:
                if flow_control_frame.flow_status == PDU.FlowStatus.Wait:
                    if self.params.wftmax == 0:
                        self._trigger_error(isotp.errors.UnsupportedWaitFrameError(
                            'Received a FlowControl requesting to wait, but wftmax is set to 0'))
                    elif self.wft_counter >= self.params.wftmax:
                        self._trigger_error(isotp.errors.MaximumWaitFrameReachedError(
                            'Received %d wait frame which is the maximum set in params.wftmax' % (self.wft_counter)))
                        self._stop_sending(success=False)
                    else:
                        self.wft_counter += 1
                        if self.tx_state in [self.TxState.WAIT_FC, self.TxState.TRANSMIT_CF]:
                            self.tx_state = self.TxState.WAIT_FC
                            self._start_rx_fc_timer()

                elif flow_control_frame.flow_status == PDU.FlowStatus.ContinueToSend and not self.timer_rx_fc.is_timed_out():
                    self.wft_counter = 0
                    self.timer_rx_fc.stop()
                    assert flow_control_frame.stmin_sec is not None
                    if self.params.override_receiver_stmin is not None:
                        self.timer_tx_stmin.set_timeout(self.params.override_receiver_stmin)
                    else:
                        self.timer_tx_stmin.set_timeout(flow_control_frame.stmin_sec)
                    self.remote_blocksize = flow_control_frame.blocksize

                    if self.tx_state == self.TxState.WAIT_FC:
                        self.tx_block_counter = 0
                        self.timer_tx_stmin.start()
                    elif self.tx_state == self.TxState.TRANSMIT_CF:
                        pass

                    self.tx_state = self.TxState.TRANSMIT_CF

        # ======= Timeouts ======
        if self.timer_rx_fc.is_timed_out():
            self._trigger_error(isotp.errors.FlowControlTimeoutError('Reception of FlowControl timed out. Stopping transmission'))
            self._stop_sending(success=False)

        # ======= FSM ======
        # Check this first as we may have another isotp frame to send and we need to handle it right away without waiting for next "process()" call
        if self.tx_state != self.TxState.IDLE and len(self.tx_buffer) == 0:
            self._stop_sending(success=True)

        immediate_rx_msg_required = False
        if self.tx_state == self.TxState.IDLE:
            read_tx_queue = True  # Read until we get non-empty frame to send
            while read_tx_queue:
                read_tx_queue = False
                if not self.tx_queue.empty():
                    self.active_send_request = self.tx_queue.get()
                    if len(self.active_send_request.data) == 0:
                        read_tx_queue = True  # Read another frame from tx_queue
                        self.active_send_request.complete(True)
                    else:
                        self.tx_buffer = bytearray(self.active_send_request.data)
                        size_on_first_byte = (len(self.tx_buffer) + len(self.address.tx_payload_prefix)) <= 7
                        size_offset = 1 if size_on_first_byte else 2

                        # Single frame
                        if len(self.tx_buffer) <= self.params.tx_data_length - size_offset - len(self.address.tx_payload_prefix):
                            if size_on_first_byte:
                                msg_data = self.address.tx_payload_prefix + bytearray([0x0 | len(self.tx_buffer)]) + self.tx_buffer
                            else:
                                msg_data = self.address.tx_payload_prefix + bytearray([0x0, len(self.tx_buffer)]) + self.tx_buffer

                            arbitration_id = self.address.get_tx_arbitration_id(self.active_send_request.target_address_type)
                            msg_temp = self._make_tx_msg(arbitration_id, msg_data)

                            if len(msg_data) > allowed_bytes:
                                self.tx_standby_msg = msg_temp
                                self.tx_state = self.TxState.TRANSMIT_SF_STANDBY
                            else:
                                output_msg = msg_temp

                        # Multi frame - First Frame
                        else:
                            self.tx_frame_length = len(self.tx_buffer)
                            encode_length_on_2_first_bytes = True if self.tx_frame_length <= 0xFFF else False
                            if encode_length_on_2_first_bytes:
                                data_length = self.params.tx_data_length - 2 - len(self.address.tx_payload_prefix)
                                msg_data = self.address.tx_payload_prefix + \
                                    bytearray([0x10 | ((self.tx_frame_length >> 8) & 0xF), self.tx_frame_length & 0xFF]) + self.tx_buffer[:data_length]
                            else:
                                data_length = self.params.tx_data_length - 6 - len(self.address.tx_payload_prefix)
                                msg_data = self.address.tx_payload_prefix + bytearray([0x10, 0x00, (self.tx_frame_length >> 24) & 0xFF, (self.tx_frame_length >> 16) & 0xFF, (
                                    self.tx_frame_length >> 8) & 0xFF, (self.tx_frame_length >> 0) & 0xFF]) + self.tx_buffer[:data_length]

                            arbitration_id = self.address.get_tx_arbitration_id()
                            self.tx_buffer = self.tx_buffer[data_length:]
                            self.tx_seqnum = 1
                            msg_temp = self._make_tx_msg(arbitration_id, msg_data)
                            if len(msg_data) <= allowed_bytes:
                                output_msg = msg_temp
                                self.tx_state = self.TxState.WAIT_FC
                                self._start_rx_fc_timer()
                            else:
                                self.tx_standby_msg = msg_temp
                                self.tx_state = self.TxState.TRANSMIT_FF_STANDBY

        elif self.tx_state in [self.TxState.TRANSMIT_SF_STANDBY, self.TxState.TRANSMIT_FF_STANDBY]:
            # This states serves if the rate limiter prevent from starting a new transmission.
            # We need to pop the isotp frame to know if the rate limiter must kick, but since the data is already popped,
            # we can't stay in IDLE state. So we come here until the rate limiter gives us permission to proceed.

            if self.tx_standby_msg is not None:
                if len(self.tx_standby_msg.data) <= allowed_bytes:
                    output_msg = self.tx_standby_msg
                    self.tx_standby_msg = None

                    if self.tx_state == self.TxState.TRANSMIT_FF_STANDBY:
                        self._start_rx_fc_timer()
                        self.tx_state = self.TxState.WAIT_FC    # After a first frame, we wait for flow control
                    else:
                        self.tx_state = self.TxState.IDLE   # After a single frame, there's nothing to do

        elif self.tx_state == self.TxState.WAIT_FC:
            pass  # Nothing to do. Flow control will make the FSM switch state by calling init_tx_consecutive_frame

        elif self.tx_state == self.TxState.TRANSMIT_CF:
            assert self.remote_blocksize is not None
            if self.timer_tx_stmin.is_timed_out():
                data_length = self.params.tx_data_length - 1 - len(self.address.tx_payload_prefix)
                msg_data = self.address.tx_payload_prefix + bytearray([0x20 | self.tx_seqnum]) + self.tx_buffer[:data_length]
                arbitration_id = self.address.get_tx_arbitration_id()
                msg_temp = self._make_tx_msg(arbitration_id, msg_data)
                if len(msg_temp.data) <= allowed_bytes:
                    output_msg = msg_temp
                    self.tx_buffer = self.tx_buffer[data_length:]
                    self.tx_seqnum = (self.tx_seqnum + 1) & 0xF
                    self.timer_tx_stmin.start()
                    self.tx_block_counter += 1

            if (len(self.tx_buffer) == 0):
                self._stop_sending(success=True)

            elif self.remote_blocksize != 0 and self.tx_block_counter >= self.remote_blocksize:
                self.tx_state = self.TxState.WAIT_FC
                immediate_rx_msg_required = True
                self._start_rx_fc_timer()

        if output_msg is not None:
            self.rate_limiter.inform_byte_sent(len(output_msg.data))

        return self.ProcessTxReport(msg=output_msg, immediate_rx_required=immediate_rx_msg_required)

    def set_sleep_timing(self, idle: float, wait_fc: float) -> None:
        """
        Sets values in seconds that can be passed to ``time.sleep()`` when the stack is processed in a different thread.
        """
        self.timings = {
            (self.RxState.IDLE, self.TxState.IDLE): idle,
            (self.RxState.IDLE, self.TxState.WAIT_FC): wait_fc,
        }

    def set_address(self, address: isotp.address.Address):
        """
        Sets the layer :class:`Address<isotp.Address>`. Can be set after initialization if needed.
        """

        if not isinstance(address, isotp.address.Address):
            raise ValueError('address must be a valid Address instance')

        self.address = address

        if self.address.txid is not None and (self.address.txid > 0x7F4 and self.address.txid < 0x7F6 or self.address.txid > 0x7FA and self.address.txid < 0x7FB):
            self.logger.warning('Used txid overlaps the range of ID reserved by ISO-15765 (0x7F4-0x7F6 and 0x7FA-0x7FB)')

        if self.address.rxid is not None and (self.address.rxid > 0x7F4 and self.address.rxid < 0x7F6 or self.address.rxid > 0x7FA and self.address.rxid < 0x7FB):
            self.logger.warning('Used rxid overlaps the range of ID reserved by ISO-15765 (0x7F4-0x7F6 and 0x7FA-0x7FB)')

    def _pad_message_data(self, msg_data: bytes) -> bytes:
        """Pad a message if required with the proper padding byte according to the configuration"""
        must_pad = False
        padding_byte = 0xCC if self.params.tx_padding is None else self.params.tx_padding

        if self.params.tx_data_length == 8:
            if self.params.tx_data_min_length is None:
                if self.params.tx_padding is not None:     # ISO-15765:2016 - 10.4.2.1
                    must_pad = True
                    target_length = 8
                else:   # ISO-15765:2016 - 10.4.2.2
                    pass

            else:       # issue #27
                must_pad = True
                target_length = self.params.tx_data_min_length

        elif self.params.tx_data_length > 8:
            if self.params.tx_data_min_length is None:  # ISO-15765:2016 - 10.4.2.3
                target_length = self._get_nearest_can_fd_size(len(msg_data))
                must_pad = True
            else:               # Issue #27
                must_pad = True
                target_length = max(self.params.tx_data_min_length, self._get_nearest_can_fd_size(len(msg_data)))

        if must_pad and len(msg_data) < target_length:
            return msg_data + bytes([padding_byte & 0xFF] * (target_length - len(msg_data)))

        return msg_data

    def _empty_rx_buffer(self) -> None:
        self.rx_buffer = bytearray()

    def _empty_tx_buffer(self) -> None:
        self.tx_buffer = bytearray()

    def _start_rx_fc_timer(self) -> None:
        self.timer_rx_fc = Timer(timeout=float(self.params.rx_flowcontrol_timeout) / 1000)
        self.timer_rx_fc.start()

    def _start_rx_cf_timer(self) -> None:
        self.timer_rx_cf = Timer(timeout=float(self.params.rx_consecutive_frame_timeout) / 1000)
        self.timer_rx_cf.start()

    def _append_rx_data(self, data) -> None:
        self.rx_buffer.extend(data)

    def _request_tx_flowcontrol(self, status=PDU.FlowStatus.ContinueToSend) -> None:
        self.pending_flow_control_tx = True
        self.pending_flowcontrol_status = status

    def _stop_sending_flow_control(self) -> None:
        self.pending_flow_control_tx = False
        self.last_flow_control_frame = None

    def _make_tx_msg(self, arbitration_id: int, data: bytes) -> CanMessage:
        data = self._pad_message_data(data)
        return CanMessage(
            arbitration_id=arbitration_id,
            dlc=self._get_dlc(data, validate_tx=True),
            data=data,
            extended_id=self.address.is_29bits,
            is_fd=self.params.can_fd,
            bitrate_switch=self.params.bitrate_switch
        )

    def _get_dlc(self, data: bytes, validate_tx: bool = False) -> int:
        fdlen = self._get_nearest_can_fd_size(len(data))
        if validate_tx:
            if self.params.tx_data_length == 8:
                if fdlen < 2 or fdlen > 8:
                    raise ValueError("Impossible DLC size for payload of %d bytes with tx_data_length of %d" %
                                     (len(data), self.params.tx_data_length))

        if fdlen >= 2 and fdlen <= 8: return fdlen
        elif fdlen == 12: return 9
        elif fdlen == 16: return 10
        elif fdlen == 20: return 11
        elif fdlen == 24: return 12
        elif fdlen == 32: return 13
        elif fdlen == 48: return 14
        elif fdlen == 64: return 15
        raise ValueError("Impossible DLC size for payload of %d bytes with tx_data_length of %d" % (len(data), self.params.tx_data_length))

    def _get_nearest_can_fd_size(self, size: int) -> int:
        if size <= 8:
            return size
        if size <= 12: return 12
        if size <= 16: return 16
        if size <= 20: return 20
        if size <= 24: return 24
        if size <= 32: return 32
        if size <= 48: return 48
        if size <= 64: return 64
        raise ValueError("Impossible data size for CAN FD : %d " % (size))

    def _make_flow_control(self, flow_status: int = PDU.FlowStatus.ContinueToSend, blocksize: Optional[int] = None, stmin: Optional[int] = None):
        if blocksize is None:
            blocksize = self.params.blocksize

        if stmin is None:
            stmin = self.params.stmin
        data = PDU.craft_flow_control_data(flow_status, blocksize, stmin)

        return self._make_tx_msg(self.address.get_tx_arbitration_id(), self.address.tx_payload_prefix + data)

    def stop_sending(self) -> None:
        """
        Request the TransportLayer object to stop transmitting, clear the transmit buffer and put back its transmit state machine to idle state.
        """
        self._stop_sending(success=False)

    def _stop_sending(self, success) -> None:
        if self.active_send_request is not None:
            self.active_send_request.complete(success)
            self.active_send_request = None
        self._empty_tx_buffer()
        self.tx_state = self.TxState.IDLE
        self.tx_frame_length = 0
        self.timer_rx_fc.stop()
        self.timer_tx_stmin.stop()
        self.remote_blocksize = None
        self.tx_block_counter = 0
        self.tx_seqnum = 0
        self.wft_counter = 0
        self.tx_standby_msg = None

    def stop_receiving(self) -> None:
        """
        Request the TransportLayer object to stop receiving, clear the reception buffer and put back its receive state machine to idle state. 
        If a reception is ongoing, the following messages will be discared and considered like garbage
        """
        self._stop_receiving()

    def _stop_receiving(self) -> None:

        self.actual_rxdl = None
        self.rx_state = self.RxState.IDLE
        self._empty_rx_buffer()
        self._stop_sending_flow_control()
        self.timer_rx_cf.stop()

    def clear_rx_queue(self):
        while not self.rx_queue.empty():
            self.rx_queue.get_nowait()

    def clear_tx_queue(self):
        while not self.tx_queue.empty():
            self.tx_queue.get_nowait()

    # Init the reception of a multi-pdu frame.
    def _start_reception_after_first_frame_if_valid(self, pdu: PDU) -> bool:
        assert pdu.length is not None
        self._empty_rx_buffer()
        if pdu.rx_dl not in [8, 12, 16, 20, 24, 32, 48, 64]:
            self._trigger_error(isotp.errors.InvalidCanFdFirstFrameRXDL(
                "Received a FirstFrame with a RX_DL value of %d which is invalid according to ISO-15765-2" % (pdu.rx_dl)))
            self._stop_receiving()
            return False

        self.actual_rxdl = pdu.rx_dl

        started = False
        if pdu.length > self.params.max_frame_size:
            self._trigger_error(isotp.errors.FrameTooLongError(
                "Received a First Frame with a length of %d bytes, but params.max_frame_size is set to %d bytes. Ignoring" % (pdu.length, self.params.max_frame_size)))
            self._request_tx_flowcontrol(PDU.FlowStatus.Overflow)
            self.rx_state = self.RxState.IDLE
        else:
            self.rx_state = self.RxState.WAIT_CF
            self.rx_frame_length = pdu.length
            self._append_rx_data(pdu.data)
            self._request_tx_flowcontrol(PDU.FlowStatus.ContinueToSend)
            self._start_rx_cf_timer()
            started = True

        self.last_seqnum = 0
        self.rx_block_counter = 0

        return started

    def _trigger_error(self, error: isotp.errors.IsoTpError) -> None:
        if self.error_handler is not None:
            if hasattr(self.error_handler, '__call__') and isinstance(error, isotp.errors.IsoTpError):
                self.error_handler(error)
            else:
                self.logger.warning('Given error handler is not a callable object.')

        self.logger.warning(str(error))

    # Clears everything within the layer.
    def reset(self) -> None:
        """
        Reset the layer: Empty all buffers, set the internal state machines to Idle
        """
        self.clear_rx_queue()
        self.clear_tx_queue()
        self._stop_sending(success=False)
        self._stop_receiving()

        self.rate_limiter.reset()

    # Gives a time to pass to time.sleep() based on the state of the FSM. Avoid using too much CPU
    def sleep_time(self) -> float:
        """
        Returns a value in seconds that can be passed to ``time.sleep()`` when the stack is processed in a different thread.

        The value will change according to the internal state machine state, sleeping longer while idle and shorter when active.
        """

        key = (self.rx_state, self.tx_state)
        if key in self.timings:
            return self.timings[key]
        else:
            return 0.001

    def is_tx_throttled(self) -> bool:
        """Tells if the transmission is actively being slowed down by the rate limited"""
        return self.tx_state in [self.TxState.TRANSMIT_SF_STANDBY, self.TxState.TRANSMIT_FF_STANDBY]

    def is_rx_active(self) -> bool:
        return self.rx_state != self.RxState.IDLE

    def is_tx_transmitting_cf(self) -> bool:
        return self.tx_state == self.TxState.TRANSMIT_CF

    def next_cf_delay(self) -> Optional[float]:
        if not self.is_tx_transmitting_cf():
            return None

        if self.timer_tx_stmin.is_timed_out():
            return 0
        return self.timer_tx_stmin.remaining()


class TransportLayer(TransportLayerLogic):
    """
    An IsoTP transport layer implementation that runs in a separate thread. The main public interface are ``start``, ``stop``, ``send``, ``recv``.
    For backward compatibility, this class will behave similarly as a V1 TransportLayer if start/stop are never called; meaning that ``process()`` can be called by the user

    :param rxfn: Function to be called by the transport layer to read the CAN layer. Must return a :class:`isotp.CanMessage<isotp.CanMessage>` or None if no message has been received.
        For optimal performance, this function should perform a blocking read that waits on IO
    :type rxfn: Callable : expected signature: ``my_txfn(msg:isotp.CanMessage) -> None``

    :param txfn: Function to be called by the transport layer to send a message on the CAN layer. This function should receive a :class:`isotp.CanMessage<isotp.CanMessage>`
    :type txfn: Callable : expected signature: ``my_rxfn(timeout:float) -> Optional[isotp.CanMessage]``

    :param address: The address information of CAN messages. Includes the addressing mode, txid/rxid, source/target address and address extension. See :class:`isotp.Address<isotp.Address>` for more details.
    :type address: isotp.Address

    :param error_handler: A function to be called when an error has been detected. 
        An :class:`isotp.IsoTpError<isotp.IsoTpError>` (inheriting Exception class) will be given as sole parameter. See the :ref:`Error section<Errors>`
        When started, the error handler will be called from a different thread than the user thread, make sure to consider thread safety if the error handler is more complex than a log.
    :type error_handler: Callable

    :param params: List of parameters for the transport layer. See :ref:`the list of parameters<parameters>`
    :type params: dict
    """
    class Events:
        main_thread_ready: threading.Event
        relay_thread_ready: threading.Event
        stop_requested: threading.Event
        reset_tx: threading.Event
        reset_rx: threading.Event

        def __init__(self):
            self.main_thread_ready = threading.Event()
            self.relay_thread_ready = threading.Event()
            self.stop_requested = threading.Event()
            self.reset_tx = threading.Event()
            self.reset_rx = threading.Event()

    started: bool
    main_thread: Optional[threading.Thread]
    relay_thread: Optional[threading.Thread]
    default_read_timeout: float
    events: Events
    rx_relay_queue: "queue.Queue[Optional[CanMessage]]"
    user_rxfn: TransportLayerLogic.RxFn

    def __init__(self,
                 rxfn: TransportLayerLogic.RxFn,
                 txfn: TransportLayerLogic.TxFn,
                 address: isotp.Address,
                 error_handler: Optional[TransportLayerLogic.ErrorHandler] = None,
                 params: Optional[Dict[str, Any]] = None,
                 read_timeout=0.05):

        self.rx_relay_queue = queue.Queue()
        self.started = False
        self.main_thread = None
        self.default_read_timeout = read_timeout
        self.events = self.Events()
        self.user_rxfn = rxfn   # Used by the relay thread

        def post_send_callback(send_request: TransportLayer.SendRequest) -> None:
            # This callback wakeup the main thread from its blocking read if necessary
            self.rx_relay_queue.put(None)

        TransportLayerLogic.__init__(self, rxfn, txfn, address, error_handler, params, post_send_callback)

    def _read_relay_queue(self, timeout: Optional[float]) -> Optional[CanMessage]:
        try:
            return self.rx_relay_queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def start(self) -> None:
        """Start the internal thread that handles the IsoTP layer."""
        self.logger.debug(f"Starting {self.__class__.__name__}")
        if self.started:
            raise RuntimeError("Transport Layer is already started")

        self.set_rxfn(self._read_relay_queue)
        self.main_thread = threading.Thread(target=self._main_thread_fn)
        self.relay_thread = threading.Thread(target=self._relay_thread_fn)

        self.events.main_thread_ready.clear()
        self.events.relay_thread_ready.clear()
        self.events.stop_requested.clear()
        self.events.reset_tx.clear()
        self.events.reset_rx.clear()

        self.main_thread.start()
        self.relay_thread.start()

        self.events.main_thread_ready.wait(0.5)
        if not self.events.main_thread_ready.is_set():
            self.stop()
            raise RuntimeError("Failed to start the Transport Layer")

        self.events.relay_thread_ready.wait(0.5)
        if not self.events.relay_thread_ready.is_set():
            self.stop()
            raise RuntimeError("Failed to start the Transport Layer")

        self.started = True

    def stop(self) -> None:
        """Stops the internal thread that handles the IsoTP layer."""
        self.logger.debug(f"Stopping {self.__class__.__name__}")
        self.events.stop_requested.set()
        self.rx_relay_queue.put(None)

        if self.main_thread is not None:
            if self.main_thread.is_alive():
                self.main_thread.join()
            self.main_thread = None

        if self.relay_thread is not None:
            if self.relay_thread.is_alive():
                self.relay_thread.join()
            self.relay_thread = None

        self.events.main_thread_ready.clear()
        self.events.relay_thread_ready.clear()
        self.events.stop_requested.clear()
        self.events.reset_tx.clear()
        self.events.reset_rx.clear()

        self.reset()
        self.set_rxfn(self.user_rxfn)
        self.started = False
        self.logger.debug(f"{self.__class__.__name__} Stopped")

    def _relay_thread_fn(self) -> None:
        """Internal function executed by the relay thread. Reads the user rxfn and put any results in a queue."""
        self.logger.debug("Relay thread has started")
        assert self.user_rxfn is not None
        self.events.relay_thread_ready.set()
        while not self.events.stop_requested.is_set():
            rx_timeout = 0.0 if self.is_tx_throttled() else self.default_read_timeout
            data = self.user_rxfn(rx_timeout)
            if data is not None:
                self.rx_relay_queue.put(data)

    def _main_thread_fn(self) -> None:
        """Internal function executed by the main thread. """
        self.logger.debug("Main thread has started")
        self.events.main_thread_ready.set()
        try:
            while not self.events.stop_requested.is_set():
                rx_timeout = 0.0 if self.is_tx_throttled() else self.default_read_timeout

                if not self.is_rx_active() and self.is_tx_transmitting_cf():
                    delay = self.next_cf_delay()
                    assert delay is not None
                    if delay > 0:
                        time.sleep(delay)   # If we are transmitting CFs, no need to call rxfn, we can stream those CF with short sleep
                    if not self.events.stop_requested.is_set():
                        self.process(do_rx=False, do_tx=True)
                else:
                    t1 = time.monotonic()
                    count_stats = self.process(rx_timeout=rx_timeout)
                    diff = time.monotonic() - t1
                    if not self.events.stop_requested.is_set():
                        if not self.blocking_rxfn or (count_stats.received == 0 and diff < rx_timeout * 0.5):
                            time.sleep(max(0, min(self.sleep_time(), rx_timeout - diff)))

                if self.events.reset_tx.is_set():
                    self._stop_sending(success=False)
                    self.events.reset_tx.clear()

                if self.events.reset_rx.is_set():
                    self._stop_receiving()
                    self.events.reset_rx.clear()

        finally:
            self.reset()
            self.logger.debug("Thread is exiting")

    @is_documented_by(TransportLayerLogic.stop_sending)
    def stop_sending(self):
        if self.started:
            if not self.events.stop_requested.is_set():
                if self.main_thread is not None and self.main_thread.is_alive():
                    self.events.reset_tx.set()
                    while self.events.reset_tx.is_set():
                        time.sleep(0.05)
        else:
            self._stop_sending()

    @is_documented_by(TransportLayerLogic.stop_receiving)
    def stop_receiving(self):
        if self.started:
            if not self.events.stop_requested.is_set():
                if self.main_thread is not None and self.main_thread.is_alive():
                    self.events.reset_rx.set()
                    while self.events.reset_rx.is_set():
                        time.sleep(0.05)
        else:
            self._stop_receiving()


class BusOwner:
    bus: "can.BusABC"


def python_can_tx_canbus_3plus(owner: BusOwner, msg: CanMessage) -> None:
    owner.bus.send(can.Message(arbitration_id=msg.arbitration_id, data=msg.data,
                               is_extended_id=msg.is_extended_id, is_fd=msg.is_fd, bitrate_switch=msg.bitrate_switch))  # type:ignore


def python_can_tx_canbus_3minus(owner: BusOwner, msg: CanMessage) -> None:
    owner.bus.send(can.Message(arbitration_id=msg.arbitration_id, data=msg.data,
                               extended_id=msg.is_extended_id, is_fd=msg.is_fd, bitrate_switch=msg.bitrate_switch))  # type:ignore


def make_python_can_tx_func(owner: BusOwner) -> Callable[[CanMessage], None]:
    message_input_args = inspect.signature(can.Message.__init__).parameters
    if 'is_extended_id' in message_input_args:
        return functools.partial(python_can_tx_canbus_3plus, owner)
    else:
        return functools.partial(python_can_tx_canbus_3minus, owner)


class CanStack(TransportLayer, BusOwner):
    """
    The IsoTP transport layer preconfigured to use `python-can <https://python-can.readthedocs.io>`__ as CAN layer. python-can must be installed in order to use this class.
    All parameters except the ``bus`` parameter will be given to the :class:`TransportLayer<isotp.TransportLayer>` constructor

    :param bus: A python-can bus object implementing ``recv`` and ``send``
    :type bus: BusABC

    :param bus: A python-can bus object implementing ``recv`` and ``send``
    :type bus: BusABC

    :param address: The address information of CAN messages. Includes the addressing mode, txid/rxid, source/target address and address extension. See :class:`isotp.Address<isotp.Address>` for more details.
    :type address: isotp.Address

    :param error_handler: A function to be called when an error has been detected. An :class:`isotp.protocol.IsoTpError<isotp.protocol.IsoTpError>` (inheriting Exception class) will be given as sole parameter
    :type error_handler: Callable

    :param params: List of parameters for the transport layer
    :type params: dict

    """
    default_read_timeout: float

    def rx_canbus(self, timeout: Optional[float] = None) -> Optional[CanMessage]:
        if timeout is None:
            timeout = self.default_read_timeout
        msg = self.bus.recv(timeout)
        if msg is not None:
            return CanMessage(arbitration_id=msg.arbitration_id, data=msg.data, extended_id=msg.is_extended_id, is_fd=msg.is_fd, bitrate_switch=msg.bitrate_switch)
        return None

    def __init__(self, bus: "can.BusABC", read_timeout: float = 0.0, *args, **kwargs):
        if not _can_available:
            raise RuntimeError(f"python-can is not installed in this environment and is required for the {self.__class__.__name__} object.")

        self.set_bus(bus)
        self.default_read_timeout = read_timeout
        kwargs.update(dict(
            rxfn=self.rx_canbus,
            txfn=make_python_can_tx_func(self),
        ))
        super().__init__(*args, **kwargs)

    def set_bus(self, bus: "can.BusABC") -> None:
        if not isinstance(bus, can.BusABC):
            raise ValueError('bus must be a python-can BusABC object')
        self.bus = bus
