import unittest
import queue



# Just a class with some helper such as simulate_rx() to make the tests cleaners.
class TransportLayerBaseTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        self.ll_rx_queue = queue.Queue()
        self.ll_tx_queue = queue.Queue()
        self.error_triggered = {}

    def error_handler(self, error):
        if error.__class__ not in self.error_triggered:
            self.error_triggered[error.__class__] = []

        self.error_triggered[error.__class__].append(error)

    def stack_txfn(self, msg):
        if not self.ll_tx_queue.full():
            self.ll_tx_queue.put(msg)

    def stack_rxfn(self):
        if not self.ll_rx_queue.empty():
            return  self.ll_rx_queue.get()

    def rx_isotp_frame(self):
        return self.stack.recv()

    def tx_isotp_frame(self, frame):
        self.stack.send(frame)

    def get_tx_can_msg(self):
        if not self.ll_tx_queue.empty():
            return self.ll_tx_queue.get()

    def make_payload(self, size, start_val=0):
        return [int(x%0x100) for x in range(start_val, start_val+size)]

    def assert_sent_flow_control(self, stmin, blocksize, prefix = None, padding_byte=None, extra_msg=''):
        msg = self.get_tx_can_msg()
        self.assertIsNotNone(msg, 'Expected a Flow Control message, but none was sent.' + ' ' + extra_msg)
        data = bytearray()
        if prefix is not None:
            data.extend(prefix)

        data.extend(bytearray([0x30, blocksize, stmin]))
        if padding_byte is not None:
            padlen = 5
            if prefix is not None:
                padlen -= len(prefix)
            data.extend(bytearray([padding_byte]*padlen))

        self.assertEqual(msg.data, data, 'Message sent is not the wanted flow control'+ ' ' + extra_msg)    # Flow Control
        self.assertEqual(msg.dlc, len(data), 'Flow control message has wrong DLC. Expecting=0x%02x, received=0x%02x' % (len(data), msg.dlc))    

    def assert_error_triggered(self, error_type):
        if error_type in self.error_triggered:
            if len(self.error_triggered[error_type]):
                return

        raise AssertionError('Error of type %s not triggered' % error_type.__name__)

    def assert_no_error_triggered(self):
        if len(self.error_triggered) > 0:
            raise AssertionError('%d errors hsa been triggered while non should have' % len(self.error_triggered))          

    def clear_errors(self):
        self.error_triggered = {}

    def init_test_case(self):
        while not self.ll_rx_queue.empty():
            self.ll_rx_queue.get()

        while not self.ll_tx_queue.empty():
            self.ll_tx_queue.get()

        self.clear_errors()

    def simulate_rx_msg(self, msg):
        self.ll_rx_queue.put(msg)

    def make_flow_control_data(self, flow_status, stmin, blocksize, prefix=None):
        data = bytearray()
        if prefix is not None:
            data.extend(bytearray(prefix))
        data.extend(bytearray( [0x30 | (flow_status & 0xF), blocksize, stmin]))

        return data