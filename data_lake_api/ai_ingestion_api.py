#!/usr/bin/env python3
"""
SKHY - TAMI Level 4/5 Enterprise Integration & Agentic AI API
Provides HDF5 Data Lake persistence, multi-subsystem real-time tracking,
and REST / GraphQL interfaces for Agentic AI multi-physics training,
plant power balance (Q_sci), and real-time stellarator diagnostic queries.
"""

import sys
import os
import time
import socket
import threading
from typing import List, Optional, Dict, Any
import h5py
import numpy as np

from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import strawberry
from strawberry.fastapi import GraphQLRouter

# Add parent directory to path to import python_common
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

from python_common.skhy_telemetry_pb2 import (
    QuenchDiagnostic, DigitalTwinState, SubsystemTelemetryReport, OperationalMode
)

# ============================================================================
# In-Memory Buffer & HDF5 Persistence Storage Engine
# ============================================================================

HDF5_FILE_PATH = "tami_data_lake.h5"

telemetry_buffer: List[dict] = []
digital_twin_buffer: List[dict] = []
quench_events_buffer: List[dict] = []
subsystem_buffer: List[dict] = []
active_operational_mode = "MODE_STEADY_STATE_NOMINAL"

buffer_lock = threading.Lock()

def init_hdf5():
    try:
        with h5py.File(HDF5_FILE_PATH, "a") as f:
            if "quench_telemetry" not in f:
                f.create_group("quench_telemetry")
            if "digital_twin" not in f:
                f.create_group("digital_twin")
            if "subsystems" not in f:
                f.create_group("subsystems")
        print(f"[DATA-LAKE] HDF5 Data Lake initialized at '{HDF5_FILE_PATH}'")
    except Exception as e:
        print(f"[DATA-LAKE-INIT-WARNING] {e}")

def persist_subsystem_to_hdf5(record: dict):
    try:
        with h5py.File(HDF5_FILE_PATH, "a") as f:
            grp = f["subsystems"]
            ts_str = str(record["timestamp_ns"])
            if ts_str not in grp:
                sub = grp.create_group(ts_str)
                sub.attrs["mode"] = record.get("active_mode", "UNKNOWN")
                sub.attrs["coil_temp_k"] = record["coil_cryo"]["coil_temperature_k"]
                sub.attrs["q_sci"] = record["power_balance"]["scientific_gain_q_sci"]
                sub.attrs["div_heat_flux"] = record["divertor"]["peak_heat_flux_mw_per_m2"]
                sub.attrs["tbr"] = record["blanket"]["tritium_breeding_ratio"]
    except Exception:
        pass

# ============================================================================
# GraphQL Schema Definitions (Strawberry)
# ============================================================================

@strawberry.type
class CoilCryoGQL:
    coil_temperature_k: float
    helium_pressure_bar: float
    peak_coil_stress_mpa: float
    critical_current_ratio: float
    quench_margin_k: float
    nzpv_mps: float
    quench_warning: bool
    coil_id: str

@strawberry.type
class PlasmaCoreGQL:
    electron_temp_kev: float
    ion_temp_kev: float
    electron_density_1e20_m3: float
    energy_confinement_tau_s: float
    lawson_triple_product_kev_s_m3: float
    toroidal_beta_percent: float
    qi_neoclassical_loss_fraction: float
    mhd_quiescent: bool

@strawberry.type
class DivertorGQL:
    peak_heat_flux_mw_per_m2: float
    target_surface_temp_c: float
    detachment_achieved: bool
    impurity_seeding_rate_pa_m3_s: float
    sol_plasma_density_1e19_m3: float
    thermal_overload_alert: bool

@strawberry.type
class BlanketGQL:
    pb_li_inlet_temp_c: float
    pb_li_outlet_temp_c: float
    neutron_wall_load_mw_per_m2: float
    tritium_breeding_ratio: float
    tritium_extraction_rate_g_per_day: float
    coolant_flow_rate_kg_s: float

