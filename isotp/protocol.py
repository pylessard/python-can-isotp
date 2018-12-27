import queue
import logging
from copy import copy
import binascii
import time
import functools


class CanMessage:
	__slots__ = 'arbitration_id', 'dlc', 'data','is_extended_id'

	def __init__(self, arbitration_id=None, dlc=None, data=None, extended_id=False):
		self.arbitration_id = arbitration_id
		self.dlc = dlc
		self.data = data
		self.is_extended_id = extended_id

class PDU:
	__slots__ = 'type', 'length', 'data', 'blocksize', 'stmin', 'stmin_sec', 'seqnum', 'flow_status'

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
		"""
		Converts a CAN Message into a meaningful PDU such as SingleFrame, FirstFrame, ConsecutiveFrame, FlowControl

		:param msg: The CAN message
		:type msg: `isotp.protocol.CanMessage`
		"""
		self.type = None
		self.length = None
		self.data = None
		self.blocksize = None
		self.stmin = None
		self.stmin_sec = None
		self.seqnum = None
		self.flow_status = None

		if msg is None:
			return

		if len(msg.data)>start_of_data:
			hnb =  (msg.data[start_of_data] >> 4) & 0xF
			if hnb > 3:
				raise ValueError('Received message with unknown frame type %d' % hnb)
			self.type = int(hnb)
		else:
			raise ValueError('Empty CAN frame')

		if self.type == self.Type.SINGLE_FRAME:
			self.length = int(msg.data[start_of_data]) & 0xF
			if len(msg.data) < self.length + 1:
				raise ValueError('Single Frame length is bigger than CAN frame length')

			if self.length == 0 or self.length > 7-start_of_data:
				raise ValueError("Received Single Frame with invalid length of %d" % self.length)
			self.data = msg.data[1+start_of_data:][:self.length]

		elif self.type == self.Type.FIRST_FRAME:
			if len(msg.data) < 2+start_of_data:
				raise ValueError('First frame must be at least %d bytes long' % (2+start_of_data))

			self.length = ((int(msg.data[start_of_data]) & 0xF) << 8) | int(msg.data[start_of_data+1])
			if len(msg.data) < 8:
				if len(msg.data) < self.length + 2 + start_of_data:
					raise ValueError('First frame specifies a length that is inconsistent with underlying CAN message DLC')

			self.data = msg.data[2+start_of_data:][:min(self.length, 6-start_of_data)]
				
		elif self.type == self.Type.CONSECUTIVE_FRAME:
			self.seqnum = int(msg.data[start_of_data]) & 0xF
			self.data = msg.data[start_of_data+1:]

		elif self.type == self.Type.FLOW_CONTROL:
			if len(msg.data) < 3+start_of_data:
				raise ValueError('Flow Control frame must be at least 3 bytes')

			self.flow_status = int(msg.data[start_of_data]) & 0xF
			if self.flow_status >= 3:
				raise ValueError('Unknown flow status')

			self.blocksize = int(msg.data[1+start_of_data])
			stmin_temp = int(msg.data[2+start_of_data])

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

class IsoTpError(Exception):
	def __init__(self, *args, **kwargs):
		Exception.__init__(self, *args, **kwargs)

class FlowControlTimeoutError(IsoTpError):
	pass
class ConsecutiveFrameTimeoutError(IsoTpError):
	pass
class InvalidCanDataError(IsoTpError):
	pass
class UnexpectedFlowControlError(IsoTpError):
	pass
class UnexpectedConsecutiveFrameError(IsoTpError):
	pass
class ReceptionInterruptedWithSingleFrameError(IsoTpError):
	pass
class ReceptionInterruptedWithFirstFrameError(IsoTpError):
	pass
class WrongSequenceNumberError(IsoTpError):
	pass
class UnsuportedWaitFrameError(IsoTpError):
	pass
class MaximumWaitFrameReachedError(IsoTpError):
	pass

class AddressingMode:
	Normal_11bits = 0
	Normal_29bits = 1
	NormalFixed_29bits = 2
	Extended_11bits = 3
	Extended_29bits = 4
	Mixed_11bits = 5
	Mixed_29bits = 6

class TargetAddressType:
	Physical = 0		# 1 to 1 communication
	Functional = 1		# 1 to n communication

