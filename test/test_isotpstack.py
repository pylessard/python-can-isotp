import isotp
import queue
import os
import binascii
import time
import unittest
from .ThreadableTest import ThreadableTest
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


Message = isotp.stack.CanMessage

class testTimer(unittest.TestCase):
	def test_timer(self):
		timeout = 0.2
		t = isotp.stack.Timer(timeout=timeout)
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

class TestPDUDecoding(unittest.TestCase):

	def make_pdu(self, data):
		return isotp.stack.PDU(Message(data=bytearray(data)))

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
		self.assertEqual(frame.type, isotp.stack.PDU.Type.SINGLE_FRAME)
		self.assertEqual(frame.data, bytearray([0xAA]))
		self.assertEqual(frame.length, len(frame.data))

		with self.assertRaises(ValueError):
			self.make_pdu([0x02, 0x11])

		frame = self.make_pdu([0x02, 0x11, 0x22])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.SINGLE_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22]))
		self.assertEqual(frame.length, len(frame.data))

		frame = self.make_pdu([0x02, 0x11, 0x22, 0x33, 0x44])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.SINGLE_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22]))
		self.assertEqual(frame.length, len(frame.data))

		frame = self.make_pdu([0x07, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.SINGLE_FRAME)
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
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22]))
		self.assertEqual(frame.length, 2)

		frame = self.make_pdu([0x10, 0x02, 0x11, 0x22, 0x33])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22]))
		self.assertEqual(frame.length, 2)

		frame = self.make_pdu([0x10, 0x06, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66]))
		self.assertEqual(frame.length, 6)

		with self.assertRaises(ValueError):	# Missing data byte
			frame = self.make_pdu([0x10, 0x0A, 0x11, 0x22, 0x33, 0x44, 0x55])

		frame = self.make_pdu([0x10, 0x0A, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66]))
		self.assertEqual(frame.length, 0xA)

		frame = self.make_pdu([0x1A, 0xBC, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FIRST_FRAME)
		self.assertEqual(frame.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66]))
		self.assertEqual(frame.length, 0xABC)

	
	def test_decode_consecutive_frame(self):
		with self.assertRaises(ValueError):	# Empty payload
			self.make_pdu([])

		frame = self.make_pdu([0x20])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.CONSECUTIVE_FRAME)
		self.assertEqual(frame.data, bytearray([]))
		self.assertEqual(frame.seqnum, 0)

		frame = self.make_pdu([0x20, 0x11])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.CONSECUTIVE_FRAME)
		self.assertEqual(frame.data, bytearray([0x11]))
		self.assertEqual(frame.seqnum, 0)

		frame = self.make_pdu([0x2A, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.CONSECUTIVE_FRAME)
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
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FLOW_CONTROL)
		self.assertEqual(frame.flow_status, isotp.stack.PDU.FlowStatus.ContinueToSend)
		self.assertEqual(frame.blocksize, 0)
		self.assertEqual(frame.stmin, 0)
		self.assertEqual(frame.stmin_sec, 0)

		frame = self.make_pdu([0x31, 0x00, 0x00])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FLOW_CONTROL)
		self.assertEqual(frame.flow_status, isotp.stack.PDU.FlowStatus.Wait)
		self.assertEqual(frame.blocksize, 0)
		self.assertEqual(frame.stmin, 0)
		self.assertEqual(frame.stmin_sec, 0)

		frame = self.make_pdu([0x32, 0x00, 0x00])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FLOW_CONTROL)
		self.assertEqual(frame.flow_status, isotp.stack.PDU.FlowStatus.Overflow)
		self.assertEqual(frame.blocksize, 0)
		self.assertEqual(frame.stmin, 0)
		self.assertEqual(frame.stmin_sec, 0)

		for i in range(3, 0xF):	# Reserved Flow status
			with self.assertRaises(ValueError):
				frame = self.make_pdu([0x30 + i, 0x00, 0x00])

		frame = self.make_pdu([0x30, 0xFF, 0x00])
		self.assertEqual(frame.type, isotp.stack.PDU.Type.FLOW_CONTROL)
		self.assertEqual(frame.flow_status, isotp.stack.PDU.FlowStatus.ContinueToSend)
		self.assertEqual(frame.blocksize, 0xFF)
		self.assertEqual(frame.stmin, 0)
		self.assertEqual(frame.stmin_sec, 0)

		for i in range(0,0x7F):		# Millisecs
			frame = self.make_pdu([0x30, 0x00, i])
			self.assertEqual(frame.type, isotp.stack.PDU.Type.FLOW_CONTROL)
			self.assertEqual(frame.flow_status, isotp.stack.PDU.FlowStatus.ContinueToSend)
			self.assertEqual(frame.blocksize, 0)
			self.assertEqual(frame.stmin, i)
			self.assertEqual(frame.stmin_sec, i/1000)

		for i in range(0xF1, 0xF9):	# Microsecs
			frame = self.make_pdu([0x30, 0x00, i])
			self.assertEqual(frame.type, isotp.stack.PDU.Type.FLOW_CONTROL)
			self.assertEqual(frame.flow_status, isotp.stack.PDU.FlowStatus.ContinueToSend)
			self.assertEqual(frame.blocksize, 0)
			self.assertEqual(frame.stmin, i)
			self.assertEqual(frame.stmin_sec, (i - 0xF0)/10000)

		for i in range(0x80, 0xF1):		# Reserved StMin
			with self.assertRaises(ValueError):
				frame = self.make_pdu([0x30, 0x00, i])

		for i in range(0xFA, 0x100):	# Reserved StMin
			with self.assertRaises(ValueError):
				frame = self.make_pdu([0x30, 0x00, i])


