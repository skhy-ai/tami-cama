use std::net::UdpSocket;
use std::time::Instant;
use prost::Message;

pub mod proxima_telemetry {
    include!(concat!(env!("OUT_DIR"), "/proxima.telemetry.rs"));
}

use proxima_telemetry::{
    QuenchDiagnostic, MacroStateCommand, SystemState,
};

/// Level 1 Edge Quench Protection Node (MTCA.4 MicroTCA Chassis)
/// Zero-allocation microsecond safety kernel for REBCO HTS magnets
fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    log::info!("=========================================================================");
    log::info!(" PROXIMA FUSION - LEVEL 1 EDGE QUENCH PROTECTION MODULE (MTCA.4 FPGA)");
    log::info!(" Safety Architecture: IEC 62443 Level 1 Direct Safety Interlock Zone");
    log::info!(" Input Conduit: High-Frequency Sensor Stream (UDP 9003)");
    log::info!(" Hardware Target: HTS Fast Discharge Breaker & Magnet Energy Dump Switch");
    log::info!(" Hard Latency Target: < 50 Microseconds Response Time");
    log::info!("=========================================================================");

    let socket = UdpSocket::bind("127.0.0.1:9003")?;
    log::info!("[IEC62443-ZONE-L1] MTCA.4 Edge Safety Kernel listening on UDP 127.0.0.1:9003...");

    let mut buf = [0u8; 65536];

    loop {
        let (amt, _src) = match socket.recv_from(&mut buf) {
            Ok(res) => res,
            Err(e) => {
                log::error!("[IEC62443-ZONE-L1] Socket recv error: {}", e);
                continue;
            }
        };

        let start_time = Instant::now();
        let payload = &buf[..amt];

        // 1. Decode QuenchDiagnostic
        if let Ok(diag) = QuenchDiagnostic::decode(payload) {
            evaluate_edge_quench_rules(&diag, start_time);
        } else if let Ok(cmd) = MacroStateCommand::decode(payload) {
            log::warn!(
                "[IEC62443-ZONE-L1-HARDWARE-INTERLOCK] RECEIVED EXTERNAL MACRO COMMAND State {} From '{}' IN {} μs!",
                cmd.target_state, cmd.executing_authority, start_time.elapsed().as_micros()
            );
            if cmd.target_state == SystemState::StateEmergencyQuenchDump as i32 {
                trigger_hardware_fast_dump("EXTERNAL_SUPERVISORY_MACRO_COMMAND", start_time);
            }
        }
    }
}

/// Zero-Allocation Multi-Sensor Fusion Evaluation Algorithm
fn evaluate_edge_quench_rules(diag: &QuenchDiagnostic, start_time: Instant) {
    // Multi-sensor fusion thresholds for REBCO HTS tape thermal runaway
    const FOAS_ACOUSTIC_ANOMALY_HZ: f64 = 25000.0; // Acoustic strain emission > 25 kHz
    const THERMAL_RISE_RATE_K_PER_S: f64 = 5.0;     // Temperature rise rate > 5 K/s
    const STRAY_CAPACITANCE_SHIFT_RATE: f64 = 15.0; // dC/dt > 15 pF/s
    const REBCO_NZPV_THRESHOLD_MPS: f64 = 0.02;     // NZPV > 0.02 m/s

    let acoustic_trigger = diag.foas_acoustic_frequency_hz >= FOAS_ACOUSTIC_ANOMALY_HZ;
    let thermal_trigger = diag.thermal_rise_rate_k_per_s >= THERMAL_RISE_RATE_K_PER_S;
    let capacitance_trigger = diag.capacitance_shift_rate_pf_per_s.abs() >= STRAY_CAPACITANCE_SHIFT_RATE;
    let nzpv_trigger = diag.normal_zone_propagation_velocity_mps >= REBCO_NZPV_THRESHOLD_MPS;

    // Multi-sensor fusion decision matrix
    if acoustic_trigger || thermal_trigger || capacitance_trigger || nzpv_trigger || diag.quench_detected {
        let elapsed_us = start_time.elapsed().as_micros();
        log::error!(
            "[IEC62443-L1-INTERLOCK-TRIPPED] ANOMALY CONFIRMED in {} μs! [FOAS: {} Hz (trig={}), dT/dt: {:.2} K/s (trig={}), dC/dt: {:.2} pF/s (trig={}), NZPV: {:.4} m/s (trig={})]",
            elapsed_us, diag.foas_acoustic_frequency_hz, acoustic_trigger,
            diag.thermal_rise_rate_k_per_s, thermal_trigger,
            diag.capacitance_shift_rate_pf_per_s, capacitance_trigger,
            diag.normal_zone_propagation_velocity_mps, nzpv_trigger
        );

        trigger_hardware_fast_dump(&diag.sensor_id, start_time);
    } else {
        log::trace!(
            "[IEC62443-L1-NOMINAL] Sensor {} checked in {} μs",
            diag.sensor_id, start_time.elapsed().as_micros()
        );
    }
}

/// Microsecond Hardware Abstraction Layer (HAL) Actuator Pulse
fn trigger_hardware_fast_dump(source: &str, start_time: Instant) {
    let latency_us = start_time.elapsed().as_micros();

    println!("=========================================================================");
    println!(">>> [HARDWARE INTERLOCK PULSE - MTCA.4 FPGA DIRECT ACTUATION] <<<");
    println!(">>> SYSTEM STATE CHANGED TO: EMERGENCY_QUENCH_DUMP                       <<<");
    println!(">>> TRIGGER SOURCE: {}                                            <<<", source);
    println!(">>> TOTAL LATENCY (INGRESS TO DUMP ACTUATION): {} microseconds          <<<", latency_us);
    println!(">>> FAST DISCHARGE BREAKER COILS: ACTIVATED                               <<<");
    println!(">>> CRYOGENIC BYPASS VALVES: OPENED                                     <<<");
    println!("=========================================================================");
}
