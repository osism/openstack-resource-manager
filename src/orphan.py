# SPDX-License-Identifier: AGPL-3.0-or-later

import sys

from loguru import logger
import openstack
from oslo_config import cfg
from tabulate import tabulate
from typing import List


PROJECT_NAME = "orphan"
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


def check(servicename, resourcename, resources, projects):
    result = []

    logger.info(f"Checking {servicename} / {resourcename}")
    for resource in resources:
        try:
            if hasattr(resource, "tenant_id"):
                project_id = resource.tenant_id
            elif hasattr(resource, "project_id"):
                project_id = resource.project_id
            elif hasattr(resource, "os-vol-tenant-attr:tenant_id"):
                project_id = getattr(resource, "os-vol-tenant-attr:tenant_id")
            elif hasattr(resource, "project"):
                project_id = resource.project
            elif hasattr(resource, "member_id"):
                project_id = resource.member_id
            else:
                project_id = resource.get("project_id")
        except Exception:
            logger.error("%s resource %s not supported" % (servicename, resourcename))
            logger.debug(dir(resource))
            project_id = None

        if hasattr(resource, "id"):
            resource_id = resource.id
        elif resourcename == "imagemember":
            resource_id = resource.get("member_id")
        else:
            resource_id = resource.get("id")

        logger.debug(f"Checking {resource_id}")

        if (project_id and project_id not in projects) or (
            resourcename == "rbacpolicy"
            and resource.get("target_tenant") not in projects
        ):
            result.append([servicename, resourcename, resource_id, project_id])
            logger.debug(
                f"{servicename} - {resourcename}: {resource_id} (project: {project_id})"
            )

    return result


# Connect to the OpenStack environment
cloud = openstack.connect(cloud=CONF.cloud)

domains = [x for x in cloud.list_domains() if x.name != "heat_user_domain"]

projects: List[int] = []
for domain in domains:
    projects_in_domain = [x.id for x in cloud.list_projects(domain_id=domain.id)]
    projects = projects + projects_in_domain

result = []

result += check(
    "nova",
    "server",
    cloud.compute.servers(all_projects=True),
    projects,
)

result += check("neutron", "port", cloud.network.ports(), projects)
result += check("neutron", "router", cloud.network.routers(), projects)
result += check("neutron", "network", cloud.network.networks(), projects)
result += check("neutron", "subnet", cloud.network.subnets(), projects)
result += check(
    "neutron",
    "floatingip",
    cloud.network.ips(),
    projects,
)
result += check(
    "neutron",
    "rbacpolicy",
    cloud.network.rbac_policies(),
    projects,
)
result += check(
    "neutron",
    "securitygroup",
    cloud.network.security_groups(),
    projects,
)
result += check(
    "neutron",
    "securitygrouprule",
    cloud.network.security_group_rules(),
    projects,
)

result += check("glance", "image", cloud.image.images(), projects)
for image in [
    image
    for image in cloud.image.images()
    if "visibility" in image and image.visibility == "shared"
]:
    result += check(
        "glance",
        "imagemember",
        cloud.image.members(image.id),
        projects,
    )

result += check(
    "cinder",
    "volume",
    cloud.volume.volumes(all_projects=True),
    projects,
)
result += check(
    "cinder",
    "volume-snapshot",
    cloud.volume.snapshots(all_projects=True),
    projects,
)
result += check(
    "cinder",
    "backups",
    cloud.volume.backups(all_projects=True),
    projects,
)

print(
    tabulate(
        result,
        headers=["servicename", "resourcename", "resource_id", "project_id"],
        tablefmt="psql",
    )
)
