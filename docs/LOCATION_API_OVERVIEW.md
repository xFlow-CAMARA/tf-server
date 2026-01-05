# CAMARA Location Retrieval API - Overview

## What is Location Retrieval?

Get the **geographic location** of a mobile device as an **area** (not exact coordinates) to protect privacy.

**Use Cases:**
- Emergency services locating callers
- Fleet management tracking vehicles
- Geofencing applications
- Asset tracking

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                            │
│   ┌──────────────┐                                                  │
│   │   Web App    │  "Where is device 12.1.0.1?"                     │
│   └──────┬───────┘                                                  │
└──────────┼──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY LAYER                            │
│   ┌──────────────┐                                                  │
│   │   TF-SDK     │  CAMARA Location API (Port 8200)                 │
│   │   (Python)   │  POST /location-retrieval/v0/retrieve            │
│   └──────┬───────┘                                                  │
└──────────┼──────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    NETWORK EXPOSURE LAYER (NEF)                      │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐     │
│   │  monitoring  │ ───► │ ue-identity  │ ───► │    Redis     │     │
│   │   -event     │      │  -service    │      │   (UE Data)  │     │
│   │  Port 8102   │      │              │      │              │     │
│   └──────────────┘      └──────────────┘      └──────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         5G CORE NETWORK                              │
│   ┌──────────────┐                                                  │
│   │   CoreSim    │  Has UE location (cell-based: NCGI)              │
│   │   Port 8080  │                                                  │
│   └──────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### Device Identification

You can identify a device by any of these:

| Identifier | Example | Format |
|------------|---------|--------|
| **ipv4Address** | `12.1.0.1` | IPv4 address |
| **phoneNumber** | `+33612345678` | E.164 format |
| **networkAccessIdentifier** | `imsi-001010000000001` | IMSI/NAI |
| **ipv6Address** | `2001:db8::1` | IPv6 address |

### Area Types

Location is returned as an **area**, not a point:

```
CIRCLE                              POLYGON
┌─────────────────────┐            ┌─────────────────────┐
│                     │            │    ●───────●        │
│       ╭─────╮       │            │   /         \       │
│      ╱       ╲      │            │  /           \      │
│     │    ●    │     │            │ ●             ●     │
│      ╲       ╱      │            │  \           /      │
│       ╰─────╯       │            │   \         /       │
│                     │            │    ●───────●        │
│  center + radius    │            │  3-15 boundary pts  │
└─────────────────────┘            └─────────────────────┘
```

### Optional Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| **maxAge** | int | Max age of location data in seconds |
| **maxSurface** | int | Max area size in square meters |

---

## Call Flow Diagrams

### Flow 1: Successful Location Retrieval

```
┌────────┐     ┌─────────┐     ┌─────────┐     ┌───────┐
│  App   │     │ TF-SDK  │     │   NEF   │     │ Redis │
└───┬────┘     └────┬────┘     └────┬────┘     └───┬───┘
    │               │               │              │
    │ POST /retrieve│               │              │
    │ {device: IP}  │               │              │
    │──────────────►│               │              │
    │               │               │              │
    │               │ POST /3gpp-   │              │
    │               │ monitoring... │              │
    │               │──────────────►│              │
    │               │               │              │
    │               │               │ Query UE     │
    │               │               │─────────────►│
    │               │               │              │
    │               │               │ Location     │
    │               │               │◄─────────────│
    │               │               │              │
    │               │ 200 OK        │              │
    │               │◄──────────────│              │
    │               │               │              │
    │ 200 OK        │               │              │
    │ {area: CIRCLE}│               │              │
    │◄──────────────│               │              │
```

### Flow 2: Device Not Found

