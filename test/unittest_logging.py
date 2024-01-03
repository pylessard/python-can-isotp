import logging
import isotp

logger = logging.getLogger(isotp.TransportLayer.LOGGER_NAME)
formatter = logging.Formatter('(%(relativeCreated)d) [%(name)s] %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(level=logging.DEBUG)
logger.disabled = True


def configure_transport_layer(layer: isotp.TransportLayer):
    layer.logger.addHandler(handler)
    layer.logger.disabled = logger.disabled
    layer.logger.setLevel(logger.getEffectiveLevel())