@strawberry.type
class PowerBalanceGQL:
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
class SubsystemReportGQL:
    timestamp_ns: str
    active_mode: str
    mode_description: str
    coil_cryo: CoilCryoGQL
    plasma_core: PlasmaCoreGQL
    divertor: DivertorGQL
    blanket: BlanketGQL
    power_balance: PowerBalanceGQL

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
class QueryGQL:
    @strawberry.field
    def latest_subsystem_report(self) -> Optional[SubsystemReportGQL]:
        with buffer_lock:
            if not subsystem_buffer:
                # Return nominal default structure if buffer empty
                return SubsystemReportGQL(
                    timestamp_ns=str(int(time.time() * 1e9)),
                    active_mode="MODE_STEADY_STATE_NOMINAL",
                    mode_description="Normal Steady-State Burn: QI high-confinement flattop",
                    coil_cryo=CoilCryoGQL(
                        coil_temperature_k=20.0,
                        helium_pressure_bar=5.2,
                        peak_coil_stress_mpa=145.0,
                        critical_current_ratio=0.58,
                        quench_margin_k=72.0,
                        nzpv_mps=0.0,
                        quench_warning=False,
                        coil_id="HTS-MODULAR-COIL-03"
                    ),
                    plasma_core=PlasmaCoreGQL(
                        electron_temp_kev=14.8,
                        ion_temp_kev=14.2,
                        electron_density_1e20_m3=1.85,
                        energy_confinement_tau_s=1.65,
                        lawson_triple_product_kev_s_m3=43.3,
                        toroidal_beta_percent=4.25,
                        qi_neoclassical_loss_fraction=0.0012,
                        mhd_quiescent=True
                    ),
                    divertor=DivertorGQL(
                        peak_heat_flux_mw_per_m2=4.2,
                        target_surface_temp_c=485.0,
                        detachment_achieved=True,
                        impurity_seeding_rate_pa_m3_s=1.45,
                        sol_plasma_density_1e19_m3=2.4,
                        thermal_overload_alert=False
                    ),
                    blanket=BlanketGQL(
                        pb_li_inlet_temp_c=350.0,
                        pb_li_outlet_temp_c=495.0,
                        neutron_wall_load_mw_per_m2=1.85,
                        tritium_breeding_ratio=1.15,
                        tritium_extraction_rate_g_per_day=142.0,
                        coolant_flow_rate_kg_s=280.0
                    ),
                    power_balance=PowerBalanceGQL(
                        scientific_gain_q_sci=10.2,
                        engineering_gain_q_eng=2.14,
                        fusion_power_mw=255.0,
                        heating_power_mw=25.0,
                        gross_electric_power_mw=106.4,
                        net_electric_power_mw=56.3,
                        recirculating_power_mw=41.66,
                        parasitic_cryo_power_mw=8.5,
                        lawson_triple_product_kev_s_m3=43.3,
                        net_electricity_achieved=True
                    )
                )

            s = subsystem_buffer[-1]
            return SubsystemReportGQL(
                timestamp_ns=str(s["timestamp_ns"]),
                active_mode=s["active_mode"],
                mode_description=s["mode_description"],
                coil_cryo=CoilCryoGQL(**s["coil_cryo"]),
                plasma_core=PlasmaCoreGQL(**s["plasma_core"]),
                divertor=DivertorGQL(**s["divertor"]),
                blanket=BlanketGQL(**s["blanket"]),
                power_balance=PowerBalanceGQL(**s["power_balance"])
            )

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

graphql_schema = strawberry.Schema(query=QueryGQL)
graphql_app = GraphQLRouter(graphql_schema)

# ============================================================================
# FastAPI REST Endpoints & Background Telemetry Ingestion Receiver
# ============================================================================

app = FastAPI(
    title="SKHY - TAMI Agentic AI Data Lake API",
    description="Purdue Level 4/5 Enterprise API for Multi-Subsystem Stellarator Telemetry, Plant Power Balance, and Agentic AI Ingestion",
    version="2.5.0"
)

# Enable CORS for browser UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    ingest_thread = threading.Thread(target=udp_telemetry_listener, daemon=True)
    ingest_thread.start()

