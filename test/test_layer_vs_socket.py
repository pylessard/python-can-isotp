import unittest
import time
import isotp
from test.ThreadableTest import ThreadableTest
from . import tools
import math
import threading
from . import unittest_logging  # Don't remove

from typing import List

try:
    import can
    can_module_missing = False
except ImportError:
    can_module_missing = True


@unittest.skipIf(tools.check_isotp_socket_possible() == False, 'Cannot test stack against IsoTP socket. %s' % tools.isotp_socket_impossible_reason())
@unittest.skipIf(can_module_missing, 'Python-can must be isntalled to run this test suite')
class TestLayerAgainstSocket(ThreadableTest):

    stack: isotp.CanStack
    socket_list: List[isotp.socket]

    def __init__(self, *args, **kwargs):
        ThreadableTest.__init__(self, *args, **kwargs)
        if not hasattr(self.__class__, '_next_id'):
            self.__class__._next_id = 1

        (self.stack_txid, self.stack_rxid) = tools.get_next_can_id_pair()

    def setUp(self):
        self.socket_list = []
        self.transmission_complete = threading.Event()
        self.reception_complete = threading.Event()
        self.socket_ready = threading.Event()
        self.stack_ready = threading.Event()
        self.allow_send = threading.Event()

    def make_socket(self, tx_data_length=8, can_fd=False, *args, **kwargs):
        mtu = isotp.tpsock.LinkLayerProtocol.CAN_FD if can_fd else isotp.tpsock.LinkLayerProtocol.CAN

        if mtu == isotp.tpsock.LinkLayerProtocol.CAN:
            assert tx_data_length == 8, "CAN bus only supports 8-bytes payloads"

        s = isotp.socket(*args, **kwargs)
        s.set_ll_opts(mtu=mtu, tx_dl=tx_data_length)
        self.socket_list.append(s)
        return s

    def get_can_stack(self, **isotp_params_override):
        # Default configuration
        isotp_params = {
            'stmin': 10,  # Will request the sender to wait 10ms between consecutive frame. 0-127ms or 100-900ns with values from 0xF1-0xF9
            'blocksize': 48,  # Request the sender to send 48 consecutives frames before sending a new flow control message
            'wftmax': 0,  # Number of wait frame allowed before triggering an error
            'tx_data_length': 8,  # Link layer (CAN layer) works with 8 byte payload (CAN 2.0)
            'tx_padding': 0,  # Will pad all transmitted CAN messages with byte 0x00. None means no padding
            'rx_flowcontrol_timeout': 1000,  # Triggers a timeout if a flow control is awaited for more than 1000 milliseconds
            'rx_consecutive_frame_timeout': 1000,  # Triggers a timeout if a consecutive frame is awaited for more than 1000 milliseconds
            'override_receiver_stmin': None,  # When sending, respect the stmin requirement of the receiver. If set to True, go as fast as possible.
            'can_fd': False,
            'max_frame_size': 4095,
            'bitrate_switch': False,
            'rate_limit_enable': False,
            'listen_mode': False,
            'blocking_send': False
        }

        isotp_params.update(isotp_params_override)
        return isotp.CanStack(bus=self.bus, address=self.address, params=isotp_params)

    def clientSetUp(self, socketcan_fd=False, tx_data_length=8):
        bus_config = tools.get_test_interface_config()
        bus_config['fd'] = socketcan_fd

        if hasattr(self, 'stack'):    # In case this is recalled by the test.
            self.stack.stop()

        if hasattr(self, 'bus'):    # In case this is recalled by the test.
            self.bus.shutdown()

        self.bus = can.interface.Bus(**bus_config)
        self.address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.stack_txid, rxid=self.stack_rxid)
        self.stack = self.get_can_stack(can_fd=socketcan_fd, tx_data_length=tx_data_length)
        self.stack.start()

    def clientTearDown(self):
        self.stack.stop()
        self.bus.shutdown()

    def tearDown(self):
        for socket in self.socket_list:
            socket.close()

    def process_stack_receive(self, timeout=1):
        t1 = time.monotonic()
        self.reception_complete.clear()
        while time.monotonic() - t1 < timeout:
            if self.stack.available():
                break
            time.sleep(0.01)
        self.reception_complete.set()
        return self.stack.recv()

    def process_stack_send(self, timeout=1):
        self.transmission_complete.clear()
        t1 = time.monotonic()
        while time.monotonic() - t1 < timeout:
            if not self.stack.transmitting():
                break
            time.sleep(0.01)
        self.transmission_complete.set()

    def wait_transmission_complete(self, timeout=1):
        self.transmission_complete.wait(timeout)
        if not self.transmission_complete.is_set():
            raise TimeoutError("Transmission timed out")

    def wait_reception_complete(self, timeout=1):
        self.reception_complete.wait(timeout)
        if not self.reception_complete.is_set():
            raise TimeoutError("Reception timed out")

    def wait_socket_ready(self, timeout=1):
        self.socket_ready.wait(timeout)
        if not self.socket_ready.is_set():
            raise TimeoutError("Socket not ready")

    def wait_stack_ready(self, timeout=1):
        self.stack_ready.wait(timeout)
        if not self.stack_ready.is_set():
            raise TimeoutError("Stack not ready")

    def make_payload(self, size: int, start=0):
        return bytes([x % 255 for x in range(start, start + size)])

    # ========= Test cases ======

    def do_test_tx_dl_receive_server(self, remote_tx_data_length=8):
        s = self.make_socket(tx_data_length=remote_tx_data_length, can_fd=True)
        s.bind(tools.get_test_interface_config("channel"), isotp.Address(txid=self.stack_rxid, rxid=self.stack_txid))
        self.socket_ready.set()
        self.wait_stack_ready(timeout=2)  # Recreating the stack may take some time.
        s.send(self.make_payload(100))
        self.wait_reception_complete()

    def do_test_tx_dl_receive_client(self, tx_data_length=8):
        self.clientSetUp(socketcan_fd=True, tx_data_length=tx_data_length)
        self.wait_socket_ready()
        self.stack_ready.set()
        frame = self.process_stack_receive()
        self.assertEqual(frame, self.make_payload(100))

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_receive_tx_data_length_8_8(self):
        return self.do_test_tx_dl_receive_server(remote_tx_data_length=8)

    def _test_receive_tx_data_length_8_8(self):
        return self.do_test_tx_dl_receive_client(tx_data_length=8)

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_receive_tx_data_length_64_64(self):
        return self.do_test_tx_dl_receive_server(remote_tx_data_length=64)

    def _test_receive_tx_data_length_64_64(self):
        return self.do_test_tx_dl_receive_client(tx_data_length=64)

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_receive_tx_data_length_8_64(self):
        return self.do_test_tx_dl_receive_server(remote_tx_data_length=64)

    def _test_receive_tx_data_length_8_64(self):
        return self.do_test_tx_dl_receive_client(tx_data_length=8)

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_receive_tx_data_length_64_8(self):
        return self.do_test_tx_dl_receive_server(remote_tx_data_length=8)

    def _test_receive_tx_data_length_64_8(self):
        return self.do_test_tx_dl_receive_client(tx_data_length=64)

    def do_test_tx_dl_transmit_server(self, remote_tx_data_length=8):
        s = self.make_socket(tx_data_length=remote_tx_data_length, can_fd=True, timeout=5)
        s.bind(tools.get_test_interface_config("channel"), isotp.Address(txid=self.stack_rxid, rxid=self.stack_txid))
        self.socket_ready.set()
        self.wait_stack_ready()  # Creating the stack may take some time as we delete the previous and create a new one
        self.wait_transmission_complete(2)
        frame = s.recv()
        self.reception_complete.set()
        payload = self.make_payload(100)
        self.assertEqual(frame, payload)

    def do_test_tx_dl_transmit_client(self, tx_data_length=8):
        self.clientSetUp(socketcan_fd=True, tx_data_length=tx_data_length)
        self.stack_ready.set()
        self.wait_socket_ready()
        payload = self.make_payload(100)
        self.stack.send(payload)
        self.process_stack_send()
        self.wait_reception_complete(3)

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_transmit_tx_data_length_8_8(self):
        return self.do_test_tx_dl_transmit_server(remote_tx_data_length=8)

    def _test_transmit_tx_data_length_8_8(self):
        return self.do_test_tx_dl_transmit_client(tx_data_length=8)

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_transmit_tx_data_length_64_64(self):
        return self.do_test_tx_dl_transmit_server(remote_tx_data_length=64)

    def _test_transmit_tx_data_length_64_64(self):
        return self.do_test_tx_dl_transmit_client(tx_data_length=64)

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_transmit_tx_data_length_8_64(self):
        return self.do_test_tx_dl_transmit_server(remote_tx_data_length=64)

    def _test_transmit_tx_data_length_8_64(self):
        return self.do_test_tx_dl_transmit_client(tx_data_length=8)

    @unittest.skipIf(tools.is_can_fd_socket_possible() == False, 'CAN FD socket is not possible. %s' % tools.isotp_can_fd_socket_impossible_reason())
    def test_transmit_tx_data_length_64_8(self):
        return self.do_test_tx_dl_transmit_server(remote_tx_data_length=8)

    def _test_transmit_tx_data_length_64_8(self):
        return self.do_test_tx_dl_transmit_client(tx_data_length=64)

    def test_transmit_long_stmin(self):
        s = self.make_socket(timeout=5)
        s.set_fc_opts(stmin=100)
        s.bind(tools.get_test_interface_config("channel"), isotp.Address(txid=self.stack_rxid, rxid=self.stack_txid))
        self.socket_ready.set()
        frame = s.recv()
        self.assertEqual(frame, self.make_payload(150))
        self.reception_complete.set()

    def _test_transmit_long_stmin(self):
        self.wait_socket_ready()
        payload = self.make_payload(150)
        ncf = math.ceil(max(len(payload) - 6, 0) / 7)
        expected_time = ncf * 0.1
        self.stack.send(payload)
        t1 = time.monotonic()
        self.process_stack_send(timeout=2 * expected_time * 0.95)
        diff = time.monotonic() - t1
        self.assertGreater(diff, expected_time)
        self.wait_reception_complete()

    def test_receive_long_stmin(self):
        s = self.make_socket()
        s.bind(tools.get_test_interface_config("channel"), isotp.Address(txid=self.stack_rxid, rxid=self.stack_txid))
        self.socket_ready.set()
        s.send(self.make_payload(150))
        self.wait_reception_complete(timeout=5)

    def _test_receive_long_stmin(self):
        self.wait_socket_ready()
        payload = self.make_payload(150)
        ncf = math.ceil(max(len(payload) - 6, 0) / 7)
        expected_time = ncf * 0.1
        t1 = time.monotonic()
        self.stack.params.set('stmin', 100)
        frame = self.process_stack_receive(timeout=2 * expected_time)
        self.assertEqual(frame, payload)
        diff = time.monotonic() - t1
        self.assertGreater(diff, expected_time * 0.95)

    def test_receive_extended_29bits(self):
        s = self.make_socket()
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=self.stack_rxid,
                             rxid=self.stack_txid, source_address=0x88, target_address=0x99)
        s.bind(tools.get_test_interface_config("channel"), addr)
        self.socket_ready.set()
        s.send(self.make_payload(100))
        self.wait_reception_complete()

    def _test_receive_extended_29bits(self):
        self.wait_socket_ready()
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=self.stack_txid,
                             rxid=self.stack_rxid, source_address=0x99, target_address=0x88)
        self.stack.set_address(addr)
        frame = self.process_stack_receive()
        self.assertEqual(frame, self.make_payload(100))

    def test_transmit_extended_29bits(self):
        s = self.make_socket(timeout=3)
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=self.stack_rxid,
                             rxid=self.stack_txid, source_address=0x88, target_address=0x99)
        s.bind(tools.get_test_interface_config("channel"), addr)
        self.socket_ready.set()

        self.wait_transmission_complete(1)
        frame = s.recv()
        self.reception_complete.set()
        self.assertEqual(frame, self.make_payload(100, 1))

    def _test_transmit_extended_29bits(self):
        self.wait_socket_ready()
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=self.stack_txid,
                             rxid=self.stack_rxid, source_address=0x99, target_address=0x88)
        self.stack.set_address(addr)
        self.stack_ready.set()
        self.stack.send(self.make_payload(100, 1))
        self.process_stack_send()
        self.wait_reception_complete()

    def test_receive_mixed_29bits(self):
        s = self.make_socket()
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x88, target_address=0x99, address_extension=0xDD)
        s.bind(tools.get_test_interface_config("channel"), addr)
        self.socket_ready.set()
        s.send(self.make_payload(100, 2))
        self.wait_reception_complete()

    def _test_receive_mixed_29bits(self):
        self.wait_socket_ready()
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x99, target_address=0x88, address_extension=0xDD)
        self.stack.set_address(addr)
        frame = self.process_stack_receive()
        self.assertEqual(frame, self.make_payload(100, 2))

    def test_transmit_mixed_29bits(self):
        s = self.make_socket(timeout=3)
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x88, target_address=0x99, address_extension=0xEE)
        s.bind(tools.get_test_interface_config("channel"), addr)
        self.socket_ready.set()
        self.wait_stack_ready()
        frame = s.recv()
        self.assertEqual(frame, self.make_payload(100, 5))
        self.reception_complete.set()

    def _test_transmit_mixed_29bits(self):
        self.stack_ready.set()
        self.wait_socket_ready()
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x99, target_address=0x88, address_extension=0xEE)
        self.stack.set_address(addr)
        self.stack.send(self.make_payload(100, 5))
        self.process_stack_send(2)
        self.wait_reception_complete()

    def test_transmit_asymmetric_address(self):
        s = self.make_socket(timeout=3)
        addr = isotp.AsymmetricAddress(
            tx_addr=isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=0x123, address_extension=0xAA, tx_only=True),
            rx_addr=isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x88, target_address=0x99, address_extension=0xBB, rx_only=True)
        )
        s.bind(tools.get_test_interface_config("channel"), addr)
        self.socket_ready.set()
        self.wait_stack_ready()
        frame = s.recv()
        self.assertEqual(frame, self.make_payload(100, 5))
        self.reception_complete.set()

    def _test_transmit_asymmetric_address(self):
        self.stack_ready.set()
        self.wait_socket_ready()
        addr = isotp.AsymmetricAddress(
            tx_addr=isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x99, target_address=0x88, address_extension=0xBB, tx_only=True),
            rx_addr=isotp.Address(isotp.AddressingMode.Mixed_11bits, rxid=0x123, address_extension=0xAA, rx_only=True)
        )
        self.stack.set_address(addr)
        self.stack.send(self.make_payload(100, 5))
        self.process_stack_send(2)
        self.wait_reception_complete()
