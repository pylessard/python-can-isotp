import isotp
import time
from . import unittest_logging
from .TransportLayerBaseTest import TransportLayerBaseTest
Message = isotp.CanMessage


# Check the behaviour of the transport layer. Sequenece of CAN frames, timings, etc.
class TestTransportLayerThreadingBehavior(TransportLayerBaseTest):
    TXID = 0x112
    RXID = 0x223

    def setUp(self):
        super().setUp()

        params = {
            'stmin': 1,
            'blocksize': 8,
            'squash_stmin_requirement': False,
            'rx_flowcontrol_timeout': 1000,
            'rx_consecutive_frame_timeout': 1000,
            'wftmax': 0,
            'tx_data_length': 8,
            'wait_for_tx_after_rx_time': None
        }

        self.address = isotp.Address(isotp.AddressingMode.Normal_11bits, txid=self.TXID, rxid=self.RXID)
        self.stack = isotp.TransportLayer(
            txfn=self.stack_txfn,
            rxfn=self.stack_rxfn_blocking,
            address=self.address,
            error_handler=self.error_handler,
            params=params
        )

        self.stack.start()

    def tearDown(self) -> None:
        self.stack.stop()
        super().tearDown()

    def simulate_rx(self, data, rxid=RXID, dlc=None):
        self.simulate_rx_msg(Message(arbitration_id=rxid, data=bytearray(data), dlc=dlc))

    def simulate_rx_flowcontrol(self, flow_status, stmin, blocksize, prefix=None):
        data = bytearray()
        if prefix is not None:
            data.extend(bytearray(prefix))
        data.extend(bytearray([0x30 | (flow_status & 0xF), blocksize, stmin]))

        self.simulate_rx(data=data)
