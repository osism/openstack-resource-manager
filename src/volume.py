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

# error
