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

The CAN messages going in and out from the transport layer are defined with :class:`isotp.CanMessage<isotp.CanMessage>`. 

.. autoclass:: isotp.CanMessage

-----

Parameters
----------

The transport layer ``params`` parameter must be a dictionary with the following keys.

.. _param_stmin:

.. attribute:: stmin
   :annotation: (int)

   **default: 0**

   The single-byte Separation Time to include in the flow control message that the layer will send when receiving data. 
   Refer to ISO-15765-2 for specific values. From 1 to 127, represents milliseconds. From 0xF1 to 0xF9, represents hundreds of microseconds (100us, 200us, ..., 900us). 0 Means no timing requirements

.. _param_blocksize:

.. attribute:: blocksize
   :annotation: (int)

   **default: 8**

   The single-byte Block Size to include in the flow control message that the layer will send when receiving data.
   Represents to number of consecutive frame that a sender should send before expecting the layer to send a flow control message. 0 Means infinitely large block size (implying no flow control message)

.. _param_tx_data_length:

.. attribute:: tx_data_length
   :annotation: (int)

   **default: 8**

   The number of bytes that the Link Layer (CAN layer) can transport. This value defines the size of the outputed messages and can be any positive integer between 4 and 255. 
   It not only change the length of the data inside a transmitted CAN message, but will also affect the Data Length Code (DLC) of it.

   - If ``tx_data_length`` is between 4 and 8, the message dlc property will be equal to ``tx_data_length``
   - If ``tx_data_length`` is a valid CAN FD length (12, 16, 20, 24, 32, 48, 64) a CAN FD DLC will be used (respectively 9,10,11,12,13,14,15)
   - If ``tx_data_length`` is a non-standard value, the DLC will be set to ``None``

   This parameter was formely ``ll_data_length`` but has been renamed to explicitly indicate that it affects transmitted messages only.

.. _param_squash_stmin_requirement:

.. attribute:: squash_stmin_requirement
   :annotation: (bool)

   **default: False**

   Indicates if the layer should override the receiver separation time (stmin) when sending and try sending as fast as possible instead.
   This can be useful when the layer is running on an operating system giving low priority to your application; such as Windows that has a thread resolution of 16ms.

.. _param_rx_flowcontrol_timeout:

.. attribute:: rx_flowcontrol_timeout
   
   **default: 1000**

   The number of milliseconds to wait for a flow control frame before stopping reception and triggering a :class:`FlowControlTimeoutError<isotp.FlowControlTimeoutError>`.
   Defined as **N_BS** bs ISO-15765-2

.. _param_rx_consecutive_frame_timeout:

.. attribute:: rx_consecutive_frame_timeout
   :annotation: (int)

   **default: 1000**

   The number of milliseconds to wait for a consecutive frame before stopping reception and triggering a :class:`ConsecutiveFrameTimeoutError<isotp.ConsecutiveFrameTimeoutError>`.
   Defined as **N_CS** by ISO-15765-2

.. _param_tx_padding:

.. attribute:: tx_padding
   :annotation: (int or None)

   **default: 0**

   When not ``None`` represents the byte used for padding messages sent. No padding applied when ``None``

.. _param_wftmax:

.. attribute:: wftmax
   :annotation: (int)

   **default: 0**

   The single-byte Wait Frame Max to include in the flow control message that the layer will send when receiving data. 
   When this limits is reached, reception will stop and trigger a :class:`MaximumWaitFrameReachedError<isotp.MaximumWaitFrameReachedError>`

   A value of 0 that wait frames are not supported and none shall be sent.

.. _param_max_frame_size:

.. attribute:: max_frame_size
   :annotation: (int)

   **default: 4095**

   The maximum frame length that the stack will accept to receive. ISO-15765-2:2016 allows frames as long as 2^32-1 (4294967295 bytes). When a FirstFrame is sent with a length longer than ``max_frame_size``, the message will be ignored, a FlowControl message with FlowStaus=2 (Overflow) will be sent and a :class:`FrameTooLongError<isotp.FrameTooLongError>` will be triggered.

   This parameter mainly is a protection to avoid crashes due to lack of memory (caused by an external device).

.. _param_can_fd:

.. attribute:: can_fd
   :annotation: (bool)

   **default: False**

   Indicates that the stack is sending CAN FD frame. CAN message outputted by the transport layer will have the ``is_fd`` property set. This parameter does not need to be set in order to have a ``tx_data_length`` greater than 8; it only simplify the integration with ``python-can``.


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

.. _Errors:

Errors
------

When calling ``TransportLayer.process``, no exception should raise. Still, errors are possible and are given to an error handler provided by the user. 
An error handler should ba a callable function that expects an Exception as first parameter.

.. function:: my_error_handler(error)

   :param error: The error
   :type error: :class:`isotp.IsoTpError<isotp.IsoTpError>`

All errors inherit :class:`isotp.IsoTpError<isotp.IsoTpError>` which themselve inherits :class:`Exception<Exception>`

.. autoclass:: isotp.FlowControlTimeoutError
.. autoclass:: isotp.ConsecutiveFrameTimeoutError
.. autoclass:: isotp.InvalidCanDataError
.. autoclass:: isotp.UnexpectedFlowControlError
.. autoclass:: isotp.UnexpectedConsecutiveFrameError
.. autoclass:: isotp.ReceptionInterruptedWithSingleFrameError
.. autoclass:: isotp.ReceptionInterruptedWithFirstFrameError
.. autoclass:: isotp.WrongSequenceNumberError
.. autoclass:: isotp.UnsuportedWaitFrameError
.. autoclass:: isotp.MaximumWaitFrameReachedError
.. autoclass:: isotp.FrameTooLongError

