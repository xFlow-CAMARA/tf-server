#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CoreSim OAM (Operations and Maintenance) API Example

This example demonstrates how to control and monitor CoreSim simulations
using the OAM APIs through the TF SDK.
"""

from sunrise6g_opensdk.common.sdk import Sdk as sdkclient
import json
import time


def main():
    print("\n" + "=" * 70)
    print("CoreSim OAM (Operations and Maintenance) API Example")
    print("=" * 70)

    # Initialize CoreSim adapter
    adapter_specs = {
        "network": {
            "client_name": "coresim",
            "base_url": "http://localhost:8080",
            "scs_as_id": "nef",
            "oam_port": 8081,
            "redis_addr": "localhost:6380",
            "nef_callback_url": "http://localhost:9092/eventsubscriptions"
        }
    }

    try:
        adapters = sdkclient.create_adapters_from(adapter_specs)
        network_client = adapters.get("network")
        print("\n✓ Network client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return

    # Get Initial Status
    try:
        print("\n--- Getting Initial CoreSim Status ---")
        status = network_client.get_status()
        print(f"✓ CoreSim Status: {json.dumps(status, indent=2)}")

    except Exception as e:
        print(f"✗ Failed to get status: {e}")
        return

    # Configure Simulation
    try:
        print("\n--- Configuring CoreSim Simulation ---")
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
                "numOfUe": 10,      # 10 UEs
                "numOfgNB": 5,      # 5 gNBs
                "arrivalRate": 2    # 2 UEs arriving per time unit
            }
        }

        response = network_client.configure_simulation(config)
        print(f"✓ Simulation configured")
        print(f"  UEs: {config['simulationProfile']['numOfUe']}")
        print(f"  gNBs: {config['simulationProfile']['numOfgNB']}")
        print(f"  Arrival Rate: {config['simulationProfile']['arrivalRate']}")

    except Exception as e:
        print(f"✗ Failed to configure simulation: {e}")
        return

    # Get Status After Configuration
    try:
        print("\n--- Getting Status After Configuration ---")
        status = network_client.get_status()
        print(f"✓ CoreSim Status: {json.dumps(status, indent=2)}")

    except Exception as e:
        print(f"✗ Failed to get status: {e}")

    # Start Simulation
    try:
        print("\n--- Starting CoreSim Simulation ---")
        response = network_client.start_simulation()
        print(f"✓ Simulation started")
        print(f"  Response: {json.dumps(response, indent=2)}")

    except Exception as e:
        print(f"✗ Failed to start simulation: {e}")
        return

    # Monitor Simulation (simulate running for a few seconds)
    try:
        print("\n--- Monitoring Simulation (10 seconds) ---")
        for i in range(5):
            time.sleep(2)
            status = network_client.get_status()
            print(f"[{i+1}] Status: {json.dumps(status, indent=2)}")

    except Exception as e:
        print(f"✗ Failed to monitor simulation: {e}")

    # Stop Simulation
    try:
        print("\n--- Stopping CoreSim Simulation ---")
        response = network_client.stop_simulation()
        print(f"✓ Simulation stopped")
        print(f"  Response: {json.dumps(response, indent=2)}")

    except Exception as e:
        print(f"✗ Failed to stop simulation: {e}")

    # Get Final Status
    try:
        print("\n--- Getting Final CoreSim Status ---")
        status = network_client.get_status()
        print(f"✓ Final CoreSim Status: {json.dumps(status, indent=2)}")

    except Exception as e:
        print(f"✗ Failed to get final status: {e}")

    print("\n" + "=" * 70)
    print("OAM API Example Completed Successfully")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
