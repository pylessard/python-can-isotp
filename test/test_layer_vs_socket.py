import unittest
import time
import isotp
from test.ThreadableTest import ThreadableTest
from . import unittest_logging
from . import tools
import math


@unittest.skipIf(tools.check_isotp_socket_possible() == False, 'Cannot test stack against IsoTP socket. %s' % tools.isotp_socket_impossible_reason())
class TestLayerAgainstSocket(ThreadableTest):
    
    def __init__(self, *args, **kwargs):
        ThreadableTest.__init__(self, *args, **kwargs)
        if not hasattr(self.__class__, '_next_id'):
            self.__class__._next_id=1

        (self.stack_txid, self.stack_rxid) = tools.get_next_can_id_pair()

        self.transmission_complete = False
        self.reception_complete = False
        self.socket_ready=False

        global can
        import can

    def setUp(self):
        self.socket_list = []

    def make_socket(self, *args, **kwargs):
        s = isotp.socket(*args, **kwargs)
        self.socket_list.append(s)
        return s

    def clientSetUp(self):
        self.bus = can.interface.Bus(tools.get_test_interface(), bustype='socketcan')
        address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.stack_txid, rxid=self.stack_rxid)
        self.stack = isotp.CanStack(bus=self.bus, address=address)

    def tearDown(self):
        for socket in self.socket_list:
            socket.close()
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
        s = self.make_socket()
        s.bind(tools.get_test_interface(), txid=self.stack_rxid, rxid=self.stack_txid)
        self.socket_ready = True
        s.send(b'a'*100)
        self.wait_reception_complete()

    def _test_receive(self):
        self.wait_socket_ready()
        frame = self.process_stack_receive()
        self.assertEqual(frame, b'a'*100)

    def test_transmit(self):
        s = self.make_socket()
        s.bind(tools.get_test_interface(), txid=self.stack_rxid, rxid=self.stack_txid)
        self.socket_ready = True

        self.wait_transmission_complete(1)
        frame = s.recv()
        self.assertEqual(frame, b'b'*100)

    def _test_transmit(self):
        self.wait_socket_ready()
        self.stack.send(b'b'*100)
        self.process_stack_send()
        
    def test_transmit_long_stmin(self):
        s = self.make_socket()
        s.set_fc_opts(stmin=100)
        s.bind(tools.get_test_interface(), txid=self.stack_rxid, rxid=self.stack_txid)
        self.socket_ready = True
        self.wait_transmission_complete(5)
        frame = s.recv()
        self.assertEqual(frame, b'b'*150)

    def _test_transmit_long_stmin(self):
        self.wait_socket_ready()
        payload = b'b'*150
        ncf = math.ceil(max(len(payload)-6,0)/7)
        expected_time = ncf * 0.1
        self.stack.send(payload)
        t1 = time.time()
        self.process_stack_send(timeout=2*expected_time*0.95)
        diff = time.time() - t1
        self.assertGreater(diff, expected_time)

    def test_receive_long_stmin(self):
        s = self.make_socket()
        s.bind(tools.get_test_interface(), txid=self.stack_rxid, rxid=self.stack_txid)
        self.socket_ready = True
        s.send(b'a'*150)
        self.wait_reception_complete(timeout=5)

    def _test_receive_long_stmin(self):
        self.wait_socket_ready()
        payload = b'a'*150
        ncf = math.ceil(max(len(payload)-6,0)/7)
        expected_time = ncf * 0.1
        t1 = time.time()
        self.stack.params.set('stmin', 100)
        frame = self.process_stack_receive(timeout=2*expected_time)
        self.assertEqual(frame, payload)
        diff = time.time() - t1
        self.assertGreater(diff, expected_time*0.95)

    def test_receive_extended_29bits(self):
        s = self.make_socket()
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=self.stack_rxid, rxid=self.stack_txid, source_address=0x88, target_address=0x99)
        s.bind(tools.get_test_interface(),addr)
        self.socket_ready = True
        s.send(b'a'*100)
        self.wait_reception_complete()

    def _test_receive_extended_29bits(self):
        self.wait_socket_ready()
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=self.stack_txid, rxid=self.stack_rxid, source_address=0x99, target_address=0x88)
        self.stack.set_address(addr)
        frame = self.process_stack_receive()
        self.assertEqual(frame, b'a'*100)

    def test_transmit_extended_29bits(self):
        s = self.make_socket()
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=self.stack_rxid, rxid=self.stack_txid, source_address=0x88, target_address=0x99)
        s.bind(tools.get_test_interface(), addr)
        self.socket_ready = True

        self.wait_transmission_complete(1)
        frame = s.recv()
        self.assertEqual(frame, b'b'*100)

    def _test_transmit_extended_29bits(self):
        self.wait_socket_ready()
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=self.stack_txid, rxid=self.stack_rxid, source_address=0x99, target_address=0x88)
        self.stack.set_address(addr)
        self.stack.send(b'b'*100)
        self.process_stack_send()

    def test_receive_mixed_29bits(self):
        s = self.make_socket()
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x88, target_address=0x99, address_extension=0xDD)
        s.bind(tools.get_test_interface(),addr)
        self.socket_ready = True
        s.send(b'c'*100)
        self.wait_reception_complete()

    def _test_receive_mixed_29bits(self):
        self.wait_socket_ready()
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x99, target_address=0x88, address_extension=0xDD)
        self.stack.set_address(addr)
        frame = self.process_stack_receive()
        self.assertEqual(frame, b'c'*100)

    def test_transmit_mixed_29bits(self):
        s = self.make_socket()
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x88, target_address=0x99, address_extension=0xEE)
        s.bind(tools.get_test_interface(), addr)
        self.socket_ready = True

        self.wait_transmission_complete(1)
        frame = s.recv()
        self.assertEqual(frame, b'd'*100)

    def _test_transmit_mixed_29bits(self):
        self.wait_socket_ready()
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x99, target_address=0x88, address_extension=0xEE)
        self.stack.set_address(addr)
        self.stack.send(b'd'*100)
        self.process_stack_send()