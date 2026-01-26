"""
CAMARA Quality-On-Demand API v1.1.0 Router
Fully CAMARA-compliant implementation using tf-sdk
"""

from fastapi import APIRouter, HTTPException, Header, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import json
from mongodb_client import get_mongo_client

router = APIRouter(prefix="/quality-on-demand/v1", tags=["CAMARA QoD"])

# CAMARA-compliant models  
class DeviceIpv4Addr(BaseModel):
    publicAddress: str
    privateAddress: Optional[str] = None
    publicPort: Optional[int] = None

class Device(BaseModel):
    phoneNumber: Optional[str] = None
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None

class ApplicationServer(BaseModel):
    ipv4Address: Optional[str] = None
    ipv6Address: Optional[str] = None

class PortRange(BaseModel):
    from_port: int = Field(..., alias="from")
    to_port: int = Field(..., alias="to")

class PortsSpec(BaseModel):
    ranges: Optional[List[PortRange]] = None
    ports: Optional[List[int]] = None

class SinkCredential(BaseModel):
    credentialType: str = "ACCESSTOKEN"
    accessToken: str
    accessTokenExpiresUtc: str
    accessTokenType: str = "bearer"

class CreateSession(BaseModel):
    device: Optional[Device] = None
    applicationServer: ApplicationServer
    devicePorts: Optional[PortsSpec] = None
    applicationServerPorts: Optional[PortsSpec] = None
    qosProfile: str
    duration: int = Field(..., ge=1)
    sink: Optional[str] = None
    sinkCredential: Optional[SinkCredential] = None

class ExtendSessionDuration(BaseModel):
    requestedAdditionalDuration: int = Field(..., ge=1)

class RetrieveSessionsInput(BaseModel):
    device: Device

class SessionInfo(BaseModel):
    device: Optional[Device] = None
    applicationServer: ApplicationServer
    devicePorts: Optional[PortsSpec] = None
    applicationServerPorts: Optional[PortsSpec] = None
    qosProfile: str
    sink: Optional[str] = None
    sinkCredential: Optional[SinkCredential] = None
    sessionId: str
    duration: int
    startedAt: Optional[str] = None
    expiresAt: Optional[str] = None
    qosStatus: str
    statusInfo: Optional[str] = None

# In-memory session storage
qod_sessions = {}

# Will be set by main api_server.py
network_clients = {}


def get_correlator(x_correlator: Optional[str]) -> str:
    """Generate or return x-correlator header"""
    return x_correlator or str(uuid.uuid4())


def camara_error_response(
    status: int,
    code: str,
    message: str,
    correlator: str
) -> JSONResponse:
    """Create a CAMARA-compliant error response with proper headers"""
    return JSONResponse(
        status_code=status,
        content={"status": status, "code": code, "message": message},
        headers={"x-correlator": correlator}
    )


def get_client(core: str):
    """Get network client for specified core"""
    return network_clients.get(core.lower())

