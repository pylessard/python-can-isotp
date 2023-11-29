Examples
========

.. _example_transmit_can_stack:

Basic transmission with python-can
----------------------------------

.. code-block:: python
   
    import isotp
    import logging
    import time

    from can.interfaces.vector import VectorBus

    def my_error_handler(error):
        # Called by a different thread. Make it thread safe.
        logging.warning('IsoTp error happened : %s - %s' % (error.__class__.__name__, str(error)))

    bus = VectorBus(channel=0, bitrate=500000)
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)

    stack = isotp.CanStack(bus, address=addr, error_handler=my_error_handler)
    stack.start()
    stack.send(b'Hello, this is a long payload sent in small chunks')

    while stack.transmitting():
        time.sleep(stack.sleep_time())

    print("Payload transmission done.")
    stack.stop()
    bus.shutdown()

-----

.. _example_transmit_can_stack_blocking_send:

Basic blocking transmission
----------------------------------
.. code-block:: python
   
    import isotp
    import logging
    import time

    from can.interfaces.vector import VectorBus

    def my_error_handler(error):
        # Called by a different thread. Make it thread safe.
        logging.warning('IsoTp error happened : %s - %s' % (error.__class__.__name__, str(error)))

    bus = SocketcanBus(channel='vcan0')
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)

    params = {
        'blocking_send' : True
    }

    stack = isotp.CanStack(bus, address=addr, error_handler=my_error_handler, params=params)
    stack.start()
    try:
        stack.send(b'Hello, this is a long payload sent in small chunks', timeout=1.0)
    except isotp.BlockingSendFailure:
        # Catches all failure, including isotp.BlockingSendTimeout
        print("Failed to transmit")
    print("Payload transmission done.")
    stack.stop()
    bus.shutdown()

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

------

Sending with functional addressing (broadcast)
----------------------------------------------

.. code-block:: python

   import isotp
   import time

   from can.interfaces.vector import VectorBus

   bus = VectorBus(channel=0, bitrate=500000)
   addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)
   stack = isotp.CanStack(bus, address=addr)
   stack.send(b'Hello', isotp.TargetAddressType.Functional) # Payload must fit a Single Frame. Functional addressing only works with Single Frames

   while stack.transmitting():
      time.sleep(stack.sleep_time())

   bus.shutdown()

-----

Defining custom rxfn and txfn
-----------------------------

In this example, we see how to configure a :class:`TransportLayer<isotp.TransportLayer>` to interact with a hardware different than python-can with a fictive API.

.. code-block:: python

   import isotp

   def my_rxfn():
       # All my_hardware_something and get_something() function are fictive of course.
       msg = my_hardware_api_recv()
       return isotp.CanMesage(arbitration_id=msg.get_id(), data=msg.get_data(), dlc=msg.get_dlc(), extended_id=msg.is_extended_id())


   def my_txfn(isotp_msg):
       # all set_something functions and my_hardware_something are fictive.
       msg = my_hardware_api_make_msg()
       msg.set_id(isotp_msg.arbitration_id)
       msg.set_data(isotp_msg.data)
       msg.set_dlc(isotp_msg.dlc)
       msg.set_extended_id(isotp_msg.is_extended_id)
       my_hardware_api_send(msg)

   addr = isotp.Address(isotp.AddressingMode.Normal_29bits, txid=0x123456, rxid = 0x123457)
   layer = isotp.TransportLayer(rxfn=my_rxfn, txfn=my_txfn, address=addr)

   # ... rest of programs
   # ...

   my_hardware_close()

-----

Defining partial rxfn and txfn
------------------------------

If your hardware API requires some sort of handle to be given to its functions, you will need a way to pass this handle from your app down to ``rxfn`` and ``txfn``.
The :class:`TransportLayer<isotp.TransportLayer>` will call ``rxfn`` and ``txfn`` with no additional parameters, which might be an issue.

A clean way to overcome this limitation is to use a ``functools.partial`` function. 

.. code-block:: python

   import isotp
   from functools import partial   # Allow partial functions

   # hardware_handle is passed through partial func
   def my_rxfn(hardware_handle):
       msg = my_hardware_api_recv(hardware_handle)
       return isotp.CanMesage(arbitration_id=msg.get_id(), data=msg.get_data(), dlc=msg.get_dlc(), extended_id=msg.is_extended_id())

   # hardware_handle is passed through partial func
   def my_txfn(hardware_handle, isotp_msg):
       # all set_something functions and my_hardware_something are fictive.
       msg = my_hardware_api_make_msg()
       msg.set_id(isotp_msg.arbitration_id)
       msg.set_data(isotp_msg.data)
       msg.set_dlc(isotp_msg.dlc)
       msg.set_extended_id(isotp_msg.is_extended_id)
       my_hardware_api_send(hardware_handle, msg)

   hardware_handle = my_hardware_open()    # Fictive handle mechanism
   addr = isotp.Address(isotp.AddressingMode.Normal_29bits, txid=0x123456, rxid = 0x123457)
   # This is where the magic happens
   layer = isotp.TransportLayer(rxfn=partial(my_rxfn, hardware_handle), txfn=partial(my_txfn, hardware_handle), address=addr)

   # ... rest of programs
   # ...

   my_hardware_close()
