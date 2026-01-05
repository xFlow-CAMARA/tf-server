"""
CAMARA Traffic Influence API vWIP Router
Fully CAMARA-compliant implementation using tf-sdk
"""

from fastapi import APIRouter, HTTPException, Header, Request, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid
import json

router = APIRouter(prefix="/traffic-influence/vwip", tags=["CAMARA Traffic Influence"])

# Shared network clients (populated by api_server.py)
network_clients = {}

# In-memory storage for traffic influence resources
traffic_influences = {}


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

# CAMARA-compliant models
class PhoneNumber(BaseModel):
    """Phone number in E.164 format"""
    number: str = Field(pattern=r'^\+[1-9][0-9]{4,14}$')

class DeviceIpv4Addr(BaseModel):
    """IPv4 device identifier"""
    publicAddress: str
    privateAddress: Optional[str] = None
    publicPort: Optional[int] = Field(None, ge=0, le=65535)

class Device(BaseModel):
    """Device identifier"""
    phoneNumber: Optional[str] = Field(None, pattern=r'^\+[1-9][0-9]{4,14}$')
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None

class DeviceResponse(BaseModel):
    """Single device identifier in response"""
    phoneNumber: Optional[str] = None
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None

class SourceTrafficFilters(BaseModel):
    """Source traffic filters"""
    sourcePort: Optional[int] = Field(None, ge=0, le=65535)

class DestinationTrafficFilters(BaseModel):
    """Destination traffic filters"""
    destinationPort: Optional[int] = Field(None, ge=0, le=65535)
    destinationProtocol: Optional[str] = None

class TrafficInfluenceState(str, Enum):
    """State of traffic influence resource"""
    ORDERED = "ordered"
    CREATED = "created"
    ACTIVE = "active"
    ERROR = "error"
    DELETION_IN_PROGRESS = "deletion in progress"
    DELETED = "deleted"

class SinkCredential(BaseModel):
    """Sink credential for notifications"""
    credentialType: Literal["ACCESSTOKEN"] = "ACCESSTOKEN"
    accessToken: str
    accessTokenExpiresUtc: str
    accessTokenType: Literal["bearer"] = "bearer"

class CreateSubscriptionDetail(BaseModel):
    """Subscription detail configuration"""
    pass  # Empty for now, can be extended per API requirements

class Config(BaseModel):
    """Configuration for subscription"""
    subscriptionDetail: CreateSubscriptionDetail
    subscriptionExpireTime: Optional[str] = None
    subscriptionMaxEvents: Optional[int] = Field(None, ge=1)
    initialEvent: Optional[bool] = None

class SubscriptionRequest(BaseModel):
    """Subscription request for notifications"""
    protocol: Literal["HTTP"] = "HTTP"
    sink: str = Field(pattern=r'^https://.+$')
    sinkCredential: Optional[SinkCredential] = None
    types: List[str] = ["org.camaraproject.traffic-influence.v1.traffic-influence-change"]
    config: Config

class TrafficInfluence(BaseModel):
    """Traffic influence resource - base model"""
    trafficInfluenceID: Optional[str] = None
    apiConsumerId: str
    appId: str = Field(description="Application UUID")
    appInstanceId: Optional[str] = Field(None, description="Specific app instance UUID")
    edgeCloudRegion: Optional[str] = None
    edgeCloudZoneId: Optional[str] = None
    state: Optional[TrafficInfluenceState] = TrafficInfluenceState.ORDERED
    sourceTrafficFilters: Optional[SourceTrafficFilters] = None
    destinationTrafficFilters: Optional[DestinationTrafficFilters] = None
    subscriptionRequest: Optional[SubscriptionRequest] = None
    
    class Config:
        # Allow extra fields for forward compatibility
        extra = 'ignore'

class PostTrafficInfluence(BaseModel):
    """Request to create traffic influence for any user"""
    apiConsumerId: str
    appId: str
    appInstanceId: Optional[str] = None
    edgeCloudRegion: Optional[str] = None
    edgeCloudZoneId: Optional[str] = None
    sourceTrafficFilters: Optional[SourceTrafficFilters] = None
    destinationTrafficFilters: Optional[DestinationTrafficFilters] = None
    subscriptionRequest: Optional[SubscriptionRequest] = None

