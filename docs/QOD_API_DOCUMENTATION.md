# CAMARA Quality-on-Demand (QoD) API v1.1.0 - Complete Request Traceback

**Version:** 1.1.0  
**Date:** December 17, 2025  
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Complete Request Flow](#3-complete-request-flow)
4. [Component Details](#4-component-details)
5. [Data Models](#5-data-models)
6. [API Endpoints](#6-api-endpoints)
7. [Error Handling](#7-error-handling)
8. [Headers](#8-headers)
9. [Example Requests](#9-example-requests)

---

## 1. Overview

The QoD API allows applications to request specific Quality of Service (QoS) for network connections. It follows the CAMARA specification v1.1.0 and is implemented as a multi-layer system spanning:

- **Frontend Dashboard** (Next.js) → Port 3002
- **Next.js API Routes** → Internal middleware
- **TF-SDK Backend Adapter** → HTTP client to Python backend
- **TF-SDK Python API Server** (FastAPI) → Port 8200
- **TF-SDK Network Client** (Python SDK) → SDK library
- **NEF as-session-with-qos** (Go) → Port 8100
- **PCF (Policy Control Function)** → 5G Core

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    CAMARA Dashboard (Next.js)                            │   │
│  │                    http://localhost:3002                                 │   │
│  │                                                                          │   │
│  │  QodPanel.tsx                                                            │   │
│  │  ├── Form inputs: deviceIp, appServerIp, qosProfile, duration           │   │
│  │  └── Calls: apiClient.createQodSession(payload)                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │ HTTP POST /api/qod
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND API LAYER                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  api-client.ts                                                          │   │
│  │  ├── Adds x-correlator header (UUID)                                    │   │
│  │  ├── Sets timeout (10s)                                                 │   │
│  │  └── Handles CAMARA error format                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  app/api/qod/route.ts (Next.js API Route)                               │   │
│  │  ├── Extracts x-correlator from request                                 │   │
│  │  ├── Validates applicationServer.ipv4Address required                   │   │
│  │  ├── Normalizes device structure                                        │   │
│  │  ├── Calls adapter.createQodSession()                                   │   │
│  │  └── Returns 201 Created with x-correlator header                       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  lib/adapters/base-tfsdk.ts (Backend Adapter)                           │   │
│  │  ├── Axios client to TF-SDK (http://tf-sdk-api:8200)                    │   │
│  │  ├── Adds x-correlator header                                           │   │
│  │  ├── Normalizes device with normalizeDevice()                           │   │
│  │  └── POST /quality-on-demand/v1/sessions?core=coresim                   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │ HTTP POST to TF-SDK
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        TF-SDK PYTHON BACKEND                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  api_server.py (FastAPI) - Port 8200                                    │   │
│  │  ├── Initializes network_clients dict                                   │   │
│  │  ├── init_network_client("coresim")                                     │   │
│  │  │   └── Creates sdkclient with adapter_specs:                          │   │
│  │  │       ├── base_url: http://localhost:8080 (CoreSim)                  │   │
│  │  │       ├── qod_base_url: http://localhost:8100 (NEF QoD)              │   │
│  │  │       ├── redis_addr: localhost:6380                                 │   │
│  │  │       └── scs_as_id: "nef"                                           │   │
│  │  └── Shares network_clients with camara_qod module                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  camara_qod.py (CAMARA QoD Router)                                      │   │
│  │  POST /quality-on-demand/v1/sessions                                    │   │
│  │                                                                          │   │
│  │  1. Extract x-correlator (or generate UUID)                             │   │
│  │  2. Parse JSON body → CreateSession model                               │   │
│  │  3. Get network client for core (coresim)                               │   │
│  │  4. Build session_info dict:                                            │   │
│  │     {                                                                    │   │
│  │       "duration": 3600,                                                 │   │
│  │       "qosProfile": "qos-e",                                            │   │
│  │       "applicationServer": {"ipv4Address": "10.0.0.1"},                 │   │
│  │       "sink": "https://example.com/notifications",                      │   │
│  │       "device": {                                                       │   │
│  │         "ipv4Address": {                                                │   │
│  │           "publicAddress": "12.1.0.1",                                  │   │
│  │           "privateAddress": "12.1.0.1"  ← defaults to public            │   │
│  │         }                                                               │   │
│  │       }                                                                 │   │
│  │     }                                                                    │   │
│  │  5. Call client.create_qod_session(session_info)                        │   │
│  │  6. Create SessionInfo response                                         │   │
│  │  7. Store in qod_sessions dict                                          │   │
│  │  8. Return JSONResponse(status=201, headers={"x-correlator": ...})      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │ Python SDK call
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      TF-SDK PYTHON NETWORK CLIENT                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  sunrise6g_opensdk/network/core/base_network_client.py                  │   │
│  │                                                                          │   │
│  │  create_qod_session(session_info: Dict) → Dict                          │   │
│  │  ├── _build_qod_subscription(session_info)                              │   │
│  │  │   ├── Validates via schemas.CreateSession.model_validate()           │   │
│  │  │   ├── Extracts device_ipv4 from nested Pydantic models               │   │
│  │  │   ├── Calls core_specific_qod_validation()                           │   │
│  │  │   └── Creates AsSessionWithQoSSubscription:                          │   │
│  │  │       {                                                              │   │
│  │  │         "notificationDestination": "https://...",                    │   │
│  │  │         "qosReference": "qos-e",                                     │   │
│  │  │         "ueIpv4Addr": "12.1.0.1",                                    │   │
│  │  │         "usageThreshold": {"duration": 3600}                         │   │
│  │  │       }                                                              │   │
│  │  │                                                                       │   │
│  │  └── common.as_session_with_qos_post(base_url, scs_as_id, subscription) │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                     │                                            │
│                                     ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  sunrise6g_opensdk/network/core/common.py                               │   │
│  │                                                                          │   │
│  │  as_session_with_qos_post(base_url, scs_as_id, model_payload)           │   │
│  │  ├── URL: {base_url}/3gpp-as-session-with-qos/v1/{scs_as_id}/subscriptions│ │
│  │  │   → http://localhost:8100/3gpp-as-session-with-qos/v1/nef/subscriptions│ │
│  │  ├── Method: POST                                                        │   │
│  │  ├── Headers: {"Content-Type": "application/json", "accept": "..."}     │   │
│  │  ├── Body: model_payload.model_dump_json(exclude_none=True, by_alias=True)│  │
│  │  └── Returns: response.json()                                           │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │ HTTP POST (3GPP TS 29.122/522)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          NEF as-session-with-qos                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  Go Service - Port 8100                                                  │   │
│  │  Path: /3gpp-as-session-with-qos/v1/{scsAsId}/subscriptions             │   │
│  │                                                                          │   │
│  │  internal/northbound/api_as_session_controller.go                       │   │
│  │  ├── CreateASSessionWithQoSSubscription handler                         │   │
│  │  └── Calls service.PostSessionWithQoSSubscription()                     │   │
│  │                                                                          │   │
│  │  internal/northbound/service/as_session_service.go                      │   │
│  │  PostSessionWithQoSSubscription(afId, data):                            │   │
│  │  1. Get/create AF context                                               │   │
│  │  2. Validate: UeIpv4Addr OR Gpsi OR UeIpv6Addr required                 │   │
│  │  3. sessionWithQoS2PolicyAuthz() → Convert to PCF format:               │   │
│  │     AppSessionContextReqData {                                          │   │
│  │       AfAppId: "nef",                                                   │   │
│  │       UeIpv4: "12.1.0.1",                                               │   │
│  │       NotifUri: "https://example.com/notifications",                    │   │
│  │       Dnn: "internet",                                                  │   │
│  │       SliceInfo: {Sst: 1, Sd: "010203"},                                │   │
│  │       QosDuration: 3600,                                                │   │
│  │       MedComponents: {                                                  │   │
│  │         "1": {                                                          │   │
│  │           MedCompN: 1,                                                  │   │
│  │           FStatus: "ENABLED",                                           │   │
│  │           MarBwDl: "120 Kbps",  ← from QoS config                       │   │
│  │           MarBwUl: "120 Kbps",                                          │   │
│  │           MedType: "VIDEO",                                             │   │
│  │           MedSubComps: {flow descriptors}                               │   │
│  │         }                                                               │   │
│  │       }                                                                 │   │
│  │     }                                                                    │   │
│  │  4. connector.CreatePolicyAuthzSubscription() → HTTP to PCF            │   │
│  │  5. Store subscription in AF context                                    │   │
│  │  6. Return 201 Created with location header                             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │ HTTP POST (3GPP TS 29.514)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PCF (Policy Control Function)                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  5G Core Component (CoreSim simulated / OAI real)                       │   │
│  │                                                                          │   │
│  │  Npcf_PolicyAuthorization_Create API                                    │   │
│  │  ├── Validates UE exists and has active PDU session                     │   │
│  │  ├── Creates Policy Authorization context                               │   │
│  │  ├── Allocates QoS resources (GBR, MBR, 5QI)                            │   │
│  │  └── Returns AppSessionId                                               │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Complete Request Flow

### 3.1 Create QoD Session - Step by Step

#### Step 1: User Interaction (QodPanel.tsx)

**File:** `/home/xflow/camara-dashboard/src/components/QodPanel.tsx`

```typescript
// User fills form and clicks submit
const handleSubmit = async (e: React.FormEvent) => {
  const reqPayload = {
    device: {
      ipv4Address: {
        publicAddress: formData.deviceIp,  // e.g., "12.1.0.1"
      },
    },
    applicationServer: {
      ipv4Address: formData.appServerIp,   // e.g., "10.0.0.1"
    },
    qosProfile: formData.qosProfile,       // e.g., "qos-e"
    duration: formData.duration,           // e.g., 3600
  };
  
  const data = await apiClient.createQodSession(reqPayload);
};
```

#### Step 2: API Client (api-client.ts)

**File:** `/home/xflow/camara-dashboard/src/lib/api-client.ts`

```typescript
async createQodSession(data: any): Promise<any> {
  return this.request<any>('/api/qod', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

private async request<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  // Auto-generate x-correlator if not present
  const headers = new Headers(fetchOptions.headers);
  if (!headers.has('x-correlator')) {
    headers.set('x-correlator', crypto.randomUUID());
  }
  // ... make request
}
```

#### Step 3: Next.js API Route (route.ts)

**File:** `/home/xflow/camara-dashboard/src/app/api/qod/route.ts`

```typescript
export async function POST(request: NextRequest) {
  const correlator = getCorrelator(request);  // Extract or generate UUID

  const body = await request.json();
  const adapter = getAdapter(body.adapter || 'tfsdk');

  // Validate required fields
  if (!body.applicationServer?.ipv4Address) {
    return errorResponse(400, 'INVALID_ARGUMENT', 
      'applicationServer.ipv4Address is required', correlator);
  }

  // Normalize device structure
  const normalizedDevice = normalizeDevice(body.device);

  const result = await adapter.createQodSession({
    device: normalizedDevice,
    applicationServer: body.applicationServer,
    qosProfile: body.qosProfile || 'qos-e',
    duration: body.duration || 3600,
    // ...
  });

  // Return 201 Created per CAMARA spec
  return NextResponse.json(result, {
    status: 201,
    headers: { 'x-correlator': correlator },
  });
}
```

#### Step 4: Backend Adapter (base-tfsdk.ts)

**File:** `/home/xflow/camara-dashboard/src/lib/adapters/base-tfsdk.ts`

```typescript
async createQodSession(request: QodSession): Promise<QodSessionResponse> {
  const payload: any = {
    duration: request.duration,
    qosProfile: request.qosProfile,
    applicationServer: request.applicationServer,
  };

  if (request.device) {
    payload.device = normalizeDevice(request.device);
  }

  // HTTP POST to TF-SDK Python backend
  const response = await this.client.post(
    `/quality-on-demand/v1/sessions?core=${this.coreName}`,  // ?core=coresim
    payload,
    { headers: this.getHeaders() }  // includes x-correlator
  );
  
  return response.data;
}
```

**Target URL:** `http://tf-sdk-api:8200/quality-on-demand/v1/sessions?core=coresim`

#### Step 5: TF-SDK FastAPI Server (camara_qod.py)

**File:** `/home/xflow/oop/tf-sdk/camara_qod.py`

```python
@router.post("/sessions", status_code=201)
async def create_qod_session(
    raw_request: Request,
    response: Response,
    core: str = "coresim",
    x_correlator: str = Header(None)
):
    correlator = get_correlator(x_correlator)
    response.headers["x-correlator"] = correlator
    
    body = await raw_request.json()
    session_request = CreateSession(**body)
    
    client = get_client(core)  # Gets network_clients["coresim"]
    
    # Build session info with proper device format
    session_info = {
        "duration": session_request.duration,
        "qosProfile": session_request.qosProfile,
        "applicationServer": session_request.applicationServer.model_dump(exclude_none=True),
        "sink": session_request.sink or "https://example.com/notifications",
    }
    
    if session_request.device:
        device_dict = {}
        if session_request.device.ipv4Address:
            ipv4_dict = {
                "publicAddress": session_request.device.ipv4Address.publicAddress,
            }
            # Default privateAddress to publicAddress (NEF requirement)
            if session_request.device.ipv4Address.privateAddress:
                ipv4_dict["privateAddress"] = session_request.device.ipv4Address.privateAddress
            else:
                ipv4_dict["privateAddress"] = session_request.device.ipv4Address.publicAddress
            device_dict["ipv4Address"] = ipv4_dict
        session_info["device"] = device_dict
    
    # Call SDK
    result = client.create_qod_session(session_info)
    
    # Create response
    session_id = str(uuid.uuid4())
    session_data = SessionInfo(
        sessionId=session_id,
        duration=session_request.duration,
        qosProfile=session_request.qosProfile,
        qosStatus="AVAILABLE",
        startedAt=datetime.utcnow().isoformat() + "Z",
        expiresAt=(datetime.utcnow() + timedelta(seconds=session_request.duration)).isoformat() + "Z",
        # ...
    )
    
    qod_sessions[session_id] = session_data
    
    return JSONResponse(
        status_code=201,
        content=session_data.model_dump(exclude_none=True),
        headers={"x-correlator": correlator}
    )
```

#### Step 6: TF-SDK Network Client (base_network_client.py)

**File:** `/home/xflow/oop/tf-sdk/src/sunrise6g_opensdk/network/core/base_network_client.py`

```python
def create_qod_session(self, session_info: Dict) -> Dict:
    """Creates a QoS session based on CAMARA QoD API input."""
    
    # Build 3GPP-compliant subscription
    subscription = self._build_qod_subscription(session_info)
    
    # POST to NEF
    response = common.as_session_with_qos_post(
        self.base_url,    # http://localhost:8100
        self.scs_as_id,   # "nef"
        subscription
    )
    
    subscription_info = schemas.AsSessionWithQoSSubscription(**response)
    
    session_info = schemas.SessionInfo(
        sessionId=schemas.SessionId(uuid.UUID(subscription_info.subscription_id)),
        qosStatus=schemas.QosStatus.REQUESTED,
        **session_info,
    )
    return session_info.model_dump(mode="json", by_alias=True)

def _build_qod_subscription(self, session_info: Dict) -> schemas.AsSessionWithQoSSubscription:
    """Convert CAMARA format to 3GPP TS 29.122 format"""
    
    valid_session_info = schemas.CreateSession.model_validate(session_info)
    
    device_ipv4 = None
    if valid_session_info.device.ipv4Address:
        device_ipv4 = valid_session_info.device.ipv4Address.root.publicAddress.root
    
    subscription = schemas.AsSessionWithQoSSubscription(
        notificationDestination=str(valid_session_info.sink),
        qosReference=valid_session_info.qosProfile.root,
        ueIpv4Addr=device_ipv4,
        usageThreshold=schemas.UsageThreshold(duration=valid_session_info.duration),
    )
    return subscription
```

#### Step 7: HTTP Call to NEF (common.py)

**File:** `/home/xflow/oop/tf-sdk/src/sunrise6g_opensdk/network/core/common.py`

```python
def as_session_with_qos_post(base_url: str, scs_as_id: str, model_payload: BaseModel) -> dict:
    data = model_payload.model_dump_json(exclude_none=True, by_alias=True)
    url = as_session_with_qos_build_url(base_url, scs_as_id)
    return _make_request("POST", url, data=data)

def as_session_with_qos_build_url(base_url: str, scs_as_id: str, session_id: str = None):
    url = f"{base_url}/3gpp-as-session-with-qos/v1/{scs_as_id}/subscriptions"
    # → http://localhost:8100/3gpp-as-session-with-qos/v1/nef/subscriptions
    return url

def _make_request(method: str, url: str, data=None):
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
    }
    response = requests.request(method, url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()
```

**3GPP Request Body (JSON):**
```json
{
  "notificationDestination": "https://example.com/notifications",
  "qosReference": "qos-e",
  "ueIpv4Addr": "12.1.0.1",
  "usageThreshold": {
    "duration": 3600
  }
}
```

#### Step 8: NEF as-session-with-qos Service (Go)

**File:** `/home/xflow/nef/as-session-with-qos/internal/northbound/service/as_session_service.go`

```go
func (s *Service) PostSessionWithQoSSubscription(afId string, data *models.AsSessionWithQoSSubscription) (string, int, error) {
    af := s.Ctx().GetAf(afId)
    if af == nil {
        af = s.Ctx().AddAf(afId)
    }
    
    af.Mu.Lock()
    defer af.Mu.Unlock()
    
    if len(data.UeIpv4Addr) > 0 {
        // Single UE case - send to PCF
        pa_ctx, err := s.sessionWithQoS2PolicyAuthz(afId, data)
        if err == nil {
            loc, err := s.Connector().CreatePolicyAuthzSubscription(*pa_ctx)
            if err != nil {
                return "", http.StatusInternalServerError, 
                    fmt.Errorf("could not create PCF Policy Authorization context")
            }
            tiLoc, subCtx := af.NewAfSubscription(data)
            subCtx.AppSessId = loc
            return tiLoc, http.StatusCreated, nil
        }
    }
    // ...
}

func (s *Service) sessionWithQoS2PolicyAuthz(afId string, data *models.AsSessionWithQoSSubscription) (*pcfclient.AppSessionContext, error) {
    // Convert to PCF format
    req := pcfclient.AppSessionContextReqData{
        AfAppId:   &afId,
        UeIpv4:    pcfclient.PtrString(data.UeIpv4Addr),
        NotifUri:  data.NotificationDestination,
        SuppFeat:  s.Cfg().SupportedFeat,
        Dnn:       pcfclient.PtrString(data.Dnn),
        SliceInfo: &pcfclient.Snssai{Sst: data.Snssai.Sst, Sd: data.Snssai.Sd},
    }
    
    // Build media components with QoS info
    qosInfo := s.Cfg().QosConf[data.QosReference]  // e.g., "qos-e"
    medComponent.SetMarBwDl(qosInfo.MarBwDl)       // "120 Kbps"
    medComponent.SetMarBwUl(qosInfo.MarBwUl)       // "120 Kbps"
    
    ctx := &pcfclient.AppSessionContext{}
    ctx.SetAscReqData(req)
    return ctx, nil
}
```

#### Step 9: PCF Policy Authorization

The NEF calls the PCF using 3GPP TS 29.514 Npcf_PolicyAuthorization API:

**Endpoint:** `POST /npcf-policyauthorization/v1/app-sessions`

**PCF Actions:**
1. Validates UE exists in core network
2. Checks PDU session is active
3. Creates Policy Authorization context
4. Allocates QoS resources based on qosReference
5. Returns AppSessionId

---

## 4. Component Details

### 4.1 Frontend Dashboard

| Property | Value |
|----------|-------|
| Framework | Next.js 14 |
| Port | 3002 |
| Language | TypeScript |
| Key Files | `QodPanel.tsx`, `api-client.ts`, `route.ts` |

### 4.2 TF-SDK Python Backend

| Property | Value |
|----------|-------|
| Framework | FastAPI |
| Port | 8200 |
| Language | Python 3.11+ |
| Key Files | `api_server.py`, `camara_qod.py` |

### 4.3 TF-SDK Python SDK

| Property | Value |
|----------|-------|
| Package | `sunrise6g_opensdk` |
| Key Files | `base_network_client.py`, `common.py`, `schemas.py` |

### 4.4 NEF as-session-with-qos

| Property | Value |
|----------|-------|
| Language | Go 1.21+ |
| Port | 8100 |
| API Standard | 3GPP TS 29.122/29.522 |
| Key Files | `as_session_service.go` |

### 4.5 Configuration

**api_server.py initialization:**
```python
adapter_specs = {
    "network": {
        "client_name": "coresim",
        "base_url": "http://localhost:8080",        # CoreSim SBI
        "scs_as_id": "nef",
        "oam_port": 8081,
        "redis_addr": "localhost:6380",
        "nef_callback_url": "http://localhost:9092/eventsubscriptions",
        "qod_base_url": "http://localhost:8100",    # NEF QoD
        "location_base_url": "http://localhost:8102",
        "ti_base_url": "http://localhost:8101",
    }
}
```

---

## 5. Data Models

### 5.1 CAMARA CreateSession (Input)

```python
class CreateSession(BaseModel):
    device: Optional[Device] = None
    applicationServer: ApplicationServer
    devicePorts: Optional[PortsSpec] = None
    applicationServerPorts: Optional[PortsSpec] = None
    qosProfile: str
    duration: int = Field(..., ge=1)
    sink: Optional[str] = None
    sinkCredential: Optional[SinkCredential] = None
```

### 5.2 Device

```python
class Device(BaseModel):
    phoneNumber: Optional[str] = None
    networkAccessIdentifier: Optional[str] = None
    ipv4Address: Optional[DeviceIpv4Addr] = None
    ipv6Address: Optional[str] = None

class DeviceIpv4Addr(BaseModel):
    publicAddress: str
    privateAddress: Optional[str] = None
    publicPort: Optional[int] = None
```

### 5.3 SessionInfo (Response)

```python
class SessionInfo(BaseModel):
    sessionId: str
    duration: int
    qosProfile: str
    device: Optional[Device] = None
    applicationServer: ApplicationServer
    devicePorts: Optional[PortsSpec] = None
    applicationServerPorts: Optional[PortsSpec] = None
    qosStatus: str                    # REQUESTED | AVAILABLE | UNAVAILABLE
    statusInfo: Optional[str] = None  # DURATION_EXPIRED | NETWORK_TERMINATED | DELETE_REQUESTED
    startedAt: Optional[str] = None   # ISO 8601 timestamp
    expiresAt: Optional[str] = None   # ISO 8601 timestamp
    sink: Optional[str] = None
    sinkCredential: Optional[SinkCredential] = None
```

### 5.4 3GPP AsSessionWithQoSSubscription

```python
class AsSessionWithQoSSubscription(BaseModel):
    notificationDestination: str
    qosReference: str
    ueIpv4Addr: Optional[str] = None
    ueIpv6Addr: Optional[str] = None
    gpsi: Optional[str] = None
    usageThreshold: UsageThreshold
    flowInfo: Optional[List[FlowInfo]] = None
    dnn: Optional[str] = None
    snssai: Optional[Snssai] = None
```

---

## 6. API Endpoints

### 6.1 Create Session

| Property | Value |
|----------|-------|
| Method | POST |
| CAMARA Path | `/quality-on-demand/v1/sessions` |
| 3GPP Path | `/3gpp-as-session-with-qos/v1/{scsAsId}/subscriptions` |
| Success Status | 201 Created |
| Response Headers | `x-correlator`, `Location` |

### 6.2 Get Session

| Property | Value |
|----------|-------|
| Method | GET |
| CAMARA Path | `/quality-on-demand/v1/sessions/{sessionId}` |
| 3GPP Path | `/3gpp-as-session-with-qos/v1/{scsAsId}/subscriptions/{subscriptionId}` |
| Success Status | 200 OK |
| Response Headers | `x-correlator` |

### 6.3 Delete Session

| Property | Value |
|----------|-------|
| Method | DELETE |
| CAMARA Path | `/quality-on-demand/v1/sessions/{sessionId}` |
| 3GPP Path | `/3gpp-as-session-with-qos/v1/{scsAsId}/subscriptions/{subscriptionId}` |
| Success Status | 204 No Content |
| Response Headers | `x-correlator` |

### 6.4 Extend Session

| Property | Value |
|----------|-------|
| Method | POST |
| CAMARA Path | `/quality-on-demand/v1/sessions/{sessionId}/extend` |
| Success Status | 200 OK |
| Request Body | `{"requestedAdditionalDuration": 1800}` |

### 6.5 Retrieve Sessions by Device

| Property | Value |
|----------|-------|
| Method | POST |
| CAMARA Path | `/quality-on-demand/v1/retrieve-sessions` |
| Success Status | 200 OK |
| Request Body | `{"device": {...}}` |

---

## 7. Error Handling

### 7.1 CAMARA Error Response Format

```json
{
  "status": 404,
  "code": "DEVICE_NOT_FOUND",
  "message": "Device not registered or no active PDU session"
}
```

### 7.2 Error Code Mapping

| HTTP Status | CAMARA Code | Description |
|-------------|-------------|-------------|
| 400 | INVALID_ARGUMENT | Invalid request parameters |
| 400 | INVALID_DEVICE_IDENTIFIER | Device identifier format invalid |
| 401 | UNAUTHENTICATED | Missing or invalid authentication |
| 403 | PERMISSION_DENIED | Access denied |
| 404 | NOT_FOUND | Session not found |
| 404 | DEVICE_NOT_FOUND | Device not registered |
| 409 | CONFLICT | Resource conflict |
| 409 | SESSION_EXTENSION_NOT_ALLOWED | Cannot extend inactive session |
| 422 | DEVICE_UNIDENTIFIABLE | No valid device identifier |
| 422 | MISSING_IDENTIFIER | Required identifier missing |
| 429 | TOO_MANY_REQUESTS | Rate limit exceeded |
| 500 | INTERNAL | Internal server error |
| 503 | SERVICE_UNAVAILABLE | Backend service unavailable |

### 7.3 Error Propagation

```
NEF Error → SDK CoreHttpError → camara_qod CAMARA Error → adapter → route.ts → apiClient → UI
```

---

## 8. Headers

### 8.1 x-correlator

**Purpose:** Request/response correlation for distributed tracing

**Flow:**
1. Frontend generates UUID if not present
2. Passed through all layers
3. Returned in every response

```
Request:  x-correlator: 550e8400-e29b-41d4-a716-446655440000
Response: x-correlator: 550e8400-e29b-41d4-a716-446655440000
```

### 8.2 Location Header

Returned on POST (201 Created):
```
Location: /quality-on-demand/v1/sessions/550e8400-e29b-41d4-a716-446655440000
```

---

## 9. Example Requests

### 9.1 Create Session - Full Example

**Request:**
```http
POST /api/qod HTTP/1.1
Host: localhost:3002
Content-Type: application/json
x-correlator: 550e8400-e29b-41d4-a716-446655440000

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

**Response:**
```http
HTTP/1.1 201 Created
Content-Type: application/json
x-correlator: 550e8400-e29b-41d4-a716-446655440000

{
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "duration": 3600,
  "qosProfile": "qos-e",
  "device": {
    "ipv4Address": {
      "publicAddress": "12.1.0.1",
      "privateAddress": "12.1.0.1"
    }
  },
  "applicationServer": {
    "ipv4Address": "10.0.0.1"
  },
  "qosStatus": "AVAILABLE",
  "startedAt": "2025-12-17T10:30:00.000Z",
  "expiresAt": "2025-12-17T11:30:00.000Z"
}
```

### 9.2 Get Session

**Request:**
```http
GET /api/qod?sessionId=a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Host: localhost:3002
x-correlator: 550e8400-e29b-41d4-a716-446655440001
```

**Response:**
```http
HTTP/1.1 200 OK
Content-Type: application/json
x-correlator: 550e8400-e29b-41d4-a716-446655440001

{
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "duration": 3600,
  "qosProfile": "qos-e",
  "qosStatus": "AVAILABLE",
  "startedAt": "2025-12-17T10:30:00.000Z",
  "expiresAt": "2025-12-17T11:30:00.000Z"
}
```

### 9.3 Delete Session

**Request:**
```http
DELETE /api/qod?sessionId=a1b2c3d4-e5f6-7890-abcd-ef1234567890 HTTP/1.1
Host: localhost:3002
x-correlator: 550e8400-e29b-41d4-a716-446655440002
```

**Response:**
```http
HTTP/1.1 204 No Content
x-correlator: 550e8400-e29b-41d4-a716-446655440002
```

### 9.4 Error Response Example

**Request (missing device):**
```http
POST /api/qod HTTP/1.1
Host: localhost:3002
Content-Type: application/json

{
  "qosProfile": "qos-e",
  "duration": 3600
}
```

**Response:**
```http
HTTP/1.1 400 Bad Request
Content-Type: application/json
x-correlator: auto-generated-uuid

{
  "status": 400,
  "code": "INVALID_ARGUMENT",
  "message": "applicationServer.ipv4Address is required"
}
```

---

## Appendix: QoS Profiles

| Profile | Description | Guaranteed Bandwidth |
|---------|-------------|---------------------|
| qos-e | Low latency eMBB | 120 Kbps |
| qos2 | Medium bandwidth | 240 Kbps |
| qos3 | High bandwidth | 480 Kbps |

---

*Documentation generated: December 17, 2025*
