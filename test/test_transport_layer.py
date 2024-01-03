import isotp
from . import unittest_logging
import queue
from functools import partial
import unittest
Message = isotp.CanMessage
from typing import List


class SpliceableQueue(queue.Queue):
    _rx_splices: List[queue.Queue]
    _tx_splices: List[queue.Queue]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tx_splices = []
        self._rx_splices = []

    def add_tx_splice(self, q: queue.Queue):
        self._tx_splices.append(q)

    def add_rx_splice(self, q: queue.Queue):
        self._rx_splices.append(q)

    def put(self, *args, **kwargs):
        super().put(*args, **kwargs)
        for splice in self._tx_splices:
            splice.put(*args, **kwargs)

    def get(self, *args, **kwargs):
        v = super().get(*args, **kwargs)
        for splice in self._rx_splices:
            splice.put(v)
        return v


# Check the behavior of the transport layer. Sequenece of CAN frames, timings, etc.
class TestTransportLayerStackAgainstStack(unittest.TestCase):
    TXID = 0x120
    RXID = 0x121

    STACK_PARAMS = {
        'stmin': 2,
        'blocksize': 8,
        'override_receiver_stmin': None,
        'rx_flowcontrol_timeout': 1000,
        'rx_consecutive_frame_timeout': 1000,
        'wftmax': 0,
        'tx_data_length': 8,
        'tx_padding': None,
        'rx_flowcontrol_timeout': 1000,
        'rx_consecutive_frame_timeout': 1000,
        'can_fd': False,
        'max_frame_size': 65536,
        'bitrate_switch': False,
        'rate_limit_enable': False,
        'listen_mode': False,
        'blocking_send': False
    }

    def setUp(self):
        self.error_triggered = {}
        self.queue1to2 = SpliceableQueue()
        self.queue2to1 = SpliceableQueue()

        params1 = self.STACK_PARAMS.copy()
        params1.update(dict(logger_name='layer1'))

        params2 = self.STACK_PARAMS.copy()
        params2.update(dict(logger_name='layer2'))

        self.address1 = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.TXID, rxid=self.RXID)
        self.address2 = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.RXID, rxid=self.TXID)
        self.layer1 = isotp.TransportLayer(
            txfn=partial(self.send_queue, self.queue1to2),
            rxfn=partial(self.read_queue_blocking, self.queue2to1),
            address=self.address1,
            error_handler=self.error_handler,
            params=params1
        )

        self.layer2 = isotp.TransportLayer(
            txfn=partial(self.send_queue, self.queue2to1),
            rxfn=partial(self.read_queue_blocking, self.queue1to2),
            address=self.address2,
            error_handler=self.error_handler,
            params=params2
        )

        unittest_logging.configure_transport_layer(self.layer1)
        unittest_logging.configure_transport_layer(self.layer2)

        self.layer1.start()
        self.layer2.start()

    def tearDown(self) -> None:
        self.layer1.stop()
        self.layer2.stop()

    def error_handler(self, error):
        if error.__class__ not in self.error_triggered:
            self.error_triggered[error.__class__] = []
        unittest_logging.logger.debug("Error reported:%s" % error)
        self.error_triggered[error.__class__].append(error)

    def assert_no_error_reported(self):
        self.assertEqual(len(self.error_triggered), 0, "At least 1 error was reported")

    def read_queue_blocking(self, q: queue.Queue, timeout: float):
        try:
            return q.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def send_queue(self, q: queue.Queue, val: isotp.CanMessage, timeout: float = 1):
        q.put(val, block=False, timeout=timeout)

    def test_multiframe(self):
        payload = bytearray([x & 0xFF for x in range(100)])
        self.layer1.send(payload)
        data = self.layer2.recv(block=True, timeout=3)
        self.assertEqual(data, payload)
        self.assert_no_error_reported()

    def test_single_frame(self):
        payload = bytearray([x & 0xFF for x in range(5)])
        self.layer1.send(payload)
        data = self.layer2.recv(block=True, timeout=3)
        self.assertEqual(data, payload)
        self.assert_no_error_reported()

    def test_send_4095(self):
        payload = bytearray([x & 0xFF for x in range(4095)])
        self.layer1.send(payload)
        data = self.layer2.recv(block=True, timeout=10)
        self.assertEqual(data, payload)
        self.assert_no_error_reported()

    def test_send_10000(self):
        payload = bytearray([x & 0xFF for x in range(10000)])
        self.layer1.send(payload)

        data = self.layer2.recv(block=True, timeout=20)
        self.assertEqual(data, payload)
        self.assert_no_error_reported()

    def test_blocking_send_timeout(self):
        self.layer1.params.blocking_send = True
        self.layer1.load_params()
        self.layer2.stop()

        with self.assertRaises(isotp.BlockingSendFailure):
            # Will fail because no receiver to send the flow control
            # Timeout will trigger before any other error
            self.layer1.send(bytes([1] * 10), send_timeout=0.5)

    def test_blocking_send_error(self):
        self.layer1.params.blocking_send = True
        self.layer1.load_params()
        self.layer2.stop()

        with self.assertRaises(isotp.BlockingSendFailure):
            # Will fail because no receiver to send the flow control
            # Transmission will fail because no flow control
            self.layer1.send(bytes([1] * 10), send_timeout=10)

    def test_blocking_send(self):
        self.layer1.params.blocking_send = True
        self.layer1.load_params()
        # layer2 has a thread to handle reception
        self.layer1.send(bytes([1] * 100), send_timeout=5)
        self.assert_no_error_reported()

    def test_listen_mode(self):
        layer3_rx_queue = queue.Queue()
        layer3_tx_queue = queue.Queue()

        self.queue1to2.add_tx_splice(layer3_rx_queue)
        self.queue2to1.add_tx_splice(layer3_rx_queue)

        params3 = self.STACK_PARAMS.copy()
        params3.update(dict(logger_name='layer3', listen_mode=True))

        # Layer 3 should receive the same thing as layer 2 even though it receives all messages
        layer3 = isotp.TransportLayer(
            txfn=partial(self.send_queue, layer3_tx_queue),
            rxfn=partial(self.read_queue_blocking, layer3_rx_queue),
            address=self.address2,
            error_handler=self.error_handler,
            params=params3
        )

        unittest_logging.configure_transport_layer(layer3)
        layer3.start()
        try:
            payload = bytes([x % 255 for x in range(100)])
            self.layer1.send(payload)
            payload2 = self.layer2.recv(block=True, timeout=5)
            self.assertEqual(payload, payload2)

            payload3 = layer3.recv(block=True, timeout=1)
            self.assertEqual(payload, payload3)

            self.assert_no_error_reported()
            self.assertTrue(layer3_tx_queue.empty())    # layer3 cannot send
        finally:
            layer3.stop()

    def test_no_call_to_process_after_start(self):
        # Make sure we maintain backward compatibility without introducing weird race conditions into old application
        with self.assertRaises(RuntimeError):
            self.layer1.process()   # layer is running, Cannot call process

        self.layer1.stop()
        self.layer1.process()   # OK to call backwrd compatible process() when not running


