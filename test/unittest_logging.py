import logging
import isotp

logger = logging.getLogger(isotp.TransportLayer.LOGGER_NAME)
formatter = logging.Formatter('(%(relativeCreated)d) %(message)s')
h = logging.StreamHandler()
h.setFormatter(formatter)
logger.addHandler(h)
logger.setLevel(level=logging.DEBUG)
logger.disabled = True