class Address:
	def __init__(self, addressing_mode = None, txid=None, rxid=None, target_address=None, source_address=None, address_extension=None):
		self.addressing_mode	= addressing_mode
		self.target_address		= target_address
		self.source_address		= source_address
		self.address_extension	= address_extension
		self.txid				= txid
		self.rxid				= rxid

		self.validate()

		# From here, input is good. Do some precomputing for speed optimization withou bothering about types or values
		self.is_29bits 						= True if self.addressing_mode in [ AddressingMode.Normal_29bits, AddressingMode.NormalFixed_29bits, AddressingMode.Extended_29bits, AddressingMode.Mixed_29bits] else False
		self.tx_arbitration_id_physical  	= self._get_tx_arbitraton_id(TargetAddressType.Physical)
		self.tx_arbitration_id_functional  	= self._get_tx_arbitraton_id(TargetAddressType.Functional)

		self.tx_payload_prefix = bytearray()
		self.rx_prefix_size = 0

		if self.addressing_mode in [AddressingMode.Extended_11bits, AddressingMode.Extended_29bits]:
			self.tx_payload_prefix.extend(bytearray([self.target_address]))
			self.rx_prefix_size = 1
		elif self.addressing_mode in [AddressingMode.Mixed_11bits, AddressingMode.Mixed_29bits]:
			self.tx_payload_prefix.extend(bytearray([self.address_extension]))
			self.rx_prefix_size = 1

		self.rxmask = None
		if self.addressing_mode == AddressingMode.NormalFixed_29bits:
			self.rxmask = 0x18DA0000	# This should ignore variant between Physical and Functional addressing
		elif self.addressing_mode == AddressingMode.Mixed_29bits:
			self.rxmask = 0x18CD0000	# This should ignore variant between Physical and Functional addressing

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
		if self.addressing_mode not in [AddressingMode.Normal_11bits,AddressingMode.Normal_29bits,AddressingMode.NormalFixed_29bits,AddressingMode.Extended_11bits,AddressingMode.Extended_29bits,AddressingMode.Mixed_11bits,AddressingMode.Mixed_29bits]:
			raise ValueError('Addressing mode is not valid')

		if self.addressing_mode in [AddressingMode.Normal_11bits, AddressingMode.Normal_29bits]:
			if self.rxid is None or self.txid is None:
				raise ValueError('txid and rxid must be specified for Normal addressing mode (11 bits ID)')
			if self.rxid == self.txid:
				raise ValueError('txid and rxid must be different for Normal addressing mode')
		
		elif self.addressing_mode == AddressingMode.NormalFixed_29bits:
			if self.target_address is None or self.source_address is None:
				raise ValueError('target_address and source_address must be specified for Normal Fixed addressing (29 bits ID)')
		
		elif self.addressing_mode in [AddressingMode.Extended_11bits, AddressingMode.Extended_29bits]:
			if self.target_address is None or self.rxid is None or self.txid is None:
				raise ValueError('target_address, rxid and txid must be specified for Extended addressing mode ')
			if self.rxid == self.txid:
				raise ValueError('txid and rxid must be different')

		elif self.addressing_mode == AddressingMode.Mixed_11bits:
			if self.rxid is None or self.txid is None or self.address_extension is None:
				raise ValueError('rxid, txid and address_extension must be specified for Mixed addressing mode')

		elif self.addressing_mode == AddressingMode.Mixed_29bits:
			if self.target_address is None or self.source_address is None or self.address_extension is None:
				raise ValueError('target_address, source_address and address_extension must be specified for Mixed addressing mode')

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

	def get_tx_arbitraton_id(self, pdu_type, address_type=TargetAddressType.Physical):
		if address_type == TargetAddressType.Functional:
			if pdu_type == PDU.Type.SINGLE_FRAME:
				return self.tx_arbitration_id_functional
			else:
				raise RuntimeError('Only SingleFrame are allowed when TaType is Functional. This error should never happen.')
		else:
			return self.tx_arbitration_id_physical

	def _get_tx_arbitraton_id(self, address_type):
		if self.addressing_mode == AddressingMode.Normal_11bits:
			return self.txid
		elif self.addressing_mode == AddressingMode.Normal_29bits:
			return self.txid
		elif self.addressing_mode == AddressingMode.NormalFixed_29bits:
			bits23_16 = 0xDA0000 if address_type==TargetAddressType.Physical else 0xDB0000
			return 0x18000000 | bits23_16 | (self.target_address << 8) | self.source_address
		elif self.addressing_mode == AddressingMode.Extended_11bits:
			return self.txid
		elif self.addressing_mode == AddressingMode.Extended_29bits:
			return self.txid
		elif self.addressing_mode == AddressingMode.Mixed_11bits:
			return self.txid
		elif self.addressing_mode == AddressingMode.Mixed_29bits:
			bits23_16 = 0xCE0000 if address_type==TargetAddressType.Physical else 0xCD0000
			return 0x18000000 | bits23_16 | (self.target_address << 8) | self.source_address

	def _is_for_me_normal(self, msg):
		if self.is_29bits == msg.is_extended_id:
			return msg.arbitration_id == self.rxid
		return False

	def _is_for_me_extended(self, msg):
		if self.is_29bits == msg.is_extended_id:
			if msg.data is not None and len(msg.data) > 0:
				return msg.arbitration_id == self.rxid and int(msg.data[0]) == self.source_address 
		return False

	def _is_for_me_normalfixed(self, msg):
		if self.is_29bits == msg.is_extended_id:
			return ((msg.arbitration_id >> 16) & 0xFF) in [218,219] and (msg.arbitration_id & 0xFF00) >> 8 == self.source_address and msg.arbitration_id & 0xFF == self.target_address
		return False

	def _is_for_me_mixed_11bits(self, msg):
		if self.is_29bits == msg.is_extended_id:
			if msg.data is not None and len(msg.data) > 0:
				return msg.arbitration_id == self.rxid and int(msg.data[0]) == self.address_extension
		return False

	def _is_for_me_mixed_29bits(self, msg):
		if self.is_29bits == msg.is_extended_id:
			if msg.data is not None and len(msg.data) > 0:
				return ((msg.arbitration_id >> 16) & 0xFF) in [205,206] and (msg.arbitration_id & 0xFF00) >> 8 == self.source_address and msg.arbitration_id & 0xFF == self.target_address and int(msg.data[0]) == self.address_extension
		return False