class TestTransportLayerStackAgainstStackAsymetricAddress(unittest.TestCase):
    STACK_PARAMS = {
        'stmin': 2,
        'blocksize': 8,
        'override_receiver_stmin': None,
        'rx_flowcontrol_timeout': 1000,
        'rx_consecutive_frame_timeout': 1000,
        'wftmax': 0,
        'tx_data_length': 8,
        'tx_padding': None,
        'rx_flowcontrol_timeout': 1000,
        'rx_consecutive_frame_timeout': 1000,
        'can_fd': False,
        'max_frame_size': 65536,
        'bitrate_switch': False,
        'rate_limit_enable': False,
        'listen_mode': False,
        'blocking_send': False
    }

    def setUp(self):
        self.error_triggered = {}
        self.queue1to2 = SpliceableQueue()
        self.queue2to1 = SpliceableQueue()

        params1 = self.STACK_PARAMS.copy()
        params1.update(dict(logger_name='layer1'))

        params2 = self.STACK_PARAMS.copy()
        params2.update(dict(logger_name='layer2'))

        self.address1 = isotp.AsymmetricAddress(
            tx_addr=isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=0x123, address_extension=0xAA, tx_only=True),
            rx_addr=isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x88, target_address=0x99, address_extension=0xBB, rx_only=True)
        )
        self.address2 = isotp.AsymmetricAddress(
            tx_addr=isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x99, target_address=0x88, address_extension=0xBB, tx_only=True),
            rx_addr=isotp.Address(isotp.AddressingMode.Mixed_11bits, rxid=0x123, address_extension=0xAA, rx_only=True)
        )
        self.layer1 = isotp.TransportLayer(
            txfn=partial(self.send_queue, self.queue1to2),
            rxfn=partial(self.read_queue_blocking, self.queue2to1),
            address=self.address1,
            error_handler=self.error_handler,
            params=params1
        )

        self.layer2 = isotp.TransportLayer(
            txfn=partial(self.send_queue, self.queue2to1),
            rxfn=partial(self.read_queue_blocking, self.queue1to2),
            address=self.address2,
            error_handler=self.error_handler,
            params=params2
        )

        unittest_logging.configure_transport_layer(self.layer1)
        unittest_logging.configure_transport_layer(self.layer2)

        self.layer1.start()
        self.layer2.start()

    def tearDown(self) -> None:
        self.layer1.stop()
        self.layer2.stop()

    def error_handler(self, error):
        if error.__class__ not in self.error_triggered:
            self.error_triggered[error.__class__] = []
        unittest_logging.logger.debug("Error reported:%s" % error)
        self.error_triggered[error.__class__].append(error)

    def assert_no_error_reported(self):
        self.assertEqual(len(self.error_triggered), 0, "At least 1 error was reported")

    def read_queue_blocking(self, q: queue.Queue, timeout: float):
        try:
            return q.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def send_queue(self, q: queue.Queue, val: isotp.CanMessage, timeout: float = 1):
        q.put(val, block=False, timeout=timeout)

    def test_layer1_2_layer2(self):
        payload = bytearray([x & 0xFF for x in range(100)])
        self.layer1.send(payload)
        data = self.layer2.recv(block=True, timeout=3)
        self.assertEqual(data, payload)
        self.assert_no_error_reported()

    def test_layer2_2_layer1(self):
        payload = bytearray([x & 0xFF for x in range(100)])
        self.layer2.send(payload)
        data = self.layer1.recv(block=True, timeout=3)
        self.assertEqual(data, payload)
        self.assert_no_error_reported()
