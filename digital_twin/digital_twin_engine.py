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
    PurdueLevel, PayloadType, OperationalMode, ReactorType,
    Envelope, DigitalTwinState, QuenchDiagnostic,
    CoilCryoTelemetry, PlasmaCoreTelemetry, DivertorTelemetry,
    BlanketTelemetry, SubsystemTelemetryReport,
    TokamakCoreTelemetry, IcfCoreTelemetry, StellaratorCoreTelemetry
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
# Tokamak & ICF Core Physics Subsystem Digital Twins
# ============================================================================

class TokamakCoreDigitalTwin:
    """Subsystem: Tokamak Core Physics, Central Solenoid, Divertor & Disruption Predictor"""
    def __init__(self):
        self.plasma_current_ma = 15.0
        self.cs_current_ka = 42.0
        self.safety_factor_q95 = 3.25
        self.loop_voltage_v = 0.12
        self.divertor_flux_mw_m2 = 6.5
        self.vertical_disp_mm = 0.0
        self.elm_freq_hz = 12.0
        self.disruption_warning = False
        self.runaway_current_ma = 0.0
        self.internal_inductance = 0.85
        self.greenwald_fraction = 0.72

    def update(self, mode: OperationalMode, time_elapsed: float = 0.0) -> TokamakCoreTelemetry:
        if mode == OperationalMode.MODE_TOKAMAK_MAJOR_DISRUPTION:
            # Thermal quench -> Current quench runaway
            decay = min(1.0, time_elapsed / 2.5)
            self.plasma_current_ma = max(0.1, 15.0 * (1.0 - decay))
            self.loop_voltage_v = 150.0 * np.exp(-time_elapsed) + float(np.random.normal(0, 5.0))
            self.safety_factor_q95 = max(1.1, 3.25 - 2.1 * decay)
            self.divertor_flux_mw_m2 = min(35.0, 6.5 + 28.5 * np.exp(-((time_elapsed - 0.5)**2) / 0.2))
            self.disruption_warning = True
            self.runaway_current_ma = min(4.2, 3.5 * decay)
            self.internal_inductance = 1.65
        elif mode == OperationalMode.MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT:
            drift = min(1.0, time_elapsed / 3.0)
            self.vertical_disp_mm = 120.0 * drift + float(np.random.normal(0, 3.0))
            self.divertor_flux_mw_m2 = 6.5 + 18.0 * drift
            self.disruption_warning = self.vertical_disp_mm > 50.0
            self.safety_factor_q95 = max(1.8, 3.25 - 1.2 * drift)
        elif mode == OperationalMode.MODE_TOKAMAK_UNMITIGATED_ELM_BURST:
            self.elm_freq_hz = 45.0 + float(np.random.normal(0, 3.0))
            self.divertor_flux_mw_m2 = 24.5 + 6.0 * np.sin(time_elapsed * 25.0)
            self.disruption_warning = False
        elif mode == OperationalMode.MODE_TOKAMAK_RUNAWAY_ELECTRON_AVALANCHE:
            self.runaway_current_ma = 3.8 + float(np.random.normal(0, 0.1))
            self.loop_voltage_v = 45.0 + float(np.random.normal(0, 2.0))
            self.disruption_warning = True
        elif mode == OperationalMode.MODE_TOKAMAK_NEOCLASSICAL_TEARING_MODE:
            self.safety_factor_q95 = 2.15 + float(np.random.normal(0, 0.05))
            self.internal_inductance = 1.15
            self.disruption_warning = False
            self.divertor_flux_mw_m2 = 5.2
        else: # MODE_TOKAMAK_NOMINAL_BURNTIME or default
            self.plasma_current_ma = 15.0 + float(np.random.normal(0, 0.05))
            self.cs_current_ka = 42.0 - 0.2 * time_elapsed
            self.safety_factor_q95 = 3.25 + float(np.random.normal(0, 0.02))
            self.loop_voltage_v = 0.12 + float(np.random.normal(0, 0.01))
            self.divertor_flux_mw_m2 = 6.5 + float(np.random.normal(0, 0.2))
            self.vertical_disp_mm = float(np.random.normal(0, 1.2))
            self.elm_freq_hz = 12.0 + float(np.random.normal(0, 0.5))
            self.disruption_warning = False
            self.runaway_current_ma = 0.0
            self.internal_inductance = 0.85
            self.greenwald_fraction = 0.72

        return TokamakCoreTelemetry(
            plasma_current_ma=self.plasma_current_ma,
            central_solenoid_current_ka=self.cs_current_ka,
            safety_factor_q95=self.safety_factor_q95,
            loop_voltage_v=self.loop_voltage_v,
            poloidal_divertor_heat_flux_mw_m2=self.divertor_flux_mw_m2,
            vertical_displacement_z_mm=self.vertical_disp_mm,
            elm_frequency_hz=self.elm_freq_hz,
            disruption_warning=self.disruption_warning,
            runaway_electron_current_ma=self.runaway_current_ma,
            internal_inductance_li=self.internal_inductance,
            greenwald_density_fraction=self.greenwald_fraction
        )

