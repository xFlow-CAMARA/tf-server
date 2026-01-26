"""
CAMARA SIM Swap API Models

Compliant with CAMARA SIM Swap specification.
https://github.com/camaraproject/SimSwap

The SIM Swap API provides:
- Check if SIM swap occurred during a past period
- Retrieve timestamp of latest SIM swap
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


# ====================== Request Models ======================

class CreateCheckSimSwap(BaseModel):
    """
    Request body for checking if SIM swap occurred.
    
    phoneNumber is required for 2-legged auth flows.
    For 3-legged flows, phone number is derived from access token.
    """
    model_config = ConfigDict(extra='forbid')
    
    phoneNumber: Optional[str] = Field(
        None,
        pattern=r'^\+[1-9][0-9]{4,14}$',
        description="Phone number in E.164 format (e.g., +346661113334)",
        examples=["+346661113334"]
    )
    maxAge: Optional[int] = Field(
        240,
        ge=1,
        le=2400,
        description="Period in hours to be checked for SIM swap (1-2400, default 240)",
        examples=[240]
    )


class CreateSimSwapDate(BaseModel):
    """
    Request body for retrieving SIM swap date.
    
    phoneNumber is required for 2-legged auth flows.
    For 3-legged flows, phone number is derived from access token.
    """
    model_config = ConfigDict(extra='forbid')
    
    phoneNumber: Optional[str] = Field(
        None,
        pattern=r'^\+[1-9][0-9]{4,14}$',
        description="Phone number in E.164 format (e.g., +346661113334)",
        examples=["+346661113334"]
    )


# ====================== Response Models ======================

class CheckSimSwapInfo(BaseModel):
    """
    Response for SIM swap check.
    
    Indicates whether a SIM swap occurred during the requested period.
    """
    model_config = ConfigDict(extra='forbid')
    
    swapped: bool = Field(
        ...,
        description="Indicates whether the SIM card has been swapped during the period within the provided maxAge"
    )


class SimSwapInfo(BaseModel):
    """
    Response for SIM swap date retrieval.
    
    Contains timestamp of latest SIM swap or null if:
    - No swap occurred within monitored period
    - Data retention policies prevent sharing the date
    """
    model_config = ConfigDict(extra='forbid')
    
    latestSimChange: Optional[datetime] = Field(
        ...,
        description="Timestamp of latest SIM swap performed. Null if no swap occurred or data not available due to retention policies.",
        examples=["2024-09-18T07:37:53.471Z"]
    )
    monitoredPeriod: Optional[int] = Field(
        None,
        description="Timeframe in days for SIM card change supervision. Provided when latestSimChange is null to indicate monitored period.",
        examples=[120]
    )


# ====================== Error Models ======================

class ErrorInfo(BaseModel):
    """CAMARA-compliant error response"""
    model_config = ConfigDict(extra='forbid')
    
    status: int = Field(..., description="HTTP response status code")
    code: str = Field(..., description="A human-readable code to describe the error")
    message: str = Field(..., description="A human-readable description of what the event represents")
