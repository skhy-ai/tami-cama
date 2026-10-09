#!/usr/bin/env python3
"""
SKHY - TAMI Level 4/5 Modular Stellarator Digital Twin & Surrogate Model Engine
Implements multi-subsystem physics simulations and a PyTorch Physics-Informed Neural Network (PINN)
for real-time 3D magnetic equilibrium (V3FIT surrogate), HTS thermal dynamics, and Plant Power Balance.

Subsystems Modeled:
1. HTS Magnet Coils & Cryogenics (REBCO non-planar modular coils, helium coolant, Lorentz stress, Ic margin)
2. Plasma Core & Confinement (QI neoclassical transport, Te/Ti, density, Lawson triple product, beta)
3. Divertor & First-Wall Heat Exhaust (Scrape-off layer SOL, heat flux, radiative detachment, impurity seeding)
4. Breeding Blanket & Tritium Fuel Cycle (Liquid PbLi eutectic coolant, 14.1 MeV neutron loading, TBR ~ 1.15)
5. Balance of Plant (BoP) & Electrical Power Conversion (Sam Wurzel Q_sci framework, gross/net electricity)
"""

import sys
import os
import time
import socket
import argparse
import numpy as np
import torch
import torch.nn as nn

# Add parent directory to path to import python_common
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

from python_common.skhy_telemetry_pb2 import (
    PurdueLevel, PayloadType, OperationalMode,
    Envelope, DigitalTwinState, QuenchDiagnostic,
    CoilCryoTelemetry, PlasmaCoreTelemetry, DivertorTelemetry,
    BlanketTelemetry, SubsystemTelemetryReport
)

class StellaratorPINN(nn.Module):
    """
    Physics-Informed Neural Network Surrogate Model for QI Stellarator Equilibrium & Power Balance.
    Maps input sensor features to 3D flux surface mesh coordinates, MHD plasma parameters, and power balance.
    """
    def __init__(self, input_dim=8, mesh_points=32):
        super(StellaratorPINN, self).__init__()
        self.mesh_points = mesh_points

        self.backbone = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.Tanh(),
            nn.Linear(128, 256),
            nn.Tanh(),
            nn.Linear(256, 128),
            nn.SiLU()
        )

        # Multi-head architecture
        self.flux_surface_head = nn.Linear(128, mesh_points * 3) # R, Z, Phi coordinates
        self.thermal_head = nn.Linear(128, mesh_points)          # Thermal grid
        self.mhd_head = nn.Linear(128, 3)                         # Beta, axis displacement, peak strain
        self.power_head = nn.Linear(128, 2)                       # Q_sci, Lawson triple product

    def forward(self, x):
        features = self.backbone(x)
        raw_mesh = self.flux_surface_head(features)
        mesh = raw_mesh.view(-1, self.mesh_points, 3)

        thermal_map = self.thermal_head(features)
        mhd_params = self.mhd_head(features)
        power_params = self.power_head(features)

        beta = torch.sigmoid(mhd_params[:, 0]) * 0.08             # Toroidal beta (0-8%)
        axis_shift = torch.tanh(mhd_params[:, 1]) * 0.05          # Axis displacement (-5cm to +5cm)
        peak_strain = torch.relu(mhd_params[:, 2]) * 350.0 + 50.0 # Coil strain (50-400 MPa)

        q_sci_raw = torch.relu(power_params[:, 0]) * 15.0         # Q_sci (0 to 15.0)
        lawson_product = torch.relu(power_params[:, 1]) * 6.0 + 1.0 # n*T*tau_E (1.0 to 7.0 e20 keV s m^-3)

        return mesh, thermal_map, beta, axis_shift, peak_strain, q_sci_raw, lawson_product

# ============================================================================
# Modular Subsystem Physics Models
# ============================================================================

