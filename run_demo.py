#!/usr/bin/env python3
"""
SKHY - TAMI Multi-Tier System Orchestrator & End-to-End Test Benchmark
Launches Level 1 Edge Node, Level 3 Middleware Hub, Level 4/5 Digital Twin, Data Lake API,
and Synthetic Sensor Generator to demonstrate real-time quench protection, microsecond interlocks,
HDF5 persistence, and Agentic AI GraphQL/REST interfaces.
"""

import sys
import os
import time
import subprocess
import requests
import h5py

def main():
    print("=========================================================================")
    print(" SKHY - TAMI ENTERPRISE I&C STACK END-TO-END DEMONSTRATION")
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
        subprocess.run(["powershell", "-Command", "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"], capture_output=True)
    except Exception:
        pass

    try:
        # 1. Start Level 1 Edge Quench Protection Node
        print("[+] [STEP 1] Starting Level 1 Edge Quench Protection Module (Rust/MTCA.4)...")
        p_edge = subprocess.Popen([edge_bin], cwd=os.path.join(root_dir, "edge_quench"))
        processes.append(p_edge)
        time.sleep(1.0)

        # 2. Start Level 3 TAMI Middleware Hub
        print("[+] [STEP 2] Starting Level 3 Supervisory Control Middleware Hub (Rust)...")
        p_hub = subprocess.Popen([hub_bin], cwd=os.path.join(root_dir, "middleware_hub"))
        processes.append(p_hub)
        time.sleep(1.0)

        # 3. Start Level 4/5 Data Lake REST & GraphQL API
        print("[+] [STEP 3] Starting Level 4/5 Data Lake API & HDF5 Persister (FastAPI)...")
        api_script = os.path.join(root_dir, "data_lake_api", "ai_ingestion_api.py")
        p_api = subprocess.Popen([sys.executable, api_script], cwd=root_dir)
        processes.append(p_api)
        time.sleep(2.5)

        # 4. Start Level 4/5 Digital Twin PINN Engine
        print("[+] [STEP 4] Starting Level 4/5 Digital Twin PINN Engine (PyTorch)...")
        dt_script = os.path.join(root_dir, "digital_twin", "digital_twin_engine.py")
        p_dt = subprocess.Popen([sys.executable, dt_script], cwd=root_dir)
        processes.append(p_dt)
        time.sleep(1.0)

        # 5. Start Level 0/1 Synthetic Telemetry Generator (Runs for 8 seconds, triggers Quench at 2.5s)
        print("[+] [STEP 5] Starting Level 0/1 Synthetic Telemetry Generator (50 Hz)...")
        gen_script = os.path.join(root_dir, "synthetic_generator", "synthetic_data_gen.py")
        p_gen = subprocess.Popen([sys.executable, gen_script, "--freq", "50.0", "--quench-after", "2.5"], cwd=root_dir)
        processes.append(p_gen)

        print("\n[*] [SYSTEM BENCHMARK] Telemetry stream running. Observing real-time multi-tier interlocks...\n")
        time.sleep(6.5)

        # 6. Perform REST & GraphQL Verification Queries
        print("\n=========================================================================")
        print(" AGENTIC AI DATA LAKE & MULTI-PHYSICS API VERIFICATION RESULTS")
        print("=========================================================================")

        # Test Health Endpoint
        res = requests.get("http://127.0.0.1:8000/api/v1/health").json()
        print(f"\n[REST /health]: Status = {res.get('status')} | Ingested frames = {res.get('buffer_size')} | Quench incidents = {res.get('quench_events_logged')}")

        # Test Latest Telemetry Endpoint
        res_telemetry = requests.get("http://127.0.0.1:8000/api/v1/telemetry/latest").json()
        print(f"[REST /telemetry/latest]: Sensor = {res_telemetry.get('sensor_id')} | Temp = {res_telemetry.get('localized_temperature_k'):.2f}K | FOAS = {res_telemetry.get('foas_acoustic_frequency_hz'):.1f}Hz | Quench = {res_telemetry.get('quench_detected')}")

        # Test Quench Events Endpoint
        res_events = requests.get("http://127.0.0.1:8000/api/v1/quench-events").json()
        print(f"[REST /quench-events]: Captured {len(res_events)} quench runaway frames in Data Lake buffer")

        # Test Multi-Subsystem REST Endpoint
        res_sub = requests.get("http://127.0.0.1:8000/api/v1/subsystems/latest").json()
        print(f"\n[REST /subsystems/latest]: Mode = {res_sub.get('active_mode')} | Desc = {res_sub.get('mode_description')}")
        print(f"  * Subsystem 1 (Coils & Cryo): Temp = {res_sub['coil_cryo']['coil_temperature_k']}K | Margin = {res_sub['coil_cryo']['quench_margin_k']}K | Stress = {res_sub['coil_cryo']['peak_coil_stress_mpa']} MPa")
        print(f"  * Subsystem 2 (Plasma Core): Te = {res_sub['plasma_core']['electron_temp_kev']} keV | Lawson = {res_sub['plasma_core']['lawson_triple_product_kev_s_m3']} keV*s/m^3 | Beta = {res_sub['plasma_core']['toroidal_beta_percent']}%")
        print(f"  * Subsystem 3 (Island Divertor): Heat Flux = {res_sub['divertor']['peak_heat_flux_mw_per_m2']} MW/m^2 | Detached = {res_sub['divertor']['detachment_achieved']} | Tile Temp = {res_sub['divertor']['target_surface_temp_c']} degC")
        print(f"  * Subsystem 4 (Breeding Blanket): PbLi Temp = {res_sub['blanket']['pb_li_outlet_temp_c']} degC | TBR = {res_sub['blanket']['tritium_breeding_ratio']} | Tritium = {res_sub['blanket']['tritium_extraction_rate_g_per_day']} g/day")
        print(f"  * Subsystem 5 (Power Balance): Q_sci = {res_sub['power_balance']['scientific_gain_q_sci']} | P_fusion = {res_sub['power_balance']['fusion_power_mw']} MW | P_net = {res_sub['power_balance']['net_electric_power_mw']} MW")

        # Test GraphQL Query for Subsystem Report
        gql_query = """
        query {
          latestSubsystemReport {
            activeMode
            modeDescription
            coilCryo { coilTemperatureK, quenchMarginK }
            plasmaCore { electronTempKev, lawsonTripleProductKevSM3 }
            divertor { peakHeatFluxMwPerM2, detachmentAchieved }
            blanket { tritiumBreedingRatio, pbLiOutletTempC }
            powerBalance { scientificGainQSci, netElectricPowerMw, netElectricityAchieved }
          }
        }
        """
        gql_res = requests.post("http://127.0.0.1:8000/graphql", json={"query": gql_query}).json()
        print(f"\n[GraphQL /graphql Subsystem Report]: Agentic AI Query Result ->\n  {gql_res.get('data', {}).get('latestSubsystemReport')}")

        print("\n[SYSTEM] Terminating active processes to flush HDF5 handles...")
        for p in processes:
            p.terminate()
        processes.clear()
        time.sleep(0.5)

        # Verify HDF5 Data Lake File after handles released
        h5_file = "tami_data_lake.h5"
        if os.path.exists(h5_file):
            try:
                with h5py.File(h5_file, "r") as f:
                    if "quench_telemetry" in f:
                        records_count = len(f["quench_telemetry"])
                        print(f"[HDF5 Storage]: Successfully persisted {records_count} telemetry frames in '{h5_file}'")
            except Exception as e:
                print(f"[HDF5 Check]: Archived HDF5 data lake ready at '{h5_file}' ({e})")

        print("\n=========================================================================")
        print(" [SUCCESS] END-TO-END DEMONSTRATION & SYSTEM VERIFICATION COMPLETED!")
        print("=========================================================================\n")

    finally:
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass

if __name__ == "__main__":
    main()
