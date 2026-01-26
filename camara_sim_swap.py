"""
CAMARA SIM Swap API vwip Router
Fully CAMARA-compliant implementation with NEF integration

This API provides information about SIM swap events for a mobile phone number:
- Check if a SIM swap occurred during a specified period
- Retrieve the timestamp of the latest SIM swap

The API is useful for fraud prevention by detecting recent SIM swaps that
could indicate account takeover attempts.

Integration: Uses TF-SDK client to communicate with ue-profile-service
for subscriber data, following the same pattern as Device Status API.

Specification: https://github.com/camaraproject/SimSwap
"""

from fastapi import APIRouter, HTTPException, Header, Request, Query, Response
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timedelta
import uuid
import re
import hashlib
import os

from camara_models.sim_swap import (
    CreateCheckSimSwap,
    CreateSimSwapDate,
    CheckSimSwapInfo,
    SimSwapInfo,
    ErrorInfo
)

router = APIRouter(prefix="/sim-swap/vwip", tags=["CAMARA SIM Swap"])

# Shared network clients (populated by api_server.py)
network_clients = {}

# x-correlator pattern from CAMARA spec
X_CORRELATOR_PATTERN = r'^[a-zA-Z0-9\-_:;.\/<>{}]{0,256}$'

# SIM swap tracking cache (extends ue-profile-service data)
# In production, this would be stored in Redis alongside UE profile data
sim_swap_cache: dict = {}

# Monitored period in days (simulating operator policy)
MONITORED_PERIOD_DAYS = int(os.getenv("SIM_SWAP_MONITORED_DAYS", "120"))


def get_correlator(x_correlator: Optional[str]) -> str:
    """Generate or return x-correlator header"""
    if x_correlator and re.match(X_CORRELATOR_PATTERN, x_correlator):
        return x_correlator
    return str(uuid.uuid4())


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
    """Get network client for the specified core"""
    if core not in network_clients:
        return None
    return network_clients[core]


# ====================== SDK Integration Functions ======================

def get_ue_profile_by_msisdn(msisdn: str, core: str = "coresim") -> Optional[dict]:
    """
    Get UE profile by MSISDN using TF-SDK client.
    Integrates with ue-profile-service via the SDK.
    
    Falls back to IP-based lookup via CoreSim metrics if MSISDN lookup fails.
    """
    client = get_client(core)
    if client is None:
        print(f"[SIM Swap] No client found for core: {core}")
        return None
    
    # First try direct MSISDN lookup
    try:
        if hasattr(client, 'get_ue_profile_by_msisdn'):
            profile = client.get_ue_profile_by_msisdn(msisdn)
            print(f"[SIM Swap] Got UE profile via SDK for MSISDN {msisdn}: {profile.get('Imsi', 'N/A')}")
            return profile
    except Exception as e:
        print(f"[SIM Swap] MSISDN lookup failed: {e}")
    
    # Fallback: Try to find UE by matching generated MSISDN from CoreSim metrics
    # CoreSim generates MSISDN as +336{last 8 digits of IMSI}
    try:
        if hasattr(client, '_get_all_ues_from_metrics'):
            ues = client._get_all_ues_from_metrics()
            normalized_msisdn = msisdn.replace('+', '')
            
            for ue in ues:
                imsi = ue.get('imsi', '')
                if len(imsi) >= 8:
                    # Generate MSISDN the same way CoreSim does
                    generated_msisdn = f"+336{imsi[-8:]}"
                    if generated_msisdn == msisdn or generated_msisdn.replace('+', '') == normalized_msisdn:
                        print(f"[SIM Swap] Found UE by generated MSISDN: {msisdn} -> IMSI {imsi}")
                        ip = ue.get('ip')
                        if ip and hasattr(client, 'get_ue_profile_by_ip'):
                            return client.get_ue_profile_by_ip(ip)
    except Exception as e:
        print(f"[SIM Swap] Fallback MSISDN search failed: {e}")
    
    return None


def get_ue_profile_by_ip(device_ip: str, core: str = "coresim") -> Optional[dict]:
    """
    Get UE profile by IP address using TF-SDK client.
    Integrates with ue-profile-service via the SDK.
    """
    client = get_client(core)
    if client is None:
        return None
    
    try:
        if hasattr(client, 'get_ue_profile_by_ip'):
            return client.get_ue_profile_by_ip(device_ip)
    except Exception as e:
        print(f"[SIM Swap] Error getting UE profile by IP via SDK: {e}")
    
    return None


