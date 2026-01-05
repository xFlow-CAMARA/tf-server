"""
Module: gsm2aeros_converter.py
Initial GSMA -> TOSCA generator.

Notes:
- GSMA ApplicationModel does not include container image or ports directly.
  (Those usually come from Artefacts, which we're ignoring for now.)
- We provide an `image_map` hook to resolve artefactId -> image string.
- Defaults to a public nginx image if nothing is provided.
- Network ports are omitted for now (exposePorts = False).
"""

from typing import Callable, Dict, List, Optional

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
from sunrise6g_opensdk.edgecloud.adapters.aeros.errors import (
    InvalidArgumentError,
    ResourceNotFoundError,
)
from sunrise6g_opensdk.edgecloud.core import gsma_schemas
from sunrise6g_opensdk.logger import setup_logger

logger = setup_logger(__name__, is_debug=True, file_name=config.LOG_FILE)


def generate_tosca_from_gsma_with_artefacts(  # noqa: C901
    app_model: gsma_schemas.ApplicationModel,
    zone_id: str,
    artefact_resolver: Callable[[str], Optional[gsma_schemas.Artefact]],
) -> str:
    """
    Build a TOSCA YAML from a GSMA `ApplicationModel` by resolving each component's `artefactId`.

    Rules/assumptions:
      - One node_template per `AppComponentSpec` in the application model.
      - Container image is taken from the first entry of `artefact.componentSpec[i].images`.
      - Ports come (best-effort) from `exposedInterfaces` items in the matching componentSpec, e.g. {"protocol": "TCP", "port": 8080}.
      - Host filter includes domain_id == `zone_id` and basic CPU/mem constraints.
      - For PUBLICREPO artefacts: set `is_private=False` and omit credentials entirely.
        For PRIVATEREPO artefacts: set `is_private=True` and include non-empty username/password if present.
      - `cliArgs` are derived from `commandLineParams` dict:
            - bool True -> "flag"
            - key/value -> "key=value"
        `envVars` are derived from `compEnvParams` list:
            - [{"name": "KEY", "value": "VAL"}] -> [{"KEY": "VAL"}, ...]
      - If a component name mismatch occurs between app and artefact, fall back to the first artefact componentSpec.

    :param app_model: GSMA ApplicationModel (already validated)
    :param zone_id: Target aerOS domain id/zone urn for host node filter
    :param artefact_resolver: Callable that returns an Artefact for a given artefactId
    :return: TOSCA YAML string (tosca_simple_yaml_1_3)
    """
    node_templates: Dict[str, NodeTemplate] = {}

    for comp in app_model.appComponentSpecs:
        artefact = artefact_resolver(comp.artefactId)
        if not artefact:
            raise ResourceNotFoundError(f"GSMA artefact '{comp.artefactId}' not found")

        # pick the componentSpec that matches componentName, else first
        comp_spec = None
        if artefact.componentSpec:
            for c in artefact.componentSpec:
                if c.componentName == comp.componentName:
                    comp_spec = c
                    break
            if comp_spec is None:
                comp_spec = artefact.componentSpec[0]
        else:
            raise InvalidArgumentError(f"Artefact '{artefact.artefactId}' has no componentSpec")

        # Resolve container image
        image = comp_spec.images[0] if comp_spec.images else "docker.io/library/nginx:stable"
        if "/" in image:
            repository_url = "/".join(image.split("/")[:-1])
            image_file = image.split("/")[-1]
        else:
            repository_url, image_file = "docker_hub", image

        # Ports (best-effort) from exposedInterfaces
        ports: Dict[str, ExposedPort] = {}
        expose_ports = False
        if comp_spec.exposedInterfaces:
            for idx, iface in enumerate(comp_spec.exposedInterfaces):
                protocol = str(iface.get("protocol", "TCP")).lower()
                port = iface.get("port")
                if isinstance(port, int):
                    ports[f"if{idx}"] = ExposedPort(
                        properties=PortProperties(protocol=[protocol], source=port)
                    )
                    expose_ports = True

        # Build cliArgs as a list of dicts: [{"KEY": "VAL"}, {"FLAG": ""}, ...]
        cli_args: List[Dict[str, str]] = []
        cmd = getattr(comp_spec, "commandLineParams", None)

        if isinstance(cmd, dict):
            for k, v in cmd.items():
                if v is True:
                    cli_args.append({str(k): ""})  # flag without value
                elif v is False or v is None:
                    continue
                else:
                    cli_args.append({str(k): str(v)})
        elif isinstance(cmd, list):
            # if someone passes ["--flag", "--opt=1"] style
            for item in cmd:
                if isinstance(item, str):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        cli_args.append({k: v})
                    else:
                        cli_args.append({item: ""})

        # Build envVars from compEnvParams list of {"name": "...", "value": "..."}
        env_vars: List[Dict[str, str]] = []
        if isinstance(getattr(comp_spec, "compEnvParams", None), list):
            for item in comp_spec.compEnvParams:
                if isinstance(item, dict):
                    if "name" in item and "value" in item:
                        env_vars.append({str(item["name"]): str(item["value"])})
                    elif len(item) == 1:  # already mapping-like {"KEY": "VAL"}
                        k, v = next(iter(item.items()))
                        env_vars.append({str(k): str(v)})

        # Host filter (basic example)
        host_props = HostProperty(
            cpu_arch={"equal": "x64"},
            realtime={"equal": False},
            cpu_usage={"less_or_equal": "0.4"},
            mem_size={"greater_or_equal": "1024"},
            energy_efficiency={"greater_or_equal": "0"},
            green={"greater_or_equal": "0"},
            domain_id=DomainIdOperator(equal=zone_id),
        )

        requirements = [
            CustomRequirement(
                network=NetworkRequirement(
                    properties=NetworkProperties(ports=ports, exposePorts=expose_ports)
                )
            ),
            CustomRequirement(
                host=HostRequirement(
                    node_filter=NodeFilter(
                        capabilities=[{"host": HostCapability(properties=host_props)}],
                        properties=None,
                    )
                )
            ),
        ]

        # PUBLICREPO => is_private=False and omit credentials
        repo_type = getattr(artefact, "repoType", None)
        is_private = bool(repo_type == "PRIVATEREPO")
        username = None
        password = None
        if is_private and artefact.artefactRepoLocation:
            u = artefact.artefactRepoLocation.userName
            p = artefact.artefactRepoLocation.password
            username = u if u else None
            password = p if p else None

        node_templates[comp.componentName] = NodeTemplate(
            type="tosca.nodes.Container.Application",
            isJob=False,
            requirements=requirements,
            artifacts={
                "application_image": ArtifactModel(
                    file=image_file,
                    type="tosca.artifacts.Deployment.Image.Container.Docker",
                    repository=repository_url,
                    is_private=is_private,  # False for PUBLICREPO
                    username=username,  # None for PUBLICREPO
                    password=password,  # None for PUBLICREPO
                )
            },
            interfaces={
                "Standard": {
                    "create": {
                        "implementation": "application_image",
                        "inputs": {
                            "cliArgs": cli_args,
                            "envVars": env_vars,
                        },
                    }
                }
            },
        )

    # Assemble and dump TOSCA
    tosca = TOSCA(
        tosca_definitions_version="tosca_simple_yaml_1_3",
        description=f"GSMA->TOSCA for {app_model.appMetaData.appName} ({app_model.appId})",
        serviceOverlay=False,
        node_templates=node_templates,
    )

    tosca_dict = tosca.model_dump(by_alias=True, exclude_none=True)
    # Clean requirements lists from None entries
    for template in tosca_dict.get("node_templates", {}).values():
        template["requirements"] = [
            {k: v for k, v in req.items() if v is not None}
            for req in template.get("requirements", [])
        ]

    return yaml.dump(tosca_dict, sort_keys=False)
