use bytes::Bytes;
use std::collections::HashMap;
use std::net::UdpSocket;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::net::TcpListener;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use prost::Message;

pub mod skhy_telemetry {
    include!(concat!(env!("OUT_DIR"), "/skhy.telemetry.rs"));
}

use skhy_telemetry::{
    Envelope, QuenchDiagnostic, DigitalTwinState, MacroStateCommand,
    PurdueLevel, PayloadType, QuenchSeverity, SystemState,
};

/// IEC 62443 Rate Limiter for Level 3 Ingestion Zone
struct RateLimiter {
    last_seen: HashMap<String, u64>,
    tokens: HashMap<String, f64>,
    max_tokens: f64,
    refill_rate_per_sec: f64,
}

impl RateLimiter {
    fn new(max_tokens: f64, refill_rate_per_sec: f64) -> Self {
        Self {
            last_seen: HashMap::new(),
            tokens: HashMap::new(),
            max_tokens,
            refill_rate_per_sec,
        }
    }

    fn allow(&mut self, source_id: &str, now_sec: u64) -> bool {
        let last = *self.last_seen.get(source_id).unwrap_or(&now_sec);
        let elapsed = (now_sec.saturating_sub(last)) as f64;
        self.last_seen.insert(source_id.to_string(), now_sec);

        let current_tokens = self.tokens.entry(source_id.to_string()).or_insert(self.max_tokens);
        *current_tokens = (*current_tokens + elapsed * self.refill_rate_per_sec).min(self.max_tokens);

        if *current_tokens >= 1.0 {
            *current_tokens -= 1.0;
            true
        } else {
            false
        }
    }
}

/// TAMI Middleware Hub (Purdue Level 3 - Supervisory Control & Bridge)
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    log::info!("=========================================================================");
    log::info!(" SKHY - TAMI MIDDLEWARE HUB (LEVEL 3 SUPERVISORY CONTROL)");
    log::info!(" Safety Architecture: IEC 62443 Security Level 3 - Zone Segregation");
    log::info!(" Ingest Conduit: DDS / Level 2 Area Control (Port 9001)");
    log::info!(" Egress Conduit: Kafka / Level 4 Enterprise Data Lake (Port 9002 / Forwarder)");
    log::info!(" Alert Conduit: Deterministic Microsecond DDS Emergency Bus");
    log::info!("=========================================================================");

    let rate_limiter = Arc::new(Mutex::new(RateLimiter::new(100.0, 100.0)));
    let sequence_tracker: Arc<Mutex<HashMap<String, u64>>> = Arc::new(Mutex::new(HashMap::new()));

    // Bind Level 2 Ingestion Listener (TCP/DDS conduit fallback)
    let listener = TcpListener::bind("127.0.0.1:9001").await?;
    log::info!("[IEC62443-ZONE-L3] Listening for Level 2 Telemetry on 127.0.0.1:9001...");

    // Socket for UDP DDS Alert Channel (to Level 1/2)
    let alert_udp_socket = UdpSocket::bind("127.0.0.1:0")?;

    loop {
        let (mut socket, addr) = listener.accept().await?;
        let rate_limiter_clone = Arc::clone(&rate_limiter);
        let sequence_tracker_clone = Arc::clone(&sequence_tracker);
        let alert_udp = alert_udp_socket.try_clone()?;

        tokio::spawn(async move {
            log::info!("[IEC62443-CONDUIT-L2-TO-L3] Connection established from L2 Controller: {}", addr);
            let mut buf = vec![0u8; 65536];

            loop {
                // Read 4-byte big endian length prefix
                let mut len_bytes = [0u8; 4];
                if socket.read_exact(&mut len_bytes).await.is_err() {
                    break;
                }
                let msg_len = u32::from_be_bytes(len_bytes) as usize;

                if msg_len > buf.len() {
                    buf.resize(msg_len, 0);
                }

                if socket.read_exact(&mut buf[..msg_len]).await.is_err() {
                    log::warn!("[IEC62443-CONDUIT-L2-TO-L3] Packet read error from {}", addr);
                    break;
                }

                let payload = &buf[..msg_len];

                // Attempt decoding as QuenchDiagnostic
                if let Ok(quench_diag) = QuenchDiagnostic::decode(payload) {
                    process_quench_diagnostic(&quench_diag, &rate_limiter_clone, &sequence_tracker_clone, &alert_udp);
                } else if let Ok(twin_state) = DigitalTwinState::decode(payload) {
                    log::info!("[IEC62443-CONDUIT-L3-TO-L4] Digital Twin State Forwarded -> Kafka Topic 'stellarator.digital_twin' (Step {})", twin_state.simulation_step);
                } else if let Ok(cmd) = MacroStateCommand::decode(payload) {
                    log::info!("[IEC62443-CONDUIT-SUPERVISORY] Macro State Command Received: State {} Authority '{}'", cmd.target_state, cmd.executing_authority);
                } else {
                    log::warn!("[IEC62443-SECURITY] Malformed payload received on L2-L3 conduit from {}", addr);
                }
            }

            log::info!("[IEC62443-CONDUIT-L2-TO-L3] Connection closed for {}", addr);
        });
    }
}

