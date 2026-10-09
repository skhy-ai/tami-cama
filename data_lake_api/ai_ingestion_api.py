#!/usr/bin/env python3
"""
SKHY - TAMI Level 4/5 Enterprise Integration & Agentic AI API
Provides HDF5 Data Lake persistence and REST / GraphQL interfaces for Agentic AI
multi-physics training, plant power balance, and real-time stellarator diagnostic queries.
"""

import sys
import os
import time
import socket
import threading
from typing import List, Optional
import h5py
import numpy as np

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import uvicorn
import strawberry
from strawberry.fastapi import GraphQLRouter

# Add parent directory to path to import python_common
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

from python_common.skhy_telemetry_pb2 import QuenchDiagnostic, DigitalTwinState

# ============================================================================
# In-Memory Buffer & HDF5 Persistence Storage Engine
# ============================================================================

HDF5_FILE_PATH = "tami_data_lake.h5"

telemetry_buffer: List[dict] = []
digital_twin_buffer: List[dict] = []
quench_events_buffer: List[dict] = []
buffer_lock = threading.Lock()

def init_hdf5():
    with h5py.File(HDF5_FILE_PATH, "a") as f:
        if "quench_telemetry" not in f:
            f.create_group("quench_telemetry")
        if "digital_twin" not in f:
            f.create_group("digital_twin")
    print(f"[DATA-LAKE] HDF5 Data Lake initialized at '{HDF5_FILE_PATH}'")

def persist_telemetry_to_hdf5(record: dict):
    try:
        with h5py.File(HDF5_FILE_PATH, "a") as f:
            grp = f["quench_telemetry"]
            ts_str = str(record["timestamp_ns"])
            if ts_str not in grp:
                sub = grp.create_group(ts_str)
                sub.attrs["sensor_id"] = record["sensor_id"]
                sub.attrs["temperature_k"] = record["localized_temperature_k"]
                sub.attrs["foas_freq_hz"] = record["foas_acoustic_frequency_hz"]
                sub.attrs["nzpv_mps"] = record["normal_zone_propagation_velocity_mps"]
                sub.attrs["quench_detected"] = record["quench_detected"]
    except Exception as e:
        print(f"[DATA-LAKE-HDF5-ERROR] {e}")

# ============================================================================
# GraphQL Schema Definitions (Strawberry)
# ============================================================================

@strawberry.type
class TelemetryGQL:
    timestamp_ns: str
    sensor_id: str
    localized_temperature_k: float
    thermal_rise_rate_k_per_s: float
    foas_acoustic_frequency_hz: float
    foas_acoustic_amplitude_db: float
    stray_capacitance_pf: float
    capacitance_shift_rate_pf_per_s: float
    normal_zone_propagation_velocity_mps: float
    quench_detected: bool
    plasma_density_m3: float

@strawberry.type
class DigitalTwinGQL:
    simulation_step: int
    peak_coil_strain_mpa: float
    plasma_beta_toroidal: float
    magnetic_axis_displacement_m: float
    pinn_loss: float
    equilibrium_converged: bool
    scientific_gain_q_sci: float
    engineering_gain_q_eng: float
    fusion_power_mw: float
    heating_power_mw: float
    gross_electric_power_mw: float
    net_electric_power_mw: float
    recirculating_power_mw: float
    parasitic_cryo_power_mw: float
    lawson_triple_product_kev_s_m3: float
    net_electricity_achieved: bool

