# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
from time import sleep

from loguru import logger
import openstack
from oslo_config import cfg
from prompt_toolkit import prompt
import pymysql

PROJECT_NAME = "loadbalancer"
CONF = cfg.CONF
opts = [
    cfg.BoolOpt("debug", help="Enable debug logging", default=False),
    cfg.StrOpt("connection", help="Database connection string", default=None),
    cfg.StrOpt("loadbalancer", help="Loadbalancer ID to handle", default=None),
    cfg.StrOpt(
        "type",
        help="Status type to handle",
        default="provisioning_status",
        choices=["provisioning_status", "operating_status"],
    ),
    cfg.StrOpt("cloud", help="Cloud name in clouds.yaml", default="service"),
]
CONF.register_cli_opts(opts)
CONF(sys.argv[1:], project=PROJECT_NAME)

SLEEP_WAIT_FOR_AMPHORA_BOOT = 5
TIMEOUT_WAIT_FOR_AMPHORA_BOOT = 120

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

# MariaDB [octavia]> describe load_balancer;
# +---------------------+--------------+------+-----+---------+-------+
# | Field               | Type         | Null | Key | Default | Extra |
# +---------------------+--------------+------+-----+---------+-------+
# | project_id          | varchar(36)  | YES  |     | NULL    |       |
# | id                  | varchar(36)  | NO   | PRI | NULL    |       |
# | name                | varchar(255) | YES  |     | NULL    |       |
# | description         | varchar(255) | YES  |     | NULL    |       |
# | provisioning_status | varchar(16)  | NO   | MUL | NULL    |       |
# | operating_status    | varchar(16)  | NO   | MUL | NULL    |       |
# | enabled             | tinyint(1)   | NO   |     | NULL    |       |
# | topology            | varchar(36)  | YES  | MUL | NULL    |       |
# | server_group_id     | varchar(36)  | YES  |     | NULL    |       |
# | created_at          | datetime     | YES  |     | NULL    |       |
# | updated_at          | datetime     | YES  |     | NULL    |       |
# | provider            | varchar(64)  | YES  |     | NULL    |       |
# | flavor_id           | varchar(36)  | YES  | MUL | NULL    |       |
# | availability_zone   | varchar(255) | YES  | MUL | NULL    |       |
# +---------------------+--------------+------+-----+---------+-------+


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


def reset_load_balancer_operating_status(load_balancer):
    global database

    with database.cursor() as cursor:
        query = f"UPDATE load_balancer SET operating_status = 'ONLINE' WHERE id = '{load_balancer.id}';"
        logger.debug(query)
        cursor.execute(query)
        database.commit()


def reset_load_balancer_provisioning_status(load_balancer):
    global database

    with database.cursor() as cursor:
        query = f"UPDATE load_balancer SET provisioning_status = 'ACTIVE' WHERE id = '{load_balancer.id}';"
        logger.debug(query)
        cursor.execute(query)
        database.commit()


def set_error_load_balancer_provisioning_status(load_balancer):
    global database

    with database.cursor() as cursor:
        query = f"UPDATE load_balancer SET provisioning_status = 'ERROR' WHERE id = '{load_balancer.id}';"
        logger.debug(query)
        cursor.execute(query)
        database.commit()


# Connect to the OpenStack environment
cloud = openstack.connect(cloud=CONF.cloud)

# Connect to the database
# NOTE: Beautify this
connection_parts = CONF.connection.split("//")[1]
db_username = connection_parts.split(":")[0]
db_password = connection_parts.split(":")[1].split("@")[0]
db_host = connection_parts.split("@")[1].split(":")[0]
db_port = int(connection_parts.split("@")[1].split(":")[1].split("/")[0])
db_database = connection_parts.split("@")[1].split(":")[1].split("/")[1]

database = pymysql.connect(
    host=db_host,
    port=db_port,
    user=db_username,
    password=db_password,
    database=db_database,
    cursorclass=pymysql.cursors.DictCursor,
)

