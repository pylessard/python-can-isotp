import unittest
from .TransportLayerBaseTest import TransportLayerBaseTest
from . import unittest_logging
import isotp

Message = isotp.CanMessage

# We check that addressing modes have the right effect on payloads.


class TestAddressingMode(TransportLayerBaseTest):
    def setUp(self):
        super().setUp()

    def test_create_address(self):
        isotp.Address(isotp.AddressingMode.Normal_11bits, txid=1, rxid=2)
        isotp.Address(isotp.AddressingMode.Normal_29bits, txid=1, rxid=2)
        isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=1, target_address=2)
        isotp.Address(isotp.AddressingMode.Extended_11bits, txid=1, rxid=2, target_address=3, source_address=5)
        isotp.Address(isotp.AddressingMode.Extended_29bits, txid=1, rxid=2, target_address=3, source_address=5)
        isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=1, rxid=2, address_extension=3)
        isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, target_address=2, address_extension=3)

    def test_create_address_bad_params(self):
        # Make sure that any missing param is catched
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Normal_11bits, txid=1)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=1)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Normal_29bits, rxid=2)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Normal_29bits, txid=1)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.NormalFixed_29bits, target_address=2)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=1)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_11bits, rxid=2, target_address=3, source_address=5)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_11bits, txid=1, target_address=3, source_address=5)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_11bits, txid=1, rxid=2, source_address=5)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_11bits, txid=1, rxid=2, target_address=3)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_29bits, rxid=2, target_address=3, source_address=5)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_29bits, txid=1, target_address=3, source_address=5)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_29bits, txid=1, rxid=2, source_address=5)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_29bits, txid=1, rxid=2, target_address=3)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_11bits, rxid=2, address_extension=3)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=1, address_extension=3)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=1, rxid=2)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, target_address=2, address_extension=3)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, address_extension=3)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, target_address=2)

    def test_create_partial_address(self):
        # Valid partial addresses
        isotp.Address(isotp.AddressingMode.Normal_11bits, txid=1, tx_only=True)
        isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=1, rx_only=True)
        isotp.Address(isotp.AddressingMode.Normal_29bits, txid=1, tx_only=True)
        isotp.Address(isotp.AddressingMode.Normal_29bits, rxid=2, rx_only=True)

        isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=1, target_address=2, tx_only=True)
        isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=1, target_address=2, rx_only=True)

        isotp.Address(isotp.AddressingMode.Extended_11bits, txid=1, target_address=3, tx_only=True)
        isotp.Address(isotp.AddressingMode.Extended_11bits, rxid=2, source_address=5, rx_only=True)

        isotp.Address(isotp.AddressingMode.Extended_29bits, txid=1, target_address=3, tx_only=True)
        isotp.Address(isotp.AddressingMode.Extended_29bits, rxid=2, source_address=5, rx_only=True)

        isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=1, address_extension=3, tx_only=True)
        isotp.Address(isotp.AddressingMode.Mixed_11bits, rxid=1, address_extension=3, rx_only=True)

        isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, target_address=2, address_extension=3, tx_only=True)
        isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, target_address=2, address_extension=3, rx_only=True)

    def test_create_partial_address_bad_params(self):
        # Create partial addresses with missing parameters
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=1, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Normal_11bits, txid=1, rx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Normal_29bits, rxid=1, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Normal_29bits, txid=2, rx_only=True)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=1, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.NormalFixed_29bits, target_address=2, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=1, rx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.NormalFixed_29bits, target_address=2, rx_only=True)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_11bits, target_address=3, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_11bits, txid=1, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_11bits, source_address=5, rx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_11bits, rxid=2, rx_only=True)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_29bits, target_address=3, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_29bits, txid=1, tx_only=True)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_29bits, source_address=5, rx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Extended_29bits, rxid=2, rx_only=True)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_11bits, address_extension=3, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=1, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_11bits, address_extension=3, rx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_11bits, rxid=1, rx_only=True)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, target_address=2, address_extension=3, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, address_extension=3, tx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, target_address=2, tx_only=True)

        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, target_address=2, address_extension=3, rx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, address_extension=3, rx_only=True)
        with self.assertRaises(Exception):
            isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, target_address=2, rx_only=True)

    def test_create_address_asymmetric(self):
        required_params_per_mode_and_dir = {
            isotp.AddressingMode.Normal_11bits: {'tx': ['txid'], 'rx': ['rxid']},
            isotp.AddressingMode.Normal_29bits: {'tx': ['txid'], 'rx': ['rxid']},
            isotp.AddressingMode.NormalFixed_29bits: {'tx': ['source_address', 'target_address'], 'rx': ['source_address', 'target_address']},
            isotp.AddressingMode.Extended_11bits: {'tx': ['txid', 'target_address'], 'rx': ['rxid', 'source_address']},
            isotp.AddressingMode.Extended_29bits: {'tx': ['txid', 'target_address'], 'rx': ['rxid', 'source_address']},
            isotp.AddressingMode.Mixed_11bits: {'tx': ['txid', 'address_extension'], 'rx': ['rxid', 'address_extension']},
            isotp.AddressingMode.Mixed_29bits: {
                'tx': ['source_address', 'target_address', 'address_extension'],
                'rx': ['source_address', 'target_address', 'address_extension']
            }
        }

        for tx_mode in required_params_per_mode_and_dir:
            tx_params_list = required_params_per_mode_and_dir[tx_mode]['tx']
            tx_params = dict(zip(tx_params_list, range(len(tx_params_list))))   # Make a dummy value
            for rx_mode in required_params_per_mode_and_dir:
                rx_params_list = required_params_per_mode_and_dir[rx_mode]['rx']
                rx_params = dict(zip(rx_params_list, range(len(rx_params_list))))   # Make a dummy value
                unittest_logging.logger.debug(f"tx_mode={tx_mode}, rx_mode={rx_mode}")
                txaddr = isotp.Address(tx_mode, tx_only=True, **tx_params)
                rxaddr = isotp.Address(rx_mode, rx_only=True, **rx_params)
                addr = isotp.AsymmetricAddress(tx_addr=txaddr, rx_addr=rxaddr)

                self.assertTrue(txaddr.is_partial_address())
                self.assertTrue(rxaddr.is_partial_address())
                self.assertFalse(addr.is_partial_address())

                # Let's make sure that the interface is not broken. All methods can be called without raising an exception
                addr.get_rx_arbitration_id(isotp.TargetAddressType.Functional)
                addr.get_rx_arbitration_id(isotp.TargetAddressType.Physical)
                addr.get_tx_arbitration_id(isotp.TargetAddressType.Functional)
                addr.get_tx_arbitration_id(isotp.TargetAddressType.Physical)

                addr.requires_tx_extension_byte()
                addr.requires_rx_extension_byte()
                addr.get_tx_extension_byte()
                addr.get_rx_extension_byte()
                addr.is_tx_29bits()
                addr.is_rx_29bits()
                addr.is_for_me(isotp.CanMessage())
                addr.get_rx_prefix_size()
                addr.get_tx_payload_prefix()
                addr.is_partial_address()

    def test_single_frame_only_function_tatype(self):
        tatype = isotp.TargetAddressType.Functional

        address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=1, rxid=2)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
        layer.send(self.make_payload(7), tatype)
        with self.assertRaises(ValueError):
            layer.send(self.make_payload(8), tatype)

        address = isotp.Address(isotp.AddressingMode.Normal_29bits, txid=1, rxid=2)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
        layer.send(self.make_payload(7), tatype)
        with self.assertRaises(ValueError):
            layer.send(self.make_payload(8), tatype)

        address = isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=1, target_address=2)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
        layer.send(self.make_payload(7), tatype)
        with self.assertRaises(ValueError):
            layer.send(self.make_payload(8), tatype)

        address = isotp.Address(isotp.AddressingMode.Extended_11bits, txid=1, rxid=2, target_address=3, source_address=4)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
        layer.send(self.make_payload(6), tatype)
        with self.assertRaises(ValueError):
            layer.send(self.make_payload(7), tatype)

        address = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=1, rxid=2, target_address=3, source_address=4)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
        layer.send(self.make_payload(6), tatype)
        with self.assertRaises(ValueError):
            layer.send(self.make_payload(7), tatype)

        address = isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=1, rxid=2, address_extension=3)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
        layer.send(self.make_payload(6), tatype)
        with self.assertRaises(ValueError):
            layer.send(self.make_payload(7), tatype)

        address = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=1, target_address=2, address_extension=3)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address)
        layer.send(self.make_payload(6), tatype)
        with self.assertRaises(ValueError):
            layer.send(self.make_payload(7), tatype)

    def test_11bits_normal_basic(self):
        rxid = 0x123
        txid = 0x456
        address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=txid, rxid=rxid)

        self.assertTrue(address.is_for_me(Message(arbitration_id=rxid)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid + 1)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid)

    def test_11bits_normal_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        rxid = 0x123
        txid = 0x456
        address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=txid, rxid=rxid)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive Single frame - Functional
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]), extended_id=False))
        layer.process()
        self.assert_sent_flow_control(stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([0x21, 0x07, 0x08]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical / Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
        self.assertFalse(msg.is_extended_id)

        # Transmit single frame - Functional : tx_dl = 32
        layer.reset()
        layer.params.set('tx_data_length', 32)
        layer.send(b'\xAA' * 30, functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([0x00, 30] + [0xaa] * 30))
        self.assertFalse(msg.is_extended_id)

        with self.assertRaises(ValueError):
            layer.reset()
            layer.params.set('tx_data_length', 32)
            layer.send(b'\x04' * 31, functional)
        layer.params.set('tx_data_length', 8)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09]))
        self.assertFalse(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0), extended_id=False))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([0x21, 0x0A, 0x0B]))
        self.assertFalse(msg.is_extended_id)

    def test_29bits_normal_basic(self):
        rxid = 0x123456
        txid = 0x789ABC

        address = isotp.Address(isotp.AddressingMode.Normal_29bits, txid=txid, rxid=rxid)
        self.assertTrue(address.is_for_me(Message(arbitration_id=rxid, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid, extended_id=False)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid + 1, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid + 1, extended_id=False)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid)

    def test_29bits_normal_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        rxid = 0x123456
        txid = 0x789ABC
        address = isotp.Address(isotp.AddressingMode.Normal_29bits, txid=txid, rxid=rxid)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive Single frame - Functional
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]), extended_id=True))
        layer.process()
        self.assert_sent_flow_control(stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([0x21, 0x07, 0x08]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical / Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09]))
        self.assertTrue(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0), extended_id=True))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([0x21, 0x0A, 0x0B]))
        self.assertTrue(msg.is_extended_id)

    def test_asymmetric_address_normal_11_29(self):
        rxid = 0x123
        txid = 0x789ABC
        address = isotp.AsymmetricAddress(
            tx_addr=isotp.Address(isotp.AddressingMode.Normal_29bits, txid=txid, tx_only=True),
            rx_addr=isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=rxid, rx_only=True)
        )
        self.assertTrue(address.is_tx_29bits())
        self.assertFalse(address.is_rx_29bits())

        self.assertTrue(address.is_for_me(Message(arbitration_id=rxid)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid + 1)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid)

    def test_29bits_normal_fixed(self):
        ta = 0x55
        sa = 0xAA
        rxid_physical = 0x18DAAA55
        rxid_functional = 0x18DBAA55
        txid_physical = 0x18DA55AA
        txid_functional = 0x18DB55AA

        address = isotp.Address(isotp.AddressingMode.NormalFixed_29bits, target_address=ta, source_address=sa)

        self.assertTrue(address.is_for_me(Message(rxid_physical, extended_id=True)))
        self.assertTrue(address.is_for_me(Message(rxid_functional, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(txid_physical, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(txid_functional, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=(rxid_physical) & 0x7FF, extended_id=False)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid_physical + 1, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=(rxid_physical + 1) & 0x7FF, extended_id=False)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid_physical)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid_functional)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid_physical)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid_functional)

    def test_29bits_normal_fixed_custom_id(self):
        ta = 0x55
        sa = 0xAA
        rxid_physical = 0x1F40AA55
        rxid_functional = 0x1F41AA55
        txid_physical = 0x1F4055AA
        txid_functional = 0x1F4155AA

        p_id = 0x1F400000
        f_id = 0x1F410000

        address = isotp.Address(isotp.AddressingMode.NormalFixed_29bits, target_address=ta, source_address=sa, physical_id=p_id, functional_id=f_id)

        self.assertTrue(address.is_for_me(Message(rxid_physical, extended_id=True)))
        self.assertTrue(address.is_for_me(Message(rxid_functional, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(txid_physical, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(txid_functional, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=(rxid_physical) & 0x7FF, extended_id=False)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=rxid_physical + 1, extended_id=True)))
        self.assertFalse(address.is_for_me(Message(arbitration_id=(rxid_physical + 1) & 0x7FF, extended_id=False)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid_physical)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid_functional)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid_physical)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid_functional)

    def test_29bits_normal_fixed_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        ta = 0x55
        sa = 0xAA
        rxid_physical = 0x18DAAA55
        rxid_functional = 0x18DBAA55
        txid_physical = 0x18DA55AA
        txid_functional = 0x18DB55AA

        address = isotp.Address(isotp.AddressingMode.NormalFixed_29bits, target_address=ta, source_address=sa)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive Single frame - Functional
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid_functional, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray(
            [0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]), extended_id=True))
        layer.process()
        self.assert_sent_flow_control(stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([0x21, 0x07, 0x08]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit single frame - Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_functional)
        self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09]))
        self.assertTrue(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=self.make_flow_control_data(
            flow_status=0, stmin=0, blocksize=0), extended_id=True))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x21, 0x0A, 0x0B]))
        self.assertTrue(msg.is_extended_id)

    def test_29bits_normal_fixed_custom_id_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        ta = 0x55
        sa = 0xAA
        rxid_physical = 0x1F40AA55
        rxid_functional = 0x1F41AA55
        txid_physical = 0x1F4055AA
        txid_functional = 0x1F4155AA

        p_id = 0x1F400000
        f_id = 0x1F410000

        address = isotp.Address(isotp.AddressingMode.NormalFixed_29bits, target_address=ta, source_address=sa, physical_id=p_id, functional_id=f_id)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive Single frame - Functional
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid_functional, data=bytearray([0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray(
            [0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]), extended_id=True))
        layer.process()
        self.assert_sent_flow_control(stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([0x21, 0x07, 0x08]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit single frame - Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_functional)
        self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09]))
        self.assertTrue(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=self.make_flow_control_data(
            flow_status=0, stmin=0, blocksize=0), extended_id=True))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x21, 0x0A, 0x0B]))
        self.assertTrue(msg.is_extended_id)

    def test_11bits_extended(self):
        txid = 0x123
        rxid = 0x456
        sa = 0x55
        ta = 0xAA

        address = isotp.Address(isotp.AddressingMode.Extended_11bits, txid=txid, rxid=rxid, source_address=sa, target_address=ta)

        self.assertFalse(address.is_for_me(Message(rxid, extended_id=False)))  # No data
        self.assertFalse(address.is_for_me(Message(txid, extended_id=False)))  # No data, wrong id
        self.assertFalse(address.is_for_me(Message(rxid, data=bytearray([ta]), extended_id=False)))  # wrong id
        self.assertTrue(address.is_for_me(Message(rxid, data=bytearray([sa]), extended_id=False)))
        self.assertFalse(address.is_for_me(Message(rxid, data=bytearray([sa]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(rxid + 1, data=bytearray([sa]), extended_id=False)))
        self.assertFalse(address.is_for_me(Message(rxid, data=bytearray([sa + 1]), extended_id=False)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid)

    def test_11bits_extended_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        txid = 0x123
        rxid = 0x456
        sa = 0x55
        ta = 0xAA

        address = isotp.Address(isotp.AddressingMode.Extended_11bits, txid=txid, rxid=rxid, source_address=sa, target_address=ta)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical / Functional
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([sa, 0x03, 0x01, 0x02, 0x03]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([sa, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=False))
        layer.process()
        self.assert_sent_flow_control(prefix=[ta], stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([sa, 0x21, 0x06, 0x07, 0x08]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x03, 0x04, 0x05, 0x06]))
        self.assertFalse(msg.is_extended_id)

        # Transmit single frame - Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x03, 0x04, 0x05, 0x06]))
        self.assertFalse(msg.is_extended_id)

        # Transmit single frame - Functional; txdl=32
        layer.reset()
        layer.params.set('tx_data_length', 32)
        layer.send(b'\x55' * 29, functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x00, 29] + [0x55] * 29))
        self.assertFalse(msg.is_extended_id)

        # Transmit single frame - Functional; txdl=32
        with self.assertRaises(ValueError):
            layer.reset()
            layer.params.set('tx_data_length', 32)
            layer.send(b'\x55' * 30, functional)
        layer.params.set('tx_data_length', 8)

        # Transmit single frame with payload length 7 - Physical; txdl=16...64
        for tx_len in (12, 16, 20, 24, 32, 48, 64):
            layer.reset()
            layer.params.set("tx_data_length", tx_len)
            layer.send(b'\x55' * 7)
            layer.process()

            msg = self.get_tx_can_msg()
            self.assertIsNotNone(msg)
            self.assertEqual(msg.arbitration_id, txid)
            self.assertEqual(msg.data, bytearray([ta, 0x00, 0x07] + [0x55] * 7 + [0xCC] * 2))
            self.assertFalse(msg.is_extended_id)
        layer.params.set("tx_data_length", 8)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
        self.assertFalse(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(
            flow_status=0, stmin=0, blocksize=0, prefix=[sa]), extended_id=False))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x21, 0x09, 0x0A, 0x0B]))
        self.assertFalse(msg.is_extended_id)

    def test_29bits_extended(self):
        txid = 0x123
        rxid = 0x456
        sa = 0x55
        ta = 0xAA

        address = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=txid, rxid=rxid, source_address=sa, target_address=ta)

        self.assertFalse(address.is_for_me(Message(rxid, extended_id=True)))  # No data
        self.assertFalse(address.is_for_me(Message(txid, extended_id=True)))  # No data, wrong id
        self.assertFalse(address.is_for_me(Message(rxid, data=bytearray([ta]), extended_id=True)))  # wrong id
        self.assertTrue(address.is_for_me(Message(rxid, data=bytearray([sa]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(rxid, data=bytearray([sa]), extended_id=False)))
        self.assertFalse(address.is_for_me(Message(rxid + 1, data=bytearray([sa]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(rxid, data=bytearray([sa + 1]), extended_id=True)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid)

    def test_29bits_extended_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        txid = 0x123
        rxid = 0x456
        sa = 0x55
        ta = 0xAA

        address = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=txid, rxid=rxid, source_address=sa, target_address=ta)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical / Functional
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([sa, 0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([sa, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=True))
        layer.process()
        self.assert_sent_flow_control(prefix=[ta], stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([sa, 0x21, 0x06, 0x07, 0x08]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit single frame - Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
        self.assertTrue(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(
            flow_status=0, stmin=0, blocksize=0, prefix=[sa]), extended_id=True))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ta, 0x21, 0x09, 0x0A, 0x0B]))
        self.assertTrue(msg.is_extended_id)

    def test_11bits_mixed(self):
        txid = 0x123
        rxid = 0x456
        ae = 0x99

        address = isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=txid, rxid=rxid, address_extension=ae)

        self.assertFalse(address.is_for_me(Message(rxid, extended_id=False)))  # No data
        self.assertFalse(address.is_for_me(Message(txid, extended_id=False)))  # No data, wrong id
        self.assertTrue(address.is_for_me(Message(rxid, data=bytearray([ae]), extended_id=False)))
        self.assertFalse(address.is_for_me(Message(rxid, data=bytearray([ae]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(rxid + 1, data=bytearray([ae]), extended_id=False)))
        self.assertFalse(address.is_for_me(Message(rxid, data=bytearray([ae + 1]), extended_id=False)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid)

    def test_11bits_mixed_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        txid = 0x123
        rxid = 0x456
        ae = 0x99

        address = isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=txid, rxid=rxid, address_extension=ae)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical / Functional
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([ae, 0x03, 0x01, 0x02, 0x03]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([ae, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=False))
        layer.process()
        self.assert_sent_flow_control(prefix=[ae], stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([ae, 0x21, 0x06, 0x07, 0x08]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
        self.assertFalse(msg.is_extended_id)

        # Transmit single frame - Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
        self.assertFalse(msg.is_extended_id)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ae, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
        self.assertFalse(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid, data=self.make_flow_control_data(
            flow_status=0, stmin=0, blocksize=0, prefix=[ae]), extended_id=False))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid)
        self.assertEqual(msg.data, bytearray([ae, 0x21, 0x09, 0x0A, 0x0B]))
        self.assertFalse(msg.is_extended_id)

    def test_29bits_mixed(self):
        ta = 0x55
        sa = 0xAA
        ae = 0x99
        rxid_physical = 0x18CEAA55
        rxid_functional = 0x18CDAA55
        txid_physical = 0x18CE55AA
        txid_functional = 0x18CD55AA

        address = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=sa, target_address=ta, address_extension=ae)

        self.assertFalse(address.is_for_me(Message(rxid_physical, extended_id=True)))     # No data
        self.assertFalse(address.is_for_me(Message(rxid_functional, extended_id=True)))     # No data
        self.assertFalse(address.is_for_me(Message(txid_physical, extended_id=True)))     # No data
        self.assertFalse(address.is_for_me(Message(txid_functional, extended_id=True)))     # No data

        self.assertTrue(address.is_for_me(Message(rxid_physical, data=bytearray([ae]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(rxid_physical, data=bytearray([ae]), extended_id=False)))
        self.assertTrue(address.is_for_me(Message(rxid_functional, data=bytearray([ae]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(rxid_functional, data=bytearray([ae]), extended_id=False)))
        self.assertFalse(address.is_for_me(Message(txid_physical, data=bytearray([ae]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(txid_functional, data=bytearray([ae]), extended_id=True)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid_physical)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid_functional)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid_physical)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid_functional)

    def test_29bits_mixed_custom_id(self):
        ta = 0x55
        sa = 0xAA
        ae = 0x99
        rxid_physical = 0x1F4EAA55
        rxid_functional = 0x1F4DAA55
        txid_physical = 0x1F4E55AA
        txid_functional = 0x1F4D55AA

        p_id = 0x1F4E0000
        f_id = 0x1F4D0000

        address = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=sa, target_address=ta,
                                address_extension=ae, physical_id=p_id, functional_id=f_id)

        self.assertFalse(address.is_for_me(Message(rxid_physical, extended_id=True)))     # No data
        self.assertFalse(address.is_for_me(Message(rxid_functional, extended_id=True)))     # No data
        self.assertFalse(address.is_for_me(Message(txid_physical, extended_id=True)))     # No data
        self.assertFalse(address.is_for_me(Message(txid_functional, extended_id=True)))     # No data

        self.assertTrue(address.is_for_me(Message(rxid_physical, data=bytearray([ae]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(rxid_physical, data=bytearray([ae]), extended_id=False)))
        self.assertTrue(address.is_for_me(Message(rxid_functional, data=bytearray([ae]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(rxid_functional, data=bytearray([ae]), extended_id=False)))
        self.assertFalse(address.is_for_me(Message(txid_physical, data=bytearray([ae]), extended_id=True)))
        self.assertFalse(address.is_for_me(Message(txid_functional, data=bytearray([ae]), extended_id=True)))

        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Physical), txid_physical)
        self.assertEqual(address.get_tx_arbitration_id(isotp.TargetAddressType.Functional), txid_functional)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Physical), rxid_physical)
        self.assertEqual(address.get_rx_arbitration_id(isotp.TargetAddressType.Functional), rxid_functional)

    def test_29bits_mixed_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        ta = 0x55
        sa = 0xAA
        ae = 0x99
        rxid_physical = 0x18CEAA55
        rxid_functional = 0x18CDAA55
        txid_physical = 0x18CE55AA
        txid_functional = 0x18CD55AA

        address = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=sa, target_address=ta, address_extension=ae)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([ae, 0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive Single frame - Functional
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid_functional, data=bytearray([ae, 0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([ae, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=True))
        layer.process()
        self.assert_sent_flow_control(prefix=[ae], stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([ae, 0x21, 0x06, 0x07, 0x08]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit single frame - Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_functional)
        self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([ae, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
        self.assertTrue(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=self.make_flow_control_data(
            flow_status=0, stmin=0, blocksize=0, prefix=[ae]), extended_id=True))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([ae, 0x21, 0x09, 0x0A, 0x0B]))
        self.assertTrue(msg.is_extended_id)

    def test_29bits_mixed_custom_id_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        ta = 0x55
        sa = 0xAA
        ae = 0x99
        rxid_physical = 0x1F4EAA55
        rxid_functional = 0x1F4DAA55
        txid_physical = 0x1F4E55AA
        txid_functional = 0x1F4D55AA

        p_id = 0x1F4E0000
        f_id = 0x1F4D0000

        address = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=sa, target_address=ta,
                                address_extension=ae, physical_id=p_id, functional_id=f_id)
        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([ae, 0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive Single frame - Functional
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid_functional, data=bytearray([ae, 0x03, 0x01, 0x02, 0x03]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([ae, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=True))
        layer.process()
        self.assert_sent_flow_control(prefix=[ae], stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=bytearray([ae, 0x21, 0x06, 0x07, 0x08]), extended_id=True))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit single frame - Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_functional)
        self.assertEqual(msg.data, bytearray([ae, 0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([ae, 0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08]))
        self.assertTrue(msg.is_extended_id)

        self.simulate_rx_msg(Message(arbitration_id=rxid_physical, data=self.make_flow_control_data(
            flow_status=0, stmin=0, blocksize=0, prefix=[ae]), extended_id=True))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([ae, 0x21, 0x09, 0x0A, 0x0B]))
        self.assertTrue(msg.is_extended_id)

    def test_asymmetric_address_normalfixed_29_Mixed_11_through_layer(self):
        functional = isotp.TargetAddressType.Functional
        physical = isotp.TargetAddressType.Physical
        ta = 0x55
        sa = 0xAA
        rxid = 0x111
        rx_address_extension = 0x88
        txid_physical = 0x18DA55AA
        txid_functional = 0x18DB55AA

        address = isotp.AsymmetricAddress(
            tx_addr=isotp.Address(isotp.AddressingMode.NormalFixed_29bits, target_address=ta, source_address=sa, tx_only=True),
            rx_addr=isotp.Address(isotp.AddressingMode.Mixed_11bits, rxid=rxid, address_extension=rx_address_extension, rx_only=True)
        )

        layer = isotp.TransportLayer(txfn=self.stack_txfn, rxfn=self.stack_rxfn, address=address, params={'stmin': 0, 'blocksize': 0})

        # Receive Single frame - Physical
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([rx_address_extension, 0x03, 0x01, 0x02, 0x03]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03')

        # Receive multiframe - Physical
        layer.reset()
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray(
            [rx_address_extension, 0x10, 0x08, 0x01, 0x02, 0x03, 0x04, 0x05]), extended_id=False))
        layer.process()
        self.assert_sent_flow_control(stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray([rx_address_extension, 0x21, 0x06, 0x07, 0x08]), extended_id=False))
        layer.process()
        frame = layer.recv()
        self.assertIsNotNone(frame)
        self.assertEqual(frame, b'\x01\x02\x03\x04\x05\x06\x07\x08')

        # Transmit single frame - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit single frame - Functional
        layer.reset()
        layer.send(b'\x04\x05\x06', functional)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_functional)
        self.assertEqual(msg.data, bytearray([0x03, 0x04, 0x05, 0x06]))
        self.assertTrue(msg.is_extended_id)

        # Transmit multiframe - Physical
        layer.reset()
        layer.send(b'\x04\x05\x06\x07\x08\x09\x0A\x0B', physical)
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x10, 0x08, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09]))
        self.assertTrue(msg.is_extended_id)
        flow_control_payload = bytearray([rx_address_extension]) + self.make_flow_control_data(flow_status=0, stmin=0, blocksize=0)
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=flow_control_payload, extended_id=False))
        layer.process()
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.arbitration_id, txid_physical)
        self.assertEqual(msg.data, bytearray([0x21, 0x0A, 0x0B]))
        self.assertTrue(msg.is_extended_id)
