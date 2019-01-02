Examples
========

.. _example_transmit_no_thread_can_stack:

Basic transmission with python-can
----------------------------------

.. code-block:: python
   
   import isotp
   import logging
   import time

   from can.interfaces.vector import VectorBus

   def my_error_handler(error):
      logging.warning('IsoTp error happened : %s - %s' % (error.__class__.__name__, str(error)))

   bus = VectorBus(channel=0, bitrate=500000)
   addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)

   stack = isotp.CanStack(bus, address=addr, error_handler=my_error_handler)
   stack.send(b'Hello, this is a long payload sent in small chunks')

   while stack.transmitting():
      stack.process()
      time.sleep(stack.sleep_time())

   print("Payload tranmission done.")

   bus.shutdown()

-----

.. _example_receive_threaded_can_stack:

Threaded reception with python-can
----------------------------------

.. code-block:: python
   
   import isotp
   import logging
   import time
   import threading

   from can.interfaces.socketcan import SocketcanBus

   class ThreadedApp:
      def __init__(self):
         self.exit_requested = False
         self.bus = SocketcanBus(channel='vcan0')
         addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)
         self.stack = isotp.CanStack(self.bus, address=addr, error_handler=self.my_error_handler)

      def start(self):
         self.exit_requested = False
         self.thread = threading.Thread(target = self.thread_task)
         self.thread.start() 

      def stop(self):
         self.exit_requested = True
         if self.thread.isAlive():
            self.thread.join() 

      def my_error_handler(self, error):
         logging.warning('IsoTp error happened : %s - %s' % (error.__class__.__name__, str(error)))

      def thread_task(self):
         while self.exit_requested == False:
            self.stack.process()                # Non-blocking
            time.sleep(self.stack.sleep_time()) # Variable sleep time based on state machine state

      def shutdown(self):
         self.stop()
         self.bus.shutdown()

   if __name__ == '__main__':
      app = ThreadedApp()
      app.start()

      print('Waiting for payload - maximum 5 sec')
      t1 = time.time()
      while time.time() - t1 < 5:
         if app.stack.available():
            payload = app.stack.recv()
            print("Received payload : %s" % (payload))
            break
         time.sleep(0.2)

      print("Exiting")
      app.shutdown()

-----

.. _example_addressing:

Different type of addresses
---------------------------

.. code-block:: python
   
   import isotp

   isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)
   isotp.Address(isotp.AddressingMode.Normal_29bits, rxid=0x123456, txid=0x789ABC)
   isotp.Address(isotp.AddressingMode.NormalFixed_29bits, source_address=0x11, target_address=0x22)
   isotp.Address(isotp.AddressingMode.Extended_11bits, rxid=0x123, txid=0x456, source_address=0x55, target_address=0xAA)
   isotp.Address(isotp.AddressingMode.Extended_29bits, rxid=0x123456, txid=0x789ABC, source_address=0x55, target_address=0xAA)
   isotp.Address(isotp.AddressingMode.Mixed_11bits, rxid=0x123, txid=0x456, address_extension=0x99)   
   isotp.Address(isotp.AddressingMode.Mixed_29bits, source_address=0x11, target_address=0x22, address_extension=0x99)


