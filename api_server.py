#!/usr/bin/env python3
"""
TF-SDK REST API Server

Wraps TF-SDK to provide REST endpoints for CAMARA APIs.
Supports multiple 5G cores: CoreSim, Open5GS, OAI, Open5GCore
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sunrise6g_opensdk.common.sdk import Sdk as sdkclient
import os
import uvicorn
import yaml
import requests
from datetime import datetime, timedelta
import re
import subprocess

app = FastAPI(title="TF-SDK API Server", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import CAMARA routers
import camara_qod
import camara_location
import camara_traffic_influence
import camara_number_verification

app.include_router(camara_qod.router)
app.include_router(camara_location.router)
app.include_router(camara_traffic_influence.router)
app.include_router(camara_number_verification.router)

# Store multiple network clients for different 5G cores
network_clients = {}

def init_network_client(core_name: str):
    """Initialize a network client for a specific 5G core"""
    # Core-specific base URLs
    base_urls = {
        "coresim": os.getenv("CORESIM_BASE_URL", "http://localhost:8080"),
        "oai": os.getenv("OAI_BASE_URL", "http://oai-amf:80"),
        "open5gs": os.getenv("OPEN5GS_BASE_URL", "http://localhost:8080"),
        "open5gcore": os.getenv("OPEN5GCORE_BASE_URL", "http://localhost:8080")
    }
    
    # CoreSim-specific configuration
    if core_name.lower() == "coresim":
        adapter_specs = {
            "network": {
                "client_name": "coresim",
                "base_url": base_urls["coresim"],
                "scs_as_id": "nef",
                "oam_port": 8081,
                "redis_addr": os.getenv("REDIS_ADDR", "localhost:6380"),
                "nef_callback_url": os.getenv("NEF_CALLBACK_URL", "http://localhost:9092/eventsubscriptions"),
                "qod_base_url": os.getenv("NEF_QOD_BASE_URL", "http://localhost:8100"),
                "location_base_url": os.getenv("NEF_LOCATION_BASE_URL", "http://localhost:8102"),
                "ti_base_url": os.getenv("NEF_TI_BASE_URL", "http://localhost:8101"),
                "ue_identity_base_url": os.getenv("NEF_UE_IDENTITY_BASE_URL", "http://localhost:8103"),
            }
        }
    else:
        # OAI and other cores - minimal config
        adapter_specs = {
            "network": {
                "client_name": core_name.lower(),
                "base_url": base_urls.get(core_name.lower(), base_urls["coresim"]),
                "scs_as_id": "nef",
            }
        }
    
    try:
        adapters = sdkclient.create_adapters_from(adapter_specs)
        client = adapters.get("network")
        print(f"✓ TF-SDK network client initialized for {core_name}")
        return client
    except Exception as e:
        print(f"✗ Failed to initialize TF-SDK for {core_name}: {e}")
        return None

# Initialize default CoreSim client
network_clients["coresim"] = init_network_client("coresim")

# Track active core
active_core = {"name": "coresim"}  # Default to coresim

network_client = network_clients[active_core["name"]]

# Share network_clients with CAMARA modules
camara_qod.network_clients = network_clients
camara_location.network_clients = network_clients
camara_traffic_influence.network_clients = network_clients
camara_number_verification.network_clients = network_clients

def get_client(core: str = "coresim"):
    """Get network client for specified core"""
    core_lower = core.lower()
    if core_lower not in network_clients:
        # Try to initialize on-demand
        network_clients[core_lower] = init_network_client(core_lower)
    return network_clients.get(core_lower)


# Legacy models for backward compatibility
class QodSessionRequest(BaseModel):
    duration: Optional[int] = 3600
    qosProfile: str = "qos-e"
    device: Dict[str, Any]
    applicationServer: Dict[str, Any]
    devicePorts: Optional[Dict[str, Any]] = None
    applicationServerPorts: Optional[Dict[str, Any]] = None
    notificationUrl: str
    notificationAuthToken: Optional[str] = None


class LocationRequest(BaseModel):
    device: Dict[str, Any]
    maxAge: Optional[int] = 60


class TrafficInfluenceRequest(BaseModel):
    appId: str
    appInstanceId: str
    edgeCloudZoneId: str
    notificationUri: str
    device: Dict[str, Any]


# Health check
@app.get("/health")
async def health():
    return {
        "status": "healthy", 
        "cores": list(network_clients.keys()),
        "activeCore": active_core["name"]
    }


# Get active core
@app.get("/api/cores/active")
async def get_active_core():
    """Get the currently active 5G core"""
    return {
        "activeCore": active_core["name"],
        "availableCores": list(network_clients.keys())
    }


# Switch active core
@app.post("/api/cores/active")
async def set_active_core(request: Request):
    """Switch the active 5G core network"""
    try:
        body = await request.json()
        core_name = body.get("coreName")
        
        if not core_name:
            raise HTTPException(status_code=400, detail="Missing 'coreName' field")
        
        if core_name not in network_clients:
            raise HTTPException(
                status_code=404, 
                detail=f"Core '{core_name}' not found. Available: {list(network_clients.keys())}"
            )
        
        if network_clients[core_name] is None:
            raise HTTPException(
                status_code=503,
                detail=f"Core '{core_name}' is not initialized"
            )
        
        # Update active core
        old_core = active_core["name"]
        active_core["name"] = core_name
        
        # Update NEF configurations
        update_nef_configs(core_name)
        
        # Restart NEF services to apply new configuration
        restart_result = restart_nef_services()
        
        return {
            "success": True,
            "previousCore": old_core,
            "activeCore": active_core["name"],
            "message": f"Switched from {old_core} to {core_name}. NEF services restarted.",
            "nefRestart": restart_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def restart_nef_services():
    """Restart NEF services to apply configuration changes"""
    try:
        # List of NEF service containers to restart
        nef_services = [
            "3gpp-as-session-with-qos",
            "3gpp-traffic-influence",
            "3gpp-monitoring-event"
        ]
        
        restart_status = {}
        for service in nef_services:
            try:
                result = subprocess.run(
                    ["docker", "restart", service],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                restart_status[service] = "restarted" if result.returncode == 0 else "failed"
            except Exception as e:
                restart_status[service] = f"error: {str(e)}"
        
        return restart_status
    except Exception as e:
        return {"error": str(e)}


def update_nef_configs(core_name: str):
    """Update NEF configuration files to use the specified core"""
    import yaml
    
    # Core-specific configurations
    core_configs = {
        "coresim": {
            "useNrf": False,
            "nrfSvc": "http://nrf.net01.3gpp.eurecom.fr",
            "pcfSvc": "http://core-simulator:8080"
        },
        "oai": {
            "useNrf": True,
            "nrfSvc": "http://oai-nrf:80",
            "pcfSvc": "http://oai-pcf:80"
        }
    }
    
    config = core_configs.get(core_name, core_configs["coresim"])
    
    # Update asSessionWithQos.yaml
    qos_config_path = "/config/asSessionWithQos.yaml"
    if os.path.exists(qos_config_path):
        try:
            with open(qos_config_path, 'r') as f:
                qos_config = yaml.safe_load(f)
            
            qos_config['sbi']['useNrf'] = config['useNrf']
            qos_config['sbi']['nrfSvc'] = config['nrfSvc']
            qos_config['sbi']['pcfSvc'] = config['pcfSvc']
            
            with open(qos_config_path, 'w') as f:
                yaml.dump(qos_config, f, default_flow_style=False)
            
            print(f"✓ Updated asSessionWithQos.yaml for {core_name}")
        except Exception as e:
            print(f"✗ Failed to update asSessionWithQos.yaml: {e}")
    
    # Update trafficInfluence.yaml
    ti_config_path = "/config/trafficInfluence.yaml"
    if os.path.exists(ti_config_path):
        try:
            with open(ti_config_path, 'r') as f:
                ti_config = yaml.safe_load(f)
            
            ti_config['sbi']['useNrf'] = config['useNrf']
            ti_config['sbi']['nrfSvc'] = config['nrfSvc']
            ti_config['sbi']['pcfSvc'] = config['pcfSvc']
            
            with open(ti_config_path, 'w') as f:
                yaml.dump(ti_config, f, default_flow_style=False)
            
            print(f"✓ Updated trafficInfluence.yaml for {core_name}")
        except Exception as e:
            print(f"✗ Failed to update trafficInfluence.yaml: {e}")


# List available 5G cores
@app.get("/api/cores")
async def list_cores():
    """List available 5G cores with connection status"""
    available_cores = []
    
    core_configs = {
        "coresim": {
            "displayName": "CoreSim",
            "configPath": "/coresim-config/coreSim.yaml",
            "prometheusUrl": "http://coresim-prometheus:9090",
            "grafanaUrl": "http://grafana:3000",
            "type": "simulator"
        }
    }
    
    for core_name, info in core_configs.items():
        is_initialized = core_name in network_clients and network_clients[core_name] is not None
        # For cores with config files, check if they exist
        # For cores without config files (like OAI), consider them configured if initialized
        has_config = (info["configPath"] and os.path.exists(info["configPath"])) if info["configPath"] else is_initialized
        
        # Try to get actual status if initialized
        connected = False
        status_detail = "not_configured"
        config_data = None
        ues = []
        
        if is_initialized:
            try:
                client = network_clients[core_name]
                status_response = client.get_status()
                status_detail = status_response.get("Status", "UNKNOWN")
                # Only mark as connected if simulation is actually running
                connected = (status_detail == "STARTED")
            except Exception as e:
                status_detail = f"error: {str(e)}"
        elif has_config:
            status_detail = "configured"
        
        # Read configuration file if it exists
        if info["configPath"] and os.path.exists(info["configPath"]):
            try:
                import yaml
                with open(info["configPath"], 'r') as f:
                    config_data = yaml.safe_load(f)
            except Exception as e:
                print(f"Failed to read config for {core_name}: {e}")
        
        # Fetch UE information from CoreSim metrics endpoint or config
        if core_name == "coresim" and (connected or has_config):
            # Try to get UEs from metrics first (when simulation is running)
            if connected:
                try:
                    import requests
                    import re
                    # Get metrics from CoreSim metrics endpoint
                    response = requests.get(
                        "http://core-simulator:9090/metrics",
                        timeout=2
                    )
                    if response.status_code == 200:
                        metrics_text = response.text
                        # Parse ue_ip_info metrics using regex
                        # Format: ue_ip_info{imsi="001010000000001",ip="12.1.0.1",...} 1
                        pattern = r'ue_ip_info\{imsi="([^"]+)",ip="([^"]+)"'
                        for match in re.finditer(pattern, metrics_text):
                            imsi = match.group(1)
                            ip = match.group(2)
                            ues.append({
                                "imsi": imsi,
                                "ip": ip
                            })
                        if ues:
                            print(f"✓ Found {len(ues)} UEs for {core_name} from metrics")
                except Exception as e:
                    print(f"Failed to fetch UEs from metrics for {core_name}: {e}")
            
            # If no UEs from metrics, generate from config
            if not ues and config_data and config_data.get("simulationProfile"):
                try:
                    profile = config_data["simulationProfile"]
                    num_ue = profile.get("numOfUe", 0)
                    plmn = profile.get("plmn", {})
                    mcc = plmn.get("mcc", "001")
                    mnc = plmn.get("mnc", "01")
                    
                    for i in range(1, num_ue + 1):
                        imsi = f"{mcc}{mnc}{str(i).zfill(10)}"
                        ip = f"12.1.0.{i}"
                        ues.append({
                            "imsi": imsi,
                            "ip": ip
                        })
                    if ues:
                        print(f"✓ Generated {len(ues)} UEs for {core_name} from config")
                except Exception as e:
                    print(f"Failed to generate UEs from config for {core_name}: {e}")
        
        core_info = {
            "name": core_name,
            "displayName": info["displayName"],
            "connected": connected,
            "hasConfig": has_config,
            "status": status_detail,
            "initialized": is_initialized,
            "type": info.get("type", "5g_core")
        }
        
        if config_data:
            core_info["config"] = config_data
        
        if "networkFunctions" in info:
            core_info["networkFunctions"] = info["networkFunctions"]
        
        if "ranSimulator" in info:
            # Load actual RAN simulator config from file
            ran_sim = info["ranSimulator"].copy()
            if "configPath" in ran_sim and os.path.exists(ran_sim["configPath"]):
                try:
                    with open(ran_sim["configPath"], 'r') as f:
                        ran_config = yaml.safe_load(f)
                    ran_sim["config"] = ran_config
                except Exception as e:
                    print(f"Failed to read RAN config for {core_name}: {e}")
            core_info["ranSimulator"] = ran_sim
        
        if ues:
            core_info["ues"] = ues
        
        available_cores.append(core_info)
    
    return {"cores": available_cores}


# OAI Core Control
@app.post("/api/cores/oai/control")
async def control_oai_core(request: Request):
    """Start or stop OAI 5G Core and gnbsim"""
    try:
        import subprocess
        body = await request.json()
        action = body.get("action")
        
        if action not in ["start", "stop", "restart"]:
            raise HTTPException(status_code=400, detail="Action must be 'start', 'stop', or 'restart'")
        
        oai_dir = "/oai-core"
        if not os.path.exists(oai_dir):
            raise HTTPException(status_code=404, detail="OAI core directory not found")
        
        if action == "start":
            # Start OAI core
            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                cwd=oai_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Failed to start OAI core: {result.stderr}"
                )
            
            return {
                "success": True,
                "message": "OAI 5G Core started. Waiting for services to be ready (~2 min). gnbsim will auto-register UEs.",
                "action": "start",
                "stdout": result.stdout
            }
        
        elif action == "stop":
            # Stop OAI core
            result = subprocess.run(
                ["docker-compose", "down"],
                cwd=oai_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to stop OAI core: {result.stderr}"
                )
            
            return {
                "success": True,
                "message": "OAI 5G Core stopped",
                "action": "stop",
                "stdout": result.stdout
            }
        
        elif action == "restart":
            # Restart OAI core
            result = subprocess.run(
                ["docker-compose", "restart"],
                cwd=oai_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to restart OAI core: {result.stderr}"
                )
            
            return {
                "success": True,
                "message": "OAI 5G Core restarted",
                "action": "restart",
                "stdout": result.stdout
            }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Operation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Get OAI Core status
@app.get("/api/cores/oai/status")
async def get_oai_status():
    """Get OAI 5G Core container status"""
    try:
        import subprocess
        
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=oai-", "--format", "{{.Names}}\t{{.Status}}\t{{.State}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="Failed to get container status")
        
        containers = []
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    containers.append({
                        "name": parts[0],
                        "status": parts[1],
                        "state": parts[2]
                    })
        
        # Count running containers
        running = sum(1 for c in containers if c["state"] == "running")
        total = len(containers)
        
        # Check gnbsim logs for UE registrations
        ue_registered = 0
        try:
            gnbsim_result = subprocess.run(
                ["docker", "logs", "--tail", "100", "oai-gnbsim"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if gnbsim_result.returncode == 0:
                # Count successful registrations
                ue_registered = gnbsim_result.stdout.count("Registration successful")
        except:
            pass
        
        return {
            "running": running > 0,
            "containers": containers,
            "summary": f"{running}/{total} containers running",
            "uesRegistered": ue_registered,
            "ready": running == total and running > 0
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Operation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Update CoreSim configuration
@app.put("/api/cores/{core_name}/config")
async def update_core_config(core_name: str, config: dict):
    """Update configuration for a specific core"""
    if core_name != "coresim":
        raise HTTPException(status_code=404, detail="Core not found or not configurable")
    
    config_path = "/coresim-config/coreSim.yaml"
    
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Config file not found")
    
    try:
        import yaml
        
        # Read existing config
        with open(config_path, 'r') as f:
            existing_config = yaml.safe_load(f)
        
        # Update simulation profile fields
        if "simulationProfile" in config and "simulationProfile" in existing_config:
            profile = existing_config["simulationProfile"]
            updates = config["simulationProfile"]
            
            # Update PLMN
            if "plmn" in updates and "plmn" in profile:
                if "mcc" in updates["plmn"]:
                    profile["plmn"]["mcc"] = updates["plmn"]["mcc"]
                if "mnc" in updates["plmn"]:
                    profile["plmn"]["mnc"] = updates["plmn"]["mnc"]
            
            # Update other fields
            if "numOfUe" in updates:
                profile["numOfUe"] = int(updates["numOfUe"])
            if "numOfgNB" in updates:
                profile["numOfgNB"] = int(updates["numOfgNB"])
            if "dnn" in updates:
                profile["dnn"] = updates["dnn"]
            if "arrivalRate" in updates:
                profile["arrivalRate"] = int(updates["arrivalRate"])
            
            # Update slice
            if "slice" in updates and "slice" in profile:
                if "sst" in updates["slice"]:
                    profile["slice"]["sst"] = int(updates["slice"]["sst"])
                if "sd" in updates["slice"]:
                    profile["slice"]["sd"] = updates["slice"]["sd"]
        
        # Write updated config
        with open(config_path, 'w') as f:
            yaml.dump(existing_config, f, default_flow_style=False, sort_keys=False)
        
        return {"success": True, "message": "Configuration updated successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


# ============================================================================
# Legacy/Backward Compatibility Endpoints
# ============================================================================

# CoreSim control endpoints
@app.get("/api/{core}/status")
async def get_core_status(core: str):
    """Get status for any 5G core"""
    client = get_client(core)
    if client is None:
        raise HTTPException(status_code=503, detail=f"TF-SDK client for {core} not initialized")
    
    try:
        import yaml
        import os
        
        # Get core runtime status
        status_response = client.get_status()
        sim_status = status_response.get("Status", "UNKNOWN")
        
        # Load configuration based on core type
        profile_paths = {
            "coresim": "/home/xflow/coresim/core-simulator/cli/cnsim-profile.yaml",
            # Add paths for other cores as they are configured
            # "open5gs": "/path/to/open5gs/config.yaml",
            # "oai": "/path/to/oai/config.yaml",
        }
        
        profile_path = profile_paths.get(core.lower())
        
        if not profile_path or not os.path.exists(profile_path):
            raise HTTPException(
                status_code=503, 
                detail=f"Configuration file not found for {core}. Please configure the 5G core first."
            )
        
        with open(profile_path, 'r') as f:
            profiles = yaml.safe_load(f)
            
        if "profiles" not in profiles or "default" not in profiles["profiles"]:
            raise HTTPException(
                status_code=503,
                detail=f"Invalid configuration file for {core}: missing default profile"
            )
        
        default_profile = profiles["profiles"]["default"]
        
        # Validate required fields
        required_fields = ["plmn", "dnn", "numUe"]
        for field in required_fields:
            if field not in default_profile:
                raise HTTPException(
                    status_code=503,
                    detail=f"Invalid configuration: missing required field '{field}'"
                )
        
        plmn = default_profile["plmn"]
        dnn = default_profile["dnn"]
        num_ue = default_profile["numUe"]
        num_gnbs = default_profile.get("gNBs", 0)  # Get gNBs count, default to 0
        
        config = {
            "plmn": plmn,
            "dnn": dnn,
            "numOfUe": num_ue,
            "numOfGnbs": num_gnbs
        }
        
        # Generate UE list based on profile config
        ues = []
        ip_base = default_profile.get("ueIpBase", "12.1.0")  # Allow IP base override
        for i in range(1, num_ue + 1):
            ues.append({
                "supi": f"{plmn['mcc']}{plmn['mnc']}{str(i).zfill(10)}",
                "ipAddress": f"{ip_base}.{i}",
                "dnn": dnn
            })
        
        return {
            "core": core,
            "status": sim_status,
            "ues": ues,
            "config": config,
            "available": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/coresim/control")
async def control_coresim(request: Request):
    """Control CoreSim simulator (start/stop)"""
    return await control_core("coresim", request)


@app.post("/api/cores/{core_name}/control")
async def control_core(core_name: str, request: Request):
    """Unified control endpoint for any 5G core simulation"""
    client = get_client(core_name)
    if client is None:
        raise HTTPException(status_code=503, detail=f"TF-SDK client for {core_name} not initialized")
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    
    action = body.get("action")
    if not action:
        raise HTTPException(status_code=400, detail="Missing 'action' field")
    
    try:
        if action == "start":
            # First stop if running, then restart container to clear metrics
            try:
                client.stop_simulation()
                import time
                time.sleep(1)
            except:
                pass
            
            # Restart the CoreSim container to reset metrics
            import subprocess
            try:
                subprocess.run(["docker", "restart", "core-simulator"], 
                             check=True, capture_output=True, timeout=30)
                time.sleep(15)  # Wait longer for container to be fully ready
            except Exception as e:
                print(f"Warning: Could not restart container: {e}")
            
            # Retry logic for starting simulation
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = client.start_simulation()
                    return {"success": True, "core": core_name, "action": "start", "data": result}
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                        time.sleep(3)
                    else:
                        raise
        elif action == "stop":
            result = client.stop_simulation()
            return {"success": True, "core": core_name, "action": "stop", "data": result}
        elif action == "restart":
            # Stop then start
            client.stop_simulation()
            import time
            time.sleep(2)
            result = client.start_simulation()
            return {"success": True, "core": core_name, "action": "restart", "data": result}
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}. Use: start or stop")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/{core}/start")
async def start_core(core: str):
    """Start any 5G core simulation (legacy endpoint)"""
    client = get_client(core)
    if client is None:
        raise HTTPException(status_code=503, detail=f"TF-SDK client for {core} not initialized")
    
    try:
        result = client.start_simulation()
        return {"success": True, "core": core, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/{core}/stop")
async def stop_core(core: str):
    """Stop any 5G core simulation (legacy endpoint)"""
    client = get_client(core)
    if client is None:
        raise HTTPException(status_code=503, detail=f"TF-SDK client for {core} not initialized")
    
    try:
        result = client.stop_simulation()
        return {"success": True, "core": core, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# QoD endpoints
@app.post("/api/{core}/qod/sessions")
async def create_qod_session(core: str, request: QodSessionRequest):
    """Create QoD session on any 5G core"""
    client = get_client(core)
    if client is None:
        raise HTTPException(status_code=503, detail=f"TF-SDK client for {core} not initialized")
    
    try:
        # Build session info in TF-SDK format
        session_info = {
            "duration": request.duration,
            "qosProfile": request.qosProfile,
            "device": request.device,
            "applicationServer": request.applicationServer,
            "sink": request.notificationUrl,
        }
        
        if request.devicePorts:
            session_info["devicePorts"] = request.devicePorts
        if request.applicationServerPorts:
            session_info["applicationServerPorts"] = request.applicationServerPorts
        
        result = client.create_qod_session(session_info)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/{core}/qod/sessions/{session_id}")
async def get_qod_session(core: str, session_id: str):
    """Get QoD session details from any 5G core"""
    client = get_client(core)
    if client is None:
        raise HTTPException(status_code=503, detail=f"TF-SDK client for {core} not initialized")
    
    try:
        result = client.get_qod_session(session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/{core}/qod/sessions/{session_id}")
async def delete_qod_session(core: str, session_id: str):
    """Delete QoD session from any 5G core"""
    client = get_client(core)
    if client is None:
        raise HTTPException(status_code=503, detail=f"TF-SDK client for {core} not initialized")
    
    try:
        client.delete_qod_session(session_id)
        return {"status": "deleted", "sessionId": session_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Location endpoints
@app.post("/api/{core}/location/retrieve")
async def retrieve_location(core: str, request: LocationRequest):
    """Retrieve device location from any 5G core"""
    client = get_client(core)
    if client is None:
        raise HTTPException(status_code=503, detail=f"TF-SDK client for {core} not initialized")
    
    try:
        location_info = {
            "device": request.device,
            "maxAge": request.maxAge,
        }
        result = network_client.retrieve_location(location_info)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Traffic Influence endpoints
@app.post("/api/traffic-influence/subscriptions")
async def create_traffic_influence(request: TrafficInfluenceRequest):
    if network_client is None:
        raise HTTPException(status_code=503, detail="TF-SDK not initialized")
    
    try:
        ti_info = {
            "appId": request.appId,
            "appInstanceId": request.appInstanceId,
            "edgeCloudZoneId": request.edgeCloudZoneId,
            "notificationUri": request.notificationUri,
            "device": request.device,
        }
        result = network_client.create_traffic_influence(ti_info)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/traffic-influence/subscriptions/{subscription_id}")
async def get_traffic_influence(subscription_id: str):
    if network_client is None:
        raise HTTPException(status_code=503, detail="TF-SDK not initialized")
    
    try:
        result = network_client.get_traffic_influence_subscription(subscription_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/traffic-influence/subscriptions/{subscription_id}")
async def delete_traffic_influence(subscription_id: str):
    if network_client is None:
        raise HTTPException(status_code=503, detail="TF-SDK not initialized")
    
    try:
        network_client.delete_traffic_influence(subscription_id)
        return {"status": "deleted", "subscriptionId": subscription_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Cache for CAMARA releases (TTL: 1 hour)
_camara_release_cache = {
    "data": None,
    "timestamp": None,
    "ttl": 3600  # 1 hour in seconds
}

# Cache for 3GPP spec releases (TTL: 1 hour)
_3gpp_release_cache = {
    "data": None,
    "timestamp": None,
    "ttl": 3600  # 1 hour in seconds
}

def get_github_latest_release(repo: str) -> Optional[str]:
    """
    Fetch the latest release tag from a GitHub repository
    Returns version string like "v0.3.0" or None if unavailable
    """
    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/releases/latest",
            timeout=5,
            headers={"Accept": "application/vnd.github.v3+json"}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("tag_name", "latest")
        return "latest"
    except Exception:
        return "latest"

def get_camara_api_releases() -> Dict[str, str]:
    """
    Fetch CAMARA API releases with caching
    Returns dict mapping API name to release version
    """
    now = datetime.now()
    
    # Check cache validity
    if (_camara_release_cache["data"] is not None and 
        _camara_release_cache["timestamp"] is not None):
        elapsed = (now - _camara_release_cache["timestamp"]).total_seconds()
        if elapsed < _camara_release_cache["ttl"]:
            return _camara_release_cache["data"]
    
    # Fetch fresh data
    releases = {
        "qualityOnDemand": get_github_latest_release("camaraproject/QualityOnDemand"),
        "deviceLocation": get_github_latest_release("camaraproject/DeviceLocation"),
        "trafficInfluence": get_github_latest_release("camaraproject/TrafficInfluence"),
        "numberVerification": get_github_latest_release("camaraproject/NumberVerification"),
    }
    
    # Update cache
    _camara_release_cache["data"] = releases
    _camara_release_cache["timestamp"] = now
    
    return releases

def get_3gpp_spec_releases() -> Dict[str, str]:
    """
    Fetch available 3GPP specification releases from GitHub with caching
    Returns dict mapping spec number to latest release
    """
    now = datetime.now()
    
    # Check cache validity
    if (_3gpp_release_cache["data"] is not None and 
        _3gpp_release_cache["timestamp"] is not None):
        elapsed = (now - _3gpp_release_cache["timestamp"]).total_seconds()
        if elapsed < _3gpp_release_cache["ttl"]:
            return _3gpp_release_cache["data"]
    
    # Fetch fresh data
    try:
        # Fetch branches from 5GC_APIs repo to get available releases
        response = requests.get(
            "https://api.github.com/repos/jdegre/5GC_APIs/branches",
            timeout=5,
            headers={"Accept": "application/vnd.github.v3+json"}
        )
        if response.status_code == 200:
            branches = response.json()
            # Find the latest Rel-XX branch
            release_branches = [b["name"] for b in branches if b["name"].startswith("Rel-")]
            if release_branches:
                # Sort and get latest (e.g., Rel-18, Rel-19)
                latest_rel = sorted(release_branches, key=lambda x: int(x.split("-")[1]) if "-" in x else 0)[-1]
                release_num = latest_rel.split("-")[1] if "-" in latest_rel else "18"
                releases = {
                    "TS 29.122": f"3GPP Release {release_num}",
                    "TS 29.522": f"3GPP Release {release_num}",
                    "TS 29.222": f"3GPP Release {int(release_num)-1}",  # CAPIF typically one release behind
                }
                
                # Update cache
                _3gpp_release_cache["data"] = releases
                _3gpp_release_cache["timestamp"] = now
                return releases
    except Exception:
        pass
    
    # Fallback to reasonable defaults
    fallback = {
        "TS 29.122": "3GPP Release 18",
        "TS 29.522": "3GPP Release 18",
        "TS 29.222": "3GPP Release 17",
    }
    
    # Cache fallback too
    _3gpp_release_cache["data"] = fallback
    _3gpp_release_cache["timestamp"] = now
    
    return fallback

def get_3gpp_release_from_spec(spec: str) -> str:
    """
    Extract 3GPP release from specification reference
    Fetches dynamically from 3GPP API repository
    """
    spec_releases = get_3gpp_spec_releases()
    return spec_releases.get(spec, "3GPP Release 18")


def discover_nef_apis(base_url: str, service_name: str) -> list:
    """
    Dynamically discover available 3GPP APIs from NEF service
    Tries to fetch OpenAPI spec or probe common endpoints
    """
    print(f"[Discovery] Starting NEF API discovery for {service_name} at {base_url}")
    discovered_apis = []
    
    # First, try to fetch OpenAPI/Swagger spec
    openapi_paths = [
        "/openapi.json",
        "/openapi.yaml", 
        "/swagger.json",
        "/api-docs",
        "/v3/api-docs",
        "/docs/openapi.json"
    ]
    
    api_patterns = []
    spec_found = False
    
    for spec_path in openapi_paths:
        try:
            response = requests.get(f"{base_url}{spec_path}", timeout=3)
            if response.status_code == 200:
                print(f"[Discovery] Found OpenAPI spec at {base_url}{spec_path}")
                spec_data = response.json()
                # Extract paths from OpenAPI spec
                if "paths" in spec_data:
                    for path, methods in spec_data["paths"].items():
                        # Extract API name from path (e.g., /3gpp-monitoring-event/v1 -> Monitoring Event)
                        if path.startswith("/3gpp-"):
                            api_name_part = path.split("/")[1].replace("3gpp-", "").replace("-", " ").title()
                            # Determine spec from path patterns
                            spec = "TS 29.122"  # Default NEF spec
                            if "traffic-influence" in path or "analytics" in path:
                                spec = "TS 29.522"
                            elif "as-session" in path or "monitoring" in path or "device-triggering" in path:
                                spec = "TS 29.122"
                            
                            api_patterns.append({
                                "path": path,
                                "name": api_name_part,
                                "spec": spec
                            })
                    spec_found = True
                    break
        except Exception as e:
            print(f"[Discovery] Could not fetch {spec_path}: {e}")
            continue
    
    # If no OpenAPI spec found, try common 3GPP NEF API patterns
    if not spec_found:
        print(f"[Discovery] No OpenAPI spec found, using common patterns for {service_name}")
        api_patterns = [
            {"path": "/3gpp-as-session-with-qos/v1", "name": "QoS Session Management", "spec": "TS 29.122"},
            {"path": "/3gpp-monitoring-event/v1", "name": "Monitoring Event", "spec": "TS 29.122"},
            {"path": "/3gpp-traffic-influence/v1", "name": "Traffic Influence", "spec": "TS 29.522"},
            {"path": "/3gpp-analyticsexposure/v1", "name": "Analytics Exposure", "spec": "TS 29.522"},
            {"path": "/3gpp-acs/v1", "name": "Application Context Services", "spec": "TS 29.122"},
            {"path": "/3gpp-device-triggering/v1", "name": "Device Triggering", "spec": "TS 29.122"},
            {"path": "/3gpp-chargeable-party/v1", "name": "Chargeable Party", "spec": "TS 29.122"},
            {"path": "/3gpp-nidd/v1", "name": "Non-IP Data Delivery", "spec": "TS 29.122"},
            {"path": "/3gpp-bdtpolicy/v1", "name": "Background Data Transfer Policy", "spec": "TS 29.122"},
        ]
    
    # Probe each API endpoint to verify availability
    print(f"[Discovery] Probing {len(api_patterns)} API patterns...")
    for api in api_patterns:
        try:
            # Try to reach the API endpoint
            check_url = f"{base_url}{api['path']}"
            response = requests.get(check_url, timeout=2)
            print(f"[Discovery] {check_url} -> HTTP {response.status_code}")
            # If we get any response (not connection refused), API exists
            if response.status_code in [200, 401, 403, 404, 405]:  # These indicate API is present
                discovered_apis.append({
                    "name": api["name"],
                    "path": api["path"],
                    "spec": api["spec"],
                    "available": response.status_code in [200, 401, 405]  # 405 = method not allowed (GET on POST endpoint)
                })
                print(f"[Discovery] ✓ Discovered: {api['name']} at {api['path']}")
        except requests.exceptions.RequestException as e:
            # Connection refused or timeout means API not available
            print(f"[Discovery] ✗ Not available: {api['path']} - {e}")
            pass
    
    print(f"[Discovery] Found {len(discovered_apis)} NEF APIs at {base_url}")
    return discovered_apis


def discover_core_network_apis(base_url: str) -> list:
    """
    Dynamically discover available core network APIs (PCF, AMF, SMF interfaces)
    Fetches from OpenAPI spec or probes common SBI endpoints
    """
    discovered_apis = []
    
    # Try to fetch OpenAPI/Swagger spec first
    openapi_paths = [
        "/openapi.json",
        "/openapi.yaml",
        "/swagger.json",
        "/api-docs",
        "/nrf/openapi.json",  # NRF often exposes this
    ]
    
    api_patterns = []
    spec_found = False
    
    # Mapping of NF service names to TS specs and NF types
    nf_spec_map = {
        "npcf-policyauthorization": {"spec": "TS 29.514", "nf": "PCF"},
        "npcf-smpolicycontrol": {"spec": "TS 29.512", "nf": "PCF"},
        "npcf-am-policy-control": {"spec": "TS 29.507", "nf": "PCF"},
        "namf-comm": {"spec": "TS 29.518", "nf": "AMF"},
        "namf-evts": {"spec": "TS 29.518", "nf": "AMF"},
        "nsmf-pdusession": {"spec": "TS 29.502", "nf": "SMF"},
        "nsmf-event-exposure": {"spec": "TS 29.508", "nf": "SMF"},
        "nudm-sdm": {"spec": "TS 29.503", "nf": "UDM"},
        "nudm-uecm": {"spec": "TS 29.503", "nf": "UDM"},
        "nausf-auth": {"spec": "TS 29.509", "nf": "AUSF"},
        "nnrf-disc": {"spec": "TS 29.510", "nf": "NRF"},
        "nnrf-nfm": {"spec": "TS 29.510", "nf": "NRF"},
        "nssf-nsselection": {"spec": "TS 29.531", "nf": "NSSF"},
        "nudr-dr": {"spec": "TS 29.504", "nf": "UDR"},
        "nnef-eventexposure": {"spec": "TS 29.591", "nf": "NEF"},
    }
    
    for spec_path in openapi_paths:
        try:
            response = requests.get(f"{base_url}{spec_path}", timeout=3)
            if response.status_code == 200:
                spec_data = response.json()
                if "paths" in spec_data:
                    for path, methods in spec_data["paths"].items():
                        # Extract NF service name from path (e.g., /npcf-policyauthorization/v1)
                        if path.startswith("/n"):
                            parts = path.split("/")
                            if len(parts) >= 2:
                                service_name = parts[1]
                                api_name = service_name.replace("n", "", 1).replace("-", " ").title()
                                
                                # Get spec and NF from mapping
                                nf_info = nf_spec_map.get(service_name, {"spec": "TS 29.xxx", "nf": "Unknown"})
                                
                                api_patterns.append({
                                    "path": "/" + service_name + "/" + (parts[2] if len(parts) > 2 else "v1"),
                                    "name": api_name,
                                    "spec": nf_info["spec"],
                                    "nf": nf_info["nf"]
                                })
                    spec_found = True
                    break
        except Exception:
            continue
    
    # If no OpenAPI spec found, use fallback common patterns
    if not spec_found:
        api_patterns = [
            {"path": "/npcf-policyauthorization/v1", "name": "PCF Policy Authorization", "spec": "TS 29.514", "nf": "PCF"},
            {"path": "/npcf-smpolicycontrol/v1", "name": "PCF SM Policy Control", "spec": "TS 29.512", "nf": "PCF"},
            {"path": "/npcf-am-policy-control/v1", "name": "PCF AM Policy Control", "spec": "TS 29.507", "nf": "PCF"},
            {"path": "/namf-comm/v1", "name": "AMF Communication", "spec": "TS 29.518", "nf": "AMF"},
            {"path": "/namf-evts/v1", "name": "AMF Event Exposure", "spec": "TS 29.518", "nf": "AMF"},
            {"path": "/nsmf-pdusession/v1", "name": "SMF PDU Session", "spec": "TS 29.502", "nf": "SMF"},
            {"path": "/nsmf-event-exposure/v1", "name": "SMF Event Exposure", "spec": "TS 29.508", "nf": "SMF"},
            {"path": "/nudm-sdm/v2", "name": "UDM Subscriber Data Management", "spec": "TS 29.503", "nf": "UDM"},
            {"path": "/nudm-uecm/v1", "name": "UDM UE Context Management", "spec": "TS 29.503", "nf": "UDM"},
            {"path": "/nausf-auth/v1", "name": "AUSF Authentication", "spec": "TS 29.509", "nf": "AUSF"},
            {"path": "/nnrf-disc/v1", "name": "NRF Discovery", "spec": "TS 29.510", "nf": "NRF"},
            {"path": "/nnrf-nfm/v1", "name": "NRF NF Management", "spec": "TS 29.510", "nf": "NRF"},
        ]
    
    # Probe each API endpoint to verify availability
    for api in api_patterns:
        try:
            check_url = f"{base_url}{api['path']}"
            response = requests.head(check_url, timeout=2)
            if response.status_code in [200, 401, 403, 404, 405]:
                discovered_apis.append({
                    "name": api["name"],
                    "path": api["path"],
                    "spec": api["spec"],
                    "nf": api["nf"],
                    "available": response.status_code in [200, 401, 405]
                })
        except requests.exceptions.RequestException:
            pass
    
    return discovered_apis


# CAPIF Service Registry endpoint
@app.get("/services")
async def get_registered_services(filter_camara: bool = True):
    """
    Get list of registered CAMARA API services (CAPIF-style)
    Returns information about available APIs for service discovery
    Dynamically builds service list from environment configuration
    
    Args:
        filter_camara: If True (default), return only services utilized by CAMARA APIs.
                      If False, return all discovered services.
    """
    services = []
    
    # Get environment variables
    tf_sdk_base = os.getenv("TF_SDK_BASE_URL", "http://tf-sdk-api:8200")
    nef_qod_base = os.getenv("NEF_QOD_BASE_URL")
    nef_location_base = os.getenv("NEF_LOCATION_BASE_URL")
    nef_ti_base = os.getenv("NEF_TI_BASE_URL")
    core_network_base = os.getenv("CORE_NETWORK_BASE_URL")
    coresim_base = os.getenv("CORESIM_BASE_URL")
    
    # Fetch dynamic release information
    camara_releases = get_camara_api_releases()
    
    # TF-SDK API Gateway (always present)
    services.append({
        "apiId": "tf-sdk-api",
        "apiName": "TF-SDK API Gateway",
        "version": "v1",
        "baseUrl": tf_sdk_base,
        "description": "CAMARA API Gateway powered by TF-SDK - QoD, Location, Traffic Influence, Number Verification",
        "apiType": "CAMARA",
        "release": f"CAMARA (QoD: {camara_releases.get('qualityOnDemand', 'latest')}, Location: {camara_releases.get('deviceLocation', 'latest')}, Traffic: {camara_releases.get('trafficInfluence', 'latest')}, NumberVerify: {camara_releases.get('numberVerification', 'latest')})",
        "specUrl": None,  # Use individual CAMARA API specs below
        "camaraApis": {
            "qualityOnDemand": {
                "spec": "https://github.com/camaraproject/QualityOnDemand",
                "openapi": "https://github.com/camaraproject/QualityOnDemand/blob/main/code/API_definitions/quality-on-demand.yaml",
                "release": camara_releases.get("qualityOnDemand", "latest")
            },
            "deviceLocation": {
                "spec": "https://github.com/camaraproject/DeviceLocation",
                "openapi": "https://github.com/camaraproject/DeviceLocation/blob/main/code/API_definitions/location-retrieval.yaml",
                "release": camara_releases.get("deviceLocation", "latest")
            },
            "trafficInfluence": {
                "spec": "https://github.com/camaraproject/TrafficInfluence",
                "openapi": "https://github.com/camaraproject/TrafficInfluence/blob/main/code/API_definitions/traffic-influence.yaml",
                "release": camara_releases.get("trafficInfluence", "latest")
            },
            "numberVerification": {
                "spec": "https://github.com/camaraproject/NumberVerification",
                "openapi": "https://github.com/camaraproject/NumberVerification/blob/main/code/API_definitions/number-verification.yaml",
                "release": camara_releases.get("numberVerification", "latest")
            }
        },
        "endpoints": {
            "qodSessions": {
                "method": "POST", 
                "path": "/quality-on-demand/v1/sessions",
                "description": "Create QoD session for guaranteed bandwidth",
                "interactsWith": ["3gpp-as-session-with-qos", "PCF", "SMF"]
            },
            "qodSessionsGet": {
                "method": "GET",
                "path": "/quality-on-demand/v1/sessions/{sessionId}",
                "description": "Get QoD session details"
            },
            "qodSessionsDelete": {
                "method": "DELETE",
                "path": "/quality-on-demand/v1/sessions/{sessionId}",
                "description": "Delete QoD session"
            },
            "locationRetrieval": {
                "method": "POST",
                "path": "/location-retrieval/v0/retrieve",
                "description": "Retrieve device location (cell/area)",
                "interactsWith": ["3gpp-monitoring-event", "AMF", "UDM"]
            },
            "trafficInfluence": {
                "method": "POST",
                "path": "/traffic-influence/v1/subscriptions",
                "description": "Create traffic influence subscription",
                "interactsWith": ["3gpp-traffic-influence", "PCF", "UPF"]
            },
            "trafficInfluenceGet": {
                "method": "GET",
                "path": "/traffic-influence/v1/subscriptions/{subscriptionId}",
                "description": "Get traffic influence subscription"
            },
            "trafficInfluenceDelete": {
                "method": "DELETE",
                "path": "/traffic-influence/v1/subscriptions/{subscriptionId}",
                "description": "Delete traffic influence subscription"
            },
            "numberVerification": {
                "method": "POST",
                "path": "/number-verification/v0/verify",
                "description": "Verify if phone number matches device",
                "interactsWith": ["ue-identity-service", "Redis"]
            },
            "devicePhoneNumber": {
                "method": "GET",
                "path": "/number-verification/v0/device-phone-number",
                "description": "Get phone number associated with device IP",
                "interactsWith": ["ue-identity-service", "Redis"]
            }
        }
    })
    
    # Dynamically discover NEF APIs (check all configured NEF bases)
    nef_bases = []
    if nef_qod_base:
        nef_bases.append(("nef-qos", nef_qod_base))
    if nef_location_base:
        nef_bases.append(("nef-location", nef_location_base))
    if nef_ti_base:
        nef_bases.append(("nef-traffic", nef_ti_base))
    
    # Discover APIs from each NEF instance
    discovered_nef_apis = {}
    for nef_id, nef_base in nef_bases:
        discovered = discover_nef_apis(nef_base, nef_id)
        for api in discovered:
            api_key = f"{api['path'].split('/')[1]}_{nef_id}"  # e.g., 3gpp-as-session-with-qos_nef-qos
            if api_key not in discovered_nef_apis:
                discovered_nef_apis[api_key] = {
                    "api": api,
                    "baseUrl": nef_base,
                    "nefId": nef_id
                }
    
    # Add discovered NEF APIs as services with detailed endpoints
    for api_key, info in discovered_nef_apis.items():
        api = info["api"]
        api_path_parts = api["path"].split("/")
        api_id = api_path_parts[1] if len(api_path_parts) > 1 else api_key
        
        # Build detailed endpoints based on API type
        endpoints = {}
        resources_used = []
        
        if "as-session-with-qos" in api_id:
            endpoints = {
                "create": {
                    "method": "POST",
                    "path": f"{api['path']}/subscriptions",
                    "description": "Create QoS session subscription"
                },
                "get": {
                    "method": "GET",
                    "path": f"{api['path']}/subscriptions/{{subscriptionId}}",
                    "description": "Get QoS session subscription"
                },
                "update": {
                    "method": "PUT",
                    "path": f"{api['path']}/subscriptions/{{subscriptionId}}",
                    "description": "Update QoS session"
                },
                "delete": {
                    "method": "DELETE",
                    "path": f"{api['path']}/subscriptions/{{subscriptionId}}",
                    "description": "Delete QoS session"
                }
            }
            resources_used = ["PCF (Policy Control)", "SMF (Session Mgmt)"]
        elif "monitoring-event" in api_id:
            endpoints = {
                "subscribe": {
                    "method": "POST",
                    "path": f"{api['path']}/subscriptions",
                    "description": "Subscribe to monitoring events"
                },
                "get": {
                    "method": "GET",
                    "path": f"{api['path']}/subscriptions/{{subscriptionId}}",
                    "description": "Get monitoring subscription"
                },
                "delete": {
                    "method": "DELETE",
                    "path": f"{api['path']}/subscriptions/{{subscriptionId}}",
                    "description": "Delete monitoring subscription"
                }
            }
            resources_used = ["Redis (UE Data Cache)", "Identity Service (External ID resolution - UDM replacement)"]
        elif "traffic-influence" in api_id:
            endpoints = {
                "create": {
                    "method": "POST",
                    "path": f"{api['path']}/subscriptions",
                    "description": "Create traffic influence subscription"
                },
                "get": {
                    "method": "GET",
                    "path": f"{api['path']}/subscriptions/{{subscriptionId}}",
                    "description": "Get traffic influence subscription"
                },
                "update": {
                    "method": "PATCH",
                    "path": f"{api['path']}/subscriptions/{{subscriptionId}}",
                    "description": "Update traffic routing rules"
                },
                "delete": {
                    "method": "DELETE",
                    "path": f"{api['path']}/subscriptions/{{subscriptionId}}",
                    "description": "Delete traffic influence subscription"
                }
            }
            resources_used = ["PCF (Policy Control)", "SMF (Session Mgmt)"]
        else:
            endpoints = {
                "discovered": {"method": "POST", "path": api["path"]}
            }
        
        # Build spec URL based on the specification number - use main 5G_APIs repo
        spec_url = "https://forge.3gpp.org/rep/all/5G_APIs"
        
        services.append({
            "apiId": api_id,
            "apiName": f"3GPP {api['name']}",
            "version": api["path"].split("/")[-1] if "/" in api["path"] else "v1",
            "baseUrl": info["baseUrl"],
            "description": f"NEF API for {api['name']} (Discovered from {info['nefId']})",
            "apiType": "3GPP-NEF",
            "release": get_3gpp_release_from_spec(api["spec"]),
            "specification": api["spec"],
            "specUrl": spec_url,
            "endpoints": endpoints,
            "resourcesUsed": resources_used,
            "discoveryStatus": "available" if api.get("available") else "detected"
        })
    
    # Dynamically discover Core Network APIs
    if core_network_base:
        discovered_core_apis = discover_core_network_apis(core_network_base)
        
        if discovered_core_apis:
            # Group by NF type
            nf_groups = {}
            for api in discovered_core_apis:
                nf = api["nf"]
                if nf not in nf_groups:
                    nf_groups[nf] = []
                nf_groups[nf].append(api)
            
            # Create a service for each NF with its discovered APIs
            for nf, apis in nf_groups.items():
                endpoints = {}
                specs = set()
                for api in apis:
                    endpoint_key = api["path"].split("/")[-1] or api["name"].lower().replace(" ", "_")
                    endpoints[endpoint_key] = {"method": "POST", "path": api["path"]}
                    specs.add(api["spec"])
                
                services.append({
                    "apiId": f"core-{nf.lower()}",
                    "apiName": f"5GC {nf} Services",
                    "version": "v1",
                    "baseUrl": core_network_base,
                    "description": f"Discovered {nf} APIs from 5G Core Network ({len(apis)} APIs found)",
                    "apiType": "3GPP-5GC",
                    "release": get_3gpp_release_from_spec(list(specs)[0] if specs else "TS 29.500"),
                    "specification": ", ".join(sorted(specs)),
                    "specUrl": "https://forge.3gpp.org/rep/all/5G_APIs",
                    "endpoints": endpoints,
                    "discoveredApis": [{"name": api["name"], "path": api["path"], "spec": api["spec"]} for api in apis],
                    "discoveryStatus": "available"
                })
        else:
            # Fallback to single service if no APIs discovered
            services.append({
                "apiId": "core-network-service",
                "apiName": "Core Network Service",
                "version": "v1",
                "baseUrl": core_network_base,
                "description": "NEF southbound interface to 5GC (No APIs auto-discovered)",
                "apiType": "3GPP-5GC",
                "release": "3GPP Release 18",
                "specUrl": None,
                "endpoints": {
                    "pcfPolicy": {"method": "POST", "path": "/pcf/policy"},
                    "amfSubscription": {"method": "POST", "path": "/eventsubscriptions/amf"},
                    "smfSubscription": {"method": "POST", "path": "/eventsubscriptions/smf"}
                },
                "discoveryStatus": "fallback"
            })
    
    # CoreSim (if configured)
    if coresim_base:
        services.append({
            "apiId": "core-simulator",
            "apiName": "CoreSim 5G Simulator",
            "version": "v1",
            "baseUrl": coresim_base,
            "description": "5G Core Network Simulator - Active: PCF, IPAM, Redis | Implemented: AMF, SMF, NRF",
            "apiType": "Simulator",
            "release": "v1.0.0",
            "specUrl": None,
            "endpoints": {
                "status": {
                    "method": "GET",
                    "path": "/status",
                    "description": "Get simulator status and registered UEs"
                },
                "metrics": {
                    "method": "GET",
                    "path": "/metrics",
                    "description": "Get Prometheus metrics"
                },
                "config": {
                    "method": "GET",
                    "path": "/config",
                    "description": "Get core configuration (PLMN, slices, gNBs)"
                },
                "pcfPolicyAuth": {
                    "method": "POST",
                    "path": "/npcf-policyauthorization/v1/app-sessions",
                    "description": "Create PCF policy authorization (3GPP TS 29.514)"
                },
                "pcfPolicyDelete": {
                    "method": "POST",
                    "path": "/npcf-policyauthorization/v1/app-sessions/{appSessId}/delete",
                    "description": "Delete PCF policy authorization"
                },
                "smfEventSubscribe": {
                    "method": "POST",
                    "path": "/nsmf-event-exposure/v1/subscriptions",
                    "description": "Subscribe to SMF events (3GPP TS 29.508)"
                },
                "amfEventSubscribe": {
                    "method": "POST",
                    "path": "/namf-evts/v1/subscriptions",
                    "description": "Subscribe to AMF events (3GPP TS 29.518)"
                }
            },
            "networkFunctions": [
                {
                    "name": "PCF",
                    "description": "Policy Control - QoS policies, traffic routing rules, UE validation",
                    "usedBy": ["QoD API", "Traffic Influence API"],
                    "status": "active"
                },
                {
                    "name": "IPAM",
                    "description": "IP Address Management - UE IP allocation and validation",
                    "usedBy": ["QoD API", "Traffic Influence API"],
                    "status": "active"
                },
                {
                    "name": "Redis",
                    "description": "Data Cache - Stores UE location and event data",
                    "usedBy": ["Location API"],
                    "status": "active"
                },
                {
                    "name": "AMF",
                    "description": "Access and Mobility Management - UE registration, location tracking",
                    "usedBy": [],
                    "status": "inactive - data via Redis"
                },
                {
                    "name": "SMF",
                    "description": "Session Management - PDU session management, IP allocation",
                    "usedBy": [],
                    "status": "inactive - data via IPAM"
                },
                {
                    "name": "NRF",
                    "description": "NF Repository Function - Service discovery (useNrf=false)",
                    "usedBy": [],
                    "status": "inactive - direct PCF connection"
                }
            ]
        })
    
    # UE Identity Service (for Number Verification API)
    ue_identity_base = os.getenv("UE_IDENTITY_SERVICE_URL", "http://ue-identity-service:8090")
    services.append({
        "apiId": "ue-identity-service",
        "apiName": "UE Identity Service",
        "version": "v1",
        "baseUrl": ue_identity_base,
        "description": "Resolves external IDs (MSISDN/phone numbers) to network identifiers - Used by Number Verification API",
        "apiType": "Internal",
        "release": "v1.0.0",
        "specUrl": None,
        "endpoints": {
            "resolveIdentity": {
                "method": "POST",
                "path": "/identity/resolve",
                "description": "Resolve external ID (phone number) to network identity"
            },
            "getPhoneNumber": {
                "method": "GET",
                "path": "/identity/phone-number",
                "description": "Get phone number associated with device IP"
            },
            "verifyPhoneNumber": {
                "method": "POST",
                "path": "/identity/verify",
                "description": "Verify if phone number matches device"
            }
        },
        "resourcesUsed": ["Redis (UE Data Cache)", "CoreSim (UE Registration Data)"]
    })
    
    # Filter services to only show CAMARA-utilized ones if requested
    if filter_camara:
        # Define the services that are actually used by CAMARA APIs
        camara_utilized_services = {
            "tf-sdk-api",  # Main CAMARA API Gateway
            "3gpp-as-session-with-qos",  # Used by QoD API (interacts with PCF/IPAM)
            "3gpp-monitoring-event",  # Used by Location API (interacts with Redis)
            "3gpp-traffic-influence",  # Used by Traffic Influence API (interacts with PCF/IPAM)
            "ue-identity-service",  # Used by Number Verification API (resolves phone numbers)
            "core-simulator",  # CoreSim 5G Simulator (PCF, IPAM, Redis active)
        }
        
        # Filter services based on apiId and remove duplicates
        filtered_services = []
        seen_api_ids = set()
        
        for service in services:
            api_id = service.get("apiId", "")
            # Check if service is in the utilized list and not already added
            if api_id in camara_utilized_services and api_id not in seen_api_ids:
                filtered_services.append(service)
                seen_api_ids.add(api_id)
        
        return filtered_services
    
    return services


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8200, log_level="info")
