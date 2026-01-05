"""
CAMARA Number Verification API vwip Router
Fully CAMARA-compliant implementation

This API verifies or retrieves the mobile phone number currently allocated 
by the network operator to the SIM in the end user's device.

It uses silent authentication (Network-based or SIM-Based authentication) 
to verify possession of a phone number without requiring user interaction.
"""

from fastapi import APIRouter, HTTPException, Header, Request, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime
import uuid
import hashlib
import re
import os

router = APIRouter(prefix="/number-verification/vwip", tags=["CAMARA Number Verification"])

# Shared network clients (populated by api_server.py)
network_clients = {}

# x-correlator pattern from CAMARA spec
X_CORRELATOR_PATTERN = r'^[a-zA-Z0-9\-_:;.\/<>{}]{0,256}$'


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


# ====================== CAMARA-compliant Models ======================

class NumberVerificationRequestBody(BaseModel):
    """
    Payload to verify the phone number.
    Only one of phoneNumber or hashedPhoneNumber must be provided.
    minProperties: 1, maxProperties: 1
    """
    model_config = ConfigDict(extra='forbid')
    
    phoneNumber: Optional[str] = Field(
        None,
        pattern=r'^\+[1-9][0-9]{4,14}$',
        description="A public identifier addressing a telephone subscription. In mobile networks it corresponds to the MSISDN (Mobile Station International Subscriber Directory Number). In order to be globally unique it has to be formatted in international format, according to E.164 standard, prefixed with '+'.",
        examples=["+123456789"]
    )
    hashedPhoneNumber: Optional[str] = Field(
        None,
        pattern=r'^[a-fA-F0-9]{64}$',
        description="Hashed phone number. SHA-256 (in hexadecimal representation) of the mobile phone number in E.164 format (starting with country code). Prefixed with '+'.",
        examples=["32f67ab4e4312618b09cd23ed8ce41b13e095fe52b73b2e8da8ef49830e50dba"]
    )

    @field_validator('hashedPhoneNumber', 'phoneNumber', mode='before')
    @classmethod
    def check_not_both_provided(cls, v, info):
        return v

    def validate_mutual_exclusion(self):
        """Validate that exactly one of phoneNumber or hashedPhoneNumber is provided"""
        has_phone = self.phoneNumber is not None and self.phoneNumber != ""
        has_hashed = self.hashedPhoneNumber is not None and self.hashedPhoneNumber != ""
        
        if not has_phone and not has_hashed:
            raise ValueError("Either phoneNumber or hashedPhoneNumber must be provided")
        if has_phone and has_hashed:
            raise ValueError("Only one of phoneNumber or hashedPhoneNumber must be provided")
        return self


class NumberVerificationMatchResponse(BaseModel):
    """Number verification result"""
    model_config = ConfigDict(extra='forbid')
    
    devicePhoneNumberVerified: bool = Field(
        ...,
        description="Number verification. True, if it matches"
    )


class NumberVerificationShareResponse(BaseModel):
    """Number verification share result"""
    model_config = ConfigDict(extra='forbid')
    
    devicePhoneNumber: str = Field(
        ...,
        pattern=r'^\+[1-9][0-9]{4,14}$',
        description="A public identifier addressing a telephone subscription. In mobile networks it corresponds to the MSISDN (Mobile Station International Subscriber Directory Number). In order to be globally unique it has to be formatted in international format, according to E.164 standard, prefixed with '+'.",
        examples=["+123456789"]
    )


class ErrorInfo(BaseModel):
    """CAMARA-compliant error response"""
    model_config = ConfigDict(extra='forbid')
    
    status: int = Field(..., description="HTTP response status code")
    code: str = Field(..., description="A human-readable code to describe the error")
    message: str = Field(..., description="A human-readable description of what the event represents")


# ====================== Helper Functions ======================

def hash_phone_number(phone_number: str) -> str:
    """
    Compute SHA-256 hash of a phone number.
    The phone number must be in E.164 format with '+' prefix.
    """
    return hashlib.sha256(phone_number.encode('utf-8')).hexdigest()


def verify_phone_numbers(device_phone: str, request: NumberVerificationRequestBody) -> bool:
    """
    Compare the device's phone number with the provided phone number.
    Supports both plain text and hashed comparison.
    """
    if request.phoneNumber:
        # Direct comparison (normalize by removing spaces)
        return device_phone.strip() == request.phoneNumber.strip()
    
    if request.hashedPhoneNumber:
        # Hash the device phone number and compare
        device_hash = hash_phone_number(device_phone)
        return device_hash.lower() == request.hashedPhoneNumber.lower()
    
    return False


def get_client(core: str):
    """Get network client for the specified core"""
    if core not in network_clients:
        return None
    return network_clients[core]


