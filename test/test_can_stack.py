import unittest
import isotp
from . import tools
from . import unittest_logging  # Don't remove

_can_module_missing = False
_test_interface_exists = False
_bus_config = tools.get_test_interface_config()
try:
    import can
    _can_module_missing = False
    try:
        bus = can.interface.Bus(**_bus_config)
        bus.shutdown()
        _test_interface_exists = True

    except OSError:
        _test_interface_exists = False

except ImportError:
    _can_module_missing = True


@unittest.skipIf(_can_module_missing, 'Python-can must be isntalled to run this test suite')
@unittest.skipIf(not _test_interface_exists, 'Test interface not available : %s' % _bus_config.get('channel', 'UNKNOWN'))
class TestCanStackNotifier(unittest.TestCase):
    TXID = 0x130
    RXID = 0x131

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

    error_triggered: dict

    def setUp(self) -> None:
        self.error_triggered = {}

        params1 = self.STACK_PARAMS.copy()
        params1.update(dict(logger_name='layer1'))

        params2 = self.STACK_PARAMS.copy()
        params2.update(dict(logger_name='layer2'))

        self.address1 = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.TXID, rxid=self.RXID)
        self.address2 = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.RXID, rxid=self.TXID)

        bus_config = tools.get_test_interface_config()
        bus_config.update({'receive_own_messages': True})
        self.bus = can.interface.Bus(**bus_config)
        self.notifier = can.Notifier(self.bus, [])

        self.layer1 = isotp.NotifierBasedCanStack(
            bus=self.bus,
            notifier=self.notifier,
            address=self.address1,
            error_handler=self.error_handler,
            params=params1
        )

        self.layer2 = isotp.NotifierBasedCanStack(
            bus=self.bus,
            notifier=self.notifier,
            address=self.address2,
            error_handler=self.error_handler,
            params=params2
        )

        unittest_logging.configure_transport_layer(self.layer1)
        unittest_logging.configure_transport_layer(self.layer2)

        self.layer1.start()
        self.layer2.start()

    def tearDown(self) -> None:
        self.notifier.stop()
        self.layer1.stop()
        self.layer2.stop()
        self.bus.shutdown()

    def error_handler(self, error):
        if error.__class__ not in self.error_triggered:
            self.error_triggered[error.__class__] = []
        unittest_logging.logger.debug("Error reported:%s" % error)
        self.error_triggered[error.__class__].append(error)

    def assert_no_error_reported(self):
        self.assertEqual(len(self.error_triggered), 0, "At least 1 error was reported")

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


if __name__ == '__main__':
    unittest.main()
