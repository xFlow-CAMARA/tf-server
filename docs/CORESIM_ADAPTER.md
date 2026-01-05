# CoreSim Adapter with NEF Integration

This document explains how to use the CoreSim adapter with the Network Exposure Function (NEF) in the TF SDK.

## Architecture Overview

The system consists of three main components:

```
┌─────────────────────────────────────────────────────────────┐
│  TF SDK (Client)                                            │
│  └─ CoreSim Adapter (Python)                                │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP/REST
        ┌──────────┴──────────────┐
        │                         │
┌───────▼──────────┐      ┌───────▼──────────┐
│  CoreSim         │      │  NEF Services   │
│  (Port 8080/81)  │      │  (Docker)        │
│  - SBI APIs      │      │  - QoD           │
│  - OAM APIs      │      │  - Location      │
└──────────┬───────┘      │  - Traffic Inf.  │
           │              └────────┬─────────┘
           └──────────┬───────────┘
                      │
              ┌───────▼────────┐
              │  Redis         │
              │  (Data Store)  │
              └────────────────┘
```

## Installation

```bash
cd /home/xflow/oop/tf-sdk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Setup

### 1. Start CoreSim with NEF

```bash
# From docker-compose directory
cd /home/xflow/coresim/artifacts/docker-compose
docker compose up -d core-simulator

# From NEF directory (connects to CoreSim via bridge network)
cd /home/xflow/nef
docker compose up -d
```

### 2. Verify Services

```bash
# CoreSim OAM API
curl http://localhost:8081/core-simulator/v1/status

# NEF Redis
redis-cli -p 6380 PING

# Check NEF containers
docker ps | grep -E "core-simulator|core-network|as-session|traffic|monitoring"
```

## Usage

### Basic Usage

```python
from sunrise6g_opensdk.network.adapters.coresim import NetworkManager

# Using docker internal network (for containers)
manager = NetworkManager(
    base_url="http://core-simulator:8080",
    scs_as_id="nef",
    oam_port=8081,
    redis_addr="redis:6379",
    nef_callback_url="http://core-network-service:9090/eventsubscriptions"
)

# OR using localhost (for host machine)
manager = NetworkManager(
    base_url="http://localhost:8080",
    scs_as_id="nef",
    oam_port=8081,
    redis_addr="localhost:6380",
    nef_callback_url="http://localhost:9092/eventsubscriptions"
)
```

### Simulate UE Lifecycle

```python
# 1. Configure simulation
config = {
    "simulationProfile": {
        "plmn": {
            "mcc": "001",
            "mnc": "01"
        },
        "dnn": "internet",
        "slice": {
            "sst": 1,
            "sd": "FFFFFF"
        },
        "numOfUe": 20,
        "numOfgNB": 10,
        "arrivalRate": 2
    }
}
response = manager.configure_simulation(config)
print(f"Configured: {response}")

# 2. Get status
status = manager.get_status()
print(f"Status: {status}")

# 3. Start simulation (triggers NEF event subscriptions)
manager.start_simulation()

# 4. Make CAMARA API calls (see examples below)
# ...

# 5. Stop simulation
manager.stop_simulation()
```

### CAMARA QoD API

```python
# Create QoD session
session = manager.create_qod_session({
    "device": {
        "ipv4Address": {
            "publicAddress": "192.168.1.100",
            "privateAddress": "10.0.0.100"
        }
    },
    "applicationServer": {
        "ipv4Address": "10.0.0.1"
    },
    "qosProfile": "qos-e",
    "duration": 3600,
    "sink": "http://127.0.0.1:8001/callback"
})

print(f"Session created: {session['sessionId']['root']}")

# Get session details
session_id = session["sessionId"]["root"]
details = manager.get_qod_session(session_id)
print(f"Session details: {details}")

# Delete session
manager.delete_qod_session(session_id)
```

### CAMARA Location API

```python
# Subscribe to location updates
location = manager.create_monitoring_event_subscription({
    "device": {
        "networkAccessIdentifier": "user@example.com",
        "ipv4Address": "192.168.1.100",
        "phoneNumber": "+34607123456"
    }
})

print(f"Location: {location}")
```

### CAMARA Traffic Influence API

```python
# Create traffic influence
ti = manager.create_traffic_influence_resource({
    "appId": "app-123",
    "appInstanceId": "10.0.0.5",
    "edgeCloudZoneId": "zone-1",
    "notificationUri": "http://callback-server:8080/ti",
    "device": {
        "ipv4Address": {
            "publicAddress": "192.168.1.10"
        }
    }
})

print(f"TI created: {ti}")

