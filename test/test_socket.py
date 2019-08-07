import unittest
import isotp
from . import unittest_logging
from . import tools
import time
import math
import socket

@unittest.skipIf(tools.check_isotp_socket_possible() == False, 'Cannot test IsoTP socket. %s' % tools.isotp_socket_impossible_reason())
class TestSocket(unittest.TestCase):

    def setUp(self):
        self.socket_list = []

    def tearDown(self):
        for socket in self.socket_list:
            socket.close()

    def make_socket(self, *args, **kwargs):
        s = isotp.socket(*args, **kwargs)
        self.socket_list.append(s)
        return s

    def test_read_write_opts(self):
        s = self.make_socket()
        s.get_fc_opts()
        s.get_ll_opts()
        s.get_opts()

        s.set_fc_opts(stmin=11, bs=22, wftmax=33)
        o = s.get_fc_opts()
        self.assertEqual(o.stmin, 11)
        self.assertEqual(o.bs, 22)
        self.assertEqual(o.wftmax, 33)

        s.set_opts(optflag=0xFFFF, frame_txtime=0x55, ext_address=0x11, txpad=0x22, rxpad=0x33, rx_ext_address=0x44, tx_stmin=0x55)
        o = s.get_opts()

        self.assertEqual(o.optflag, 0xFFFF)
        self.assertEqual(o.frame_txtime, 0x55)
        self.assertEqual(o.ext_address, 0x11)
        self.assertEqual(o.txpad, 0x22)
        self.assertEqual(o.rxpad, 0x33)
        self.assertEqual(o.rx_ext_address, 0x44)

    def test_receive_transmit(self):
        payload = b'a'*200
        (txid, rxid) = tools.get_next_can_id_pair()
        s1 = self.make_socket()
        s2 = self.make_socket(timeout=0.2)
        addr1 = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=txid, rxid=rxid)
        addr2 = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=rxid, rxid=txid)
        s1.bind(interface = tools.get_test_interface_config("channel"), address=addr1)
        s2.bind(interface = tools.get_test_interface_config("channel"), address=addr2)
        s1.send(payload)
        t1 = time.time()
        payload2 = s2.recv()
        self.assertEqual(payload, payload2)

    def test_receive_transmit_fc_opts(self):
        (txid, rxid) = tools.get_next_can_id_pair()
        payload = b'a'*200
        ncf = math.ceil(max(len(payload)-6,0)/7)
        expected_time = ncf * 0.1
        s1 = self.make_socket()
        s2 = self.make_socket(timeout=2*expected_time)
        addr1 = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=txid, rxid=rxid)
        addr2 = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=rxid, rxid=txid)

        s2.set_fc_opts(stmin=100, bs=5)

        s1.bind(interface = tools.get_test_interface_config("channel"), address=addr1)
        s2.bind(interface = tools.get_test_interface_config("channel"), address=addr2)
        s1.send(payload)
        t1 = time.time()
        payload2 = s2.recv()
        diff = time.time() - t1
        self.assertEqual(payload, payload2)
        self.assertGreater(diff, expected_time*0.9)
        self.assertLess(diff, expected_time*1.1)

    def test_addressing_normal_11bits(self):
        addr = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=0x123, rxid=0x456)
        s = self.make_socket()
        s.bind(tools.get_test_interface_config("channel"), addr)
        (interface, rxid, txid) = s._socket.getsockname()
        opts = s.get_opts()
        self.assertEqual(txid, 0x123)
        self.assertEqual(rxid, 0x456)
        self.assertFalse(opts.rx_ext_address)
        self.assertFalse(opts.ext_address)

    def test_addressing_normal_29bits(self):
        addr = isotp.Address(isotp.AddressingMode.Normal_29bits, txid=0x123456, rxid=0x789ABC)
        s = self.make_socket()
        s.bind(tools.get_test_interface_config("channel"), addr)
        (interface, rxid, txid) = s._socket.getsockname()
        opts = s.get_opts()
        self.assertEqual(txid, 0x123456 | socket.CAN_EFF_FLAG)
        self.assertEqual(rxid, 0x789ABC | socket.CAN_EFF_FLAG)
        self.assertEqual(opts.optflag & isotp.socket.flags.EXTEND_ADDR, 0)
        self.assertEqual(opts.optflag & isotp.socket.flags.RX_EXT_ADDR, 0)


    def test_addressing_normal_fixed_29bits(self):
        addr = isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=0xaa, target_address=0x55)
        s = self.make_socket()
        s.bind(tools.get_test_interface_config("channel"), addr)
        (interface, rxid, txid) = s._socket.getsockname()
        opts = s.get_opts()
        self.assertEqual(txid, 0x18DA55AA | socket.CAN_EFF_FLAG)
        self.assertEqual(rxid, 0x18DAAA55 | socket.CAN_EFF_FLAG)
        self.assertEqual(opts.optflag & isotp.socket.flags.EXTEND_ADDR, 0)
        self.assertEqual(opts.optflag & isotp.socket.flags.RX_EXT_ADDR, 0)

    def test_addressing_extended_11bits(self):
        addr = isotp.Address(isotp.AddressingMode.Extended_11bits, txid=0x123, rxid=0x456, source_address=0xAA, target_address=0x55)
        s = self.make_socket()
        s.bind(tools.get_test_interface_config("channel"), addr)
        (interface, rxid, txid) = s._socket.getsockname()
        opts = s.get_opts()
        self.assertEqual(txid, 0x123)
        self.assertEqual(rxid, 0x456)
        self.assertNotEqual(opts.optflag & isotp.socket.flags.EXTEND_ADDR, 0)
        self.assertNotEqual(opts.optflag & isotp.socket.flags.RX_EXT_ADDR, 0)
        self.assertEqual(opts.ext_address , 0x55)
        self.assertEqual(opts.rx_ext_address, 0xAA)

    def test_addressing_extended_29bits(self):
        addr = isotp.Address(isotp.AddressingMode.Extended_29bits, txid=0x123456, rxid=0x789abc, source_address=0xAA, target_address=0x55)
        s = self.make_socket()
        s.bind(tools.get_test_interface_config("channel"), addr)
        (interface, rxid, txid) = s._socket.getsockname()
        opts = s.get_opts()
        self.assertEqual(txid, 0x123456 | socket.CAN_EFF_FLAG)
        self.assertEqual(rxid, 0x789abc | socket.CAN_EFF_FLAG)
        self.assertNotEqual(opts.optflag & isotp.socket.flags.EXTEND_ADDR, 0)
        self.assertNotEqual(opts.optflag & isotp.socket.flags.RX_EXT_ADDR, 0)
        self.assertEqual(opts.ext_address , 0x55)
        self.assertEqual(opts.rx_ext_address, 0xAA)

    def test_addressing_mixed_11bits(self):
        addr = isotp.Address(isotp.AddressingMode.Mixed_11bits, txid=0x123, rxid=0x456, address_extension=0x99)
        s = self.make_socket()
        s.bind(tools.get_test_interface_config("channel"), addr)
        (interface, rxid, txid) = s._socket.getsockname()
        opts = s.get_opts()
        self.assertEqual(txid, 0x123)
        self.assertEqual(rxid, 0x456)
        self.assertNotEqual(opts.optflag & isotp.socket.flags.EXTEND_ADDR, 0)
        self.assertNotEqual(opts.optflag & isotp.socket.flags.RX_EXT_ADDR, 0)
        self.assertEqual(opts.ext_address , 0x99)
        self.assertEqual(opts.rx_ext_address, 0x99)

    def test_addressing_mixed_29bits(self):
        addr = isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0xAA, target_address=0x55, address_extension=0x99)
        s = self.make_socket()
        s.bind(tools.get_test_interface_config("channel"), addr)
        (interface, rxid, txid) = s._socket.getsockname()
        opts = s.get_opts()
        self.assertEqual(txid, 0x18CE55AA | socket.CAN_EFF_FLAG)
        self.assertEqual(rxid, 0x18CEAA55 | socket.CAN_EFF_FLAG)
        self.assertNotEqual(opts.optflag & isotp.socket.flags.EXTEND_ADDR, 0)
        self.assertNotEqual(opts.optflag & isotp.socket.flags.RX_EXT_ADDR, 0)
        self.assertEqual(opts.ext_address , 0x99)
        self.assertEqual(opts.rx_ext_address, 0x99)
