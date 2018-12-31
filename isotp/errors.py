
class IsoTpError(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

class FlowControlTimeoutError(IsoTpError):
    pass
class ConsecutiveFrameTimeoutError(IsoTpError):
    pass
class InvalidCanDataError(IsoTpError):
    pass
class UnexpectedFlowControlError(IsoTpError):
    pass
class UnexpectedConsecutiveFrameError(IsoTpError):
    pass
class ReceptionInterruptedWithSingleFrameError(IsoTpError):
    pass
class ReceptionInterruptedWithFirstFrameError(IsoTpError):
    pass
class WrongSequenceNumberError(IsoTpError):
    pass
class UnsuportedWaitFrameError(IsoTpError):
    pass
class MaximumWaitFrameReachedError(IsoTpError):
    pass