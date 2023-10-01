# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime
import sys
from time import sleep

from dateutil import parser
from loguru import logger
import openstack
from oslo_config import cfg

PROJECT_NAME = "amphora"
CONF = cfg.CONF
opts = [
    cfg.BoolOpt("debug", help="Enable debug logging", default=False),
    cfg.BoolOpt("force", help="Force rotation of amphorae", default=False),
    cfg.BoolOpt("restore", help="Restore all amphorae in state ERROR", default=False),
    cfg.BoolOpt("rotate", help="Rotate all amphorae older than 30 days", default=False),
    cfg.StrOpt("cloud", help="Cloud name in clouds.yaml", default="service"),
    cfg.StrOpt("loadbalancer", help="Loadbalancer ID", default=None),
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
            loadbalancer_id=loadbalancer_id, status="BOOTING"
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
            loadbalancer_id=loadbalancer_id, status="PENDING_DELETE"
        )
        if not [1 for x in amphorae]:
            break
        i = i - 1
        sleep(SLEEP_WAIT_FOR_AMPHORA_DELETE)


def restore(loadbalancer_id: str):
    if loadbalancer_id:
        result = cloud.load_balancer.amphorae(
            status="ERROR", loadbalancer_id=loadbalancer_id
        )
    else:
        result = cloud.load_balancer.amphorae(status="ERROR")

    for amphora in result:
        logger.info(
            f"Amphora {amphora.id} of loadbalancer {amphora.loadbalancer_id} is in state ERROR, trigger amphora failover"
        )
        cloud.load_balancer.failover_amphora(amphora.id)
        sleep(10)  # wait for the octavia API

        wait_for_amphora_boot(amphora.loadbalancer_id)
        wait_for_amphora_delete(amphora.loadbalancer_id)


def rotate(loadbalancer_id: str):
    done = []

    if loadbalancer_id:
        result = cloud.load_balancer.amphorae(
            status="ALLOCATED", loadbalancer_id=loadbalancer_id
        )
    else:
        result = cloud.load_balancer.amphorae(status="ALLOCATED")

    for amphora in result:
        rotate = False

        if amphora.loadbalancer_id in done:
            next

        duration = datetime.now() - parser.parse(amphora.created_at)
        if duration.total_seconds() > 2592000:  # 30 days
            logger.info(f"Amphora {amphora.id} is older than 30 days")
            rotate = True
        elif CONF.force:
            logger.info(f"Force rotation of Amphora {amphora.id}")
            rotate = True
        else:
            next

        logger.info(
            f"Amphora {amphora.id} of loadbalancer {amphora.loadbalancer_id} is rotated by a loadbalancer failover"
        )

        try:
            cloud.load_balancer.failover_load_balancer(amphora.loadbalancer_id)
            sleep(10)  # wait for the octavia API

            done.append(amphora.loadbalancer_id)

            wait_for_amphora_boot(amphora.loadbalancer_id)
            wait_for_amphora_delete(amphora.loadbalancer_id)
        except openstack.exceptions.ConflictException:
            pass


# Connect to the OpenStack environment
cloud = openstack.connect(cloud=CONF.cloud)

# Restore all amphorae in state ERROR
if CONF.restore:
    restore(CONF.loadbalancer)

# Rotate all amphorae
if CONF.rotate:
    rotate(CONF.loadbalancer)
