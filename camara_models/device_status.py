"""
CAMARA Device Status API Models

Compliant with CAMARA Device Status specification.
https://github.com/camaraproject/DeviceStatus
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from enum import Enum


# ====================== Enums ======================

class ConnectivityStatus(str, Enum):
    """
    Device connectivity status (legacy).
    
    Indicates the current connectivity status of a device.
    Kept for backwards compatibility.
    """
    CONNECTED_SMS = "CONNECTED_SMS"      # Device can receive SMS only
    CONNECTED_DATA = "CONNECTED_DATA"    # Device can receive data (full connectivity)
    NOT_CONNECTED = "NOT_CONNECTED"      # Device is not reachable


class ConnectivityType(str, Enum):
    """
    CAMARA Device Reachability Status connectivity type.
    
    DATA: The device is connected to the network for Data usage
    SMS: The device is connected to the network only for SMS usage
    """
    DATA = "DATA"
    SMS = "SMS"


class RoamingStatus(str, Enum):
    """
    Device roaming status.
    
    Indicates whether a device is roaming.
    """
    ROAMING = "ROAMING"
    NOT_ROAMING = "NOT_ROAMING"


# ====================== Device Models ======================

class DeviceIpv4Addr(BaseModel):
    """
    IPv4 address identifier for a device.
    
    Used to identify devices by their IP address and optionally port.
    """
    model_config = ConfigDict(extra='forbid')
    
    publicAddress: str = Field(
        ..., 
        description="Public IPv4 address in dotted-quad notation"
    )
    privateAddress: Optional[str] = Field(
        None, 
        description="Private IPv4 address"
    )
    publicPort: Optional[int] = Field(
        None, 
        ge=0, 
        le=65535, 
        description="Public port number"
    )


class Device(BaseModel):
    """
    Device identifier.
    
    At least one identifier must be provided to identify the device.
    Supported identifiers:
    - phoneNumber: E.164 format phone number
    - networkAccessIdentifier: NAI format (user@domain)
    - ipv4Address: IPv4 address with optional port
    - ipv6Address: IPv6 address
    """
    model_config = ConfigDict(extra='forbid')
    
    phoneNumber: Optional[str] = Field(
        None,
        pattern=r'^\+[1-9][0-9]{4,14}$',
        description="Phone number in E.164 format (e.g., +33612345678)"
    )
    networkAccessIdentifier: Optional[str] = Field(
        None,
        description="Network Access Identifier (e.g., user@domain)"
    )
    ipv4Address: Optional[DeviceIpv4Addr] = Field(
        None,
        description="IPv4 address identifier"
    )
    ipv6Address: Optional[str] = Field(
        None,
        description="IPv6 address"
    )

    def has_identifier(self) -> bool:
        """Check if at least one identifier is provided"""
        return any([
            self.phoneNumber,
            self.networkAccessIdentifier,
            self.ipv4Address,
            self.ipv6Address
        ])


# ====================== Request Models ======================

class ReachabilityStatusRequest(BaseModel):
    """
    Request body for checking device reachability status.
    
    POST /device-reachability-status/vwip/retrieve
    
    Per CAMARA spec:
    - With 2-legged access token: device MUST be provided
    - With 3-legged access token: device MUST NOT be provided (identified from token)
    """
    model_config = ConfigDict(extra='forbid')
    
    device: Optional[Device] = Field(
        None, 
        description="Device identifier. Required for 2-legged tokens, must not be provided for 3-legged tokens."
    )


class RoamingStatusRequest(BaseModel):
    """
    Request body for checking device roaming status.
    
    POST /device-status/roaming/v1/retrieve
    """
    model_config = ConfigDict(extra='forbid')
    
    device: Device = Field(
        ..., 
        description="Device identifier to check roaming status for"
    )


class SubscriptionRequest(BaseModel):
    """
    Base subscription request for device status notifications.
    
    Used for both reachability and roaming subscriptions.
    """
    model_config = ConfigDict(extra='forbid')
    
    device: Device = Field(
        ..., 
        description="Device to monitor for status changes"
    )
    sink: str = Field(
        ..., 
        description="Webhook URL for event notifications"
    )
    sinkCredential: Optional[dict] = Field(
        None,
        description="Credentials for webhook authentication (e.g., OAuth2 token)"
    )
    subscriptionExpireTime: Optional[str] = Field(
        None,
        description="Subscription expiration time in ISO 8601 format"
    )
    subscriptionMaxEvents: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum number of events before subscription expires"
    )


# ====================== Response Models ======================

class ReachabilityStatusResponse(BaseModel):
    """
    Response for device reachability status.
    
    CAMARA Device Reachability Status API response.
    POST /device-reachability-status/vwip/retrieve
    """
    model_config = ConfigDict(extra='forbid')
    
    device: Optional[Device] = Field(
        None,
        description="Device identifier returned when device was provided in request (2-legged token). Only one identifier is returned."
    )
    lastStatusTime: str = Field(
        ...,
        description="The last time the device reachability status was confirmed. RFC 3339 format with timezone."
    )
    reachable: bool = Field(
        ...,
        description="Indicates overall device reachability"
    )
    connectivity: Optional[List[ConnectivityType]] = Field(
        None,
        description="Types of connectivity available (DATA, SMS, or both). Only present when reachable=true."
    )
    
    # Legacy field for backwards compatibility with existing dashboard
    reachabilityStatus: Optional[ConnectivityStatus] = Field(
        None,
        description="Legacy field for backwards compatibility. Use reachable+connectivity instead."
    )


class RoamingStatusResponse(BaseModel):
    """
    Response for device roaming status.
    
    Response for POST /device-status/roaming/v1/retrieve
    """
    model_config = ConfigDict(extra='forbid')
    
    roaming: bool = Field(
        ..., 
        description="True if device is currently roaming"
    )
    countryCode: Optional[str] = Field(
        None,
        pattern=r'^[A-Z]{2}$',
        description="ISO 3166-1 alpha-2 country code where device is located"
    )
    countryName: Optional[List[str]] = Field(
        None,
        description="Country name(s) where device is located"
    )


class SubscriptionResponse(BaseModel):
    """
    Response for subscription creation.
    
    Returned when a new reachability or roaming subscription is created.
    """
    model_config = ConfigDict(extra='forbid')
    
    subscriptionId: str = Field(
        ..., 
        description="Unique subscription identifier (UUID)"
    )
    device: Device = Field(
        ..., 
        description="Device being monitored"
    )
    sink: str = Field(
        ..., 
        description="Webhook URL for notifications"
    )
    startsAt: str = Field(
        ..., 
        description="Subscription start time in ISO 8601 format"
    )
    expiresAt: Optional[str] = Field(
        None, 
        description="Subscription expiration time in ISO 8601 format"
    )


# ====================== Event/Notification Models ======================

class ReachabilityStatusChangedEvent(BaseModel):
    """
    Event payload for reachability status changes.
    
    Sent to webhook when device reachability status changes.
    """
    model_config = ConfigDict(extra='forbid')
    
    eventType: str = Field(
        default="org.camaraproject.device-reachability-status.v0.reachability-status-changed",
        description="CloudEvent type"
    )
    subscriptionId: str = Field(
        ..., 
        description="Subscription that triggered this event"
    )
    device: Device = Field(
        ..., 
        description="Device that changed status"
    )
    reachabilityStatus: ConnectivityStatus = Field(
        ..., 
        description="New reachability status"
    )
    eventTime: str = Field(
        ..., 
        description="Time of the status change in ISO 8601 format"
    )


class RoamingStatusChangedEvent(BaseModel):
    """
    Event payload for roaming status changes.
    
    Sent to webhook when device roaming status changes.
    """
    model_config = ConfigDict(extra='forbid')
    
    eventType: str = Field(
        default="org.camaraproject.device-roaming-status.v0.roaming-status-changed",
        description="CloudEvent type"
    )
    subscriptionId: str = Field(
        ..., 
        description="Subscription that triggered this event"
    )
    device: Device = Field(
        ..., 
        description="Device that changed status"
    )
    roaming: bool = Field(
        ..., 
        description="New roaming status"
    )
    countryCode: Optional[str] = Field(
        None, 
        description="Country code if roaming"
    )
    countryName: Optional[List[str]] = Field(
        None, 
        description="Country name if roaming"
    )
    eventTime: str = Field(
        ..., 
        description="Time of the status change in ISO 8601 format"
    )


# ====================== MCC Country Mapping ======================

MCC_COUNTRY_MAP = {
    "001": {"code": "XX", "name": "Test Network"},
    "208": {"code": "FR", "name": "France"},
    "310": {"code": "US", "name": "United States"},
    "311": {"code": "US", "name": "United States"},
    "234": {"code": "GB", "name": "United Kingdom"},
    "262": {"code": "DE", "name": "Germany"},
    "222": {"code": "IT", "name": "Italy"},
    "214": {"code": "ES", "name": "Spain"},
    "505": {"code": "AU", "name": "Australia"},
    "440": {"code": "JP", "name": "Japan"},
    "450": {"code": "KR", "name": "South Korea"},
    "460": {"code": "CN", "name": "China"},
    "204": {"code": "NL", "name": "Netherlands"},
    "206": {"code": "BE", "name": "Belgium"},
    "228": {"code": "CH", "name": "Switzerland"},
    "232": {"code": "AT", "name": "Austria"},
    "302": {"code": "CA", "name": "Canada"},
    "334": {"code": "MX", "name": "Mexico"},
    "520": {"code": "TH", "name": "Thailand"},
    "525": {"code": "SG", "name": "Singapore"},
}


def get_country_from_mcc(mcc: str) -> dict:
    """
    Get country information from MCC.
    
    Args:
        mcc: Mobile Country Code (3 digits)
    
    Returns:
        Dict with 'code' (ISO 3166-1 alpha-2) and 'name'
    """
    return MCC_COUNTRY_MAP.get(mcc, {"code": "XX", "name": "Unknown"})
