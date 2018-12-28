import unittest
import isotp
import time
from . import unittest_logging

Message = isotp.CanMessage

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
        with self.assertRaises(ValueError): # Empty payload
            self.make_pdu([])

        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x10])

        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x1F])

        with self.assertRaises(ValueError): #Missing data
            self.make_pdu([0x10, 0x02])

        with self.assertRaises(ValueError): # Missing data byte
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

        with self.assertRaises(ValueError): # Missing data byte
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
        with self.assertRaises(ValueError): # Empty payload
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
        with self.assertRaises(ValueError): # Empty payload
            self.make_pdu([])

        with self.assertRaises(ValueError): # incomplete
            self.make_pdu([0x30])

        with self.assertRaises(ValueError): # incomplete
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

        for i in range(3, 0xF): # Reserved Flow status
            with self.assertRaises(ValueError):
                frame = self.make_pdu([0x30 + i, 0x00, 0x00])

        frame = self.make_pdu([0x30, 0xFF, 0x00])
        self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
        self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
        self.assertEqual(frame.blocksize, 0xFF)
        self.assertEqual(frame.stmin, 0)
        self.assertEqual(frame.stmin_sec, 0)

        for i in range(0,0x7F):     # Millisecs
            frame = self.make_pdu([0x30, 0x00, i])
            self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
            self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
            self.assertEqual(frame.blocksize, 0)
            self.assertEqual(frame.stmin, i)
            self.assertEqual(frame.stmin_sec, i/1000)

        for i in range(0xF1, 0xF9): # Microsecs
            frame = self.make_pdu([0x30, 0x00, i])
            self.assertEqual(frame.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
            self.assertEqual(frame.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
            self.assertEqual(frame.blocksize, 0)
            self.assertEqual(frame.stmin, i)
            self.assertEqual(frame.stmin_sec, (i - 0xF0)/10000)

        for i in range(0x80, 0xF1):     # Reserved StMin
            with self.assertRaises(ValueError):
                frame = self.make_pdu([0x30, 0x00, i])

        for i in range(0xFA, 0x100):    # Reserved StMin
            with self.assertRaises(ValueError):
                frame = self.make_pdu([0x30, 0x00, i])