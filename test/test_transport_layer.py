import isotp
import time
from . import unittest_logging
from .TransportLayerBaseTest import TransportLayerBaseTest
import queue
from functools import partial
import unittest
Message = isotp.CanMessage


# Check the behavior of the transport layer. Sequenece of CAN frames, timings, etc.
class TestTransportLayerStackAgainstStack(unittest.TestCase):
    TXID = 0x120
    RXID = 0x121

    STACK_PARAMS = {
        'stmin': 2,
        'blocksize': 8,
        'override_receiver_stmin': 0,
        'rx_flowcontrol_timeout': 1000,
        'rx_consecutive_frame_timeout': 1000,
        'wftmax': 0,
        'tx_data_length': 8,
        'tx_padding': None,
        'rx_flowcontrol_timeout': 1000,
        'rx_consecutive_frame_timeout': 1000,
        'squash_stmin_requirement': False,
        'can_fd': False,
        'max_frame_size': 65536,
        'bitrate_switch': False,
        'rate_limit_enable': False,
        'listen_mode': False,
        'blocking_send': False
    }

    def setUp(self):
        self.error_triggered = {}
        self.queue1to2 = queue.Queue()
        self.queue2to1 = queue.Queue()

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
