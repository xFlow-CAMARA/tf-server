# CAMARA Quality-on-Demand (QoD) API - Overview

## What is QoD?

**Quality on Demand (QoD)** allows applications to request guaranteed network quality (bandwidth, latency) for specific connections between a device and an application server.

**Use Cases:**
- Video streaming requiring stable 4K bandwidth
- Gaming needing low latency
- Video conferencing with guaranteed quality
- Industrial IoT with reliability requirements

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                            │
│                                                                      │
│   ┌──────────────┐                                                  │
│   │   Web App    │  User clicks "Create QoD Session"                │
│   │  (Browser)   │                                                  │
│   └──────┬───────┘                                                  │
│          │                                                          │
└──────────┼──────────────────────────────────────────────────────────┘
           │ HTTP
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY LAYER                            │
│                                                                      │
│   ┌──────────────┐      ┌──────────────┐                           │
│   │   Next.js    │ ───► │   TF-SDK     │  CAMARA API Server        │
│   │   Frontend   │      │   (Python)   │  Port 8200                │
│   │   Port 3002  │      │              │                           │
│   └──────────────┘      └──────┬───────┘                           │
│                                │                                    │
└────────────────────────────────┼────────────────────────────────────┘
                                 │ HTTP (3GPP API)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    NETWORK EXPOSURE LAYER (NEF)                      │
│                                                                      │
│   ┌──────────────┐                                                  │
│   │  as-session  │  3GPP TS 29.122 API                             │
│   │  -with-qos   │  Port 8100                                      │
│   │    (Go)      │                                                  │
│   └──────┬───────┘                                                  │
│          │                                                          │
└──────────┼──────────────────────────────────────────────────────────┘
           │ HTTP (3GPP TS 29.514)
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         5G CORE NETWORK                              │
│                                                                      │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────┐     │
│   │     PCF      │ ───► │     SMF      │ ───► │     UPF      │     │
│   │   (Policy)   │      │  (Session)   │      │ (User Plane) │     │
│   └──────────────┘      └──────────────┘      └──────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Components Explained

### 1. CAMARA API (Application-Facing)
- **Standard**: CAMARA QoD v1.1.0
- **Purpose**: Simple, developer-friendly API
- **Format**: RESTful JSON

### 2. NEF (Network Exposure Function)
- **Standard**: 3GPP TS 29.122/29.522
- **Purpose**: Translates CAMARA requests to 5G core format
- **Role**: Bridge between IT world and Telecom world

### 3. PCF (Policy Control Function)
- **Standard**: 3GPP TS 29.514
- **Purpose**: Enforces QoS policies in the network
- **Role**: Tells SMF what QoS to apply

### 4. SMF/UPF (Session/User Plane)
- **Purpose**: Actually applies QoS rules to traffic
- **Role**: Packet prioritization, bandwidth allocation

---

## Call Flow Diagrams

### Flow 1: Create QoD Session (Success)

```
┌────────┐     ┌─────────┐     ┌─────────┐     ┌─────┐     ┌─────┐
│  App   │     │ TF-SDK  │     │   NEF   │     │ PCF │     │ SMF │
└───┬────┘     └────┬────┘     └────┬────┘     └──┬──┘     └──┬──┘
    │               │               │             │           │
    │ POST /sessions│               │             │           │
    │ {device, qos} │               │             │           │
    │──────────────►│               │             │           │
    │               │               │             │           │
    │               │ POST /3gpp-as-│             │           │
    │               │ session-with-qos            │           │
    │               │──────────────►│             │           │
    │               │               │             │           │
    │               │               │ POST /app-  │           │
    │               │               │ sessions    │           │
    │               │               │────────────►│           │
    │               │               │             │           │
    │               │               │             │ Create    │
    │               │               │             │ QoS Flow  │
    │               │               │             │──────────►│
    │               │               │             │           │
    │               │               │             │    OK     │
    │               │               │             │◄──────────│
    │               │               │             │           │
    │               │               │ 201 Created │           │
    │               │               │◄────────────│           │
    │               │               │             │           │
    │               │ 201 Created   │             │           │
    │               │◄──────────────│             │           │
    │               │               │             │           │
    │ 201 Created   │               │             │           │
    │ {sessionId,   │               │             │           │
    │  qosStatus:   │               │             │           │
    │  AVAILABLE}   │               │             │           │
    │◄──────────────│               │             │           │
    │               │               │             │           │
```

### Flow 2: Create Session (Device Not Found)

```
┌────────┐     ┌─────────┐     ┌─────────┐     ┌─────┐
│  App   │     │ TF-SDK  │     │   NEF   │     │ PCF │
└───┬────┘     └────┬────┘     └────┬────┘     └──┬──┘
    │               │               │             │
    │ POST /sessions│               │             │
    │ {device: bad} │               │             │
    │──────────────►│               │             │
    │               │               │             │
    │               │ POST /3gpp-   │             │
    │               │──────────────►│             │
    │               │               │             │
    │               │               │ POST /app-  │
    │               │               │ sessions    │
    │               │               │────────────►│
    │               │               │             │
    │               │               │ 404 UE Not  │
    │               │               │ Found       │
    │               │               │◄────────────│
    │               │               │             │
    │               │ 404 Error     │             │
    │               │◄──────────────│             │
    │               │               │             │
    │ 404 Error     │               │             │
    │ {status: 404, │               │             │
    │  code: DEVICE │               │             │
    │  _NOT_FOUND}  │               │             │
    │◄──────────────│               │             │
    │               │               │             │
```

### Flow 3: Delete QoD Session