class HTSCoilsDigitalTwin:
    """Subsystem 1: REBCO HTS Non-Planar Modular Magnet Coils & Cryogenics"""
    def __init__(self, coil_id="HTS-MODULAR-COIL-03"):
        self.coil_id = coil_id
        self.temp_k = 20.0
        self.helium_press_bar = 5.2
        self.peak_stress_mpa = 145.0
        self.current_ratio = 0.58
        self.critical_temp_k = 92.0
        self.nzpv_mps = 0.0
        self.quench_warning = False

    def update(self, mode: OperationalMode, time_elapsed: float = 0.0):
        if mode == OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH:
            # Hotspot thermal runaway
            self.temp_k = min(110.0, 20.0 + 8.5 * time_elapsed + 1.2 * (time_elapsed ** 2))
            self.helium_press_bar = min(18.0, 5.2 + 1.8 * time_elapsed)
            self.peak_stress_mpa = min(320.0, 145.0 + 22.0 * time_elapsed)
            self.current_ratio = min(1.45, 0.58 + 0.15 * time_elapsed)
            self.nzpv_mps = float(min(0.085, 0.02 + 0.008 * time_elapsed))
            self.quench_warning = self.temp_k > 65.0 or self.current_ratio > 0.85
        elif mode == OperationalMode.MODE_STARTUP_RAMP:
            ramp_factor = min(1.0, time_elapsed / 10.0)
            self.temp_k = 18.5 + 1.5 * ramp_factor
            self.helium_press_bar = 5.0 + 0.2 * ramp_factor
            self.peak_stress_mpa = 20.0 + 125.0 * ramp_factor
            self.current_ratio = 0.10 + 0.48 * ramp_factor
            self.nzpv_mps = 0.0
            self.quench_warning = False
        else:
            # Nominal steady state with small random variations
            self.temp_k = 20.0 + float(np.random.normal(0, 0.1))
            self.helium_press_bar = 5.2 + float(np.random.normal(0, 0.05))
            self.peak_stress_mpa = 145.0 + float(np.random.normal(0, 1.2))
            self.current_ratio = 0.58 + float(np.random.normal(0, 0.01))
            self.nzpv_mps = 0.0
            self.quench_warning = False

        quench_margin = max(0.0, self.critical_temp_k - self.temp_k)
        return CoilCryoTelemetry(
            coil_temperature_k=self.temp_k,
            helium_pressure_bar=self.helium_press_bar,
            peak_coil_stress_mpa=self.peak_stress_mpa,
            critical_current_ratio=self.current_ratio,
            quench_margin_k=quench_margin,
            nzpv_mps=self.nzpv_mps,
            quench_warning=self.quench_warning,
            coil_id=self.coil_id
        )

class PlasmaCoreDigitalTwin:
    """Subsystem 2: Quasi-Isodynamic Plasma Core & MHD Confinement"""
    def __init__(self):
        self.te_kev = 14.8
        self.ti_kev = 14.2
        self.density_1e20 = 1.85
        self.tau_e_s = 1.65
        self.beta_pct = 4.25
        self.qi_orbit_loss = 0.0012

    def update(self, mode: OperationalMode, time_elapsed: float = 0.0):
        if mode == OperationalMode.MODE_PELLET_REFUELING_BURST:
            # Pellet frozen D-T injection causes rapid density spike and transient cooling
            self.density_1e20 = min(3.4, 1.85 + 1.55 * np.sin(min(np.pi, time_elapsed * 0.8)))
            self.te_kev = max(9.5, 14.8 - 3.2 * np.sin(min(np.pi, time_elapsed * 0.8)))
            self.ti_kev = max(10.0, 14.2 - 2.5 * np.sin(min(np.pi, time_elapsed * 0.8)))
            self.tau_e_s = 1.95 # Confinement improves with higher density in stellarator
            self.beta_pct = 5.85
            self.qi_orbit_loss = 0.0010
            mhd_quiescent = True
        elif mode == OperationalMode.MODE_IMPURITY_ACCUMULATION:
            # Radiative collapse from tungsten wall sputtering
            decay = min(1.0, time_elapsed / 8.0)
            self.te_kev = max(3.5, 14.8 - 11.0 * decay)
            self.ti_kev = max(3.8, 14.2 - 10.2 * decay)
            self.density_1e20 = max(0.8, 1.85 - 0.9 * decay)
            self.tau_e_s = max(0.4, 1.65 - 1.2 * decay)
            self.beta_pct = max(0.9, 4.25 - 3.2 * decay)
            self.qi_orbit_loss = 0.0150
            mhd_quiescent = False
        elif mode == OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH:
            # Confinement degrades as coil field drops
            decay = min(1.0, time_elapsed / 5.0)
            self.te_kev = max(0.5, 14.8 - 14.0 * decay)
            self.ti_kev = max(0.5, 14.2 - 13.5 * decay)
            self.density_1e20 = max(0.1, 1.85 - 1.7 * decay)
            self.tau_e_s = max(0.05, 1.65 - 1.55 * decay)
            self.beta_pct = 0.2
            self.qi_orbit_loss = 0.085
            mhd_quiescent = False
        elif mode == OperationalMode.MODE_STARTUP_RAMP:
            ramp = min(1.0, time_elapsed / 10.0)
            self.te_kev = 1.0 + 13.8 * ramp
            self.ti_kev = 0.8 + 13.4 * ramp
            self.density_1e20 = 0.2 + 1.65 * ramp
            self.tau_e_s = 0.3 + 1.35 * ramp
            self.beta_pct = 0.5 + 3.75 * ramp
            self.qi_orbit_loss = 0.0015
            mhd_quiescent = True
        else:
            # Normal steady state
            self.te_kev = 14.8 + float(np.random.normal(0, 0.15))
            self.ti_kev = 14.2 + float(np.random.normal(0, 0.15))
            self.density_1e20 = 1.85 + float(np.random.normal(0, 0.02))
            self.tau_e_s = 1.65 + float(np.random.normal(0, 0.02))
            self.beta_pct = 4.25 + float(np.random.normal(0, 0.05))
            self.qi_orbit_loss = 0.0012
            mhd_quiescent = True

        lawson = self.density_1e20 * self.ti_kev * self.tau_e_s
        return PlasmaCoreTelemetry(
            electron_temp_kev=self.te_kev,
            ion_temp_kev=self.ti_kev,
            electron_density_1e20_m3=self.density_1e20,
            energy_confinement_tau_s=self.tau_e_s,
            lawson_triple_product_kev_s_m3=lawson,
            toroidal_beta_percent=self.beta_pct,
            qi_neoclassical_loss_fraction=self.qi_orbit_loss,
            mhd_quiescent=mhd_quiescent
        )