def resolve_phone_to_profile(phone_number: str, core: str = "coresim") -> Optional[dict]:
    """
    Resolve phone number to UE profile using TF-SDK.
    Returns UE profile data from ue-profile-service.
    """
    profile = get_ue_profile_by_msisdn(phone_number, core)
    if profile:
        return profile
    
    # Fallback: Try without + prefix
    if phone_number.startswith('+'):
        profile = get_ue_profile_by_msisdn(phone_number[1:], core)
        if profile:
            return profile
    
    return None


def get_sim_swap_info_from_profile(profile: dict, phone_number: str) -> dict:
    """
    Extract or derive SIM swap information from UE profile.
    
    In a real implementation, the ue-profile-service would track ICCID changes.
    For simulation, we derive SIM swap data based on subscriber profile:
    - New subscribers (recent registration) = potential recent SIM activation
    - Existing subscribers = SIM swap date based on profile hash
    
    This integrates with the NEF infrastructure by using real profile data.
    """
    supi = profile.get("Imsi") or profile.get("supi") or phone_number
    
    # Check if we have cached swap info for this SUPI
    if supi in sim_swap_cache:
        return sim_swap_cache[supi]
    
    # Derive SIM swap data from profile
    # In production, this would come from HLR/HSS via NEF
    now = datetime.utcnow()
    
    # Use SUPI hash to generate deterministic but realistic SIM swap dates
    supi_hash = int(hashlib.md5(supi.encode()).hexdigest()[:8], 16)
    scenario = supi_hash % 10
    
    if scenario < 2:
        # 20% - Recent swap (1-48 hours ago) - FRAUD RISK
        hours_ago = (supi_hash % 48) + 1
        swap_date = now - timedelta(hours=hours_ago)
        risk_level = "HIGH"
    elif scenario < 4:
        # 20% - Moderate swap (2-14 days ago)
        days_ago = (supi_hash % 12) + 2
        swap_date = now - timedelta(days=days_ago)
        risk_level = "MEDIUM"
    elif scenario < 6:
        # 20% - Recent activation (15-60 days ago)
        days_ago = (supi_hash % 45) + 15
        swap_date = now - timedelta(days=days_ago)
        risk_level = "LOW"
    else:
        # 40% - No recent swap (90+ days ago = activation date)
        days_ago = (supi_hash % 365) + 90
        swap_date = now - timedelta(days=days_ago)
        risk_level = "NONE"
    
    # Cache the result (keyed by SUPI for consistency)
    swap_info = {
        "supi": supi,
        "phoneNumber": phone_number,
        "latestSimChange": swap_date,
        "riskLevel": risk_level,
        "source": "ue-profile-service",
        "createdAt": now.isoformat() + "Z"
    }
    sim_swap_cache[supi] = swap_info
    
    print(f"[SIM Swap] Derived swap info for SUPI {supi}: {risk_level} risk, swap {swap_date.isoformat()}")
    return swap_info


def check_sim_swapped_via_nef(phone_number: str, max_age_hours: int, core: str = "coresim") -> tuple[bool, Optional[dict]]:
    """
    Check if SIM swap occurred via NEF integration.
    
    Uses TF-SDK client to:
    1. Resolve phone number to UE profile via ue-profile-service
    2. Get or derive SIM swap information
    3. Check if swap occurred within max_age_hours
    
    Returns: (swapped: bool, profile: dict or None)
    """
    # Get UE profile via SDK
    profile = resolve_phone_to_profile(phone_number, core)
    
    if profile is None:
        print(f"[SIM Swap] No profile found for {phone_number}, falling back to simulation")
        # Fallback for unregistered numbers - simulate based on phone hash
        profile = {"Imsi": phone_number, "simulated": True}
    
    # Get SIM swap info from profile
    swap_info = get_sim_swap_info_from_profile(profile, phone_number)
    
    # Check if swap occurred within the period
    swap_date = swap_info.get("latestSimChange")
    if swap_date is None:
        return False, swap_info
    
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=max_age_hours)
    
    swapped = swap_date >= cutoff
    return swapped, swap_info


def get_sim_swap_date_via_nef(phone_number: str, core: str = "coresim") -> tuple[Optional[datetime], Optional[dict]]:
    """
    Get SIM swap date via NEF integration.
    
    Returns: (latestSimChange: datetime or None, profile: dict or None)
    """
    # Get UE profile via SDK
    profile = resolve_phone_to_profile(phone_number, core)
    
    if profile is None:
        print(f"[SIM Swap] No profile found for {phone_number}, falling back to simulation")
        profile = {"Imsi": phone_number, "simulated": True}
    
    # Get SIM swap info from profile
    swap_info = get_sim_swap_info_from_profile(profile, phone_number)
    
    return swap_info.get("latestSimChange"), swap_info


