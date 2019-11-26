import queue
import logging
from copy import copy
import binascii
import time
import functools
import isotp.address
import isotp.errors

class CanMessage:
    """
    Represent a CAN message (ISO-11898)

    :param arbitration_id: The CAN arbitration ID. Must be a 11 bits value or a 29 bits value if ``extended_id`` is True
    :type arbitration_id: int

    :param dlc: The Data Length Code representing the number of bytes in the data field
    :type dlc: int

    :param data: The 8 bytes payload of the message
    :type data: bytearray

    :param extended_id: When True, the arbitration ID stands on 29 bits. 11 bits when False
    :type extended_id: bool

    :param is_fd: When True, message has to be transmitted or has been received in a CAN FD frame. CAN frame when set to False
    :type extended_id: bool
    """
    __slots__ = 'arbitration_id', 'dlc', 'data', 'is_extended_id', 'is_fd'

    def __init__(self, arbitration_id=None, dlc=None, data=None, extended_id=False, is_fd=False):
        self.arbitration_id = arbitration_id
        self.dlc = dlc
        self.data = data
        self.is_extended_id = extended_id
        self.is_fd = is_fd

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

    def __init__(self, msg = None, start_of_data=0):

        self.type = None
        self.length = None
        self.data = None
        self.blocksize = None
        self.stmin = None
        self.stmin_sec = None
        self.seqnum = None
        self.flow_status = None
        self.rx_dl = None
        self.escape_sequence = False
        self.can_dl = None

        if msg is None:
            return

        if len(msg.data) < start_of_data:
            raise ValueError("Received message is missing data according to prefix size") 

        self.can_dl = len( msg.data)
        self.rx_dl = max(8, self.can_dl)
        msg_data = msg.data[start_of_data:]
        datalen = len(msg_data)
        # Guarantee at least presence of byte #1
        if datalen > 0:
            hnb =  (msg_data[0] >> 4) & 0xF
            if hnb > 3:
                raise ValueError('Received message with unknown frame type %d' % hnb)
            self.type = int(hnb)
        else:
            raise ValueError('Empty CAN frame')

        if self.type == self.Type.SINGLE_FRAME:
            length_placeholder = int(msg_data[0]) & 0xF
            if length_placeholder != 0:
                self.length = length_placeholder
                if self.length > datalen-1:
                    raise ValueError("Received Single Frame with length of %d while there is room for %d bytes of data with this configuration" % (self.length, datalen-1))
                self.data = msg_data[1:][:self.length]

            else:	# Escape seuqence
                if datalen < 2:
                    raise ValueError('Single frame with escape sequence must be at least %d bytes long with this configuration' % (2+start_of_data))

                self.escape_sequence = True
                self.length = int(msg_data[1])
                if self.length == 0:
                    raise ValueError("Received Single Frame with length of 0 bytes")
                if self.length > datalen-2:
                    raise ValueError("Received Single Frame with length of %d while there is room for %d bytes of data with this configuration" % (self.length, datalen-2))
                self.data = msg_data[2:][:self.length]

        elif self.type == self.Type.FIRST_FRAME:
            if datalen < 2:
                raise ValueError('First frame without escape sequence must be at least %d bytes long with this configuration' % (2+start_of_data))

            length_placeholder = ((int(msg_data[0]) & 0xF) << 8) | int(msg_data[1])
            if length_placeholder != 0:	# Frame is maximum 4095 bytes
                self.length = length_placeholder
                self.data = msg_data[2:][:min(self.length, datalen-2)]

            else:	# Frame is larger than 4095 bytes
                if datalen < 6:
                    raise ValueError('First frame with escape sequence must be at least %d bytes long with this configuration' % (6+start_of_data))
                self.escape_sequence = True
                self.length = (msg_data[2] << 24) | (msg_data[3] << 16) | (msg_data[4] << 8) | (msg_data[5] << 0)
                self.data = msg_data[6:][:min(self.length, datalen-6)]

        elif self.type == self.Type.CONSECUTIVE_FRAME:
            self.seqnum = int(msg_data[0]) & 0xF
            self.data = msg_data[1:]	# No need to check size as this will return empty data if overflow.

        elif self.type == self.Type.FLOW_CONTROL:
            if datalen < 3:
                raise ValueError('Flow Control frame must be at least %d bytes with the actual configuration' % (3+start_of_data))

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

    @classmethod
    def craft_flow_control_data(cls, flow_status, blocksize, stmin):
        return bytearray([ (0x30 | (flow_status) & 0xF), blocksize&0xFF, stmin & 0xFF])

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

