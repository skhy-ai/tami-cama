#!/usr/bin/env python3
"""
SKHY - TAMI Level 0/1 Synthetic Telemetry Generator
Simulates high-fidelity Fiber-Optic Acoustic Sensing (FOAS), Stray-Capacitance sensors,
and real-time plasma state parameters for REBCO High-Temperature Superconductor (HTS) Stellarator Coils.
"""

import sys
import os
import time
import socket
import struct
import random
import argparse
import numpy as np

# Add parent directory to path to import python_common
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_common.skhy_telemetry_pb2 import (
    PurdueLevel, PayloadType, QuenchSeverity,
    Envelope, QuenchDiagnostic
)

class SyntheticSensorNode:
    def __init__(self, sensor_id="FOAS-HTS-COIL-03A", hub_host="127.0.0.1", tcp_port=9001, udp_ports=[9003, 9004, 9005]):
        self.sensor_id = sensor_id
        self.hub_host = hub_host
        self.tcp_port = tcp_port
        self.udp_ports = udp_ports

        self.seq_num = 0
        self.baseline_temp_k = 20.0  # Cryogenic operational baseline (Kelvin)
        self.baseline_cap_pf = 120.0 # Stray capacitance baseline (pF)
        self.quench_active = False
        self.quench_start_time = 0.0

        # Create sockets
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.tcp_sock = None

    def connect_tcp(self):
        try:
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.connect((self.hub_host, self.tcp_port))
            print(f"[SYNTHETIC-GEN] Connected to Level 3 Middleware Hub at {self.hub_host}:{self.tcp_port}")
            return True
        except Exception as e:
            print(f"[SYNTHETIC-GEN] TCP connection warning ({e}) - operating in UDP broadcast fallback")
            self.tcp_sock = None
            return False

    def trigger_quench_event(self):
        """Simulates REBCO thermal runaway anomaly with FOAS acoustic strain burst."""
        self.quench_active = True
        self.quench_start_time = time.time()
        print(f"\n[SIMULATION EVENT] REBCO QUENCH EVENT TRIGGERED ON SENSOR '{self.sensor_id}'!\n")

    def generate_packet(self) -> QuenchDiagnostic:
        self.seq_num += 1
        now_ns = int(time.time() * 1e9)

        if not self.quench_active:
            # Steady-state cryogenic normal operating noise
            temp_k = self.baseline_temp_k + np.random.normal(0, 0.05)
            dt_dt = float(np.random.normal(0, 0.01))
            acoustic_freq = float(np.random.uniform(100, 3000)) # Low background acoustic noise (<3kHz)
            acoustic_amp_db = float(np.random.normal(12.0, 1.5))
            cap_pf = self.baseline_cap_pf + np.random.normal(0, 0.02)
            dc_dt = float(np.random.normal(0, 0.005))
            nzpv_mps = 0.0
            quench_detected = False
            severity = QuenchSeverity.SEVERITY_NOMINAL

            # Flattop plasma burn state: zero driven current (stellarator property), steady density
            plasma_current_ma = 0.0 + float(np.random.normal(0, 0.002))
            plasma_density = 1.85 + float(np.random.normal(0, 0.03)) # 1.85e20 m^-3
        else:
            # REBCO Quench Event Dynamics: slow 1-10 cm/s NZPV + high-frequency acoustic emission stress burst
            elapsed_sec = time.time() - self.quench_start_time

            # Thermal runaway curve (dT/dt rapidly accelerating > 5 K/s)
            dt_dt = 6.5 + 4.0 * elapsed_sec + float(np.random.normal(0, 0.2))
            temp_k = self.baseline_temp_k + (5.0 * elapsed_sec) + (2.0 * (elapsed_sec ** 2))

            # FOAS Acoustic Stress Emission Burst (28 kHz to 38 kHz high frequency strain release)
            acoustic_freq = float(29500.0 + np.random.normal(0, 800))
            acoustic_amp_db = float(45.0 + 10.0 * elapsed_sec + np.random.normal(0, 2.0))

            # Stray Capacitance Shift (dC/dt > 15 pF/s due to localized dielectric breakdown)
            dc_dt = float(18.5 + 5.0 * elapsed_sec + np.random.normal(0, 0.5))
            cap_pf = self.baseline_cap_pf + (dc_dt * elapsed_sec)

            # NZPV characteristic of REBCO HTS tape (0.025 to 0.065 m/s)
            nzpv_mps = float(min(0.085, 0.03 + 0.01 * elapsed_sec))

            quench_detected = True
            severity = QuenchSeverity.SEVERITY_CRITICAL_RUNAWAY

            # Plasma confinement collapses due to magnetic field perturbation
            plasma_current_ma = 0.0
            plasma_density = max(0.0, 1.85 - 0.9 * elapsed_sec)

        envelope = Envelope(
            timestamp_ns=now_ns,
            source_id=self.sensor_id,
            purdue_level=PurdueLevel.LEVEL_0_PROCESS,
            security_token="TLS13-TOKEN-SECURE-L0-SENSOR-789",
            sequence_number=self.seq_num,
            payload_type=PayloadType.PAYLOAD_QUENCH_DIAGNOSTIC
        )

        quench_msg = QuenchDiagnostic(
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
            plasma_current_ma=plasma_current_ma,
            plasma_density_m3=plasma_density
        )

        return quench_msg

    def publish_loop(self, frequency_hz=50.0, auto_quench_after_sec=2.5):
        print(f"[SYNTHETIC-GEN] Starting sensor telemetry stream at {frequency_hz} Hz...")
        period = 1.0 / frequency_hz
        start_time = time.time()

        self.connect_tcp()

        try:
            while True:
                loop_start = time.time()
                elapsed = loop_start - start_time

                if auto_quench_after_sec and elapsed > auto_quench_after_sec and not self.quench_active:
                    self.trigger_quench_event()

                msg = self.generate_packet()
                serialized = msg.SerializeToString()

                # 1. Send via TCP to Level 3 Hub (Length-prefixed frame)
                if self.tcp_sock:
                    try:
                        header = struct.pack(">I", len(serialized))
                        self.tcp_sock.sendall(header + serialized)
                    except Exception:
                        self.tcp_sock = None

                # 2. UDP broadcasts to Level 1 Edge Node (9003), Digital Twin (9004), and Data Lake API (9005)
                for port in self.udp_ports:
                    self.udp_sock.sendto(serialized, (self.hub_host, port))

                # Sleep to maintain requested frequency
                duration = time.time() - loop_start
                sleep_time = max(0.0, period - duration)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n[SYNTHETIC-GEN] Generator stopped by user.")
        finally:
            if self.tcp_sock:
                self.tcp_sock.close()
            self.udp_sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Telemetry Generator for REBCO HTS Magnet Sensors")
    parser.add_argument("--freq", type=float, default=50.0, help="Publishing frequency in Hz")
    parser.add_argument("--quench-after", type=float, default=2.5, help="Seconds before auto-triggering quench event")
    parser.add_argument("--sensor-id", type=str, default="FOAS-HTS-COIL-03A", help="Sensor Node ID")
    args = parser.parse_args()

    gen = SyntheticSensorNode(sensor_id=args.sensor_id)
    gen.publish_loop(frequency_hz=args.freq, auto_quench_after_sec=args.quench_after)
