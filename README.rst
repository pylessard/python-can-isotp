python-can-isotp
================

What it is
----------

A Python wrapper helping the use of `can-isotp Loadable Kernel Module <https://github.com/hartkopp/can-isotp>`_  extending SocketCAN under Linux.
It provides a friendly and pythonic interface to interact with SocketCAN using the ISO-TP (ISO-15765-2) protocol.

What it's not
-------------

 - An implementation of the ISO-TP protocol. It simplifies the access to the already available features within Python and your operating system
 - A portable module. It is designed to work under Linux only.
 - A way to magically do ISO-TP regardless of your environment. You need to load a module into your Linux kernel before using this. Otherwise, your OS will deny the creation of the socket.
 - A revolutionary module. It just makes the syntax easier :)
 
Why is it differents from other projects
----------------------------------------

Other Python libraries enabling the use of ISO-TP protocol makes an implementation of the standard in Python, in the user space.
As mentioned by the authors of SocketCAN in their documentation, this approach has many downsides, mainly when comes to respecting the protocol timings.

The best way do ISO-TP communication is within the kernel space, just like `hartkopp/can-isotp <https://github.com/hartkopp/can-isotp>`_ module does by using a socket interface following the mentality of SocketCAN. The well known duality between complexity and flexibility makes the usage of sockets onerous and non-intuitive to the uninitiated. This is where this project becomes handy, it wraps the socket object so that a programmer can configure and use it quickly, in an intuitive way.

Also, it will tells you if you do something wrong, like setting a socket options after binding the socket to the addresse. The native implementation will silently ignore the options, which can causes some headaches!

Troubleshooting
---------------

 - **My socket module does not include the `CAN_ISOTP` constant**
 
That means that your Python version does not include support for ISOTP protocol. It should be included starting from Python 3.7, under Linux build only.

 - **When I create the socket, I get `OSError [errno 19] : Protocol not supported`.**
 
The Loadable Kernel Module is not loaded in your Linux kernel. Follow the steps given it the module repository. You needs to compile the module, install the `.ko` file and then run `modprobe can-isotp` as Super User. Then your OS will accept to create a ISO-TP sockets.

Examples
--------

Without this project
####################

.. code-block:: python

   SOL_CAN_ISOTP = 106 # These constants exist in the module header, not in Python.
   CAN_ISOTP_RECV_FC = 2
   # Many more exists.

   import socket
   import struct

   s = socket.socket(socket.AF_CAN, socket.SOCK_DGRAM, socket.CAN_ISOTP)
   s2 = socket.socket(socket.AF_CAN, socket.SOCK_DGRAM, socket.CAN_ISOTP)
   # Configuring the sockets with ugly struct.pack() that requires knowledge of the LKM structure
   s.setsockopt(SOL_CAN_ISOTP, CAN_ISOTP_RECV_FC, struct.pack("=BBB", 0x10, 3,0)) #bs, stmin, wftmax
   #s.setsockopt(SOL_CAN_ISOTP, CAN_ISOTP_OPTS, struct.pack(...))
   #s.setsockopt(SOL_CAN_ISOTP, CAN_ISOTP_LL_OPTS, struct.pack(...))

   s.bind(("vcan0", 0x123, 0x456)) #rxid, txid with confusing order.
   s2.bind(("vcan0", 0x456, 0x123)) #rxid, txid
   s2.send(b"Hello, this is a long payload sent in small chunks of 8 bytes.")
   print(s.recv(4095))

With this project
-----------------

.. code-block:: python

   import isotp

   s = isotp.socket()
   s2 = isotp.socket()
   # Configuring the sockets.
   s.set_fc_opts(stmin=5, bs=10)
   #s.set_general_opts(...)
   #s.set_ll_opts(...)

   s.bind("vcan0" rxid=0x123 txid=0x456)  # We love named parameters!
   s2.bind("vcan0", rxid=0x456, txid=0x123)
   s2.send(b"Hello, this is a long payload sent in small chunks of 8 bytes.")
   print(s.recv()) 

Don't like playing with a simili-socket ?
-----------------------------------------

You don't want to reinvent the wheel by using a fake socket object, but still would like to simplify your work?
Say no more, you can use some helpers availables in the `isotp` module.

.. code-block:: python

   import isotp
   import socket
   s = socket.socket(socket.AF_CAN, socket.SOCK_DGRAM, socket.CAN_ISOTP) # native socket.
   isotp.opts.flowcontrol.write(s, stmin=5)
   isotp.opts.general.write(optflags = isotp.opts.flags.CAN_ISOTP_TX_PADDING |  isotp.opts.flags.CAN_ISOTP_RX_PADDING)
   s.bind(("vcan0", 0x123, 0x456))

Or you can access the native socket within the wrapper

.. code-block:: python

   import isotp
   s = isotp.socket()
   s.bind("vcan0", rxid=0x123, txid=0x456)
   print(s._socket.getsockname())