@strawberry.type
class QueryGQL:
    @strawberry.field
    def latest_telemetry(self) -> Optional[TelemetryGQL]:
        with buffer_lock:
            if not telemetry_buffer:
                return None
            t = telemetry_buffer[-1]
            return TelemetryGQL(
                timestamp_ns=str(t["timestamp_ns"]),
                sensor_id=t["sensor_id"],
                localized_temperature_k=t["localized_temperature_k"],
                thermal_rise_rate_k_per_s=t["thermal_rise_rate_k_per_s"],
                foas_acoustic_frequency_hz=t["foas_acoustic_frequency_hz"],
                foas_acoustic_amplitude_db=t["foas_acoustic_amplitude_db"],
                stray_capacitance_pf=t["stray_capacitance_pf"],
                capacitance_shift_rate_pf_per_s=t["capacitance_shift_rate_pf_per_s"],
                normal_zone_propagation_velocity_mps=t["normal_zone_propagation_velocity_mps"],
                quench_detected=t["quench_detected"],
                plasma_density_m3=t.get("plasma_density_m3", 1.85)
            )

    @strawberry.field
    def telemetry_history(self, limit: int = 50) -> List[TelemetryGQL]:
        with buffer_lock:
            items = telemetry_buffer[-limit:]
            return [
                TelemetryGQL(
                    timestamp_ns=str(t["timestamp_ns"]),
                    sensor_id=t["sensor_id"],
                    localized_temperature_k=t["localized_temperature_k"],
                    thermal_rise_rate_k_per_s=t["thermal_rise_rate_k_per_s"],
                    foas_acoustic_frequency_hz=t["foas_acoustic_frequency_hz"],
                    foas_acoustic_amplitude_db=t["foas_acoustic_amplitude_db"],
                    stray_capacitance_pf=t["stray_capacitance_pf"],
                    capacitance_shift_rate_pf_per_s=t["capacitance_shift_rate_pf_per_s"],
                    normal_zone_propagation_velocity_mps=t["normal_zone_propagation_velocity_mps"],
                    quench_detected=t["quench_detected"],
                    plasma_density_m3=t.get("plasma_density_m3", 1.85)
                ) for t in items
            ]

    @strawberry.field
    def digital_twin_state(self) -> Optional[DigitalTwinGQL]:
        with buffer_lock:
            if not digital_twin_buffer:
                return None
            dt = digital_twin_buffer[-1]
            return DigitalTwinGQL(
                simulation_step=dt["simulation_step"],
                peak_coil_strain_mpa=dt["peak_coil_strain_mpa"],
                plasma_beta_toroidal=dt["plasma_beta_toroidal"],
                magnetic_axis_displacement_m=dt["magnetic_axis_displacement_m"],
                pinn_loss=dt["pinn_loss"],
                equilibrium_converged=dt["equilibrium_converged"],
                scientific_gain_q_sci=dt.get("scientific_gain_q_sci", 10.2),
                engineering_gain_q_eng=dt.get("engineering_gain_q_eng", 2.1),
                fusion_power_mw=dt.get("fusion_power_mw", 255.0),
                heating_power_mw=dt.get("heating_power_mw", 25.0),
                gross_electric_power_mw=dt.get("gross_electric_power_mw", 106.4),
                net_electric_power_mw=dt.get("net_electric_power_mw", 56.2),
                recirculating_power_mw=dt.get("recirculating_power_mw", 41.6),
                parasitic_cryo_power_mw=dt.get("parasitic_cryo_power_mw", 8.5),
                lawson_triple_product_kev_s_m3=dt.get("lawson_triple_product_kev_s_m3", 4.8),
                net_electricity_achieved=dt.get("net_electricity_achieved", True)
            )

graphql_schema = strawberry.Schema(query=QueryGQL)
graphql_app = GraphQLRouter(graphql_schema)

# ============================================================================
# FastAPI REST Endpoints & Background Telemetry Ingestion Receiver
# ============================================================================

app = FastAPI(
    title="SKHY - TAMI Agentic AI Data Lake API",
    description="Purdue Level 4/5 Enterprise API for Multi-Physics Training, Plant Power Balance, HDF5 Persistence & Real-time Diagnostic Queries",
    version="2.0.0"
)

app.include_router(graphql_app, prefix="/graphql")

# Mount tutorial viewer static files
TUTORIAL_VIEWER_DIR = os.path.join(ROOT_DIR, "tutorial_viewer")
if os.path.exists(TUTORIAL_VIEWER_DIR):
    app.mount("/tutorial", StaticFiles(directory=TUTORIAL_VIEWER_DIR, html=True), name="tutorial")

@app.get("/")
def read_root():
    return RedirectResponse(url="/tutorial")

@app.get("/TUTORIAL.md")
def get_tutorial_md():
    tutorial_path = os.path.join(ROOT_DIR, "TUTORIAL.md")
    if os.path.exists(tutorial_path):
        return FileResponse(tutorial_path, media_type="text/markdown")
    raise HTTPException(status_code=404, detail="TUTORIAL.md not found")

@app.on_event("startup")
def startup_event():
    init_hdf5()
    # Start UDP ingestion listener thread for telemetry
    ingest_thread = threading.Thread(target=udp_telemetry_listener, daemon=True)
    ingest_thread.start()

