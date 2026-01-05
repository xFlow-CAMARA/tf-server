"""
CAMARA Device Location Retrieval API v0.5.0 Router
Fully CAMARA-compliant implementation using tf-sdk
"""

from fastapi import APIRouter, HTTPException, Header, Request, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import Optional, List, Literal, Union, Annotated
from datetime import datetime
import uuid
import json
import os

# Import SDK schemas
from sunrise6g_opensdk.network.core.schemas import (
    RetrievalLocationRequest,
    Device as SDKDevice,
    DeviceIpv4Addr as SDKDeviceIpv4Addr
)

router = APIRouter(prefix="/location-retrieval/v0", tags=["CAMARA Location"])

# Shared network clients (populated by api_server.py)
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


# CAMARA-compliant models
class PhoneNumber(BaseModel):
    """A phone number in E.164 format"""
    number: str = Field(pattern=r'^\+[1-9][0-9]{4,14}$')

class DeviceIpv4Addr(BaseModel):
    """IPv4 device identifier"""
    publicAddress: str = Field(description="Public IPv4 address")
    privateAddress: Optional[str] = None
    publicPort: Optional[int] = Field(None, ge=0, le=65535)

class Device(BaseModel):
    """Device identifier - at least one field required"""
    phoneNumber: Optional[str] = Field(None, pattern=r'^\+[1-9][0-9]{4,14}$')
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None

class RetrievalLocationRequest(BaseModel):
    """Request to retrieve device location"""
    device: Optional[Device] = None
    maxAge: Optional[int] = Field(None, description="Maximum age of location in seconds")
    maxSurface: Optional[int] = Field(None, ge=1, description="Maximum surface in square meters")

class Point(BaseModel):
    """Geographic coordinate point"""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

class Circle(BaseModel):
    """Circular area definition"""
    areaType: Literal["CIRCLE"] = "CIRCLE"
    center: Point
    radius: float = Field(ge=1, description="Radius in meters")

class Polygon(BaseModel):
    """Polygonal area definition"""
    areaType: Literal["POLYGON"] = "POLYGON"
    boundary: List[Point] = Field(min_length=3, max_length=15)

# Union type for area (discriminated by areaType)
Area = Annotated[Union[Circle, Polygon], Field(discriminator="areaType")]

class DeviceResponse(BaseModel):
    """Single device identifier in response"""
    phoneNumber: Optional[str] = None
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None

class Location(BaseModel):
    """Location retrieval response"""
    lastLocationTime: str = Field(description="ISO 8601 timestamp with timezone")
    area: Area
    device: Optional[DeviceResponse] = None

# In-memory storage for location data (demo purposes)
location_cache = {}

def get_client(core: str):
    """Get network client for the specified core"""
    if core not in network_clients:
        return None
    return network_clients[core]

def build_device_info(device: Optional[Device]) -> dict:
    """Convert Device model to tf-sdk format"""
    if not device:
        return {}
    
    device_info = {}
    if device.phoneNumber:
        device_info["supi"] = device.phoneNumber.replace("+", "")
    if device.ipv4Address:
        device_info["ipv4"] = device.ipv4Address.publicAddress
        if device.ipv4Address.privateAddress:
            device_info["privateIpv4"] = device.ipv4Address.privateAddress
    if device.ipv6Address:
        device_info["ipv6"] = device.ipv6Address
    
    return device_info

def simulate_location(device_info: dict, max_age: Optional[int], max_surface: Optional[int]) -> dict:
    """
    Simulate location retrieval from network.
    In production, this would call the actual network location service via tf-sdk.
    """
    # Generate realistic location data based on device
    device_hash = hash(json.dumps(device_info, sort_keys=True))
    
    # Use hash to generate consistent but varied locations
    base_lat = 45.754114 + (device_hash % 1000) / 100000
    base_lon = 4.860374 + (device_hash % 1000) / 100000
    
    # Determine area type and size
    if max_surface and max_surface < 100000:
        # Small area requested - use circle
        radius = (max_surface / 3.14159) ** 0.5  # Approximate radius from surface
        radius = max(50.0, min(radius, 500.0))  # Clamp between 50-500m
        
        return {
            "lastLocationTime": datetime.utcnow().isoformat() + "Z",
            "area": {
                "areaType": "CIRCLE",
                "center": {
                    "latitude": round(base_lat, 6),
                    "longitude": round(base_lon, 6)
                },
                "radius": round(radius, 1)
            }
        }
    else:
        # Larger area or no constraint - can use polygon
        if device_hash % 2 == 0:
            # Return circle
            return {
                "lastLocationTime": datetime.utcnow().isoformat() + "Z",
                "area": {
                    "areaType": "CIRCLE",
                    "center": {
                        "latitude": round(base_lat, 6),
                        "longitude": round(base_lon, 6)
                    },
                    "radius": 800.0
                }
            }
        else:
            # Return polygon
            return {
                "lastLocationTime": datetime.utcnow().isoformat() + "Z",
                "area": {
                    "areaType": "POLYGON",
                    "boundary": [
                        {"latitude": round(base_lat, 6), "longitude": round(base_lon, 6)},
                        {"latitude": round(base_lat - 0.000269, 6), "longitude": round(base_lon + 0.002811, 6)},
                        {"latitude": round(base_lat - 0.001624, 6), "longitude": round(base_lon + 0.001502, 6)},
                        {"latitude": round(base_lat - 0.00289, 6), "longitude": round(base_lon + 0.000751, 6)},
                        {"latitude": round(base_lat - 0.002672, 6), "longitude": round(base_lon - 0.000547, 6)}
                    ]
                }
            }

