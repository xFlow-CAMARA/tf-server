"""
CAMARA Device Location Retrieval API Models

Compliant with CAMARA Location Retrieval v0.4.0/v0.5.0 specification.
https://github.com/camaraproject/DeviceLocation
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal, Union, Annotated

from camara_models.common import Device, DeviceIpv4Addr


# ====================== Geographic Models ======================

class Point(BaseModel):
    """
    Geographic coordinate point (WGS84).
    """
    model_config = ConfigDict(extra='forbid')
    
    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude in decimal degrees (-90 to 90)"
    )
    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude in decimal degrees (-180 to 180)"
    )


class Circle(BaseModel):
    """
    Circular geographic area definition.
    Center point with radius in meters.
    """
    model_config = ConfigDict(extra='forbid')
    
    areaType: Literal["CIRCLE"] = Field(
        "CIRCLE",
        description="Area type discriminator"
    )
    center: Point = Field(
        ...,
        description="Center point of the circle"
    )
    radius: float = Field(
        ...,
        ge=1,
        description="Radius in meters"
    )


class Polygon(BaseModel):
    """
    Polygonal geographic area definition.
    List of boundary points forming a closed polygon.
    """
    model_config = ConfigDict(extra='forbid')
    
    areaType: Literal["POLYGON"] = Field(
        "POLYGON",
        description="Area type discriminator"
    )
    boundary: List[Point] = Field(
        ...,
        min_length=3,
        max_length=15,
        description="List of boundary points (3-15 points)"
    )


# Union type for area (discriminated by areaType)
Area = Annotated[Union[Circle, Polygon], Field(discriminator="areaType")]


# ====================== Location Request Models ======================

class RetrievalLocationRequest(BaseModel):
    """
    Request body for location retrieval.
    POST /location-retrieval/v0/retrieve
    """
    model_config = ConfigDict(extra='forbid')
    
    device: Optional[Device] = Field(
        None,
        description="Device identifier. Required unless using 3-legged auth."
    )
    maxAge: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum age of location in seconds. 0 means fresh location required."
    )
    maxSurface: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum surface area in square meters for location accuracy"
    )


# ====================== Location Response Models ======================

class DeviceLocationResponse(BaseModel):
    """
    Device identifier in location response.
    """
    model_config = ConfigDict(extra='forbid')
    
    phoneNumber: Optional[str] = None
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None


class Location(BaseModel):
    """
    Location retrieval response.
    Contains the device's location as a geographic area.
    """
    model_config = ConfigDict(extra='forbid')
    
    lastLocationTime: str = Field(
        ...,
        description="Timestamp of the location in ISO 8601 format with timezone"
    )
    area: Area = Field(
        ...,
        description="Geographic area (Circle or Polygon)"
    )
    device: Optional[DeviceLocationResponse] = Field(
        None,
        description="Device identifier (included when applicable)"
    )


# ====================== Location Verification Models ======================

class VerifyLocationRequest(BaseModel):
    """
    Request body for location verification.
    POST /location-verification/v0/verify
    """
    model_config = ConfigDict(extra='forbid')
    
    device: Optional[Device] = Field(
        None,
        description="Device identifier"
    )
    area: Area = Field(
        ...,
        description="Area to verify device location against"
    )
    maxAge: Optional[int] = Field(
        None,
        ge=0,
        description="Maximum age of location in seconds"
    )


class VerifyLocationResponse(BaseModel):
    """
    Location verification response.
    """
    model_config = ConfigDict(extra='forbid')
    
    verificationResult: Literal["TRUE", "FALSE", "UNKNOWN", "PARTIAL"] = Field(
        ...,
        description="Result of location verification"
    )
    lastLocationTime: Optional[str] = Field(
        None,
        description="Timestamp of the location used for verification"
    )
    matchRate: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Percentage of area overlap (for PARTIAL result)"
    )
