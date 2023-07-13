import sys
from time import sleep

from loguru import logger
import openstack
from oslo_config import cfg

PROJECT_NAME = "amphora"
CONF = cfg.CONF
opts = [
    cfg.BoolOpt("debug", help="Enable debug logging", default=False),
    cfg.BoolOpt("restore", help="Restore all amphorae in state ERROR", default=False),
    cfg.BoolOpt("rotate", help="Rotate all amphorae", default=False),
    cfg.StrOpt("cloud", help="Cloud name in clouds.yaml", default="service"),
]
CONF.register_cli_opts(opts)
CONF(sys.argv[1:], project=PROJECT_NAME)

SLEEP_WAIT_FOR_AMPHORA_BOOT = 5
TIMEOUT_WAIT_FOR_AMPHORA_BOOT = 120

SLEEP_WAIT_FOR_AMPHORA_DELETE = 5
TIMEOUT_WAIT_FOR_AMPHORA_DELETE = 60

if CONF.debug:
    level = "DEBUG"
else:
    level = "INFO"

log_fmt = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<level>{message}</level>"
)

logger.remove()
logger.add(sys.stderr, format=log_fmt, level=level, colorize=True)


def wait_for_amphora_boot(loadbalancer_id):
    global cloud

    logger.info(
        f"Wait up to {TIMEOUT_WAIT_FOR_AMPHORA_BOOT} seconds for amphora boot of loadbalancer {loadbalancer_id}"
    )

    i = TIMEOUT_WAIT_FOR_AMPHORA_BOOT / SLEEP_WAIT_FOR_AMPHORA_BOOT

    while i:
        amphorae = cloud.load_balancer.amphorae(
            loadbalancer_id=amphora.loadbalancer_id, status="BOOTING"
        )
        if not [1 for x in amphorae]:
            break
        i = i - 1
        sleep(SLEEP_WAIT_FOR_AMPHORA_BOOT)


def wait_for_amphora_delete(loadbalancer_id):
    global cloud

    logger.info(
        f"Wait up to {TIMEOUT_WAIT_FOR_AMPHORA_DELETE} seconds for amphora delete of loadbalancer {loadbalancer_id}"
    )

    i = TIMEOUT_WAIT_FOR_AMPHORA_DELETE / SLEEP_WAIT_FOR_AMPHORA_DELETE

    while i:
        amphorae = cloud.load_balancer.amphorae(
            loadbalancer_id=amphora.loadbalancer_id, status="PENDING_DELETE"
        )
        if not [1 for x in amphorae]:
            break
        i = i - 1
        sleep(SLEEP_WAIT_FOR_AMPHORA_DELETE)


# Connect to the OpenStack environment
cloud = openstack.connect(cloud=CONF.cloud)

# Restore all amphorae in state ERROR
if CONF.restore:
    for amphora in cloud.load_balancer.amphorae(status="ERROR"):
        logger.info(
            f"Amphora {amphora.id} of loadbalancer {amphora.loadbalancer_id} is in state ERROR, trigger failover"
        )
        cloud.load_balancer.failover_amphora(amphora.id)
        sleep(10)  # wait for the octavia API

        wait_for_amphora_boot(amphora.loadbalancer_id)
        wait_for_amphora_delete(amphora.loadbalancer_id)

# Rotate all amphorae
if CONF.rotate:
    for amphora in cloud.load_balancer.amphorae(status="ALLOCATED"):
        logger.info(f"Amphora {amphora.id} is rotated by a failover")

        cloud.load_balancer.failover_amphora(amphora.id)
        sleep(10)  # wait for the octavia API

        wait_for_amphora_boot(amphora.loadbalancer_id)
        wait_for_amphora_delete(amphora.loadbalancer_id)