class DivertorDigitalTwin:
    """Subsystem 3: Island Divertor & Scrape-off Layer (SOL) Heat Exhaust"""
    def __init__(self):
        self.heat_flux_mw_m2 = 4.2
        self.target_temp_c = 485.0
        self.detachment = True
        self.impurity_seeding = 1.45
        self.sol_density_1e19 = 2.4

    def update(self, mode: OperationalMode, time_elapsed: float = 0.0):
        if mode == OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT:
            # Radiative detachment lost: heat flux shoots past 10 MW/m^2 engineering limit
            surge = min(1.0, time_elapsed / 4.0)
            self.heat_flux_mw_m2 = 4.2 + 12.6 * surge + float(np.random.normal(0, 0.3)) # ~16.8 MW/m^2
            self.target_temp_c = 485.0 + 510.0 * surge                                  # ~995 °C
            self.detachment = False
            self.impurity_seeding = max(0.1, 1.45 - 1.3 * surge)                       # Puff failure
            self.sol_density_1e19 = 1.2
            overload = self.heat_flux_mw_m2 > 10.0
        elif mode == OperationalMode.MODE_PELLET_REFUELING_BURST:
            # Moderate divertor heat load increase during density wave
            self.heat_flux_mw_m2 = 5.8 + float(np.random.normal(0, 0.2))
            self.target_temp_c = 540.0 + float(np.random.normal(0, 5.0))
            self.detachment = True
            self.impurity_seeding = 2.1
            self.sol_density_1e19 = 3.8
            overload = False
        elif mode == OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH:
            self.heat_flux_mw_m2 = max(0.2, 4.2 - 0.8 * time_elapsed)
            self.target_temp_c = max(100.0, 485.0 - 50.0 * time_elapsed)
            self.detachment = True
            self.impurity_seeding = 0.0
            self.sol_density_1e19 = 0.2
            overload = False
        else:
            # Steady state with active impurity seeding
            self.heat_flux_mw_m2 = 4.2 + float(np.random.normal(0, 0.15))
            self.target_temp_c = 485.0 + float(np.random.normal(0, 3.0))
            self.detachment = True
            self.impurity_seeding = 1.45 + float(np.random.normal(0, 0.05))
            self.sol_density_1e19 = 2.4 + float(np.random.normal(0, 0.08))
            overload = False

        return DivertorTelemetry(
            peak_heat_flux_mw_per_m2=self.heat_flux_mw_m2,
            target_surface_temp_c=self.target_temp_c,
            detachment_achieved=self.detachment,
            impurity_seeding_rate_pa_m3_s=self.impurity_seeding,
            sol_plasma_density_1e19_m3=self.sol_density_1e19,
            thermal_overload_alert=overload
        )