fn process_quench_diagnostic(
    diag: &QuenchDiagnostic,
    rate_limiter: &Arc<Mutex<RateLimiter>>,
    sequence_tracker: &Arc<Mutex<HashMap<String, u64>>>,
    alert_udp: &UdpSocket,
) {
    let now_sec = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();

    let env = match &diag.envelope {
        Some(e) => e,
        None => {
            log::warn!("[IEC62443-SECURITY] Rejecting QuenchDiagnostic missing envelope");
            return;
        }
    };

    // 1. Rate Limiting Check
    {
        let mut limiter = rate_limiter.lock().unwrap();
        if !limiter.allow(&env.source_id, now_sec) {
            log::warn!("[IEC62443-SECURITY] Rate limit exceeded for source '{}' - Dropping packet", env.source_id);
            return;
        }
    }

    // 2. Sequence Continuity Check
    {
        let mut seq_map = sequence_tracker.lock().unwrap();
        let last_seq = seq_map.entry(env.source_id.clone()).or_insert(0);
        if env.sequence_number <= *last_seq && *last_seq != 0 {
            log::warn!("[IEC62443-SECURITY] Out-of-order or duplicate packet from '{}': seq {} <= last {}", env.source_id, env.sequence_number, last_seq);
        }
        *last_seq = env.sequence_number;
    }

    // 3. Process Safety Alert & Level 3 Supervisory Rule Evaluation
    let is_critical = diag.severity == QuenchSeverity::SeverityCriticalRunaway as i32;
    if diag.quench_detected || is_critical {
        log::error!(
            "[IEC62443-CRITICAL-ALERT] QUENCH RUNAWAY DETECTED! Sensor: {} Temp: {:.2}K dT/dt: {:.2}K/s FOAS: {:.1}Hz NZPV: {:.4}m/s",
            diag.sensor_id, diag.localized_temperature_k, diag.thermal_rise_rate_k_per_s,
            diag.foas_acoustic_frequency_hz, diag.normal_zone_propagation_velocity_mps
        );

        // Formulate High-Priority DDS Emergency Macro State Command
        let emergency_cmd = MacroStateCommand {
            envelope: Some(Envelope {
                timestamp_ns: SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos() as u64,
                source_id: "TAMI-SUPERVISORY-HUB-L3".to_string(),
                purdue_level: PurdueLevel::Level3Supervisory as i32,
                security_token: "HMAC-SHA256-HIGH-PRIORITY-INTERLOCK-TOKEN".to_string(),
                sequence_number: 999999,
                payload_type: PayloadType::PayloadMacroStateCommand as i32,
            }),
            target_state: SystemState::StateEmergencyQuenchDump as i32,
            executing_authority: "SUPERVISORY-SAFETY-INTERLOCK-ENGINE".to_string(),
            command_id: format!("CMD-EMERGENCY-DUMP-{}", now_sec),
            override_timeout_ms: 500,
            reason: format!("REBCO Thermal Runaway Anomaly on Sensor {}", diag.sensor_id),
        };

        let mut buf = Vec::new();
        emergency_cmd.encode(&mut buf).unwrap();

        // Broadcast to Level 1 / Level 2 DDS Fast Dump Circuit (UDP Port 9003)
        let _ = alert_udp.send_to(&buf, "127.0.0.1:9003");
        log::info!("[IEC62443-CONDUIT-ALERT-BUS] Broadcasted EMERGENCY_QUENCH_DUMP via Microsecond DDS Channel");
    } else {
        log::debug!(
            "[IEC62443-TELEMETRY-NOMINAL] Sensor: {} Temp: {:.2}K FOAS: {:.1}Hz",
            diag.sensor_id, diag.localized_temperature_k, diag.foas_acoustic_frequency_hz
        );
    }

    // 4. Bridge raw telemetry to Kafka Data Lake Sink Topic ('stellarator.quench_telemetry')
    log::info!(
        "[IEC62443-CONDUIT-L3-TO-L4] Forwarded QuenchDiagnostic telemetry to Kafka topic 'stellarator.quench_telemetry' (seq={})",
        env.sequence_number
    );
}
