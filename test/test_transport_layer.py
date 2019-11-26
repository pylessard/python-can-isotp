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
                'wftmax' : 0,
                'tx_data_length' : 8
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
        self.stack.params.set('tx_data_length', 8)
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
        self.assertIsNone(self.get_tx_can_msg()) # Do not send flow control
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

    # CAN FD

    def test_receive_can_fd_single_frame_12bytes_no_escape_sequence(self):
        payload = self.make_payload(11)
        self.simulate_rx([0x0B] + payload)
        self.stack.process()
        self.assert_error_triggered(isotp.MissingEscapeSequenceError)
        self.assertIsNone(self.rx_isotp_frame())

    def test_receive_can_fd_single_frame_12bytes_escape_sequence(self):
        payload = self.make_payload(10)
        self.simulate_rx([0x00, 0x0A] + payload)
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    def test_receive_can_fd_single_frame_16bytes_no_escape_sequence(self):
        payload = self.make_payload(5)
        self.simulate_rx([0x05] + payload + [0xCC]*10)
        self.stack.process()
        self.assert_error_triggered(isotp.MissingEscapeSequenceError)
        self.assertIsNone(self.rx_isotp_frame())

    def test_receive_can_fd_single_frame_16bytes_escape_sequence(self):
        payload = self.make_payload(14)
        self.simulate_rx([0x00, 0x0E] + payload)
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    def test_receive_can_fd_single_frame_48_bytes_escape_sequence(self):
        payload = self.make_payload(46)
        self.simulate_rx([0x00, 46] + payload)
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    def test_receive_can_fd_single_frame_64_bytes_escape_sequence(self):
        payload = self.make_payload(62)
        self.simulate_rx([0x00, 62] + payload)
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    def test_receive_can_fd_single_frame_64_bytes_padding(self):
        payload = self.make_payload(60)
        self.simulate_rx([0x00, 60] + payload + [0xAA, 0xBB])
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    def test_receive_can_fd_single_frame_64_bytes_padding(self):
        payload = self.make_payload(60)
        self.simulate_rx([0x00, 60] + payload + [0xAA, 0xBB])
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    def test_receive_can_fd_multiframe_12_bytes(self):
        self.stack.params.set('stmin', 5)
        self.stack.params.set('blocksize', 4)
        payload = self.make_payload(37)
        self.simulate_rx([0x10, 37] + payload[0:10])
        self.stack.process()
        self.assert_sent_flow_control(stmin=5, blocksize=4)
        self.simulate_rx([0x21] + payload[10:21])
        self.simulate_rx([0x22] + payload[21:32])
        self.simulate_rx([0x23] + payload[32:37])
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    def test_receive_can_fd_multiframe_32_bytes(self):
        self.stack.params.set('stmin', 5)
        self.stack.params.set('blocksize', 4)
        payload = self.make_payload(100)
        self.simulate_rx([0x10, 100] + payload[0:30])
        self.stack.process()
        self.assert_sent_flow_control(stmin=5, blocksize=4)
        self.simulate_rx([0x21] + payload[30:61])
        self.simulate_rx([0x22] + payload[61:92])
        self.simulate_rx([0x23] + payload[92:100] + [0xCC]*23)
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    def test_receive_can_fd_multiframe_64_bytes_escape_sequence(self):
        self.stack.params.set('stmin', 5)
        self.stack.params.set('blocksize', 2)
        payload = self.make_payload(0x120)
        self.simulate_rx([0x10, 0x00, 0x00, 0x00, 0x01, 0x20 ] + payload[0:58])
        self.stack.process()
        self.assert_sent_flow_control(stmin=5, blocksize=2)
        self.simulate_rx([0x21] + payload[58:121])
        self.simulate_rx([0x22] + payload[121:184])
        self.stack.process()
        self.assert_sent_flow_control(stmin=5, blocksize=2)
        self.simulate_rx([0x23] + payload[184:247] )
        self.simulate_rx([0x24] + payload[247:288] + [0xCC]*6 )
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, bytearray(payload))

    #ISO-15765-2[2016] Specify that a changing rx_dl shall be ignored
    def test_receive_can_fd_ignore_changing_rxdl(self):
        self.stack.params.set('stmin', 5)
        self.stack.params.set('blocksize', 4)
        payload = self.make_payload(100)
        self.simulate_rx([0x10, 100] + payload[0:30])	# rx_dl is implicitly 32
        self.stack.process()
        self.assert_sent_flow_control(stmin=5, blocksize=4)
        self.simulate_rx([0x21] + payload[30:61])	#32
        self.simulate_rx([0x22] + payload[61:80])	# Ooops can_dl = 20. Should be 32
        self.stack.process()
        self.assert_error_triggered(isotp.ChangingInvalidRXDLError)
        self.simulate_rx([0x23] + payload[80:100] + [0xCC]*11)
        self.stack.process()
        self.assert_error_triggered(isotp.WrongSequenceNumberError)
        self.stack.process()
        frame = self.rx_isotp_frame()
        self.assertIsNone(frame)

    def test_receive_first_frame_rxdl_too_small_but_ok(self):
        self.simulate_rx([0x10, 20, 1,2,3,4,5])	# Missing one byte to get a 8 bytes payload. OK according to standard.
        self.stack.process()
        self.assert_no_error_triggered()


    def test_receive_first_frame_rxdl_too_small(self):
        self.stack.params.set('tx_data_length', 12)
        self.simulate_rx([0x10, 20, 1,2,3,4,5,6,7,8,9])	# Missing one byte to get a 12 bytes payload. Incomplete message, must be ignored.
        self.stack.process()
        self.assert_error_triggered(isotp.InvalidCanFdFirstFrameRXDL)
        self.assertIsNone(self.get_tx_can_msg())




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
        self.stack.params.set('tx_data_length', 8)
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
        self.stack.params.set('tx_data_length', 8)
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

    def test_send_respect_overflow(self):
        payload = self.make_payload(0x30)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertEqual(msg.data, bytearray([0x10, 0x30] + payload[:6]))
        self.assertIsNone(self.get_tx_can_msg())
        self.stack.process()
        self.assertIsNone(self.get_tx_can_msg())
        self.simulate_rx_flowcontrol(flow_status=2, stmin=0, blocksize=8)   # Overflow
        self.stack.process()
        self.assert_error_triggered(isotp.OverflowError)
        self.assertIsNone(self.get_tx_can_msg()) 

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
        self.stack.params.set('blocksize', 0)
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
        self.assertEqual(msg.dlc, len(msg.data))
        self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)

        seqnum = 1
        n=2
        self.stack.process()
        while True:
            msg = self.get_tx_can_msg()
            self.assertIsNotNone(msg)
            self.assertEqual(msg.data, bytearray([0x20 | seqnum] + payload[n:min(n+7, payload_size)]))
            self.assertEqual(msg.dlc, len(msg.data))
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
        self.assertEqual(msg.dlc, len(msg.data))
        self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)

        seqnum = 1
        n=2
        self.stack.process()
        while True:
            msg = self.get_tx_can_msg()
            self.assertIsNotNone(msg)
            self.assertEqual(msg.data, bytearray([0x20 | seqnum] + payload[n:min(n+7, payload_size)]))
            self.assertEqual(msg.dlc, len(msg.data))
            n+=7
            seqnum = (seqnum+1) & 0xF

            if n > payload_size:
                break

    # CAN FD
    # Make sure a single frame with length > 8 uses escape sequence
    def test_transmit_single_frame_txdl_12_bytes(self):
        self.stack.params.set('tx_data_length', 12)
        payload = self.make_payload(10)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertEqual(msg.data, bytearray([0x00, len(payload)] + payload))
        self.assertEqual(msg.dlc, 9 )

    def test_transmit_single_frame_txdl_12_bytes_default_padding(self):
        self.stack.params.set('tx_data_length', 12)
        payload = self.make_payload(9)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertEqual(msg.data, bytearray([0x00, len(payload)] + payload + [0xCC] ))	# Default padding byte
        self.assertEqual(msg.dlc, 9 )

    def test_transmit_single_frame_txdl_16_bytes_padding(self):
        self.stack.params.set('tx_data_length', 16)
        self.stack.params.set('tx_padding', 0xAA)
        payload = self.make_payload(10)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertEqual(msg.data, bytearray([0x0, len(payload)] + payload + [0xAA] * 4))	
        self.assertEqual(msg.dlc, 10 )

    def test_transmit_single_frame_txdl_64_bytes_default_padding(self):
        self.stack.params.set('tx_data_length', 64)
        payload = self.make_payload(55)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertEqual(msg.data, bytearray([0x00, len(payload)] + payload + [0xCC] * (64-len(payload)-2)))	
        self.assertEqual(msg.dlc, 15 )

    def test_can_fd_singleframe_tx_dl(self):
        tx_dl_list = [8,12,16,20,24,32,48,64]
        dlc_map = {4:4, 5:5, 6:6, 7:7, 8:8, 12:9, 16:10, 20:11, 24:12, 32:13, 48:14, 64:15}
        for tx_dl in tx_dl_list:
            error_details = "tx_dl = %d" % tx_dl
            self.stack.params.set('tx_data_length', tx_dl)
            escape_sequence = False if tx_dl == 8 else True
            prefix_length = 2 if escape_sequence else 1
            payload = self.make_payload(tx_dl-prefix_length)
            prefix = [0x00, len(payload)] if escape_sequence else [0x00 | len(payload)]
            self.tx_isotp_frame(payload)
            self.stack.process()
            msg = self.get_tx_can_msg()
            self.assertEqual(msg.data, bytearray(prefix+payload), error_details)
            self.assertEqual(msg.dlc,  dlc_map[tx_dl], error_details)

    def test_transmit_is_fd_property(self):
        self.stack.params.set('can_fd', True)
        payload = self.make_payload(5)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertTrue(msg.is_fd)	

        self.stack.params.set('can_fd', False)
        payload = self.make_payload(5)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertFalse(msg.is_fd)	

    # In this test we send a CAN FD multiframe without specifying tx_data_length so the stack decide the message size and takes the most efficent choice.
    def _test_send_can_fd_multiframe_N_bytes_payload_no_txd(self, payload_size, tx_dl):
        self.stack.params.set('tx_data_length', tx_dl)

        error_detail = "Payload size = %d" % payload_size 	# We append the siz eof the payload to error message for debug purpose.

        payload = self.make_payload(payload_size)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()


        if payload_size > 0xFFF:	# Escape sequence needed
            len_bytes = [(payload_size >> 24)&0xFF, (payload_size >> 16)&0xFF, (payload_size >> 8)&0xFF, (payload_size >> 0)&0xFF]
            data = bytearray([0x10, 0x00] + len_bytes + payload[:tx_dl-6])
            n=tx_dl-6
        else:						# Escape seuqnece not needed
            data = bytearray([0x10 | (payload_size >> 8) & 0xFF, payload_size & 0xFF] + payload[:tx_dl-2])
            n = tx_dl-2
        self.assertEqual(msg.data, data, error_detail)
        self.assertEqual(msg.dlc, 15, error_detail)
        self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)

        # Start sending Consecutive Frames
        seqnum = 1
        self.stack.process()
        while True:
            msg = self.get_tx_can_msg()
            self.assertIsNotNone(msg, error_detail)
            if n+tx_dl-1 > payload_size:
                last_msg_size = self.nearest_can_fd_size(payload_size-n+1)	# The target msg.data size
                dlc = self.get_canfd_dlc(last_msg_size)
                data = bytearray([0x20 | seqnum] + payload[n:payload_size] + [0xCC] * (last_msg_size +n -payload_size-1) )
                n+= (payload_size-n)
            else:
                data = bytearray([0x20 | seqnum] + payload[n:n+tx_dl-1])
                n+=tx_dl-1
                dlc = self.get_canfd_dlc(tx_dl)
            self.assertEqual(msg.data,  data, error_detail)
            self.assertIn(len(msg.data), [1,2,3,4,5,6,7,8,12,16,20,24,32,48,64], error_detail)	# Double check data size
            self.assertEqual(msg.dlc, dlc, error_detail)
            seqnum = (seqnum+1) & 0xF

            if n >= payload_size:
                break

    def test_send_10000_bytes_payload_no_txdl_can_fd(self):
        self._test_send_can_fd_multiframe_N_bytes_payload_no_txd(10000, 64)

    # Give payload size that make sure that the last can message is next to DLC edge (8,12,16,20,24,32,48,64)
    def test_canfd_multiframe_boundary_txdl_64(self):
        payload_sizes = [63,64,65,123,124,125,126,134,135,136,137, 140,141, 144,145, 148,149, 156,157, 173,174, 188, 189, 0x7ff+1, 0x7ff+31, 0x7ff+32]
        for size in payload_sizes:
            self._test_send_can_fd_multiframe_N_bytes_payload_no_txd(size, 64)


    def test_send_can_fd_multiframe_txdl_32(self):
        self.stack.params.set('tx_data_length', 32)
        payload = self.make_payload(100)
        self.tx_isotp_frame(payload)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.data, bytearray([0x10, 100] + payload[0:30]))
        self.simulate_rx_flowcontrol(flow_status=0, stmin=0, blocksize=0)
        self.stack.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.data, bytearray([0x21] + payload[30:61]))
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.data, bytearray([0x22] + payload[61:92]))
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.data, bytearray([0x23] + payload[92:100] + [0xCC]*3))

        self.assertIsNone(self.get_tx_can_msg())
        self.stack.process()
        self.assertIsNone(self.get_tx_can_msg())		

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
                'tx_data_length' : 8,
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
            params['tx_data_length'] = -1
            self.create_layer(params)

        with self.assertRaises(ValueError):
            params['tx_data_length'] = 0x100
            self.create_layer(params)

        with self.assertRaises(ValueError):
            params['tx_data_length'] = 'string'
            self.create_layer(params)

        with self.assertRaises(ValueError):
            params['tx_data_length'] = None
            self.create_layer(params)

        with self.assertRaises(ValueError):
            params['tx_data_length'] = 7
            self.create_layer(params)

        with self.assertRaises(ValueError):
            params['tx_data_length'] = 9
            self.create_layer(params)

        tx_dls = [8,12,16,20,24,32,48,64]
        for tx_dl in tx_dls:
            params['tx_data_length'] = tx_dl
            self.create_layer(params)
            with self.assertRaises(ValueError):
                params['tx_data_length'] = tx_dl-1
                self.create_layer(params)

        params['tx_data_length'] = 8

        with self.assertRaises(ValueError):
            params['max_frame_size'] = -1
            self.create_layer(params)

        with self.assertRaises(ValueError):
            params['max_frame_size'] = 'string'
            self.create_layer(params)
        params['max_frame_size'] = 4095
