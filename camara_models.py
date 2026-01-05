"""
CAMARA API Models - Backward Compatibility Module

This module re-exports all CAMARA models from the camara_models package
for backward compatibility with existing code.

For new code, import directly from camara_models package:
    from camara_models import Device, ErrorCode, SessionInfo
    from camara_models.qod import CreateSession
    from camara_models.location import Location
"""

# Re-export everything from the camara_models package
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
    VerifyLocationRequest,
    VerifyLocationResponse,
    DeviceLocationResponse,
)

from camara_models.traffic_influence import (
    TrafficInfluenceState,
    TrafficInfluenceNotificationType,
    SourceTrafficFilters,
    DestinationTrafficFilters,
    SubscriptionDetail,
    SubscriptionConfig,
    TrafficInfluenceRequest,
    TrafficInfluenceUpdate,
    TrafficInfluenceResponse,
    TrafficInfluenceNotification,
)

from camara_models.number_verification import (
    NumberVerificationRequestBody,
    NumberVerificationMatchResponse,
    NumberVerificationShareResponse,
    hash_phone_number,
    verify_phone_numbers,
    validate_phone_number_format,
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
    "VerifyLocationRequest",
    "VerifyLocationResponse",
    "DeviceLocationResponse",
    # Traffic Influence
    "TrafficInfluenceState",
    "TrafficInfluenceNotificationType",
    "SourceTrafficFilters",
    "DestinationTrafficFilters",
    "SubscriptionDetail",
    "SubscriptionConfig",
    "TrafficInfluenceRequest",
    "TrafficInfluenceUpdate",
    "TrafficInfluenceResponse",
    "TrafficInfluenceNotification",
    # Number Verification
    "NumberVerificationRequestBody",
    "NumberVerificationMatchResponse",
    "NumberVerificationShareResponse",
    "hash_phone_number",
    "verify_phone_numbers",
    "validate_phone_number_format",
]