class IcfCoreDigitalTwin:
    """Subsystem: Inertial Confinement Fusion (ICF) Driver, Beam Balance & Target Chamber"""
    def __init__(self):
        self.laser_energy_mj = 2.15
        self.repetition_rate_hz = 5.0
        self.target_gain_g = 85.0
        self.implosion_symmetry_rms = 0.45
        self.ablation_pressure_mbar = 180.0
        self.timing_jitter_ps = 4.2
        self.optics_trans_pct = 98.5
        self.tracking_error_um = 8.5
        self.chamber_pressure_pa = 0.05
        self.shots_count = 12500
        self.rt_instability_alert = False

    def update(self, mode: OperationalMode, time_elapsed: float = 0.0) -> IcfCoreTelemetry:
        self.shots_count += int(self.repetition_rate_hz * 0.5)

        if mode == OperationalMode.MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY:
            self.implosion_symmetry_rms = 2.85 + float(np.random.normal(0, 0.15))
            self.target_gain_g = max(2.5, 85.0 - 80.0 * min(1.0, time_elapsed / 3.0))
            self.rt_instability_alert = True
        elif mode == OperationalMode.MODE_ICF_LASER_POWER_IMBALANCE_JITTER:
            self.timing_jitter_ps = 28.5 + float(np.random.normal(0, 2.0))
            self.implosion_symmetry_rms = 1.95 + float(np.random.normal(0, 0.1))
            self.target_gain_g = 18.0 + float(np.random.normal(0, 2.0))
            self.rt_instability_alert = False
        elif mode == OperationalMode.MODE_ICF_FINAL_OPTICS_DEBRIS_DAMAGE:
            degrade = min(1.0, time_elapsed / 5.0)
            self.optics_trans_pct = 98.5 - 18.0 * degrade
            self.target_gain_g = 85.0 * ((self.optics_trans_pct / 100.0) ** 2)
            self.rt_instability_alert = False
        elif mode == OperationalMode.MODE_ICF_TARGET_TRACKING_INJECTION_MISS:
            self.tracking_error_um = 52.0 + float(np.random.normal(0, 4.0))
            self.target_gain_g = 0.05
            self.rt_instability_alert = False
        elif mode == OperationalMode.MODE_ICF_CHAMBER_CLEARING_PRESSURE_CHOKE:
            self.chamber_pressure_pa = 4.8 + float(np.random.normal(0, 0.3))
            self.target_gain_g = 22.0
            self.rt_instability_alert = False
        else: # MODE_ICF_NOMINAL_REPETITION_PULSE
            self.laser_energy_mj = 2.15 + float(np.random.normal(0, 0.01))
            self.repetition_rate_hz = 5.0
            self.target_gain_g = 85.0 + float(np.random.normal(0, 1.2))
            self.implosion_symmetry_rms = 0.45 + float(np.random.normal(0, 0.03))
            self.ablation_pressure_mbar = 180.0 + float(np.random.normal(0, 2.0))
            self.timing_jitter_ps = 4.2 + float(np.random.normal(0, 0.2))
            self.optics_trans_pct = 98.5 + float(np.random.normal(0, 0.1))
            self.tracking_error_um = 8.5 + float(np.random.normal(0, 0.5))
            self.chamber_pressure_pa = 0.05 + float(np.random.normal(0, 0.005))
            self.rt_instability_alert = False

        return IcfCoreTelemetry(
            driver_laser_energy_mj=self.laser_energy_mj,
            repetition_rate_hz=self.repetition_rate_hz,
            target_gain_g=self.target_gain_g,
            implosion_symmetry_rms_pct=self.implosion_symmetry_rms,
            capsule_ablation_pressure_mbar=self.ablation_pressure_mbar,
            beam_timing_jitter_ps=self.timing_jitter_ps,
            final_optics_transmission_pct=self.optics_trans_pct,
            target_tracking_error_um=self.tracking_error_um,
            target_chamber_pressure_pa=self.chamber_pressure_pa,
            total_shots_fired=self.shots_count,
            rayleigh_taylor_instability_alert=self.rt_instability_alert
        )