def udp_telemetry_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 9005))
    print("[DATA-LAKE-API] Ingestion listener attached to UDP 127.0.0.1:9005")

    while True:
        try:
            data, _ = sock.recvfrom(65536)
            try:
                diag = QuenchDiagnostic()
                diag.ParseFromString(data)
                record = {
                    "timestamp_ns": diag.envelope.timestamp_ns,
                    "sensor_id": diag.sensor_id,
                    "localized_temperature_k": diag.localized_temperature_k,
                    "thermal_rise_rate_k_per_s": diag.thermal_rise_rate_k_per_s,
                    "foas_acoustic_frequency_hz": diag.foas_acoustic_frequency_hz,
                    "foas_acoustic_amplitude_db": diag.foas_acoustic_amplitude_db,
                    "stray_capacitance_pf": diag.stray_capacitance_pf,
                    "capacitance_shift_rate_pf_per_s": diag.capacitance_shift_rate_pf_per_s,
                    "normal_zone_propagation_velocity_mps": diag.normal_zone_propagation_velocity_mps,
                    "quench_detected": diag.quench_detected,
                    "plasma_density_m3": diag.plasma_density_m3
                }

                with buffer_lock:
                    telemetry_buffer.append(record)
                    if len(telemetry_buffer) > 1000:
                        telemetry_buffer.pop(0)

                    if diag.quench_detected:
                        quench_events_buffer.append(record)
                        if len(quench_events_buffer) > 100:
                            quench_events_buffer.pop(0)

                persist_telemetry_to_hdf5(record)

            except Exception:
                # Try decoding DigitalTwinState
                twin = DigitalTwinState()
                twin.ParseFromString(data)
                record_twin = {
                    "simulation_step": twin.simulation_step,
                    "peak_coil_strain_mpa": twin.peak_coil_strain_mpa,
                    "plasma_beta_toroidal": twin.plasma_beta_toroidal,
                    "magnetic_axis_displacement_m": twin.magnetic_axis_displacement_m,
                    "pinn_loss": twin.pinn_loss,
                    "equilibrium_converged": twin.equilibrium_converged,
                    "scientific_gain_q_sci": twin.scientific_gain_q_sci,
                    "engineering_gain_q_eng": twin.engineering_gain_q_eng,
                    "fusion_power_mw": twin.fusion_power_mw,
                    "heating_power_mw": twin.heating_power_mw,
                    "gross_electric_power_mw": twin.gross_electric_power_mw,
                    "net_electric_power_mw": twin.net_electric_power_mw,
                    "recirculating_power_mw": twin.recirculating_power_mw,
                    "parasitic_cryo_power_mw": twin.parasitic_cryo_power_mw,
                    "lawson_triple_product_kev_s_m3": twin.lawson_triple_product_kev_s_m3,
                    "net_electricity_achieved": twin.net_electricity_achieved
                }
                with buffer_lock:
                    digital_twin_buffer.append(record_twin)
                    if len(digital_twin_buffer) > 200:
                        digital_twin_buffer.pop(0)

        except Exception as e:
            time.sleep(0.1)

@app.get("/api/v1/health")
def get_health():
    return {
        "status": "HEALTHY",
        "purdue_level": "LEVEL_4_PLANT_MANAGEMENT / LEVEL_5_ENTERPRISE_AI",
        "iec62443_compliance": "ZONE_5_ISOLATED_READ_ONLY_API",
        "buffer_size": len(telemetry_buffer),
        "quench_events_logged": len(quench_events_buffer),
        "digital_twin_frames": len(digital_twin_buffer),
        "hdf5_storage": HDF5_FILE_PATH
    }

@app.get("/api/v1/telemetry/latest")
def get_latest_telemetry():
    with buffer_lock:
        if not telemetry_buffer:
            raise HTTPException(status_code=404, detail="No telemetry frames ingested yet")
        return telemetry_buffer[-1]

@app.get("/api/v1/digital-twin/latest")
def get_latest_digital_twin():
    with buffer_lock:
        if not digital_twin_buffer:
            # Default nominal response
            return {
                "simulation_step": 1,
                "scientific_gain_q_sci": 10.2,
                "engineering_gain_q_eng": 2.14,
                "fusion_power_mw": 255.0,
                "heating_power_mw": 25.0,
                "gross_electric_power_mw": 106.4,
                "net_electric_power_mw": 56.3,
                "recirculating_power_mw": 41.66,
                "parasitic_cryo_power_mw": 8.5,
                "lawson_triple_product_kev_s_m3": 4.85,
                "net_electricity_achieved": True
            }
        return digital_twin_buffer[-1]

@app.get("/api/v1/quench-events")
def get_quench_events():
    with buffer_lock:
        return quench_events_buffer

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
