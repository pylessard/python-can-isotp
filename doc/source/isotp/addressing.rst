Addressing
==========

ISO-15765 defines several addressing modes and this module supports them all. Depending on the addressing mode, the source/target addresses will be defined in a different way.
An IsoTP address is represented by the :class:`isotp.Address<isotp.Address>` object.

------

Definitions
-----------

.. autoclass:: isotp.Address

.. autoclass:: isotp.AddressingMode
   :members: 
   :undoc-members:
   :member-order: bysource
   :exclude-members: get_name

.. autoclass:: isotp.TargetAddressType
   :members: 
   :member-order: bysource
   :undoc-members:

-----

Addressing modes
----------------

Normal addressing
#################

In normal addressing, a CAN arbitration ID is selected for transmission (txid) and reception (rxid).  

Condition to receive a message (discarded if not met): 
 - Message arbitration ID must match receiver ``rxid``

This mode is possible in both legislated 11-bits and extended 29-bits CAN identifiers

Example : 
 - rxid : 0x123 
 - txid : 0x456

::

   // Reception of a 10 bytes payload
   0x123    [8]   10 0A 00 01 02 03 04    // First frame
   0x456    [4]   03 00 08 00             // Flow control
   0x123    [6]   21 05 06 07 08 09       // Consecutive frame

-----

Normal fixed addressing
#######################

In normal fixed addressing, a ``target_address`` and a ``source_address`` is encoded in the CAN arbitration ID. 

Condition to receive a message (discarded if not met): 
 - Message Target Address must match receiver ``source_address``
 - Message Source Address must match the receiver ``target_address``

This mode is only possible with extended 29-bits CAN identifiers.

A message arbitration ID sent in normal fixed addressing is encoded like the following (with <TA>=Target Address and <SA>=Source Address) 

   - 1-to-1 communication (target_address_type = Physical) :  0x18DA<TA><SA>
   - 1-to-n communication (target_address_type = Functional) :  0x18DB<TA><SA>

Example : 
 - source_address : 0x55
 - target_address : 0xAA

::

   // Reception of a 10 bytes payload
   0x18DA55AA    [8]   10 0A 00 01 02 03 04  // First frame
   0x18DAAA55    [4]   03 00 08 00           // Flow control
   0x18DA55AA    [6]   21 05 06 07 08 09     // Consecutive frame

-----

Extended addressing
###################

In extended addressing, ``rxid`` and ``txid`` must be set just like normal addressing, but an additional ``source_address`` and ``target_address`` must be given. The additional addresses will be added as the first byte of each CAN message sent. 

Condition to receive a message (discarded if not met): 
 - Message arbitration ID must match receiver ``rxid``
 - Payload first byte must match receiver ``source_address``

This mode is possible in both legislated 11-bits and extended 29-bits CAN identifiers

Example : 
 - rxid : 0x123 
 - txid : 0x456
 - source_address : 0x55
 - target_address : 0xAA

::

   // Reception of a 10 bytes payload
   0x123    [8]   55 10 0A 00 01 02 03    // First frame
   0x456    [5]   AA 03 00 08 00          // Flow control
   0x123    [8]   55 21 04 05 06 07 08 09 // consecutive frame

-----

Mixed addressing - 11 bits
##########################

Mixed addressing (11 bits) is a mix of normal addressing and extended addressing. The payload prefix is called ``address_extension``

When used in legislated 11-bits CAN, Mixed addressing behaves like extended addressing with both source_address and target_address being defined by ``address_extension``

Condition to receive a message (discarded if not met): 
 - Message arbitration ID must match receiver ``rxid``
 - Payload first byte must match receiver ``address_extension``

Example : 
 - rxid : 0x123 
 - txid : 0x456
 - address_extension : 0x99

::

   // Reception of a 10 bytes payload
   0x123    [8]   99 10 0A 00 01 02 03    // First frame
   0x456    [5]   99 03 00 08 00          // Flow control
   0x123    [8]   99 21 04 05 06 07 08 09 // consecutive frame


-----

Mixed addressing - 29 bits
##########################

Mixed addressing (29 bits) is a mix of normal fixed addressing and extended addressing. The payload prefix is called ``address_extension``

A message arbitration ID sent in 29 bits mixed addressing is encoded like the following (with <TA>=Target Address and <SA>=Source Address) 

   - 1-to-1 communication (target_address_type = Physical) :  0x18CE<TA><SA>
   - 1-to-n communication (target_address_type = Functional) :  0x18CD<TA><SA>

Condition to receive a message (discarded if not met): 
 - Message Target Address must match receiver ``source_address``
 - Message Source Address must match the receiver ``target_address``
 - Payload first byte must match receiver ``address_extension``


Example : 
 - source_address : 0x55
 - target_address : 0xAA
 - address_extension : 0x99

::

   // Reception of a 10 bytes payload
   0x18CE55AA    [8]   99 10 0A 00 01 02 03    // First frame
   0x18CEAA55    [5]   99 03 00 08 00          // Flow control
   0x18CE55AA    [8]   99 21 04 05 06 07 08 09 // consecutive frame
