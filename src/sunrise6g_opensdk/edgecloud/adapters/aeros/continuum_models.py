"""
aerOS continuum models
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ServiceNotFound(BaseModel):
    """
    Docstring
    """

    detail: str = "Service not found"


class CPUComparisonOperator(BaseModel):
    """
    CPU requirment for now is that usage should be less than
    """

    less_or_equal: Union[float, None] = None


class CPUArchComparisonOperator(BaseModel):
    """
    CPU arch requirment, equal to str
    """

    equal: Union[str, None] = None


class MEMComparisonOperator(BaseModel):
    """
    RAM requirment for now is that available RAM should be more than
    """

    greater_or_equal: Union[str, None] = None


class EnergyEfficienyComparisonOperator(BaseModel):
    """
    Energy Efficiency requirment for now is that IE should have energy efficiency more than a %
    """

    greater_or_equal: Union[str, None] = None


class GreenComparisonOperator(BaseModel):
    """
    IE Green requirment for now is that IE should have green energy mix which us more than a %
    """

    greater_or_equal: Union[str, None] = None


class RTComparisonOperator(BaseModel):
    """
    Real Time requirment T/F
    """

    equal: Union[bool, None] = None


class CpuArch(str, Enum):
    """
    Enumeration with possible cpu types
    """

    x86_64 = "x86_64"
    arm64 = "arm64"
    arm32 = "arm32"


class Coordinates(BaseModel):
    """
    IE coordinate requirements
    """

    coordinates: List[List[float]]


class DomainIdOperator(BaseModel):
    """
    CPU arch requirment, equal to str
    """

    equal: Union[str, None] = None


class Property(BaseModel):
    """
    IE capabilities
    """

    cpu_usage: CPUComparisonOperator = Field(default_factory=CPUComparisonOperator)
    cpu_arch: CPUArchComparisonOperator = Field(default_factory=CPUArchComparisonOperator)
    mem_size: MEMComparisonOperator = Field(default_factory=MEMComparisonOperator)
    realtime: RTComparisonOperator = Field(default_factory=RTComparisonOperator)
    area: Coordinates = None
    energy_efficiency: EnergyEfficienyComparisonOperator = Field(
        default_factory=EnergyEfficienyComparisonOperator
    )
    green: GreenComparisonOperator = Field(default_factory=GreenComparisonOperator)
    domain_id: DomainIdOperator = Field(default_factory=DomainIdOperator)

    # @field_validator('mem_size')
    # def validate_mem_size(cls, v):
    #     if not v or "MB" not in v:
    #         raise ValueError("mem_size must be in MB and specified")
    #     mem_size_value = int(v.split(" ")[0])
    #     if mem_size_value < 2000:
    #         raise ValueError("mem_size must be greater or equal to 2000 MB")
    #     return v


class HostCapability(BaseModel):
    """
    Host properties
    """

    properties: Property


class NodeFilter(BaseModel):
    """
    Node filter,
    How to filter continuum IE and select canditate list
    """

    properties: Optional[Dict[str, List[str]]] = None
    capabilities: Optional[List[Dict[str, HostCapability]]] = None


class HostRequirement(BaseModel):
    """
    capabilities of node
    """

    # node_filter: Dict[str, List[Dict[str, HostCapability]]]
    node_filter: NodeFilter


class PortProperties(BaseModel):
    """
    Workload port description
    """

    protocol: List[str] = Field(...)
    source: int = Field(...)


class ExposedPort(BaseModel):
    """
    Workload exposed network ports
    """

    properties: PortProperties = Field(...)


class NetworkProperties(BaseModel):
    """
    Dict of network requirments, name of port and protperty = [protocol, port] mapping
    """

    ports: Dict[str, ExposedPort] = Field(...)
    exposePorts: Optional[bool]


class NetworkRequirement(BaseModel):
    """
    Top level key of network requirments
    """

    properties: NetworkProperties


class CustomRequirement(BaseModel):
    """
    Define a custom requirement type that can be either a host or a network requirement
    """

    host: HostRequirement = None
    network: NetworkRequirement = None


class ArtifactModel(BaseModel):
    """
    Artifact has a useer defined id and then a dict with the following keys:
    """

    file: str
    type: str
    repository: str
    is_private: Optional[bool] = False
    username: Optional[str] = None
    password: Optional[str] = None


class NodeTemplate(BaseModel):
    """
    Node template "tosca.nodes.Container.Application"
    """

    type: str
    requirements: List[CustomRequirement]
    artifacts: Dict[str, ArtifactModel]
    interfaces: Dict[str, Any]
    isJob: Optional[bool] = False


class TOSCA(BaseModel):
    """
    The TOSCA structure
    """

    tosca_definitions_version: str
    description: str
    serviceOverlay: Optional[bool] = False
    node_templates: Dict[str, NodeTemplate]


TOSCA_YAML_EXAMPLE = """
tosca_definitions_version: tosca_simple_yaml_1_3
description: A test service for testing TOSCA generation
serviceOverlay: false

node_templates:
  auto-component:
    type: tosca.nodes.Container.Application
    isJob: False
    artifacts:
      application_image:
        file: aeros-public/common-deployments/nginx:latest
        repository: registry.gitlab.aeros-project.eu
        type: tosca.artifacts.Deployment.Image.Container.Docker
    interfaces:
      Standard:
        create:
          implementation: application_image
          inputs:
            cliArgs:
            - -a: aa
            envVars:
            - URL: bb
    requirements:
    - network:
        properties:
          ports:
            port1:
              properties:
                protocol:
                - tcp
                source: 80
            port2:
              properties:
                protocol:
                - tcp
                source: 443
          exposePorts: True
    - host:
        node_filter:
          capabilities:
          - host:
              properties:
                cpu_arch:
                  equal: x64
                realtime:
                  equal: false
                cpu_usage:
                  less_or_equal: '0.4'
                mem_size:
                  greater_or_equal: '1'
                domain_id:
                  equal: urn:ngsi-ld:Domain:NCSRD
                energy_efficiency:
                  greater_or_equal: '0.5'
                green:
                    greater_or_equal: '0.5'
                domain_id:
                    equal: urn:ngsi-ld:Domain:ncsrd01
          properties: null




"""