# ============================================================================
# Main Master Multi-Subsystem & Multi-Reactor Digital Twin Engine
# ============================================================================

class DigitalTwinEngine:
    def __init__(self, port=9004, api_port=9005, reactor_type=ReactorType.REACTOR_QI_STELLARATOR):
        self.port = port
        self.api_port = api_port
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[DIGITAL-TWIN] Initializing SKHY PyTorch PINN Multi-Reactor Engine on device: {self.device}")

        self.model = StellaratorPINN(input_dim=8, mesh_points=32).to(self.device)
        self.model.eval()

        self.sim_step = 0
        self.active_reactor = reactor_type
        self.active_mode = OperationalMode.MODE_STEADY_STATE_NOMINAL
        self.mode_start_time = time.time()

        # Initialize Subsystem Twins
        self.coils_subsystem = HTSCoilsDigitalTwin()
        self.plasma_subsystem = PlasmaCoreDigitalTwin()
        self.divertor_subsystem = DivertorDigitalTwin()
        self.blanket_subsystem = BreedingBlanketDigitalTwin()
        self.tokamak_subsystem = TokamakCoreDigitalTwin()
        self.icf_subsystem = IcfCoreDigitalTwin()

        # UDP socket for sending multi-subsystem reports
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def set_reactor_type(self, reactor_type: ReactorType):
        self.active_reactor = reactor_type
        if reactor_type == ReactorType.REACTOR_TOKAMAK:
            self.active_mode = OperationalMode.MODE_TOKAMAK_NOMINAL_BURNTIME
        elif reactor_type == ReactorType.REACTOR_ICF:
            self.active_mode = OperationalMode.MODE_ICF_NOMINAL_REPETITION_PULSE
        else:
            self.active_mode = OperationalMode.MODE_STEADY_STATE_NOMINAL
        self.mode_start_time = time.time()
        print(f"[DIGITAL-TWIN] Reactor Concept switched to: {ReactorType.Name(reactor_type)}")

    def set_mode(self, mode: OperationalMode):
        self.active_mode = mode
        self.mode_start_time = time.time()
        print(f"[DIGITAL-TWIN] Operational Mode switched to: {OperationalMode.Name(mode)}")

    def compute_all_subsystems(self, quench_diag: QuenchDiagnostic = None) -> SubsystemTelemetryReport:
        self.sim_step += 1
        now_ns = int(time.time() * 1e9)
        time_in_mode = time.time() - self.mode_start_time

        # Update core physics based on active reactor type
        coil_telemetry = self.coils_subsystem.update(self.active_mode, time_in_mode)
        plasma_telemetry = self.plasma_subsystem.update(self.active_mode, time_in_mode)
        divertor_telemetry = self.divertor_subsystem.update(self.active_mode, time_in_mode)
        tokamak_telemetry = self.tokamak_subsystem.update(self.active_mode, time_in_mode)
        icf_telemetry = self.icf_subsystem.update(self.active_mode, time_in_mode)

        # --------------------------------------------------------------------
        # Multi-Physics Reactor Power Balance Calculations
        # --------------------------------------------------------------------
        if self.active_reactor == ReactorType.REACTOR_ICF:
            # Pulsed Inertial Confinement Fusion Power Flow
            driver_mj = icf_telemetry.driver_laser_energy_mj
            rep_rate = icf_telemetry.repetition_rate_hz
            gain_g = icf_telemetry.target_gain_g
            heating_mw = driver_mj * rep_rate # Time-averaged laser energy delivered to chamber (MW)
            q_sci = gain_g
            fusion_mw = heating_mw * gain_g

            eta_driver = 0.15 # Laser driver wall-plug electrical efficiency (~15%)
            recirc_heat_mw = heating_mw / eta_driver
            parasitic_cryo_mw = 12.0 # Pellet factory & cryogenic target positioner
            eta_thermal = 0.38
            total_recirc_mw = recirc_heat_mw + parasitic_cryo_mw

        elif self.active_reactor == ReactorType.REACTOR_TOKAMAK:
            # Advanced Tokamak Power Flow
            heating_mw = 35.0 # Combined NBI, ECRH, ICRF auxiliary heating
            if self.active_mode == OperationalMode.MODE_TOKAMAK_NOMINAL_BURNTIME:
                q_sci = 10.5 + float(np.random.normal(0, 0.15))
            elif self.active_mode == OperationalMode.MODE_TOKAMAK_MAJOR_DISRUPTION:
                q_sci = 0.05
            elif self.active_mode == OperationalMode.MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT:
                q_sci = 3.2
            elif self.active_mode == OperationalMode.MODE_TOKAMAK_UNMITIGATED_ELM_BURST:
                q_sci = 8.5
            elif self.active_mode == OperationalMode.MODE_TOKAMAK_NEOCLASSICAL_TEARING_MODE:
                q_sci = 4.2
            else:
                q_sci = 9.5
            fusion_mw = q_sci * heating_mw

            eta_heating = 0.55
            recirc_heat_mw = heating_mw / eta_heating
            parasitic_cryo_mw = 14.0 # TF/PF/CS Superconducting coils
            eta_thermal = 0.38
            total_recirc_mw = recirc_heat_mw + parasitic_cryo_mw

        else: # REACTOR_QI_STELLARATOR
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

            eta_heating = 0.60
            recirc_heat_mw = heating_mw / eta_heating
            parasitic_cryo_mw = 8.5 if self.active_mode != OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH else 14.5
            eta_thermal = 0.38
            total_recirc_mw = recirc_heat_mw + parasitic_cryo_mw

        # Universal Breeding Blanket
        blanket_telemetry = self.blanket_subsystem.update(fusion_mw, self.active_mode)

        total_exit_power_mw = fusion_mw + heating_mw
        gross_elec_mw = total_exit_power_mw * eta_thermal
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
            # Stellarator
            OperationalMode.MODE_STEADY_STATE_NOMINAL: "Normal Steady-State Burn: QI high-confinement flattop",
            OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT: "Divertor Detachment Anomaly: Peak heat flux > 10 MW/m^2",
            OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH: "REBCO Coil Hotspot: Quench runaway in Module 3",
            OperationalMode.MODE_PELLET_REFUELING_BURST: "Cryogenic D-T Pellet Injection: High density alpha burst",
            OperationalMode.MODE_IMPURITY_ACCUMULATION: "Tungsten Impurity Core Influx: Radiative cooling collapse",
            OperationalMode.MODE_STARTUP_RAMP: "Startup Ignition Sequence: Coil ramp-up & ECRH microwave breakdown",
            # Tokamak
            OperationalMode.MODE_TOKAMAK_NOMINAL_BURNTIME: "Tokamak Nominal H-Mode Burn: Ip=15MA inductive flattop",
            OperationalMode.MODE_TOKAMAK_MAJOR_DISRUPTION: "Tokamak Major Disruption: Thermal quench & current collapse",
            OperationalMode.MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT: "Tokamak VDE: Vertical stability lost, wall impact",
            OperationalMode.MODE_TOKAMAK_UNMITIGATED_ELM_BURST: "Tokamak Unmitigated ELM: Divertor target heat spike",
            OperationalMode.MODE_TOKAMAK_RUNAWAY_ELECTRON_AVALANCHE: "Tokamak Runaway Beam: Relativistic electron avalanche",
            OperationalMode.MODE_TOKAMAK_NEOCLASSICAL_TEARING_MODE: "Tokamak NTM Island: Magnetic island degrades tau_E",
            # ICF
            OperationalMode.MODE_ICF_NOMINAL_REPETITION_PULSE: "ICF High-Rep Rate Pulse: 5Hz shot flattop, G=85",
            OperationalMode.MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY: "ICF Rayleigh-Taylor Instability: Capsule mix collapse",
            OperationalMode.MODE_ICF_LASER_POWER_IMBALANCE_JITTER: "ICF Laser Jitter: Power imbalance & timing jitter",
            OperationalMode.MODE_ICF_FINAL_OPTICS_DEBRIS_DAMAGE: "ICF Optical Damage: Debris shield transmission degraded",
            OperationalMode.MODE_ICF_TARGET_TRACKING_INJECTION_MISS: "ICF Target Injection Miss: Off-center dud shot",
            OperationalMode.MODE_ICF_CHAMBER_CLEARING_PRESSURE_CHOKE: "ICF Chamber Choke: Incomplete post-shot vapor exhaust"
        }.get(self.active_mode, f"Active Mode: {mode_name}")

        # Construct polymorphic SubsystemTelemetryReport
        report = SubsystemTelemetryReport(
            envelope=envelope,
            reactor_type=self.active_reactor,
            active_mode=self.active_mode,
            mode_description=mode_desc,
            blanket=blanket_telemetry,
            power_balance=power_balance_state,
            coil_cryo=coil_telemetry,
            plasma_core=plasma_telemetry,
            divertor=divertor_telemetry
        )

        # Populate appropriate reactor_core oneof
        if self.active_reactor == ReactorType.REACTOR_TOKAMAK:
            report.tokamak_core.CopyFrom(tokamak_telemetry)
        elif self.active_reactor == ReactorType.REACTOR_ICF:
            report.icf_core.CopyFrom(icf_telemetry)
        else:
            report.stellarator_core.CopyFrom(StellaratorCoreTelemetry(
                coil_cryo=coil_telemetry,
                plasma_core=plasma_telemetry,
                divertor=divertor_telemetry
            ))

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
                        reactor_name = ReactorType.Name(report.reactor_type)
                        print(
                            f"[DIGITAL-TWIN] Step {self.sim_step:04d} | Reactor: {reactor_name} | "
                            f"Mode: {report.mode_description[:30]}... | "
                            f"Q_sci: {pb.scientific_gain_q_sci:.2f} | P_net: {pb.net_electric_power_mw:.1f} MW"
                        )
                except Exception:
                    pass
        except KeyboardInterrupt:
            print("\n[DIGITAL-TWIN] Surrogate model engine shut down gracefully.")
        finally:
            sock.close()
            self.tx_sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SKHY Multi-Reactor Digital Twin Engine")
    parser.add_argument("--port", type=int, default=9004, help="UDP listening port")
    parser.add_argument("--api-port", type=int, default=9005, help="Data Lake API UDP port")
    parser.add_argument("--reactor", type=str, default="stellarator",
                        choices=["stellarator", "tokamak", "icf"], help="Active fusion reactor concept")
    parser.add_argument("--mode", type=str, default="nominal", help="Initial operational mode")
    args = parser.parse_args()

    reactor_map = {
        "stellarator": ReactorType.REACTOR_QI_STELLARATOR,
        "tokamak": ReactorType.REACTOR_TOKAMAK,
        "icf": ReactorType.REACTOR_ICF
    }

    engine = DigitalTwinEngine(port=args.port, api_port=args.api_port, reactor_type=reactor_map[args.reactor])
    engine.listen_and_evaluate()