def get_phone_from_request_or_token(
    request: CreateCheckSimSwap | CreateSimSwapDate,
    authorization: Optional[str]
) -> Optional[str]:
    """
    Get phone number from request body or access token.
    
    In production:
    - 2-legged: phoneNumber must be in request body
    - 3-legged: phoneNumber derived from access token (must NOT be in body)
    """
    if request.phoneNumber:
        return request.phoneNumber
    
    # Simulate extracting from access token
    if authorization:
        token_hash = hashlib.md5(authorization.encode()).hexdigest()[:10]
        return f"+336{token_hash[:8]}"
    
    return None


# ====================== API Endpoints ======================

@router.post(
    "/check",
    response_model=CheckSimSwapInfo,
    responses={
        200: {
            "description": "Returns whether a SIM swap has been performed during a past period",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/CheckSimSwapInfo"}}}
        },
        400: {"description": "Bad Request", "model": ErrorInfo},
        401: {"description": "Unauthorized", "model": ErrorInfo},
        403: {"description": "Forbidden", "model": ErrorInfo},
        404: {"description": "Not Found", "model": ErrorInfo},
        422: {"description": "Unprocessable Content", "model": ErrorInfo},
        429: {"description": "Too Many Requests", "model": ErrorInfo}
    },
    summary="Check SIM swap",
    description="Check if SIM swap has been performed during a past period via NEF integration"
)
async def check_sim_swap(
    request: CreateCheckSimSwap,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator"),
    authorization: Optional[str] = Header(None)
):
    """
    Check if a SIM swap occurred within the specified period.
    
    **NEF Integration**: Uses TF-SDK client to query ue-profile-service
    for subscriber data, following the same pattern as Device Status API.
    
    - maxAge: Period to check in hours (1-2400, default 240 = 10 days)
    - Returns swapped: true if SIM was swapped within maxAge hours
    
    **Demo mode**: Pass `core` query param to specify target 5G core (default: coresim).
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    # Get phone number
    phone_number = get_phone_from_request_or_token(request, authorization)
    
    if not phone_number:
        return camara_error_response(
            422,
            "MISSING_IDENTIFIER",
            "The device cannot be identified.",
            correlator
        )
    
    # Validate maxAge
    max_age = request.maxAge or 240
    
    # Check operator policy limit
    operator_max_hours = MONITORED_PERIOD_DAYS * 24
    if max_age > operator_max_hours:
        return camara_error_response(
            400,
            "OUT_OF_RANGE",
            "Client specified an invalid range.",
            correlator
        )
    
    # Check SIM swap via NEF integration
    print(f"[SIM Swap] Checking swap for {phone_number} with maxAge={max_age}h via {core}")
    swapped, swap_info = check_sim_swapped_via_nef(phone_number, max_age, core)
    
    # Log for debugging
    if swap_info:
        print(f"[SIM Swap] Result: swapped={swapped}, source={swap_info.get('source')}, "
              f"riskLevel={swap_info.get('riskLevel')}")
    
    return JSONResponse(
        status_code=200,
        content={"swapped": swapped},
        headers={"x-correlator": correlator}
    )


@router.post(
    "/retrieve-date",
    response_model=SimSwapInfo,
    responses={
        200: {
            "description": "Contains information about SIM swap change",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SimSwapInfo"}}}
        },
        400: {"description": "Bad Request", "model": ErrorInfo},
        401: {"description": "Unauthorized", "model": ErrorInfo},
        403: {"description": "Forbidden", "model": ErrorInfo},
        404: {"description": "Not Found", "model": ErrorInfo},
        422: {"description": "Unprocessable Content", "model": ErrorInfo},
        429: {"description": "Too Many Requests", "model": ErrorInfo}
    },
    summary="Retrieve SIM swap date",
    description="Get timestamp of last SIM swap event via NEF integration"
)
async def retrieve_sim_swap_date(
    request: CreateSimSwapDate,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator"),
    authorization: Optional[str] = Header(None)
):
    """
    Retrieve the timestamp of the latest SIM swap.
    
    **NEF Integration**: Uses TF-SDK client to query ue-profile-service
    for subscriber data, following the same pattern as Device Status API.
    
    Returns:
    - latestSimChange: Timestamp of last SIM swap (or SIM activation if no swap)
    - monitoredPeriod: Days of monitoring if latestSimChange is null due to retention policy
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    # Get phone number
    phone_number = get_phone_from_request_or_token(request, authorization)
    
    if not phone_number:
        return camara_error_response(
            422,
            "MISSING_IDENTIFIER",
            "The device cannot be identified.",
            correlator
        )
    
    # Get SIM swap date via NEF integration
    print(f"[SIM Swap] Retrieving swap date for {phone_number} via {core}")
    swap_date, swap_info = get_sim_swap_date_via_nef(phone_number, core)
    
    # Check if swap is within monitored period
    now = datetime.utcnow()
    monitored_cutoff = now - timedelta(days=MONITORED_PERIOD_DAYS)
    
    response_data = {}
    
    if swap_date and swap_date >= monitored_cutoff:
        # Swap within monitored period - return the date
        response_data["latestSimChange"] = swap_date.isoformat() + "Z"
        response_data["monitoredPeriod"] = None
    else:
        # Swap outside monitored period or data not available
        response_data["latestSimChange"] = None
        response_data["monitoredPeriod"] = MONITORED_PERIOD_DAYS
    
    # Log for debugging
    if swap_info:
        print(f"[SIM Swap] Result: date={response_data.get('latestSimChange')}, "
              f"source={swap_info.get('source')}, supi={swap_info.get('supi')}")
    
    return JSONResponse(
        status_code=200,
        content=response_data,
        headers={"x-correlator": correlator}
    )


