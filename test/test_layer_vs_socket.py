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

    def make_socket(self, tx_data_length=8, can_fd=False, *args, **kwargs):
        mtu = isotp.tpsock.LinkLayerProtocol.CAN_FD if can_fd else isotp.tpsock.LinkLayerProtocol.CAN

        if mtu == isotp.tpsock.LinkLayerProtocol.CAN:
            assert tx_data_length == 8, "CAN bus only supports 8-bytes payloads"

        s = isotp.socket(*args, **kwargs)
        s.set_ll_opts(mtu=mtu, tx_dl=tx_data_length)
        self.socket_list.append(s)
        return s

    def get_can_stack(self, **isotp_params_overload):
        # Default configuration
        isotp_params = {
            'stmin': 10,  # Will request the sender to wait 10ms between consecutive frame. 0-127ms or 100-900ns with values from 0xF1-0xF9
            'blocksize': 48,  # Request the sender to send 48 consecutives frames before sending a new flow control message
            'wftmax': 0,  # Number of wait frame allowed before triggering an error
            'tx_data_length': 8,  # Link layer (CAN layer) works with 8 byte payload (CAN 2.0)
            'tx_padding': 0,  # Will pad all transmitted CAN messages with byte 0x00. None means no padding
            'rx_flowcontrol_timeout': 1000,  # Triggers a timeout if a flow control is awaited for more than 1000 milliseconds
            'rx_consecutive_frame_timeout': 1000,  # Triggers a timeout if a consecutive frame is awaited for more than 1000 milliseconds
            'squash_stmin_requirement': False,  # When sending, respect the stmin requirement of the receiver. If set to True, go as fast as possible.
            'can_fd': False
        }

        isotp_params.update(isotp_params_overload)

        return isotp.CanStack(bus=self.bus, address=self.address, params=isotp_params)

    def clientSetUp(self, socketcan_fd=False):
        bus_config = tools.get_test_interface_config()
        bus_config['fd'] = socketcan_fd

        if hasattr(self, 'bus'):    # In case this is recalled by the test.
            self.bus.shutdown()

        if hasattr(self, 'stack'):    # In case this is recalled by the test.
            self.stack.reset()

        self.bus = can.interface.Bus(**bus_config)
        self.address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.stack_txid, rxid=self.stack_rxid)
        self.stack = self.get_can_stack()

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
    def do_test_tx_dl_receive_server(self, tx_data_length=8, remote_tx_data_length=8):
        self.clientSetUp(socketcan_fd=True)
        self.stack = self.get_can_stack(tx_data_length=tx_data_length, can_fd=True)
        s = self.make_socket(tx_data_length=remote_tx_data_length, can_fd = True)
        s.bind(tools.get_test_interface_config("channel"), txid=self.stack_rxid, rxid=self.stack_txid)
        self.socket_ready = True
        s.send(b'a'*100)
        self.wait_reception_complete()

    def do_test_tx_dl_receive_client(self):
        self.wait_socket_ready()
        frame = self.process_stack_receive()
        self.assertEqual(frame, b'a'*100)

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_receive_tx_data_length_8_8(self):
        return self.do_test_tx_dl_receive_server(tx_data_length=8, remote_tx_data_length=8)

    def _test_receive_tx_data_length_8_8(self):
        return self.do_test_tx_dl_receive_client()

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_receive_tx_data_length_64_64(self):
        return self.do_test_tx_dl_receive_server(tx_data_length=64, remote_tx_data_length=64)

    def _test_receive_tx_data_length_64_64(self):
        return self.do_test_tx_dl_receive_client()

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_receive_tx_data_length_8_64(self):
        return self.do_test_tx_dl_receive_server(tx_data_length=8, remote_tx_data_length=64)

    def _test_receive_tx_data_length_8_64(self):
        return self.do_test_tx_dl_receive_client()

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_receive_tx_data_length_64_8(self):
        return self.do_test_tx_dl_receive_server(tx_data_length=64, remote_tx_data_length=8)

    def _test_receive_tx_data_length_64_8(self):
        return self.do_test_tx_dl_receive_client()



    def do_test_tx_dl_transmit_server(self, tx_data_length=8, remote_tx_data_length=8):
        self.clientSetUp(socketcan_fd=True)
        self.stack = self.get_can_stack(tx_data_length=tx_data_length, can_fd=True)
        s = self.make_socket(tx_data_length=remote_tx_data_length, can_fd=True)
        s.bind(tools.get_test_interface_config("channel"), txid=self.stack_rxid, rxid=self.stack_txid)
        self.socket_ready = True

        self.wait_transmission_complete(1)
        frame = s.recv()
        self.assertEqual(frame, b'b'*100)

    def do_test_tx_dl_transmit_client(self):
        self.wait_socket_ready()
        self.stack.send(b'b'*100)
        self.process_stack_send()

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason()) 
    def test_transmit_tx_data_length_8_8(self):
        return self.do_test_tx_dl_transmit_server(tx_data_length=8, remote_tx_data_length=8)

    def _test_transmit_tx_data_length_8_8(self):
        return self.do_test_tx_dl_transmit_client()

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_transmit_tx_data_length_64_64(self):
        return self.do_test_tx_dl_transmit_server(tx_data_length=64, remote_tx_data_length=64)

    def _test_transmit_tx_data_length_64_64(self):
        return self.do_test_tx_dl_transmit_client()

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_transmit_tx_data_length_8_64(self):
        return self.do_test_tx_dl_transmit_server(tx_data_length=8, remote_tx_data_length=64)

    def _test_transmit_tx_data_length_8_64(self):
        return self.do_test_tx_dl_transmit_client()

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_transmit_tx_data_length_64_8(self):
        return self.do_test_tx_dl_transmit_server(tx_data_length=64, remote_tx_data_length=8)

    def _test_transmit_tx_data_length_64_8(self):
        return self.do_test_tx_dl_transmit_client()



    def test_transmit_long_stmin(self):
        s = self.make_socket()
        s.set_fc_opts(stmin=100)
        s.bind(tools.get_test_interface_config("channel"), txid=self.stack_rxid, rxid=self.stack_txid)
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
        s.bind(tools.get_test_interface_config("channel"), txid=self.stack_rxid, rxid=self.stack_txid)
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
        s.bind(tools.get_test_interface_config("channel"),addr)
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
        s.bind(tools.get_test_interface_config("channel"), addr)
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
        s.bind(tools.get_test_interface_config("channel"),addr)
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
        s.bind(tools.get_test_interface_config("channel"), addr)
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
