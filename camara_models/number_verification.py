"""
CAMARA Number Verification API Models

Compliant with CAMARA Number Verification vWIP specification.
https://github.com/camaraproject/NumberVerification
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional
import re


# ====================== Request Models ======================

class NumberVerificationRequestBody(BaseModel):
    """
    Payload to verify the phone number.
    
    POST /number-verification/vwip/verify
    
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

    def validate_mutual_exclusion(self) -> "NumberVerificationRequestBody":
        """
        Validate that exactly one of phoneNumber or hashedPhoneNumber is provided.
        Call this after model instantiation.
        """
        has_phone = self.phoneNumber is not None and self.phoneNumber != ""
        has_hashed = self.hashedPhoneNumber is not None and self.hashedPhoneNumber != ""
        
        if not has_phone and not has_hashed:
            raise ValueError("Either phoneNumber or hashedPhoneNumber must be provided")
        if has_phone and has_hashed:
            raise ValueError("Only one of phoneNumber or hashedPhoneNumber must be provided")
        return self


# ====================== Response Models ======================

class NumberVerificationMatchResponse(BaseModel):
    """
    Number verification result.
    
    Response for POST /number-verification/vwip/verify
    """
    model_config = ConfigDict(extra='forbid')
    
    devicePhoneNumberVerified: bool = Field(
        ...,
        description="Number verification. True, if it matches"
    )


class NumberVerificationShareResponse(BaseModel):
    """
    Number verification share result.
    
    Response for GET /number-verification/vwip/device-phone-number
    """
    model_config = ConfigDict(extra='forbid')
    
    devicePhoneNumber: str = Field(
        ...,
        pattern=r'^\+[1-9][0-9]{4,14}$',
        description="A public identifier addressing a telephone subscription. In mobile networks it corresponds to the MSISDN (Mobile Station International Subscriber Directory Number). In order to be globally unique it has to be formatted in international format, according to E.164 standard, prefixed with '+'.",
        examples=["+123456789"]
    )


# ====================== Helper Functions ======================

def hash_phone_number(phone_number: str) -> str:
    """
    Compute SHA-256 hash of a phone number.
    The phone number must be in E.164 format with '+' prefix.
    
    Args:
        phone_number: Phone number in E.164 format (e.g., "+123456789")
    
    Returns:
        64-character hexadecimal string (lowercase)
    """
    import hashlib
    return hashlib.sha256(phone_number.encode('utf-8')).hexdigest()


def verify_phone_numbers(
    device_phone: str,
    request: NumberVerificationRequestBody
) -> bool:
    """
    Compare the device's phone number with the provided phone number.
    Supports both plain text and hashed comparison.
    
    Args:
        device_phone: The device's actual phone number in E.164 format
        request: The verification request containing either phoneNumber or hashedPhoneNumber
    
    Returns:
        True if the phone numbers match, False otherwise
    """
    if request.phoneNumber:
        # Direct comparison
        return device_phone.strip() == request.phoneNumber.strip()
    
    if request.hashedPhoneNumber:
        # Hash the device phone number and compare (case-insensitive)
        device_hash = hash_phone_number(device_phone)
        return device_hash.lower() == request.hashedPhoneNumber.lower()
    
    return False


def validate_phone_number_format(phone_number: str) -> bool:
    """
    Validate that a phone number is in E.164 format.
    
    Args:
        phone_number: Phone number to validate
    
    Returns:
        True if valid E.164 format, False otherwise
    """
    pattern = r'^\+[1-9][0-9]{4,14}$'
    return bool(re.match(pattern, phone_number))
