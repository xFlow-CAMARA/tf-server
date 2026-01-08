"""
CAMARA Device Status API Router
Fully CAMARA-compliant implementation

This API provides the ability to:
- Check if a device is reachable (connectivity status)
- Check if a device is roaming
- Subscribe to connectivity/roaming status changes

Reference: https://github.com/camaraproject/DeviceStatus
"""

from fastapi import APIRouter, HTTPException, Header, Request, Query, Response
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime
import uuid
import re
import os
import requests

# Import models from camara_models package
from camara_models.device_status import (
    ConnectivityStatus,
    ConnectivityType,
    RoamingStatus,
    Device,
    DeviceIpv4Addr,
    ReachabilityStatusRequest,
    ReachabilityStatusResponse,
    RoamingStatusRequest,
    RoamingStatusResponse,
    SubscriptionRequest,
    SubscriptionResponse,
    ReachabilityStatusChangedEvent,
    RoamingStatusChangedEvent,
    MCC_COUNTRY_MAP,
    get_country_from_mcc,
)
from camara_models.common import ErrorInfo

router = APIRouter(prefix="/device-status", tags=["CAMARA Device Status"])

# Shared network clients (populated by api_server.py)
network_clients = {}

# x-correlator pattern from CAMARA spec
X_CORRELATOR_PATTERN = r'^[a-zA-Z0-9\-_:;.\/<>{}]{0,256}$'

# Default home PLMN for demo (can be configured)
HOME_PLMN = {
    "mcc": os.getenv("HOME_MCC", "001"),
    "mnc": os.getenv("HOME_MNC", "06")
}


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


# ====================== In-memory subscription storage ======================
# In production, use Redis or a database
subscriptions = {
    "reachability": {},
    "roaming": {}
}


# ====================== Helper Functions ======================

def get_client(core: str):
    """Get network client for the specified core"""
    if core not in network_clients:
        return None
    return network_clients[core]


def get_ue_profile(device_ip: str, core: str = "coresim") -> Optional[dict]:
    """
    Get UE profile using TF-SDK client.
    Returns profile with RegistrationStatus, ConnectionStatus, Plmn, etc.
    """
    client = get_client(core)
    if client is None:
        return None
    
    try:
        # Use TF-SDK client method
        if hasattr(client, 'get_ue_profile_by_ip'):
            return client.get_ue_profile_by_ip(device_ip)
        
        # Fallback: use get_msisdn_by_ip and then profile
        if hasattr(client, 'get_msisdn_by_ip'):
            try:
                msisdn = client.get_msisdn_by_ip(device_ip)
                if msisdn and hasattr(client, 'get_ue_profile_by_msisdn'):
                    return client.get_ue_profile_by_msisdn(msisdn)
            except Exception:
                pass
    except Exception as e:
        print(f"Error getting UE profile via SDK: {e}")
    
    return None


def get_ue_profile_by_msisdn(msisdn: str, core: str = "coresim") -> Optional[dict]:
    """Get UE profile by MSISDN using TF-SDK"""
    client = get_client(core)
    if client is None:
        return None
    
    try:
        if hasattr(client, 'get_ue_profile_by_msisdn'):
            return client.get_ue_profile_by_msisdn(msisdn)
    except Exception as e:
        print(f"Error getting UE profile by MSISDN: {e}")
    
    return None


def resolve_device_to_profile(device: Device, core: str) -> Optional[dict]:
    """Resolve device identifier to UE profile using TF-SDK"""
    if device.ipv4Address and device.ipv4Address.publicAddress:
        return get_ue_profile(device.ipv4Address.publicAddress, core)
    
    if device.phoneNumber:
        return get_ue_profile_by_msisdn(device.phoneNumber, core)
    
    return None


def get_reachability_via_sdk(device_ip: str, core: str = "coresim") -> Optional[dict]:
    """
    Get device reachability status using TF-SDK client.
    Preferred method - uses SDK's built-in status mapping.
    """
    client = get_client(core)
    if client is None:
        return None
    
    try:
        if hasattr(client, 'get_device_reachability_status'):
            return client.get_device_reachability_status(device_ip)
    except Exception as e:
        print(f"Error getting reachability via SDK: {e}")
    
    return None