class TransportLayer:
    """
    The IsoTP transport layer implementation

    :param rxfn: Function to be called by the transport layer to read the CAN layer. Must return a :class:`isotp.CanMessage<isotp.CanMessage>` or None if no message has been received.
    :type rxfn: Callable

    :param txfn: Function to be called by the transport layer to send a message on the CAN layer. This function should receive a :class:`isotp.CanMessage<isotp.CanMessage>`
    :type txfn: Callable

    :param address: The address information of CAN messages. Includes the addressing mode, txid/rxid, source/target address and address extension. See :class:`isotp.Address<isotp.Address>` for more details.
    :type address: isotp.Address

    :param error_handler: A function to be called when an error has been detected. An :class:`isotp.IsoTpError<isotp.IsoTpError>` (inheriting Exception class) will be given as sole parameter. See the :ref:`Error section<Errors>`
    :type error_handler: Callable

    :param params: List of parameters for the transport layer
    :type params: dict

    """

    LOGGER_NAME = 'isotp'

    class Params:
        __slots__ = 'stmin', 'blocksize', 'squash_stmin_requirement', 'rx_flowcontrol_timeout', 'rx_consecutive_frame_timeout', 'tx_padding', 'wftmax', 'tx_data_length', 'max_frame_size', 'can_fd'

        def __init__(self):
            self.stmin 							=  0
            self.blocksize 						=  8
            self.squash_stmin_requirement 		=  False
            self.rx_flowcontrol_timeout 		=  1000
            self.rx_consecutive_frame_timeout 	=  1000
            self.tx_padding 					=  None
            self.wftmax						    = 0
            self.tx_data_length					= 8
            self.max_frame_size					= 4095
            self.can_fd							= False

        def set(self, key, val, validate=True):
            param_alias = {
                    'll_data_length' : 'tx_data_length'	# For backward compatibility
            }
            if key in param_alias:
                key = param_alias[key]
            setattr(self, key, val)
            if validate:
                self.validate()


        def validate(self):
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

            if not isinstance(self.squash_stmin_requirement, bool):
                raise ValueError('squash_stmin_requirement must be a boolean value')

            if not isinstance(self.wftmax, int):
                raise ValueError('wftmax must be an integer')

            if self.wftmax < 0 :
                raise ValueError('wftmax must be and integer equal or greater than 0')

            if not isinstance(self.tx_data_length, int) :
                raise ValueError('tx_data_length must be an integer')

            if self.tx_data_length not in [8,12,16,20,24,32,48,64]:
                raise ValueError('tx_data_length must be one of these value : 8, 12, 16, 20, 24, 32, 48, 64 ')	

            if not isinstance(self.max_frame_size, int):
                raise ValueError('max_frame_size must be an integer')

            if self.max_frame_size < 0:
                raise ValueError('max_frame_size must be a positive integer')

            if not isinstance(self.can_fd, bool):
                raise ValueError('can_fd must be a boolean value')


    class Timer:
        def __init__(self, timeout):
            self.set_timeout(timeout)
            self.start_time = None

        def set_timeout(self, timeout):
            self.timeout = timeout

        def start(self, timeout=None):
            if timeout is not None:
                self.set_timeout(timeout)
            self.start_time = time.time()

        def stop(self):
            self.start_time = None

        def elapsed(self):
            if self.start_time is not None:
                return time.time() - self.start_time
            else:
                return 0

        def is_timed_out(self):
            if self.is_stopped():
                return False
            else:
                return self.elapsed() > self.timeout or self.timeout == 0

        def is_stopped(self):
            return self.start_time == None

    class RxState:
        IDLE = 0
        WAIT_CF = 1

    class TxState:
        IDLE = 0
        WAIT_FC = 1
        TRANSMIT_CF = 2

    def __init__(self, rxfn, txfn, address=None, error_handler=None, params=None):
        self.params = self.Params()
        self.logger = logging.getLogger(self.LOGGER_NAME)

        if params is not None:
            for k in params:
                self.params.set(k, params[k], validate=False)
        self.params.validate()

        self.remote_blocksize = None	# Block size received in Flow Control message

        self.rxfn = rxfn 	# Function to call to receive a CAN message
        self.txfn = txfn	# Function to call to transmit a CAN message

        self.set_address(address)

        self.tx_queue = queue.Queue()			# Layer Input queue for IsoTP frame
        self.rx_queue = queue.Queue()			# Layer Output queue for IsoTP frame

        self.rx_state = self.RxState.IDLE		# State of the reception FSM
        self.tx_state = self.TxState.IDLE		# State of the transmission FSM

        self.rx_block_counter = 0
        self.last_seqnum = None					# Consecutive frame Sequence number of previous message	
        self.rx_frame_length = 0				# Length of IsoTP frame being received at the moment
        self.tx_frame_length = 0				# Length of the data that we are sending
        self.last_flow_control_frame = None		# When a FlowControl is received. Put here
        self.tx_block_counter = 0				# Keeps track of how many block we've sent
        self.tx_seqnum = 0						# Keeps track of the actual sequence number while sending
        self.wft_counter = 0 					# Keeps track of how many wait frame we've received

        self.pending_flow_control_tx = False	# Flag indicating that we need to transmit a flow control message. Set by Rx Process, Cleared by Tx Process
        self.empty_rx_buffer()
        self.empty_tx_buffer()

        self.timer_tx_stmin = self.Timer(timeout = 0)
        self.timer_rx_fc  	= self.Timer(timeout = float(self.params.rx_flowcontrol_timeout) / 1000)
        self.timer_rx_cf 	= self.Timer(timeout = float(self.params.rx_consecutive_frame_timeout) / 1000)

        self.error_handler = error_handler
        self.actual_rxdl   = None	



    def send(self, data, target_address_type=isotp.address.TargetAddressType.Physical):
        """
        Enqueue an IsoTP frame to be sent over CAN network

        :param data: The data to be sent
        :type data: bytearray

        :param target_address_type: Optional parameter that can be Physical (0) for 1-to-1 communication or Functional (1) for 1-to-n. See :class:`isotp.TargetAddressType<isotp.TargetAddressType>`
        :type target_address_type: int

        :raises ValueError: Input parameter is not a bytearray or not convertible to bytearray
        :raises RuntimeError: Transmit queue is full
        """	
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
                raise ValueError('Cannot send multipacket frame with Functional TargetAddressType')

        self.tx_queue.put( {'data':data, 'target_address_type':target_address_type})	# frame is always an IsoTPFrame here

    # Receive an IsoTP frame. Output of the layer
    def recv(self):
        """
        Dequeue an IsoTP frame from the reception queue if available.

        :return: The next available IsoTP frame
        :rtype: bytearray or None
        """	
        if not self.rx_queue.empty():
            return self.rx_queue.get()

    def available(self):
        """
        Returns ``True`` if an IsoTP frame is awaiting in the reception ``queue``. ``False`` otherwise
        """	
        return not self.rx_queue.empty()

    def transmitting(self):
        """
        Returns ``True`` if an IsoTP frame is being transmitted. ``False`` otherwise
        """	
        return not self.tx_queue.empty() or self.tx_state != self.TxState.IDLE

    def process(self):
        """
        Function to be called periodically, as fast as possible. 
        This function is non-blocking.
        """	
        msg = True
        while msg is not None:
            msg = self.rxfn()
            if msg is not None:
                self.logger.debug("Receiving : <%03X> (%d)\t %s" % (msg.arbitration_id, len(msg.data), binascii.hexlify(msg.data)))
                self.process_rx(msg)

        msg = True
        while msg is not None:
            msg = self.process_tx()
            if msg is not None:
                self.logger.debug("Sending : <%03X> (%d)\t %s" % (msg.arbitration_id, len(msg.data), binascii.hexlify(msg.data)))
                self.txfn(msg)

    def process_rx(self, msg):

        if not self.address.is_for_me(msg):
            return 

        # Decoding of message into PDU
        try:
            pdu = PDU(msg, start_of_data=self.address.rx_prefix_size)
        except Exception as e:
            self.trigger_error(isotp.errors.InvalidCanDataError("Received invalid CAN frame. %s" % (str(e))))
            self.stop_receiving()
            return

        # Check timeout first
        if self.timer_rx_cf.is_timed_out():
            self.trigger_error(isotp.errors.ConsecutiveFrameTimeoutError("Reception of CONSECUTIVE_FRAME timed out."))
            self.stop_receiving()

        # Process Flow Control message
        if pdu.type == PDU.Type.FLOW_CONTROL:
            self.last_flow_control_frame = pdu 	 # Given to process_tx method. Queue of 1 message depth

            if self.rx_state == self.RxState.WAIT_CF:
                if pdu.flow_status == PDU.FlowStatus.Wait or pdu.flow_status == PDU.FlowStatus.ContinueToSend:
                    self.start_rx_cf_timer()
            return # Nothing else to be done with FlowControl. Return and wait for next message

        if pdu.type == PDU.Type.SINGLE_FRAME:
            if pdu.can_dl > 8 and pdu.escape_sequence == False:
                self.trigger_error(isotp.errors.MissingEscapeSequenceError('For SingleFrames conveyed on a CAN message with data length (CAN_DL) > 8, length should be encoded on byte #1 and byte #0 should be 0x00'))
                return

        # Process the state machine
        if self.rx_state == self.RxState.IDLE:
            self.rx_frame_length = 0
            self.timer_rx_cf.stop()
            if pdu.type == PDU.Type.SINGLE_FRAME:
                if pdu.data is not None:
                    self.rx_queue.put(copy(pdu.data))

            elif pdu.type == PDU.Type.FIRST_FRAME:
                self.start_reception_after_first_frame_if_valid(pdu)
            elif pdu.type == PDU.Type.CONSECUTIVE_FRAME:
                self.trigger_error(isotp.errors.UnexpectedConsecutiveFrameError('Received a ConsecutiveFrame while reception was idle. Ignoring'))


        elif self.rx_state == self.RxState.WAIT_CF:
            if pdu.type == PDU.Type.SINGLE_FRAME:
                if pdu.data is not None:
                    self.rx_queue.put(copy(pdu.data))
                    self.rx_state = self.RxState.IDLE
                    self.trigger_error(isotp.errors.ReceptionInterruptedWithSingleFrameError('Reception of IsoTP frame interrupted with a new SingleFrame'))

            elif pdu.type == PDU.Type.FIRST_FRAME:
                self.start_reception_after_first_frame_if_valid(pdu)
                self.trigger_error(isotp.errors.ReceptionInterruptedWithFirstFrameError('Reception of IsoTP frame interrupted with a new FirstFrame'))

            elif pdu.type == PDU.Type.CONSECUTIVE_FRAME:
                expected_seqnum = (self.last_seqnum +1) & 0xF
                if pdu.seqnum == expected_seqnum:
                    bytes_to_receive = (self.rx_frame_length - len(self.rx_buffer) )
                    if pdu.rx_dl != self.actual_rxdl and pdu.rx_dl < bytes_to_receive:
                        self.trigger_error(isotp.errors.ChangingInvalidRXDLError("Received a ConsecutiveFrame with RX_DL=%d while expected RX_DL=%d. Ignoring frame" % (pdu.rx_dl, self.actual_rxdl)))
                        return	

                    self.start_rx_cf_timer() 	# Received a CF message. Restart counter. Timeout handled above.
                    self.last_seqnum = pdu.seqnum
                    self.append_rx_data(pdu.data[:bytes_to_receive])	# Python handle overflow
                    if len(self.rx_buffer) >= self.rx_frame_length:
                        self.rx_queue.put(copy(self.rx_buffer))			# Data complete
                        self.stop_receiving() 							# Go back to IDLE. Reset all variables and timers.
                    else:
                        self.rx_block_counter += 1
                        if self.params.blocksize > 0 and (self.rx_block_counter % self.params.blocksize) == 0:
                            self.request_tx_flowcontrol()  	 # Sets a flag to 1. process_tx will send it for use.
                            self.timer_rx_cf.stop() 		 # Deactivate that timer while we wait for flow control
                else:
                    self.stop_receiving()
                    self.trigger_error(isotp.errors.WrongSequenceNumberError('Received a ConsecutiveFrame with wrong SequenceNumber. Expecting 0x%X, Received 0x%X' % (expected_seqnum, pdu.seqnum)))

    def process_tx(self):
        output_msg = None 	 # Value outputed.  If None, no subsequent call to process_tx will be done.

        # Sends flow control if process_rx requested it
        if self.pending_flow_control_tx:
            self.pending_flow_control_tx = False
            return self.make_flow_control(flow_status=self.pending_flowcontrol_status);	# No need to wait.

        # Handle flow control reception
        flow_control_frame = self.last_flow_control_frame	# Reads the last message received and clears it. (Dequeue message)
        self.last_flow_control_frame = None

        if flow_control_frame is not None:
            if flow_control_frame.flow_status == PDU.FlowStatus.Overflow: 	# Needs to stop sending. 
                self.stop_sending()
                self.trigger_error(isotp.errors.OverflowError('Received a FlowControl PDU indicating an Overflow. Stopping transmission.'))
                return

            if self.tx_state == self.TxState.IDLE:
                self.trigger_error(isotp.errors.UnexpectedFlowControlError('Received a FlowControl message while transmission was Idle. Ignoring'))
            else:
                if flow_control_frame.flow_status == PDU.FlowStatus.Wait:
                    if self.params.wftmax == 0:
                        self.trigger_error(isotp.errors.UnsuportedWaitFrameError('Received a FlowControl requesting to wait, but fwtmax is set to 0'))
                    elif self.wft_counter >= self.params.wftmax:
                        self.trigger_error(isotp.errors.MaximumWaitFrameReachedError('Received %d wait frame which is the maximum set in params.wftmax' % (self.wft_counter)))
                        self.stop_sending()
                    else:
                        self.wft_counter += 1
                        if self.tx_state in [self.TxState.WAIT_FC, self.TxState.TRANSMIT_CF]:
                            self.tx_state = self.TxState.WAIT_FC
                            self.start_rx_fc_timer()

                elif flow_control_frame.flow_status == PDU.FlowStatus.ContinueToSend and not self.timer_rx_fc.is_timed_out():
                    self.wft_counter = 0
                    self.timer_rx_fc.stop()
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
            self.trigger_error(isotp.errors.FlowControlTimeoutError('Reception of FlowControl timed out. Stopping transmission'))
            self.stop_sending()


        # ======= FSM ======

        # Check this first as we may have another isotp frame to send and we need to handle it right away without waiting for next "process()" call
        if self.tx_state != self.TxState.IDLE and len(self.tx_buffer) == 0:
            self.stop_sending()	


        if self.tx_state == self.TxState.IDLE:
            read_tx_queue = True	# Read until we get non-empty frame to send
            while read_tx_queue:
                read_tx_queue = False
                if not self.tx_queue.empty():
                    popped_object = self.tx_queue.get()
                    if len(popped_object['data']) == 0:
                        read_tx_queue = True	# Read another frame from tx_queue
                    else:
                        self.tx_buffer = bytearray(popped_object['data'])
                        size_on_first_byte = True if len(self.tx_buffer) <= 7 else False
                        size_offset = 1 if size_on_first_byte else 2

                        # Single frame
                        if len(self.tx_buffer) <= self.params.tx_data_length-size_offset-len(self.address.tx_payload_prefix):	
                            if size_on_first_byte:
                                msg_data 	= self.address.tx_payload_prefix + bytearray([0x0 | len(self.tx_buffer)]) + self.tx_buffer
                            else:
                                msg_data 	= self.address.tx_payload_prefix + bytearray([0x0, len(self.tx_buffer)]) + self.tx_buffer
                            arbitration_id 	= self.address.get_tx_arbitraton_id(popped_object['target_address_type'])
                            output_msg		= self.make_tx_msg(arbitration_id, msg_data)

                        # Multi frame - First Frame
                        else:							
                            self.tx_frame_length = len(self.tx_buffer)
                            encode_length_on_2_first_bytes = True if self.tx_frame_length <= 0xFFF else False
                            if encode_length_on_2_first_bytes:
                                data_length = self.params.tx_data_length-2-len(self.address.tx_payload_prefix)
                                msg_data 	= self.address.tx_payload_prefix + bytearray([0x10|((self.tx_frame_length >> 8) & 0xF), self.tx_frame_length&0xFF]) + self.tx_buffer[:data_length]
                            else:
                                data_length = self.params.tx_data_length-6-len(self.address.tx_payload_prefix)
                                msg_data 	= self.address.tx_payload_prefix + bytearray([0x10, 0x00, (self.tx_frame_length>>24) & 0xFF, (self.tx_frame_length>>16) & 0xFF, (self.tx_frame_length>>8) & 0xFF, (self.tx_frame_length>>0) & 0xFF]) + self.tx_buffer[:data_length]

                            arbitration_id 	= self.address.get_tx_arbitraton_id()
                            output_msg 		= self.make_tx_msg(arbitration_id, msg_data)
                            self.tx_buffer 	= self.tx_buffer[data_length:]
                            self.tx_state 	= self.TxState.WAIT_FC
                            self.tx_seqnum 	= 1
                            self.start_rx_fc_timer()


        elif self.tx_state == self.TxState.WAIT_FC:
            pass # Nothing to do. Flow control will make the FSM switch state by calling init_tx_consecutive_frame

        elif self.tx_state == self.TxState.TRANSMIT_CF:
            if self.timer_tx_stmin.is_timed_out() or self.params.squash_stmin_requirement:
                data_length = self.params.tx_data_length-1-len(self.address.tx_payload_prefix)
                msg_data = self.address.tx_payload_prefix + bytearray([0x20 | self.tx_seqnum]) + self.tx_buffer[:data_length]
                arbitration_id 	= self.address.get_tx_arbitraton_id()
                output_msg = self.make_tx_msg(arbitration_id, msg_data)
                self.tx_buffer = self.tx_buffer[data_length:]
                self.tx_seqnum = (self.tx_seqnum + 1 ) & 0xF
                self.timer_tx_stmin.start()
                self.tx_block_counter+=1
            if (len(self.tx_buffer) == 0):
                self.stop_sending()

            elif self.remote_blocksize != 0 and self.tx_block_counter >= self.remote_blocksize:
                self.tx_state = self.TxState.WAIT_FC
                self.start_rx_fc_timer()

        return output_msg

    def set_address(self, address):
        """
        Sets the layer :class:`Address<isotp.Address>`. Can be set after initialization if needed.
        """

        if not isinstance(address, isotp.address.Address):
            raise ValueError('address must be a valid Address instance')

        self.address = address

        if self.address.txid is not None and (self.address.txid > 0x7F4 and self.address.txid < 0x7F6 or self.address.txid > 0x7FA and self.address.txid < 0x7FB) :
            self.logger.warning('Used txid overlaps the range of ID reserved by ISO-15765 (0x7F4-0x7F6 and 0x7FA-0x7FB)')

        if self.address.rxid is not None and (self.address.rxid > 0x7F4 and self.address.rxid < 0x7F6 or self.address.rxid > 0x7FA and self.address.rxid < 0x7FB) :
            self.logger.warning('Used rxid overlaps the range of ID reserved by ISO-15765 (0x7F4-0x7F6 and 0x7FA-0x7FB)')

    def pad_message_data(self, msg_data):
        must_pad = False
        target_length = self.params.tx_data_length
        if self.params.tx_padding is not None:
            must_pad = True

        elif self.params.tx_data_length > 8 and len(msg_data) > 8:
            must_pad = True
            target_length = self.get_nearest_can_fd_size(len(msg_data))

        padding_byte = 0xCC if self.params.tx_padding is None else self.params.tx_padding

        if must_pad and len(msg_data) < target_length:
            msg_data.extend(bytearray([padding_byte & 0xFF] * (target_length-len(msg_data))))

    def empty_rx_buffer(self):
        self.rx_buffer = bytearray()

    def empty_tx_buffer(self):
        self.tx_buffer = bytearray()

    def start_rx_fc_timer(self):
        self.timer_rx_fc  	= self.Timer(timeout = float(self.params.rx_flowcontrol_timeout) / 1000)
        self.timer_rx_fc.start()

    def start_rx_cf_timer(self):
        self.timer_rx_cf 	= self.Timer(timeout = float(self.params.rx_consecutive_frame_timeout) / 1000)
        self.timer_rx_cf.start()

    def append_rx_data(self, data):
        self.rx_buffer.extend(data)

    def request_tx_flowcontrol(self, status=PDU.FlowStatus.ContinueToSend):
        self.pending_flow_control_tx = True
        self.pending_flowcontrol_status = status

    def stop_sending_flow_control(self):
        self.pending_flow_control_tx = False
        self.last_flow_control_frame = None

    def make_tx_msg(self, arbitration_id, data):
        self.pad_message_data(data)
        return CanMessage(arbitration_id = arbitration_id, dlc=self.get_dlc(data, validate_tx=True), data=data, extended_id=self.address.is_29bits, is_fd=self.params.can_fd)

    def get_dlc(self, data, validate_tx=False):
        fdlen = self.get_nearest_can_fd_size(len(data))
        if validate_tx:
            if self.params.tx_data_length == 8:
                if fdlen < 2 or fdlen > 8:
                    raise ValueError("Impossible DLC size for payload of %d bytes with tx_data_length of %d" % (len(data), self.params.tx_data_length ))

        if fdlen >= 2 and fdlen <= 8: return fdlen
        elif fdlen == 12: return 9
        elif fdlen == 16: return 10
        elif fdlen == 20: return 11
        elif fdlen == 24: return 12
        elif fdlen == 32: return 13
        elif fdlen == 48: return 14
        elif fdlen == 64: return 15
        raise ValueError("Impossible DLC size for payload of %d bytes with tx_data_length of %d" % (len(data)))



    def get_nearest_can_fd_size(self, size):
        if size <= 8:
            return size
        if size<=12: return 12
        if size<=16: return 16
        if size<=20: return 20
        if size<=24: return 24
        if size<=32: return 32
        if size<=48: return 48
        if size<=64: return 64
        raise ValueError("Impossible data size for CAN FD : %d " % (size))

    def make_flow_control(self, flow_status=PDU.FlowStatus.ContinueToSend, blocksize=None, stmin=None):
        if blocksize is None:
            blocksize = self.params.blocksize

        if stmin is None:
            stmin = self.params.stmin
        data = PDU.craft_flow_control_data(flow_status, blocksize, stmin)

        return self.make_tx_msg(self.address.get_tx_arbitraton_id(), self.address.tx_payload_prefix + data)

    def request_wait_flow_control(self):
        self.must_wait_for_flow_control = True

    def stop_sending(self):
        self.empty_tx_buffer()
        self.tx_state = self.TxState.IDLE
        self.tx_frame_length = 0
        self.timer_rx_fc.stop()
        self.timer_tx_stmin.stop()
        self.remote_blocksize = None
        self.tx_block_counter = 0
        self.tx_seqnum = 0
        self.wft_counter = 0

    def stop_receiving(self):
        self.actual_rxdl = None
        self.rx_state = self.RxState.IDLE
        self.empty_rx_buffer()
        self.stop_sending_flow_control()
        self.timer_rx_cf.stop()

    # Init the reception of a multi-pdu frame. 
    def start_reception_after_first_frame_if_valid(self, pdu):
        self.empty_rx_buffer()
        if pdu.rx_dl not in [8,12,16,20,24,32,48,64]:
            self.trigger_error(isotp.errors.InvalidCanFdFirstFrameRXDL("Received a FirstFrame with a RX_DL value of %d which is invalid according to ISO-15765-2" % (pdu.rx_dl)))
            self.stop_receiving()
            return

        self.actual_rxdl = pdu.rx_dl

        if pdu.length > self.params.max_frame_size:
            self.trigger_error(isotp.errors.FrameTooLongError("Received a Frist Frame with a length of %d bytes, but params.max_frame_size is set to %d bytes. Ignoring" % (pdu.length, self.params.max_frame_size)))
            self.request_tx_flowcontrol(PDU.FlowStatus.Overflow)
            self.rx_state = self.RxState.IDLE	
        else:
            self.rx_state = self.RxState.WAIT_CF
            self.rx_frame_length = pdu.length
            self.append_rx_data(pdu.data)
            self.request_tx_flowcontrol(PDU.FlowStatus.ContinueToSend)

        self.start_rx_cf_timer()
        self.last_seqnum = 0
        self.rx_block_counter = 0


    def trigger_error(self, error):
        if self.error_handler is not None:
            if hasattr(self.error_handler, '__call__') and isinstance(error, isotp.errors.IsoTpError):
                self.error_handler(error)
            else:
                self.logger.warning('Given error handler is not a callable object.')

        self.logger.warning(str(error))

    # Clears everything within the layer.
    def reset(self):
        """
        Reset the layer: Empty all buffers, set the internal state machines to Idle
        """
        while not self.tx_queue.empty():
            self.tx_queue.get()

        while not self.rx_queue.empty():
            self.rx_queue.get()

        self.stop_sending()
        self.stop_receiving()

    # Gives a time to pass to time.sleep() based on the state of the FSM. Avoid using too much CPU
    def sleep_time(self):
        """
        Returns a value in seconds that can be passed to ``time.sleep()`` when the stack is processed in a different thread.

        The value will change according to the internal state machine state, sleeping longer while idle and shorter when active.
        """
        timings = {
                (self.RxState.IDLE, self.TxState.IDLE) 		: 0.05,
                (self.RxState.IDLE, self.TxState.WAIT_FC) 	: 0.01,
        }

        key = (self.rx_state, self.tx_state)
        if key in timings:
            return timings[key]
        else:
            return 0.001

