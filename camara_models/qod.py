"""
CAMARA Quality on Demand (QoD) API Models

Compliant with CAMARA QoD v1.1.0 specification.
https://github.com/camaraproject/QualityOnDemand
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from enum import Enum

from camara_models.common import (
    Device,
    ApplicationServer,
    PortsSpec,
    SinkCredential,
)


# ====================== QoD Enums ======================

class QosStatus(str, Enum):
    """
    Status of the QoS session.
    """
    REQUESTED = "REQUESTED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class StatusInfo(str, Enum):
    """
    Additional status information for QoS sessions.
    Provides reason for session termination or status change.
    """
    DURATION_EXPIRED = "DURATION_EXPIRED"
    NETWORK_TERMINATED = "NETWORK_TERMINATED"
    DELETE_REQUESTED = "DELETE_REQUESTED"


# ====================== QoD Request Models ======================

class CreateSession(BaseModel):
    """
    Request body for creating a QoS session.
    POST /quality-on-demand/v1/sessions
    """
    model_config = ConfigDict(extra='forbid')
    
    device: Optional[Device] = Field(
        None,
        description="Device identifier. Required unless using 3-legged auth."
    )
    applicationServer: ApplicationServer = Field(
        ...,
        description="Application server identifier (required)"
    )
    devicePorts: Optional[PortsSpec] = Field(
        None,
        description="Device port specification for traffic filtering"
    )
    applicationServerPorts: Optional[PortsSpec] = Field(
        None,
        description="Application server port specification"
    )
    qosProfile: str = Field(
        ...,
        description="QoS profile name (e.g., 'qos-e', 'qos-s', 'qos-m', 'qos-l')"
    )
    duration: int = Field(
        ...,
        ge=1,
        description="Session duration in seconds"
    )
    sink: Optional[str] = Field(
        None,
        description="Webhook URL for notifications (must be HTTPS)"
    )
    sinkCredential: Optional[SinkCredential] = Field(
        None,
        description="Credential for webhook authentication"
    )


class ExtendSessionDuration(BaseModel):
    """
    Request body for extending a QoS session duration.
    POST /quality-on-demand/v1/sessions/{sessionId}/extend
    """
    model_config = ConfigDict(extra='forbid')
    
    requestedAdditionalDuration: int = Field(
        ...,
        ge=1,
        description="Additional duration to add in seconds"
    )


class RetrieveSessionsInput(BaseModel):
    """
    Request body for retrieving sessions by device.
    POST /quality-on-demand/v1/retrieve-sessions
    """
    model_config = ConfigDict(extra='forbid')
    
    device: Device = Field(
        ...,
        description="Device identifier to retrieve sessions for"
    )


# ====================== QoD Response Models ======================

class SessionInfo(BaseModel):
    """
    QoS session information response.
    Returned by session creation and retrieval endpoints.
    """
    model_config = ConfigDict(extra='forbid')
    
    sessionId: str = Field(
        ...,
        description="Unique session identifier (UUID)"
    )
    duration: int = Field(
        ...,
        description="Session duration in seconds"
    )
    qosProfile: str = Field(
        ...,
        description="QoS profile name"
    )
    device: Optional[Device] = Field(
        None,
        description="Device identifier"
    )
    applicationServer: ApplicationServer = Field(
        ...,
        description="Application server identifier"
    )
    devicePorts: Optional[PortsSpec] = Field(
        None,
        description="Device port specification"
    )
    applicationServerPorts: Optional[PortsSpec] = Field(
        None,
        description="Application server port specification"
    )
    qosStatus: QosStatus = Field(
        ...,
        description="Current status of the QoS session"
    )
    statusInfo: Optional[StatusInfo] = Field(
        None,
        description="Additional status information"
    )
    startedAt: Optional[str] = Field(
        None,
        description="Session start time in ISO 8601 format"
    )
    expiresAt: Optional[str] = Field(
        None,
        description="Session expiration time in ISO 8601 format"
    )
    sink: Optional[str] = Field(
        None,
        description="Webhook URL for notifications"
    )
    sinkCredential: Optional[SinkCredential] = Field(
        None,
        description="Credential for webhook authentication"
    )
