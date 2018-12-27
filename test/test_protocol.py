import isotp
import queue
import os
import binascii
import time
import unittest
from test.ThreadableTest import ThreadableTest
from functools import partial
import logging

#logging.basicConfig(level=logging.DEBUG,)

try:
	_SOCKET_IMPOSSIBLE_REASON = ''
	_interface_name = 'vcan0'
	import isotp
	import can
	s = isotp.socket()
	s.bind(_interface_name,1,2)
	s.close()
	_ISOTP_SOCKET_POSSIBLE = True
except Exception as e:
	_SOCKET_IMPOSSIBLE_REASON = str(e)
	_ISOTP_SOCKET_POSSIBLE = False

Message = isotp.protocol.CanMessage

# Make sure that our Timer class used for timeouts is working OK
class testTimer(unittest.TestCase):
	def test_timer(self):
		timeout = 0.2
		t = isotp.TransportLayer.Timer(timeout=timeout)
		self.assertFalse(t.is_timed_out())
		self.assertEqual(t.elapsed(), 0)
		t.start()
		self.assertFalse(t.is_timed_out())
		time.sleep(timeout+0.01)
		self.assertTrue(t.elapsed() > timeout)
		self.assertTrue(t.is_timed_out)
		t.stop()
		self.assertFalse(t.is_timed_out())
		self.assertEqual(t.elapsed(), 0)
		t.start()
		self.assertFalse(t.is_timed_out())

# Here we check that we decode properly ecah type of frame
class TestPDUDecoding(unittest.TestCase):

	def make_pdu(self, data):
		return isotp.protocol.PDU(Message(data=bytearray(data)))

	def test_decode_single_frame(self):
		with self.assertRaises(ValueError):
			self.make_pdu([])

		with self.assertRaises(ValueError):
			self.make_pdu([0])

		for i in range(8,0xF):
			with self.assertRaises(ValueError):
				self.make_pdu([i])

		with self.assertRaises(ValueError):
			self.make_pdu([0x01])

		frame = self.make_pdu([0x01, 0xAA])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
		self.assertEqual(frame.data, bytearray([0xAA]))
		self.assertEqual(frame.length, len(frame.data))

		with self.assertRaises(ValueError):
			self.make_pdu([0x02, 0x11])

		frame = self.make_pdu([0x02, 0x11, 0x22])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22]))
		self.assertEqual(frame.length, len(frame.data))

		frame = self.make_pdu([0x02, 0x11, 0x22, 0x33, 0x44])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22]))
		self.assertEqual(frame.length, len(frame.data))

		frame = self.make_pdu([0x07, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77]))
		self.assertEqual(frame.length, len(frame.data))

		with self.assertRaises(ValueError):
			self.make_pdu([0x08,  0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])


	def test_decode_first_frame(self):
		with self.assertRaises(ValueError):	# Empty payload
			self.make_pdu([])

		with self.assertRaises(ValueError): # Incomplete length
			self.make_pdu([0x10])

		with self.assertRaises(ValueError): # Incomplete length
			self.make_pdu([0x1F])

		with self.assertRaises(ValueError):	#Missing data
			self.make_pdu([0x10, 0x02])

		with self.assertRaises(ValueError):	# Missing data byte
			self.make_pdu([0x10, 0x02, 0x11])

		frame = self.make_pdu([0x10, 0x02, 0x11, 0x22])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22]))
		self.assertEqual(frame.length, 2)

		frame = self.make_pdu([0x10, 0x02, 0x11, 0x22, 0x33])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22]))
		self.assertEqual(frame.length, 2)

		frame = self.make_pdu([0x10, 0x06, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66]))
		self.assertEqual(frame.length, 6)

		with self.assertRaises(ValueError):	# Missing data byte
			frame = self.make_pdu([0x10, 0x0A, 0x11, 0x22, 0x33, 0x44, 0x55])

		frame = self.make_pdu([0x10, 0x0A, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66]))
		self.assertEqual(frame.length, 0xA)

		frame = self.make_pdu([0x1A, 0xBC, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66]))
		self.assertEqual(frame.length, 0xABC)

	
	def test_decode_consecutive_frame(self):
		with self.assertRaises(ValueError):	# Empty payload
			self.make_pdu([])

		frame = self.make_pdu([0x20])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.CONSECUTIVE_FRAME)
		self.assertEqual(frame.data, bytearray([]))
		self.assertEqual(frame.seqnum, 0)

		frame = self.make_pdu([0x20, 0x11])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.CONSECUTIVE_FRAME)
		self.assertEqual(frame.data, bytearray([0x11]))
		self.assertEqual(frame.seqnum, 0)

		frame = self.make_pdu([0x2A, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.CONSECUTIVE_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77]))
		self.assertEqual(frame.seqnum, 0xA)


	def test_decode_flow_control(self):
		with self.assertRaises(ValueError):	# Empty payload
			self.make_pdu([])

		with self.assertRaises(ValueError):	# incomplete
			self.make_pdu([0x30])

		with self.assertRaises(ValueError):	# incomplete
			self.make_pdu([0x30, 0x00])

		frame = self.make_pdu([0x30, 0x00, 0x00])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
		self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
		self.assertEqual(frame.blocksize, 0)
		self.assertEqual(frame.stmin, 0)
		self.assertEqual(frame.stmin_sec, 0)

		frame = self.make_pdu([0x31, 0x00, 0x00])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
		self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.Wait)
		self.assertEqual(frame.blocksize, 0)
		self.assertEqual(frame.stmin, 0)
		self.assertEqual(frame.stmin_sec, 0)

		frame = self.make_pdu([0x32, 0x00, 0x00])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
		self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.Overflow)
		self.assertEqual(frame.blocksize, 0)
		self.assertEqual(frame.stmin, 0)
		self.assertEqual(frame.stmin_sec, 0)

		for i in range(3, 0xF):	# Reserved Flow status
			with self.assertRaises(ValueError):
				frame = self.make_pdu([0x30 + i, 0x00, 0x00])

		frame = self.make_pdu([0x30, 0xFF, 0x00])
		self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
		self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
		self.assertEqual(frame.blocksize, 0xFF)
		self.assertEqual(frame.stmin, 0)
		self.assertEqual(frame.stmin_sec, 0)

		for i in range(0,0x7F):		# Millisecs
			frame = self.make_pdu([0x30, 0x00, i])
			self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
			self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
			self.assertEqual(frame.blocksize, 0)
			self.assertEqual(frame.stmin, i)
			self.assertEqual(frame.stmin_sec, i/1000)

		for i in range(0xF1, 0xF9):	# Microsecs
			frame = self.make_pdu([0x30, 0x00, i])
			self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
			self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
			self.assertEqual(frame.blocksize, 0)
			self.assertEqual(frame.stmin, i)
			self.assertEqual(frame.stmin_sec, (i - 0xF0)/10000)

		for i in range(0x80, 0xF1):		# Reserved StMin
			with self.assertRaises(ValueError):
				frame = self.make_pdu([0x30, 0x00, i])

		for i in range(0xFA, 0x100):	# Reserved StMin
			with self.assertRaises(ValueError):
				frame = self.make_pdu([0x30, 0x00, i])

