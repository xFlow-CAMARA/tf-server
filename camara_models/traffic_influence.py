"""
CAMARA Traffic Influence API Models

Compliant with CAMARA Traffic Influence vWIP specification.
https://github.com/camaraproject/EdgeCloud
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal
from enum import Enum

from camara_models.common import Device, DeviceResponse, SinkCredential


# ====================== Traffic Influence Enums ======================

class TrafficInfluenceState(str, Enum):
    """
    State of a traffic influence resource.
    Follows the state machine: ordered → created → active → deletion in progress → deleted
    """
    ORDERED = "ordered"
    CREATED = "created"
    ACTIVE = "active"
    ERROR = "error"
    DELETION_IN_PROGRESS = "deletion in progress"
    DELETED = "deleted"


class TrafficInfluenceNotificationType(str, Enum):
    """
    Types of traffic influence notifications.
    """
    STATE_CHANGED = "org.camaraproject.traffic-influence.v0.state-changed"
    RESOURCE_DELETED = "org.camaraproject.traffic-influence.v0.resource-deleted"


# ====================== Traffic Filter Models ======================

class SourceTrafficFilters(BaseModel):
    """
    Source traffic filters for traffic influence.
    """
    model_config = ConfigDict(extra='forbid')
    
    sourcePort: Optional[int] = Field(
        None,
        ge=0,
        le=65535,
        description="Source port number"
    )


class DestinationTrafficFilters(BaseModel):
    """
    Destination traffic filters for traffic influence.
    """
    model_config = ConfigDict(extra='forbid')
    
    destinationPort: Optional[int] = Field(
        None,
        ge=0,
        le=65535,
        description="Destination port number"
    )
    destinationProtocol: Optional[str] = Field(
        None,
        description="Protocol (e.g., 'TCP', 'UDP')"
    )


# ====================== Subscription Models ======================

class SubscriptionDetail(BaseModel):
    """
    Subscription detail for notifications.
    """
    model_config = ConfigDict(extra='forbid')
    pass  # Can be extended per specific requirements


class SubscriptionConfig(BaseModel):
    """
    Configuration for traffic influence subscriptions.
    """
    model_config = ConfigDict(extra='forbid')
    
    subscriptionDetail: Optional[SubscriptionDetail] = None
    subscriptionExpireTime: Optional[str] = Field(
        None,
        description="Expiration time in ISO 8601 format"
    )
    subscriptionMaxEvents: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum number of events before subscription expires"
    )


# ====================== Traffic Influence Request Models ======================

class TrafficInfluenceRequest(BaseModel):
    """
    Request body for creating a traffic influence resource.
    POST /traffic-influence/vwip/traffic-influences
    POST /traffic-influence/vwip/traffic-influence-devices
    """
    model_config = ConfigDict(extra='forbid')
    
    appId: str = Field(
        ...,
        description="Application identifier"
    )
    device: Optional[Device] = Field(
        None,
        description="Device identifier (required for device-specific endpoint)"
    )
    sourceTrafficFilters: Optional[SourceTrafficFilters] = Field(
        None,
        description="Source traffic filters"
    )
    destinationTrafficFilters: Optional[DestinationTrafficFilters] = Field(
        None,
        description="Destination traffic filters"
    )
    sink: Optional[str] = Field(
        None,
        description="Webhook URL for notifications"
    )
    sinkCredential: Optional[SinkCredential] = Field(
        None,
        description="Credential for webhook authentication"
    )
    config: Optional[SubscriptionConfig] = Field(
        None,
        description="Subscription configuration"
    )


class TrafficInfluenceUpdate(BaseModel):
    """
    Request body for updating a traffic influence resource.
    PATCH /traffic-influence/vwip/traffic-influences/{trafficInfluenceId}
    """
    model_config = ConfigDict(extra='forbid')
    
    sourceTrafficFilters: Optional[SourceTrafficFilters] = None
    destinationTrafficFilters: Optional[DestinationTrafficFilters] = None
    sink: Optional[str] = None
    sinkCredential: Optional[SinkCredential] = None
    config: Optional[SubscriptionConfig] = None


# ====================== Traffic Influence Response Models ======================

class TrafficInfluenceResponse(BaseModel):
    """
    Traffic influence resource response.
    Returned by creation, retrieval, and update endpoints.
    """
    model_config = ConfigDict(extra='forbid')
    
    trafficInfluenceId: str = Field(
        ...,
        description="Unique identifier for the traffic influence resource"
    )
    appId: str = Field(
        ...,
        description="Application identifier"
    )
    device: Optional[DeviceResponse] = Field(
        None,
        description="Device identifier (excluded in list responses for privacy)"
    )
    state: TrafficInfluenceState = Field(
        ...,
        description="Current state of the resource"
    )
    sourceTrafficFilters: Optional[SourceTrafficFilters] = None
    destinationTrafficFilters: Optional[DestinationTrafficFilters] = None
    sink: Optional[str] = None
    sinkCredential: Optional[SinkCredential] = None
    config: Optional[SubscriptionConfig] = None
    startsAt: Optional[str] = Field(
        None,
        description="Start time in ISO 8601 format"
    )
    expiresAt: Optional[str] = Field(
        None,
        description="Expiration time in ISO 8601 format"
    )


# ====================== Notification Models ======================

class TrafficInfluenceNotification(BaseModel):
    """
    CloudEvents notification for traffic influence state changes.
    """
    model_config = ConfigDict(extra='forbid')
    
    specversion: str = Field("1.0", description="CloudEvents spec version")
    type: TrafficInfluenceNotificationType = Field(
        ...,
        description="Event type"
    )
    source: str = Field(
        ...,
        description="Event source URI"
    )
    id: str = Field(
        ...,
        description="Unique event identifier"
    )
    time: str = Field(
        ...,
        description="Event timestamp in ISO 8601 format"
    )
    datacontenttype: str = Field(
        "application/json",
        description="Content type of data"
    )
    data: TrafficInfluenceResponse = Field(
        ...,
        description="Event payload containing the traffic influence resource"
    )