@router.post("/sessions", status_code=201)
async def create_qod_session(
    raw_request: Request,
    response: Response,
    core: str = "coresim",
    x_correlator: str = Header(None)
):
    """
    CAMARA QoD v1.1.0: Create QoS session
    POST /quality-on-demand/v1/sessions
    Returns: 201 Created with session info
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    # Parse request body
    try:
        body = await raw_request.json()
        session_request = CreateSession(**body)
    except ValidationError as e:
        return camara_error_response(400, "INVALID_ARGUMENT", "Client specified an invalid argument, request body or query param.", correlator)
    except Exception as e:
        return camara_error_response(400, "INVALID_ARGUMENT", "Client specified an invalid argument, request body or query param.", correlator)
    
    # Get network client
    client = get_client(core)
    if client is None:
        return camara_error_response(500, "INTERNAL", "Internal server error.", correlator)
    
    # Build session_info for SDK with proper device format
    try:
        session_info = {
            "duration": session_request.duration,
            "qosProfile": session_request.qosProfile,
            "applicationServer": session_request.applicationServer.model_dump(exclude_none=True),
            "sink": session_request.sink or "https://example.com/notifications",
        }
        
        # Handle device - ensure CAMARA-compliant structure
        if session_request.device:
            device_dict = {}
            
            if session_request.device.phoneNumber:
                device_dict["phoneNumber"] = session_request.device.phoneNumber
            
            if session_request.device.ipv4Address:
                ipv4_dict = {
                    "publicAddress": session_request.device.ipv4Address.publicAddress,
                }
                # Add privateAddress (required by NEF) - default to publicAddress for CoreSim
                if session_request.device.ipv4Address.privateAddress:
                    ipv4_dict["privateAddress"] = session_request.device.ipv4Address.privateAddress
                else:
                    ipv4_dict["privateAddress"] = session_request.device.ipv4Address.publicAddress
                
                if session_request.device.ipv4Address.publicPort:
                    ipv4_dict["publicPort"] = session_request.device.ipv4Address.publicPort
                
                device_dict["ipv4Address"] = ipv4_dict
            
            if session_request.device.ipv6Address:
                device_dict["ipv6Address"] = session_request.device.ipv6Address
            
            if session_request.device.networkAccessIdentifier:
                device_dict["networkAccessIdentifier"] = session_request.device.networkAccessIdentifier
            
            session_info["device"] = device_dict
        
        # Add optional ports
        if session_request.devicePorts:
            session_info["devicePorts"] = session_request.devicePorts.model_dump(exclude_none=True)
        if session_request.applicationServerPorts:
            session_info["applicationServerPorts"] = session_request.applicationServerPorts.model_dump(exclude_none=True)
        
        # Call tf-sdk to create session
        result = client.create_qod_session(session_info)
        
    except Exception as tf_error:
        error_msg = str(tf_error)
        print(f"QoD Session Creation Error: {error_msg}")
        print(f"Error type: {type(tf_error).__name__}")
        import traceback
        traceback.print_exc()
        # Map network errors to CAMARA error codes
        if "not connected" in error_msg.lower() or "not found" in error_msg.lower():
            return camara_error_response(404, "IDENTIFIER_NOT_FOUND", 
                "Device identifier not found.", correlator)
        elif "invalid" in error_msg.lower():
            return camara_error_response(400, "INVALID_ARGUMENT",
                "Client specified an invalid argument, request body or query param.", correlator)
        else:
            return camara_error_response(500, "INTERNAL",
                "Internal server error.", correlator)
        
    # Create session response
    session_id = str(uuid.uuid4())
    
    # Per CAMARA spec: initially return REQUESTED status
    # Session becomes AVAILABLE after network confirmation
    session_data = SessionInfo(
        device=session_request.device,
        applicationServer=session_request.applicationServer,
        devicePorts=session_request.devicePorts,
        applicationServerPorts=session_request.applicationServerPorts,
        qosProfile=session_request.qosProfile,
        sink=session_request.sink,
        sinkCredential=session_request.sinkCredential,
        sessionId=session_id,
        duration=session_request.duration,
        qosStatus="REQUESTED",
        # startedAt and expiresAt are not included when qosStatus is REQUESTED
        startedAt=None,
        expiresAt=None,
        statusInfo=None
    )
    
    qod_sessions[session_id] = session_data
    
    # Save to MongoDB (only successful responses, no errors)
    try:
        mongo_client = get_mongo_client()
        mongo_client.save_qod_session(
            session_id=session_id,
            operation="CREATE",
            request_data=body,
            response_data=session_data.model_dump(exclude_none=True),
            status_code=201,
            device=session_request.device.model_dump(exclude_none=True) if session_request.device else None,
            qos_profile=session_request.qosProfile,
        )
    except Exception as mongo_error:
        # Log error but don't fail the request
        print(f"MongoDB save error: {mongo_error}")
    
    # Return 201 Created with session info
    return JSONResponse(
        status_code=201,
        content=session_data.model_dump(exclude_none=True),
        headers={"x-correlator": correlator}
    )


@router.get("/sessions/{sessionId}", response_model=SessionInfo)
async def get_qod_session(
    sessionId: str,
    response: Response,
    x_correlator: str = Header(None)
):
    """
    CAMARA QoD v1.1.0: Get QoS session
    GET /quality-on-demand/v1/sessions/{sessionId}
    Returns: 200 OK with session info
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    if sessionId not in qod_sessions:
        return camara_error_response(404, "NOT_FOUND", "The specified resource is not found.", correlator)
    
    session_data = qod_sessions[sessionId]
    
    # Save GET operation to MongoDB
    try:
        mongo_client = get_mongo_client()
        mongo_client.save_qod_session(
            session_id=sessionId,
            operation="GET",
            request_data={"sessionId": sessionId},
            response_data=session_data.model_dump(exclude_none=True),
            status_code=200,
        )
    except Exception as mongo_error:
        print(f"MongoDB save error: {mongo_error}")
    
    return session_data


