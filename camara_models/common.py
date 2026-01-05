"""
CAMARA Common Models

Shared models and utilities used across all CAMARA APIs.
Based on CAMARA Commonalities specification.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from enum import Enum


# ====================== Error Codes ======================

class ErrorCode(str, Enum):
    """
    CAMARA Error Codes - from CAMARA_common.yaml
    These are standardized error codes used across all CAMARA APIs.
    """
    # Generic error codes
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INVALID_TOKEN = "INVALID_TOKEN"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    INTERNAL = "INTERNAL"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    
    # Device-specific error codes
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    DEVICE_UNIDENTIFIABLE = "DEVICE_UNIDENTIFIABLE"
    DEVICE_NOT_APPLICABLE = "DEVICE_NOT_APPLICABLE"
    INVALID_DEVICE_IDENTIFIER = "INVALID_DEVICE_IDENTIFIER"
    MISSING_IDENTIFIER = "MISSING_IDENTIFIER"
    UNNECESSARY_IDENTIFIER = "UNNECESSARY_IDENTIFIER"
    
    # QoD-specific error codes
    QOD_SESSION_EXTENSION_NOT_ALLOWED = "QUALITY_ON_DEMAND.SESSION_EXTENSION_NOT_ALLOWED"
    
    # Traffic Influence specific
    DENIED_WAIT = "DENIED_WAIT"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    SERVICE_NOT_APPLICABLE = "SERVICE_NOT_APPLICABLE"
    
    # Number Verification specific
    NUMBER_VERIFICATION_USER_NOT_AUTHENTICATED_BY_MOBILE_NETWORK = "NUMBER_VERIFICATION.USER_NOT_AUTHENTICATED_BY_MOBILE_NETWORK"


class ErrorInfo(BaseModel):
    """
    CAMARA-compliant error response format.
    Used for all error responses across CAMARA APIs.
    """
    model_config = ConfigDict(extra='forbid')
    
    status: int = Field(..., description="HTTP response status code")
    code: str = Field(..., description="A human-readable code to describe the error")
    message: str = Field(..., description="A human-readable description of what the event represents")


# ====================== Device Identification Models ======================

class DeviceIpv4Addr(BaseModel):
    """
    IPv4 address identifier for a device.
    Used to identify devices by their IP address.
    """
    model_config = ConfigDict(extra='forbid')
    
    publicAddress: str = Field(..., description="Public IPv4 address in dotted-quad notation")
    privateAddress: Optional[str] = Field(None, description="Private IPv4 address")
    publicPort: Optional[int] = Field(None, ge=0, le=65535, description="Public port number")


class Device(BaseModel):
    """
    Device identifier.
    At least one identifier must be provided.
    """
    model_config = ConfigDict(extra='forbid')
    
    phoneNumber: Optional[str] = Field(
        None,
        pattern=r'^\+[1-9][0-9]{4,14}$',
        description="Phone number in E.164 format with '+' prefix"
    )
    networkAccessIdentifier: Optional[str] = Field(
        None,
        description="Network Access Identifier (NAI) for the device"
    )
    ipv4Address: Optional[DeviceIpv4Addr] = Field(
        None,
        description="IPv4 address identifier"
    )
    ipv6Address: Optional[str] = Field(
        None,
        description="IPv6 address in standard notation"
    )


class DeviceResponse(BaseModel):
    """
    Device identifier in API responses.
    Similar to Device but used in response payloads.
    """
    model_config = ConfigDict(extra='forbid')
    
    phoneNumber: Optional[str] = None
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None


# ====================== Application Server Models ======================

class ApplicationServer(BaseModel):
    """
    Application server identifier.
    Used to specify the target application server for network services.
    """
    model_config = ConfigDict(extra='forbid')
    
    ipv4Address: Optional[str] = Field(None, description="IPv4 address of the application server")
    ipv6Address: Optional[str] = Field(None, description="IPv6 address of the application server")


# ====================== Port Specification Models ======================

class PortRange(BaseModel):
    """Port range specification"""
    model_config = ConfigDict(extra='forbid', populate_by_name=True)
    
    from_port: int = Field(..., alias="from", ge=0, le=65535, description="Start port")
    to_port: int = Field(..., alias="to", ge=0, le=65535, description="End port")


class PortsSpec(BaseModel):
    """
    Port specification for traffic filtering.
    Can specify individual ports or port ranges.
    """
    model_config = ConfigDict(extra='forbid')
    
    ranges: Optional[List[PortRange]] = Field(None, description="List of port ranges")
    ports: Optional[List[int]] = Field(None, description="List of individual ports")


# ====================== Sink Credential Models ======================

class SinkCredential(BaseModel):
    """
    Credential for notification sink (webhook).
    Used for CloudEvents notifications.
    """
    model_config = ConfigDict(extra='forbid')
    
    credentialType: str = Field("ACCESSTOKEN", description="Type of credential")
    accessToken: str = Field(..., description="Access token for authentication")
    accessTokenExpiresUtc: str = Field(..., description="Token expiration time in ISO 8601 format")
    accessTokenType: str = Field("bearer", description="Token type")


# ====================== Helper Functions ======================

def create_error_info(status: int, code: str, message: str) -> dict:
    """Create a CAMARA-compliant error response dict"""
    return {"status": status, "code": code, "message": message}


def map_status_to_code(status: int) -> str:
    """Map HTTP status code to default CAMARA error code"""
    mapping = {
        400: ErrorCode.INVALID_ARGUMENT.value,
        401: ErrorCode.UNAUTHENTICATED.value,
        403: ErrorCode.PERMISSION_DENIED.value,
        404: ErrorCode.NOT_FOUND.value,
        409: ErrorCode.CONFLICT.value,
        422: ErrorCode.DEVICE_UNIDENTIFIABLE.value,
        429: ErrorCode.TOO_MANY_REQUESTS.value,
        500: ErrorCode.INTERNAL.value,
        501: ErrorCode.NOT_IMPLEMENTED.value,
        503: ErrorCode.SERVICE_UNAVAILABLE.value,
    }
    return mapping.get(status, ErrorCode.INTERNAL.value)
