import logging
import sys

from oslo_config import cfg
import os_client_config

PROJECT_NAME = "list-orphaned-resources-api"
CONF = cfg.CONF
opts = [
    cfg.BoolOpt("debug", help="Enable debug logging", default=False),
    cfg.StrOpt("cloud", help="Cloud name in clouds.yaml", default="service"),
]
CONF.register_cli_opts(opts)
CONF(sys.argv[1:], project=PROJECT_NAME)

if CONF.debug:
    level = logging.DEBUG
else:
    level = logging.INFO
logging.basicConfig(
    format="%(asctime)s - %(message)s", level=level, datefmt="%Y-%m-%d %H:%M:%S"
)


def check(servicename, resourcename, resources, projects):
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
            logging.error("%s resource %s not supported" % (servicename, resourcename))
            logging.debug(dir(resource))
            project_id = None

        if hasattr(resource, "id"):
            resource_id = resource.id
        else:
            resource_id = resource.get("id")

        if resourcename == "imagemember":
            resource_id = "image_id: %s, member_id: %s" % (
                resource.get("image_id"),
                resource.get("member_id"),
            )

        if project_id and project_id not in projects:
            print(
                "%s - %s: %s (project: %s)"
                % (servicename, resourcename, resource_id, project_id)
            )

        if (
            resourcename == "rbacpolicy"
            and resource.get("target_tenant") not in projects
        ):
            print(
                "%s - %s: %s (project: %s)"
                % (servicename, resourcename, resource_id, project_id)
            )


keystone = os_client_config.make_client("identity", cloud=CONF.cloud)
clients = {
    "cinder": os_client_config.make_client("volume", cloud=CONF.cloud),
    "glance": os_client_config.make_client("image", cloud=CONF.cloud),
    "neutron": os_client_config.make_client("network", cloud=CONF.cloud),
    "nova": os_client_config.make_client("compute", cloud=CONF.cloud),
    "heat": os_client_config.make_client("orchestration", cloud=CONF.cloud),
}

domains = [x for x in keystone.domains.list() if x.name != "heat_user_domain"]

projects = []
for domain in domains:
    projects_in_domain = [x.id for x in keystone.projects.list(domain=domain.id)]
    projects = projects + projects_in_domain

check(
    "nova",
    "server",
    clients["nova"].servers.list(search_opts={"all_tenants": True}),
    projects,
)

check("neutron", "port", clients["neutron"].list_ports()["ports"], projects)
check("neutron", "router", clients["neutron"].list_routers()["routers"], projects)
check("neutron", "network", clients["neutron"].list_networks()["networks"], projects)
check("neutron", "subnet", clients["neutron"].list_subnets()["subnets"], projects)
check(
    "neutron",
    "floatingip",
    clients["neutron"].list_floatingips()["floatingips"],
    projects,
)
check(
    "neutron",
    "rbacpolicy",
    clients["neutron"].list_rbac_policies()["rbac_policies"],
    projects,
)
check(
    "neutron",
    "securitygroup",
    clients["neutron"].list_security_groups()["security_groups"],
    projects,
)
check(
    "neutron",
    "securitygrouprule",
    clients["neutron"].list_security_group_rules()["security_group_rules"],
    projects,
)

check("glance", "image", clients["glance"].images.list(), projects)
for image in [
    image
    for image in clients["glance"].images.list()
    if "visibility" in image and image.visibility == "shared"
]:
    check(
        "glance",
        "imagemember",
        clients["glance"].image_members.list(image.id),
        projects,
    )

check(
    "cinder",
    "volume",
    clients["cinder"].volumes.list(search_opts={"all_tenants": True}),
    projects,
)
check(
    "cinder",
    "volume-snapshot",
    clients["cinder"].volume_snapshots.list(search_opts={"all_tenants": True}),
    projects,
)
check(
    "cinder",
    "backups",
    clients["cinder"].backups.list(search_opts={"all_tenants": True}),
    projects,
)

check("heat", "stack", clients["heat"].stacks.list(), projects)