class TransportLayer:

	class Params:
		__slots__ = 'stmin', 'blocksize', 'squash_stmin_requirement', 'rx_flowcontrol_timeout', 'rx_consecutive_frame_timeout', 'tx_padding', 'wftmax'

		def __init__(self):
			self.stmin 							=  0
			self.blocksize 						=  8
			self.squash_stmin_requirement 		=  False
			self.rx_flowcontrol_timeout 		=  1000
			self.rx_consecutive_frame_timeout 	=  1000
			self.tx_padding 					=  None
			self.wftmax						    = 0

		def set(self, key, val):
			setattr(self, key, val)
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
				raise ValueError('wftmax must be and integerequal or greater than 0')

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
		"""
		The IsoTP transport layer implementation

		:param rxfn: Function to be called by the transport layer to read the CAN layer. Must return a ``isotp.protocol.CanMessage`` or None if no message has been received.
		:type rxfn: Callable

		:param txfn: Function to be called by the transport layer to send a message on the CAN layer. This function should receive a ``isotp.protocol.CanMessage``
		:type txfn: Callable

		:param txid: The CAN ID to use for transmission. Applies to normal addressing mode
		:type txid: int

		:param rxid: The CAN ID to use for reception. Applies to normal addressing mode
		:type rxid: int

		:param extended_id: Specifies if the given rxid/txid are extended CAN ID
		:type extended_id: bool

		:param error_handler: A function to be called when an error has been detected. An ``isotp.protocol.IsoTpError`` (inheriting Exception class) will be given as sole parameter
		:type error_handler: Callable

		:param params: List of parameters for the transport layer
		:type params: dict

		"""
		self.params = self.Params()

		if params is not None:
			for k in params:
				self.params.set(k, params[k])

		self.remote_blocksize = None	# Block size received in Flow Control message

		self.rxfn = rxfn 	# Function to call to receive a CAN message
		self.txfn = txfn	# Function to call to transmimt a CAN message

		if not isinstance(address, Address):
			raise ValueError('address must be a valid Address instance')

		self.address = address

		if self.address.txid is not None and (self.address.txid > 0x7F4 and self.address.txid < 0x7F6 or self.address.txid > 0x7FA and self.address.txid < 0x7FB) :
			self.logger.warning('Used txid overlaps the range of ID reserved by ISO-15765 (0x7F4-0x7F6 and 0x7FA-0x7FB)')

		if self.address.rxid is not None and (self.address.rxid > 0x7F4 and self.address.rxid < 0x7F6 or self.address.rxid > 0x7FA and self.address.rxid < 0x7FB) :
			self.logger.warning('Used rxid overlaps the range of ID reserved by ISO-15765 (0x7F4-0x7F6 and 0x7FA-0x7FB)')

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
		self.tx_seqnum = 0						# Keeps track of the actual sequence number whil sending
		self.wft_counter = 0 					# Keeps track of how many wait frame we've received

		self.pending_flow_control_tx = False	# Flag indicating that we need to transmist a flow control message. Set by Rx Process, Cleared by Tx Process
		self.empty_rx_buffer()
		self.empty_tx_buffer()

		self.timer_tx_stmin = self.Timer(timeout = 0)
		self.timer_rx_fc  	= self.Timer(timeout = float(self.params.rx_flowcontrol_timeout) / 1000)
		self.timer_rx_cf 	= self.Timer(timeout = float(self.params.rx_consecutive_frame_timeout) / 1000)

		self.error_handler = error_handler

		self.logger = logging.getLogger(self.__class__.__name__)

	
	def send(self, data, target_address_type=TargetAddressType.Physical):
		"""
		Enqueue an IsoTP frame to be sent over CAN network

		:param data: The data to be sent
		:type data: bytearray

		:param data: Optional parameter that can be Physical (0) for 1-to-1 communication or Functional (1) for 1-to-n. See :class:`isotp.protocol.Address.TargetAddressType<isotp.protocol.Address.TargetAddressType>`
		:type data: int

		:raises ValueError: Input parameter is not a bytearray or not convertible to bytearray
		:raises RuntimeError: Transmit queue is full
		"""	
		if not isinstance(data, bytearray):
			try:
				data = bytearray(data)
			except:
				raise ValueError('data must be an IsoTpFrame or bytearray')

		if self.tx_queue.full():
			raise RuntimeError('Transmit queue is full')

		if target_address_type == TargetAddressType.Functional:
			if len(data) > 7-len(self.address.tx_payload_prefix):
				raise ValueError('Cannot send multipacket frame with Functional TargetAddressType')

		self.tx_queue.put( {'data':data, 'target_address_type':target_address_type})	# farme is always an IsoTPFrame here

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
		Return True if an IsoTP frame is awaiting in the reception queue. False otherwise
		"""	
		return not self.rx_queue.empty()

	def transmitting(self):
		"""
		Return True if an IsoTP frame is being transmitted. False otherwise
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
				self.logger.debug("Receiving : <%03X> %s" % (msg.arbitration_id, binascii.hexlify(msg.data)))
				self.process_rx(msg)

		msg = True
		while msg is not None:
			msg = self.process_tx()
			if msg is not None:
				self.logger.debug("Sending : <%03X> %s" % (msg.arbitration_id, binascii.hexlify(msg.data)))
				self.txfn(msg)

	def process_rx(self, msg):
		
		if not self.address.is_for_me(msg):
			return 

		# Decoding of message into PDU
		try:
			pdu = PDU(msg, self.address.rx_prefix_size)
		except Exception as e:
			self.trigger_error(InvalidCanDataError("Received invalid CAN frame. %s" % (str(e))))
			self.stop_receiving()
			return

		# Check timeout first
		if self.timer_rx_cf.is_timed_out():
			self.trigger_error(ConsecutiveFrameTimeoutError("Reception of CONSECUTIVE_FRAME timed out."))
			self.stop_receiving()

		# Process Flow Control message
		if pdu.type == PDU.Type.FLOW_CONTROL:
			self.last_flow_control_frame = pdu 	 # Given to process_tx method. Queue of 1 message depth

			if self.rx_state == self.RxState.WAIT_CF:
				if pdu.flow_status == PDU.FlowStatus.Wait or pdu.flow_status == PDU.FlowStatus.ContinueToSend:
					self.start_rx_cf_timer()
			return # Nothing else to be done with FlowControl. Return and wait for next message

		# Process the state machine
		if self.rx_state == self.RxState.IDLE:
			self.rx_frame_length = 0
			self.timer_rx_cf.stop()

			if pdu.type == PDU.Type.SINGLE_FRAME:
				if pdu.data is not None:
					self.rx_queue.put(copy(pdu.data))

			elif pdu.type == PDU.Type.FIRST_FRAME:
				self.start_reception_after_first_frame(pdu)
			elif pdu.type == PDU.Type.CONSECUTIVE_FRAME:
				self.trigger_error(UnexpectedConsecutiveFrameError('Received a ConsecutiveFrame while reception was idle. Ignoring'))
				

		elif self.rx_state == self.RxState.WAIT_CF:
			if pdu.type == PDU.Type.SINGLE_FRAME:
				if pdu.data is not None:
					self.rx_queue.put(copy(pdu.data))
					self.rx_state = self.RxState.IDLE
					self.trigger_error(ReceptionInterruptedWithSingleFrameError('Reception of IsoTP frame interrupted with a new SingleFrame'))

			elif pdu.type == PDU.Type.FIRST_FRAME:
				self.start_reception_after_first_frame(pdu)
				self.trigger_error(ReceptionInterruptedWithFirstFrameError('Reception of IsoTP frame interrupted with a new FirstFrame'))

			elif pdu.type == PDU.Type.CONSECUTIVE_FRAME:
				self.start_rx_cf_timer() 	# Received a CF message. Restart counter. Timeout handled above.

				expected_seqnum = (self.last_seqnum +1) & 0xF
				if pdu.seqnum == expected_seqnum:
					self.last_seqnum = pdu.seqnum
					bytes_to_receive = (self.rx_frame_length - len(self.rx_buffer) )
					self.append_rx_data(pdu.data[:bytes_to_receive])	# Python handle overflow
					if len(self.rx_buffer) >= self.rx_frame_length:
						self.rx_queue.put(copy(self.rx_buffer))			# Data complete
						self.stop_receiving() 							# Go back to IDLE. Reset all variables and timers.
					else:
						self.rx_block_counter += 1
						if self.rx_block_counter % self.params.blocksize == 0:
							self.request_tx_flowcontrol()  	 # Sets a flag to 1. process_tx will send it for use.
							self.timer_rx_cf.stop() 		 # Deactivate that timer while we wait for flow control
				else:
					self.stop_receiving()
					self.trigger_error(WrongSequenceNumberError('Received a ConsecutiveFrame with wrong SequenceNumber. Expecting 0x%X, Received 0x%X' % (expected_seqnum, pdu.seqnum)))

	def process_tx(self):
		output_msg = None 	 # Value outputed.  If None, no subsequent call to process_tx will be done.

		# Sends flow control if process_rx requested it
		if self.pending_flow_control_tx:
			self.pending_flow_control_tx = False
			return self.make_flow_control(flow_status=PDU.FlowStatus.ContinueToSend);	# Overflow is not possible. No need to wait.

		# Handle flow control reception
		flow_control_frame = self.last_flow_control_frame	# Reads the last message received and clears it. (Dequeue message)
		self.last_flow_control_frame = None

		if flow_control_frame is not None:
			if flow_control_frame.flow_status == PDU.FlowStatus.Overflow: 	# Needs to stop sending. 
				self.stop_sending()
				return

			if self.tx_state == self.TxState.IDLE:
				self.trigger_error(UnexpectedFlowControlError('Received a FlowControl message while transmission was Idle. Ignoring'))
			else:
				if flow_control_frame.flow_status == PDU.FlowStatus.Wait:
					if self.params.wftmax == 0:
						self.trigger_error(UnsuportedWaitFrameError('Received a FlowControl requesting to wait, but fwtmax is set to 0'))
					elif self.wft_counter >= self.params.wftmax:
						self.trigger_error(MaximumWaitFrameReachedError('Received %d wait frame which is the maximum set in params.wftmax' % (self.wft_counter)))
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
			self.trigger_error(FlowControlTimeoutError('Reception of FlowControl timed out. Stopping transmission'))
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


						if len(self.tx_buffer) <= 7-len(self.address.tx_payload_prefix):	# Single frame
							msg_data 		= self.address.tx_payload_prefix + bytearray([0x0 | len(self.tx_buffer)]) + self.tx_buffer
							arbitration_id 	= self.address.get_tx_arbitraton_id(PDU.Type.SINGLE_FRAME, popped_object['target_address_type'])
							output_msg		= self.make_tx_msg(arbitration_id, msg_data)
						else:							# Multi frame
							self.tx_frame_length = len(self.tx_buffer)
							msg_data 		= self.address.tx_payload_prefix + bytearray([0x10|((self.tx_frame_length >> 8) & 0xF), self.tx_frame_length&0xFF]) + self.tx_buffer[:6-len(self.address.tx_payload_prefix)]
							arbitration_id 	= self.address.get_tx_arbitraton_id(PDU.Type.FIRST_FRAME)
							output_msg 		= self.make_tx_msg(arbitration_id, msg_data)
							self.tx_buffer 	= self.tx_buffer[6-len(self.address.tx_payload_prefix):]
							self.tx_state 	= self.TxState.WAIT_FC
							self.tx_seqnum 	= 1
							self.start_rx_fc_timer()

		elif self.tx_state == self.TxState.WAIT_FC:
			pass # Nothing to do. Flow control will make the FSM switch state by calling init_tx_consecutive_frame

		elif self.tx_state == self.TxState.TRANSMIT_CF:
			if self.timer_tx_stmin.is_timed_out() or self.params.squash_stmin_requirement:
				msg_data = self.address.tx_payload_prefix + bytearray([0x20 | self.tx_seqnum]) + self.tx_buffer[:7-len(self.address.tx_payload_prefix)]
				arbitration_id 	= self.address.get_tx_arbitraton_id(PDU.Type.CONSECUTIVE_FRAME)
				output_msg = self.make_tx_msg(arbitration_id, msg_data)
				self.tx_buffer = self.tx_buffer[7-len(self.address.tx_payload_prefix):]
				self.tx_seqnum = (self.tx_seqnum + 1 ) & 0xF
				self.timer_tx_stmin.start()
				self.tx_block_counter+=1

			if self.remote_blocksize != 0 and self.tx_block_counter >= self.remote_blocksize:
				self.tx_state = self.TxState.WAIT_FC
				self.start_rx_fc_timer()

		return output_msg
	
	def pad_message_data(self, msg_data):
		if len(msg_data) < 8 and self.params.tx_padding is not None:
			msg_data.extend(bytearray([self.params.tx_padding & 0xFF] * (8-len(msg_data))))
		
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

	def request_tx_flowcontrol(self):
		self.pending_flow_control_tx = True

	def stop_sending_flow_control(self):
		self.pending_flow_control_tx = False
		self.last_flow_control_frame = None

	def make_tx_msg(self, arbitration_id, data):
		self.pad_message_data(data)
		return CanMessage(arbitration_id = arbitration_id, dlc=len(data), data=data, extended_id=self.address.is_29bits)

	def make_flow_control(self, flow_status=PDU.FlowStatus.ContinueToSend, blocksize=None, stmin=None):
		if blocksize is None:
			blocksize = self.params.blocksize

		if stmin is None:
			stmin = self.params.stmin
		data = PDU.craft_flow_control_data(flow_status, blocksize, stmin)

		return self.make_tx_msg(self.address.get_tx_arbitraton_id(PDU.Type.FLOW_CONTROL), self.address.tx_payload_prefix + data)

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
		self.rx_state = self.RxState.IDLE
		self.empty_rx_buffer()
		self.stop_sending_flow_control()
		self.timer_rx_cf.stop()

	# Init the reception of a multi-pdu frame. 
	def start_reception_after_first_frame(self, frame):
		self.last_seqnum = 0
		self.rx_block_counter = 0
		self.empty_rx_buffer()
		self.rx_frame_length = frame.length
		self.rx_state = self.RxState.WAIT_CF
		self.append_rx_data(frame.data)
		self.request_tx_flowcontrol()
		self.start_rx_cf_timer()

	def trigger_error(self, error):
		if self.error_handler is not None:
			if hasattr(self.error_handler, '__call__') and isinstance(error, IsoTpError):
				self.error_handler(error)
			else:
				self.logger.warning('Given error handler is not a callable object.')

		self.logger.warning(str(error))

	# Clears everything within the layer.
	def reset(self):
		while not self.tx_queue.empty():
			self.tx_queue.get()

		while not self.rx_queue.empty():
			self.rx_queue.get()

		self.stop_sending()
		self.stop_receiving()

	# Gives a time to pass to time.sleep() based on the state of the FSM. Avoid using too much CPU
	def sleep_time(self):
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
	def tx_canbus(self, msg):
		self.bus.send(can.Message(arbitration_id=msg.arbitration_id, data = msg.data, extended_id=msg.is_extended_id))

	def rx_canbus(self):
		msg = self.bus.recv(0)
		if msg is not None:
			return CanMessage(arbitration_id=msg.arbitration_id, data=msg.data, extended_id=msg.is_extended_id)

	def __init__(self, bus, *args, **kwargs):
		global can
		import can
		self.set_bus(bus)
		TransportLayer.__init__(self, rxfn=self.rx_canbus, txfn=self.tx_canbus, *args, **kwargs)

	def set_bus(self, bus):
		if not isinstance(bus, can.BusABC):
			raise ValueError('bus must be a python-can BusABC object')
		self.bus=bus