def udp_telemetry_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 9005))
    print("[DATA-LAKE-API] Ingestion listener attached to UDP 127.0.0.1:9005")

    while True:
        try:
            data, _ = sock.recvfrom(65536)

            # 1. Attempt decoding SubsystemTelemetryReport
            try:
                sub_report = SubsystemTelemetryReport()
                sub_report.ParseFromString(data)

                # Extract into dictionary
                mode_str = OperationalMode.Name(sub_report.active_mode)
                record_sub = {
                    "timestamp_ns": sub_report.envelope.timestamp_ns,
                    "active_mode": mode_str,
                    "mode_description": sub_report.mode_description,
                    "coil_cryo": {
                        "coil_temperature_k": round(sub_report.coil_cryo.coil_temperature_k, 2),
                        "helium_pressure_bar": round(sub_report.coil_cryo.helium_pressure_bar, 2),
                        "peak_coil_stress_mpa": round(sub_report.coil_cryo.peak_coil_stress_mpa, 1),
                        "critical_current_ratio": round(sub_report.coil_cryo.critical_current_ratio, 3),
                        "quench_margin_k": round(sub_report.coil_cryo.quench_margin_k, 1),
                        "nzpv_mps": round(sub_report.coil_cryo.nzpv_mps, 4),
                        "quench_warning": sub_report.coil_cryo.quench_warning,
                        "coil_id": sub_report.coil_cryo.coil_id
                    },
                    "plasma_core": {
                        "electron_temp_kev": round(sub_report.plasma_core.electron_temp_kev, 2),
                        "ion_temp_kev": round(sub_report.plasma_core.ion_temp_kev, 2),
                        "electron_density_1e20_m3": round(sub_report.plasma_core.electron_density_1e20_m3, 3),
                        "energy_confinement_tau_s": round(sub_report.plasma_core.energy_confinement_tau_s, 3),
                        "lawson_triple_product_kev_s_m3": round(sub_report.plasma_core.lawson_triple_product_kev_s_m3, 2),
                        "toroidal_beta_percent": round(sub_report.plasma_core.toroidal_beta_percent, 2),
                        "qi_neoclassical_loss_fraction": round(sub_report.plasma_core.qi_neoclassical_loss_fraction, 5),
                        "mhd_quiescent": sub_report.plasma_core.mhd_quiescent
                    },
                    "divertor": {
                        "peak_heat_flux_mw_per_m2": round(sub_report.divertor.peak_heat_flux_mw_per_m2, 2),
                        "target_surface_temp_c": round(sub_report.divertor.target_surface_temp_c, 1),
                        "detachment_achieved": sub_report.divertor.detachment_achieved,
                        "impurity_seeding_rate_pa_m3_s": round(sub_report.divertor.impurity_seeding_rate_pa_m3_s, 2),
                        "sol_plasma_density_1e19_m3": round(sub_report.divertor.sol_plasma_density_1e19_m3, 2),
                        "thermal_overload_alert": sub_report.divertor.thermal_overload_alert
                    },
                    "blanket": {
                        "pb_li_inlet_temp_c": round(sub_report.blanket.pb_li_inlet_temp_c, 1),
                        "pb_li_outlet_temp_c": round(sub_report.blanket.pb_li_outlet_temp_c, 1),
                        "neutron_wall_load_mw_per_m2": round(sub_report.blanket.neutron_wall_load_mw_per_m2, 2),
                        "tritium_breeding_ratio": round(sub_report.blanket.tritium_breeding_ratio, 3),
                        "tritium_extraction_rate_g_per_day": round(sub_report.blanket.tritium_extraction_rate_g_per_day, 1),
                        "coolant_flow_rate_kg_s": round(sub_report.blanket.coolant_flow_rate_kg_s, 1)
                    },
                    "power_balance": {
                        "scientific_gain_q_sci": round(sub_report.power_balance.scientific_gain_q_sci, 2),
                        "engineering_gain_q_eng": round(sub_report.power_balance.engineering_gain_q_eng, 2),
                        "fusion_power_mw": round(sub_report.power_balance.fusion_power_mw, 1),
                        "heating_power_mw": round(sub_report.power_balance.heating_power_mw, 1),
                        "gross_electric_power_mw": round(sub_report.power_balance.gross_electric_power_mw, 1),
                        "net_electric_power_mw": round(sub_report.power_balance.net_electric_power_mw, 1),
                        "recirculating_power_mw": round(sub_report.power_balance.recirculating_power_mw, 1),
                        "parasitic_cryo_power_mw": round(sub_report.power_balance.parasitic_cryo_power_mw, 1),
                        "lawson_triple_product_kev_s_m3": round(sub_report.power_balance.lawson_triple_product_kev_s_m3, 2),
                        "net_electricity_achieved": sub_report.power_balance.net_electricity_achieved
                    }
                }

                # Also populate telemetry_buffer from sub_report for uniform availability
                quench_rec = {
                    "timestamp_ns": sub_report.envelope.timestamp_ns,
                    "sensor_id": sub_report.coil_cryo.coil_id,
                    "localized_temperature_k": sub_report.coil_cryo.coil_temperature_k,
                    "thermal_rise_rate_k_per_s": 0.0 if not sub_report.coil_cryo.quench_warning else 8.5,
                    "foas_acoustic_frequency_hz": 1200.0 if not sub_report.coil_cryo.quench_warning else 31200.0,
                    "foas_acoustic_amplitude_db": 15.0 if not sub_report.coil_cryo.quench_warning else 52.0,
                    "stray_capacitance_pf": 120.0,
                    "capacitance_shift_rate_pf_per_s": 0.1,
                    "normal_zone_propagation_velocity_mps": sub_report.coil_cryo.nzpv_mps,
                    "quench_detected": sub_report.coil_cryo.quench_warning,
                    "plasma_density_m3": sub_report.plasma_core.electron_density_1e20_m3
                }
                with buffer_lock:
                    subsystem_buffer.append(record_sub)
                    if len(subsystem_buffer) > 500:
                        subsystem_buffer.pop(0)

                    telemetry_buffer.append(quench_rec)
                    if len(telemetry_buffer) > 1000:
                        telemetry_buffer.pop(0)

                    if sub_report.coil_cryo.quench_warning:
                        quench_events_buffer.append(quench_rec)
                        if len(quench_events_buffer) > 100:
                            quench_events_buffer.pop(0)

                persist_subsystem_to_hdf5(record_sub)
                continue
            except Exception:
                pass

            # 2. Attempt decoding QuenchDiagnostic
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
            except Exception:
                pass

        except Exception as e:
            time.sleep(0.05)

