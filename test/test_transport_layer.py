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


	def simulate_rx(self, data, rxid=RXID, dlc=None):
		self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray(data), dlc=dlc))

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

	def test_receive_single_sf_rxdl_16(self):
		self.stack.params.set('ll_data_length', 16)
		payload = self.make_payload(10)

		self.simulate_rx(data = [0x00, len(payload)] + payload, dlc=10)
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload))

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

	# Make sure we can receive multiple single frame
	def test_receive_multiple_sf_rxdl_16(self):
		self.stack.params.set('ll_data_length', 16)
		self.stack.process()
		self.stack.process()

		payload1 = self.make_payload(10)
		payload2 = self.make_payload(12, 100)

		self.simulate_rx(data = [0, len(payload1)] + payload1)
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload1))

		self.assertIsNone(self.rx_isotp_frame())
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())

		self.simulate_rx(data = [0, len(payload2)] + payload2)
		self.stack.process()
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload2))

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

	def test_receive_overflow_handling(self):
		self.stack.params.set('stmin', 0)
		self.stack.params.set('blocksize', 0)
		self.stack.params.set('max_frame_size', 32)

		payload = self.make_payload(33)
		self.simulate_rx(data = [0x10, 33] + payload[0:6])
		self.stack.process()
		self.assert_error_triggered(isotp.FrameTooLongError)
		self.assert_sent_flow_control(stmin=0, blocksize=0, flowstatus=isotp.protocol.PDU.FlowStatus.Overflow)
		self.simulate_rx(data = [0x21] + payload[6:10])
		self.stack.process()
		self.assert_error_triggered(isotp.UnexpectedConsecutiveFrameError)

		self.simulate_rx(data = [0x10, 32] + payload[0:6])
		self.stack.process()
		self.assert_sent_flow_control(stmin=0, blocksize=0, flowstatus=isotp.protocol.PDU.FlowStatus.ContinueToSend)

	def test_receive_overflow_handling_escape_sequence(self):
		self.stack.params.set('stmin', 0)
		self.stack.params.set('blocksize', 0)
		self.stack.params.set('max_frame_size', 32)

		payload = self.make_payload(33)
		self.simulate_rx(data = [0x10, 0, 0,0,0,33] + payload[0:2])
		self.stack.process()
		self.assert_error_triggered(isotp.FrameTooLongError)
		self.assert_sent_flow_control(stmin=0, blocksize=0, flowstatus=isotp.protocol.PDU.FlowStatus.Overflow)
		self.simulate_rx(data = [0x21] + payload[6:10])
		self.stack.process()
		self.assert_error_triggered(isotp.UnexpectedConsecutiveFrameError)

		self.simulate_rx(data = [0x10, 0,0,0,0,32] + payload[0:2])
		self.stack.process()
		self.assert_sent_flow_control(stmin=0, blocksize=0, flowstatus=isotp.protocol.PDU.FlowStatus.ContinueToSend)

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
		self.simulate_rx(data = [0x21] + payload[6:13])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x22] + payload[13:20])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x23] + payload[20:27])
		self.stack.process()
		self.assert_sent_flow_control(stmin=5, blocksize=3)
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x24] + payload[27:30])
		self.stack.process()		
		data = self.rx_isotp_frame()
		self.assertEqual(data, bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())

	def test_long_multiframe_blocksize_zero(self):
		payload_size = 30
		payload = self.make_payload(payload_size)
		self.stack.params.set('blocksize', 0)
		self.stack.params.set('stmin', 5)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:6])
		self.stack.process()
		self.assert_sent_flow_control(stmin=5, blocksize=0)
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x21] + payload[6:13])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x22] + payload[13:20])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x23] + payload[20:27])
		self.stack.process()
		self.assertIsNone(self.rx_isotp_frame())
		self.simulate_rx(data = [0x24] + payload[27:30])
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
		self.assert_error_triggered(isotp.WrongSequenceNumberError)

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
		self.assert_error_triggered(isotp.ConsecutiveFrameTimeoutError)
		self.assert_error_triggered(isotp.UnexpectedConsecutiveFrameError)

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
		self.assert_error_triggered(isotp.ConsecutiveFrameTimeoutError)
		self.assert_error_triggered(isotp.UnexpectedConsecutiveFrameError)

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
		self.assert_error_triggered(isotp.ReceptionInterruptedWithFirstFrameError)

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
		self.assert_error_triggered(isotp.ReceptionInterruptedWithSingleFrameError)

	def test_receive_4095_multiframe(self):
		payload_size = 4095
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x1F, 0xFF] + payload[0:6])
		n = 6
		seqnum = 1
		while n<=payload_size:
			self.simulate_rx(data = [0x20 | (seqnum & 0xF)] + payload[n:min(n+7, payload_size)])	
			self.stack.process()
			n += 7
			seqnum +=1
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())
	
	def test_receive_4096_multiframe(self):
		self.stack.params.set('max_frame_size', 5000)
		payload_size = 4096
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, 0x00, 0x00, 0x00, 0x10, 0x00] + payload[0:2])
		n = 2
		seqnum = 1
		while n<=payload_size:
			self.simulate_rx(data = [0x20 | (seqnum & 0xF)] + payload[n:min(n+7, payload_size)])	
			self.stack.process()
			n += 7
			seqnum +=1
		self.assertEqual(self.rx_isotp_frame(), bytearray(payload))
		self.assertIsNone(self.rx_isotp_frame())

	def test_receive_10000_multiframe(self):
		self.stack.params.set('max_frame_size', 11000)
		payload_size = 10000
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, 0x00, 0x00, 0x00, 0x27, 0x10] + payload[0:2])
		n = 2
		seqnum = 1
		while n<=payload_size:
			self.simulate_rx(data = [0x20 | (seqnum & 0xF)] + payload[n:min(n+7, payload_size)])	
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
		while n<=payload_size:
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
			self.assert_error_triggered(isotp.InvalidCanDataError)
			self.clear_errors()

	def test_receive_multiframe_rxdl_12bytes(self):
		self.stack.params.set('ll_data_length', 12)
		payload_size = 30
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:10])
		self.stack.process()
		self.simulate_rx(data = [0x21] + payload[10:21])
		self.simulate_rx(data = [0x22] + payload[21:30])
		self.stack.process()
		data = self.rx_isotp_frame()
		self.assertEqual(data, bytearray(payload))

	def test_receive_data_length_12_but_set_8_bytes(self):
		self.stack.params.set('ll_data_length', 8)
		payload_size = 30
		payload = self.make_payload(payload_size)
		self.simulate_rx(data = [0x10, payload_size] + payload[0:10])
		self.stack.process()
		self.simulate_rx(data = [0x21] + payload[10:21])
		self.simulate_rx(data = [0x22] + payload[21:30])
		self.stack.process()
		data = self.rx_isotp_frame()
		self.assertNotEqual(data, bytearray(payload))


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

	def test_padding_single_frame_dl_12_bytes(self):
		padding_byte = 0xAA
		self.stack.params.set('tx_padding', padding_byte)
		self.stack.params.set('ll_data_length', 12)
		expected_dlc = 9  # According to CAN FD. 12 btyes data requires DLC=9

		for i in range(1,11):
			payload = self.make_payload(i,i)
			self.assertIsNone(self.get_tx_can_msg())
			self.tx_isotp_frame(payload)
			self.stack.process()
			msg = self.get_tx_can_msg()
			self.assertEqual(msg.arbitration_id, self.TXID)
			self.assertEqual(msg.dlc, expected_dlc)
			if i <= 7: 	
				self.assertEqual(msg.data, bytearray([0x00 | i] + payload + [padding_byte] * (11-i)))
			else:
				self.assertEqual(msg.data, bytearray([0x00, i] + payload + [padding_byte] * (10-i)))

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

	def test_padding_multi_frame_dl_12_bytes(self):
		padding_byte = 0x55
		expected_dlc = 9  # According to CAN FD. 12 btyes data requires DLC=9
		self.stack.params.set('tx_padding', padding_byte)
		self.stack.params.set('ll_data_length', 12)
		payload = self.make_payload(15)
		self.assertIsNone(self.get_tx_can_msg())
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.arbitration_id, self.TXID)
		self.assertEqual(msg.dlc, expected_dlc)
		self.assertEqual(msg.data, bytearray([0x10, 15] + payload[:10]))
		self.assertIsNone(self.get_tx_can_msg())
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=8)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertIsNotNone(msg)
		self.assertEqual(msg.arbitration_id, self.TXID)
		self.assertEqual(msg.dlc, expected_dlc)
		self.assertEqual(msg.data, bytearray([0x21] + payload[10:15] + [padding_byte]*6))
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
		self.assert_error_triggered(isotp.FlowControlTimeoutError)

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
		self.assert_error_triggered(isotp.FlowControlTimeoutError)

	def test_send_unexpected_flow_control(self):
		self.simulate_rx_flowcontrol(flow_status=0, stmin=100, blocksize=8)
		self.stack.process()
		self.assertIsNone(self.get_tx_can_msg())
		self.assert_error_triggered(isotp.UnexpectedFlowControlError)

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
		
		self.assert_error_triggered(isotp.FlowControlTimeoutError)

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
		self.assert_error_triggered(isotp.UnsuportedWaitFrameError)

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
		self.assert_error_triggered(isotp.UnsuportedWaitFrameError)

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
		self.assert_error_triggered(isotp.MaximumWaitFrameReachedError)
		self.assert_error_triggered(isotp.UnexpectedFlowControlError)

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
		self.assert_error_triggered(isotp.MaximumWaitFrameReachedError)
		self.assert_error_triggered(isotp.UnexpectedFlowControlError)

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

	#Possible since 2016 version of ISO-15765-2
	def test_send_10000_bytes_payload(self):
		payload_size = 10000;
		payload = self.make_payload(payload_size)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 0x00, 0x00, 0x00, 0x27, 0x10] + payload[:2]))
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)

		seqnum = 1
		n=2
		self.stack.process()
		while True:
			msg = self.get_tx_can_msg()
			self.assertIsNotNone(msg)
			self.assertEqual(msg.data, bytearray([0x20 | seqnum] + payload[n:min(n+7, payload_size)]))
			n+=7
			seqnum = (seqnum+1) & 0xF

			if n > payload_size:
				break

	#Possible since 2016 version of ISO-15765-2
	def test_send_4096_bytes_payload(self):
		payload_size = 4096;
		payload = self.make_payload(payload_size)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 0x00, 0x00, 0x00, 0x10, 0x00] + payload[:2]))
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)

		seqnum = 1
		n=2
		self.stack.process()
		while True:
			msg = self.get_tx_can_msg()
			self.assertIsNotNone(msg)
			self.assertEqual(msg.data, bytearray([0x20 | seqnum] + payload[n:min(n+7, payload_size)]))
			n+=7
			seqnum = (seqnum+1) & 0xF

			if n > payload_size:
				break

	#Possible since 2016 version of ISO-15765-2
	def test_send_10000_bytes_payload_dl_20(self):
		txdl = 20
		self.stack.params.set('ll_data_length', txdl)
		payload_size = 10000;
		payload = self.make_payload(payload_size)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 0x00, 0x00, 0x00, 0x27, 0x10] + payload[:txdl-6]))
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)

		seqnum = 1
		n=txdl-6
		self.stack.process()
		while True:
			msg = self.get_tx_can_msg()
			self.assertIsNotNone(msg)
			self.assertEqual(msg.data, bytearray([0x20 | seqnum] + payload[n:min(n+txdl-1, payload_size)]))
			n+=txdl-1
			seqnum = (seqnum+1) & 0xF

			if n > payload_size:
				break

	def test_transmit_single_sf_txdl_12_bytes(self):
		self.stack.params.set('ll_data_length', 12)
		payload = self.make_payload(10)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x00, len(payload)] + payload))
		self.assertEqual(msg.dlc, len(payload) + 2 )

	def test_transmit_single_sf_txdl_12_bytes(self):
		self.stack.params.set('ll_data_length', 12)
		payload = self.make_payload(7)	# Message fits in 8 bytes, process like normal CAN message 
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x0 | len(payload)] + payload))
		self.assertEqual(msg.dlc, len(payload) +1 )

	def test_transmit_multiple_sf_txdl_12_bytes(self):
		self.stack.params.set('ll_data_length', 12)
		payload1 = self.make_payload(10)
		payload2 = self.make_payload(9)

		expected_dlc = 9  # According to CAN FD. 12 btyes data requires DLC=9
		
		self.tx_isotp_frame(payload1)
		self.tx_isotp_frame(payload2)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x00, len(payload1)] + payload1))
		self.assertEqual(msg.dlc, expected_dlc)

		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x00, len(payload2)] + payload2))
		self.assertEqual(msg.dlc, expected_dlc)

		self.assertIsNone(self.get_tx_can_msg())

	def test_transmit_sf_size_limit_canfd(self):
		txdl=16
		self.stack.params.set('ll_data_length', txdl)

		for i in range(1, txdl-2):
			payload = self.make_payload(i,i)
			self.tx_isotp_frame(payload)
			self.stack.process()
			msg = self.get_tx_can_msg()
			self.assertIsNotNone(msg, "i=%d"%i)
			self.assertEqual( (msg.data[0] & 0xF0) >> 4, 0, binascii.hexlify(msg.data))
			self.assertIsNone(self.get_tx_can_msg())

		self.tx_isotp_frame(self.make_payload(txdl-1))
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual( (msg.data[0] & 0xF0) >> 4, 1, binascii.hexlify(msg.data))

	def test_transmit_multiframe_txdl_12_bytes(self):
		self.stack.params.set('ll_data_length', 12)
		payload = self.make_payload(30)
		self.tx_isotp_frame(payload)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x10, 30] + payload[:10]))
		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)
		self.stack.process()
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x21] + payload[10:21]))
		msg = self.get_tx_can_msg()
		self.assertEqual(msg.data, bytearray([0x22] + payload[21:30]))

