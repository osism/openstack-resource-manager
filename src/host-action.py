# SPDX-License-Identifier: AGPL-3.0-or-later

import time
import sys

from loguru import logger
import openstack
from oslo_config import cfg
from tabulate import tabulate
from prompt_toolkit import prompt

PROJECT_NAME = "host-action"
CONF = cfg.CONF
opts = [
    cfg.BoolOpt("debug", help="Enable debug logging", default=False),
    cfg.BoolOpt("wait", help="Wait for completion of action", default=True),
    cfg.StrOpt("action", help="Action", default="list"),
    cfg.StrOpt("cloud", help="Cloud name in clouds.yaml", default="service"),
    cfg.StrOpt("host", help="Compute node", default=""),
    cfg.StrOpt("input", help="Additional input", default=""),
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

result = []

for server in cloud.compute.servers(all_projects=True, host=CONF.host):
    result.append([server.id, server.name, server.status])

print(
    tabulate(
        result,
        headers=["ID", "Name", "Status"],
        tablefmt="psql",
    )
)

if CONF.action:
    if CONF.action == "live-migrate":
        for server in result:
            if server[2] not in ["ACTIVE"]:
                logger.info(
                    f"{server[0]} ({server[1]}) in status {server[2]} cannot be live migrated"
                )
                continue

            answer = prompt(f"Live migrate server {server[0]} ({server[1]}) [yes/no]: ")
            if answer in ["yes", "y"]:
                logger.info(f"Live migrating server {server[0]}")
                cloud.compute.live_migrate_server(
                    server[0], host=CONF.input, block_migration="auto"
                )

                if CONF.wait:
                    inner_wait = True
                    while inner_wait:
                        time.sleep(2)
                        s = cloud.compute.get_server(server[0])
                        if s.status in ["MIGRATING"]:
                            logger.info(
                                f"Live migration of {server[0]} ({server[1]}) is still in progress"
                            )
                            inner_wait = True
                        else:
                            inner_wait = False
    elif CONF.action == "stop":
        for server in result:
            if server[2] not in ["ACTIVE"]:
                logger.info(
                    f"{server[0]} ({server[1]}) in status {server[2]} cannot be stopped"
                )
                continue
            answer = prompt(f"Stop server {server[0]} ({server[1]}) [yes/no]: ")
            if answer in ["yes", "y"]:
                logger.info(f"Stopping server {server[0]}")
                cloud.compute.stop_server(server[0])
