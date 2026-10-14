#!/usr/bin/env python3
"""
SKHY - TAMI Multi-Tier System Orchestrator & End-to-End Test Benchmark
Launches Level 1 Edge Node, Level 3 Middleware Hub, Level 4/5 Digital Twin, Data Lake API,
Synthetic Sensor Generator, and Interactive Tutorial Viewer.
Runs interactively until the user presses Ctrl+C.
"""

import sys
import os
import time
import subprocess
import webbrowser
import requests
import h5py

def main():
    print("=========================================================================")
    print(" SKHY - TAMI ENTERPRISE I&C STACK & MULTI-REACTOR DIGITAL TWIN")
    print(" Purdue Model Levels 0-5 | Zero-Trust & IEC 62443 Security Architecture")
    print("=========================================================================\n")

    root_dir = os.path.abspath(os.path.dirname(__file__))

    # Find executables
    edge_bin = os.path.join(root_dir, "edge_quench", "target", "release", "edge_quench.exe")
    if not os.path.exists(edge_bin):
        edge_bin = os.path.join(root_dir, "edge_quench", "target", "debug", "edge_quench.exe")

    hub_bin = os.path.join(root_dir, "middleware_hub", "target", "release", "middleware_hub.exe")
    if not os.path.exists(hub_bin):
        hub_bin = os.path.join(root_dir, "middleware_hub", "target", "debug", "middleware_hub.exe")

    processes = []

    # Ensure port 8000 is clear on Windows
    try:
        subprocess.run(
            ["powershell", "-Command", "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
            capture_output=True
        )
    except Exception:
        pass

    try:
        # 1. Start Level 1 Edge Quench Protection Node
        if os.path.exists(edge_bin):
            print("[+] [STEP 1] Starting Level 1 Edge Quench Protection Module (Rust/MTCA.4)...")
            p_edge = subprocess.Popen([edge_bin], cwd=os.path.join(root_dir, "edge_quench"))
            processes.append(p_edge)
            time.sleep(1.0)
        else:
            print("[!] [STEP 1] edge_quench binary not found, continuing with Level 4/5 stack...")

        # 2. Start Level 3 TAMI Middleware Hub
        if os.path.exists(hub_bin):
            print("[+] [STEP 2] Starting Level 3 Supervisory Control Middleware Hub (Rust)...")
            p_hub = subprocess.Popen([hub_bin], cwd=os.path.join(root_dir, "middleware_hub"))
            processes.append(p_hub)
            time.sleep(1.0)
        else:
            print("[!] [STEP 2] middleware_hub binary not found, continuing with Level 4/5 stack...")

        # 3. Start Level 4/5 Data Lake REST & GraphQL API (also serves the Tutorial Web Studio)
        print("[+] [STEP 3] Starting Level 4/5 Data Lake API & Tutorial Server (FastAPI)...")
        api_script = os.path.join(root_dir, "data_lake_api", "ai_ingestion_api.py")
        p_api = subprocess.Popen([sys.executable, api_script], cwd=root_dir)
        processes.append(p_api)
        time.sleep(2.5)

        # 4. Start Level 4/5 Digital Twin Multi-Physics Engine
        print("[+] [STEP 4] Starting Level 4/5 Digital Twin PINN Engine (PyTorch)...")
        dt_script = os.path.join(root_dir, "digital_twin", "digital_twin_engine.py")
        p_dt = subprocess.Popen([sys.executable, dt_script], cwd=root_dir)
        processes.append(p_dt)
        time.sleep(1.0)

        # 5. Start Level 0/1 Synthetic Telemetry Generator (Continuous multi-reactor streaming)
        print("[+] [STEP 5] Starting Level 0/1 Synthetic Telemetry Generator (Continuous stream)...")
        gen_script = os.path.join(root_dir, "synthetic_generator", "synthetic_data_gen.py")
        p_gen = subprocess.Popen([sys.executable, gen_script, "--freq", "25.0", "--mode", "cycle", "--cycle-interval", "10.0"], cwd=root_dir)
        processes.append(p_gen)

        print("\n[*] Waiting for data pipelines to initialize...")
        time.sleep(3.0)

        # 6. Perform REST & GraphQL Verification Queries
        print("\n=========================================================================")
        print(" AGENTIC AI DATA LAKE & MULTI-PHYSICS API VERIFICATION RESULTS")
        print("=========================================================================")

        try:
            # Test Health Endpoint
            res = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=3).json()
            print(f"\n[REST /health]: Status = {res.get('status')} | Ingested frames = {res.get('buffer_size')} | Quench incidents = {res.get('quench_events_logged')}")

            # Test Available Reactors Endpoint
            res_reactors = requests.get("http://127.0.0.1:8000/api/v1/reactors", timeout=3).json()
            print(f"[REST /reactors]: Active = {res_reactors.get('active_reactor')} | Supported topologies = {[r['id'] for r in res_reactors.get('reactors', [])]}")

            # Test Multi-Subsystem REST Endpoint
            res_sub = requests.get("http://127.0.0.1:8000/api/v1/subsystems/latest", timeout=3).json()
            print(f"[REST /subsystems/latest]: Topology = {res_sub.get('reactor_type')} | Mode = {res_sub.get('active_mode')}")
            if "coil_cryo" in res_sub:
                print(f"  * Subsystem 1 (Coils & Cryo): Temp = {res_sub['coil_cryo']['coil_temperature_k']}K | Margin = {res_sub['coil_cryo']['quench_margin_k']}K")
            if "plasma_core" in res_sub:
                print(f"  * Subsystem 2 (Plasma Core): Te = {res_sub['plasma_core']['electron_temp_kev']} keV | Beta = {res_sub['plasma_core']['toroidal_beta_percent']}%")
            if "power_balance" in res_sub:
                print(f"  * Subsystem 5 (Power Balance): Q_sci = {res_sub['power_balance']['scientific_gain_q_sci']} | P_net = {res_sub['power_balance']['net_electric_power_mw']} MW")

            # Test GraphQL Query for Subsystem Report
            gql_query = """
            query {
              latestSubsystemReport {
                reactorType
                activeMode
                modeDescription
                powerBalance { scientificGainQSci, netElectricPowerMw, netElectricityAchieved }
              }
            }
            """
            gql_res = requests.post("http://127.0.0.1:8000/graphql", json={"query": gql_query}, timeout=3).json()
            print(f"\n[GraphQL /graphql Report]: Agentic AI Query Result ->\n  {gql_res.get('data', {}).get('latestSubsystemReport')}")
        except Exception as e:
            print(f"[!] API verification warning: {e}")

        # 7. Open Browser to Mission Control & Digital Twin
        twin_url = "http://127.0.0.1:8000/"
        manual_url = "http://127.0.0.1:8000/manual"
        print("\n=========================================================================")
        print(" [LIVE SERVICES ACTIVE] TAMI MISSION CONTROL & 3D DIGITAL TWIN")
        print("=========================================================================")
        print(f"[+] Launching Mission Control in browser: {twin_url}")
        print("    * View 1: 3D Multi-Reactor Twin & Subsystem Telemetry")
        print("    * View 2: 2D Energy Balance (Sankey Flow & Presets)")
        print("    * View 3: Edge Interlock & REBCO Quench Simulator")
        print("    * View 4: Purdue 6-Tier Architecture Inspector")
        print("\n[*] Available interactive endpoints:")
        print(f"    - Mission Control:     {twin_url}")
        print(f"    - Engineering Manual:  {manual_url}")
        print("    - REST API Docs:       http://127.0.0.1:8000/api/docs")
        print("    - GraphQL Console:     http://127.0.0.1:8000/graphql")
        print("\n[!] Multi-reactor services are running interactively.")
        print("[!] Press Ctrl+C in this terminal to stop all services.\n")

        try:
            webbrowser.open(twin_url)
        except Exception:
            pass

        # 8. Interactive Execution Loop (Heartbeat)
        heartbeat_count = 0
        while True:
            time.sleep(2.0)
            heartbeat_count += 1
            # Check child processes health
            for p in processes:
                if p.poll() is not None:
                    # A process exited unexpectedly, continue or log
                    pass

    except KeyboardInterrupt:
        print("\n\n[!] KeyboardInterrupt received. Gracefully shutting down all TAMI services...")
    finally:
        print("[SYSTEM] Terminating active processes and releasing port handles...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(0.5)

        # Verify HDF5 Data Lake File
        h5_file = "tami_data_lake.h5"
        if os.path.exists(h5_file):
            try:
                with h5py.File(h5_file, "r") as f:
                    if "quench_telemetry" in f:
                        records_count = len(f["quench_telemetry"])
                        print(f"[HDF5 Storage]: Persisted {records_count} telemetry frames in '{h5_file}'")
            except Exception as e:
                print(f"[HDF5 Storage]: HDF5 data lake archive available at '{h5_file}'")

        print("\n=========================================================================")
        print(" [SHUTDOWN COMPLETE] All TAMI processes successfully stopped.")
        print("=========================================================================\n")

if __name__ == "__main__":
    main()