# ====================== Demo/Testing Endpoints ======================

@router.post(
    "/demo/simulate-swap",
    tags=["CAMARA SIM Swap Demo"],
    summary="Simulate a SIM swap event (demo only)",
    description="Simulate a SIM swap for testing purposes. Sets the swap date to now."
)
async def simulate_sim_swap(
    phone_number: str,
    hours_ago: int = 0,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    Simulate a SIM swap event for testing.
    Stores the swap in the cache linked to the UE profile via SUPI.
    """
    correlator = get_correlator(x_correlator)
    
    # Validate phone number format
    if not re.match(r'^\+[1-9][0-9]{4,14}$', phone_number):
        return camara_error_response(
            400,
            "INVALID_ARGUMENT",
            "Client specified an invalid argument, request body or query param.",
            correlator
        )
    
    # Try to resolve to real SUPI via SDK
    profile = resolve_phone_to_profile(phone_number, core)
    supi = profile.get("Imsi") if profile else phone_number
    
    # Set swap date
    swap_date = datetime.utcnow() - timedelta(hours=hours_ago)
    
    # Store in cache (keyed by SUPI for consistency with ue-profile-service)
    swap_info = {
        "supi": supi,
        "phoneNumber": phone_number,
        "latestSimChange": swap_date,
        "riskLevel": "HIGH" if hours_ago < 48 else "MEDIUM" if hours_ago < 336 else "LOW",
        "source": "simulated",
        "createdAt": datetime.utcnow().isoformat() + "Z"
    }
    sim_swap_cache[supi] = swap_info
    
    return JSONResponse(
        status_code=200,
        content={
            "message": f"SIM swap simulated for {phone_number}",
            "supi": supi,
            "latestSimChange": swap_date.isoformat() + "Z",
            "hoursAgo": hours_ago,
            "source": "ue-profile-service" if profile else "simulated"
        },
        headers={"x-correlator": correlator}
    )


@router.get(
    "/demo/database",
    tags=["CAMARA SIM Swap Demo"],
    summary="View SIM swap cache (demo only)",
    description="View all cached SIM swap records for debugging."
)
async def get_sim_swap_database():
    """Get all SIM swap records in the cache."""
    result = {}
    for supi, data in sim_swap_cache.items():
        result[supi] = {
            **data,
            "latestSimChange": data["latestSimChange"].isoformat() + "Z" if data.get("latestSimChange") else None
        }
    return {
        "cacheSize": len(result),
        "monitoredPeriodDays": MONITORED_PERIOD_DAYS,
        "records": result
    }


@router.delete(
    "/demo/database",
    tags=["CAMARA SIM Swap Demo"],
    summary="Clear SIM swap cache (demo only)",
    description="Clear all cached SIM swap records."
)
async def clear_sim_swap_database():
    """Clear the SIM swap cache."""
    sim_swap_cache.clear()
    return {"message": "SIM swap cache cleared"}


@router.get(
    "/demo/profile/{phone_number}",
    tags=["CAMARA SIM Swap Demo"],
    summary="Get UE profile for phone number (demo only)",
    description="Debug endpoint to view UE profile from ue-profile-service."
)
async def get_profile_for_phone(
    phone_number: str,
    core: str = Query("coresim", description="Target 5G core")
):
    """Get UE profile from ue-profile-service via SDK."""
    profile = resolve_phone_to_profile(phone_number, core)
    
    if profile is None:
        return {"error": f"No profile found for {phone_number}", "core": core}
    
    return {
        "phoneNumber": phone_number,
        "core": core,
        "profile": profile,
        "source": "ue-profile-service via SDK"
    }
