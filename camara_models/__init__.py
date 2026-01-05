"""
CAMARA Models Package

This package contains all CAMARA API model definitions organized by API.
"""

from camara_models.common import (
    ErrorCode,
    ErrorInfo,
    Device,
    DeviceIpv4Addr,
    DeviceResponse,
    ApplicationServer,
    PortRange,
    PortsSpec,
    SinkCredential,
    create_error_info,
    map_status_to_code,
)

from camara_models.qod import (
    QosStatus,
    StatusInfo,
    CreateSession,
    ExtendSessionDuration,
    RetrieveSessionsInput,
    SessionInfo,
)

from camara_models.location import (
    Point,
    Circle,
    Polygon,
    Area,
    RetrievalLocationRequest,
    Location,
)

from camara_models.traffic_influence import (
    TrafficInfluenceState,
    SourceTrafficFilters,
    DestinationTrafficFilters,
    TrafficInfluenceRequest,
    TrafficInfluenceResponse,
    TrafficInfluenceNotification,
)

from camara_models.number_verification import (
    NumberVerificationRequestBody,
    NumberVerificationMatchResponse,
    NumberVerificationShareResponse,
)

__all__ = [
    # Common
    "ErrorCode",
    "ErrorInfo",
    "Device",
    "DeviceIpv4Addr",
    "DeviceResponse",
    "ApplicationServer",
    "PortRange",
    "PortsSpec",
    "SinkCredential",
    "create_error_info",
    "map_status_to_code",
    # QoD
    "QosStatus",
    "StatusInfo",
    "CreateSession",
    "ExtendSessionDuration",
    "RetrieveSessionsInput",
    "SessionInfo",
    # Location
    "Point",
    "Circle",
    "Polygon",
    "Area",
    "RetrievalLocationRequest",
    "Location",
    # Traffic Influence
    "TrafficInfluenceState",
    "SourceTrafficFilters",
    "DestinationTrafficFilters",
    "TrafficInfluenceRequest",
    "TrafficInfluenceResponse",
    "TrafficInfluenceNotification",
    # Number Verification
    "NumberVerificationRequestBody",
    "NumberVerificationMatchResponse",
    "NumberVerificationShareResponse",
]
