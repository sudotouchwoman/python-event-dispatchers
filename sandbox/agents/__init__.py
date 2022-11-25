import logging


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    fmt="[%(asctime)s]::[%(name)s]::[%(threadName)s] - %(message)s",
    datefmt="%H:%M:%S",
)
handler.setFormatter(formatter)
log.addHandler(handler)