class PostTrafficInfluenceDevice(PostTrafficInfluence):
    """Request to create traffic influence for specific device"""
    device: Device

class PatchTrafficInfluence(BaseModel):
    """Request to update traffic influence"""
    appInstanceId: Optional[str] = None
    edgeCloudRegion: Optional[str] = None
    edgeCloudZoneId: Optional[str] = None
    sourceTrafficFilters: Optional[SourceTrafficFilters] = None
    destinationTrafficFilters: Optional[DestinationTrafficFilters] = None
    subscriptionRequest: Optional[SubscriptionRequest] = None

class ErrorInfo(BaseModel):
    """CAMARA error response"""
    status: int
    code: str
    message: str


def get_client(core: str):
    """Get network client for the specified core"""
    if core not in network_clients:
        return None
    return network_clients[core]

def simulate_traffic_influence(
    resource_id: str,
    app_id: str,
    device: Optional[Device] = None,
    region: Optional[str] = None,
    zone: Optional[str] = None
) -> Dict[str, Any]:
    """
    Simulate traffic influence configuration.
    In production, this would call the actual network traffic influence service.
    """
    # Simulate selecting best app instance
    selected_instance = str(uuid.uuid4())
    
    return {
        "trafficInfluenceID": resource_id,
        "state": TrafficInfluenceState.ACTIVE,
        "selected_appInstanceId": [selected_instance],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@router.get("/traffic-influences", response_model=List[TrafficInfluence])
async def get_all_traffic_influences(
    response: Response,
    appId: Optional[str] = Query(None, description="Filter by application ID"),
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Traffic Influence vWIP: Get all traffic influence resources
    GET /traffic-influence/vwip/traffic-influences
    
    Optionally filter by appId. For privacy, device information is not returned.
    Returns: 200 OK with list of resources
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    client = get_client(core)
    if client is None:
        return camara_error_response(503, "SERVICE_UNAVAILABLE", f"Core '{core}' not available", correlator)
    
    results = []
    for ti_id, ti_data in traffic_influences.items():
        if appId and ti_data.get("appId") != appId:
            continue
        
        # Remove device info for privacy when listing
        ti_copy = ti_data.copy()
        ti_copy.pop("device", None)
        results.append(ti_copy)
    
    return results

@router.post("/traffic-influences", status_code=201, response_model=TrafficInfluence)
async def create_traffic_influence(
    raw_request: Request,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Traffic Influence vWIP: Create traffic influence for any user
    POST /traffic-influence/vwip/traffic-influences
    
    Influences traffic routing toward optimal Edge Application Server instances.
    Returns: 201 Created with Location header
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    try:
        body = await raw_request.json()
        request_data = PostTrafficInfluence(**body)
        
        client = get_client(core)
        if client is None:
            return camara_error_response(503, "SERVICE_UNAVAILABLE", f"Core '{core}' not available", correlator)
        
        # Build traffic influence info for SDK
        ti_info = {
            "apiConsumerId": request_data.apiConsumerId,
            "appId": request_data.appId,
        }
        
        # Add optional fields
        if request_data.appInstanceId:
            ti_info["appInstanceId"] = request_data.appInstanceId
        if request_data.edgeCloudRegion:
            ti_info["edgeCloudRegion"] = request_data.edgeCloudRegion
        if request_data.edgeCloudZoneId:
            ti_info["edgeCloudZoneId"] = request_data.edgeCloudZoneId
        if request_data.sourceTrafficFilters:
            ti_info["sourceTrafficFilters"] = request_data.sourceTrafficFilters.model_dump()
        if request_data.destinationTrafficFilters:
            ti_info["destinationTrafficFilters"] = request_data.destinationTrafficFilters.model_dump()
        
        # Call SDK to create traffic influence
        try:
            sdk_response = client.create_traffic_influence_resource(ti_info)
            resource_id = sdk_response.get("trafficInfluenceID") or str(uuid.uuid4())
        except Exception as tf_error:
            error_msg = str(tf_error)
            return camara_error_response(500, "INTERNAL", f"Internal error: {error_msg[:100]}", correlator)
        
        # Add Location header as per CAMARA spec
        response.headers["Location"] = f"/traffic-influence/vwip/traffic-influences/{resource_id}"
        
        # Build CAMARA-compliant response
        ti_resource = {
            "trafficInfluenceID": resource_id,
            "apiConsumerId": request_data.apiConsumerId,
            "appId": request_data.appId,
            "state": TrafficInfluenceState.ACTIVE.value,
        }
        
        # Add optional fields
        if request_data.appInstanceId:
            ti_resource["appInstanceId"] = request_data.appInstanceId
        if request_data.edgeCloudRegion:
            ti_resource["edgeCloudRegion"] = request_data.edgeCloudRegion
        if request_data.edgeCloudZoneId:
            ti_resource["edgeCloudZoneId"] = request_data.edgeCloudZoneId
        if request_data.sourceTrafficFilters:
            ti_resource["sourceTrafficFilters"] = request_data.sourceTrafficFilters.model_dump()
        if request_data.destinationTrafficFilters:
            ti_resource["destinationTrafficFilters"] = request_data.destinationTrafficFilters.model_dump()
        if request_data.subscriptionRequest:
            ti_resource["subscriptionRequest"] = request_data.subscriptionRequest.model_dump()
        
        # Store resource
        traffic_influences[resource_id] = ti_resource
        
        return JSONResponse(
            status_code=201,
            content=ti_resource,
            headers={
                "x-correlator": correlator,
                "Location": f"/traffic-influence/vwip/traffic-influences/{resource_id}"
            }
        )
        
    except ValidationError as e:
        return camara_error_response(400, "INVALID_ARGUMENT", f"Invalid request: {str(e)}", correlator)
    except Exception as e:
        return camara_error_response(500, "INTERNAL", "Internal server error", correlator)


@router.post("/traffic-influence-devices", status_code=201, response_model=TrafficInfluence)
async def create_traffic_influence_device(
    raw_request: Request,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Traffic Influence vWIP: Create traffic influence for specific device
    POST /traffic-influence/vwip/traffic-influence-devices
    
    Influences traffic routing for a specific user device.
    Returns: 201 Created with Location header
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    try:
        body = await raw_request.json()
        request_data = PostTrafficInfluenceDevice(**body)
        
        # Validate device is provided
        if not request_data.device:
            return camara_error_response(422, "MISSING_IDENTIFIER", 
                "Device identifier is required for this endpoint", correlator)
        
        client = get_client(core)
        if client is None:
            return camara_error_response(503, "SERVICE_UNAVAILABLE", f"Core '{core}' not available", correlator)
        
        # Build traffic influence info for SDK with proper device format
        ti_info = {
            "apiConsumerId": request_data.apiConsumerId,
            "appId": request_data.appId,
            "appInstanceId": request_data.appInstanceId or "default-instance",
            "notificationUri": "http://callback.example.com/notifications",
        }
        
        # Handle device - ensure CAMARA-compliant structure
        if request_data.device:
            device_dict = {}
            
            if request_data.device.phoneNumber:
                device_dict["phoneNumber"] = request_data.device.phoneNumber
            
            if request_data.device.ipv4Address:
                ipv4_dict = {
                    "publicAddress": request_data.device.ipv4Address.publicAddress,
                }
                # Add privateAddress (required by NEF) - default to publicAddress
                if request_data.device.ipv4Address.privateAddress:
                    ipv4_dict["privateAddress"] = request_data.device.ipv4Address.privateAddress
                else:
                    ipv4_dict["privateAddress"] = request_data.device.ipv4Address.publicAddress
                
                if request_data.device.ipv4Address.publicPort:
                    ipv4_dict["publicPort"] = request_data.device.ipv4Address.publicPort
                
                device_dict["ipv4Address"] = ipv4_dict
            
            if request_data.device.ipv6Address:
                device_dict["ipv6Address"] = request_data.device.ipv6Address
            
            if request_data.device.networkAccessIdentifier:
                device_dict["networkAccessIdentifier"] = request_data.device.networkAccessIdentifier
            
            ti_info["device"] = device_dict
        
        # Add optional fields
        if request_data.appInstanceId:
            ti_info["appInstanceId"] = request_data.appInstanceId
        if request_data.edgeCloudRegion:
            ti_info["edgeCloudRegion"] = request_data.edgeCloudRegion
        if request_data.edgeCloudZoneId:
            ti_info["edgeCloudZoneId"] = request_data.edgeCloudZoneId
        if request_data.sourceTrafficFilters:
            ti_info["sourceTrafficFilters"] = request_data.sourceTrafficFilters.model_dump()
        if request_data.destinationTrafficFilters:
            ti_info["destinationTrafficFilters"] = request_data.destinationTrafficFilters.model_dump()
        
        # Call SDK to create traffic influence
        try:
            sdk_response = client.create_traffic_influence_resource(ti_info)
            resource_id = sdk_response.get("trafficInfluenceID") or str(uuid.uuid4())
        except Exception as tf_error:
            error_msg = str(tf_error)
            
            # Map network errors to CAMARA error codes
            if ("not connected" in error_msg.lower() or 
                "not found" in error_msg.lower() or 
                "redis: nil" in error_msg.lower() or
                "failed to get ue" in error_msg.lower() or
                "could not create pcf policy" in error_msg.lower()):
                return camara_error_response(404, "DEVICE_NOT_FOUND",
                    "Device not registered or no active PDU session", correlator)
            else:
                return camara_error_response(500, "INTERNAL",
                    f"Internal error: {error_msg[:100]}", correlator)
        
        # Add Location header as per CAMARA spec
        response.headers["Location"] = f"/traffic-influence/vwip/traffic-influences/{resource_id}"
        
        # Build CAMARA-compliant response
        ti_resource = {
            "trafficInfluenceID": resource_id,
            "apiConsumerId": request_data.apiConsumerId,
            "appId": request_data.appId,
            "state": TrafficInfluenceState.ACTIVE.value,
            "device": request_data.device.model_dump(exclude_none=True),
        }
        
        # Add optional fields
        if request_data.appInstanceId:
            ti_resource["appInstanceId"] = request_data.appInstanceId
        if request_data.edgeCloudRegion:
            ti_resource["edgeCloudRegion"] = request_data.edgeCloudRegion
        if request_data.edgeCloudZoneId:
            ti_resource["edgeCloudZoneId"] = request_data.edgeCloudZoneId
        if request_data.sourceTrafficFilters:
            ti_resource["sourceTrafficFilters"] = request_data.sourceTrafficFilters.model_dump()
        if request_data.destinationTrafficFilters:
            ti_resource["destinationTrafficFilters"] = request_data.destinationTrafficFilters.model_dump()
        if request_data.subscriptionRequest:
            ti_resource["subscriptionRequest"] = request_data.subscriptionRequest.model_dump()
        
        # Store resource
        traffic_influences[resource_id] = ti_resource
        
        return JSONResponse(
            status_code=201,
            content=ti_resource,
            headers={
                "x-correlator": correlator,
                "Location": f"/traffic-influence/vwip/traffic-influences/{resource_id}"
            }
        )
        
    except ValidationError as e:
        return camara_error_response(400, "INVALID_ARGUMENT", f"Invalid request: {str(e)}", correlator)
    except Exception as e:
        return camara_error_response(500, "INTERNAL", "Internal server error", correlator)


@router.get("/traffic-influences/{trafficInfluenceID}", response_model=TrafficInfluence)
async def get_traffic_influence_by_id(
    trafficInfluenceID: str,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Traffic Influence vWIP: Get traffic influence by ID
    GET /traffic-influence/vwip/traffic-influences/{trafficInfluenceID}
    
    For privacy, device information is not returned.
    Returns: 200 OK with resource info
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    client = get_client(core)
    if client is None:
        return camara_error_response(503, "SERVICE_UNAVAILABLE", f"Core '{core}' not available", correlator)
    
    if trafficInfluenceID not in traffic_influences:
        return camara_error_response(404, "NOT_FOUND", 
            f"Traffic influence resource {trafficInfluenceID} not found", correlator)
    
    # Return without device info for privacy
    ti_data = traffic_influences[trafficInfluenceID].copy()
    ti_data.pop("device", None)
    return ti_data


@router.patch("/traffic-influences/{trafficInfluenceID}", response_model=TrafficInfluence)
async def patch_traffic_influence(
    trafficInfluenceID: str,
    raw_request: Request,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Traffic Influence vWIP: Update traffic influence
    PATCH /traffic-influence/vwip/traffic-influences/{trafficInfluenceID}
    
    Resource must be in 'active' state. Device cannot be modified.
    Returns: 200 OK with Location header
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    try:
        if trafficInfluenceID not in traffic_influences:
            return camara_error_response(404, "NOT_FOUND",
                f"Traffic influence resource {trafficInfluenceID} not found", correlator)
        
        ti_resource = traffic_influences[trafficInfluenceID]
        
        # Add Location header
        response.headers["Location"] = f"/traffic-influence/vwip/traffic-influences/{trafficInfluenceID}"
        
        # Check if resource is active
        if ti_resource["state"] != TrafficInfluenceState.ACTIVE.value:
            return camara_error_response(409, "DENIED_WAIT",
                "Resource must be in 'active' state before modification", correlator)
        
        body = await raw_request.json()
        patch_data = PatchTrafficInfluence(**body)
        
        # Update allowed fields
        if patch_data.appInstanceId is not None:
            ti_resource["appInstanceId"] = patch_data.appInstanceId
        if patch_data.edgeCloudRegion is not None:
            ti_resource["edgeCloudRegion"] = patch_data.edgeCloudRegion
        if patch_data.edgeCloudZoneId is not None:
            ti_resource["edgeCloudZoneId"] = patch_data.edgeCloudZoneId
        if patch_data.sourceTrafficFilters is not None:
            ti_resource["sourceTrafficFilters"] = patch_data.sourceTrafficFilters.model_dump()
        if patch_data.destinationTrafficFilters is not None:
            ti_resource["destinationTrafficFilters"] = patch_data.destinationTrafficFilters.model_dump()
        if patch_data.subscriptionRequest is not None:
            ti_resource["subscriptionRequest"] = patch_data.subscriptionRequest.model_dump()
        
        # Mark as ordered, will transition back to active
        ti_resource["state"] = TrafficInfluenceState.ORDERED.value
        
        # Simulate re-activation
        try:
            result = simulate_traffic_influence(
                trafficInfluenceID,
                ti_resource["appId"],
                device=Device(**ti_resource["device"]) if "device" in ti_resource else None,
                region=ti_resource.get("edgeCloudRegion"),
                zone=ti_resource.get("edgeCloudZoneId")
            )
            ti_resource["state"] = TrafficInfluenceState.ACTIVE.value
        except Exception as e:
            ti_resource["state"] = TrafficInfluenceState.ERROR.value
        
        # Return without device info
        result_data = ti_resource.copy()
        result_data.pop("device", None)
        return result_data
        
    except ValidationError as e:
        return camara_error_response(400, "INVALID_ARGUMENT", f"Invalid request: {str(e)}", correlator)
    except Exception as e:
        return camara_error_response(500, "INTERNAL", "Internal server error", correlator)


@router.delete("/traffic-influences/{trafficInfluenceID}", status_code=202)
async def delete_traffic_influence(
    trafficInfluenceID: str,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Traffic Influence vWIP: Delete traffic influence
    DELETE /traffic-influence/vwip/traffic-influences/{trafficInfluenceID}
    
    Returns: 202 Accepted (async deletion)
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    client = get_client(core)
    if client is None:
        return camara_error_response(503, "SERVICE_UNAVAILABLE", f"Core '{core}' not available", correlator)
    
    if trafficInfluenceID not in traffic_influences:
        return camara_error_response(404, "NOT_FOUND",
            f"Traffic influence resource {trafficInfluenceID} not found", correlator)
    
    # Mark as deletion in progress, then delete
    traffic_influences[trafficInfluenceID]["state"] = TrafficInfluenceState.DELETION_IN_PROGRESS.value
    del traffic_influences[trafficInfluenceID]
    
    # Return empty 202 response per CAMARA spec
    return JSONResponse(status_code=202, content={}, headers={"x-correlator": correlator})

# Health check endpoint
@router.get("/health")
async def health_check(response: Response):
    """Health check for traffic influence service"""
    response.headers["x-correlator"] = str(uuid.uuid4())
    return {
        "status": "healthy",
        "service": "CAMARA Traffic Influence API",
        "version": "vwip",
        "active_resources": len(traffic_influences)
    }