# Just a class with some helper such as simulate_rx() to make the tests cleaners.
class TransportLayerBaseTest(unittest.TestCase):
	def __init__(self, *args, **kwargs):
		unittest.TestCase.__init__(self, *args, **kwargs)
		self.ll_rx_queue = queue.Queue()
		self.ll_tx_queue = queue.Queue()
		self.error_triggered = {}

	def error_handler(self, error):
		if error.__class__ not in self.error_triggered:
			self.error_triggered[error.__class__] = []

		self.error_triggered[error.__class__].append(error)

	def stack_txfn(self, msg):
		if not self.ll_tx_queue.full():
			self.ll_tx_queue.put(msg)

	def stack_rxfn(self):
		if not self.ll_rx_queue.empty():
			return  self.ll_rx_queue.get()

	def rx_isotp_frame(self):
		return self.stack.recv()

	def tx_isotp_frame(self, frame):
		self.stack.send(frame)

	def get_tx_can_msg(self):
		if not self.ll_tx_queue.empty():
			return self.ll_tx_queue.get()

	def make_payload(self, size, start_val=0):
		return [int(x%0x100) for x in range(start_val, start_val+size)]

	def assert_sent_flow_control(self, stmin, blocksize, prefix = None, padding_byte=None, extra_msg=''):
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg, 'Expected a Flow Control message, but none was sent.' + ' ' + extra_msg)
		data = bytearray()
		if prefix is not None:
			data.extend(prefix)

		data.extend(bytearray([0x30, blocksize, stmin]))
		if padding_byte is not None:
			padlen = 5
			if prefix is not None:
				padlen -= len(prefix)
			data.extend(bytearray([padding_byte]*padlen))

		self.assertEqual(msg.data, data, 'Message sent is not the wanted flow control'+ ' ' + extra_msg)	# Flow Control
		self.assertEqual(msg.dlc, len(data), 'Flow control message has wrong DLC. Expecting=0x%02x, received=0x%02x' % (len(data), msg.dlc))	

	def assert_error_triggered(self, error_type):
		if error_type in self.error_triggered:
			if len(self.error_triggered[error_type]):
				return

		raise AssertionError('Error of type %s not triggered' % error_type.__name__)

	def assert_no_error_triggered(self):
		if len(self.error_triggered) > 0:
			raise AssertionError('%d errors hsa been triggered while non should have' % len(self.error_triggered))			

	def clear_errors(self):
		self.error_triggered = {}

	def init_test_case(self):
		while not self.ll_rx_queue.empty():
			self.ll_rx_queue.get()

		while not self.ll_tx_queue.empty():
			self.ll_tx_queue.get()

		self.clear_errors()

	def simulate_rx_msg(self, msg):
		self.ll_rx_queue.put(msg)

	def make_flow_control_data(self, flow_status, stmin, blocksize, prefix=None):
		data = bytearray()
		if prefix is not None:
			data.extend(bytearray(prefix))
		data.extend(bytearray( [0x30 | (flow_status & 0xF), blocksize, stmin]))

		return data