@router.delete("/sessions/{sessionId}", status_code=204)
async def delete_qod_session(
    sessionId: str,
    response: Response,
    x_correlator: str = Header(None)
):
    """
    CAMARA QoD v1.1.0: Delete QoS session
    DELETE /quality-on-demand/v1/sessions/{sessionId}
    Returns: 204 No Content
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    if sessionId not in qod_sessions:
        return camara_error_response(404, "NOT_FOUND", "The specified resource is not found.", correlator)
    
    session = qod_sessions[sessionId]
    session_data_before_delete = session.model_dump(exclude_none=True)
    session.qosStatus = "UNAVAILABLE"
    session.statusInfo = "DELETE_REQUESTED"
    del qod_sessions[sessionId]
    
    # Save DELETE operation to MongoDB
    try:
        mongo_client = get_mongo_client()
        mongo_client.save_qod_session(
            session_id=sessionId,
            operation="DELETE",
            request_data={"sessionId": sessionId},
            response_data=session_data_before_delete,
            status_code=204,
        )
    except Exception as mongo_error:
        print(f"MongoDB save error: {mongo_error}")
    
    # 204 No Content - FastAPI handles this automatically with status_code=204
    response.headers["x-correlator"] = correlator
    return Response(status_code=204, headers={"x-correlator": correlator})


@router.post("/sessions/{sessionId}/extend", response_model=SessionInfo)
async def extend_qod_session(
    sessionId: str,
    request: ExtendSessionDuration,
    response: Response,
    x_correlator: str = Header(None)
):
    """
    CAMARA QoD v1.1.0: Extend session duration
    POST /quality-on-demand/v1/sessions/{sessionId}/extend
    Returns: 200 OK with updated session info
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    if sessionId not in qod_sessions:
        return camara_error_response(404, "NOT_FOUND", "The specified resource is not found.", correlator)
    
    session = qod_sessions[sessionId]
    
    if session.qosStatus != "AVAILABLE":
        return camara_error_response(
            409,
            "QUALITY_ON_DEMAND.SESSION_EXTENSION_NOT_ALLOWED",
            f"Extending the session duration is not allowed in the current state ({session.qosStatus}). The session must be in the AVAILABLE state.",
            correlator
        )
    
    session.duration += request.requestedAdditionalDuration
    if session.expiresAt:
        current_expires = datetime.fromisoformat(session.expiresAt.replace('Z', ''))
        new_expires = current_expires + timedelta(seconds=request.requestedAdditionalDuration)
        session.expiresAt = new_expires.isoformat() + "Z"
    
    return session


@router.post("/retrieve-sessions", response_model=List[SessionInfo])
async def retrieve_sessions_by_device(
    request: RetrieveSessionsInput,
    response: Response,
    x_correlator: str = Header(None)
):
    """
    CAMARA QoD v1.1.0: Get sessions for a device
    POST /quality-on-demand/v1/retrieve-sessions
    Returns: 200 OK with list of sessions
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    matching_sessions = []
    
    for session in qod_sessions.values():
        if session.device:
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