class BreedingBlanketDigitalTwin:
    """Subsystem 4: Liquid PbLi Breeding Blanket & Tritium Extraction"""
    def __init__(self):
        self.inlet_temp_c = 350.0
        self.outlet_temp_c = 495.0
        self.neutron_wall_load_mw_m2 = 1.85
        self.tbr = 1.15
        self.tritium_rate_g_day = 142.0
        self.coolant_flow_kg_s = 280.0

    def update(self, fusion_power_mw: float, mode: OperationalMode):
        if fusion_power_mw <= 0.1:
            self.inlet_temp_c = 300.0
            self.outlet_temp_c = 310.0
            self.neutron_wall_load_mw_m2 = 0.0
            self.tbr = 0.0
            self.tritium_rate_g_day = 0.0
            self.coolant_flow_kg_s = 50.0
        else:
            # Blanket neutron power scales with fusion thermal power
            power_ratio = fusion_power_mw / 255.0
            self.neutron_wall_load_mw_m2 = 1.85 * power_ratio + float(np.random.normal(0, 0.02))
            self.outlet_temp_c = 350.0 + 145.0 * power_ratio + float(np.random.normal(0, 1.0))
            self.inlet_temp_c = 350.0 + float(np.random.normal(0, 0.5))
            self.tbr = 1.15 + float(np.random.normal(0, 0.005))
            self.tritium_rate_g_day = 142.0 * power_ratio
            self.coolant_flow_kg_s = 280.0

        return BlanketTelemetry(
            pb_li_inlet_temp_c=self.inlet_temp_c,
            pb_li_outlet_temp_c=self.outlet_temp_c,
            neutron_wall_load_mw_per_m2=self.neutron_wall_load_mw_m2,
            tritium_breeding_ratio=self.tbr,
            tritium_extraction_rate_g_per_day=self.tritium_rate_g_day,
            coolant_flow_rate_kg_s=self.coolant_flow_kg_s
        )

# ============================================================================
# Main Master Multi-Subsystem Digital Twin Engine
# ============================================================================