class TestStack(unittest.TestCase):
	RXID = 0x456
	TXID = 0x123

	def error_handler(self, error):
		if error.__class__ not in self.error_triggered:
			self.error_triggered[error.__class__] = []

		self.error_triggered[error.__class__].append(error)


	def setUp(self):
		self.ll_rx_queue = queue.Queue()
		self.ll_tx_queue = queue.Queue()
		params = {
			'stmin' : 1,
			'blocksize' : 8,
			'squash_stmin_requirement' : False,
			'rx_flowcontrol_timeout'  : 1000,
			'rx_consecutive_frame_timeout' : 1000,
			'wftmax' : 0
		}
		self.stack = isotp.stack(txfn=self.stack_txfn, rxfn=self.stack_rxfn, txid=self.TXID, rxid=self.RXID, error_handler = self.error_handler, params = params)
		self.error_triggered = {}

	def stack_txfn(self, msg):
		if not self.ll_tx_queue.full():
			self.ll_tx_queue.put(msg)

	def stack_rxfn(self):
		if not self.ll_rx_queue.empty():
			return  self.ll_rx_queue.get()

	def simulate_rx(self, data, rxid=RXID):
		self.ll_rx_queue.put(Message(arbitration_id=rxid, data=bytearray(data)))

	def simulate_rx_flowcontrol(self, flow_status, stmin, blocksize):
		self.simulate_rx(data = [0x30 | (flow_status & 0xF), blocksize, stmin])

	def rx_isotp_frame(self):
		return self.stack.recv()

	def tx_isotp_frame(self, frame):
		self.stack.send(frame)

	def get_tx_can_msg(self):
		if not self.ll_tx_queue.empty():
			return self.ll_tx_queue.get()

	def make_payload(self, size, start_val=0):
		return [int(x%0x100) for x in range(start_val, start_val+size)]

	def assert_sent_flow_control(self, stmin, blocksize, padding_byte=None, extra_msg=''):
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg, 'Expected a Flow Control message, but none was sent.' + ' ' + extra_msg)
		data = bytearray([0x30, blocksize, stmin])
		if padding_byte is not None:
			data.extend(bytearray([padding_byte]*5))

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


	# ============= Testing starts here ============

	def test_receive_single_sf(self):
		self.simulate_rx(data = [0x05, 0x11, 0x22, 0x33, 0x44, 0x55])
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray([0x11, 0x22, 0x33, 0x44, 0x55]))

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
		self.assert_error_triggered(isotp.stack.WrongSequenceNumberError)

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
		self.assert_error_triggered(isotp.stack.ConsecutiveFrameTimeoutError)
		self.assert_error_triggered(isotp.stack.UnexpectedConsecutiveFrameError)

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
		self.assert_error_triggered(isotp.stack.ConsecutiveFrameTimeoutError)
		self.assert_error_triggered(isotp.stack.UnexpectedConsecutiveFrameError)

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
		self.assert_error_triggered(isotp.stack.ReceptionInterruptedWithFirstFrameError)

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
		self.assert_error_triggered(isotp.stack.ReceptionInterruptedWithSingleFrameError)

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
			self.assert_error_triggered(isotp.stack.InvalidCanDataError)
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
		self.assert_error_triggered(isotp.stack.FlowControlTimeoutError)

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
		self.assert_error_triggered(isotp.stack.FlowControlTimeoutError)

	def test_send_unexpected_flow_control(self):
		self.simulate_rx_flowcontrol(flow_status=0, stmin=100, blocksize=8)
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.assert_error_triggered(isotp.stack.UnexpectedFlowControlError)

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
		
		self.assert_error_triggered(isotp.stack.FlowControlTimeoutError)

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
		self.assert_error_triggered(isotp.stack.UnsuportedWaitFrameError)

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
		self.assert_error_triggered(isotp.stack.UnsuportedWaitFrameError)

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
		self.assert_error_triggered(isotp.stack.MaximumWaitFrameReachedError)
		self.assert_error_triggered(isotp.stack.UnexpectedFlowControlError)

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
		self.assert_error_triggered(isotp.stack.MaximumWaitFrameReachedError)
		self.assert_error_triggered(isotp.stack.UnexpectedFlowControlError)

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
	def create_stack(self, params):
		return isotp.stack(txfn=self.stack_txfn, rxfn=self.stack_rxfn, txid=self.TXID, rxid=self.RXID, params = params)

	def test_params_bad_values(self):
		params = {
			'stmin' : 1,
			'blocksize' : 8,
			'squash_stmin_requirement' : False,
			'rx_flowcontrol_timeout'  : 1000,
			'rx_consecutive_frame_timeout' : 1000
		}

		self.create_stack({}) # Empty params. Use default value
		self.create_stack(params)

		with self.assertRaises(ValueError):
			params['stmin'] = -1
			self.create_stack(params)

		with self.assertRaises(ValueError):
			params['stmin'] = 0x100
			self.create_stack(params)

		with self.assertRaises(ValueError):
			params['stmin'] = 'string'
			self.create_stack(params)
		params['stmin'] = 1


		with self.assertRaises(ValueError):
			params['blocksize'] = -1
			self.create_stack(params)

		with self.assertRaises(ValueError):
			params['blocksize'] = 0x100
			self.create_stack(params)

		with self.assertRaises(ValueError):
			params['blocksize'] = 'string'
			self.create_stack(params)
		params['blocksize'] = 8


		with self.assertRaises(ValueError):
			params['squash_stmin_requirement'] = 'string'
			self.create_stack(params)
		params['squash_stmin_requirement'] = False


		with self.assertRaises(ValueError):
			params['rx_flowcontrol_timeout'] = -1
			self.create_stack(params)

		with self.assertRaises(ValueError):
			params['rx_flowcontrol_timeout'] = 'string'
			self.create_stack(params)
		params['rx_flowcontrol_timeout'] = 1000


		with self.assertRaises(ValueError):
			params['rx_consecutive_frame_timeout'] = -1
			self.create_stack(params)

		with self.assertRaises(ValueError):
			params['rx_consecutive_frame_timeout'] = 'string'
			self.create_stack(params)
		params['rx_consecutive_frame_timeout'] = 1000


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

	def send(self, bus, msg):
		bus.send(can.Message(arbitration_id=msg.arbitration_id, data = msg.data, extended_id=msg.is_extended_id))

	def recv(self, bus):
		msg = bus.recv(0)
		if msg is not None:
			return self.stack.CanMessage(arbitration_id=msg.arbitration_id, data=msg.data, extended_id=msg.is_extended_id)		

	def make_tp_sock(self, stmin=0, bs=8, wftmax=0):
		socket = isotp.socket()
		socket.set_fc_opts(stmin=stmin, bs=bs, wftmax=wftmax)
		socket.bind(_interface_name, txid=self.stack_rxid, rxid=self.stack_txid)
		return socket
		
	def setUp(self):
		self.socket = self.make_tp_sock(stmin=0, bs=8, wftmax=0)

	def clientSetUp(self):
		self.bus = can.interface.Bus(_interface_name, bustype='socketcan')
		self.stack = isotp.stack(txid=self.stack_txid, rxid=self.stack_rxid, txfn=partial(self.send, self.bus), rxfn=partial(self.recv, self.bus))

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

	@unittest.skip('This test always fails because of lost messages. Issue seems deeper than this stack. Seems to be coming from the interface or isotp kernel module.')
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