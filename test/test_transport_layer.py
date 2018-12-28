import isotp
import queue
import os
import binascii
import time
import unittest
from functools import partial
import isotp
from . import unittest_logging
from .TransportLayerBaseTest import TransportLayerBaseTest
Message = isotp.CanMessage


# Check the behaviour of the transport layer. Sequenece of CAN frames, timings, etc.
class TestTransportLayer(TransportLayerBaseTest):
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
		address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.TXID, rxid=self.RXID)
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
		address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.TXID, rxid=self.RXID)
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


