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
    PurdueLevel, PayloadType, OperationalMode, ReactorType,
    Envelope, DigitalTwinState, QuenchDiagnostic,
    CoilCryoTelemetry, PlasmaCoreTelemetry, DivertorTelemetry,
    BlanketTelemetry, SubsystemTelemetryReport,
    TokamakCoreTelemetry, IcfCoreTelemetry, StellaratorCoreTelemetry
)

# ============================================================================
# In-Memory Buffer & HDF5 Persistence Storage Engine
# ============================================================================

HDF5_FILE_PATH = "tami_data_lake.h5"

telemetry_buffer: List[dict] = []
digital_twin_buffer: List[dict] = []
quench_events_buffer: List[dict] = []
subsystem_buffer: List[dict] = []
active_reactor_type: str = "REACTOR_QI_STELLARATOR"
active_operational_mode: str = "MODE_STEADY_STATE_NOMINAL"

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
                sub.attrs["reactor_type"] = record.get("reactor_type", "REACTOR_QI_STELLARATOR")
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
class TokamakCoreGQL:
    plasma_current_ma: float
    central_solenoid_current_ka: float
    safety_factor_q95: float
    loop_voltage_v: float
    poloidal_divertor_heat_flux_mw_m2: float
    vertical_displacement_z_mm: float
    elm_frequency_hz: float
    disruption_warning: bool
    runaway_electron_current_ma: float
    internal_inductance_li: float
    greenwald_density_fraction: float

@strawberry.type
class IcfCoreGQL:
    driver_laser_energy_mj: float
    repetition_rate_hz: float
    target_gain_g: float
    implosion_symmetry_rms_pct: float
    capsule_ablation_pressure_mbar: float
    beam_timing_jitter_ps: float
    final_optics_transmission_pct: float
    target_tracking_error_um: float
    target_chamber_pressure_pa: float
    total_shots_fired: int
    rayleigh_taylor_instability_alert: bool

@strawberry.type
class StellaratorCoreGQL:
    rotational_transform_iota_edge: float
    bootstrap_current_ka: float
    island_divertor_strike_temp_c: float
    qi_symmetry_metric: float

