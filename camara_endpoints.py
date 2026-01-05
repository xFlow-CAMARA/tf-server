"""
CAMARA Quality-On-Demand API Endpoints
Compliant with CAMARA QoD v1.1.0 specification
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
import uuid
from datetime import datetime, timedelta

from camara_models import (
    CreateSession, SessionInfo, ExtendSessionDuration,
    RetrieveSessionsInput, QosStatus, StatusInfo, ErrorInfo
)

router = APIRouter(prefix="/quality-on-demand/v1", tags=["CAMARA QoD"])

# In-memory session storage (production would use database)
qod_sessions = {}


def get_correlator(x_correlator: Optional[str] = None) -> str:
    """Generate or return x-correlator header"""
    return x_correlator or str(uuid.uuid4())


@router.post("/sessions", response_model=SessionInfo, status_code=201)
async def create_qod_session(
    request: CreateSession,
    core: str = "coresim",
    x_correlator: Optional[str] = Header(None)
):
    """
    Create QoS session
    POST /quality-on-demand/v1/sessions
    """
    correlator = get_correlator(x_correlator)
    
    # Validate sink is HTTPS if provided
    if request.sink and not request.sink.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail={
                "status": 400,
                "code": "INVALID_SINK",
                "message": "Sink URL must use HTTPS protocol"
            },
            headers={"x-correlator": correlator}
        )
    
    try:
        # Import here to avoid circular dependency
        from api_server import get_client
        
        client = get_client(core)
        if client is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": 503,
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Service temporarily unavailable"
                },
                headers={"x-correlator": correlator}
            )
        
        # Convert CAMARA format to tf-sdk format
        session_info = {
            "duration": request.duration,
            "qosProfile": request.qosProfile,
            "device": request.device.dict(exclude_none=True) if request.device else None,
            "applicationServer": request.applicationServer.dict(exclude_none=True),
            "sink": request.sink or "https://example.com/notifications",
        }
        
        if request.devicePorts:
            session_info["devicePorts"] = request.devicePorts.dict(exclude_none=True)
        if request.applicationServerPorts:
            session_info["applicationServerPorts"] = request.applicationServerPorts.dict(exclude_none=True)
        
        result = client.create_qod_session(session_info)
        
        # Generate session ID and store
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=request.duration)
        
        session_data = SessionInfo(
            sessionId=session_id,
            duration=request.duration,
            qosProfile=request.qosProfile,
            device=request.device,
            applicationServer=request.applicationServer,
            devicePorts=request.devicePorts,
            applicationServerPorts=request.applicationServerPorts,
            qosStatus=QosStatus.AVAILABLE,
            startedAt=now.isoformat() + "Z",
            expiresAt=expires_at.isoformat() + "Z",
            sink=request.sink,
            sinkCredential=request.sinkCredential
        )
        
        qod_sessions[session_id] = session_data
        
        return session_data
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "status": 400,
                "code": "INVALID_ARGUMENT",
                "message": str(e)
            },
            headers={"x-correlator": correlator}
        )


@router.get("/sessions/{sessionId}", response_model=SessionInfo)
async def get_qod_session(
    sessionId: str,
    x_correlator: Optional[str] = Header(None)
):
    """
    Get QoS session information
    GET /quality-on-demand/v1/sessions/{sessionId}
    """
    correlator = get_correlator(x_correlator)
    
    if sessionId not in qod_sessions:
        raise HTTPException(
            status_code=404,
            detail={
                "status": 404,
                "code": "NOT_FOUND",
                "message": "The specified session is not found"
            },
            headers={"x-correlator": correlator}
        )
    
    return qod_sessions[sessionId]


@router.delete("/sessions/{sessionId}", status_code=204)
async def delete_qod_session(
    sessionId: str,
    x_correlator: Optional[str] = Header(None)
):
    """
    Delete a QoS session
    DELETE /quality-on-demand/v1/sessions/{sessionId}
    """
    correlator = get_correlator(x_correlator)
    
    if sessionId not in qod_sessions:
        raise HTTPException(
            status_code=404,
            detail={
                "status": 404,
                "code": "NOT_FOUND",
                "message": "The specified session is not found"
            },
            headers={"x-correlator": correlator}
        )
    
    # Update status before deletion
    session = qod_sessions[sessionId]
    session.qosStatus = QosStatus.UNAVAILABLE
    session.statusInfo = StatusInfo.DELETE_REQUESTED
    
    del qod_sessions[sessionId]
    return None


@router.post("/sessions/{sessionId}/extend", response_model=SessionInfo)
async def extend_qod_session(
    sessionId: str,
    request: ExtendSessionDuration,
    x_correlator: Optional[str] = Header(None)
):
    """
    Extend the duration of an active session
    POST /quality-on-demand/v1/sessions/{sessionId}/extend
    """
    correlator = get_correlator(x_correlator)
    
    if sessionId not in qod_sessions:
        raise HTTPException(
            status_code=404,
            detail={
                "status": 404,
                "code": "NOT_FOUND",
                "message": "The specified session is not found"
            },
            headers={"x-correlator": correlator}
        )
    
    session = qod_sessions[sessionId]
    
    if session.qosStatus != QosStatus.AVAILABLE:
        raise HTTPException(
            status_code=409,
            detail={
                "status": 409,
                "code": "QUALITY_ON_DEMAND.SESSION_EXTENSION_NOT_ALLOWED",
                "message": f"Extending the session duration is not allowed in the current state ({session.qosStatus}). The session must be in the AVAILABLE state."
            },
            headers={"x-correlator": correlator}
        )
    
    # Extend duration
    session.duration += request.requestedAdditionalDuration
    if session.expiresAt:
        current_expires = datetime.fromisoformat(session.expiresAt.replace('Z', ''))
        new_expires = current_expires + timedelta(seconds=request.requestedAdditionalDuration)
        session.expiresAt = new_expires.isoformat() + "Z"
    
    return session


@router.post("/retrieve-sessions", response_model=List[SessionInfo])
async def retrieve_sessions_by_device(
    request: RetrieveSessionsInput,
    x_correlator: Optional[str] = Header(None)
):
    """
    Get QoS session information for a device
    POST /quality-on-demand/v1/retrieve-sessions
    """
    correlator = get_correlator(x_correlator)
    
    # Find sessions matching the device
    matching_sessions = []
    
    for session in qod_sessions.values():
        if session.device:
            # Match by any provided identifier
            if request.device.ipv4Address and session.device.ipv4Address:
                if request.device.ipv4Address.publicAddress == session.device.ipv4Address.publicAddress:
                    matching_sessions.append(session)
                    continue
            
            if request.device.phoneNumber and session.device.phoneNumber:
                if request.device.phoneNumber == session.device.phoneNumber:
                    matching_sessions.append(session)
                    continue
                    
            if request.device.ipv6Address and session.device.ipv6Address:
                if request.device.ipv6Address == session.device.ipv6Address:
                    matching_sessions.append(session)
                    continue
    
    return matching_sessions