if CONF.loadbalancer and CONF.type == "provisioning_status":
    load_balancer = cloud.load_balancer.get_load_balancer(CONF.loadbalancer)

    logger.info(
        f"Loadbalancer {load_balancer.name} is in provisioning_status '{load_balancer.provisioning_status}'"
    )

    if load_balancer.provisioning_status == "PENDING_CREATE":
        result = prompt(f"Delete loadbalancer {CONF.loadbalancer} [yes/no]: ")
        if result == "yes":
            logger.info(f"Deleting {load_balancer.name}")
            set_error_load_balancer_provisioning_status(load_balancer)

            cloud.load_balancer.delete_load_balancer(load_balancer.id)

    elif load_balancer.provisioning_status == "PENDING_UPDATE":
        result = prompt(f"Reset loadbalancer {CONF.loadbalancer} [yes/no]: ")
        if result == "yes":
            logger.info(f"Resetting {load_balancer.name}")
            reset_load_balancer_provisioning_status(load_balancer)

            logger.info(f"Triggering failover for {load_balancer.name}")
            cloud.load_balancer.failover_load_balancer(load_balancer.id)
            sleep(10)  # wait for the octavia API
            wait_for_amphora_boot(load_balancer.id)

    # This only works when there is at least on working amphora. Therefore, this is only useful
    # if the load balancer ID is explicitly specified.
    elif load_balancer.provisioning_status == "ERROR":
        result = prompt(f"Reset loadbalancer {CONF.loadbalancer} [yes/no]: ")
        if result == "yes":
            logger.info(f"Resetting {load_balancer.name}")
            reset_load_balancer_provisioning_status(load_balancer)
            cloud.load_balancer.failover_load_balancer(load_balancer.id)
            sleep(10)  # wait for the octavia API
            wait_for_amphora_boot(load_balancer.id)
    else:
        logger.error(
            f"{CONF.loadbalancer} has to be in provisioning_status PENDING_UPDATE or PENDING_CREATE"
        )
        sys.exit(1)

elif not CONF.loadbalancer and CONF.type == "provisioning_status":
    load_balancers = cloud.load_balancer.load_balancers(
        provisioning_status="PENDING_UPDATE"
    )

    for load_balancer in load_balancers:
        logger.info(
            f"Loadbalancer {load_balancer.name} is in provisioning_status PENDING_UPDATE"
        )
        result = prompt(f"Reset loadbalancer {load_balancer.name} [yes/no]: ")

        if result == "yes":
            logger.info(f"Resetting {load_balancer.name}")
            reset_load_balancer_provisioning_status(load_balancer)

            logger.info(f"Triggering failover for {load_balancer.name}")
            cloud.load_balancer.failover_load_balancer(load_balancer.id)
            sleep(10)  # wait for the octavia API
            wait_for_amphora_boot(load_balancer.id)
        else:
            logger.debug(f"Skipping {load_balancer.name}")

elif CONF.loadbalancer and CONF.type == "operating_status":
    load_balancer = cloud.load_balancer.get_load_balancer(CONF.loadbalancer)
    if load_balancer.operating_status != "ERROR":
        logger.error(f"{CONF.loadbalancer} has to be in operating_status ERROR")
        sys.exit(1)
    elif load_balancer.provisioning_status != "ACTIVE":
        logger.error(f"{CONF.loadbalancer} has to be in provisioning_status ACTIVE")
        sys.exit(1)

    result = prompt(f"Reset loadbalancer {CONF.loadbalancer} [yes/no]: ")
    if result == "yes":
        logger.info(f"Resetting {load_balancer.name}")
        reset_load_balancer_operating_status(load_balancer)

        logger.info(f"Triggering failover for {load_balancer.name}")
        cloud.load_balancer.failover_load_balancer(load_balancer.id)
        sleep(10)  # wait for the octavia API
        wait_for_amphora_boot(load_balancer.id)

elif not CONF.loadbalancer and CONF.type == "operating_status":
    load_balancers = cloud.load_balancer.load_balancers(provisioning_status="ERROR")
    for load_balancer in load_balancers:
        logger.info(f"Loadbalancer {load_balancer.name} is in operating_status ERROR")

        if load_balancer.provisioning_status != "ACTIVE":
            logger.error(f"{CONF.loadbalancer} has to be in provisioning_status ACTIVE")
            sys.exit(1)

        result = prompt(f"Reset loadbalancer {load_balancer.name} [yes/no]: ")
        if result == "yes":
            logger.info(f"Resetting {load_balancer.name}")
            reset_load_balancer_operating_status(load_balancer)

            logger.info(f"Triggering failover for {load_balancer.name}")
            cloud.load_balancer.failover_load_balancer(load_balancer.id)
            sleep(10)  # wait for the octavia API
            wait_for_amphora_boot(load_balancer.id)

        else:
            logger.debug(f"Skipping {load_balancer.name}")