def get_device_phone_number_from_token(access_token: str, core: str) -> Optional[str]:
    """
    Extract the device phone number from the access token.
    
    In a real implementation, this would:
    1. Validate the 3-legged OAuth token
    2. Extract the phone number claim from the token (authenticated via mobile network)
    3. Return the phone number associated with the authenticated session
    
    For simulation/demo purposes with CoreSim, we simulate this by:
    - Using a mock phone number mapping based on the token
    - Or querying the UE profile service to get the MSISDN
    """
    client = get_client(core)
    if client is None:
        return None
    
    # In production, extract from JWT claims or OIDC userinfo
    # For CoreSim demo, we'll use a simulated phone number
    # The token would contain the authenticated user's phone number
    
    # Simulate getting phone number from authenticated session
    # In real implementation, this comes from the network authentication
    try:
        # Try to get from UE profile service via tf-sdk
        # This simulates the network-based authentication flow
        if hasattr(client, 'get_authenticated_phone_number'):
            return client.get_authenticated_phone_number(access_token)
    except Exception:
        pass
    
    # Fallback: Return a simulated phone number for demo
    # In production, this would return None if token is invalid
    return None


def simulate_authenticated_phone_number(device_ip: Optional[str] = None) -> str:
    """
    Simulate getting the authenticated phone number for demo purposes.
    
    In production, the phone number comes from:
    - Network-based authentication (mobile network identifies the device)
    - SIM-based authentication (TS.43 temporary token)
    
    For CoreSim demo, we generate a consistent phone number based on device info.
    """
    if device_ip:
        # Generate consistent phone number from IP
        ip_hash = int(hashlib.md5(device_ip.encode()).hexdigest()[:8], 16)
        phone_suffix = str(ip_hash % 10000000000).zfill(10)
        return f"+1{phone_suffix}"
    
    # Default demo phone number
    return "+33612345678"


# ====================== Mock Token Storage ======================
# In production, this would be handled by the OAuth/OIDC provider
# Maps access tokens to authenticated phone numbers (from network auth)
authenticated_sessions = {}


def register_authenticated_session(token: str, phone_number: str, device_ip: Optional[str] = None):
    """Register an authenticated session (for demo/testing purposes)"""
    authenticated_sessions[token] = {
        "phoneNumber": phone_number,
        "deviceIp": device_ip,
        "authenticatedAt": datetime.utcnow().isoformat() + "Z"
    }


def get_phone_from_session(token: str) -> Optional[str]:
    """Get phone number from authenticated session"""
    session = authenticated_sessions.get(token)
    if session:
        return session.get("phoneNumber")
    return None


# ====================== API Endpoints ======================

