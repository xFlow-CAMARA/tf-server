"""
CAMARA Quality-On-Demand API v1.1.0 Schemas

This module defines Pydantic models that conform to the official CAMARA QoD specification.
Reference: https://github.com/camaraproject/QualityOnDemand
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime


# ============================================================================
# Device Identification Models
# ============================================================================

class DeviceIpv4Addr(BaseModel):
    """Device IPv4 address with public and optional private address or port"""
    publicAddress: str = Field(..., description="Public IPv4 address")
    privateAddress: Optional[str] = Field(None, description="Private IPv4 address")
    publicPort: Optional[int] = Field(None, ge=0, le=65535, description="Public port number")

    @validator('publicPort', 'privateAddress', always=True)
    def check_private_or_port(cls, v, values):
        """Ensure at least privateAddress or publicPort is provided"""
        if 'publicAddress' in values and v is None:
            if not values.get('privateAddress') and not values.get('publicPort'):
                return values.get('publicAddress')  # Default to publicAddress
        return v


class Device(BaseModel):
    """Device identification - at least one identifier required"""
    phoneNumber: Optional[str] = Field(None, regex=r'^\+[1-9][0-9]{4,14}$')
    networkAccessIdentifier: Optional[str] = Field(None, description="Format: localId@domain")
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "ipv4Address": {
                    "publicAddress": "12.1.0.1",
                    "privateAddress": "12.1.0.1"
                }
            }
        }


class ApplicationServer(BaseModel):
    """Application server identification"""
    ipv4Address: Optional[str] = Field(None, description="IPv4 address or CIDR")
    ipv6Address: Optional[str] = Field(None, description="IPv6 address or CIDR")

    @validator('ipv4Address', 'ipv6Address')
    def at_least_one_address(cls, v, values):
        """Ensure at least one address type is provided"""
        if not v and not values.get('ipv4Address') and not values.get('ipv6Address'):
            raise ValueError("At least one of ipv4Address or ipv6Address must be provided")
        return v


# ============================================================================
# Port Specification Models
# ============================================================================

class PortRange(BaseModel):
    """TCP/UDP port range"""
    from_port: int = Field(..., alias="from", ge=0, le=65535)
    to_port: int = Field(..., alias="to", ge=0, le=65535)

    @validator('to_port')
    def to_greater_than_from(cls, v, values):
        if 'from_port' in values and v < values['from_port']:
            raise ValueError("'to' must be greater than or equal to 'from'")
        return v

    class Config:
        allow_population_by_field_name = True


class PortsSpec(BaseModel):
    """Port specification with ranges and/or individual ports"""
    ranges: Optional[List[PortRange]] = None
    ports: Optional[List[int]] = Field(None, description="List of individual port numbers")

    class Config:
        schema_extra = {
            "example": {
                "ranges": [{"from": 5010, "to": 5020}],
                "ports": [5060, 5070]
            }
        }


# ============================================================================
# Notification/Sink Models
# ============================================================================

class SinkCredential(BaseModel):
    """Sink credential for authenticated notifications"""
    credentialType: Literal["ACCESSTOKEN"] = "ACCESSTOKEN"
    accessToken: str = Field(..., description="Bearer access token")
    accessTokenExpiresUtc: str = Field(..., description="ISO 8601 UTC timestamp")
    accessTokenType: Literal["bearer"] = "bearer"

    @validator('accessTokenExpiresUtc')
    def validate_timestamp(cls, v):
        """Validate ISO 8601 format"""
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("accessTokenExpiresUtc must be a valid ISO 8601 timestamp")
        return v


# ============================================================================
# QoS Session Models
# ============================================================================

QosStatus = Literal["REQUESTED", "AVAILABLE", "UNAVAILABLE"]
StatusInfo = Literal["DURATION_EXPIRED", "NETWORK_TERMINATED", "DELETE_REQUESTED"]


class CreateSession(BaseModel):
    """Request body for creating a QoS session"""
    device: Optional[Device] = Field(
        None,
        description="Required when using 2-legged token, must not be provided with 3-legged token"
    )
    applicationServer: ApplicationServer
    devicePorts: Optional[PortsSpec] = None
    applicationServerPorts: Optional[PortsSpec] = None
    qosProfile: str = Field(
        ...,
        min_length=3,
        max_length=256,
        regex=r'^[a-zA-Z0-9_.-]+$',
        description="QoS profile name"
    )
    duration: int = Field(..., ge=1, description="Session duration in seconds")
    sink: Optional[str] = Field(None, regex=r'^https://.+$', description="HTTPS notification URL")
    sinkCredential: Optional[SinkCredential] = None

    class Config:
        schema_extra = {
            "example": {
                "device": {
                    "ipv4Address": {
                        "publicAddress": "12.1.0.1",
                        "privateAddress": "12.1.0.1"
                    }
                },
                "applicationServer": {"ipv4Address": "10.0.0.1"},
                "qosProfile": "qos-e",
                "duration": 3600,
                "sink": "https://example.com/notifications"
            }
        }


class SessionInfo(BaseModel):
    """QoS session information response"""
    sessionId: str = Field(..., description="Session ID in UUID format")
    duration: int = Field(..., ge=1)
    qosProfile: str
    device: Optional[Device] = Field(
        None,
        description="Only returned when provided in request or disambiguation needed"
    )
    applicationServer: ApplicationServer
    devicePorts: Optional[PortsSpec] = None
    applicationServerPorts: Optional[PortsSpec] = None
    qosStatus: QosStatus
    statusInfo: Optional[StatusInfo] = Field(
        None,
        description="Reason for UNAVAILABLE status"
    )
    startedAt: Optional[str] = Field(
        None,
        description="ISO 8601 timestamp when qosStatus became AVAILABLE"
    )
    expiresAt: Optional[str] = Field(
        None,
        description="ISO 8601 timestamp when session expires"
    )
    sink: Optional[str] = None
    sinkCredential: Optional[SinkCredential] = None

    class Config:
        schema_extra = {
            "example": {
                "sessionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "duration": 3600,
                "qosProfile": "qos-e",
                "applicationServer": {"ipv4Address": "10.0.0.1"},
                "qosStatus": "AVAILABLE",
                "startedAt": "2024-06-01T12:00:00Z",
                "expiresAt": "2024-06-01T13:00:00Z"
            }
        }


class ExtendSessionDuration(BaseModel):
    """Request body for extending session duration"""
    requestedAdditionalDuration: int = Field(
        ...,
        ge=1,
        description="Additional duration in seconds"
    )


class RetrieveSessionsInput(BaseModel):
    """Request body for retrieving sessions by device"""
    device: Device


# ============================================================================
# CloudEvents Models for Notifications
# ============================================================================

class QosStatusChangedData(BaseModel):
    """Data payload for QoS status change event"""
    sessionId: str
    qosStatus: QosStatus
    statusInfo: Optional[StatusInfo] = None


class CloudEvent(BaseModel):
    """CloudEvents v1.0 specification for QoD notifications"""
    id: str = Field(..., description="Unique event identifier")
    source: str = Field(..., description="URI identifying the event source")
    specversion: Literal["1.0"] = "1.0"
    type: Literal["org.camaraproject.quality-on-demand.v1.qos-status-changed"]
    time: str = Field(..., description="ISO 8601 timestamp")
    datacontenttype: Literal["application/json"] = "application/json"
    data: QosStatusChangedData

    class Config:
        schema_extra = {
            "example": {
                "id": "83a0d986-0866-4f38-b8c0-fc65bfcda452",
                "source": "https://api.example.com/qod/v1/sessions/123e4567-e89b",
                "specversion": "1.0",
                "type": "org.camaraproject.quality-on-demand.v1.qos-status-changed",
                "time": "2024-06-01T13:00:00Z",
                "datacontenttype": "application/json",
                "data": {
                    "sessionId": "123e4567-e89b-12d3-a456-426614174000",
                    "qosStatus": "UNAVAILABLE",
                    "statusInfo": "DURATION_EXPIRED"
                }
            }
        }


# ============================================================================
# Error Response Models
# ============================================================================

class ErrorInfo(BaseModel):
    """Standard CAMARA error response"""
    status: int = Field(..., description="HTTP status code")
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")

    class Config:
        schema_extra = {
            "example": {
                "status": 400,
                "code": "INVALID_ARGUMENT",
                "message": "Client specified an invalid argument"
            }
        }