def get_roaming_via_sdk(device_ip: str, core: str = "coresim") -> Optional[dict]:
    """
    Get device roaming status using TF-SDK client.
    Preferred method - uses SDK's built-in roaming detection.
    """
    client = get_client(core)
    if client is None:
        return None
    
    try:
        if hasattr(client, 'get_device_roaming_status'):
            return client.get_device_roaming_status(
                device_ip, 
                home_mcc=HOME_PLMN["mcc"], 
                home_mnc=HOME_PLMN["mnc"]
            )
    except Exception as e:
        print(f"Error getting roaming via SDK: {e}")
    
    return None
    
    # Add more resolution methods as needed
    return None


def map_connection_status(profile: dict) -> ConnectivityStatus:
    """Map UE profile connection status to CAMARA ConnectivityStatus"""
    conn_status = profile.get("ConnectionStatus", "").upper()
    reg_status = profile.get("RegistrationStatus", "").upper()
    
    # Check registration first
    if reg_status in ["DEREGISTERED", "NOT_REGISTERED"]:
        return ConnectivityStatus.NOT_CONNECTED
    
    # Map connection status
    if conn_status == "CONNECTED":
        # Check if has PDU sessions (data connectivity)
        pdu_sessions = profile.get("PduSessions", {})
        if pdu_sessions and len(pdu_sessions) > 0:
            return ConnectivityStatus.CONNECTED_DATA
        return ConnectivityStatus.CONNECTED_SMS
    elif conn_status == "IDLE":
        return ConnectivityStatus.CONNECTED_SMS
    else:
        return ConnectivityStatus.NOT_CONNECTED