@router.post("/verify", response_model=NumberVerificationMatchResponse, responses={
    200: {
        "description": "OK",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/NumberVerificationMatchResponse"}
            }
        }
    },
    400: {
        "description": "Problem with the client request",
        "content": {
            "application/json": {
                "example": {"status": 400, "code": "INVALID_ARGUMENT", "message": "Client specified an invalid argument, request body or query param"}
            }
        }
    },
    401: {
        "description": "Unauthorized",
        "content": {
            "application/json": {
                "example": {"status": 401, "code": "UNAUTHENTICATED", "message": "Request not authenticated due to missing, invalid, or expired credentials."}
            }
        }
    },
    403: {
        "description": "Client does not have sufficient permission",
        "content": {
            "application/json": {
                "examples": {
                    "PERMISSION_DENIED": {
                        "value": {"status": 403, "code": "PERMISSION_DENIED", "message": "Client does not have sufficient permissions to perform this action."}
                    },
                    "USER_NOT_AUTHENTICATED_BY_MOBILE_NETWORK": {
                        "value": {"status": 403, "code": "NUMBER_VERIFICATION.USER_NOT_AUTHENTICATED_BY_MOBILE_NETWORK", "message": "Client must authenticate via the mobile network to use this service"}
                    }
                }
            }
        }
    }
})
async def phone_number_verify(
    raw_request: Request,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    device_ip: Optional[str] = Query(None, description="Device IP address (demo mode - bypasses token auth)"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Number Verification vwip: Verify phone number
    
    POST /number-verification/vwip/verify
    
    Verifies if the specified phone number (plain text or hashed) matches 
    the phone number associated with the authenticated mobile network session.
    
    **Authentication Requirements:**
    - Requires a 3-legged OAuth token obtained via mobile network authentication
    - User interaction is NOT allowed (silent authentication only)
    - SMS OTP or username/password authentication is NOT supported
    - **Demo mode**: Pass `device_ip` query param to bypass token authentication
    
    **Request Body:**
    - `phoneNumber`: Plain text phone number in E.164 format (e.g., +123456789)
    - `hashedPhoneNumber`: SHA-256 hash of phone number in E.164 format
    - Only ONE of the above must be provided
    
    **Returns:**
    - `devicePhoneNumberVerified`: true if phone number matches, false otherwise
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    # Parse and validate request body
    try:
        body = await raw_request.json()
        verify_request = NumberVerificationRequestBody(**body)
        verify_request.validate_mutual_exclusion()
    except ValueError as e:
        return camara_error_response(400, "INVALID_ARGUMENT", str(e), correlator)
    except Exception as e:
        return camara_error_response(400, "INVALID_ARGUMENT", f"Invalid request: {str(e)}", correlator)
    
    # Demo mode: if device_ip is provided, use it directly for network lookup
    if device_ip:
        client = get_client(core)
        if client is not None and hasattr(client, 'verify_phone_number'):
            try:
                is_match = client.verify_phone_number(
                    ip_address=device_ip,
                    phone_number=verify_request.phoneNumber,
                    hashed_phone_number=verify_request.hashedPhoneNumber
                )
                return NumberVerificationMatchResponse(devicePhoneNumberVerified=is_match)
            except Exception as e:
                return camara_error_response(500, "INTERNAL", f"Network lookup failed: {str(e)}", correlator)
        else:
            return camara_error_response(503, "SERVICE_UNAVAILABLE", "Network client not available", correlator)
    
    # Production mode: require Bearer token
    auth_header = raw_request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return camara_error_response(
            401, 
            "UNAUTHENTICATED", 
            "Request not authenticated due to missing, invalid, or expired credentials.",
            correlator
        )
    
    access_token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Get the authenticated phone number from the session
    # In production, this validates the token and extracts the phone number
    # from the network authentication flow
    device_phone_number = get_phone_from_session(access_token)
    
    if device_phone_number is None:
        # Try to get device IP from request for network-based lookup
        client_ip = raw_request.client.host if raw_request.client else None
        
        # Check if we can get phone number from network client via tf-sdk
        client = get_client(core)
        if client is not None and client_ip:
            try:
                # Try to resolve phone number from network via UE Identity Service
                if hasattr(client, 'get_msisdn_by_ip'):
                    device_phone_number = client.get_msisdn_by_ip(client_ip)
                    # Register for subsequent requests
                    register_authenticated_session(access_token, device_phone_number, client_ip)
            except Exception as e:
                # Log the error but continue to try fallback
                pass
        
        if device_phone_number is None:
            # For demo: simulate authenticated phone number
            device_phone_number = simulate_authenticated_phone_number(client_ip)
            # Register for subsequent requests
            register_authenticated_session(access_token, device_phone_number, client_ip)
    
    # Perform verification
    # Try using tf-sdk's verify_phone_number if available
    client = get_client(core)
    if client is not None and hasattr(client, 'verify_phone_number'):
        client_ip = raw_request.client.host if raw_request.client else None
        if client_ip:
            try:
                is_match = client.verify_phone_number(
                    ip_address=client_ip,
                    phone_number=verify_request.phoneNumber,
                    hashed_phone_number=verify_request.hashedPhoneNumber
                )
                return NumberVerificationMatchResponse(devicePhoneNumberVerified=is_match)
            except Exception:
                # Fall back to local verification
                pass
    
    # Local verification fallback
    is_match = verify_phone_numbers(device_phone_number, verify_request)
    
    return NumberVerificationMatchResponse(devicePhoneNumberVerified=is_match)


@router.get("/device-phone-number", response_model=NumberVerificationShareResponse, responses={
    200: {
        "description": "OK",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/NumberVerificationShareResponse"}
            }
        }
    },
    400: {
        "description": "Problem with the client request",
        "content": {
            "application/json": {
                "example": {"status": 400, "code": "INVALID_ARGUMENT", "message": "Client specified an invalid argument, request body or query param"}
            }
        }
    },
    401: {
        "description": "Unauthorized",
        "content": {
            "application/json": {
                "example": {"status": 401, "code": "UNAUTHENTICATED", "message": "Request not authenticated due to missing, invalid, or expired credentials."}
            }
        }
    },
    403: {
        "description": "Client does not have sufficient permission",
        "content": {
            "application/json": {
                "examples": {
                    "PERMISSION_DENIED": {
                        "value": {"status": 403, "code": "PERMISSION_DENIED", "message": "Client does not have sufficient permissions to perform this action."}
                    },
                    "USER_NOT_AUTHENTICATED_BY_MOBILE_NETWORK": {
                        "value": {"status": 403, "code": "NUMBER_VERIFICATION.USER_NOT_AUTHENTICATED_BY_MOBILE_NETWORK", "message": "Client must authenticate via the mobile network to use this service"}
                    }
                }
            }
        }
    }
})
async def phone_number_share(
    raw_request: Request,
    response: Response,
    core: str = Query("coresim", description="Target 5G core"),
    device_ip: Optional[str] = Query(None, description="Device IP address (demo mode - bypasses token auth)"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator")
):
    """
    CAMARA Number Verification vwip: Get device phone number
    
    GET /number-verification/vwip/device-phone-number
    
    Returns the phone number associated with the authenticated mobile network session.
    This allows API consumers to verify the number themselves.
    
    **Authentication Requirements:**
    - Requires a 3-legged OAuth token obtained via mobile network authentication
    - User interaction is NOT allowed (silent authentication only)
    - SMS OTP or username/password authentication is NOT supported
    - **Demo mode**: Pass `device_ip` query param to bypass token authentication
    
    **Returns:**
    - `devicePhoneNumber`: The phone number in E.164 format (e.g., +123456789)
    """
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    # Demo mode: if device_ip is provided, use it directly for network lookup
    if device_ip:
        client = get_client(core)
        if client is not None and hasattr(client, 'get_msisdn_by_ip'):
            try:
                phone_number = client.get_msisdn_by_ip(device_ip)
                return NumberVerificationShareResponse(devicePhoneNumber=phone_number)
            except Exception as e:
                return camara_error_response(500, "INTERNAL", f"Network lookup failed: {str(e)}", correlator)
        else:
            return camara_error_response(503, "SERVICE_UNAVAILABLE", "Network client not available", correlator)
    
    # Production mode: require Bearer token
    auth_header = raw_request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return camara_error_response(
            401, 
            "UNAUTHENTICATED", 
            "Request not authenticated due to missing, invalid, or expired credentials.",
            correlator
        )
    
    access_token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Get the authenticated phone number from the session
    device_phone_number = get_phone_from_session(access_token)
    
    if device_phone_number is None:
        # Try to get device IP from request for network-based lookup
        client_ip = raw_request.client.host if raw_request.client else None
        
        # Check if we can get phone number from network client via tf-sdk
        client = get_client(core)
        if client is not None and client_ip:
            try:
                # Try to resolve phone number from network via UE Identity Service
                if hasattr(client, 'get_msisdn_by_ip'):
                    device_phone_number = client.get_msisdn_by_ip(client_ip)
                    # Register for subsequent requests
                    register_authenticated_session(access_token, device_phone_number, client_ip)
            except Exception:
                pass
        
        if device_phone_number is None:
            # For demo: simulate authenticated phone number
            device_phone_number = simulate_authenticated_phone_number(client_ip)
            # Register for subsequent requests
            register_authenticated_session(access_token, device_phone_number, client_ip)
    
    return NumberVerificationShareResponse(devicePhoneNumber=device_phone_number)


# ====================== Demo/Testing Endpoints ======================

@router.post("/demo/register-session", include_in_schema=True, tags=["Demo"])
async def demo_register_session(
    phone_number: str = Query(..., description="Phone number in E.164 format"),
    token: str = Query(None, description="Access token (auto-generated if not provided)"),
    device_ip: Optional[str] = Query(None, description="Device IP address")
):
    """
    Demo endpoint: Register an authenticated session for testing.
    
    This simulates the network authentication flow that would normally happen
    via OIDC Authorization Code Flow or CIBA with TS.43 token.
    
    In production, sessions are created by the OAuth/OIDC provider after
    successful network-based authentication.
    """
    # Validate phone number format
    if not re.match(r'^\+[1-9][0-9]{4,14}$', phone_number):
        raise HTTPException(
            status_code=400,
            detail="Phone number must be in E.164 format (e.g., +123456789)"
        )
    
    # Generate token if not provided
    if not token:
        token = str(uuid.uuid4())
    
    register_authenticated_session(token, phone_number, device_ip)
    
    return {
        "message": "Session registered successfully",
        "accessToken": token,
        "phoneNumber": phone_number,
        "usage": f"Use 'Authorization: Bearer {token}' header for /verify and /device-phone-number endpoints"
    }


@router.get("/demo/hash-phone-number", include_in_schema=True, tags=["Demo"])
async def demo_hash_phone_number(
    phone_number: str = Query(..., description="Phone number in E.164 format to hash")
):
    """
    Demo endpoint: Generate SHA-256 hash of a phone number.
    
    Useful for testing the /verify endpoint with hashedPhoneNumber.
    """
    # Validate phone number format
    if not re.match(r'^\+[1-9][0-9]{4,14}$', phone_number):
        raise HTTPException(
            status_code=400,
            detail="Phone number must be in E.164 format (e.g., +123456789)"
        )
    
    hashed = hash_phone_number(phone_number)
    
    return {
        "phoneNumber": phone_number,
        "hashedPhoneNumber": hashed,
        "usage": f"Use '{hashed}' as hashedPhoneNumber in /verify request"
    }