@router.post("/retrieve", response_model=Location, responses={
    400: {"description": "Invalid argument"},
    401: {"description": "Unauthenticated"},
    403: {"description": "Permission denied"},
    404: {"description": "Device not found"},
    422: {"description": "Unprocessable entity"}
})
async def retrieve_location(
    raw_request: Request,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Location Retrieval v0.5.0: Retrieve device location
    POST /location-retrieval/v0/retrieve
    
    Returns the area where the device is currently located, either as:
    - CIRCLE: defined by center coordinates and radius
    - POLYGON: defined by boundary points
    
    The device can be identified by:
    - phoneNumber: E.164 format with + prefix
    - ipv4Address: public/private addresses and optional port
    - ipv6Address: IPv6 address
    - networkAccessIdentifier: NAI format
    
    Returns: 200 OK with location info
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    try:
        # Parse request body
        body = await raw_request.json()
        request_data = RetrievalLocationRequest(**body)
        
        # Validate device identification
        if not request_data.device:
            return camara_error_response(
                422, "MISSING_IDENTIFIER",
                "Device identifier is required", correlator
            )
        
        # Check if at least one device identifier is provided
        device = request_data.device
        if not any([device.phoneNumber, device.ipv4Address, device.ipv6Address, device.networkAccessIdentifier]):
            return camara_error_response(
                422, "DEVICE_UNIDENTIFIABLE",
                "At least one device identifier must be provided", correlator
            )
        
        # Get network client
        client = get_client(core)
        if client is None:
            return camara_error_response(
                503, "SERVICE_UNAVAILABLE",
                f"Core '{core}' not available", correlator
            )
        
        # Build device info for SDK
        sdk_device = None
        if device:
            device_dict = {}
            
            if device.phoneNumber:
                device_dict["phoneNumber"] = device.phoneNumber
            
            if device.ipv4Address:
                ipv4_dict = {
                    "publicAddress": device.ipv4Address.publicAddress,
                }
                # Add privateAddress (required by NEF) - default to publicAddress
                if device.ipv4Address.privateAddress:
                    ipv4_dict["privateAddress"] = device.ipv4Address.privateAddress
                else:
                    ipv4_dict["privateAddress"] = device.ipv4Address.publicAddress
                
                if device.ipv4Address.publicPort:
                    ipv4_dict["publicPort"] = device.ipv4Address.publicPort
                
                device_dict["ipv4Address"] = ipv4_dict
            
            if device.ipv6Address:
                device_dict["ipv6Address"] = device.ipv6Address
            
            if device.networkAccessIdentifier:
                device_dict["networkAccessIdentifier"] = device.networkAccessIdentifier
            
            sdk_device = device_dict
        
        # Create SDK request and call location service
        try:
            from sunrise6g_opensdk.network.core.schemas import RetrievalLocationRequest as SDKLocationRequest
            location_request = SDKLocationRequest(
                device=sdk_device,
                maxAge=request_data.maxAge,
                maxSurface=request_data.maxSurface
            )
            location_response = client.create_monitoring_event_subscription(location_request)
            location_data = location_response.model_dump(mode='json', exclude_none=True) if hasattr(location_response, 'model_dump') else location_response
            
        except Exception as tf_error:
            error_msg = str(tf_error)
            
            # Map network errors to CAMARA error codes
            if ("not connected" in error_msg.lower() or 
                "not found" in error_msg.lower() or 
                "redis: nil" in error_msg.lower() or
                "failed to get ue" in error_msg.lower()):
                return camara_error_response(
                    404, "DEVICE_NOT_FOUND",
                    "Device not registered or no active PDU session", correlator
                )
            else:
                return camara_error_response(
                    500, "INTERNAL",
                    f"Internal error: {error_msg[:100]}", correlator
                )
        
        # Add device identifier to response (echo back what was sent)
        if body.get("device"):
            response_device = DeviceResponse(
                phoneNumber=device.phoneNumber,
                networkAccessIdentifier=device.networkAccessIdentifier,
                ipv4Address=device.ipv4Address,
                ipv6Address=device.ipv6Address
            )
            location_data["device"] = response_device.model_dump(exclude_none=True)
        
        return JSONResponse(
            status_code=200,
            content=location_data,
            headers={"x-correlator": correlator}
        )
        
    except ValidationError as e:
        return camara_error_response(400, "INVALID_ARGUMENT", str(e), correlator)
    except Exception as e:
        return camara_error_response(500, "INTERNAL", "Internal server error", correlator)

# Health check endpoint
@router.get("/health")
async def health_check(response: Response):
    """Health check for location retrieval service"""
    response.headers["x-correlator"] = str(uuid.uuid4())
    return {
        "status": "healthy",
        "service": "CAMARA Location Retrieval API",
        "version": "v0.5.0"
    }