@strawberry.type
class SubsystemReportGQL:
    timestamp_ns: str
    reactor_type: str
    active_mode: str
    mode_description: str
    coil_cryo: CoilCryoGQL
    plasma_core: PlasmaCoreGQL
    divertor: DivertorGQL
    blanket: BlanketGQL
    power_balance: PowerBalanceGQL
    tokamak_core: Optional[TokamakCoreGQL] = None
    icf_core: Optional[IcfCoreGQL] = None

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
            report_data = get_latest_subsystems_dict()
            tokamak_gql = TokamakCoreGQL(**report_data["tokamak_core"]) if "tokamak_core" in report_data else None
            icf_gql = IcfCoreGQL(**report_data["icf_core"]) if "icf_core" in report_data else None
            return SubsystemReportGQL(
                timestamp_ns=str(report_data["timestamp_ns"]),
                reactor_type=report_data.get("reactor_type", active_reactor_type),
                active_mode=report_data["active_mode"],
                mode_description=report_data["mode_description"],
                coil_cryo=CoilCryoGQL(**report_data["coil_cryo"]),
                plasma_core=PlasmaCoreGQL(**report_data["plasma_core"]),
                divertor=DivertorGQL(**report_data["divertor"]),
                blanket=BlanketGQL(**report_data["blanket"]),
                power_balance=PowerBalanceGQL(**report_data["power_balance"]),
                tokamak_core=tokamak_gql,
                icf_core=icf_gql
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
    return RedirectResponse(url="/tutorial/")

@app.get("/style.css")
def get_root_style():
    fpath = os.path.join(TUTORIAL_VIEWER_DIR, "style.css")
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")

@app.get("/app.js")
def get_root_app():
    fpath = os.path.join(TUTORIAL_VIEWER_DIR, "app.js")
    if os.path.exists(fpath):
        return FileResponse(fpath, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/TUTORIAL.md")
def get_tutorial_md():
    tutorial_path = os.path.join(ROOT_DIR, "TUTORIAL.md")
    if os.path.exists(tutorial_path):
        return FileResponse(tutorial_path, media_type="text/markdown")
    raise HTTPException(status_code=404, detail="TUTORIAL.md not found")

@app.get("/tutorial/TUTORIAL.md")
def get_tutorial_md_sub():
    tutorial_path = os.path.join(ROOT_DIR, "TUTORIAL.md")
    if os.path.exists(tutorial_path):
        return FileResponse(tutorial_path, media_type="text/markdown")
    raise HTTPException(status_code=404, detail="TUTORIAL.md not found")

@app.on_event("startup")
def startup_event():
    init_hdf5()
    ingest_thread = threading.Thread(target=udp_telemetry_listener, daemon=True)
    ingest_thread.start()

def generate_simulated_subsystem_record(reactor: str, mode: str) -> dict:
    now_ns = int(time.time() * 1e9)

    # Base common subsystems
    record = {
        "timestamp_ns": now_ns,
        "reactor_type": reactor,
        "active_mode": mode,
        "mode_description": "",
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

    if reactor == "REACTOR_TOKAMAK":
        record["coil_cryo"]["coil_id"] = "TF-D-SHAPED-COIL-07"
        record["tokamak_core"] = {
            "plasma_current_ma": 15.0,
            "central_solenoid_current_ka": 42.5,
            "safety_factor_q95": 3.25,
            "loop_voltage_v": 0.12,
            "poloidal_divertor_heat_flux_mw_m2": 4.8,
            "vertical_displacement_z_mm": 0.8,
            "elm_frequency_hz": 18.0,
            "disruption_warning": False,
            "runaway_electron_current_ma": 0.0,
            "internal_inductance_li": 0.85,
            "greenwald_density_fraction": 0.78
        }
        record["power_balance"] = {
            "scientific_gain_q_sci": 12.0,
            "engineering_gain_q_eng": 2.28,
            "fusion_power_mw": 360.0,
            "heating_power_mw": 30.0,
            "gross_electric_power_mw": 148.2,
            "net_electric_power_mw": 83.2,
            "recirculating_power_mw": 50.0,
            "parasitic_cryo_power_mw": 15.0,
            "lawson_triple_product_kev_s_m3": 48.6,
            "net_electricity_achieved": True
        }
        record["mode_description"] = "Tokamak Steady-State Flattop Burn (Ip=15MA, q95=3.25, Q=12)"

        if mode == "MODE_TOKAMAK_MAJOR_DISRUPTION":
            record["tokamak_core"]["plasma_current_ma"] = 0.8
            record["tokamak_core"]["loop_voltage_v"] = 185.0
            record["tokamak_core"]["disruption_warning"] = True
            record["tokamak_core"]["runaway_electron_current_ma"] = 2.45
            record["divertor"]["peak_heat_flux_mw_per_m2"] = 22.5
            record["divertor"]["thermal_overload_alert"] = True
            record["plasma_core"]["mhd_quiescent"] = False
            record["power_balance"]["scientific_gain_q_sci"] = 0.05
            record["power_balance"]["net_electric_power_mw"] = -45.0
            record["power_balance"]["net_electricity_achieved"] = False
            record["mode_description"] = "MAJOR DISRUPTION: Thermal quench & 185V inductive spike!"
        elif mode == "MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT":
            record["tokamak_core"]["vertical_displacement_z_mm"] = 48.5
            record["tokamak_core"]["disruption_warning"] = True
            record["mode_description"] = "VERTICAL DISPLACEMENT EVENT: Axisymmetric Delta-Z surge >45mm"
        elif mode == "MODE_TOKAMAK_UNMITIGATED_ELM_BURST":
            record["tokamak_core"]["elm_frequency_hz"] = 85.0
            record["tokamak_core"]["poloidal_divertor_heat_flux_mw_m2"] = 16.4
            record["divertor"]["peak_heat_flux_mw_per_m2"] = 16.4
            record["divertor"]["thermal_overload_alert"] = True
            record["mode_description"] = "TYPE-I ELM BURST: Pedestal collapse, divertor peak 16.4 MW/m^2"
        elif mode == "MODE_TOKAMAK_RUNAWAY_ELECTRON_AVALANCHE":
            record["tokamak_core"]["runaway_electron_current_ma"] = 3.8
            record["tokamak_core"]["disruption_warning"] = True
            record["mode_description"] = "RUNAWAY ELECTRON AVALANCHE: Relativistic 3.8 MA wall impact warning"
        elif mode == "MODE_TOKAMAK_NEOCLASSICAL_TEARING_MODE":
            record["tokamak_core"]["internal_inductance_li"] = 1.42
            record["plasma_core"]["energy_confinement_tau_s"] = 0.85
            record["power_balance"]["scientific_gain_q_sci"] = 5.8
            record["mode_description"] = "NEOCLASSICAL TEARING MODE (2/1 Island): Confinement degraded 45%"

    elif reactor == "REACTOR_ICF":
        record["coil_cryo"]["coil_id"] = "ICF-CRYOGENIC-TARGET-HOLDER"
        record["icf_core"] = {
            "driver_laser_energy_mj": 2.15,
            "repetition_rate_hz": 5.0,
            "target_gain_g": 85.0,
            "implosion_symmetry_rms_pct": 0.65,
            "capsule_ablation_pressure_mbar": 185.0,
            "beam_timing_jitter_ps": 8.5,
            "final_optics_transmission_pct": 98.2,
            "target_tracking_error_um": 12.4,
            "target_chamber_pressure_pa": 0.045,
            "total_shots_fired": 184520,
            "rayleigh_taylor_instability_alert": False
        }
        # ICF Power Balance: 2.15 MJ * 85 * 5 Hz = 913.75 MW fusion power
        p_fus = 2.15 * 85.0 * 5.0
        p_laser_elec = (2.15 * 5.0) / 0.15 # 71.67 MW electrical input for laser (eta_driver = 15%)
        p_gross = p_fus * 0.38 # 347.2 MW gross electric
        p_net = p_gross - p_laser_elec - 12.0 # ~263.5 MW net
        record["power_balance"] = {
            "scientific_gain_q_sci": 85.0,
            "engineering_gain_q_eng": round(p_gross / (p_laser_elec + 12.0), 2),
            "fusion_power_mw": round(p_fus, 1),
            "heating_power_mw": round(2.15 * 5.0, 1),
            "gross_electric_power_mw": round(p_gross, 1),
            "net_electric_power_mw": round(p_net, 1),
            "recirculating_power_mw": round(p_laser_elec, 1),
            "parasitic_cryo_power_mw": 12.0,
            "lawson_triple_product_kev_s_m3": 75.0,
            "net_electricity_achieved": True
        }
        record["mode_description"] = "ICF 5Hz Repetition Pulse (2.15 MJ UV, Gain G=85, Pfusion=914 MW)"

        if mode == "MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY":
            record["icf_core"]["rayleigh_taylor_instability_alert"] = True
            record["icf_core"]["implosion_symmetry_rms_pct"] = 4.8
            record["icf_core"]["target_gain_g"] = 8.5
            p_fus_deg = 2.15 * 8.5 * 5.0
            p_gross_deg = p_fus_deg * 0.38
            p_net_deg = p_gross_deg - p_laser_elec - 12.0
            record["power_balance"]["scientific_gain_q_sci"] = 8.5
            record["power_balance"]["fusion_power_mw"] = round(p_fus_deg, 1)
            record["power_balance"]["gross_electric_power_mw"] = round(p_gross_deg, 1)
            record["power_balance"]["net_electric_power_mw"] = round(p_net_deg, 1)
            record["power_balance"]["net_electricity_achieved"] = p_net_deg > 0
            record["mode_description"] = "RAYLEIGH-TAYLOR INSTABILITY: Capsule mix fingers, gain collapses 90%!"
        elif mode == "MODE_ICF_LASER_POWER_IMBALANCE_JITTER":
            record["icf_core"]["beam_timing_jitter_ps"] = 38.5
            record["icf_core"]["implosion_symmetry_rms_pct"] = 2.9
            record["mode_description"] = "LASER JITTER: Beam synchronization jitter >35ps degrades drive"
        elif mode == "MODE_ICF_FINAL_OPTICS_DEBRIS_DAMAGE":
            record["icf_core"]["final_optics_transmission_pct"] = 76.4
            record["mode_description"] = "FINAL OPTICS DAMAGE: Debris shield pitted, transmission dropped 22%"
        elif mode == "MODE_ICF_TARGET_TRACKING_INJECTION_MISS":
            record["icf_core"]["target_tracking_error_um"] = 48.0
            record["icf_core"]["target_gain_g"] = 0.5
            record["mode_description"] = "TARGET INJECTION MISS: Pellet off-center >45 um, dud ignition shot"
        elif mode == "MODE_ICF_CHAMBER_CLEARING_PRESSURE_CHOKE":
            record["icf_core"]["target_chamber_pressure_pa"] = 12.5
            record["mode_description"] = "CHAMBER CLEARING CHOKE: Post-shot vapor exhaust bottleneck"

    else:
        # Stellarator modes
        record["mode_description"] = "QI Stellarator High-Confinement Steady-State Burn (Q=10.2)"
        if mode == "MODE_DIVERTOR_DETACHMENT_FAULT":
            record["divertor"]["peak_heat_flux_mw_per_m2"] = 16.8
            record["divertor"]["target_surface_temp_c"] = 995.0
            record["divertor"]["detachment_achieved"] = False
            record["divertor"]["thermal_overload_alert"] = True
            record["mode_description"] = "DIVERTOR ATTACHMENT FAULT: Heat flux surges to 16.8 MW/m^2"
        elif mode == "MODE_HTS_COIL_HOTSPOT_QUENCH":
            record["coil_cryo"]["coil_temperature_k"] = 96.5
            record["coil_cryo"]["quench_margin_k"] = 0.0
            record["coil_cryo"]["critical_current_ratio"] = 1.35
            record["coil_cryo"]["quench_warning"] = True
            record["coil_cryo"]["nzpv_mps"] = 0.045
            record["power_balance"]["net_electric_power_mw"] = -25.0
            record["power_balance"]["net_electricity_achieved"] = False
            record["mode_description"] = "HTS COIL HOTSPOT QUENCH: Critical temp exceeded, fast dump active!"
        elif mode == "MODE_PELLET_REFUELING_BURST":
            record["plasma_core"]["electron_density_1e20_m3"] = 3.2
            record["power_balance"]["scientific_gain_q_sci"] = 16.5
            record["power_balance"]["fusion_power_mw"] = 412.5
            record["mode_description"] = "PELLET REFUELING BURST: Cryo D-T wave, core density surges to 3.2e20"
        elif mode == "MODE_IMPURITY_ACCUMULATION":
            record["plasma_core"]["electron_temp_kev"] = 3.5
            record["power_balance"]["scientific_gain_q_sci"] = 1.8
            record["power_balance"]["net_electric_power_mw"] = -12.5
            record["power_balance"]["net_electricity_achieved"] = False
            record["mode_description"] = "CORE IMPURITY ACCUMULATION: Tungsten radiation collapse"
        elif mode == "MODE_STARTUP_RAMP":
            record["power_balance"]["scientific_gain_q_sci"] = 0.8
            record["power_balance"]["net_electric_power_mw"] = -32.0
            record["power_balance"]["net_electricity_achieved"] = False
            record["mode_description"] = "STARTUP IGNITION RAMP: Coils charging 0-5.5T, ECRH ionization"

    return record

def get_latest_subsystems_dict() -> dict:
    with buffer_lock:
        if subsystem_buffer:
            # Check if latest in buffer matches active_reactor_type
            for item in reversed(subsystem_buffer):
                if item.get("reactor_type") == active_reactor_type:
                    return item
            return subsystem_buffer[-1]
    return generate_simulated_subsystem_record(active_reactor_type, active_operational_mode)

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

                reactor_str = ReactorType.Name(sub_report.reactor_type)
                mode_str = OperationalMode.Name(sub_report.active_mode)

                record_sub = {
                    "timestamp_ns": sub_report.envelope.timestamp_ns,
                    "reactor_type": reactor_str,
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

                if sub_report.HasField("tokamak_core"):
                    tc = sub_report.tokamak_core
                    record_sub["tokamak_core"] = {
                        "plasma_current_ma": round(tc.plasma_current_ma, 2),
                        "central_solenoid_current_ka": round(tc.central_solenoid_current_ka, 1),
                        "safety_factor_q95": round(tc.safety_factor_q95, 2),
                        "loop_voltage_v": round(tc.loop_voltage_v, 3),
                        "poloidal_divertor_heat_flux_mw_m2": round(tc.poloidal_divertor_heat_flux_mw_m2, 2),
                        "vertical_displacement_z_mm": round(tc.vertical_displacement_z_mm, 2),
                        "elm_frequency_hz": round(tc.elm_frequency_hz, 1),
                        "disruption_warning": tc.disruption_warning,
                        "runaway_electron_current_ma": round(tc.runaway_electron_current_ma, 3),
                        "internal_inductance_li": round(tc.internal_inductance_li, 3),
                        "greenwald_density_fraction": round(tc.greenwald_density_fraction, 3)
                    }

                if sub_report.HasField("icf_core"):
                    ic = sub_report.icf_core
                    record_sub["icf_core"] = {
                        "driver_laser_energy_mj": round(ic.driver_laser_energy_mj, 2),
                        "repetition_rate_hz": round(ic.repetition_rate_hz, 1),
                        "target_gain_g": round(ic.target_gain_g, 2),
                        "implosion_symmetry_rms_pct": round(ic.implosion_symmetry_rms_pct, 2),
                        "capsule_ablation_pressure_mbar": round(ic.capsule_ablation_pressure_mbar, 1),
                        "beam_timing_jitter_ps": round(ic.beam_timing_jitter_ps, 1),
                        "final_optics_transmission_pct": round(ic.final_optics_transmission_pct, 1),
                        "target_tracking_error_um": round(ic.target_tracking_error_um, 1),
                        "target_chamber_pressure_pa": round(ic.target_chamber_pressure_pa, 4),
                        "total_shots_fired": ic.total_shots_fired,
                        "rayleigh_taylor_instability_alert": ic.rayleigh_taylor_instability_alert
                    }

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
        "active_reactor": active_reactor_type,
        "active_mode": active_operational_mode,
        "purdue_level": "LEVEL_4_PLANT_MANAGEMENT / LEVEL_5_ENTERPRISE_AI",
        "iec62443_compliance": "ZONE_5_ISOLATED_READ_ONLY_API",
        "reactors_supported": ["REACTOR_QI_STELLARATOR", "REACTOR_TOKAMAK", "REACTOR_ICF"],
        "subsystems_tracked": ["Coils & Cryogenics", "Plasma Core", "Divertor", "Breeding Blanket", "Power Balance", "Polymorphic Core"],
        "subsystem_frames_logged": len(subsystem_buffer),
        "quench_events_logged": len(quench_events_buffer),
        "hdf5_storage": HDF5_FILE_PATH
    }

@app.get("/api/v1/reactors")
def get_available_reactors():
    return {
        "active_reactor": active_reactor_type,
        "reactors": [
            {
                "id": "REACTOR_QI_STELLARATOR",
                "name": "Quasi-Isodynamic (QI) Modular Stellarator",
                "topology": "Continuous 3D Magnetic Confinement",
                "description": "3D non-planar modular HTS coils with zero net plasma current, intrinsic disruption immunity, steady-state operation, island divertor detachment, and high scientific gain Q_sci ~ 10.",
                "driver_system": "ECRH / ICRH Microwave Heating (60% wall-plug eff)",
                "typical_q": 10.2,
                "default_mode": "MODE_STEADY_STATE_NOMINAL",
                "failure_modes": ["Detachment Fault", "REBCO Hotspot Quench", "Impurity Radiative Collapse"]
            },
            {
                "id": "REACTOR_TOKAMAK",
                "name": "Advanced Tokamak (Inductive / Steady-State)",
                "topology": "Axisymmetric Toroidal Magnetic Confinement",
                "description": "High plasma current (Ip ~ 15 MA) driven inductively via Central Solenoid and non-inductively via NBI. High confinement with D-shaped TF coils, subject to major disruptions, locked modes, and Greenwald density limits.",
                "driver_system": "Central Solenoid Inductive + NBI (65% eff)",
                "typical_q": 12.0,
                "default_mode": "MODE_TOKAMAK_NOMINAL_BURNTIME",
                "failure_modes": ["Major Disruption", "Vertical Displacement Event (VDE)", "Type-I ELM Burst", "Runaway Avalanche", "NTM 2/1 Island"]
            },
            {
                "id": "REACTOR_ICF",
                "name": "Inertial Confinement Fusion (ICF)",
                "topology": "Pulsed Laser-Driven Inertial Microimplosions",
                "description": "High repetition rate (5 Hz) cryogenic D-T target capsules compressed to >1000x solid density using 2.15 MJ UV laser bank. Target gain G = 85, driver electrical efficiency ~15%.",
                "driver_system": "Pulsed UV Diode-Pumped Solid-State Lasers (15% eff)",
                "typical_q": 85.0,
                "default_mode": "MODE_ICF_NOMINAL_REPETITION_PULSE",
                "failure_modes": ["Rayleigh-Taylor Instability", "Laser Timing Jitter", "Final Optics Debris Damage", "Target Injection Miss", "Chamber Pressure Choke"]
            }
        ]
    }

@app.post("/api/v1/reactor/set/{reactor_id}")
def set_reactor_type(reactor_id: str):
    global active_reactor_type, active_operational_mode
    valid_reactors = {
        "REACTOR_QI_STELLARATOR": "MODE_STEADY_STATE_NOMINAL",
        "REACTOR_TOKAMAK": "MODE_TOKAMAK_NOMINAL_BURNTIME",
        "REACTOR_ICF": "MODE_ICF_NOMINAL_REPETITION_PULSE"
    }
    if reactor_id not in valid_reactors:
        raise HTTPException(status_code=400, detail=f"Invalid reactor ID. Choose from: {list(valid_reactors.keys())}")

    active_reactor_type = reactor_id
    active_operational_mode = valid_reactors[reactor_id]
    return {
        "status": "SUCCESS",
        "active_reactor": active_reactor_type,
        "active_mode": active_operational_mode
    }

@app.get("/api/v1/subsystems/latest")
def get_latest_subsystems():
    return get_latest_subsystems_dict()

@app.get("/api/v1/subsystems/{subsystem_name}")
def get_individual_subsystem(subsystem_name: str = Path(..., description="coil_cryo, plasma_core, divertor, blanket, power_balance, tokamak_core, icf_core")):
    latest = get_latest_subsystems()
    if subsystem_name in latest:
        return {"subsystem": subsystem_name, "data": latest[subsystem_name]}
    raise HTTPException(status_code=404, detail=f"Subsystem '{subsystem_name}' not recognized")

@app.get("/api/v1/modes")
def get_available_modes(reactor: Optional[str] = Query(None, description="Optional reactor filter")):
    all_modes = {
        "REACTOR_QI_STELLARATOR": [
            {
                "id": "MODE_STEADY_STATE_NOMINAL",
                "name": "Steady-State Nominal",
                "description": "QI flattop high-confinement regime (Q_sci ~ 10.2, P_net > +56 MW, Coils 20K, Divertor Detached)",
                "category": "nominal"
            },
            {
                "id": "MODE_DIVERTOR_DETACHMENT_FAULT",
                "name": "Divertor Detachment Fault",
                "description": "Impurity puff line failure, strike point heat flux surges past 10 MW/m^2 to ~16.8 MW/m^2",
                "category": "anomaly"
            },
            {
                "id": "MODE_HTS_COIL_HOTSPOT_QUENCH",
                "name": "REBCO Coil Hotspot Quench",
                "description": "Cryogenic thermal runaway in Coil 3, FOAS acoustic stress emissions > 25 kHz, NZPV acceleration",
                "category": "critical"
            },
            {
                "id": "MODE_PELLET_REFUELING_BURST",
                "name": "Pellet Refueling Density Burst",
                "description": "Cryogenic D-T frozen pellet injected at 1.2 km/s, core density doubles, momentary Q_sci surges to 16.5",
                "category": "nominal"
            },
            {
                "id": "MODE_IMPURITY_ACCUMULATION",
                "name": "Core Tungsten Impurity Collapse",
                "description": "Metal wall sputtering influx, core Bremsstrahlung radiation spikes, plasma collapses into electrical deficit",
                "category": "anomaly"
            },
            {
                "id": "MODE_STARTUP_RAMP",
                "name": "Startup Ignition Ramp",
                "description": "Coil magnetic field ramp 0-5.5T, ECRH microwave gyrotron ionization and plasma breakdown",
                "category": "nominal"
            }
        ],
        "REACTOR_TOKAMAK": [
            {
                "id": "MODE_TOKAMAK_NOMINAL_BURNTIME",
                "name": "Tokamak Flattop Burn",
                "description": "Inductive current Ip=15 MA flattop, q95=3.25, Q_sci=12.0, detached divertor (<5 MW/m^2)",
                "category": "nominal"
            },
            {
                "id": "MODE_TOKAMAK_MAJOR_DISRUPTION",
                "name": "Major Disruption & Thermal Quench",
                "description": "MHD locked mode triggers total thermal quench (<1 ms), loop voltage spikes to 185V, Ip drops to 0",
                "category": "critical"
            },
            {
                "id": "MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT",
                "name": "Vertical Displacement Event (VDE)",
                "description": "Vertical position control loss, axisymmetric Z-shift >40mm, halo currents into vacuum vessel wall",
                "category": "critical"
            },
            {
                "id": "MODE_TOKAMAK_UNMITIGATED_ELM_BURST",
                "name": "Type-I Edge Localized Mode (ELM)",
                "description": "H-mode pedestal pressure limit breach, divertor peak heat flux spikes to 16.4 MW/m^2",
                "category": "anomaly"
            },
            {
                "id": "MODE_TOKAMAK_RUNAWAY_ELECTRON_AVALANCHE",
                "name": "Runaway Electron Avalanche",
                "description": "Relativistic electron beam formation during current quench, 3.8 MA beam localized wall strike risk",
                "category": "critical"
            },
            {
                "id": "MODE_TOKAMAK_NEOCLASSICAL_TEARING_MODE",
                "name": "Neoclassical Tearing Mode (2/1 NTM)",
                "description": "Magnetic island formation at q=2 surface, beta degradation, 45% confinement loss",
                "category": "anomaly"
            }
        ],
        "REACTOR_ICF": [
            {
                "id": "MODE_ICF_NOMINAL_REPETITION_PULSE",
                "name": "5Hz Repetition Pulse Flattop",
                "description": "2.15 MJ UV laser pulse on cryogenic DT pellet @ 5 Hz, Target Gain G=85, Pfusion=914 MW",
                "category": "nominal"
            },
            {
                "id": "MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY",
                "name": "Rayleigh-Taylor Hydro Instability",
                "description": "Ablation-front Rayleigh-Taylor mix fingers penetrate DT hot spot, target gain drops 90% to G=8.5",
                "category": "critical"
            },
            {
                "id": "MODE_ICF_LASER_POWER_IMBALANCE_JITTER",
                "name": "Laser Power Imbalance & Jitter",
                "description": "Beam synchronization jitter >35ps and beam-to-beam energy imbalance >3% distort implosion spherical symmetry",
                "category": "anomaly"
            },
            {
                "id": "MODE_ICF_FINAL_OPTICS_DEBRIS_DAMAGE",
                "name": "Final Optics Debris Degradation",
                "description": "Target debris and 14.1 MeV neutron pitting degrades disposable debris shield transmission to 76%",
                "category": "anomaly"
            },
            {
                "id": "MODE_ICF_TARGET_TRACKING_INJECTION_MISS",
                "name": "Target Injection Tracking Miss",
                "description": "Pellet injection tracker off-center >40um at chamber center, partial beam illumination dud shot",
                "category": "critical"
            },
            {
                "id": "MODE_ICF_CHAMBER_CLEARING_PRESSURE_CHOKE",
                "name": "Chamber Clearing Pressure Choke",
                "description": "Incomplete post-shot vapor exhaust pumpdown, background gas pressure exceeds 0.1 Torr threshold",
                "category": "anomaly"
            }
        ]
    }

    target_reactor = reactor or active_reactor_type
    modes = all_modes.get(target_reactor, all_modes["REACTOR_QI_STELLARATOR"])

    return {
        "active_reactor": active_reactor_type,
        "active_mode": active_operational_mode,
        "modes": modes,
        "all_modes_by_reactor": all_modes
    }

@app.post("/api/v1/mode/set/{mode_id}")
def set_operational_mode(mode_id: str):
    global active_operational_mode
    valid_modes = [
        # Stellarator
        "MODE_STEADY_STATE_NOMINAL", "MODE_DIVERTOR_DETACHMENT_FAULT",
        "MODE_HTS_COIL_HOTSPOT_QUENCH", "MODE_PELLET_REFUELING_BURST",
        "MODE_IMPURITY_ACCUMULATION", "MODE_STARTUP_RAMP",
        # Tokamak
        "MODE_TOKAMAK_NOMINAL_BURNTIME", "MODE_TOKAMAK_MAJOR_DISRUPTION",
        "MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT", "MODE_TOKAMAK_UNMITIGATED_ELM_BURST",
        "MODE_TOKAMAK_RUNAWAY_ELECTRON_AVALANCHE", "MODE_TOKAMAK_NEOCLASSICAL_TEARING_MODE",
        # ICF
        "MODE_ICF_NOMINAL_REPETITION_PULSE", "MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY",
        "MODE_ICF_LASER_POWER_IMBALANCE_JITTER", "MODE_ICF_FINAL_OPTICS_DEBRIS_DAMAGE",
        "MODE_ICF_TARGET_TRACKING_INJECTION_MISS", "MODE_ICF_CHAMBER_CLEARING_PRESSURE_CHOKE"
    ]
    if mode_id not in valid_modes:
        raise HTTPException(status_code=400, detail=f"Invalid mode ID. Choose from: {valid_modes}")

    active_operational_mode = mode_id
    return {"status": "SUCCESS", "active_reactor": active_reactor_type, "active_mode": active_operational_mode}

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
