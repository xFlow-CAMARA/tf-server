# CAMARA Location Retrieval API v0.5.0 - Complete Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Complete Request Flow](#3-complete-request-flow)
4. [Data Models](#4-data-models)
5. [API Endpoint](#5-api-endpoint)
6. [Error Handling](#6-error-handling)
7. [Call Flow Diagrams](#7-call-flow-diagrams)
8. [Example Requests](#8-example-requests)

---

## 1. Overview

### What is Location Retrieval?

The **CAMARA Location Retrieval API** allows applications to get the current geographic location of a mobile device. The location is returned as an **area** (not exact coordinates) to protect user privacy.

### Use Cases

- **Emergency Services** - Locate users calling for help
- **Fleet Management** - Track delivery vehicles
- **Geofencing** - Trigger actions when devices enter/exit areas
- **Asset Tracking** - Monitor valuable equipment
- **Location-Based Services** - Provide nearby recommendations

### Key Features

| Feature | Description |
|---------|-------------|
| **Area-Based** | Returns Circle or Polygon, not exact point |
| **Privacy First** | Respects maxSurface to limit precision |
| **Multiple Identifiers** | IPv4, IPv6, phone number, or NAI |
| **Freshness Control** | maxAge parameter for data recency |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                            │
│   ┌──────────────┐                                                  │
│   │   Web App    │  "Where is device 12.1.0.1?"                     │
│   │  (Browser)   │                                                  │
│   └──────┬───────┘                                                  │
└──────────┼──────────────────────────────────────────────────────────┘
           │ HTTP POST /api/location
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY LAYER                            │
│   ┌──────────────┐      ┌──────────────┐                           │
│   │   Next.js    │ ───► │   TF-SDK     │  CAMARA API Server        │
│   │   Frontend   │      │   (Python)   │  Port 8200                │
│   │   Port 3002  │      │              │                           │
│   └──────────────┘      └──────┬───────┘                           │
└────────────────────────────────┼────────────────────────────────────┘
                                 │ POST /3gpp-monitoring-event/v1/...
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    NETWORK EXPOSURE LAYER (NEF)                      │
│   ┌──────────────┐      ┌──────────────┐                           │
│   │  monitoring  │ ───► │ue-identity   │  Resolves IP → SUPI       │
│   │   -event     │      │  -service    │                           │
│   │    (Go)      │      │              │                           │
│   │  Port 8102   │      └──────┬───────┘                           │
│   └──────┬───────┘             │                                    │
│          │                     ▼                                    │
│          │              ┌──────────────┐                           │
│          │              │    Redis     │  UE Data Store            │
│          │              │  Port 6380   │                           │
│          │              └──────────────┘                           │
└──────────┼──────────────────────────────────────────────────────────┘
           │ Query UE Info
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         5G CORE NETWORK                              │
│   ┌──────────────┐      ┌──────────────┐                           │
│   │   CoreSim    │ ───► │     AMF      │  Has UE location (NCGI)   │
│   │   Port 8080  │      │              │                           │
│   └──────────────┘      └──────────────┘                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Roles

| Component | Port | Purpose |
|-----------|------|---------|
| **TF-SDK** | 8200 | CAMARA API server, transforms requests |
| **monitoring-event** | 8102 | NEF service for location queries |
| **ue-identity-service** | 8080 | Maps IP addresses to SUPI identifiers |
| **Redis** | 6380 | Stores UE state and location data |
| **CoreSim** | 8080 | Simulates 5G core network |

---

## 3. Complete Request Flow

### Step-by-Step Traceback

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Frontend (LocationPanel.tsx)                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  User selects device and clicks "Get Location"                      │
│                                                                     │
│  const payload = {                                                  │
│    device: {                                                        │
│      networkAccessIdentifier: "imsi-001010000000001"                │
│    },                                                               │
│    maxAge: 60                                                       │
│  };                                                                 │
│  await apiClient.getLocation(payload);                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: API Client (api-client.ts)                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  - Generates x-correlator UUID                                      │
│  - POST /api/location with JSON body                                │
│  - Sets Content-Type: application/json                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Next.js Route (app/api/location/route.ts)                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  - Extracts x-correlator                                            │
│  - Validates device identifier present                              │
│  - Normalizes device structure                                      │
│  - Calls adapter.getLocation(request)                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: Backend Adapter (base-tfsdk.ts)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  POST http://tf-sdk-api:8200/location-retrieval/v0/retrieve         │
│       ?core=coresim                                                 │
│                                                                     │
│  Headers: { "x-correlator": "uuid", "Content-Type": "json" }        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 5: CAMARA Location Router (camara_location.py)                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  @router.post("/retrieve")                                          │
│  async def retrieve_location():                                     │
│      # Validate device identifier                                   │
│      if not request_data.device:                                    │
│          return error(422, "MISSING_IDENTIFIER")                    │
│                                                                     │
│      # Build SDK request                                            │
│      location_request = SDKLocationRequest(                         │
│          device=sdk_device,                                         │
│          maxAge=request_data.maxAge                                 │
│      )                                                              │
│                                                                     │
│      # Call SDK                                                     │
│      location_response = client.create_monitoring_event_subscription│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 6: TF-SDK Network Client (base_network_client.py)              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  def create_monitoring_event_subscription():                        │
│      # Build 3GPP subscription                                      │
│      subscription = _build_monitoring_event_subscription(request)   │
│                                                                     │
│      # Transform CAMARA → 3GPP format                               │
│      subscription_3gpp.externalId = device.networkAccessIdentifier  │
│      subscription_3gpp.ipv4Addr = device.ipv4Address.publicAddress  │
│                                                                     │
│      # POST to NEF                                                  │
│      response = common.monitoring_event_post(                       │
│          base_url,    # http://localhost:8102                       │
│          scs_as_id,   # "nef"                                       │
│          subscription                                               │
│      )                                                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 7: HTTP to NEF (common.py)                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  URL: http://localhost:8102/3gpp-monitoring-event/v1/nef/subscriptions
│  Method: POST                                                       │
│  Body: {                                                            │
│    "externalId": "nef:imsi-001010000000001",                        │
│    "monitoringType": "LOCATION_REPORTING",                          │
│    "maximumNumberOfReports": 1,                                     │
│    "notificationDestination": "http://callback.example.com"         │
│  }                                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 8: NEF monitoring-event Service (Go)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PostMonitoringEventSubscription(afId, data):                       │
│                                                                     │
│  1. Parse externalId → "nef:imsi-001010000000001"                   │
│                                                                     │
│  2. LookupExternalId(afId, externalId)                              │
│     → Calls ue-identity-service                                     │
│     → Returns SUPI: "imsi-001010000000001"                          │
│                                                                     │
│  3. QueryUEInfo(supi)                                               │
│     → Queries Redis for UE state                                    │
│     → Returns location (NCGI cell ID)                               │
│                                                                     │
│  4. prepareImmediateReport(externalId, LOCATION_REPORTING, ue)      │
│     → Generates geographic area from cell ID                        │
│     → Returns MonitoringEventReport with polygon                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 9: Response Transformation (base_network_client.py)            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  # Parse 3GPP response                                              │
│  monitoring_event_report = MonitoringEventReport(**response)        │
│                                                                     │
│  # Extract geographic area                                          │
│  geo_area = monitoring_event_report.locationInfo.geographicArea     │
│                                                                     │
│  # Convert to CAMARA polygon                                        │
│  camara_point_list = []                                             │
│  for point in geo_area.polygon.point_list:                          │
│      camara_point_list.append(Point(                                │
│          latitude=point.lat,                                        │
│          longitude=point.lon                                        │
│      ))                                                             │
│                                                                     │
│  # Build CAMARA Location response                                   │
│  return Location(                                                   │
│      area=Polygon(boundary=camara_point_list),                      │
│      lastLocationTime=last_location_time                            │
│  )                                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 10: Final Response to Client                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  HTTP 200 OK                                                        │
│  Headers: { "x-correlator": "original-uuid" }                       │
│  Body: {                                                            │
│    "lastLocationTime": "2025-12-17T10:30:00.000Z",                  │
│    "area": {                                                        │
│      "areaType": "POLYGON",                                         │
│      "boundary": [                                                  │
│        {"latitude": 48.8576, "longitude": 2.3532},                  │
│        {"latitude": 48.8576, "longitude": 2.3512},                  │
│        {"latitude": 48.8556, "longitude": 2.3512},                  │
│        {"latitude": 48.8556, "longitude": 2.3532}                   │
│      ]                                                              │
│    }                                                                │
│  }                                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Models

### 4.1 Request Models

#### RetrievalLocationRequest
```python
class RetrievalLocationRequest(BaseModel):
    device: Device              # Required - device identifier
    maxAge: Optional[int]       # Max age of location data (seconds)
    maxSurface: Optional[int]   # Max area size (square meters)
```

#### Device
```python
class Device(BaseModel):
    phoneNumber: Optional[str]              # E.164 format: +1234567890
    networkAccessIdentifier: Optional[str]  # NAI: user@realm
    ipv4Address: Optional[DeviceIpv4Addr]   # IPv4 with optional port
    ipv6Address: Optional[str]              # IPv6 address
```

#### DeviceIpv4Addr
```python
class DeviceIpv4Addr(BaseModel):
    publicAddress: str                # Required: public IPv4
    privateAddress: Optional[str]     # Private IPv4 (NAT)
    publicPort: Optional[int]         # Port 0-65535
```

### 4.2 Response Models

#### Location
```python
class Location(BaseModel):
    lastLocationTime: str    # ISO 8601 timestamp
    area: Area               # Circle or Polygon
    device: Optional[Device] # Echo of input device
```

#### Circle
```python
class Circle(BaseModel):
    areaType: Literal["CIRCLE"] = "CIRCLE"
    center: Point           # Center coordinates
    radius: float           # Radius in meters (≥1)
```

#### Polygon
```python
class Polygon(BaseModel):
    areaType: Literal["POLYGON"] = "POLYGON"
    boundary: List[Point]   # 3-15 points defining boundary
```

#### Point
```python
class Point(BaseModel):
    latitude: float    # -90 to 90
    longitude: float   # -180 to 180
```

### 4.3 Data Transformation

```
CAMARA Request                    3GPP Request
─────────────────────────────────────────────────────────────────
{                                 {
  "device": {                       "externalId": "nef:imsi-...",
    "networkAccessIdentifier":      "monitoringType": 
      "imsi-001010000000001"          "LOCATION_REPORTING",
  },                                "maximumNumberOfReports": 1,
  "maxAge": 60                      "notificationDestination":
}                                     "http://callback.example"
                                  }


3GPP Response                     CAMARA Response
─────────────────────────────────────────────────────────────────
{                                 {
  "monitoringType":                 "lastLocationTime": 
    "LOCATION_REPORTING",             "2025-12-17T10:30:00Z",
  "eventTime": "2025-...",          "area": {
  "locationInfo": {                   "areaType": "POLYGON",
    "geographicArea": {               "boundary": [
      "shape": "POLYGON",               {"latitude": 48.8576,
      "pointList": [                     "longitude": 2.3532},
        {"lat": 48.8576,                ...
         "lon": 2.3532},              ]
        ...                         }
      ]                           }
    },
    "ageOfLocationInfo": {
      "duration": 5
    }
  }
}
```

---

## 5. API Endpoint

### POST /location-retrieval/v0/retrieve

| Property | Value |
|----------|-------|
| Method | POST |
| Path | `/location-retrieval/v0/retrieve` |
| Content-Type | `application/json` |
| Success Status | 200 OK |

#### Request Headers

| Header | Required | Description |
|--------|----------|-------------|
| Content-Type | Yes | `application/json` |
| x-correlator | No | UUID for request tracing |
| Authorization | No* | Bearer token (production) |

#### Request Body

```json
{
  "device": {
    "ipv4Address": {
      "publicAddress": "12.1.0.1"
    }
  },
  "maxAge": 60,
  "maxSurface": 10000
}
```

#### Response Headers

| Header | Description |
|--------|-------------|
| x-correlator | Same as request or auto-generated |
| Content-Type | `application/json` |

#### Response Body (200 OK)

```json
{
  "lastLocationTime": "2025-12-17T10:30:00.000Z",
  "area": {
    "areaType": "CIRCLE",
    "center": {
      "latitude": 45.754114,
      "longitude": 4.860374
    },
    "radius": 150.0
  },
  "device": {
    "ipv4Address": {
      "publicAddress": "12.1.0.1"
    }
  }
}
```

---

## 6. Error Handling

### Error Response Format

```json
{
  "status": 404,
  "code": "DEVICE_NOT_FOUND",
  "message": "Device not registered or no active PDU session"
}
```

### Error Codes

| HTTP | Code | When |
|------|------|------|
| 400 | INVALID_ARGUMENT | Malformed request |
| 401 | UNAUTHENTICATED | Missing/invalid auth |
| 403 | PERMISSION_DENIED | Not authorized |
| 404 | DEVICE_NOT_FOUND | UE not in network |
| 422 | MISSING_IDENTIFIER | No device in request |
| 422 | DEVICE_UNIDENTIFIABLE | No valid identifier |
| 500 | INTERNAL | Server error |
| 503 | SERVICE_UNAVAILABLE | NEF unavailable |

### Error Mapping in Code

```python
# camara_location.py
if ("not found" in error_msg.lower() or 
    "redis: nil" in error_msg.lower()):
    return camara_error_response(
        404, "DEVICE_NOT_FOUND",
        "Device not registered or no active PDU session",
        correlator
    )
```

---

## 7. Call Flow Diagrams

### Flow 1: Successful Location Retrieval

```
┌────────┐     ┌─────────┐     ┌─────────┐     ┌───────┐     ┌───────┐
│  App   │     │ TF-SDK  │     │   NEF   │     │ UE-ID │     │ Redis │
└───┬────┘     └────┬────┘     └────┬────┘     └───┬───┘     └───┬───┘
    │               │               │              │             │
    │ POST /retrieve│               │              │             │
    │ {device: IP}  │               │              │             │
    │──────────────►│               │              │             │
    │               │               │              │             │
    │               │ POST /3gpp-   │              │             │
    │               │ monitoring... │              │             │
    │               │──────────────►│              │             │
    │               │               │              │             │
    │               │               │ Lookup IP    │             │
    │               │               │─────────────►│             │
    │               │               │              │             │
    │               │               │   SUPI       │             │
    │               │               │◄─────────────│             │
    │               │               │              │             │
    │               │               │ Query UE     │             │
    │               │               │─────────────────────────►│
    │               │               │              │             │
    │               │               │ Location Data│             │
    │               │               │◄─────────────────────────│
    │               │               │              │             │
    │               │ 200 OK        │              │             │
    │               │ {locationInfo}│              │             │
    │               │◄──────────────│              │             │
    │               │               │              │             │
    │ 200 OK        │               │              │             │
    │ {area: POLYGON│               │              │             │
    │  lastLocation}│               │              │             │
    │◄──────────────│               │              │             │
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
    │               │ monitoring... │              │
    │               │──────────────►│              │
    │               │               │              │
    │               │               │ Query UE     │
    │               │               │─────────────►│
    │               │               │              │
    │               │               │ redis: nil   │
    │               │               │◄─────────────│
    │               │               │              │
    │               │ 404 Not Found │              │
    │               │◄──────────────│              │
    │               │               │              │
    │ 404 Error     │               │              │
    │ {code: DEVICE │               │              │
    │  _NOT_FOUND}  │               │              │
    │◄──────────────│               │              │
```

### Flow 3: Missing Device Identifier

```
┌────────┐     ┌─────────┐
│  App   │     │ TF-SDK  │
└───┬────┘     └────┬────┘
    │               │
    │ POST /retrieve│
    │ {}  (no device)
    │──────────────►│
    │               │
    │               │ Validation
    │               │ fails
    │               │
    │ 422 Error     │
    │ {code: MISSING│
    │  _IDENTIFIER} │
    │◄──────────────│
```

---

## 8. Example Requests

### 8.1 Location by IPv4 Address

**Request:**
```http
POST /location-retrieval/v0/retrieve?core=coresim HTTP/1.1
Host: localhost:8200
Content-Type: application/json
x-correlator: 550e8400-e29b-41d4-a716-446655440000

{
  "device": {
    "ipv4Address": {
      "publicAddress": "12.1.0.1"
    }
  },
  "maxAge": 60
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json
x-correlator: 550e8400-e29b-41d4-a716-446655440000

{
  "lastLocationTime": "2025-12-17T10:30:00.000Z",
  "area": {
    "areaType": "CIRCLE",
    "center": {
      "latitude": 45.754114,
      "longitude": 4.860374
    },
    "radius": 150.0
  },
  "device": {
    "ipv4Address": {
      "publicAddress": "12.1.0.1"
    }
  }
}
```

### 8.2 Location by Network Access Identifier

**Request:**
```http
POST /location-retrieval/v0/retrieve?core=coresim HTTP/1.1
Host: localhost:8200
Content-Type: application/json
x-correlator: 550e8400-e29b-41d4-a716-446655440001

{
  "device": {
    "networkAccessIdentifier": "imsi-001010000000001"
  },
  "maxAge": 120,
  "maxSurface": 50000
}
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json
x-correlator: 550e8400-e29b-41d4-a716-446655440001

{
  "lastLocationTime": "2025-12-17T10:32:15.000Z",
  "area": {
    "areaType": "POLYGON",
    "boundary": [
      {"latitude": 48.8576, "longitude": 2.3532},
      {"latitude": 48.8576, "longitude": 2.3512},
      {"latitude": 48.8556, "longitude": 2.3512},
      {"latitude": 48.8556, "longitude": 2.3532}
    ]
  },
  "device": {
    "networkAccessIdentifier": "imsi-001010000000001"
  }
}
```

### 8.3 Location by Phone Number

**Request:**
```http
POST /location-retrieval/v0/retrieve?core=coresim HTTP/1.1
Host: localhost:8200
Content-Type: application/json
x-correlator: 550e8400-e29b-41d4-a716-446655440002

{
  "device": {
    "phoneNumber": "+33612345678"
  }
}
```

### 8.4 Error Response - Device Not Found

**Request:**
```http
POST /location-retrieval/v0/retrieve?core=coresim HTTP/1.1
Host: localhost:8200
Content-Type: application/json

{
  "device": {
    "ipv4Address": {
      "publicAddress": "999.999.999.999"
    }
  }
}
```

**Response:**
```http
HTTP/1.1 404 Not Found
Content-Type: application/json
x-correlator: auto-generated-uuid

{
  "status": 404,
  "code": "DEVICE_NOT_FOUND",
  "message": "Device not registered or no active PDU session"
}
```

### 8.5 Error Response - Missing Identifier

**Request:**
```http
POST /location-retrieval/v0/retrieve?core=coresim HTTP/1.1
Host: localhost:8200
Content-Type: application/json

{
  "maxAge": 60
}
```

**Response:**
```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json
x-correlator: auto-generated-uuid

{
  "status": 422,
  "code": "MISSING_IDENTIFIER",
  "message": "Device identifier is required"
}
```

---

## Appendix: Area Types

### Circle vs Polygon

| Type | Use Case | Structure |
|------|----------|-----------|
| **CIRCLE** | Simple approximation | center + radius |
| **POLYGON** | Complex boundaries | 3-15 boundary points |

### maxSurface Parameter

Controls the maximum area size returned:

| maxSurface | Typical Result |
|------------|----------------|
| < 10,000 m² | Small circle (~50-100m radius) |
| 10,000-100,000 m² | Medium circle or polygon |
| > 100,000 m² | Large polygon |
| Not specified | Network decides |

### Privacy Considerations

- Location is always an **area**, never an exact point
- Minimum radius enforced (typically 50m)
- User consent required (handled by authorization)

---

*Documentation generated: December 17, 2025*
