#!/usr/bin/env python3
"""
SKHY - TAMI Level 0/1 High-Fidelity Synthetic Telemetry Generator
Simulates real-time multi-physics sensor telemetry for Quasi-Isodynamic (QI) REBCO Stellarators
across normal operations and multiple operational/anomaly feature modes:

Modes Supported:
1. MODE_STEADY_STATE_NOMINAL: Flattop high-confinement QI burn, Q_sci ~ 10.5, P_net > 0, 20K cryo.
2. MODE_DIVERTOR_DETACHMENT_FAULT: Strike-point detachment loss, heat flux > 15 MW/m^2.
3. MODE_HTS_COIL_HOTSPOT_QUENCH: Localized normal zone runaway, FOAS burst > 25 kHz, NZPV acceleration.
4. MODE_PELLET_REFUELING_BURST: Cryogenic D-T frozen pellet injection, density spike, alpha heating burst.
5. MODE_IMPURITY_ACCUMULATION: Tungsten core sputtering, radiative cooling collapse, Q_sci degradation.
6. MODE_STARTUP_RAMP: Coil energization 0-5.5T, ECRH microwave breakdown ignition.
7. MODE_MULTI_CYCLE: Continuous automated sequence transitioning through all states.
"""

import sys
import os
import time
import socket
import struct
import argparse
import numpy as np

# Add parent directory to path to import python_common
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT_DIR)

from python_common.skhy_telemetry_pb2 import (
    PurdueLevel, PayloadType, QuenchSeverity, OperationalMode,
    Envelope, QuenchDiagnostic, CoilCryoTelemetry, PlasmaCoreTelemetry,
    DivertorTelemetry, BlanketTelemetry, DigitalTwinState, SubsystemTelemetryReport
)