# Get traffic influence
resource_id = ti["trafficInfluenceID"]
ti_details = manager.get_individual_traffic_influence_resource(resource_id)

# Delete
manager.delete_traffic_influence_resource(resource_id)
```

## Docker Network Configuration

The system uses a shared Docker bridge network (`coresim-bridge`):

| Service                | Internal URL                        | External URL         | Port |
|------------------------|-------------------------------------|----------------------|------|
| CoreSim SBI            | http://core-simulator:8080          | http://localhost:8080| 8080 |
| CoreSim OAM            | http://core-simulator:8081          | http://localhost:8081| 8081 |
| NEF QoD                | http://3gpp-as-session-with-qos:8080| http://localhost:8080| 8080 |
| NEF Location           | http://3gpp-monitoring-event:8080   | http://localhost:8080| 8080 |
| NEF Traffic Influence  | http://3gpp-traffic-influence:8080  | http://localhost:8080| 8080 |
| NEF Core Network       | http://core-network-service:9090    | http://localhost:9092| 9090 |
| Redis                  | redis:6379                          | localhost:6380       | 6379 |
| Prometheus             | http://nef-prometheus:9090          | http://localhost:9091| 9090 |
| Grafana                | http://nef-grafana:3000             | http://localhost:3001| 3000 |

## Configuration Parameters

### CoreSim Environment Variables (docker-compose.yaml)

```yaml
environment:
  - USE_NRF=False                    # Use static config instead of NRF
  - CN_HTTP_VERSION=2                # HTTP/2 support
  - REDIS_ADDR=redis:6379            # Redis connection
  - AMF_IP_ADDR=http://core-simulator:8080  # AMF endpoint
  - SMF_IP_ADDR=http://core-simulator:8080  # SMF endpoint
  - EVENT_NOTIFY_URI=http://core-network-service:9090/eventsubscriptions
  - SERVER_ADDR=0.0.0.0:9090
```

### Simulation Profile (config.yaml)

```yaml
simulationProfile:
  plmn:
    mcc: "001"
    mnc: "01"
  dnn: "internet"
  slice:
    sst: 1
    sd: "FFFFFF"
  numOfUe: 20        # Number of UEs
  numOfgNB: 10       # Number of gNBs
  arrivalRate: 2     # UEs arriving per time unit
```

## Data Persistence

All UE information is automatically persisted in Redis by the Core Network Service:

```bash
# Connect to Redis
redis-cli -p 6380

# View stored data
KEYS "*"                      # All keys
HGETALL "ue:123456789"        # UE details
```

## Troubleshooting

### Connection Issues

```bash
# Check if CoreSim is running
curl http://localhost:8081/core-simulator/v1/status

# Check NEF services
docker ps -f "status=running" | grep -E "nef|core"

# View logs
docker logs core-simulator
docker logs core-network-service
```

### Redis Connection Error

```bash
# Verify Redis is accessible
telnet localhost 6380
redis-cli -p 6380 PING

# Reset Redis
docker exec nef-redis redis-cli FLUSHALL
```

### NEF Service Not Subscribing

```bash
# Check Core Network Service logs
docker logs core-network-service

# Verify CoreSim is running and initialized
curl -X POST http://localhost:8081/core-simulator/v1/start
```

## Example Complete Workflow

```python
from sunrise6g_opensdk.network.adapters.coresim import NetworkManager
import json

# Initialize
manager = NetworkManager(
    base_url="http://localhost:8080",
    redis_addr="localhost:6380"
)

# Configure
config = {
    "simulationProfile": {
        "plmn": {"mcc": "001", "mnc": "01"},
        "dnn": "internet",
        "slice": {"sst": 1, "sd": "FFFFFF"},
        "numOfUe": 5,
        "numOfgNB": 2,
        "arrivalRate": 1
    }
}
manager.configure_simulation(config)

# Start
manager.start_simulation()
print("✓ Simulation started")

# Create QoD session
session = manager.create_qod_session({
    "device": {"ipv4Address": {"publicAddress": "192.168.1.100"}},
    "applicationServer": {"ipv4Address": "10.0.0.1"},
    "qosProfile": "qos-e",
    "duration": 1800,
    "sink": "http://callback:8080/qos"
})
session_id = session["sessionId"]["root"]
print(f"✓ QoD session created: {session_id}")

# Clean up
manager.delete_qod_session(session_id)
manager.stop_simulation()
print("✓ Simulation stopped")
```

## API References

- 3GPP TS 29.502 (Nsmf_EventExposure)
- 3GPP TS 29.518 (Namf_Events)  
- 3GPP TS 29.514 (Npcf_PolicyAuthorization)
- CAMARA QoD, Location, Traffic Influence APIs