```
┌────────┐     ┌─────────┐     ┌─────────┐     ┌─────┐     ┌─────┐
│  App   │     │ TF-SDK  │     │   NEF   │     │ PCF │     │ SMF │
└───┬────┘     └────┬────┘     └────┬────┘     └──┬──┘     └──┬──┘
    │               │               │             │           │
    │ DELETE        │               │             │           │
    │ /sessions/123 │               │             │           │
    │──────────────►│               │             │           │
    │               │               │             │           │
    │               │ DELETE /3gpp- │             │           │
    │               │ .../subs/123  │             │           │
    │               │──────────────►│             │           │
    │               │               │             │           │
    │               │               │ DELETE /app-│           │
    │               │               │ sessions/X  │           │
    │               │               │────────────►│           │
    │               │               │             │           │
    │               │               │             │ Remove    │
    │               │               │             │ QoS Flow  │
    │               │               │             │──────────►│
    │               │               │             │           │
    │               │               │             │    OK     │
    │               │               │             │◄──────────│
    │               │               │             │           │
    │               │               │ 204 No      │           │
    │               │               │ Content     │           │
    │               │               │◄────────────│           │
    │               │               │             │           │
    │               │ 204 No Content│             │           │
    │               │◄──────────────│             │           │
    │               │               │             │           │
    │ 204 No Content│               │             │           │
    │◄──────────────│               │             │           │
    │               │               │             │           │
```

### Flow 4: Get Session Status

```
┌────────┐     ┌─────────┐     ┌─────────┐
│  App   │     │ TF-SDK  │     │   NEF   │
└───┬────┘     └────┬────┘     └────┬────┘
    │               │               │
    │ GET           │               │
    │ /sessions/123 │               │
    │──────────────►│               │
    │               │               │
    │               │ GET /3gpp-    │
    │               │ .../subs/123  │
    │               │──────────────►│
    │               │               │
    │               │ 200 OK        │
    │               │ {subscription}│
    │               │◄──────────────│
    │               │               │
    │ 200 OK        │               │
    │ {sessionId,   │               │
    │  qosStatus:   │               │
    │  AVAILABLE,   │               │
    │  expiresAt}   │               │
    │◄──────────────│               │
    │               │               │
```

---

## Data Transformation

### CAMARA Request (Simple)
```json
{
  "device": {
    "ipv4Address": {
      "publicAddress": "12.1.0.1"
    }
  },
  "applicationServer": {
    "ipv4Address": "10.0.0.1"
  },
  "qosProfile": "qos-e",
  "duration": 3600
}
```

### ↓ Transformed to 3GPP Format (Complex)

```json
{
  "ueIpv4Addr": "12.1.0.1",
  "notificationDestination": "https://callback.example.com",
  "qosReference": "qos-e",
  "usageThreshold": {
    "duration": 3600
  },
  "flowInfo": [{
    "flowId": 1,
    "flowDescriptions": [
      "permit in ip from 12.1.0.1 to 10.0.0.1",
      "permit out ip from 10.0.0.1 to 12.1.0.1"
    ]
  }],
  "dnn": "internet",
  "snssai": {"sst": 1, "sd": "010203"}
}
```

### ↓ Transformed to PCF Format (Internal)

```json
{
  "ascReqData": {
    "afAppId": "nef",
    "ueIpv4": "12.1.0.1",
    "notifUri": "https://callback.example.com",
    "medComponents": {
      "1": {
        "medCompN": 1,
        "fStatus": "ENABLED",
        "marBwDl": "120 Kbps",
        "marBwUl": "120 Kbps",
        "medType": "VIDEO"
      }
    }
  }
}
```

---

## QoS Profiles

| Profile | Use Case | Downlink | Uplink | 5QI |
|---------|----------|----------|--------|-----|
| qos-e | Basic streaming | 120 Kbps | 120 Kbps | 9 |
| qos2 | HD Video | 240 Kbps | 240 Kbps | 8 |
| qos3 | 4K Video | 480 Kbps | 480 Kbps | 7 |

---

## Session States

```
                    ┌─────────────┐
         POST       │             │
        /sessions   │  REQUESTED  │
       ────────────►│             │
                    └──────┬──────┘
                           │ PCF accepts
                           ▼
                    ┌─────────────┐
                    │             │
                    │  AVAILABLE  │◄──────┐
                    │             │       │ extend
                    └──────┬──────┘───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
       ┌───────────┐ ┌───────────┐ ┌───────────┐
       │  DURATION │ │  NETWORK  │ │  DELETE   │
       │  EXPIRED  │ │ TERMINATED│ │ REQUESTED │
       └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
             │             │             │
             └─────────────┼─────────────┘
                           ▼
                    ┌─────────────┐
                    │             │
                    │ UNAVAILABLE │
                    │             │
                    └─────────────┘
```

---

## HTTP Status Codes

| Operation | Success | Common Errors |
|-----------|---------|---------------|
| POST /sessions | 201 Created | 400, 404, 503 |
| GET /sessions/{id} | 200 OK | 404 |
| DELETE /sessions/{id} | 204 No Content | 404 |
| POST /sessions/{id}/extend | 200 OK | 404, 409 |

---

## Error Response Format

All errors follow CAMARA format:
```json
{
  "status": 404,
  "code": "DEVICE_NOT_FOUND",
  "message": "Device not registered or no active PDU session"
}
```

---

## x-correlator Header

Every request/response includes `x-correlator` for tracing:

```
Request:  x-correlator: abc123-def456-...
Response: x-correlator: abc123-def456-...
```

This allows tracking a request across all system components.

---

## Summary

1. **App** sends simple CAMARA request
2. **TF-SDK** validates and transforms to 3GPP format
3. **NEF** processes and calls PCF
4. **PCF** creates policy in 5G Core
5. **SMF/UPF** apply actual QoS to traffic
6. Response flows back with session ID

The complexity of 5G standards is hidden behind the simple CAMARA API.