# ============================================================================
# REST Endpoints
# ============================================================================

@app.get("/api/v1/health")
def get_health():
    return {
        "status": "HEALTHY",
        "purdue_level": "LEVEL_4_PLANT_MANAGEMENT / LEVEL_5_ENTERPRISE_AI",
        "iec62443_compliance": "ZONE_5_ISOLATED_READ_ONLY_API",
        "subsystems_tracked": ["Coils & Cryogenics", "Plasma Core", "Divertor", "Breeding Blanket", "Power Balance"],
        "subsystem_frames_logged": len(subsystem_buffer),
        "quench_events_logged": len(quench_events_buffer),
        "hdf5_storage": HDF5_FILE_PATH
    }

@app.get("/api/v1/subsystems/latest")
def get_latest_subsystems():
    with buffer_lock:
        if not subsystem_buffer:
            # Fallback default nominal structure
            return {
                "timestamp_ns": int(time.time() * 1e9),
                "active_mode": "MODE_STEADY_STATE_NOMINAL",
                "mode_description": "Normal Steady-State Burn: QI high-confinement flattop",
                "coil_cryo": {
                    "coil_temperature_k": 20.0,
                    "helium_pressure_bar": 5.2,
                    "peak_coil_stress_mpa": 145.0,
                    "critical_current_ratio": 0.58,
                    "quench_margin_k": 72.0,
                    "nzpv_mps": 0.0,
                    "quench_warning": False,
                    "coil_id": "HTS-MODULAR-COIL-03"
                },
                "plasma_core": {
                    "electron_temp_kev": 14.8,
                    "ion_temp_kev": 14.2,
                    "electron_density_1e20_m3": 1.85,
                    "energy_confinement_tau_s": 1.65,
                    "lawson_triple_product_kev_s_m3": 43.3,
                    "toroidal_beta_percent": 4.25,
                    "qi_neoclassical_loss_fraction": 0.0012,
                    "mhd_quiescent": True
                },
                "divertor": {
                    "peak_heat_flux_mw_per_m2": 4.2,
                    "target_surface_temp_c": 485.0,
                    "detachment_achieved": True,
                    "impurity_seeding_rate_pa_m3_s": 1.45,
                    "sol_plasma_density_1e19_m3": 2.4,
                    "thermal_overload_alert": False
                },
                "blanket": {
                    "pb_li_inlet_temp_c": 350.0,
                    "pb_li_outlet_temp_c": 495.0,
                    "neutron_wall_load_mw_per_m2": 1.85,
                    "tritium_breeding_ratio": 1.15,
                    "tritium_extraction_rate_g_per_day": 142.0,
                    "coolant_flow_rate_kg_s": 280.0
                },
                "power_balance": {
                    "scientific_gain_q_sci": 10.2,
                    "engineering_gain_q_eng": 2.14,
                    "fusion_power_mw": 255.0,
                    "heating_power_mw": 25.0,
                    "gross_electric_power_mw": 106.4,
                    "net_electric_power_mw": 56.3,
                    "recirculating_power_mw": 41.66,
                    "parasitic_cryo_power_mw": 8.5,
                    "lawson_triple_product_kev_s_m3": 43.3,
                    "net_electricity_achieved": True
                }
            }
        return subsystem_buffer[-1]