# Check the behaviour of the transport layer. Sequenece of CAN frames, timings, etc.
class TestBehaviour(TransportLayerBaseTest):
	RXID = 0x456
	TXID = 0x123

	def setUp(self):
		params = {
			'stmin' : 1,
			'blocksize' : 8,
			'squash_stmin_requirement' : False,
			'rx_flowcontrol_timeout'  : 1000,
			'rx_consecutive_frame_timeout' : 1000,
			'wftmax' : 0
		}
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_11bits, txid=self.TXID, rxid=self.RXID)
		self.stack = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, error_handler = self.error_handler, params = params)
		self.error_triggered = {}

		self.init_test_case()


	def simulate_rx(self, data, rxid=RXID):
		self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray(data)))

	def simulate_rx_flowcontrol(self, flow_status, stmin, blocksize, prefix=None):
		data = bytearray()
		if prefix is not None:
			data.extend(bytearray(prefix))
		data.extend(bytearray( [0x30 | (flow_status & 0xF), blocksize, stmin]))

		self.simulate_rx(data = data)

	# ============= Testing starts here ============

	# Make sure we can receive a single frame
	def test_receive_single_sf(self):
		self.simulate_rx(data = [0x05, 0x11, 0x22, 0x33, 0x44, 0x55])
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray([0x11, 0x22, 0x33, 0x44, 0x55]))

	# Make sure we can receive multiple single frame
	def test_receive_multiple_sf(self):
		self.stack.process()
		self.stack.process()

		self.simulate_rx(data = [0x05, 0x11, 0x22, 0x33, 0x44, 0x55])
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray([0x11, 0x22, 0x33, 0x44, 0x55])) 	

		self.assertIsNone(self.rx_isotp_frame())
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())

		self.simulate_rx(data = [0x05, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE])
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray([0xAA, 0xBB, 0xCC, 0xDD, 0xEE]))

		self.assertIsNone(self.rx_isotp_frame())
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())

	def test_receive_multiple_sf_single_process_call(self):
		self.simulate_rx(data = [0x05, 0x11, 0x22, 0x33, 0x44, 0x55])
		self.simulate_rx(data = [0x05, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE])
		self.stack.process()	# Call process once
		self.assertEqual(self.rx_isotp_frame(), bytearray([0x11, 0x22, 0x33, 0x44, 0x55]))
		self.assertEqual(self.rx_isotp_frame(), bytearray([0xAA, 0xBB, 0xCC, 0xDD, 0xEE]))
		self.assertIsNone(self.rx_isotp_frame())

	def test_receive_multiframe(self):
		payload_size = 10
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.simulate_rx(data = [0x21] + payload[6:10])
		self.stack.process()
		data = self.rx_isotp_frame()
		self.assertEqual(data, bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())

	def test_receive_2_multiframe(self):
		payload_size = 10
		payload = self.make_payload(payload_size)

		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.simulate_rx(data = [0x21] + payload[6:10])
		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.simulate_rx(data = [0x21] + payload[6:10])
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload))
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())

	def test_receive_multiframe_check_flowcontrol(self):
		self.stack.params.set('stmin', 0x02)
		self.stack.params.set('blocksize', 0x05)

		payload_size = 10
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.stack.process()
		self.assert_sent_flow_control(stmin=2, blocksize=5)
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x21] + payload[6:10])
		self.stack.process()
		data = self.rx_isotp_frame()
		self.assertEqual(data, bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())

	def test_receive_multiframe_flowcontrol_padding(self):
		padding_byte = 0x22
		self.stack.params.set('tx_padding', padding_byte)
		self.stack.params.set('stmin', 0x02)
		self.stack.params.set('blocksize', 0x05)

		payload_size = 10
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.stack.process()
		self.assert_sent_flow_control(stmin=2, blocksize=5, padding_byte=padding_byte)
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x21] + payload[6:10])
		self.stack.process()
		data = self.rx_isotp_frame()
		self.assertEqual(data, bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())

	def test_long_multiframe_2_flow_control(self):
		payload_size = 30
		payload = self.make_payload(payload_size)
		self.stack.params.set('stmin', 0x05)
		self.stack.params.set('blocksize', 0x3)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.stack.process()
		self.assert_sent_flow_control(stmin=5, blocksize=3)
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x21] + payload[6:14])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x22] + payload[14:21])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x23] + payload[21:28])
		self.stack.process()
		self.assert_sent_flow_control(stmin=5, blocksize=3)
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x24] + payload[28:30])
		self.stack.process()		
		data = self.rx_isotp_frame()
		self.assertEqual(data, bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())

	def test_receive_multiframe_bad_seqnum(self):
		payload_size = 10
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.simulate_rx(data = [0x22] + payload[6:10])		# Bad Sequence number
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.assertIsNone(self.get_tx_can_msg()) # Do not send flow control
		self.assert_error_triggered(isotp.protocol.WrongSequenceNumberError)

	def test_receive_timeout_consecutive_frame_after_first_frame(self):
		self.stack.params.set('rx_consecutive_frame_timeout', 200)

		payload_size = 10
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.stack.process()
		time.sleep(0.2)	# Should stop receivving after 200 msec
		self.simulate_rx(data = [0x21] + payload[6:10])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())	# No message received indeed
		self.assert_error_triggered(isotp.protocol.ConsecutiveFrameTimeoutError)
		self.assert_error_triggered(isotp.protocol.UnexpectedConsecutiveFrameError)

	def test_receive_recover_timeout_consecutive_frame(self):
		self.stack.params.set('rx_consecutive_frame_timeout', 200)

		payload_size = 10
		payload1 = self.make_payload(payload_size)
		payload2 = self.make_payload(payload_size,1)
		self.assertNotEqual(payload1, payload2)
		self.simulate_rx(data = [0x10, payload_size] + payload1[0:6])
		self.stack.process()
		time.sleep(0.2)
		self.simulate_rx(data = [0x21] + payload1[6:10])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x10, payload_size] + payload2[0:6])
		self.simulate_rx(data = [0x21] + payload2[6:10])	
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload2))	# Correctly received
		self.assert_error_triggered(isotp.protocol.ConsecutiveFrameTimeoutError)
		self.assert_error_triggered(isotp.protocol.UnexpectedConsecutiveFrameError)

	def test_receive_multiframe_interrupting_another(self):
		self.stack.params.set('rx_consecutive_frame_timeout', 200)

		payload_size = 10
		payload1 = self.make_payload(payload_size)
		payload2 = self.make_payload(payload_size,1)
		self.assertNotEqual(payload1, payload2)
		self.simulate_rx(data = [0x10, payload_size] + payload1[0:6])
		self.simulate_rx(data = [0x10, payload_size] + payload2[0:6])	# New frame interrupting previous
		self.simulate_rx(data = [0x21] + payload2[6:10])		
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload2))
		self.assertIsNone(self.rx_isotp_frame())
		self.assert_error_triggered(isotp.protocol.ReceptionInterruptedWithFirstFrameError)

	def test_receive_single_frame_interrupt_multiframe_then_recover(self):
		self.stack.params.set('rx_consecutive_frame_timeout', 200)

		payload1_size = 16
		payload2_size = 16
		payload1 = self.make_payload(payload1_size)
		payload2 = self.make_payload(payload2_size,1)
		sf_payload = self.make_payload(5, 2)
		self.assertNotEqual(payload1, payload2)
		self.simulate_rx(data = [0x10, payload1_size] + payload1[0:6])
		self.stack.process()
		self.simulate_rx(data = [0x21] + payload1[6:13])	
		self.simulate_rx(data = [0x05] + sf_payload)	
		self.simulate_rx(data = [0x10, payload2_size] + payload2[0:6])
		self.stack.process()
		self.simulate_rx(data = [0x21] + payload2[6:13])		
		self.simulate_rx(data = [0x22] + payload2[13:16])		
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray(sf_payload))
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload2))
		self.assertIsNone(self.rx_isotp_frame())
		self.assert_error_triggered(isotp.protocol.ReceptionInterruptedWithSingleFrameError)

	def test_receive_4095_multiframe(self):
		payload_size = 4095
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x1F, 0xFF] + payload[0:6])
		n = 6
		seqnum = 1
		while n<4096:
			self.simulate_rx(data = [0x20 | (seqnum & 0xF)] + payload[n:min(n+7, 4096)])	
			self.stack.process()
			n += 7
			seqnum +=1
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())

	def test_receive_4095_multiframe_check_blocksize(self):
		for blocksize in range(1,10):
			self.perform_receive_4095_multiframe_check_blocksize(blocksize=blocksize)

	def perform_receive_4095_multiframe_check_blocksize(self, blocksize):
		payload_size = 4095
		self.stack.params.set('blocksize', blocksize)
		self.stack.params.set('stmin', 2)

		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x1F, 0xFF] + payload[0:6])
		self.stack.process()
		self.assert_sent_flow_control(blocksize=blocksize, stmin=2, extra_msg='blocksize=%d' % blocksize)
		n = 6
		block_counter = 0
		seqnum = 1
		while n<4096:
			self.simulate_rx(data = [0x20 | (seqnum & 0xF)] + payload[n:min(n+7, 4096)])	
			self.stack.process()
			block_counter+=1
			n += 7
			seqnum +=1
			if block_counter % blocksize == 0 and n < 4095:
				self.assert_sent_flow_control(blocksize=blocksize, stmin=2, extra_msg='blocksize=%d' % blocksize)
			else:
				self.assertIsNone(self.get_tx_can_msg(), 'Sent a message something after block %d but shoud not have. blocksize = %d' % (block_counter, blocksize))

		self.assertEqual(self.rx_isotp_frame(), bytearray(payload), 'blocksize=%d' % blocksize)
		self.assertIsNone(self.rx_isotp_frame(), 'blocksize=%d' % blocksize)

	def receive_invalid_can_message(self):
		for i in range(4, 0x10):
			self.simulate_rx(data = [i << 4, 0x00, 0x00])
			self.stack.process()
			self.assert_error_triggered(isotp.protocol.InvalidCanDataError)
			self.clear_errors()


	# ================ Transmission ====================

	def assert_tx_timing_spin_wait_for_msg(self, mintime, maxtime):
		msg = None
		diff = 0
		t = time.time()
		while msg is None:
			self.stack.process()
			msg = self.get_tx_can_msg()
			diff = time.time() - t
			self.assertLess(diff, maxtime, 'Timed out') # timeout
		self.assertGreater(diff, mintime, 'Stack sent a message too quickly')
		return msg


	def test_send_single_frame(self):
		for i in range(1,7):
			payload = self.make_payload(i,i)
			self.assertIsNone(self.get_tx_can_msg())
			self.tx_isotp_frame(payload)
			self.stack.process()
			msg = self.get_tx_can_msg()
			self.assertEqual(msg.arbitration_id, self.TXID)
			self.assertEqual(msg.dlc, i+1)
			self.assertEqual(msg.data, bytearray([0x0 | i] + payload))

	def test_padding_single_frame(self):
		padding_byte = 0xAA
		self.stack.params.set('tx_padding', padding_byte)

		for i in range(1,7):
			payload = self.make_payload(i,i)
			self.assertIsNone(self.get_tx_can_msg())
			self.tx_isotp_frame(payload)
			self.stack.process()
			msg = self.get_tx_can_msg()
			self.assertEqual(msg.arbitration_id, self.TXID)
			self.assertEqual(msg.dlc, 8)
			self.assertEqual(msg.data, bytearray([0x0 | i] + payload + [padding_byte] * (7-i)))

	def test_send_multiple_single_frame_one_process(self):
		payloads = dict()
		for i in range(1,8):
			payload = self.make_payload(i,i)
			self.tx_isotp_frame(payload)
			payloads[i] = payload

		self.stack.process()

		for i in range(1,8):
			msg = self.get_tx_can_msg()
			self.assertIsNotNone(msg)
			self.assertEqual(msg.arbitration_id, self.TXID)
			self.assertEqual(msg.dlc, i+1)
			self.assertEqual(msg.data, bytearray([0x0 | i] + payloads[i]))

	def test_send_small_multiframe(self):
		payload = self.make_payload(10)
		self.assertIsNone(self.get_tx_can_msg())
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.arbitration_id, self.TXID)
		self.assertEqual(msg.dlc, 8)
		self.assertEqual(msg.data, bytearray([0x10, 0x0A] + payload[:6]))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=8)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, self.TXID)
		self.assertEqual(msg.dlc, 5)
		self.assertEqual(msg.data, bytearray([0x21] + payload[6:10]))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())

	def test_padding_multi_frame(self):
		padding_byte = 0x55
		self.stack.params.set('tx_padding', padding_byte)
		payload = self.make_payload(10)
		self.assertIsNone(self.get_tx_can_msg())
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.arbitration_id, self.TXID)
		self.assertEqual(msg.dlc, 8)
		self.assertEqual(msg.data, bytearray([0x10, 0x0A] + payload[:6]))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=8)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, self.TXID)
		self.assertEqual(msg.dlc, 8)
		self.assertEqual(msg.data, bytearray([0x21] + payload[6:10] + [padding_byte]*3))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())

	def test_send_2_small_multiframe(self):
		payload1 = self.make_payload(10)
		payload2 = self.make_payload(10,1)
		self.tx_isotp_frame(payload1)
		self.tx_isotp_frame(payload2)

		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.data, bytearray([0x10, 0x0A] + payload1[:6]))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=8)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.data, bytearray([0x21] + payload1[6:10]))
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.data, bytearray([0x10, 0x0A] + payload2[:6]))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=8)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.data, bytearray([0x21] + payload2[6:10]))
		self.assertIsNone(self.get_tx_can_msg())

	def test_send_multiframe_flow_control_timeout(self):
		self.stack.params.set('rx_flowcontrol_timeout', 200)

		payload = self.make_payload(10)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 0x0A] + payload[:6]))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		time.sleep(0.2)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNone(msg)
		self.assert_error_triggered(isotp.protocol.FlowControlTimeoutError)

	def test_send_multiframe_flow_control_timeout_recover(self):
		self.stack.params.set('rx_flowcontrol_timeout', 200)

		payload = self.make_payload(10)
		payload2 = self.make_payload(10,1)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 0x0A] + payload[:6]))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		time.sleep(0.2)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 0x0A] + payload[:6]))
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=8)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x21] + payload[6:10]))
		self.assert_error_triggered(isotp.protocol.FlowControlTimeoutError)

	def test_send_unexpected_flow_control(self):
		self.simulate_rx_flowcontrol(flow_status=0, stmin=100, blocksize=8)
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.assert_error_triggered(isotp.protocol.UnexpectedFlowControlError)

	def test_send_respect_wait_frame(self):
		self.stack.params.set('wftmax', 15)
		self.stack.params.set('rx_flowcontrol_timeout', 500)

		payload = self.make_payload(20)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 20] + payload[:6]))
		for i in range(10):
			self.simulate_rx_flowcontrol(flow_status=1, stmin=0, blocksize=1)
			self.stack.process()
			time.sleep(0.2)
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=1)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x21] + payload[6:13]))
		for i in range(10):
			self.simulate_rx_flowcontrol(flow_status=1, stmin=0, blocksize=1)
			self.stack.process()
			time.sleep(0.2)
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=1)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x22] + payload[13:20]))

		self.assert_no_error_triggered()

	def test_send_respect_wait_frame_but_timeout(self):
		self.stack.params.set('wftmax', 15)
		self.stack.params.set('rx_flowcontrol_timeout', 500)

		payload = self.make_payload(20)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 20] + payload[:6]))
		for i in range(3):
			self.simulate_rx_flowcontrol(flow_status=1, stmin=0, blocksize=1)
			self.stack.process()
			time.sleep(0.2)
		time.sleep(0.5)
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=1)
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		
		self.assert_error_triggered(isotp.protocol.FlowControlTimeoutError)

	def test_send_wait_frame_after_first_frame_wftmax_0(self):
		self.stack.params.set('wftmax', 0)
		payload = self.make_payload(10)
		self.tx_isotp_frame(payload)
		self.stack.process()
		self.simulate_rx_flowcontrol(flow_status=1, stmin=0, blocksize=8)
		self.stack.process()
		time.sleep(0.01)
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=8)
		self.stack.process()
		self.assert_error_triggered(isotp.protocol.UnsuportedWaitFrameError)

	def test_send_wait_frame_after_consecutive_frame_wftmax_0(self):
		self.stack.params.set('wftmax', 0)

		payload = self.make_payload(20)
		self.tx_isotp_frame(payload)
		self.stack.process()
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=1)
		self.stack.process()
		self.simulate_rx_flowcontrol(flow_status=1, stmin=0, blocksize=1)
		self.stack.process()
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=1)
		self.stack.process()
		self.assert_error_triggered(isotp.protocol.UnsuportedWaitFrameError)

	def test_send_wait_frame_after_first_frame_reach_max(self):
		self.stack.params.set('wftmax', 5)

		payload = self.make_payload(20)
		self.tx_isotp_frame(payload)
		self.stack.process()
		self.get_tx_can_msg()
		for i in range(6):
			self.simulate_rx_flowcontrol(flow_status=1, stmin=0, blocksize=1)
			self.stack.process()
			time.sleep(0.2)
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=1)
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.assert_error_triggered(isotp.protocol.MaximumWaitFrameReachedError)
		self.assert_error_triggered(isotp.protocol.UnexpectedFlowControlError)

	def test_send_wait_frame_after_conscutive_frame_reach_max(self):
		self.stack.params.set('wftmax', 5)

		payload = self.make_payload(20)
		self.tx_isotp_frame(payload)
		self.stack.process()
		self.get_tx_can_msg()
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=1)
		self.stack.process()
		self.get_tx_can_msg()
		for i in range(6):
			self.simulate_rx_flowcontrol(flow_status=1, stmin=0, blocksize=1)
			self.stack.process()
			time.sleep(0.2)
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=1)
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.assert_error_triggered(isotp.protocol.MaximumWaitFrameReachedError)
		self.assert_error_triggered(isotp.protocol.UnexpectedFlowControlError)

	def test_send_4095_multiframe_zero_stmin(self):
		self.perform_multiframe_test_no_stmin(4095, 5)

	def test_send_128_multiframe_variable_blocksize(self):
		for i in range(1,8):
			self.perform_multiframe_test_no_stmin(128, i)
	
	def perform_multiframe_test_no_stmin(self, payload_size, blocksize):
		stmin = 0
		payload = self.make_payload(payload_size)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg, 'blocksize = %d' % blocksize)
		self.assertEqual(msg.data, bytearray([0x10 | ((payload_size >> 8) & 0xF), payload_size & 0xFF] + payload[:6]), 'blocksize = %d' % blocksize)
		self.simulate_rx_flowcontrol(flow_status=0, stmin=stmin, blocksize=blocksize)

		block_counter = 0
		seqnum = 1
		n = 6
		self.stack.process()	# Call only once, should enqueue all message until next flow control
		while True:
			msg = self.get_tx_can_msg()
			if block_counter < blocksize:
				self.assertIsNotNone(msg, 'blocksize = %d' % blocksize)
				self.assertEqual(msg.data, bytearray([0x20 | seqnum] + payload[n:min(n+7, payload_size)]), 'blocksize = %d' % blocksize)
				n+=7
				seqnum = (seqnum+1) & 0xF
				block_counter+=1
				if n > payload_size:
					break
			else:
				self.assertIsNone(msg, 'blocksize = %d' % blocksize)
				self.simulate_rx_flowcontrol(flow_status=0, stmin=stmin, blocksize=blocksize)
				self.stack.process() # Receive the flow control and enqueue another bloc of can message. 
				block_counter = 0

	def test_squash_timing_requirement(self):
		self.stack.params.set('squash_stmin_requirement', True)

		payload_size = 4095
		stmin=100 # 100 msec
		blocksize = 8

		payload = self.make_payload(payload_size)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.data, bytearray([0x10 | ((payload_size >> 8) & 0xF), payload_size & 0xFF] + payload[:6]))
		self.simulate_rx_flowcontrol(flow_status=0, stmin=stmin, blocksize=blocksize)

		block_counter = 0
		seqnum = 1
		n = 6
		self.stack.process()	# Call only once, should enqueue all message until next flow control
		while True:
			msg = self.get_tx_can_msg()
			if block_counter < blocksize:
				self.assertIsNotNone(msg)
				self.assertEqual(msg.data, bytearray([0x20 | seqnum] + payload[n:min(n+7, payload_size)]))
				n+=7
				seqnum = (seqnum+1) & 0xF
				block_counter+=1
				if n > payload_size:
					break
			else:
				self.assertIsNone(msg)
				self.simulate_rx_flowcontrol(flow_status=0, stmin=stmin, blocksize=blocksize)
				self.stack.process() # Receive the flow control and enqueue another bloc of can message. 
				block_counter = 0

	def test_stmin_requirement(self):
		stmin = 100 # 100 msec
		payload_size = 30
		blocksize = 3
		payload = self.make_payload(payload_size)
		self.tx_isotp_frame(payload)
		self.stack.process()
		t = time.time()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10 | ((payload_size >> 8) & 0xF), payload_size & 0xFF] + payload[:6]), 'stmin = %d' % stmin)
		self.simulate_rx_flowcontrol(flow_status=0, stmin=stmin, blocksize=blocksize)
		msg = self.assert_tx_timing_spin_wait_for_msg(mintime=0.095, maxtime=1)
		self.assertEqual(msg.data, bytearray([0x21] + payload[6:13]))
		msg = self.assert_tx_timing_spin_wait_for_msg(mintime=0.095, maxtime=1)
		self.assertEqual(msg.data, bytearray([0x22] + payload[13:20]))
		msg = self.assert_tx_timing_spin_wait_for_msg(mintime=0.095, maxtime=1)
		self.assertEqual(msg.data, bytearray([0x23] + payload[20:27]))
		self.simulate_rx_flowcontrol(flow_status=0, stmin=stmin, blocksize=blocksize)
		msg = self.assert_tx_timing_spin_wait_for_msg(mintime=0.095, maxtime=1)
		self.assertEqual(msg.data, bytearray([0x24] + payload[27:30]))

	def test_send_nothing_with_empty_payload(self):
		self.tx_isotp_frame([])
		self.tx_isotp_frame([])
		self.tx_isotp_frame([])
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())

	def test_send_single_frame_after_empty_payload(self):
		self.tx_isotp_frame([])
		self.tx_isotp_frame([0x55])
		self.tx_isotp_frame([])
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.data, bytearray([0x01, 0x55]))

	#Sets blocksize to 0, never sends flow control except after first frame
	def test_send_blocksize_zero(self):
		payload = self.make_payload(4095)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x1F, 0xFF] + payload[:6]))
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)

		seqnum = 1
		n=6
		self.stack.process()
		while True:
			msg = self.get_tx_can_msg()
			self.assertIsNotNone(msg)
			self.assertEqual(msg.data, bytearray([0x20 | seqnum] + payload[n:min(n+7, 4095)]))
			n+=7
			seqnum = (seqnum+1) & 0xF

			if n > 4095:
				break

	# =============== Parameters ===========
	def create_layer(self, params):
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_11bits, txid=self.TXID, rxid=self.RXID)
		return isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params = params)

	def test_params_bad_values(self):
		params = {
			'stmin' : 1,
			'blocksize' : 8,
			'squash_stmin_requirement' : False,
			'rx_flowcontrol_timeout'  : 1000,
			'rx_consecutive_frame_timeout' : 1000
		}

		self.create_layer({}) # Empty params. Use default value
		self.create_layer(params)

		with self.assertRaises(ValueError):
			params['stmin'] = -1
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['stmin'] = 0x100
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['stmin'] = 'string'
			self.create_layer(params)
		params['stmin'] = 1


		with self.assertRaises(ValueError):
			params['blocksize'] = -1
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['blocksize'] = 0x100
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['blocksize'] = 'string'
			self.create_layer(params)
		params['blocksize'] = 8


		with self.assertRaises(ValueError):
			params['squash_stmin_requirement'] = 'string'
			self.create_layer(params)
		params['squash_stmin_requirement'] = False


		with self.assertRaises(ValueError):
			params['rx_flowcontrol_timeout'] = -1
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['rx_flowcontrol_timeout'] = 'string'
			self.create_layer(params)
		params['rx_flowcontrol_timeout'] = 1000


		with self.assertRaises(ValueError):
			params['rx_consecutive_frame_timeout'] = -1
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['rx_consecutive_frame_timeout'] = 'string'
			self.create_layer(params)
		params['rx_consecutive_frame_timeout'] = 1000

