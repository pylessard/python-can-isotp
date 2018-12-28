import logging
import isotp

logger = logging.getLogger(isotp.TransportLayer.LOGGER_NAME)
logger.addHandler(logging.StreamHandler())
logger.setLevel(level=logging.DEBUG)
logger.disabled = True