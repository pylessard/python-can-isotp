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

    def make_pdu(self, data, start_of_data=0):
        return isotp.protocol.PDU(Message(data=bytearray(data)),start_of_data=start_of_data)

    def make_payload(self, size, start_val=0):
        return [int(x%0x100) for x in range(start_val, start_val+size)]

    def test_decode_single_frame_no_escape_sequence(self):
        # Empty data
        with self.assertRaises(ValueError):
            self.make_pdu([])   

        # Single Frame, imcomplete escape sequence
        with self.assertRaises(ValueError):
            self.make_pdu([0])  

        prefix =[0x55, 0xAA]
        # Missing 1 byte of data for single frame without escape sequence
        for length in range(1, 0xF):  
            with self.assertRaises(ValueError):
                data = [length&0xF] + self.make_payload(length-1)
                self.make_pdu(data)

        for length in range(1, 0xF):  
            with self.assertRaises(ValueError):
                data = prefix + [length&0xF] + self.make_payload(length-len(prefix)-1)
                self.make_pdu(data, start_of_data=len(prefix))  # With prefix

        # Valid single frames without escape sequence
        for length in range(1, 0xF):
            payload = self.make_payload(length)
            data= [length&0xF] + payload
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, len(pdu.data))
            self.assertEqual(pdu.length, length)
            self.assertFalse(pdu.escape_sequence)
            self.assertEqual(pdu.can_dl, len(data))
            self.assertEqual(pdu.rx_dl, max(8,pdu.can_dl))

        for length in range(1, 0xF):
            payload = self.make_payload(length)
            data = prefix+[length&0xF] + payload
            pdu = self.make_pdu(data, start_of_data=len(prefix))    # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, len(pdu.data))
            self.assertEqual(pdu.length, length)
            self.assertFalse(pdu.escape_sequence)
            self.assertEqual(pdu.can_dl, len(data))
            self.assertEqual(pdu.rx_dl, max(8,pdu.can_dl))

        # Valid single frames without escape sequence and extra bytes that are ignored
        for length in range(1, 0xF):  
            payload = self.make_payload(length)
            data = [length&0xF] + payload + [0xAA]*10
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, len(pdu.data))
            self.assertEqual(pdu.length, length)
            self.assertFalse(pdu.escape_sequence)
            self.assertEqual(pdu.can_dl, len(data))
            self.assertEqual(pdu.rx_dl, max(8,pdu.can_dl))

        for length in range(1, 0xF):  
            payload = self.make_payload(length)
            data = prefix+[length&0xF] + payload+ [0xAA]*10
            pdu = self.make_pdu(data, start_of_data=len(prefix))    # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, len(pdu.data))
            self.assertEqual(pdu.length, length)
            self.assertFalse(pdu.escape_sequence)
            self.assertEqual(pdu.can_dl, len(data))
            self.assertEqual(pdu.rx_dl, max(8,pdu.can_dl))


    def test_decode_single_frame_escape_sequence(self):
         # Single Frame, length=0. Invalid
        with self.assertRaises(ValueError):
            self.make_pdu([0,0])  

         # Single Frame, length=0. Invalid even with data.
        with self.assertRaises(ValueError):
            self.make_pdu([0,0,0xAA])   

        prefix =[0x55, 0xAA]
        # Missing 1 byte of data for single frame with escape sequence
        for length in range(1, 0xFF):   # Up to 255 bytes. More than CAN can give, but that's ok.
            with self.assertRaises(ValueError):
                data = [0, length] + self.make_payload(length-1)
                self.make_pdu(data)

        for length in range(1, 0xFF):   # Up to 255 bytes. More than CAN can give, but that's ok.
            with self.assertRaises(ValueError):
                data = prefix + [0, length] + self.make_payload(length-1)
                self.make_pdu(data, start_of_data=len(prefix))  # With prefix

        # Valid single frames without escape sequence
        for length in range(1, 0xFF):  
            payload = self.make_payload(length)
            data = [0, length] + payload
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, len(pdu.data))
            self.assertEqual(pdu.length, length)
            self.assertEqual(pdu.can_dl, len(data))
            self.assertEqual(pdu.rx_dl, max(8,pdu.can_dl))

        for length in range(1, 0xFF):  
            payload = self.make_payload(length)
            data = prefix + [0, length] + payload
            pdu = self.make_pdu(data, start_of_data=len(prefix))    # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, len(pdu.data))
            self.assertEqual(pdu.length, length)
            self.assertTrue(pdu.escape_sequence)
            self.assertEqual(pdu.can_dl, len(data))
            self.assertEqual(pdu.rx_dl, max(8,pdu.can_dl))

        # Valid single frames without escape sequence and extra bytes that are ignored
        for length in range(1, 0xFF):  
            payload = self.make_payload(length)
            data = [0, length] + payload + [0xAA]*10
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, len(pdu.data))
            self.assertEqual(pdu.length, length)
            self.assertTrue(pdu.escape_sequence)
            self.assertEqual(pdu.can_dl, len(data))
            self.assertEqual(pdu.rx_dl, max(8,pdu.can_dl))

        for length in range(1, 0xFF):  
            payload = self.make_payload(length)
            data = prefix + [0, length] + payload + [0xAA]*10
            pdu = self.make_pdu(data, start_of_data=len(prefix))    # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.SINGLE_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, len(pdu.data))
            self.assertEqual(pdu.length, length)
            self.assertTrue(pdu.escape_sequence)
            self.assertEqual(pdu.can_dl, len(data))
            self.assertEqual(pdu.rx_dl, max(8,pdu.can_dl))

    def test_decode_first_frame_no_escape_sequence(self):
        with self.assertRaises(ValueError): # Empty payload
            self.make_pdu([])

        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x10])

        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x1F])

        pdu = self.make_pdu([0x10, 0x02])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
        self.assertEqual(pdu.data, bytearray())
        self.assertEqual(pdu.length, 2)

        pdu = self.make_pdu([0x10, 0x02, 0x11])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
        self.assertEqual(pdu.data, bytearray([0x11]))
        self.assertEqual(pdu.length, 2)

        prefix =[0x55, 0xAA]

        # Data fits in single First pdu. Shouldn't happen, but acceptable.
        for length in range(1, 0x1FF):  
            payload = self.make_payload(length)
            data = [0x10 | (length >> 8)&0xF, length&0xFF] + payload
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, length)

        for length in range(1, 0x1FF):  
            payload = self.make_payload(length)
            data = prefix + [0x10 | (length >> 8)&0xF, length&0xFF] + payload
            pdu = self.make_pdu(data, start_of_data=len(prefix))        # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, length)


        # Data doesn't fits in first pdu. Normal use case.
        for length in range(10, 0x1FF):  
            payload = self.make_payload(length)
            data = [0x10 | (length >> 8)&0xF, length&0xFF] + payload[:5]
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload[:5]))
            self.assertEqual(pdu.length, length)

        for length in range(10, 0x1FF):  
            payload = self.make_payload(length)
            data = prefix + [0x10 | (length >> 8)&0xF, length&0xFF] + payload[:5]
            pdu = self.make_pdu(data, start_of_data=len(prefix))        # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload[:5]))
            self.assertEqual(pdu.length, length)


        # Data fits in single First Frame + padding. Shouldn't happen, but acceptable.
        padding = [0xAA] * 10
        for length in range(1, 0x1FF):  
            payload = self.make_payload(length)
            data = [0x10 | (length >> 8)&0xF, length&0xFF] + payload + padding
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, length)

        for length in range(1, 0x1FF):  
            payload = self.make_payload(length)
            data = prefix + [0x10 | (length >> 8)&0xF, length&0xFF] + payload + padding
            pdu = self.make_pdu(data, start_of_data=len(prefix))        # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, length)

    def test_decode_first_frame_with_escape_sequence(self):
        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x10, 0x00])

        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x10, 0x00, 0xAA])

        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x10, 0x00, 0xAA, 0xBB])

        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x10, 0x00, 0xAA, 0xBB, 0xCC])

        with self.assertRaises(ValueError): # Incomplete length
            self.make_pdu([0x10, 0x10, 0x00, 0xAA, 0xBB, 0xCC], start_of_data=1)

        # No data in first pdu. Uncommon but possible.
        pdu = self.make_pdu([0x10, 0x00, 0xAA, 0xBB, 0xCC, 0xDD])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
        self.assertEqual(pdu.data, bytearray())
        self.assertEqual(pdu.length, 0xAABBCCDD)

        # No data in first pdu. Uncommon but possible.
        pdu = self.make_pdu([0xAA, 0xAA, 0x10, 0x00, 0xAA, 0xBB, 0xCC, 0xDD], start_of_data=2)  # With prefix
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
        self.assertEqual(pdu.data, bytearray())
        self.assertEqual(pdu.length, 0xAABBCCDD)

        pdu = self.make_pdu([0x10, 0x00, 0xAA, 0xBB, 0xCC, 0xDD, 0x11, 0x22])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
        self.assertEqual(pdu.data, bytearray([0x11, 0x22]))
        self.assertEqual(pdu.length, 0xAABBCCDD)

        pdu = self.make_pdu([0xAA, 0x10, 0x00, 0xAA, 0xBB, 0xCC, 0xDD, 0x11, 0x22, 0x33, 0x44], start_of_data=1)
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
        self.assertEqual(pdu.data, bytearray([0x11, 0x22, 0x33, 0x44]))
        self.assertEqual(pdu.length, 0xAABBCCDD)


        prefix =[0x55, 0xAA]

        # Data fits in single First pdu. Shouldn't happen, but acceptable.
        for length in range(1, 0x1FF):  
            len_data = [(length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, (length >> 0) & 0xFF]
            payload = self.make_payload(length)
            data = [0x10, 0x00] + len_data + payload
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, length)

        for length in range(1, 0x1FF):  
            len_data = [(length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, (length >> 0) & 0xFF]
            payload = self.make_payload(length)
            data = prefix + [0x10, 0x00] + len_data + payload
            pdu = self.make_pdu(data, start_of_data=len(prefix))    # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, length)

        # Data doesn't fits in first pdu. Normal use case.
        for length in range(10, 0x1FF):  
            payload = self.make_payload(length)
            len_data = [(length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, (length >> 0) & 0xFF]
            data = [0x10, 0x00] + len_data + payload[:5]
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload[:5]))
            self.assertEqual(pdu.length, length)

        for length in range(10, 0x1FF):  
            payload = self.make_payload(length)
            len_data = [(length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, (length >> 0) & 0xFF]
            data = prefix + [0x10, 0x00] + len_data + payload[:5]
            pdu = self.make_pdu(data, start_of_data=len(prefix))        # With prefix
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload[:5]))
            self.assertEqual(pdu.length, length)

        # Data fits in single First Frame + padding. Shouldn't happen, but acceptable.
        padding = [0xAA] * 10
        for length in range(1, 0x1FF):  
            payload = self.make_payload(length)
            len_data = [(length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, (length >> 0) & 0xFF]
            data = [0x10, 0x00] + len_data + payload + padding
            pdu = self.make_pdu(data)
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, length)

        for length in range(1, 0x1FF):  
            payload = self.make_payload(length)
            len_data = [(length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, (length >> 0) & 0xFF]
            data = prefix + [0x10, 0x00] + len_data + payload + padding
            pdu = self.make_pdu(data, start_of_data=len(prefix))
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FIRST_FRAME)
            self.assertEqual(pdu.data, bytearray(payload))
            self.assertEqual(pdu.length, length)


    def test_decode_consecutive_frame(self):
        with self.assertRaises(ValueError): # Empty payload
            self.make_pdu([])

        pdu = self.make_pdu([0x20])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.CONSECUTIVE_FRAME)
        self.assertEqual(pdu.data, bytearray([]))
        self.assertEqual(pdu.seqnum, 0)

        pdu = self.make_pdu([0x20, 0x11])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.CONSECUTIVE_FRAME)
        self.assertEqual(pdu.data, bytearray([0x11]))
        self.assertEqual(pdu.seqnum, 0)

        pdu = self.make_pdu([0x2A, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.CONSECUTIVE_FRAME)
        self.assertEqual(pdu.data, bytearray([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77]))
        self.assertEqual(pdu.seqnum, 0xA)


    def test_decode_flow_control(self):
        with self.assertRaises(ValueError): # Empty payload
            self.make_pdu([])

        with self.assertRaises(ValueError): # incomplete
            self.make_pdu([0x30])

        with self.assertRaises(ValueError): # incomplete
            self.make_pdu([0x30, 0x00])

        pdu = self.make_pdu([0x30, 0x00, 0x00])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
        self.assertEqual(pdu.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
        self.assertEqual(pdu.blocksize, 0)
        self.assertEqual(pdu.stmin, 0)
        self.assertEqual(pdu.stmin_sec, 0)

        pdu = self.make_pdu([0x31, 0x00, 0x00])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
        self.assertEqual(pdu.flow_status, isotp.protocol.PDU.FlowStatus.Wait)
        self.assertEqual(pdu.blocksize, 0)
        self.assertEqual(pdu.stmin, 0)
        self.assertEqual(pdu.stmin_sec, 0)

        pdu = self.make_pdu([0x32, 0x00, 0x00])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
        self.assertEqual(pdu.flow_status, isotp.protocol.PDU.FlowStatus.Overflow)
        self.assertEqual(pdu.blocksize, 0)
        self.assertEqual(pdu.stmin, 0)
        self.assertEqual(pdu.stmin_sec, 0)

        pdu = self.make_pdu([0xFF, 0xFF, 0x32, 0x01, 0x01], start_of_data=2)
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
        self.assertEqual(pdu.flow_status, isotp.protocol.PDU.FlowStatus.Overflow)
        self.assertEqual(pdu.blocksize, 1)
        self.assertEqual(pdu.stmin, 1)
        self.assertEqual(pdu.stmin_sec, 1/1000)

        for i in range(3, 0xF): # Reserved Flow status
            with self.assertRaises(ValueError):
                pdu = self.make_pdu([0x30 + i, 0x00, 0x00])

        pdu = self.make_pdu([0x30, 0xFF, 0x00])
        self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
        self.assertEqual(pdu.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
        self.assertEqual(pdu.blocksize, 0xFF)
        self.assertEqual(pdu.stmin, 0)
        self.assertEqual(pdu.stmin_sec, 0)

        for i in range(0,0x7F):     # Millisecs
            pdu = self.make_pdu([0x30, 0x00, i])
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
            self.assertEqual(pdu.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
            self.assertEqual(pdu.blocksize, 0)
            self.assertEqual(pdu.stmin, i)
            self.assertEqual(pdu.stmin_sec, i/1000)

        for i in range(0xF1, 0xF9): # Microsecs
            pdu = self.make_pdu([0x30, 0x00, i])
            self.assertEqual(pdu.type, isotp.protocol.PDU.Type.FLOW_CONTROL)
            self.assertEqual(pdu.flow_status, isotp.protocol.PDU.FlowStatus.ContinueToSend)
            self.assertEqual(pdu.blocksize, 0)
            self.assertEqual(pdu.stmin, i)
            self.assertEqual(pdu.stmin_sec, (i - 0xF0)/10000)

        for i in range(0x80, 0xF1):     # Reserved StMin
            with self.assertRaises(ValueError):
                pdu = self.make_pdu([0x30, 0x00, i])

        for i in range(0xFA, 0x100):    # Reserved StMin
            with self.assertRaises(ValueError):
                pdu = self.make_pdu([0x30, 0x00, i])
