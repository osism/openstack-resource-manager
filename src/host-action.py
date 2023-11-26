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
    cfg.BoolOpt("disable", help="Disable the host", default=False),
    cfg.BoolOpt("wait", help="Wait for completion of action", default=True),
    cfg.BoolOpt("yes", help="Always say yes", default=False),
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

if CONF.yes:
    answer = "yes"
else:
    answer = "no"

if CONF.action:
    if CONF.disable:
        services = cloud.compute.services(
            **{"host": CONF.host, "binary": "nova-compute"}
        )
        service = next(services)
        logger.info(f"Disabling nova-compute binary @ {CONF.host} ({service.id})")
        cloud.compute.disable_service(
            service=service.id,
            host=CONF.host,
            binary="nova-compute",
            disabled_reason="MAINTENANCE",
        )

    if CONF.action == "evacutate":
        if not CONF.yes:
            answer = prompt(f"Evacuate all servers on host {CONF.host} [yes/no]: ")

        start = []
        if answer in ["yes", "y"]:
            for server in result:
                if server[2] not in ["ACTIVE", "SHUTOFF"]:
                    logger.info(
                        f"{server[0]} ({server[1]}) in status {server[2]} cannot be evacuated"
                    )
                    continue
                if server[2] in ["ACTIVE"]:
                    logger.info(f"Stopping server {server[0]}")
                    start.append(server[0])
                    cloud.compute.stop_server(server[0])
                    inner_wait = True
                    while inner_wait:
                        time.sleep(2)
                        s = cloud.compute.get_server(server[0])
                        if s.status not in ["SHUTOFF"]:
                            logger.info(
                                f"Stopping of {server[0]} ({server[1]}) is still in progress"
                            )
                            inner_wait = True
                        else:
                            inner_wait = False

            services = cloud.compute.services(
                **{"host": CONF.host, "binary": "nova-compute"}
            )
            service = next(services)
            logger.info(
                f"Forcing down nova-compute binary @ {CONF.host} ({service.id})"
            )
            cloud.compute.update_service_forced_down(
                service=service.id, host=CONF.host, binary="nova-compute"
            )

            for server in result:
                if server[2] in ["SHUTOFF"]:
                    logger.info(f"Evacuating server {server[0]}")
                    cloud.compute.evacuate_server(server[0], host=CONF.input)

            for server in start:
                logger.info(f"Starting server {server}")
                cloud.compute.start_server(server)
                inner_wait = True
                while inner_wait:
                    time.sleep(2)
                    s = cloud.compute.get_server(server[0])
                    if s.status not in ["ACTIVE"]:
                        logger.info(
                            f"Starting of {server[0]} ({server[1]}) is still in progress"
                        )
                        inner_wait = True
                    else:
                        inner_wait = False

    elif CONF.action == "live-migrate":
        for server in result:
            if server[2] not in ["ACTIVE"]:
                logger.info(
                    f"{server[0]} ({server[1]}) in status {server[2]} cannot be live migrated"
                )
                continue

            if not CONF.yes:
                answer = prompt(
                    f"Live migrate server {server[0]} ({server[1]}) [yes/no]: "
                )

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

            if not CONF.yes:
                answer = prompt(f"Stop server {server[0]} ({server[1]}) [yes/no]: ")

            if answer in ["yes", "y"]:
                logger.info(f"Stopping server {server[0]}")
                cloud.compute.stop_server(server[0])
    else:
        logger.error(f"Unknown action {CONF.action}")
