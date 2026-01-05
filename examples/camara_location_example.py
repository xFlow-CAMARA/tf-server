#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CAMARA Location Retrieval API Example

This example demonstrates how to retrieve device location using the
CAMARA-compliant REST API endpoint.
"""

import requests
import json
import time


API_BASE_URL = "http://localhost:8200"
LOCATION_ENDPOINT = "/location-retrieval/vwip/retrieve"


def retrieve_location_by_phone(phone_number: str, max_age: int = None, max_surface: int = None):
    """
    Retrieve device location using phone number.
    
    Args:
        phone_number: Phone number in E.164 format (e.g., "+123456789")
        max_age: Maximum age of location data in seconds (optional)
        max_surface: Maximum acceptable area size in square meters (optional)
    
    Returns:
        dict: Location response with area (Circle or Polygon) and lastLocationTime
    """
    payload = {
        "device": {
            "phoneNumber": phone_number
        }
    }
    
    if max_age is not None:
        payload["maxAge"] = max_age
    if max_surface is not None:
        payload["maxSurface"] = max_surface
    
    headers = {
        "Content-Type": "application/json",
        "x-correlator": f"phone-location-{int(time.time())}"
    }
    
    response = requests.post(
        f"{API_BASE_URL}{LOCATION_ENDPOINT}?core=coresim",
        json=payload,
        headers=headers
    )
    
    response.raise_for_status()
    return response.json()


def retrieve_location_by_ipv4(public_address: str, public_port: int = None, private_address: str = None):
    """
    Retrieve device location using IPv4 address.
    
    Args:
        public_address: Public IPv4 address
        public_port: Public port number (optional)
        private_address: Private IPv4 address (optional)
    
    Returns:
        dict: Location response
    """
    device_ipv4 = {"publicAddress": public_address}
    
    if public_port is not None:
        device_ipv4["publicPort"] = public_port
    if private_address is not None:
        device_ipv4["privateAddress"] = private_address
    device_ipv4 = {"publicAddress": public_address}
    
    if public_port is not None:
        device_ipv4["publicPort"] = public_port
    if private_address is not None:
        device_ipv4["privateAddress"] = private_address
    
    payload = {
        "device": {
            "ipv4Address": device_ipv4
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "x-correlator": f"ipv4-location-{int(time.time())}"
    }
    
    response = requests.post(
        f"{API_BASE_URL}{LOCATION_ENDPOINT}?core=coresim",
        json=payload,
        headers=headers
    )
    
    response.raise_for_status()
    return response.json()


def print_location(location_data: dict):
    """Pretty print location data"""
    print(f"\n📍 Device Location:")
    print(f"   Last Updated: {location_data['lastLocationTime']}")
    
    area = location_data['area']
    if area['areaType'] == 'CIRCLE':
        center = area['center']
        print(f"   Area Type: Circle")
        print(f"   Center: ({center['latitude']:.6f}, {center['longitude']:.6f})")
        print(f"   Radius: {area['radius']} meters")
    elif area['areaType'] == 'POLYGON':
        print(f"   Area Type: Polygon")
        print(f"   Boundary Points: {len(area['boundary'])} points")
        for i, point in enumerate(area['boundary'], 1):
            print(f"      Point {i}: ({point['latitude']:.6f}, {point['longitude']:.6f})")
    
    if 'device' in location_data:
        device = location_data['device']
        print(f"\n   Identified by:")
        if device.get('phoneNumber'):
            print(f"      Phone: {device['phoneNumber']}")
        if device.get('ipv4Address'):
            ipv4 = device['ipv4Address']
            print(f"      IPv4: {ipv4['publicAddress']}", end="")
            if ipv4.get('publicPort'):
                print(f":{ipv4['publicPort']}", end="")
            if ipv4.get('privateAddress'):
                print(f" (private: {ipv4['privateAddress']})", end="")
            print()


def main():
    print("\n" + "=" * 70)
    print("CAMARA Location Retrieval API Example")
    print("=" * 70)
    
    # Example 1: Retrieve location by phone number
    print("\n--- Example 1: Location by Phone Number ---")
    try:
        location = retrieve_location_by_phone("+123456789", max_age=120)
        print_location(location)
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        if hasattr(e.response, 'json'):
            print(f"   Details: {e.response.json()}")
    
    # Example 2: Retrieve location by IPv4 with maxSurface constraint
    print("\n--- Example 2: Location by IPv4 with Surface Constraint ---")
    try:
        location = retrieve_location_by_ipv4(
            public_address="84.125.93.10",
            public_port=59765
        )
        print_location(location)
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
    
    # Example 3: Location with maxSurface constraint
    print("\n--- Example 3: Location with maxSurface=50000 ---")
    try:
        location = retrieve_location_by_phone("+987654321", max_surface=50000)
        print_location(location)
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
    
    # Example 4: Test error handling - missing device
    print("\n--- Example 4: Error Handling (Missing Device) ---")
    try:
        response = requests.post(
            f"{API_BASE_URL}{LOCATION_ENDPOINT}?core=coresim",
            json={},  # No device provided
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        error_data = e.response.json()
        print(f"✗ Expected Error:")
        print(f"   Status: {error_data['detail']['status']}")
        print(f"   Code: {error_data['detail']['code']}")
        print(f"   Message: {error_data['detail']['message']}")
    
    print("\n" + "=" * 70)
    print("Examples completed!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
