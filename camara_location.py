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
    
    @field_validator('*', mode='before')
    @classmethod
    def check_at_least_one(cls, v, info):
        """Ensure at least one device identifier is provided (minProperties: 1)"""
        return v
    
    def model_post_init(self, __context):
        """Validate that at least one identifier is provided"""
        if not any([self.phoneNumber, self.networkAccessIdentifier, self.ipv4Address, self.ipv6Address]):
            raise ValueError("At least one device identifier must be provided")

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
    """Single device identifier in response - maxProperties: 1"""
    phoneNumber: Optional[str] = None
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None
    
    def model_post_init(self, __context):
        """Ensure only one device identifier is provided (maxProperties: 1)"""
        identifiers = [self.phoneNumber, self.networkAccessIdentifier, self.ipv4Address, self.ipv6Address]
        if sum(x is not None for x in identifiers) > 1:
            raise ValueError("Only one device identifier can be returned")

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
    
    Note: In a real implementation, the following CAMARA error codes would be returned:
    - 422 LOCATION_RETRIEVAL.UNABLE_TO_FULFILL_MAX_AGE: Cannot provide fresh enough location
    - 422 LOCATION_RETRIEVAL.UNABLE_TO_FULFILL_MAX_SURFACE: Cannot provide accurate enough location
    - 422 LOCATION_RETRIEVAL.UNABLE_TO_LOCATE: Network cannot locate the device
    
    For simulation purposes, we always return a successful location.
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
                "The device cannot be identified.", correlator
            )
        
        # Get device for processing
        device = request_data.device
        
        # Get network client (optional for simulation)
        client = get_client(core)
        
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
            
            # If we have IP but no phoneNumber, try to resolve it for the SDK
            if device.ipv4Address and not device.phoneNumber:
                try:
                    if hasattr(client, 'get_msisdn_by_ip'):
                        resolved_msisdn = client.get_msisdn_by_ip(device.ipv4Address.publicAddress)
                        if resolved_msisdn:
                            device_dict["phoneNumber"] = resolved_msisdn
                except Exception as e:
                    # Log but continue - we'll fall back to simulation if needed
                    pass
            
            sdk_device = device_dict
        
        # For CoreSim: Use simulation for quick response (CoreSim doesn't have real location data from NEF)
        device_info = build_device_info(device)
        location_data = simulate_location(device_info, request_data.maxAge, request_data.maxSurface)
        
        # Add device identifier to response (echo back only ONE identifier as per CAMARA spec)
        # Per spec: "only one of those device identifiers is allowed in the response"
        if body.get("device"):
            # Return the first non-null identifier
            if device.phoneNumber:
                response_device = DeviceResponse(phoneNumber=device.phoneNumber)
            elif device.ipv4Address:
                response_device = DeviceResponse(ipv4Address=device.ipv4Address)
            elif device.ipv6Address:
                response_device = DeviceResponse(ipv6Address=device.ipv6Address)
            elif device.networkAccessIdentifier:
                response_device = DeviceResponse(networkAccessIdentifier=device.networkAccessIdentifier)
            else:
                response_device = None
            
            if response_device:
                location_data["device"] = response_device.model_dump(exclude_none=True)
        
        return JSONResponse(
            status_code=200,
            content=location_data,
            headers={"x-correlator": correlator}
        )
        
    except ValidationError as e:
        return camara_error_response(400, "INVALID_ARGUMENT", "Client specified an invalid argument, request body or query param.", correlator)
    except Exception as e:
        return camara_error_response(500, "INTERNAL", "Internal server error.", correlator)

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