class StellaratorSyntheticGenerator:
    def __init__(self,
                 sensor_id="FOAS-HTS-COIL-03A",
                 hub_host="127.0.0.1",
                 tcp_port=9001,
                 udp_edge_port=9003,
                 udp_twin_port=9004,
                 udp_api_port=9005):
        self.sensor_id = sensor_id
        self.hub_host = hub_host
        self.tcp_port = tcp_port
        self.udp_edge_port = udp_edge_port
        self.udp_twin_port = udp_twin_port
        self.udp_api_port = udp_api_port

        self.seq_num = 0
        self.active_mode = OperationalMode.MODE_STEADY_STATE_NOMINAL
        self.mode_start_time = time.time()
        self.cycle_mode_active = False

        # Baseline physical parameters
        self.baseline_temp_k = 20.0
        self.baseline_cap_pf = 120.0
        self.heating_mw = 25.0

        # Sockets
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tcp_sock = None

    def connect_tcp(self):
        try:
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.connect((self.hub_host, self.tcp_port))
            print(f"[SYNTHETIC-GEN] Connected to Level 3 Middleware Hub at {self.hub_host}:{self.tcp_port}")
            return True
        except Exception as e:
            print(f"[SYNTHETIC-GEN] Note: TCP Hub not reachable ({e}) - continuing UDP broadcast")
            self.tcp_sock = None
            return False

    def set_mode(self, mode: OperationalMode):
        self.active_mode = mode
        self.mode_start_time = time.time()
        mode_str = OperationalMode.Name(mode)
        print(f"\n[SYNTHETIC-GEN] >>> OPERATIONAL MODE SWITCHED TO: {mode_str} <<<\n")

    def generate_packets(self) -> tuple[QuenchDiagnostic, SubsystemTelemetryReport]:
        self.seq_num += 1
        now_ns = int(time.time() * 1e9)
        elapsed = time.time() - self.mode_start_time

        mode = self.active_mode

        # ====================================================================
        # Multi-Subsystem Physics State Evaluation
        # ====================================================================

        if mode == OperationalMode.MODE_STEADY_STATE_NOMINAL:
            # 1. Coil & Cryogenics
            temp_k = self.baseline_temp_k + float(np.random.normal(0, 0.05))
            dt_dt = float(np.random.normal(0, 0.01))
            acoustic_freq = float(np.random.uniform(200, 2500))
            acoustic_amp_db = float(np.random.normal(12.0, 1.0))
            cap_pf = self.baseline_cap_pf + float(np.random.normal(0, 0.02))
            dc_dt = float(np.random.normal(0, 0.005))
            nzpv_mps = 0.0
            quench_detected = False
            quench_warning = False
            severity = QuenchSeverity.SEVERITY_NOMINAL
            coil_stress = 145.0 + float(np.random.normal(0, 1.0))
            current_ratio = 0.58

            # 2. Plasma Core
            te_kev = 14.8 + float(np.random.normal(0, 0.1))
            ti_kev = 14.2 + float(np.random.normal(0, 0.1))
            density_1e20 = 1.85 + float(np.random.normal(0, 0.02))
            tau_e_s = 1.65 + float(np.random.normal(0, 0.02))
            beta_pct = 4.25 + float(np.random.normal(0, 0.05))
            qi_loss = 0.0012
            mhd_quiescent = True

            # 3. Divertor
            heat_flux_mw = 4.2 + float(np.random.normal(0, 0.1))
            target_temp_c = 485.0 + float(np.random.normal(0, 2.0))
            detachment = True
            seeding_rate = 1.45
            sol_density = 2.4
            div_overload = False

            # 4. Blanket & Power
            q_sci = 10.2 + float(np.random.normal(0, 0.05))
            heating_mw = 25.0
            fusion_mw = q_sci * heating_mw
            tbr = 1.15

        elif mode == OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT:
            # Divertor impurity gas line fails, heat flux surges
            surge = min(1.0, elapsed / 4.0)
            temp_k = self.baseline_temp_k + float(np.random.normal(0, 0.08))
            dt_dt = float(np.random.normal(0, 0.02))
            acoustic_freq = float(np.random.uniform(500, 4000))
            acoustic_amp_db = float(np.random.normal(16.0, 1.5))
            cap_pf = self.baseline_cap_pf + float(np.random.normal(0, 0.05))
            dc_dt = float(np.random.normal(0, 0.01))
            nzpv_mps = 0.0
            quench_detected = False
            quench_warning = False
            severity = QuenchSeverity.SEVERITY_NOMINAL
            coil_stress = 148.0
            current_ratio = 0.59

            te_kev = 14.5
            ti_kev = 13.9
            density_1e20 = 1.80
            tau_e_s = 1.60
            beta_pct = 4.15
            qi_loss = 0.0014
            mhd_quiescent = True

            # Heat flux shoots to ~16.8 MW/m^2 (safe limit is 10)
            heat_flux_mw = 4.2 + 12.6 * surge + float(np.random.normal(0, 0.2))
            target_temp_c = 485.0 + 510.0 * surge
            detachment = False
            seeding_rate = max(0.1, 1.45 - 1.35 * surge)
            sol_density = 1.2
            div_overload = heat_flux_mw > 10.0

            q_sci = 9.8
            heating_mw = 25.0
            fusion_mw = q_sci * heating_mw
            tbr = 1.14

        elif mode == OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH:
            # Quench thermal runaway in coil 3
            dt_dt = 6.5 + 4.5 * elapsed + float(np.random.normal(0, 0.2))
            temp_k = min(110.0, self.baseline_temp_k + (6.0 * elapsed) + (2.2 * (elapsed ** 2)))
            acoustic_freq = float(29800.0 + np.random.normal(0, 600)) # > 25 kHz stress burst
            acoustic_amp_db = float(48.0 + 8.0 * elapsed)
            dc_dt = float(18.5 + 4.0 * elapsed)
            cap_pf = self.baseline_cap_pf + (dc_dt * elapsed)
            nzpv_mps = float(min(0.085, 0.03 + 0.01 * elapsed))
            quench_detected = True
            quench_warning = True
            severity = QuenchSeverity.SEVERITY_CRITICAL_RUNAWAY
            coil_stress = min(320.0, 145.0 + 25.0 * elapsed)
            current_ratio = min(1.45, 0.58 + 0.18 * elapsed)

            # Plasma degrades as magnetic field collapses
            decay = min(1.0, elapsed / 5.0)
            te_kev = max(0.2, 14.8 - 14.5 * decay)
            ti_kev = max(0.2, 14.2 - 14.0 * decay)
            density_1e20 = max(0.05, 1.85 - 1.8 * decay)
            tau_e_s = max(0.01, 1.65 - 1.64 * decay)
            beta_pct = 0.1
            qi_loss = 0.12
            mhd_quiescent = False

            heat_flux_mw = max(0.2, 4.2 - 0.8 * elapsed)
            target_temp_c = max(100.0, 485.0 - 50.0 * elapsed)
            detachment = True
            seeding_rate = 0.0
            sol_density = 0.1
            div_overload = False

            q_sci = 0.0
            heating_mw = 5.0
            fusion_mw = 0.0
            tbr = 0.0

        elif mode == OperationalMode.MODE_PELLET_REFUELING_BURST:
            # Cryogenic frozen pellet injection wave
            wave = np.sin(min(np.pi, elapsed * 0.75))
            temp_k = self.baseline_temp_k + float(np.random.normal(0, 0.05))
            dt_dt = float(np.random.normal(0, 0.01))
            acoustic_freq = float(np.random.uniform(800, 3200))
            acoustic_amp_db = float(np.random.normal(14.0, 1.0))
            cap_pf = self.baseline_cap_pf
            dc_dt = 0.01
            nzpv_mps = 0.0
            quench_detected = False
            quench_warning = False
            severity = QuenchSeverity.SEVERITY_NOMINAL
            coil_stress = 152.0
            current_ratio = 0.60

            # Density surges to 3.2e20 m^-3
            density_1e20 = 1.85 + 1.35 * wave
            te_kev = max(10.5, 14.8 - 2.8 * wave)
            ti_kev = max(11.0, 14.2 - 2.2 * wave)
            tau_e_s = 1.92
            beta_pct = 5.65
            qi_loss = 0.0010
            mhd_quiescent = True

            heat_flux_mw = 5.8 + float(np.random.normal(0, 0.2))
            target_temp_c = 535.0
            detachment = True
            seeding_rate = 2.1
            sol_density = 3.6
            div_overload = False

            q_sci = 10.2 + 6.3 * wave # Q_sci surges to 16.5!
            heating_mw = 25.0
            fusion_mw = q_sci * heating_mw
            tbr = 1.18

        elif mode == OperationalMode.MODE_IMPURITY_ACCUMULATION:
            # Core tungsten impurity radiation collapse
            collapse = min(1.0, elapsed / 8.0)
            temp_k = self.baseline_temp_k + float(np.random.normal(0, 0.05))
            dt_dt = float(np.random.normal(0, 0.01))
            acoustic_freq = float(np.random.uniform(300, 2000))
            acoustic_amp_db = float(np.random.normal(12.0, 1.0))
            cap_pf = self.baseline_cap_pf
            dc_dt = 0.0
            nzpv_mps = 0.0
            quench_detected = False
            quench_warning = False
            severity = QuenchSeverity.SEVERITY_NOMINAL
            coil_stress = 144.0
            current_ratio = 0.58

            te_kev = max(3.5, 14.8 - 11.3 * collapse)
            ti_kev = max(3.8, 14.2 - 10.4 * collapse)
            density_1e20 = max(0.9, 1.85 - 0.95 * collapse)
            tau_e_s = max(0.4, 1.65 - 1.25 * collapse)
            beta_pct = max(1.1, 4.25 - 3.15 * collapse)
            qi_loss = 0.015
            mhd_quiescent = False

            heat_flux_mw = max(1.5, 4.2 - 2.5 * collapse)
            target_temp_c = max(250.0, 485.0 - 220.0 * collapse)
            detachment = True
            seeding_rate = 0.5
            sol_density = 1.4
            div_overload = False

            q_sci = max(0.8, 10.2 - 8.4 * collapse)
            heating_mw = 25.0
            fusion_mw = q_sci * heating_mw
            tbr = max(0.2, 1.15 - 0.95 * collapse)

        elif mode == OperationalMode.MODE_STARTUP_RAMP:
            # Startup sequence
            ramp = min(1.0, elapsed / 10.0)
            temp_k = 18.5 + 1.5 * ramp
            dt_dt = 0.15
            acoustic_freq = float(np.random.uniform(500, 1800))
            acoustic_amp_db = 15.0
            cap_pf = self.baseline_cap_pf
            dc_dt = 0.01
            nzpv_mps = 0.0
            quench_detected = False
            quench_warning = False
            severity = QuenchSeverity.SEVERITY_NOMINAL
            coil_stress = 20.0 + 125.0 * ramp
            current_ratio = 0.10 + 0.48 * ramp

            te_kev = 1.0 + 13.8 * ramp
            ti_kev = 0.8 + 13.4 * ramp
            density_1e20 = 0.2 + 1.65 * ramp
            tau_e_s = 0.3 + 1.35 * ramp
            beta_pct = 0.5 + 3.75 * ramp
            qi_loss = 0.0018
            mhd_quiescent = True

            heat_flux_mw = 0.5 + 3.7 * ramp
            target_temp_c = 150.0 + 335.0 * ramp
            detachment = True
            seeding_rate = 0.2 + 1.25 * ramp
            sol_density = 0.5 + 1.9 * ramp
            div_overload = False

            heating_mw = 5.0 + 20.0 * ramp
            q_sci = 0.2 + 10.0 * ramp
            fusion_mw = q_sci * heating_mw
            tbr = 0.1 + 1.05 * ramp

        # Lawson criterion calculation
        lawson = density_1e20 * ti_kev * tau_e_s

        # Plant power balance calculations (Sam Wurzel framework)
        total_exit_mw = fusion_mw + heating_mw
        eta_th = 0.38
        gross_elec_mw = total_exit_mw * eta_th
        eta_heat = 0.60
        recirc_heat_mw = heating_mw / eta_heat
        parasitic_cryo_mw = 8.5 if not quench_warning else 14.5
        total_recirc_mw = recirc_heat_mw + parasitic_cryo_mw
        net_elec_mw = gross_elec_mw - total_recirc_mw
        q_eng = gross_elec_mw / total_recirc_mw if total_recirc_mw > 0 else 0.0
        net_electricity = net_elec_mw > 0.0

        # Construct Envelope
        envelope = Envelope(
            timestamp_ns=now_ns,
            source_id=self.sensor_id,
            purdue_level=PurdueLevel.LEVEL_0_PROCESS,
            security_token="TLS13-TOKEN-SECURE-L0-SENSOR-789",
            sequence_number=self.seq_num,
            payload_type=PayloadType.PAYLOAD_QUENCH_DIAGNOSTIC
        )

        quench_packet = QuenchDiagnostic(
            envelope=envelope,
            sensor_id=self.sensor_id,
            localized_temperature_k=temp_k,
            thermal_rise_rate_k_per_s=dt_dt,
            foas_acoustic_frequency_hz=acoustic_freq,
            foas_acoustic_amplitude_db=acoustic_amp_db,
            stray_capacitance_pf=cap_pf,
            capacitance_shift_rate_pf_per_s=dc_dt,
            normal_zone_propagation_velocity_mps=nzpv_mps,
            quench_detected=quench_detected,
            severity=severity,
            plasma_current_ma=0.0,
            plasma_density_m3=density_1e20
        )

        # Multi-Subsystem Telemetry
        quench_margin_k = max(0.0, 92.0 - temp_k)
        coil_msg = CoilCryoTelemetry(
            coil_temperature_k=temp_k,
            helium_pressure_bar=5.2 if not quench_detected else min(18.0, 5.2 + 2.0 * elapsed),
            peak_coil_stress_mpa=coil_stress,
            critical_current_ratio=current_ratio,
            quench_margin_k=quench_margin_k,
            nzpv_mps=nzpv_mps,
            quench_warning=quench_warning,
            coil_id="HTS-MODULAR-COIL-03"
        )

        plasma_msg = PlasmaCoreTelemetry(
            electron_temp_kev=te_kev,
            ion_temp_kev=ti_kev,
            electron_density_1e20_m3=density_1e20,
            energy_confinement_tau_s=tau_e_s,
            lawson_triple_product_kev_s_m3=lawson,
            toroidal_beta_percent=beta_pct,
            qi_neoclassical_loss_fraction=qi_loss,
            mhd_quiescent=mhd_quiescent
        )

        divertor_msg = DivertorTelemetry(
            peak_heat_flux_mw_per_m2=heat_flux_mw,
            target_surface_temp_c=target_temp_c,
            detachment_achieved=detachment,
            impurity_seeding_rate_pa_m3_s=seeding_rate,
            sol_plasma_density_1e19_m3=sol_density,
            thermal_overload_alert=div_overload
        )

        blanket_msg = BlanketTelemetry(
            pb_li_inlet_temp_c=350.0,
            pb_li_outlet_temp_c=350.0 + 145.0 * (fusion_mw / 255.0) if fusion_mw > 0 else 310.0,
            neutron_wall_load_mw_per_m2=1.85 * (fusion_mw / 255.0) if fusion_mw > 0 else 0.0,
            tritium_breeding_ratio=tbr,
            tritium_extraction_rate_g_per_day=142.0 * (fusion_mw / 255.0) if fusion_mw > 0 else 0.0,
            coolant_flow_rate_kg_s=280.0
        )

        # 3D Coordinates
        phi_coords = np.linspace(0, 2*np.pi, 32).tolist()
        r_coords = (1.5 + 0.3 * np.cos(np.linspace(0, 2*np.pi, 32))).tolist()
        z_coords = (0.3 * np.sin(np.linspace(0, 2*np.pi, 32))).tolist()
        thermal_loads = [temp_k] * 32

        power_twin = DigitalTwinState(
            envelope=envelope,
            simulation_step=self.seq_num,
            magnetic_flux_surface_r=r_coords,
            magnetic_flux_surface_z=z_coords,
            magnetic_flux_surface_phi=phi_coords,
            localized_thermal_loads_k=thermal_loads,
            peak_coil_strain_mpa=coil_stress,
            plasma_beta_toroidal=beta_pct,
            magnetic_axis_displacement_m=0.001,
            equilibrium_converged=mhd_quiescent,
            pinn_loss=0.0012,
            scientific_gain_q_sci=q_sci,
            engineering_gain_q_eng=q_eng,
            fusion_power_mw=fusion_mw,
            heating_power_mw=heating_mw,
            gross_electric_power_mw=gross_elec_mw,
            net_electric_power_mw=net_elec_mw,
            recirculating_power_mw=recirc_heat_mw,
            parasitic_cryo_power_mw=parasitic_cryo_mw,
            lawson_triple_product_kev_s_m3=lawson,
            net_electricity_achieved=net_electricity
        )

        mode_desc_map = {
            OperationalMode.MODE_STEADY_STATE_NOMINAL: "Normal Steady-State Burn: QI high-confinement flattop",
            OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT: "Divertor Detachment Anomaly: Peak heat flux > 10 MW/m^2",
            OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH: "REBCO Coil Hotspot: Quench runaway in Module 3",
            OperationalMode.MODE_PELLET_REFUELING_BURST: "Cryogenic D-T Pellet Injection: High density alpha burst",
            OperationalMode.MODE_IMPURITY_ACCUMULATION: "Tungsten Impurity Core Influx: Radiative cooling collapse",
            OperationalMode.MODE_STARTUP_RAMP: "Startup Ignition Sequence: Coil ramp-up & ECRH breakdown"
        }

        subsystem_report = SubsystemTelemetryReport(
            envelope=envelope,
            active_mode=self.active_mode,
            mode_description=mode_desc_map.get(self.active_mode, "Operational Mode"),
            coil_cryo=coil_msg,
            plasma_core=plasma_msg,
            divertor=divertor_msg,
            blanket=blanket_msg,
            power_balance=power_twin
        )

        return quench_packet, subsystem_report

    def publish_loop(self, frequency_hz=20.0, mode_cycle_interval=12.0, quench_after_sec=None):
        print(f"[SYNTHETIC-GEN] Starting high-fidelity telemetry stream at {frequency_hz} Hz...")
        period = 1.0 / frequency_hz
        start_time = time.time()

        self.connect_tcp()

        cycle_modes = [
            (OperationalMode.MODE_STARTUP_RAMP, "Startup Ignition Ramp"),
            (OperationalMode.MODE_STEADY_STATE_NOMINAL, "Normal Steady-State Burn"),
            (OperationalMode.MODE_PELLET_REFUELING_BURST, "Cryogenic Pellet Refueling Burst"),
            (OperationalMode.MODE_STEADY_STATE_NOMINAL, "Normal Steady-State Burn"),
            (OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT, "Divertor Detachment Fault"),
            (OperationalMode.MODE_STEADY_STATE_NOMINAL, "Normal Steady-State Burn"),
            (OperationalMode.MODE_IMPURITY_ACCUMULATION, "Tungsten Core Impurity Influx"),
            (OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH, "REBCO Coil Hotspot Quench")
        ]
        cycle_idx = 0
        last_cycle_switch = time.time()

        try:
            while True:
                loop_start = time.time()

                # Automated quench trigger if requested
                if quench_after_sec and (time.time() - start_time > quench_after_sec) and self.active_mode != OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH:
                    self.set_mode(OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH)

                # Automated multi-mode cycling if enabled
                if self.cycle_mode_active and (time.time() - last_cycle_switch > mode_cycle_interval):
                    cycle_idx = (cycle_idx + 1) % len(cycle_modes)
                    new_mode, desc = cycle_modes[cycle_idx]
                    self.set_mode(new_mode)
                    last_cycle_switch = time.time()

                quench_pkt, report_pkt = self.generate_packets()

                quench_bytes = quench_pkt.SerializeToString()
                report_bytes = report_pkt.SerializeToString()

                # 1. TCP stream to Level 3 Middleware Hub (Port 9001)
                if self.tcp_sock:
                    try:
                        hdr = struct.pack(">I", len(quench_bytes))
                        self.tcp_sock.sendall(hdr + quench_bytes)
                    except Exception:
                        self.tcp_sock = None

                # 2. UDP to Level 1 Edge Node (Port 9003) - QuenchDiagnostic
                self.udp_sock.sendto(quench_bytes, (self.hub_host, self.udp_edge_port))

                # 3. UDP to Level 4 Digital Twin (Port 9004) - QuenchDiagnostic
                self.udp_sock.sendto(quench_bytes, (self.hub_host, self.udp_twin_port))

                # 4. UDP to Level 4/5 Data Lake API (Port 9005) - Both QuenchDiagnostic & SubsystemTelemetryReport
                self.udp_sock.sendto(quench_bytes, (self.hub_host, self.udp_api_port))
                self.udp_sock.sendto(report_bytes, (self.hub_host, self.udp_api_port))

                if self.seq_num % int(frequency_hz) == 0 or quench_pkt.quench_detected:
                    pb = report_pkt.power_balance
                    print(
                        f"[{OperationalMode.Name(self.active_mode)[:15]}] Frame #{self.seq_num:05d} | "
                        f"Temp: {report_pkt.coil_cryo.coil_temperature_k:5.1f}K | "
                        f"FOAS: {quench_pkt.foas_acoustic_frequency_hz:6.0f}Hz | "
                        f"Div Heat: {report_pkt.divertor.peak_heat_flux_mw_per_m2:4.1f}MW/m² | "
                        f"Q_sci: {pb.scientific_gain_q_sci:4.1f} | "
                        f"P_net: {pb.net_electric_power_mw:+5.1f}MW | "
                        f"TBR: {report_pkt.blanket.tritium_breeding_ratio:4.2f}"
                    )

                duration = time.time() - loop_start
                sleep_time = max(0.0, period - duration)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n[SYNTHETIC-GEN] Synthetic generator gracefully terminated.")
        finally:
            if self.tcp_sock:
                self.tcp_sock.close()
            self.udp_sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SKHY Stellarator High-Fidelity Synthetic Telemetry Generator")
    parser.add_argument("--freq", type=float, default=20.0, help="Publishing frequency in Hz")
    parser.add_argument("--quench-after", type=float, default=None, help="Seconds before auto-triggering quench event")
    parser.add_argument("--mode", type=str, default="steady_state",
                        choices=["steady_state", "divertor_fault", "quench", "pellet_burst", "impurity", "startup", "cycle"],
                        help="Initial operational mode or automated cycle")
    parser.add_argument("--cycle-interval", type=float, default=10.0, help="Seconds per mode when in cycle mode")
    parser.add_argument("--sensor-id", type=str, default="FOAS-HTS-COIL-03A", help="Primary sensor ID")
    args = parser.parse_args()

    mode_map = {
        "steady_state": OperationalMode.MODE_STEADY_STATE_NOMINAL,
        "divertor_fault": OperationalMode.MODE_DIVERTOR_DETACHMENT_FAULT,
        "quench": OperationalMode.MODE_HTS_COIL_HOTSPOT_QUENCH,
        "pellet_burst": OperationalMode.MODE_PELLET_REFUELING_BURST,
        "impurity": OperationalMode.MODE_IMPURITY_ACCUMULATION,
        "startup": OperationalMode.MODE_STARTUP_RAMP
    }

    gen = StellaratorSyntheticGenerator(sensor_id=args.sensor_id)

    if args.mode == "cycle":
        gen.cycle_mode_active = True
        gen.set_mode(OperationalMode.MODE_STARTUP_RAMP)
    else:
        gen.set_mode(mode_map[args.mode])

    gen.publish_loop(frequency_hz=args.freq, mode_cycle_interval=args.cycle_interval, quench_after_sec=args.quench_after)