#	def test_transmit_multiframe_txdl_5_bytes(self):
#		self.stack.params.set('ll_data_length', 5)
#		payload = self.make_payload(15)
#		self.tx_isotp_frame(payload)
#		self.stack.process()
#		msg = self.get_tx_can_msg()
#		self.assertEqual(msg.data, bytearray([0x10, 15] + payload[:3]))
#		self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)
#		self.stack.process()
#		msg = self.get_tx_can_msg()
#		self.assertEqual(msg.data, bytearray([0x21] + payload[3:7]))
#		msg = self.get_tx_can_msg()
#		self.assertEqual(msg.data, bytearray([0x22] + payload[7:11]))
#		msg = self.get_tx_can_msg()
#		self.assertEqual(msg.data, bytearray([0x23] + payload[11:15]))


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
			'rx_consecutive_frame_timeout' : 1000,
			'll_data_length' : 8,
			'max_frame_size' : 4095
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

		with self.assertRaises(ValueError):
			params['ll_data_length'] = -1
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['ll_data_length'] = 'string'
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['ll_data_length'] = 2
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['ll_data_length'] = 10
			self.create_layer(params)
		params['ll_data_length'] = 8

		with self.assertRaises(ValueError):
			params['max_frame_size'] = -1
			self.create_layer(params)

		with self.assertRaises(ValueError):
			params['max_frame_size'] = 'string'
			self.create_layer(params)
		params['max_frame_size'] = 4095




