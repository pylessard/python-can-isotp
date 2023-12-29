Examples
========

.. _example_transmit_can_stack_blocking_send:

Blocking transmission with python-can
-------------------------------------------

.. code-block:: python

    # In this example, we transmit a payload using a blocking send()
    import isotp
    import logging

    from can.interfaces.socketcan import SocketcanBus

    def my_error_handler(error):
        # I am called from a different thread, careful to race conditions!
        logging.warning('IsoTp error happened : %s - %s' % (error.__class__.__name__, str(error)))

    bus = SocketcanBus(channel='vcan0')
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)
    params = {
        'blocking_send' : True
    }
    stack = isotp.CanStack(bus, address=addr, error_handler=my_error_handler, params=params)

    try:
        stack.start()
        stack.send(b'Hello, this is a long payload sent in small chunks', timeout=2)    # Blocking send, raise on error
        print("Payload transmission successfully completed.")     # Success is guaranteed because send() can raise
    except isotp.BlockingSendFailure:   # Happens for any kind of failure, including timeouts
        print("Send failed")
    finally:
        stack.stop()
        bus.shutdown()

-----

.. _example_transmit_can_stack_non_blocking_send:

Non-blocking transmission with python-can
-----------------------------------------------

.. code-block:: python
   
    # In this example, we transmit a payload sing a non-blocking send()
    import isotp
    import logging
    import time

    from can.interfaces.socketcan import SocketcanBus

    def my_error_handler(error):
        # Called from a different thread, needs to be thread safe
        logging.warning('IsoTp error happened : %s - %s' % (error.__class__.__name__, str(error)))

    bus = SocketcanBus(channel='vcan0')
    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)
    stack = isotp.CanStack(bus, address=addr, error_handler=my_error_handler)

    try:
        stack.start()
        
        stack.send(b'Hello, this is a long payload sent in small chunks')    # Non-blocking send, does not raise exception.
        while stack.transmitting():
            time.sleep(stack.sleep_time())  # Recommended sleep time, optional

        print("Payload transmission done.") # May have failed, use the error_handler to know
    finally:
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

    addr = isotp.Address(isotp.AddressingMode.Normal_11bits, rxid=0x123, txid=0x456)
    layer = isotp.TransportLayer(rxfn=..., txfn=..., address=addr)
    try:
        layer.start()
        layer.send(b'Hello', isotp.TargetAddressType.Functional) # Payload must fit a Single Frame. Functional addressing only works with Single Frames
        while layer.transmitting():
            time.sleep(layer.sleep_time())
    finally:
        layer.stop()
        bus.shutdown()

-----

Defining custom rxfn and txfn
-----------------------------

In this example, we see how to configure a :class:`TransportLayer<isotp.TransportLayer>` to interact with a hardware different than python-can with a fictive API.

.. code-block:: python

    import isotp
    from typing import Optional

    def my_rxfn(timeout:float) -> Optional[isotp.CanMesage]:
        # All my_hardware_something and get_something() function are fictive of course.
        msg = my_hardware_api_recv(timeout) # Blocking read are encouraged for better timing.
        if msg is None:
            return None # Return None if no message available
        return isotp.CanMesage(arbitration_id=msg.get_id(), data=msg.get_data(), dlc=msg.get_dlc(), extended_id=msg.is_extended_id())


    def my_txfn(isotp_msg:isotp.CanMesage):
        # all set_something functions and my_hardware_something are fictive.
        msg = my_hardware_api_make_msg()
        msg.set_id(isotp_msg.arbitration_id)
        msg.set_data(isotp_msg.data)
        msg.set_dlc(isotp_msg.dlc)
        msg.set_extended_id(isotp_msg.is_extended_id)
        my_hardware_api_send(msg)

    addr = isotp.Address(isotp.AddressingMode.Normal_29bits, txid=0x123456, rxid = 0x123457)
    layer = isotp.TransportLayer(rxfn=my_rxfn, txfn=my_txfn, address=addr)
    layer.start()

    # ... rest of programs
    # ...

    layer.stop()
    my_hardware_close()

-----

Defining partial rxfn and txfn
------------------------------

If your hardware API requires some sort of handle to be given to its functions, you will need a way to pass this handle from your app down to ``rxfn`` and ``txfn``.
The :class:`TransportLayer<isotp.TransportLayer>` will call ``rxfn`` and ``txfn`` with no additional parameters, which might be an issue.

A clean way to overcome this limitation is to use a ``functools.partial`` function. 

.. code-block:: python

    import isotp
    import functools
    from typing import Optional

    # hardware_handle is passed through partial func
    def my_rxfn(hardware_handle, timeout:float) -> Optional[isotp.CanMesage]:
        msg = my_hardware_api_recv(timeout) # Blocking read are encouraged for better timing.
        if msg is None:
            return None # Return None if no message available
        return isotp.CanMesage(arbitration_id=msg.get_id(), data=msg.get_data(), dlc=msg.get_dlc(), extended_id=msg.is_extended_id())

    # hardware_handle is passed through partial func
    def my_txfn(hardware_handle, isotp_msg:isotp.CanMesage):
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
    partial_rxfn = functools.partial(my_rxfn, hardware_handle)
    partial_txfn = functools.partial(my_txfn, hardware_handle)
    layer = isotp.TransportLayer(rxfn=partial_rxfn, txfn=partial_txfn, address=addr)

    layer.start()
    # ... rest of programs
    # ...
    layer.stop()
    my_hardware_close()