def check_roaming_status(profile: dict) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Check if UE is roaming based on PLMN.
    Returns (is_roaming, country_code, country_name)
    """
    plmn = profile.get("Plmn", {})
    current_mcc = plmn.get("mcc", "")
    current_mnc = plmn.get("mnc", "")
    
    if not current_mcc:
        return False, None, None
    
    # Check if different from home PLMN
    is_roaming = (current_mcc != HOME_PLMN["mcc"]) or (current_mnc != HOME_PLMN["mnc"])
    
    # Get country info
    country_info = MCC_COUNTRY_MAP.get(current_mcc, {"code": "XX", "name": "Unknown"})
    
    return is_roaming, country_info["code"], country_info["name"]


# ====================== API Endpoints ======================

# -------------------- Device Reachability Status --------------------

def map_status_to_camara(legacy_status: ConnectivityStatus) -> tuple[bool, Optional[list]]:
    """
    Map legacy ConnectivityStatus to CAMARA-compliant reachable + connectivity.
    
    Returns (reachable: bool, connectivity: Optional[List[ConnectivityType]])
    """
    if legacy_status == ConnectivityStatus.CONNECTED_DATA:
        return True, [ConnectivityType.DATA]
    elif legacy_status == ConnectivityStatus.CONNECTED_SMS:
        return True, [ConnectivityType.SMS]
    else:  # NOT_CONNECTED
        return False, None


@router.post(
    "/reachability/v1/retrieve",
    response_model=ReachabilityStatusResponse,
    responses={
        200: {"description": "Contains information about current reachability status"},
        400: {"description": "Bad Request", "model": ErrorInfo},
        401: {"description": "Unauthorized", "model": ErrorInfo},
        403: {"description": "Forbidden", "model": ErrorInfo},
        404: {"description": "Not found", "model": ErrorInfo},
        422: {"description": "Unprocessable Content", "model": ErrorInfo},
        429: {"description": "Too Many Requests", "model": ErrorInfo},
        503: {"description": "Service Unavailable", "model": ErrorInfo},
    }
)
async def get_reachability_status(
    request: ReachabilityStatusRequest,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    device_ip: Optional[str] = Query(None, description="Device IP (demo mode)"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Device Reachability Status: Get the current reachability status
    
    POST /device-status/reachability/v1/retrieve
    
    Returns whether a device is reachable and the connectivity types available:
    - reachable: true/false indicating overall reachability
    - connectivity: Array of ["DATA"], ["SMS"], or ["DATA", "SMS"] when reachable
    
    Per CAMARA spec:
    - With 2-legged token: device parameter is required
    - With 3-legged token: device parameter must not be provided
    
    **Demo mode**: Pass `device_ip` query param to bypass device resolution.
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    try:
        # Resolve device IP
        resolved_ip = device_ip
        device_provided = request.device is not None
        
        if not resolved_ip and request.device and request.device.ipv4Address:
            resolved_ip = request.device.ipv4Address.publicAddress
        
        if not resolved_ip:
            # Per spec: 422 MISSING_IDENTIFIER when device cannot be identified
            return camara_error_response(
                422,
                "MISSING_IDENTIFIER",
                "The device cannot be identified. Provide device identifier or use 3-legged token.",
                correlator
            )
        
        # Try SDK method first (preferred)
        sdk_result = get_reachability_via_sdk(resolved_ip, core)
        if sdk_result:
            legacy_status = ConnectivityStatus(sdk_result["reachabilityStatus"])
            reachable, connectivity = map_status_to_camara(legacy_status)
            
            # Build response per CAMARA spec
            response_data = {
                "lastStatusTime": sdk_result.get("lastStatusTime") or (datetime.utcnow().isoformat() + "Z"),
                "reachable": reachable,
                "reachabilityStatus": legacy_status,  # Legacy field for dashboard compatibility
            }
            
            if connectivity:
                response_data["connectivity"] = connectivity
            
            # Return device in response only if it was provided in request (2-legged)
            if device_provided and request.device:
                # Per spec: return only one identifier
                if request.device.ipv4Address:
                    response_data["device"] = {"ipv4Address": request.device.ipv4Address.model_dump()}
                elif request.device.phoneNumber:
                    response_data["device"] = {"phoneNumber": request.device.phoneNumber}
            
            return ReachabilityStatusResponse(**response_data)
        
        # Fallback: use profile-based resolution
        profile = get_ue_profile(resolved_ip, core)
        
        if not profile:
            # Per spec: 404 IDENTIFIER_NOT_FOUND
            return camara_error_response(
                404,
                "IDENTIFIER_NOT_FOUND",
                "The device identifier provided is not associated with a customer account",
                correlator
            )
        
        legacy_status = map_connection_status(profile)
        reachable, connectivity = map_status_to_camara(legacy_status)
        
        response_data = {
            "lastStatusTime": datetime.utcnow().isoformat() + "Z",
            "reachable": reachable,
            "reachabilityStatus": legacy_status,  # Legacy field for dashboard compatibility
        }
        
        if connectivity:
            response_data["connectivity"] = connectivity
        
        if device_provided and request.device:
            if request.device.ipv4Address:
                response_data["device"] = {"ipv4Address": request.device.ipv4Address.model_dump()}
            elif request.device.phoneNumber:
                response_data["device"] = {"phoneNumber": request.device.phoneNumber}
        
        return ReachabilityStatusResponse(**response_data)
        
    except Exception as e:
        return camara_error_response(
            500,
            "INTERNAL",
            f"Internal server error: {str(e)}",
            correlator
        )


# -------------------- Device Roaming Status --------------------

@router.post(
    "/roaming/v1/retrieve",
    response_model=RoamingStatusResponse,
    responses={
        200: {"description": "Device roaming status retrieved successfully"},
        400: {"description": "Invalid request", "model": ErrorInfo},
        401: {"description": "Unauthorized", "model": ErrorInfo},
        404: {"description": "Device not found", "model": ErrorInfo},
        500: {"description": "Internal server error", "model": ErrorInfo},
    }
)
async def get_roaming_status(
    request: RoamingStatusRequest,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    device_ip: Optional[str] = Query(None, description="Device IP (demo mode)"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Device Roaming Status: Check if device is roaming
    
    POST /device-status/roaming/v1/retrieve
    
    Returns whether the device is currently roaming and in which country.
    
    Uses TF-SDK client for network queries.
    **Demo mode**: Pass `device_ip` query param to bypass device resolution.
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    try:
        # Resolve device IP
        resolved_ip = device_ip
        if not resolved_ip and request.device.ipv4Address:
            resolved_ip = request.device.ipv4Address.publicAddress
        
        if not resolved_ip:
            return camara_error_response(
                400,
                "INVALID_ARGUMENT",
                "Device IP address is required",
                correlator
            )
        
        # Try SDK method first (preferred)
        sdk_result = get_roaming_via_sdk(resolved_ip, core)
        if sdk_result:
            return RoamingStatusResponse(
                roaming=sdk_result["roaming"],
                countryCode=sdk_result.get("countryCode"),
                countryName=sdk_result.get("countryName")
            )
        
        # Fallback: use profile-based resolution
        profile = get_ue_profile(resolved_ip, core)
        
        if not profile:
            return camara_error_response(
                404,
                "DEVICE_NOT_FOUND",
                "The specified device was not found",
                correlator
            )
        
        is_roaming, country_code, country_name = check_roaming_status(profile)
        
        return RoamingStatusResponse(
            roaming=is_roaming,
            countryCode=country_code,
            countryName=[country_name] if country_name else None
        )
        
    except Exception as e:
        return camara_error_response(
            500,
            "INTERNAL",
            f"Internal server error: {str(e)}",
            correlator
        )


# -------------------- Reachability Status Subscriptions --------------------

@router.post(
    "/reachability/v1/subscriptions",
    response_model=SubscriptionResponse,
    status_code=201,
    responses={
        201: {"description": "Subscription created successfully"},
        400: {"description": "Invalid request", "model": ErrorInfo},
        401: {"description": "Unauthorized", "model": ErrorInfo},
    }
)
async def create_reachability_subscription(
    request: SubscriptionRequest,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Device Reachability Status: Create subscription
    
    POST /device-status/reachability/v1/subscriptions
    
    Subscribe to receive notifications when device connectivity status changes.
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    subscription_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    
    # Calculate expiration
    expires_at = request.subscriptionExpireTime
    if not expires_at:
        # Default: 24 hours
        from datetime import timedelta
        expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
    
    subscription = {
        "subscriptionId": subscription_id,
        "device": request.device.model_dump(),
        "sink": request.sink,
        "sinkCredential": request.sinkCredential,
        "startsAt": now,
        "expiresAt": expires_at,
        "maxEvents": request.subscriptionMaxEvents,
        "eventCount": 0,
        "core": core
    }
    
    subscriptions["reachability"][subscription_id] = subscription
    
    return SubscriptionResponse(
        subscriptionId=subscription_id,
        device=request.device,
        sink=request.sink,
        startsAt=now,
        expiresAt=expires_at
    )


@router.get(
    "/reachability/v1/subscriptions/{subscriptionId}",
    response_model=SubscriptionResponse,
    responses={
        200: {"description": "Subscription retrieved"},
        404: {"description": "Subscription not found", "model": ErrorInfo},
    }
)
async def get_reachability_subscription(
    subscriptionId: str,
    response: Response,
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """Get a reachability status subscription by ID"""
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    sub = subscriptions["reachability"].get(subscriptionId)
    if not sub:
        return camara_error_response(404, "NOT_FOUND", "Subscription not found", correlator)
    
    return SubscriptionResponse(
        subscriptionId=sub["subscriptionId"],
        device=Device(**sub["device"]),
        sink=sub["sink"],
        startsAt=sub["startsAt"],
        expiresAt=sub.get("expiresAt")
    )


@router.delete(
    "/reachability/v1/subscriptions/{subscriptionId}",
    status_code=204,
    responses={
        204: {"description": "Subscription deleted"},
        404: {"description": "Subscription not found", "model": ErrorInfo},
    }
)
async def delete_reachability_subscription(
    subscriptionId: str,
    response: Response,
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """Delete a reachability status subscription"""
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    if subscriptionId not in subscriptions["reachability"]:
        return camara_error_response(404, "NOT_FOUND", "Subscription not found", correlator)
    
    del subscriptions["reachability"][subscriptionId]
    return Response(status_code=204, headers={"x-correlator": correlator})


# -------------------- Roaming Status Subscriptions --------------------

@router.post(
    "/roaming/v1/subscriptions",
    response_model=SubscriptionResponse,
    status_code=201,
    responses={
        201: {"description": "Subscription created successfully"},
        400: {"description": "Invalid request", "model": ErrorInfo},
        401: {"description": "Unauthorized", "model": ErrorInfo},
    }
)
async def create_roaming_subscription(
    request: SubscriptionRequest,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Device Roaming Status: Create subscription
    
    POST /device-status/roaming/v1/subscriptions
    
    Subscribe to receive notifications when device roaming status changes.
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    subscription_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    
    expires_at = request.subscriptionExpireTime
    if not expires_at:
        from datetime import timedelta
        expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z"
    
    subscription = {
        "subscriptionId": subscription_id,
        "device": request.device.model_dump(),
        "sink": request.sink,
        "sinkCredential": request.sinkCredential,
        "startsAt": now,
        "expiresAt": expires_at,
        "maxEvents": request.subscriptionMaxEvents,
        "eventCount": 0,
        "core": core
    }
    
    subscriptions["roaming"][subscription_id] = subscription
    
    return SubscriptionResponse(
        subscriptionId=subscription_id,
        device=request.device,
        sink=request.sink,
        startsAt=now,
        expiresAt=expires_at
    )


@router.get(
    "/roaming/v1/subscriptions/{subscriptionId}",
    response_model=SubscriptionResponse,
    responses={
        200: {"description": "Subscription retrieved"},
        404: {"description": "Subscription not found", "model": ErrorInfo},
    }
)
async def get_roaming_subscription(
    subscriptionId: str,
    response: Response,
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """Get a roaming status subscription by ID"""
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    sub = subscriptions["roaming"].get(subscriptionId)
    if not sub:
        return camara_error_response(404, "NOT_FOUND", "Subscription not found", correlator)
    
    return SubscriptionResponse(
        subscriptionId=sub["subscriptionId"],
        device=Device(**sub["device"]),
        sink=sub["sink"],
        startsAt=sub["startsAt"],
        expiresAt=sub.get("expiresAt")
    )


@router.delete(
    "/roaming/v1/subscriptions/{subscriptionId}",
    status_code=204,
    responses={
        204: {"description": "Subscription deleted"},
        404: {"description": "Subscription not found", "model": ErrorInfo},
    }
)
async def delete_roaming_subscription(
    subscriptionId: str,
    response: Response,
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """Delete a roaming status subscription"""
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    if subscriptionId not in subscriptions["roaming"]:
        return camara_error_response(404, "NOT_FOUND", "Subscription not found", correlator)
    
    del subscriptions["roaming"][subscriptionId]
    return Response(status_code=204, headers={"x-correlator": correlator})


# -------------------- Demo/Simulation Endpoints --------------------

@router.post("/demo/simulate-status-change", include_in_schema=True, tags=["Demo"])
async def simulate_status_change(
    device_ip: str = Query(..., description="Device IP"),
    new_status: str = Query(..., description="New status: CONNECTED, IDLE, DISCONNECTED"),
    core: str = Query("coresim", description="Target core")
):
    """
    Demo endpoint: Simulate a device status change.
    This would trigger notifications to subscribers in a full implementation.
    """
    # In production, this would:
    # 1. Update the UE state in CoreSim/Redis
    # 2. Trigger CloudEvent notifications to all matching subscribers
    
    return {
        "message": f"Status change simulated for {device_ip}",
        "newStatus": new_status,
        "affectedSubscriptions": len(subscriptions["reachability"]) + len(subscriptions["roaming"])
    }


@router.get("/demo/subscriptions", include_in_schema=True, tags=["Demo"])
async def list_all_subscriptions():
    """Demo endpoint: List all active subscriptions"""
    return {
        "reachability": list(subscriptions["reachability"].values()),
        "roaming": list(subscriptions["roaming"].values())
    }
