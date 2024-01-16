Python support for IsoTP Transport protocol (ISO-15765) 
=======================================================

.. toctree::
   :hidden:

   Home <self>
   isotp/implementation
   isotp/socket
   isotp/addressing
   isotp/examples

This project is a Python package meant to provide support for IsoTP (ISO-15765) protocol written in Python 3. The code is published under MIT license on GitHub (`pylessard/python-can-isotp <https://github.com/pylessard/python-can-isotp>`_).

This package contains a Python implementation of the protocol in pure python that works in the user space that may or may not be coupled with `python-can <https://python-can.readthedocs.io>`_. 
It also contains a wrapper for a simplified usage of the `Linux SocketCAN IsoTP kernel module <https://github.com/hartkopp/can-isotp>`_

.. note:: You are looking at the isotp v2.x documentation. The legacy `v1.x documentation <https://can-isotp.readthedocs.io/en/v1.x>`_ is still online.

v2.x changes
------------

V2.x addressed several flaws that were present in v1.x. The main change is regarding the timing capabilities of the module. V2.x can achieve much better timing performance than
the previous version by performing blocking IO operations. The CanStack object is also able to use the python-can Notifier which behave better performance-wise

Here is the major API changes to v2.x that might make an application designed with v1.x to break

    - The Transport Layer timing is handled into an internal thread, removing the need for the user to periodically call the ``process()`` function. 
    - The user provided CAN layer receive function ``rxfn`` is expected be blocking for better performance (using the OS asynchronous read capabilities). Non-blocking ``rxfn`` are possible, but the execution of the transport layer will be throttled by calls to ``sleeps()`` to avoid bloating the CPU usage; possibly degrading overall timing
    - Some parameter have been modified.

        1. ``squash_stmin_requirement`` has been removed and replaced by ``override_receiver_stmin``
        2. Deprecated ``ll_data_length`` parameter is not supported anymore. Replaced by ``tx_data_length``
        
    - The transport layer can perform blocking sends, allowing an UDS layer to better handle its timeouts (P2/P2* vs P6 timeouts)
    - Some methods dedicated to internal usage have been prefixed with an underscore (``_``) to indicates that they are internals
    - The ``isotp.socket.recv()`` method does not return ``None`` on timeout anymore. 
        The API now comply with the Python socket API and will raise the proper exception in case of timeout.
    - ``isotp.socket.bind`` now requires an ``isotp.Address`` object and is no more backward compatible with old interface
    - The error handler is called from a different thread
    - The :class:`TransportLayer<isotp.TransportLayer>` object is now an extension of the legacy v1.x TransportLayer, which has been renamed to ``TransportLayerLogic``. See :ref:`Backward Compatibility<backward_compatibility>` and :ref:`Legacy Methods<legacy_methods>`

On top of that, some improvement makes v2.x preferable over v1.x

    - The :class:`NotifierBasedCanStack<isotp.NotifierBasedCanStack>` object has been introduced and uses a notifier instead of calling ``bus.recv()``, solving the popular issue of a CanStack depleting the receive queue and starving other modules from their incoming messages
    - :ref:`Asymmetric addressing<asymmetric_addresses>` is possible (different address for reception than transmission)
    - Sending data with a generator is now possible, accommodating use cases with large payloads
    - The module is fully type-hinted
    - It is possible to use a busy-wait to achieve even more precise timings. See the :ref:`wait_func parameter<param_wait_func>`

