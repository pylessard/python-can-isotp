Implementation
==============

This sections explains the python implementation of the IsoTP protocol.

Transport layer
---------------

Depending on your constraints, you may want to have the IsoTP protocol layer to run in Python (in the user space). For example, if you want to rely on `python-can <https://python-can.readthedocs.io/>`_ for the support of your CAN interface, you will need to run the IsoTP layer in Python.

In such case, the :class:`isotp.TransportLayer<isotp.TransportLayer>` will be the right tool. One must first define functions to access the hardware and given as parameters with ``rxfn`` and ``txfn``.

.. autoclass:: isotp.TransportLayer

If python-can must be used as CAN layer, one can use the :class:`isotp.CanStack<isotp.CanStack>` which extends the TransportLayer object with predefined functions that calls python-can. 

.. autoclass:: isotp.CanStack

-----

Parameters
----------

The transport layer ``params`` parameter must be a dictionnary with the following keys.

.. attribute:: stmin
   :annotation: (int)

   **default: 0**

   The single-byte Separation Time to include in the flow control message that the layer will send when receiving data. 
   Refer to ISO-15765-2 for specific values. From 1 to 127, represents milliseconds. From 0xF1 to 0xF9, represents hundreds of millisec (100us, 200us, ..., 900us). 0 Means no timing requirements

.. attribute:: blocksize
   :annotation: (int)

   **default: 0**

   The single-byte Block Size to include in the flow control message that the layer will send when receiving data.
   Represents to number of consecutive frame that a sender should send before expecting the layer to send a flow control message. 0 Means infinetely large block size (implying no flow control message)
     
.. attribute:: squash_stmin_requirement
   :annotation: (bool)

   **default: False**

   Indicates if the layer should override the receiver separation time (stmin) when sending and try sending as fast as possible instead.
   This can be useful when the layer is running on an operating system giving low priority to your application; such as Windows that has a thread resolution of 16ms.
     
.. attribute:: rx_flowcontrol_timeout
   
   **default: 1000**

   The number of milliseconds to wait for a **flow control frame** before stopping reception and triggering a :class:`FlowControlTimeoutError<isotp.FlowControlTimeoutError>`.
   Defined as **N_BS** bys ISO-15765-2

.. attribute:: rx_consecutive_frame_timeout
   :annotation: (int)

   **default: 1000**

   The number of milliseconds to wait for a **consecutive frame** before stopping reception and triggering a :class:`ConsecutiveFrameTimeoutError<isotp.ConsecutiveFrameTimeoutError>`.
   Defined as **N_CS** bys ISO-15765-2

.. attribute:: tx_padding
   :annotation: (int or None)

   **default: 0**

   When not ``None`` represents the byte used for padding messages sent. No padding applied when ``None``

.. attribute:: wftmax
   :annotation: (int)

   **default: 0**

   The single-byte Wait Frame Max to include in the flow control message that the layer will send when receiving data. 
   When this limits is reached, reception will stop and an the :class:`MaximumWaitFrameReachedError<isotp.MaximumWaitFrameReachedError>`

   A value of 0 means no limits

-----

Usage
-----

The :class:`isotp.TransportLayer<isotp.TransportLayer>` object has the following methods

.. automethod:: isotp.TransportLayer.send
.. automethod:: isotp.TransportLayer.recv
.. automethod:: isotp.TransportLayer.available
.. automethod:: isotp.TransportLayer.transmitting
.. automethod:: isotp.TransportLayer.set_address
.. automethod:: isotp.TransportLayer.reset
.. automethod:: isotp.TransportLayer.process
.. automethod:: isotp.TransportLayer.sleep_time

-----
