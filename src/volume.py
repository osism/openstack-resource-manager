# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime
import sys
from time import sleep

from dateutil import parser
from loguru import logger
import openstack
from oslo_config import cfg
from prompt_toolkit import prompt

PROJECT_NAME = "server"
CONF = cfg.CONF
opts = [
    cfg.BoolOpt("debug", help="Enable debug logging", default=False),
    cfg.StrOpt("cloud", help="Cloud name in clouds.yaml", default="service"),
]
CONF.register_cli_opts(opts)
CONF(sys.argv[1:], project=PROJECT_NAME)

SLEEP_WAIT_FOR_API = 2

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


# Connect to the OpenStack environment
cloud = openstack.connect(cloud=CONF.cloud)

# detaching
for volume in cloud.block_storage.volumes(all_projects=True, status="detaching"):
    duration = datetime.now() - parser.parse(volume.created_at)
    if duration.total_seconds() > 7200:
        logger.info(
            f"Volume {volume.id} hangs in DETACHING status for more than 2 hours"
        )
        logger.info(f"Aborting detach of attachment(s) of volume {volume.id}")
        cloud.block_storage.abort_volume_detaching(volume.id)

# creating
for volume in cloud.block_storage.volumes(all_projects=True, status="creating"):
    duration = datetime.now() - parser.parse(volume.created_at)
    if duration.total_seconds() > 7200:
        logger.info(
            f"Volume {volume.id} hangs in CREATING status for more than 2 hours"
        )
        result = prompt(f"Delete volume {volume.id} [yes/no]: ")
        if result == "yes":
            logger.info(f"Deleting volume {volume.id}")
            cloud.block_storage.delete_volume(volume.id, force=True)

# error_deleting
for volume in cloud.block_storage.volumes(all_projects=True, status="error_deleting"):
    logger.info(f"Volume {volume.id} hangs in ERROR_DELETING status")
    result = prompt(f"Retry to delete volume {volume.id} [yes/no]: ")
    if result == "yes":
        logger.info(f"Deleting volume {volume.id}")
        cloud.block_storage.delete_volume(volume.id, force=True)

# deleting
for volume in cloud.block_storage.volumes(all_projects=True, status="deleting"):
    duration = datetime.now() - parser.parse(volume.created_at)
    if duration.total_seconds() > 7200:
        logger.info(
            f"Volume {volume.id} hangs in DELETING status for more than 2 hours"
        )
        result = prompt(f"Retry deletion of volume {volume.id} [yes/no]: ")
        if result == "yes":
            logger.info(f"Deleting volume {volume.id}")
            cloud.block_storage.reset_volume_status(
                volume.id, status="available", attach_status=None, migration_status=None
            )
            sleep(SLEEP_WAIT_FOR_API)
            cloud.block_storage.delete_volume(volume.id, force=True)

# error
