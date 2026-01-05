<a href="https://labs.etsi.org/rep/oop/code/tf-sdk/-/pipelines" title="Pipeline Status">
  <img src="https://labs.etsi.org/rep/oop/code/tf-sdk/badges/main/pipeline.svg" alt="pipeline status">
</a>
</a>
<a href="https://labs.etsi.org/rep/oop/code/tf-sdk/-/blob/main/LICENSE" title="License">
  <img src="https://img.shields.io/badge/License-Apache%202.0-green.svg?style=plastic" alt="license">
</a>


# TF SDK

Open source SDK to abstract CAMARA/GSMA Transformation Functions (TFs) for Edge Cloud platforms, 5G network cores and O-RAN solutions.

## Features

- Abstract CAMARA NBI & GSMA E/WBI Transformation Functions (TFs)
- Unified Python SDK for interacting with Edge Cloud platforms, 5G Core solutions, and O-RAN controllers.
- Modular and extensible adapter structure


---

## API & Platform Support Matrix

### CAMARA APIs

| API Name                  | Version |
|---------------------------|---------|
| Edge Application Management | [v0.9.3-wip (commit: 79aa595)](https://github.com/camaraproject/EdgeCloud/blob/79aa5951d64391422ea5b861ab617a9540386092/code/API_definitions/Edge-Application-Management.yaml) |
| Quality-on-Demand         | [v1.0.0](https://raw.githubusercontent.com/camaraproject/QualityOnDemand/refs/tags/r2.2/code/API_definitions/quality-on-demand.yaml) |
| Location Retrieval        | [v0.4.0](https://raw.githubusercontent.com/camaraproject/DeviceLocation/refs/tags/r2.2/code/API_definitions/location-retrieval.yaml) |
| Traffic Influence         | [v0.8.1](https://raw.githubusercontent.com/camaraproject/EdgeCloud/v0.8.1/code/API_definitions/Traffic_Influence.yaml) |

### Federation APIs (E/WBI GSMA OPG)

| API Name                  | Version |
|---------------------------|---------|
|  Federation Management Service | [1.2.0](https://www.gsma.com/solutions-and-impact/technologies/networks/wp-content/uploads/2023/07/OPG.04-v3.0-GSMA-Operator-Platform-Group-East-Westbound-Interface-APIs-Version-3.0.pdf)

### EdgeCloud Platforms

| Platform   | Supported     |
|------------|------------|
| Kubernetes | ✅  |
| i2Edge     | ✅  |
| aerOS      | ✅  |

### Network Adapters

| Platform     | NEF Version | QoD | Location Retrieval | Traffic Influence |
|--------------|-------------|-----|---------------------|--------------------|
| Open5GS      | [v1.2.3](https://www.3gpp.org/ftp/Specs/archive/29_series/29.122/29122-hc0.zip) TS 29.122 (v17.12.0) | ✅  | ✅                  |                  |
| Open5GCore   | [v1.2.3](https://www.3gpp.org/ftp/Specs/archive/29_series/29.122/29122-hc0.zip) TS 29.122 (v17.12.0) | ✅  |                   |                  |
| OAI          | [v1.2.3](https://www.3gpp.org/ftp/Specs/archive/29_series/29.122/29122-hc0.zip) TS 29.122 (v17.12.0) | ✅  |                   | ✅                 |

### O-RAN Adapters

| Platform   | Supported     |
|------------|------------|
| Juniper O-RAN controller | WIP  |
| i2CAT O-RAN controller     | ✅  |


### O-RAN Platforms

| Platform         | Status  | CAMARA QoD |
|------------------|---------|------------|
| i2CAT RIC & NEF  |    ✅   |    ✅     |
| Juniper          |    ❌   |    ❌     |


---

## How to Use

### Option 1: Install via PyPI

For end users:

```bash
pip install sunrise6g-opensdk
```

### Option 2: Development Mode

If you plan to modify the SDK:

```bash
git clone https://labs.etsi.org/rep/oop/code/tf-sdk.git
cd tf-sdk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Basic Usage

You can use the SDK by simply specifying the adapters to be used. E.g. Edge Cloud Platform: i2Edge, 5G core: Open5Gs

Example available in [`/examples/example.py`](examples/example.py)

```python
python3 -m examples.example
```

---

## How to Contribute

We welcome contributions to OpenSDK!

To get started:

1. Fork the repository and create a branch from `main`.
2. Add your changes in the appropriate adapter directory.
3. Write or update tests for your changes.
4. Ensure all tests and pre-commit checks pass.
5. Submit a pull request with a clear description.

Please follow our full [Contributing Guidelines](docs/CONTRIBUTING.md) for further details.

---

## Example Workflow #1: App deployment over Kubernetes

```mermaid
sequenceDiagram
title Application Deployment using the TF SDK

actor AP as Application Vertical Provider
box Module implementing CAMARA APIs
    participant API as CAMARA Edge Application Management API
    participant SDK as TF SDK
end
participant K8s as Kubernetes

note over SDK: [Config] Edge Cloud platform: Kubernetes, IP, Port
API ->> SDK: from sunrise6g_opensdk import Sdk as sdkclient
API ->> SDK: sdkclient.create_adapters_from(configuration)
API ->> SDK: edgecloud_client = adapters.get("edgecloud")
SDK ->> SDK: SDK initialized and ready to be used
note over AP,API: Platform ready to receive CAMARA calls
AP ->> API: POST /app (APP_ONBOARD_MANIFEST)
API ->> SDK: edgecloud_client.onboard_app(APP_ONBOARD_MANIFEST)
SDK ->> K8s: Equivalent dedicated endpoint
AP ->> API: POST /appinstances (APP_ID, APP_ZONES)
API ->> SDK: edgecloud_client.deploy_app(APP_ID, APP_ZONES)
SDK ->> K8s: Equivalent dedicated endpoint
```

## Example Workflow #2: QoS Session Creation over Open5Gs

```mermaid
sequenceDiagram
title QoS Session Creation over Open5GS

actor AP as Application Vertical Provider
box Module implementing CAMARA APIs
    participant API as CAMARA QoS Management API
    participant SDK as TF SDK
end
participant NEF as NEF
participant 5GS as Open5GS

note over SDK: [Config] Network core: Open5Gs, IP, Port
API ->> SDK: from sunrise6g_opensdk import Sdk as sdkclient
API ->> SDK: sdkclient.create_adapters_from(configuration)
API ->> SDK: network_client = adapters.get("network")
SDK ->> SDK: SDK initialized and ready to be used
note over AP,API: Platform ready to receive CAMARA calls
AP ->> API: POST /sessions (QOS_SESSION_REQUEST)
API ->> SDK: network_client.create_qos_session(QOS_SESSION_REQUEST)
SDK ->> NEF: Equivalent endpoint
NEF ->> 5GS: QoS session creation
```
---

## Roadmap for Open SDK 2nd release

- [ ] Add support to GSMA OPG.02 TFs
- [x] Include JUNIPER O-RAN adapter

---

## License

Apache 2.0 License – see [`LICENSE`](LICENSE) file for details.