```
┌────────┐     ┌─────────┐     ┌─────────┐     ┌───────┐
│  App   │     │ TF-SDK  │     │   NEF   │     │ Redis │
└───┬────┘     └────┬────┘     └────┬────┘     └───┬───┘
    │               │               │              │
    │ POST /retrieve│               │              │
    │ {device: ???} │               │              │
    │──────────────►│               │              │
    │               │               │              │
    │               │ POST /3gpp-   │              │
    │               │──────────────►│              │
    │               │               │              │
    │               │               │ Query UE     │
    │               │               │─────────────►│
    │               │               │              │
    │               │               │ redis: nil   │
    │               │               │◄─────────────│
    │               │               │              │
    │               │ 404 Error     │              │
    │               │◄──────────────│              │
    │               │               │              │
    │ 404 Error     │               │              │
    │ DEVICE_NOT    │               │              │
    │ _FOUND        │               │              │
    │◄──────────────│               │              │
```

### Flow 3: Missing Identifier

```
┌────────┐     ┌─────────┐
│  App   │     │ TF-SDK  │
└───┬────┘     └────┬────┘
    │               │
    │ POST /retrieve│
    │ {} (empty)    │
    │──────────────►│
    │               │
    │ 422 Error     │
    │ MISSING_      │
    │ IDENTIFIER    │
    │◄──────────────│
```

---

## Request/Response Examples

### Simple Request (IPv4)

```json
// Request
POST /location-retrieval/v0/retrieve

{
  "device": {
    "ipv4Address": {
      "publicAddress": "12.1.0.1"
    }
  },
  "maxAge": 60
}
```

```json
// Response (Circle)
{
  "lastLocationTime": "2025-12-17T10:30:00.000Z",
  "area": {
    "areaType": "CIRCLE",
    "center": {
      "latitude": 45.754114,
      "longitude": 4.860374
    },
    "radius": 150.0
  }
}
```

### Response with Polygon

```json
{
  "lastLocationTime": "2025-12-17T10:30:00.000Z",
  "area": {
    "areaType": "POLYGON",
    "boundary": [
      {"latitude": 48.8576, "longitude": 2.3532},
      {"latitude": 48.8576, "longitude": 2.3512},
      {"latitude": 48.8556, "longitude": 2.3512},
      {"latitude": 48.8556, "longitude": 2.3532}
    ]
  }
}
```

---

## Error Codes

| HTTP | Code | Description |
|------|------|-------------|
| 400 | INVALID_ARGUMENT | Bad request format |
| 404 | DEVICE_NOT_FOUND | UE not in network |
| 422 | MISSING_IDENTIFIER | No device in request |
| 422 | DEVICE_UNIDENTIFIABLE | Invalid identifier |
| 503 | SERVICE_UNAVAILABLE | NEF down |

### Error Response Format

```json
{
  "status": 404,
  "code": "DEVICE_NOT_FOUND",
  "message": "Device not registered or no active PDU session"
}
```

---

## Data Transformation

```
CAMARA Request           →    3GPP Request           →    5G Core
───────────────────────────────────────────────────────────────────
{                             {                           
  "device": {                   "externalId":            Query by
    "ipv4Address": {              "nef:12.1.0.1",       SUPI in
      "publicAddress":          "monitoringType":        Redis
        "12.1.0.1"                "LOCATION_REPORTING"  
    }                         }                          Returns
  }                                                      Cell ID
}                                                        (NCGI)
                                     │
                                     ▼
CAMARA Response          ←    3GPP Response           ←
───────────────────────────────────────────────────────────────────
{                             {
  "area": {                     "locationInfo": {
    "areaType": "POLYGON",        "geographicArea": {     Convert
    "boundary": [...]               "shape": "POLYGON",   Cell ID
  },                                "pointList": [...]    to GPS
  "lastLocationTime": "..."       }                       coords
}                               }
                              }
```

---

## Privacy Features

| Feature | Description |
|---------|-------------|
| **Area-based** | Never returns exact coordinates |
| **Min radius** | Enforced minimum (typically 50m) |
| **maxSurface** | App can request limited precision |
| **Consent** | User must authorize via OAuth |

---

## Summary

1. **App** sends device identifier (IP, phone, etc.)
2. **TF-SDK** transforms to 3GPP format
3. **NEF** looks up device in Redis
4. **5G Core** provides cell-based location
5. **Response** contains area (Circle or Polygon)

The API hides the complexity of 5G location services behind a simple REST interface.