class DigitalTwinEngine:
    def __init__(self, port=9004, api_port=9005):
        self.port = port
        self.api_port = api_port
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[DIGITAL-TWIN] Initializing SKHY PyTorch PINN Surrogate Engine on device: {self.device}")

        self.model = StellaratorPINN(input_dim=8, mesh_points=32).to(self.device)
        self.model.eval()

        self.sim_step = 0
        self.active_mode = OperationalMode.MODE_STEADY_STATE_NOMINAL
        self.mode_start_time = time.time()

        # Initialize Subsystems
        self.coils_subsystem = HTSCoilsDigitalTwin()
        self.plasma_subsystem = PlasmaCoreDigitalTwin()
        self.divertor_subsystem = DivertorDigitalTwin()
        self.blanket_subsystem = BreedingBlanketDigitalTwin()

        # UDP socket for sending multi-subsystem reports
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def set_mode(self, mode: OperationalMode):
        self.active_mode = mode
        self.mode_start_time = time.time()
        print(f"[DIGITAL-TWIN] Operational Mode switched to: {OperationalMode.Name(mode)}")

    def compute_all_subsystems(self, quench_diag: QuenchDiagnostic = None) -> SubsystemTelemetryReport:
        self.sim_step += 1
        now_ns = int(time.time() * 1e9)
        time_in_mode = time.time() - self.mode_start_time

        # Update Subsystems
        coil_telemetry = self.coils_subsystem.update(self.active_mode, time_in_mode)
        plasma_telemetry = self.plasma_subsystem.update(self.active_mode, time_in_mode)
        divertor_telemetry = self.divertor_subsystem.update(self.active_mode, time_in_mode)

        # --------------------------------------------------------------------
        # Plant Power Balance Calculations (Sam Wurzel Framework)
        # --------------------------------------------------------------------
        if self.active_mode == OperationalMode.MODE_STEADY_STATE_NOMINAL:
            heating_mw = 25.0
            q_sci = 10.2 + float(np.random.normal(0, 0.1))
            fusion_mw = q_sci * heating_mw
        elif self.active_mode == OperationalMode.MODE_PELLET_REFUELING_BURST:
            heating_mw = 25.0
            q_sci = 16.5 + float(np.random.normal(0, 0.3))
            fusion_mw = q_sci * heating_mw
        elif self.active_mode == OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT:
            heating_mw = 25.0
            q_sci = 9.8 + float(np.random.normal(0, 0.1))
            fusion_mw = q_sci * heating_mw
        elif self.active_mode == OperationalMode.MODE_IMPURITY_ACCUMULATION:
            heating_mw = 25.0
            q_sci = max(0.5, 10.2 - 8.5 * min(1.0, time_in_mode / 8.0))
            fusion_mw = q_sci * heating_mw
        elif self.active_mode == OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH:
            heating_mw = 5.0
            q_sci = 0.0
            fusion_mw = 0.0
        elif self.active_mode == OperationalMode.MODE_STARTUP_RAMP:
            ramp = min(1.0, time_in_mode / 10.0)
            heating_mw = 5.0 + 20.0 * ramp
            q_sci = 0.5 + 9.7 * ramp
            fusion_mw = q_sci * heating_mw
        else:
            heating_mw = 25.0
            q_sci = 10.2
            fusion_mw = 255.0

        blanket_telemetry = self.blanket_subsystem.update(fusion_mw, self.active_mode)

        total_exit_power_mw = fusion_mw + heating_mw
        eta_thermal = 0.38
        gross_elec_mw = total_exit_power_mw * eta_thermal

        eta_heating = 0.60
        recirc_heat_mw = heating_mw / eta_heating
        parasitic_cryo_mw = 8.5 if self.active_mode != OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH else 14.5
        total_recirc_mw = recirc_heat_mw + parasitic_cryo_mw

        net_elec_mw = gross_elec_mw - total_recirc_mw
        q_eng = gross_elec_mw / total_recirc_mw if total_recirc_mw > 0 else 0.0
        net_electricity = net_elec_mw > 0.0

        # PyTorch PINN surrogate mesh inference
        input_features = torch.tensor([[
            coil_telemetry.coil_temperature_k / 100.0,
            divertor_telemetry.peak_heat_flux_mw_per_m2 / 20.0,
            plasma_telemetry.electron_temp_kev / 30.0,
            plasma_telemetry.electron_density_1e20_m3 / 4.0,
            120.0 / 200.0,
            0.2 / 50.0,
            coil_telemetry.nzpv_mps / 0.1,
            1.0 if coil_telemetry.quench_warning else 0.0
        ]], dtype=torch.float32).to(self.device)

        with torch.no_grad():
            mesh, thermal_map, beta, axis_shift, peak_strain, _, _ = self.model(input_features)

        mesh_np = mesh.cpu().numpy()[0]
        r_coords = (1.5 + 0.3 * np.cos(np.linspace(0, 2*np.pi, 32)) + mesh_np[:, 0] * 0.05).tolist()
        z_coords = (0.3 * np.sin(np.linspace(0, 2*np.pi, 32)) + mesh_np[:, 1] * 0.05).tolist()
        phi_coords = np.linspace(0, 2*np.pi, 32).tolist()
        thermal_loads = (coil_telemetry.coil_temperature_k + thermal_map.cpu().numpy()[0] * 5.0).tolist()

        envelope = Envelope(
            timestamp_ns=now_ns,
            source_id="TAMI-DIGITAL-TWIN-MASTER",
            purdue_level=PurdueLevel.LEVEL_4_PLANT_MANAGEMENT,
            security_token="TLS13-TOKEN-SECURE-L4-TWIN-321",
            sequence_number=self.sim_step,
            payload_type=PayloadType.PAYLOAD_SUBSYSTEM_REPORT
        )

        power_balance_state = DigitalTwinState(
            envelope=envelope,
            simulation_step=self.sim_step,
            magnetic_flux_surface_r=r_coords,
            magnetic_flux_surface_z=z_coords,
            magnetic_flux_surface_phi=phi_coords,
            localized_thermal_loads_k=thermal_loads,
            peak_coil_strain_mpa=coil_telemetry.peak_coil_stress_mpa,
            plasma_beta_toroidal=plasma_telemetry.toroidal_beta_percent,
            magnetic_axis_displacement_m=float(axis_shift.cpu().item()),
            equilibrium_converged=plasma_telemetry.mhd_quiescent,
            pinn_loss=0.0012,
            scientific_gain_q_sci=q_sci,
            engineering_gain_q_eng=q_eng,
            fusion_power_mw=fusion_mw,
            heating_power_mw=heating_mw,
            gross_electric_power_mw=gross_elec_mw,
            net_electric_power_mw=net_elec_mw,
            recirculating_power_mw=recirc_heat_mw,
            parasitic_cryo_power_mw=parasitic_cryo_mw,
            lawson_triple_product_kev_s_m3=plasma_telemetry.lawson_triple_product_kev_s_m3,
            net_electricity_achieved=net_electricity
        )

        mode_name = OperationalMode.Name(self.active_mode)
        mode_desc = {
            OperationalMode.MODE_STEADY_STATE_NOMINAL: "Normal Steady-State Burn: QI high-confinement flattop",
            OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT: "Divertor Detachment Anomaly: Peak heat flux > 10 MW/m^2",
            OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH: "REBCO Coil Hotspot: Quench runaway in Module 3",
            OperationalMode.MODE_PELLET_REFUELING_BURST: "Cryogenic D-T Pellet Injection: High density alpha burst",
            OperationalMode.MODE_IMPURITY_ACCUMULATION: "Tungsten Impurity Core Influx: Radiative cooling collapse",
            OperationalMode.MODE_STARTUP_RAMP: "Startup Ignition Sequence: Coil ramp-up & ECRH microwave breakdown"
        }.get(self.active_mode, "Unknown Mode")

        report = SubsystemTelemetryReport(
            envelope=envelope,
            active_mode=self.active_mode,
            mode_description=mode_desc,
            coil_cryo=coil_telemetry,
            plasma_core=plasma_telemetry,
            divertor=divertor_telemetry,
            blanket=blanket_telemetry,
            power_balance=power_balance_state
        )

        return report

    def listen_and_evaluate(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", self.port))
        print(f"[DIGITAL-TWIN] Listening for telemetry stream on UDP 127.0.0.1:{self.port}...")

        try:
            while True:
                data, _ = sock.recvfrom(65536)
                try:
                    diag = QuenchDiagnostic()
                    diag.ParseFromString(data)

                    # Update internal mode if quench detected from Level 1
                    if diag.quench_detected and self.active_mode != OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH:
                        self.set_mode(OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH)

                    report = self.compute_all_subsystems(diag)

                    # Broadcast SubsystemTelemetryReport to Data Lake API (Port 9005)
                    serialized_report = report.SerializeToString()
                    self.tx_sock.sendto(serialized_report, ("127.0.0.1", self.api_port))

                    if self.sim_step % 20 == 0 or diag.quench_detected:
                        pb = report.power_balance
                        print(
                            f"[DIGITAL-TWIN] Step {self.sim_step:04d} | Mode: {report.mode_description[:25]}... | "
                            f"Q_sci: {pb.scientific_gain_q_sci:.2f} | P_net: {pb.net_electric_power_mw:.1f} MW | "
                            f"Coil: {report.coil_cryo.coil_temperature_k:.1f}K | Div: {report.divertor.peak_heat_flux_mw_per_m2:.1f} MW/m²"
                        )
                except Exception:
                    pass
        except KeyboardInterrupt:
            print("\n[DIGITAL-TWIN] Surrogate model engine shut down gracefully.")
        finally:
            sock.close()
            self.tx_sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SKHY Modular Stellarator Digital Twin Engine")
    parser.add_argument("--port", type=int, default=9004, help="UDP listening port")
    parser.add_argument("--api-port", type=int, default=9005, help="Data Lake API UDP port")
    parser.add_argument("--mode", type=str, default="steady_state",
                        choices=["steady_state", "divertor_fault", "quench", "pellet_burst", "impurity", "startup"])
    args = parser.parse_args()

    mode_map = {
        "steady_state": OperationalMode.MODE_STEADY_STATE_NOMINAL,
        "divertor_fault": OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT,
        "quench": OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH,
        "pellet_burst": OperationalMode.MODE_PELLET_REFUELING_BURST,
        "impurity": OperationalMode.MODE_IMPURITY_ACCUMULATION,
        "startup": OperationalMode.MODE_STARTUP_RAMP
    }

    engine = DigitalTwinEngine(port=args.port, api_port=args.api_port)
    engine.set_mode(mode_map[args.mode])
    engine.listen_and_evaluate()