class CanStack(TransportLayer):
    """
    The IsoTP transport using `python-can <https://python-can.readthedocs.io>`_ as CAN layer. python-can must be installed in order to use this class.
    All parameters except the ``bus`` parameter will be given to the :class:`TransportLayer<isotp.TransportLayer>` constructor

    :param bus: A python-can bus object implementing ``recv`` and ``send``
    :type bus: BusABC

    :param address: The address information of CAN messages. Includes the addressing mode, txid/rxid, source/target address and address extension. See :class:`isotp.Address<isotp.Address>` for more details.
    :type address: isotp.Address

    :param error_handler: A function to be called when an error has been detected. An :class:`isotp.protocol.IsoTpError<isotp.protocol.IsoTpError>` (inheriting Exception class) will be given as sole parameter
    :type error_handler: Callable

    :param params: List of parameters for the transport layer
    :type params: dict

    """

    def tx_canbus(self, msg):
        self.bus.send(can.Message(arbitration_id=msg.arbitration_id, data = msg.data, extended_id=msg.is_extended_id, is_fd=msg.is_fd))

    def rx_canbus(self):
        msg = self.bus.recv(0)
        if msg is not None:
            return CanMessage(arbitration_id=msg.arbitration_id, data=msg.data, extended_id=msg.is_extended_id, is_fd=msg.is_fd)

    def __init__(self, bus, *args, **kwargs):
        global can
        import can
        self.set_bus(bus)
        TransportLayer.__init__(self, rxfn=self.rx_canbus, txfn=self.tx_canbus, *args, **kwargs)

    def set_bus(self, bus):
        if not isinstance(bus, can.BusABC):
            raise ValueError('bus must be a python-can BusABC object')
        self.bus=bus
