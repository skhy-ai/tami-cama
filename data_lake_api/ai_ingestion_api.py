#!/usr/bin/env python3
"""
Proxima Fusion - TAMI Level 4/5 Enterprise Integration & Agentic AI API
Provides HDF5 Data Lake persistence and REST / GraphQL interfaces for Agentic AI
multi-physics training and real-time stellarator diagnostic queries.
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
import uvicorn
import strawberry
from strawberry.fastapi import GraphQLRouter

# Add parent directory to path to import python_common
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_common.proxima_telemetry_pb2 import QuenchDiagnostic, DigitalTwinState

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

@strawberry.type
class DigitalTwinGQL:
    simulation_step: int
    peak_coil_strain_mpa: float
    plasma_beta_toroidal: float
    magnetic_axis_displacement_m: float
    pinn_loss: float
    equilibrium_converged: bool

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
                quench_detected=t["quench_detected"]
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
                    quench_detected=t["quench_detected"]
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
                equilibrium_converged=dt["equilibrium_converged"]
            )

graphql_schema = strawberry.Schema(query=QueryGQL)
graphql_app = GraphQLRouter(graphql_schema)

# ============================================================================
# FastAPI REST Endpoints & Background Telemetry Ingestion Receiver
# ============================================================================

app = FastAPI(
    title="Proxima Fusion - TAMI Agentic AI Data Lake API",
    description="Purdue Level 4/5 Enterprise API for Multi-Physics Training, HDF5 Persistence & Real-time Diagnostic Queries",
    version="1.0.0"
)

app.include_router(graphql_app, prefix="/graphql")

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
            diag = QuenchDiagnostic()
            try:
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
                    "quench_detected": diag.quench_detected
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
                pass
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
        "hdf5_storage": HDF5_FILE_PATH
    }

@app.get("/api/v1/telemetry/latest")
def get_latest_telemetry():
    with buffer_lock:
        if not telemetry_buffer:
            raise HTTPException(status_code=404, detail="No telemetry frames ingested yet")
        return telemetry_buffer[-1]

@app.get("/api/v1/telemetry/history")
def get_telemetry_history(limit: int = Query(default=100, le=500)):
    with buffer_lock:
        return telemetry_buffer[-limit:]

@app.get("/api/v1/quench-events")
def get_quench_events():
    with buffer_lock:
        return quench_events_buffer

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