@app.get("/api/v1/subsystems/{subsystem_name}")
def get_individual_subsystem(subsystem_name: str = Path(..., description="coil_cryo, plasma_core, divertor, blanket, or power_balance")):
    latest = get_latest_subsystems()
    if subsystem_name in latest:
        return {"subsystem": subsystem_name, "data": latest[subsystem_name]}
    raise HTTPException(status_code=404, detail=f"Subsystem '{subsystem_name}' not recognized")

@app.get("/api/v1/modes")
def get_available_modes():
    return {
        "active_mode": subsystem_buffer[-1]["active_mode"] if subsystem_buffer else active_operational_mode,
        "available_modes": [
            {
                "id": "MODE_STEADY_STATE_NOMINAL",
                "name": "Steady-State Nominal",
                "description": "QI flattop high-confinement regime (Q_sci ~ 10.2, P_net > +56 MW, Coils 20K, Divertor Detached)"
            },
            {
                "id": "MODE_DIVERTOR_DETACHMENT_FAULT",
                "name": "Divertor Detachment Fault",
                "description": "Impurity puff line failure, strike point heat flux surges past 10 MW/m^2 to ~16.8 MW/m^2"
            },
            {
                "id": "MODE_HTS_COIL_HOTSPOT_QUENCH",
                "name": "REBCO Coil Hotspot Quench",
                "description": "Cryogenic thermal runaway in Coil 3, FOAS acoustic stress emissions > 25 kHz, NZPV acceleration"
            },
            {
                "id": "MODE_PELLET_REFUELING_BURST",
                "name": "Pellet Refueling Density Burst",
                "description": "Cryogenic D-T frozen pellet injected at 1.2 km/s, core density doubles, momentary Q_sci surges to 16.5"
            },
            {
                "id": "MODE_IMPURITY_ACCUMULATION",
                "name": "Core Tungsten Impurity Collapse",
                "description": "Metal wall sputtering influx, core Bremsstrahlung radiation spikes, plasma collapses into electrical deficit"
            },
            {
                "id": "MODE_STARTUP_RAMP",
                "name": "Startup Ignition Ramp",
                "description": "Coil magnetic field ramp 0-5.5T, ECRH microwave gyrotron ionization and plasma breakdown"
            }
        ]
    }

@app.post("/api/v1/mode/set/{mode_id}")
def set_operational_mode(mode_id: str):
    global active_operational_mode
    valid_modes = [
        "MODE_STEADY_STATE_NOMINAL", "MODE_DIVERTOR_DETACHMENT_FAULT",
        "MODE_HTS_COIL_HOTSPOT_QUENCH", "MODE_PELLET_REFUELING_BURST",
        "MODE_IMPURITY_ACCUMULATION", "MODE_STARTUP_RAMP"
    ]
    if mode_id not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode ID. Choose from: {valid_modes}")

    active_operational_mode = mode_id
    return {"status": "SUCCESS", "active_mode": active_operational_mode}

@app.get("/api/v1/telemetry/latest")
def get_latest_telemetry():
    with buffer_lock:
        if not telemetry_buffer:
            return {
                "timestamp_ns": int(time.time() * 1e9),
                "sensor_id": "FOAS-HTS-COIL-03A",
                "localized_temperature_k": 20.0,
                "thermal_rise_rate_k_per_s": 0.0,
                "foas_acoustic_frequency_hz": 1200.0,
                "foas_acoustic_amplitude_db": 12.0,
                "stray_capacitance_pf": 120.0,
                "capacitance_shift_rate_pf_per_s": 0.0,
                "normal_zone_propagation_velocity_mps": 0.0,
                "quench_detected": False,
                "plasma_density_m3": 1.85
            }
        return telemetry_buffer[-1]

@app.get("/api/v1/quench-events")
def get_quench_events():
    with buffer_lock:
        return quench_events_buffer

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
