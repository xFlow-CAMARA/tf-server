"""
Module: converter.py
This module provides functions to convert application manifests into TOSCA models.
It includes the `generate_tosca` function that constructs a TOSCA model based on
the application manifest and associated app zones.
"""

from typing import List

import yaml

from sunrise6g_opensdk.edgecloud.adapters.aeros import config
from sunrise6g_opensdk.edgecloud.adapters.aeros.continuum_models import (
    TOSCA,
    ArtifactModel,
    CustomRequirement,
    DomainIdOperator,
    ExposedPort,
    HostCapability,
    HostRequirement,
    NetworkProperties,
    NetworkRequirement,
    NodeFilter,
    NodeTemplate,
    PortProperties,
)
from sunrise6g_opensdk.edgecloud.adapters.aeros.continuum_models import (
    Property as HostProperty,
)
from sunrise6g_opensdk.edgecloud.core.camara_schemas import AppManifest, VisibilityType
from sunrise6g_opensdk.logger import setup_logger

logger = setup_logger(__name__, is_debug=True, file_name=config.LOG_FILE)


def generate_tosca(app_manifest: AppManifest, app_zones: List[str]) -> str:
    """
    Generate a TOSCA model from the application manifest and app zones.
    Args:
        app_manifest (AppManifest): The application manifest containing details about the app.
        app_zones (List[Dict[str, Any]]): List of app zones where the app will be deployed.
    Returns:
        TOSCA yaml as string which can be used in a POST request with applcation type yaml
    """
    component = app_manifest.componentSpec[0]
    image_path = app_manifest.appRepo.imagePath.root
    image_file = image_path.split("/")[-1]
    repository_url = "/".join(image_path.split("/")[:-1]) if "/" in image_path else "docker_hub"

    zone_id = app_zones[0]
    logger.info("DEBUG : %s", app_manifest.requiredResources.root)
    # Extract minNodeMemory (fallback = 1024 MB)

    res = app_manifest.requiredResources.root
    if hasattr(res, "applicationResources") and hasattr(
        res.applicationResources.cpuPool.topology, "minNodeMemory"
    ):
        min_node_memory = res.applicationResources.cpuPool.topology.minNodeMemory
    else:
        min_node_memory = 1024

    # Build exposed network ports
    ports = {
        iface.interfaceId: ExposedPort(
            properties=PortProperties(protocol=[iface.protocol.value.lower()], source=iface.port)
        )
        for iface in component.networkInterfaces
    }

    expose_ports = any(
        iface.visibilityType == VisibilityType.VISIBILITY_EXTERNAL
        for iface in component.networkInterfaces
    )

    # Define host property constraints
    host_props = HostProperty(
        cpu_arch={"equal": "x64"},
        realtime={"equal": False},
        cpu_usage={"less_or_equal": "0.4"},
        mem_size={"greater_or_equal": str(min_node_memory)},
        energy_efficiency={"greater_or_equal": "0"},
        green={"greater_or_equal": "0"},
        domain_id=DomainIdOperator(equal=zone_id),
    )

    # Create Node compute and network requirements
    requirements = [
        CustomRequirement(
            network=NetworkRequirement(
                properties=NetworkProperties(ports=ports, exposePorts=expose_ports)
            )
        ),
        CustomRequirement(
            host=HostRequirement(
                node_filter=NodeFilter(
                    capabilities=[{"host": HostCapability(properties=host_props)}], properties=None
                )
            )
        ),
    ]
    # Define the NodeTemplate
    node_template = NodeTemplate(
        type="tosca.nodes.Container.Application",
        isJob=False,
        requirements=requirements,
        artifacts={
            "application_image": ArtifactModel(
                file=image_file,
                type="tosca.artifacts.Deployment.Image.Container.Docker",
                repository=repository_url,
                is_private=app_manifest.appRepo.type == "PRIVATEREPO",
                username=app_manifest.appRepo.userName,
                password=app_manifest.appRepo.credentials,
            )
        },
        interfaces={
            "Standard": {
                "create": {
                    "implementation": "application_image",
                    "inputs": {"cliArgs": [], "envVars": []},
                }
            }
        },
    )

    # Assemble full TOSCA object
    tosca = TOSCA(
        tosca_definitions_version="tosca_simple_yaml_1_3",
        description=f"TOSCA for {app_manifest.name}",
        serviceOverlay=False,
        node_templates={component.componentName: node_template},
    )

    tosca_dict = tosca.model_dump(by_alias=True, exclude_none=True)

    for template in tosca_dict.get("node_templates", {}).values():
        template["requirements"] = [
            {k: v for k, v in req.items() if v is not None}
            for req in template.get("requirements", [])
        ]

    yaml_str = yaml.dump(tosca_dict, sort_keys=False)
    return yaml_str