# We check that addressing modes have the right effect on payloads.
class TestAddressingMode(TransportLayerBaseTest):
	def setUp(self):
		self.init_test_case()

	def assert_cant_send_multiframe_functional(self, address):
		with self.assertRaises(Exception):
			address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FIRST_FRAME, isotp.protocol.TargetAddressType.Functional)
		with self.assertRaises(Exception):
			address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.CONSECUTIVE_FRAME, isotp.protocol.TargetAddressType.Functional)
		with self.assertRaises(Exception):
			address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FLOW_CONTROL, isotp.protocol.TargetAddressType.Functional)

	def test_create_address(self):
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_11bits, txid=1, rxid=2)
		self.assert_cant_send_multiframe_functional(address)
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_29bits, txid=1, rxid=2)
		self.assert_cant_send_multiframe_functional(address)
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.NormalFixed_29bits, source_address=1, target_address=2)
		self.assert_cant_send_multiframe_functional(address)
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Extended_11bits, txid=1, rxid=2, target_address=3)
		self.assert_cant_send_multiframe_functional(address)
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Extended_29bits, txid=1, rxid=2, target_address=3)
		self.assert_cant_send_multiframe_functional(address)
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Mixed_11bits, txid=1, rxid=2, address_extension=3)
		self.assert_cant_send_multiframe_functional(address)
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Mixed_29bits, source_address=1, target_address=2, address_extension=3)
		self.assert_cant_send_multiframe_functional(address)

	def test_single_frame_only_function_tatype(self):
		tatype = isotp.protocol.TargetAddressType.Functional

		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_11bits, txid=1, rxid=2)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
		layer.send(self.make_payload(7), tatype)
		with self.assertRaises(ValueError):
			layer.send(self.make_payload(8), tatype)

		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_29bits, txid=1, rxid=2)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
		layer.send(self.make_payload(7), tatype)
		with self.assertRaises(ValueError):
			layer.send(self.make_payload(8), tatype)

		address = isotp.protocol.Address(isotp.protocol.AddressingMode.NormalFixed_29bits, source_address=1, target_address=2)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
		layer.send(self.make_payload(7), tatype)
		with self.assertRaises(ValueError):
			layer.send(self.make_payload(8), tatype)

		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Extended_11bits, txid=1, rxid=2, target_address=3)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
		layer.send(self.make_payload(6), tatype)
		with self.assertRaises(ValueError):
			layer.send(self.make_payload(7), tatype)

		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Extended_29bits, txid=1, rxid=2, target_address=3)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
		layer.send(self.make_payload(6), tatype)
		with self.assertRaises(ValueError):
			layer.send(self.make_payload(7), tatype)

		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Mixed_11bits, txid=1, rxid=2, address_extension=3)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
		layer.send(self.make_payload(6), tatype)
		with self.assertRaises(ValueError):
			layer.send(self.make_payload(7), tatype)

		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Mixed_29bits, source_address=1, target_address=2, address_extension=3)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
		layer.send(self.make_payload(6), tatype)
		with self.assertRaises(ValueError):
			layer.send(self.make_payload(7), tatype)
		
	def test_11bits_normal_basic(self):
		rxid = 0x123
		txid = 0x456
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_11bits, txid=txid, rxid=rxid)

		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 

		self.assertTrue(address.is_for_me(Message(arbitration_id=rxid)))
		self.assertFalse(address.is_for_me(Message(arbitration_id=rxid, extended_id=True)))
		self.assertFalse(address.is_for_me(Message(arbitration_id=rxid+1)))
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, functional), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FIRST_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.CONSECUTIVE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FLOW_CONTROL, physical), txid)

	def test_11bits_normal_through_layer(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		rxid = 0x123
		txid = 0x456
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_11bits, txid=txid, rxid=rxid)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin':0, 'blocksize':0})

		# Receive Single frame - Physical
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=False))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive Single frame - Functional
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=False))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive multiframe - Physical
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]), extended_id=False))
		layer.process()
		self.assert_sent_flow_control(stmin=0, blocksize=0)
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([0x21, 0x07, 0x08]), extended_id=False))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

		#Transmit single frame - Physical / Functional
		layer.reset()
		layer.send(b'\x04\x05\x06', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
		self.assertFalse(msg.is_extended_id)

		# Transmit multiframe - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09]))
		self.assertFalse(msg.is_extended_id)

		self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0), extended_id=False))
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([0x21, 0x0A, 0x0B]))
		self.assertFalse(msg.is_extended_id)

	def test_29bits_normal_basic(self):
		rxid = 0x123456
		txid = 0x789ABC
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_29bits, txid=txid, rxid=rxid)
		self.assertTrue(address.is_for_me(Message(arbitration_id=rxid,  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(arbitration_id=rxid, extended_id=False)))
		self.assertFalse(address.is_for_me(Message(arbitration_id=rxid+1, extended_id=True)))
		self.assertFalse(address.is_for_me(Message(arbitration_id=rxid+1, extended_id=False)))
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, functional), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FIRST_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.CONSECUTIVE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FLOW_CONTROL, physical), txid)

	def test_29bits_normal_through_layer(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		rxid = 0x123456
		txid = 0x789ABC
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Normal_29bits, txid=txid, rxid=rxid)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin':0, 'blocksize':0})

		# Receive Single frame - Physical
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive Single frame - Functional
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive multiframe - Physical
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]), extended_id=True))
		layer.process()
		self.assert_sent_flow_control(stmin=0, blocksize=0)
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([0x21, 0x07, 0x08]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

		#Transmit single frame - Physical / Functional
		layer.reset()
		layer.send(b'\x04\x05\x06', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
		self.assertTrue(msg.is_extended_id)

		# Transmit multiframe - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09]))
		self.assertTrue(msg.is_extended_id)

		self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0), extended_id=True))
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([0x21, 0x0A, 0x0B]))
		self.assertTrue(msg.is_extended_id)

	def test_29bits_normal_fixed(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		ta = 0x55
		sa = 0xAA
		rxid_physical = 0x18DAAA55
		rxid_functional = 0x18DBAA55
		txid_physical = 0x18DA55AA
		txid_functional = 0x18DB55AA
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.NormalFixed_29bits, target_address = ta, source_address=sa)

		self.assertTrue(address.is_for_me(Message(rxid_physical,  extended_id=True)))
		self.assertTrue(address.is_for_me(Message(rxid_functional,  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(txid_physical,  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(txid_functional,  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(arbitration_id=(rxid_physical) & 0x7FF, extended_id=False)))
		self.assertFalse(address.is_for_me(Message(arbitration_id=rxid_physical+1, extended_id=True)))
		self.assertFalse(address.is_for_me(Message(arbitration_id=(rxid_physical+1)&0x7FF, extended_id=False)))

		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, physical), txid_physical)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, functional), txid_functional)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FIRST_FRAME, physical), txid_physical)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.CONSECUTIVE_FRAME, physical), txid_physical)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FLOW_CONTROL, physical), txid_physical)

	def test_29bits_normal_fixed_through_layer(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		ta = 0x55
		sa = 0xAA
		rxid_physical = 0x18DAAA55
		rxid_functional = 0x18DBAA55
		txid_physical = 0x18DA55AA
		txid_functional = 0x18DB55AA
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.NormalFixed_29bits, target_address = ta, source_address=sa)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin':0, 'blocksize':0})

		# Receive Single frame - Physical
		self.simulate_rx_msg(Message(arbitration_id = rxid_physical, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive Single frame - Functional
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid_functional, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive multiframe - Physical
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid_physical, data=bytearray([0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]), extended_id=True))
		layer.process()
		self.assert_sent_flow_control(stmin=0, blocksize=0)
		self.simulate_rx_msg(Message(arbitration_id = rxid_physical, data=bytearray([0x21, 0x07, 0x08]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

		#Transmit single frame - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid_physical)
		self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
		self.assertTrue(msg.is_extended_id)

		#Transmit single frame - Functional
		layer.reset()
		layer.send(b'\x04\x05\x06', functional)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid_functional)
		self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
		self.assertTrue(msg.is_extended_id)

		# Transmit multiframe - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid_physical)
		self.assertEqual(msg.data, bytearray([0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09]))
		self.assertTrue(msg.is_extended_id)

		self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0), extended_id=True))
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid_physical)
		self.assertEqual(msg.data, bytearray([0x21, 0x0A, 0x0B]))
		self.assertTrue(msg.is_extended_id)

	def test_11bits_extended(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		txid = 0x123
		rxid = 0x456
		sa = 0x55
		ta = 0xAA
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Extended_11bits, txid=txid, rxid=rxid, source_address=sa, target_address=ta)

		self.assertFalse(address.is_for_me(Message(rxid,  extended_id=False))) # No data
		self.assertFalse(address.is_for_me(Message(txid,  extended_id=False))) # No data, wrong id
		self.assertFalse(address.is_for_me(Message(rxid, data = bytearray([ta]),  extended_id=False))) # wrong id
		self.assertTrue(address.is_for_me(Message(rxid, data = bytearray([sa]),  extended_id=False)))
		self.assertFalse(address.is_for_me(Message(rxid, data = bytearray([sa]),  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(rxid+1, data = bytearray([sa]),  extended_id=False)))
		self.assertFalse(address.is_for_me(Message(rxid, data = bytearray([sa+1]),  extended_id=False)))

		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, functional), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FIRST_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.CONSECUTIVE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FLOW_CONTROL, physical), txid)

	def test_11bits_extended_through_layer(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		txid = 0x123
		rxid = 0x456
		sa = 0x55
		ta = 0xAA
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Extended_11bits, txid=txid, rxid=rxid, source_address=sa, target_address=ta)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin':0, 'blocksize':0})

		# Receive Single frame - Physical / Functional
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([sa, 0x03, 0x01, 0x02, 0x03]), extended_id=False))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive multiframe - Physical
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([sa, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=False))
		layer.process()
		self.assert_sent_flow_control(prefix=[ta], stmin=0, blocksize=0)
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([sa, 0x21, 0x06, 0x07, 0x08]), extended_id=False))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')


		#Transmit single frame - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ta, 0x03, 0x04, 0x05, 0x06]))
		self.assertFalse(msg.is_extended_id)

		#Transmit single frame - Functional
		layer.reset()
		layer.send(b'\x04\x05\x06', functional)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ta, 0x03, 0x04, 0x05, 0x06]))
		self.assertFalse(msg.is_extended_id)

		# Transmit multiframe - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ta, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
		self.assertFalse(msg.is_extended_id)

		self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0, prefix=[sa]), extended_id=False))
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ta, 0x21, 0x09, 0x0A, 0x0B]))
		self.assertFalse(msg.is_extended_id)

	def test_29bits_extended(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		txid = 0x123
		rxid = 0x456
		sa = 0x55
		ta = 0xAA
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Extended_29bits, txid=txid, rxid=rxid, source_address=sa, target_address=ta)

		self.assertFalse(address.is_for_me(Message(rxid,  extended_id=True))) # No data
		self.assertFalse(address.is_for_me(Message(txid,  extended_id=True))) # No data, wrong id
		self.assertFalse(address.is_for_me(Message(rxid, data = bytearray([ta]),  extended_id=True))) # wrong id
		self.assertTrue(address.is_for_me(Message(rxid, data = bytearray([sa]),  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(rxid, data = bytearray([sa]),  extended_id=False)))
		self.assertFalse(address.is_for_me(Message(rxid+1, data = bytearray([sa]),  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(rxid, data = bytearray([sa+1]),  extended_id=True)))

		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, functional), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FIRST_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.CONSECUTIVE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FLOW_CONTROL, physical), txid)

	def test_29bits_extended_through_layer(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		txid = 0x123
		rxid = 0x456
		sa = 0x55
		ta = 0xAA
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Extended_29bits, txid=txid, rxid=rxid, source_address=sa, target_address=ta)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin':0, 'blocksize':0})

		# Receive Single frame - Physical / Functional
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([sa, 0x03, 0x01, 0x02, 0x03]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive multiframe - Physical
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([sa, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=True))
		layer.process()
		self.assert_sent_flow_control(prefix=[ta], stmin=0, blocksize=0)
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([sa, 0x21, 0x06, 0x07, 0x08]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')


		#Transmit single frame - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ta, 0x03, 0x04, 0x05, 0x06]))
		self.assertTrue(msg.is_extended_id)

		#Transmit single frame - Functional
		layer.reset()
		layer.send(b'\x04\x05\x06', functional)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ta, 0x03, 0x04, 0x05, 0x06]))
		self.assertTrue(msg.is_extended_id)

		# Transmit multiframe - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ta, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
		self.assertTrue(msg.is_extended_id)

		self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0, prefix=[sa]), extended_id=True))
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ta, 0x21, 0x09, 0x0A, 0x0B]))
		self.assertTrue(msg.is_extended_id)

	def test_11bits_mixed(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		txid = 0x123
		rxid = 0x456
		ae = 0x99
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Mixed_11bits, txid=txid, rxid=rxid, address_extension = ae)

		self.assertFalse(address.is_for_me(Message(rxid,  extended_id=False))) # No data
		self.assertFalse(address.is_for_me(Message(txid,  extended_id=False))) # No data, wrong id
		self.assertTrue(address.is_for_me(Message(rxid, data = bytearray([ae]),  extended_id=False)))
		self.assertFalse(address.is_for_me(Message(rxid, data = bytearray([ae]),  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(rxid+1, data = bytearray([ae]),  extended_id=False)))
		self.assertFalse(address.is_for_me(Message(rxid, data = bytearray([ae+1]),  extended_id=False)))

		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, functional), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FIRST_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.CONSECUTIVE_FRAME, physical), txid)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FLOW_CONTROL, physical), txid)

	def test_11bits_mixed_through_layer(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		txid = 0x123
		rxid = 0x456
		ae = 0x99
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Mixed_11bits, txid=txid, rxid=rxid, address_extension = ae)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin':0, 'blocksize':0})

		# Receive Single frame - Physical / Functional
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([ae, 0x03, 0x01, 0x02, 0x03]), extended_id=False))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive multiframe - Physical
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([ae, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=False))
		layer.process()
		self.assert_sent_flow_control(prefix=[ae], stmin=0, blocksize=0)
		self.simulate_rx_msg(Message(arbitration_id = rxid, data=bytearray([ae, 0x21, 0x06, 0x07, 0x08]), extended_id=False))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')


		#Transmit single frame - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
		self.assertFalse(msg.is_extended_id)

		#Transmit single frame - Functional
		layer.reset()
		layer.send(b'\x04\x05\x06', functional)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
		self.assertFalse(msg.is_extended_id)

		# Transmit multiframe - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ae, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
		self.assertFalse(msg.is_extended_id)

		self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0, prefix=[ae]), extended_id=False))
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid)
		self.assertEqual(msg.data, bytearray([ae, 0x21, 0x09, 0x0A, 0x0B]))
		self.assertFalse(msg.is_extended_id)

	def test_29bits_mixed(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		ta = 0x55
		sa = 0xAA
		ae = 0x99
		rxid_physical 	= 0x18CEAA55
		rxid_functional = 0x18CDAA55
		txid_physical 	= 0x18CE55AA
		txid_functional = 0x18CD55AA

		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Mixed_29bits, source_address=sa, target_address=ta, address_extension = ae)

		self.assertFalse(address.is_for_me(Message(rxid_physical,  	extended_id=True))) 	# No data
		self.assertFalse(address.is_for_me(Message(rxid_functional, extended_id=True))) 	# No data
		self.assertFalse(address.is_for_me(Message(txid_physical,  	extended_id=True))) 	# No data
		self.assertFalse(address.is_for_me(Message(txid_functional, extended_id=True)))		# No data

		self.assertTrue(address.is_for_me(Message(rxid_physical,  	data = bytearray([ae]),  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(rxid_physical,  	data = bytearray([ae]),  extended_id=False)))
		self.assertTrue(address.is_for_me(Message(rxid_functional,  data = bytearray([ae]),  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(rxid_functional,  data = bytearray([ae]),  extended_id=False)))
		self.assertFalse(address.is_for_me(Message(txid_physical, 	data = bytearray([ae]),  extended_id=True)))
		self.assertFalse(address.is_for_me(Message(txid_functional, data = bytearray([ae]),  extended_id=True)))

		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, physical), 		txid_physical)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.SINGLE_FRAME, functional), 	txid_functional)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FIRST_FRAME, physical), 		txid_physical)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.CONSECUTIVE_FRAME, physical), txid_physical)
		self.assertEqual(address.get_tx_arbitraton_id(isotp.protocol.PDU.Type.FLOW_CONTROL, physical), 		txid_physical)

	def test_29bits_mixed_through_layer(self):
		functional = isotp.protocol.TargetAddressType.Functional 
		physical = isotp.protocol.TargetAddressType.Physical 
		ta = 0x55
		sa = 0xAA
		ae = 0x99
		rxid_physical = 0x18CEAA55
		rxid_functional = 0x18CDAA55
		txid_physical = 0x18CE55AA
		txid_functional = 0x18CD55AA
		
		address = isotp.protocol.Address(isotp.protocol.AddressingMode.Mixed_29bits, source_address=sa, target_address=ta, address_extension = ae)
		layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin':0, 'blocksize':0})

		# Receive Single frame - Physical
		self.simulate_rx_msg(Message(arbitration_id = rxid_physical, data=bytearray([ae, 0x03, 0x01, 0x02, 0x03]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive Single frame - Functional
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid_functional, data=bytearray([ae, 0x03, 0x01, 0x02, 0x03]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03')

		# Receive multiframe - Physical
		layer.reset()
		self.simulate_rx_msg(Message(arbitration_id = rxid_physical, data=bytearray([ae, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=True))
		layer.process()
		self.assert_sent_flow_control(prefix=[ae], stmin=0, blocksize=0)
		self.simulate_rx_msg(Message(arbitration_id = rxid_physical, data=bytearray([ae, 0x21, 0x06, 0x07, 0x08]), extended_id=True))
		layer.process()
		frame = layer.recv()
		self.assertIsNotNone(frame)
		self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

		#Transmit single frame - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid_physical)
		self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
		self.assertTrue(msg.is_extended_id)

		#Transmit single frame - Functional
		layer.reset()
		layer.send(b'\x04\x05\x06', functional)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid_functional)
		self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
		self.assertTrue(msg.is_extended_id)

		# Transmit multiframe - Physical
		layer.reset()
		layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid_physical)
		self.assertEqual(msg.data, bytearray([ae, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
		self.assertTrue(msg.is_extended_id)

		self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0, prefix=[ae]), extended_id=True))
		layer.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, txid_physical)
		self.assertEqual(msg.data, bytearray([ae, 0x21, 0x09, 0x0A, 0x0B]))
		self.assertTrue(msg.is_extended_id)

# Here we try to test of user space stack against a CAN_ISOTP socket that will use the Linux Kernel module.
@unittest.skipIf(_ISOTP_SOCKET_POSSIBLE == False, 'Cannot test stack against IsoTP socket. %s' % _SOCKET_IMPOSSIBLE_REASON)
class TestStackAgainstSocket(ThreadableTest):
	
	def __init__(self, *args, **kwargs):
		ThreadableTest.__init__(self, *args, **kwargs)
		if not hasattr(self.__class__, '_next_id'):
			self.__class__._next_id=100

		self.stack_txid = self.__class__._next_id
		self.stack_rxid = self.__class__._next_id +1
		self.__class__._next_id += 2

		self.transmission_complete = False
		self.reception_complete = False
		self.socket_ready=False

	def make_tp_sock(self, stmin=0, bs=8, wftmax=0):
		socket = isotp.socket()
		socket.set_fc_opts(stmin=stmin, bs=bs, wftmax=wftmax)
		socket.bind(_interface_name, txid=self.stack_rxid, rxid=self.stack_txid)
		return socket
		
	def setUp(self):
		self.socket = self.make_tp_sock(stmin=0, bs=8, wftmax=0)

	def clientSetUp(self):
		self.bus = can.interface.Bus(_interface_name, bustype='socketcan')
		address = isotp.TransportLayer.Address(isotp.TransportLayer.AddressingMode.Normal_11bits, txid=self.TXID, rxid=self.RXID)
		self.stack = isotp.CanStack(bus=self.bus, address=address)

	def tearDown(self):
		self.socket.close()
		self.stack.reset()
		self.bus.shutdown()

	def process_stack_receive(self, timeout=1):
		t1 = time.time()
		self.reception_complete = False
		while time.time() - t1 < timeout:
			self.stack.process()
			if self.stack.available():
				break
			time.sleep(self.stack.sleep_time())
		self.reception_complete = True
		return self.stack.recv()

	def process_stack_send(self, timeout=1):
		self.transmission_complete = False
		t1 = time.time()
		while time.time() - t1 < timeout:
			self.stack.process()
			if not self.stack.transmitting():
				break
			time.sleep(self.stack.sleep_time())
		self.transmission_complete = True

	def wait_transmission_complete(self, timeout=1):
		t1 = time.time()
		while time.time() - t1 < timeout and self.transmission_complete == False:
			time.sleep(0.05)

	def wait_reception_complete(self, timeout=1):
		t1 = time.time()
		while time.time() - t1 < timeout and self.reception_complete == False:
			time.sleep(0.05)

	def wait_socket_ready(self, timeout=1):
		t1 = time.time()
		while time.time() - t1 < timeout and self.socket_ready == False:
			time.sleep(0.05)
		


	# ========= Test cases ======
	def test_receive(self):
		self.socket.send(b'a'*100)
		self.wait_reception_complete()

	def _test_receive(self):
		frame = self.process_stack_receive()
		self.assertEqual(frame, b'a'*100)

	def test_transmit(self):
		self.wait_transmission_complete(1)
		frame = self.socket.recv()
		self.assertEqual(frame, b'b'*100)

	def _test_transmit(self):
		self.stack.send(b'b'*100)
		self.process_stack_send()
		
	def test_transmit_long_stmin(self):
		self.socket.close()
		self.socket = self.make_tp_sock(stmin=100) # 100ms
		self.socket_ready=True
		self.wait_transmission_complete(5)
		frame = self.socket.recv()
		self.assertEqual(frame, b'b'*150)

	def _test_transmit_long_stmin(self):
		self.wait_socket_ready()
		expected_time = 150/7*0.1
		self.stack.send(b'b'*150)
		t1 = time.time()
		self.process_stack_send(timeout=2*expected_time)
		diff = time.time() - t1
		self.assertGreater(diff, expected_time)

	def test_receive_long_stmin(self):
		self.socket.send(b'a'*150)
		self.wait_reception_complete(timeout=5)

	def _test_receive_long_stmin(self):
		expected_time = 150/7*0.1
		t1 = time.time()
		self.stack.params.set('stmin', 100)
		frame = self.process_stack_receive(timeout=2*expected_time)
		self.assertEqual(frame, b'a'*150)
		diff = time.time() - t1
		self.assertGreater(diff, expected_time)
