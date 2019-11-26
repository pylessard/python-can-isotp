
class IsoTpError(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

class FlowControlTimeoutError(IsoTpError):
    """
    Happens when the senders fails to sends a Flow Control message in time. 
    Refer to TransportLayer parameter :ref:`rx_flowcontrol_timeout<param_rx_flowcontrol_timeout>`
    """
    pass
class ConsecutiveFrameTimeoutError(IsoTpError):
    """
    Happens when the senders fails to sends a Consecutive Frame message in time. 
    Refer to TransportLayer parameter :ref:`rx_consecutive_frame_timeout<param_rx_consecutive_frame_timeout>`
    """
    pass
class InvalidCanDataError(IsoTpError):
    """
    Happens when a CAN message that cannot be decoded as valid First Frame, Consecutive Frame, Single Frame or Flow Control PDU is received.
    """
    pass
class UnexpectedFlowControlError(IsoTpError):
    """
    Happens when a Flow Control message is received and was not expected
    """
    pass
class UnexpectedConsecutiveFrameError(IsoTpError):
    """
    Happens when a Consecutive Frame message is received and was not expected
    """
    pass
class ReceptionInterruptedWithSingleFrameError(IsoTpError):
    """
    Happens when the reception of a multi packet message reception is interrupted with a new Single Frame PDU.
    """
    pass
class ReceptionInterruptedWithFirstFrameError(IsoTpError):
    """
    Happens when the reception of a multi packet message reception is interrupted with a new First Frame PDU.
    """
    pass
class WrongSequenceNumberError(IsoTpError):
    """
    Happens when a consecutive frame is received with a wrong sequence number.
    """
    pass
class UnsuportedWaitFrameError(IsoTpError):
    """
    Happens when a Flow Control PDU with FlowStatus=Wait is received and :ref:`wftmax<param_wftmax>` is set to 0
    """
    pass
class MaximumWaitFrameReachedError(IsoTpError):
    """
    Happens when too much Flow Control PDU with FlowStatus=Wait is received. Refer to :ref:`wftmax<param_wftmax>`
    """
    pass
class FrameTooLongError(IsoTpError):
    """
    Happens when a FirstFrame with a length (FF_DL) longer than :ref:`max_frame_size<param_max_frame_size>` is received. 
    """
    pass
class ChangingInvalidRXDLError(IsoTpError):
    """
    Happens when a ConsecutiveFrame is received with a length smaller than ``RX_DL`` (size of first frame) without being the last message of the IsoTP frame.
    """
    pass
class MissingEscapeSequenceError(IsoTpError):
    """
    Happens when a SingleFrame with length (CAN_DL) greater than 8 bytes is received and the length of the payload (SF_DL) is encoded in the first byte, which is forbidden by ISO-15765-2
    """
    pass
class InvalidCanFdFirstFrameRXDL(IsoTpError):
    """
    Happens when a FirstFrame is received with missing data; In other words when CAN_DL is smaller than the deduced RX_DL. The sender did not optimized the capacity usage of the CAN message.
    """
    pass
class OverflowError(IsoTpError):
    """
    Happens when the TransportLayer receive a FlowControl PDU with a FlowStatus=Overflow (2). In this event, the transmission is stopped.
    """
    pass