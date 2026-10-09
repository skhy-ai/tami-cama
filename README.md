# Proxima Fusion - TAMI (Telemetry, Analytics, Monitoring, & Integration) Architecture Stack

Foundational software architecture for the enterprise Instrumentation and Control (I&C) stack of a Quasi-Isodynamic High-Temperature-Superconductor (QI-HTS) stellarator, engineered by the Lead Systems Software Architecture & Staff Engineering team at Proxima Fusion.

---

## 🏛 Architecture Overview: The 6-Tier Purdue Model & IEC 62443 Conduits

```
  +-----------------------------------------------------------------------------------+
  | LEVEL 5: ENTERPRISE AGENTIC AI & MULTI-PHYSICS TRAINING                          |
  | - REST & GraphQL API (FastAPI / Strawberry)                                      |
  | - Physics-Informed Neural Network (PINN) Multi-Physics Training Datasets          |
  +-----------------------------------------------------------------------------------+
                                        ▲  ▲
                                        │  │ (Conduit: REST/GraphQL HTTP/2)
                                        ▼  ▼
  +-----------------------------------------------------------------------------------+
  | LEVEL 4: DIGITAL TWIN SURROGATE ENGINE & DATA LAKE PERSISTENCE                   |
  | - PyTorch PINN Surrogate Model (V3FIT 3D Magnetic Equilibrium & Thermal Mesh)     |
  | - HDF5 Time-Series Archival (`tami_data_lake.h5` / IMAS Standard Data Structure)  |
  +-----------------------------------------------------------------------------------+
                                        ▲  ▲
                                        │  │ (Conduit: Apache Kafka / TLS 1.3 Streaming)
                                        ▼  ▼
  +-----------------------------------------------------------------------------------+
  | LEVEL 3: TAMI SUPERVISORY CONTROL MIDDLEWARE HUB (Rust)                           |
  | - High-Throughput Protobuf Ingestion & Rate-Limiting                              |
  | - Envelope Token Validation & Sequence Continuity Check                           |
  | - High-Priority Microsecond Alert Broadcast Bus                                  |
  +-----------------------------------------------------------------------------------+
                                        ▲  ▲
                                        │  │ (Conduit: DDS Real-Time Control Bus)
                                        ▼  ▼
  +-----------------------------------------------------------------------------------+
  | LEVEL 2: AREA CONTROL & PLCs                                                      |
  | - Deterministic Magnet Power Supply Subsystem Controllers                        |
  | - Cryogenic Loop Regulators                                                       |
  +-----------------------------------------------------------------------------------+
                                        ▲  ▲
                                        │  │ (Conduit: Direct Sub-Millisecond Bus)
                                        ▼  ▼
  +-----------------------------------------------------------------------------------+
  | LEVEL 1: EDGE QUENCH PROTECTION MODULE (Rust / MTCA.4 MicroTCA FPGA)             |
  | - Zero-Allocation Microsecond Protection Kernel                                   |
  | - Multi-Sensor Fusion: FOAS (>25 kHz acoustic burst) + dT/dt (>5 K/s) + dC/dt     |
  | - REBCO Normal Zone Propagation Velocity (NZPV ~0.01 - 0.1 m/s) Tracking          |
  | - Immediate Hardware Fast Discharge Breaker Actuation                             |
  +-----------------------------------------------------------------------------------+
                                        ▲  ▲
                                        │  │ (Level 0 Hardware Sensors & Actuators)
  +-----------------------------------------------------------------------------------+
  | LEVEL 0: PHYSICAL STELLARATOR HARDWARE & SENSORS                                  |
  | - Fiber-Optic Acoustic Sensing (FOAS) Strain Cables                              |
  | - Stray Capacitance Co-wound Probes & Cryogenic REBCO Tape Coils                  |
  +-----------------------------------------------------------------------------------+
```

---

## 🔒 Security Architecture (IEC 62443 Compliance)

1. **Zone Segregation**: Level 0/1 (Safety Interlock Zone), Level 2 (Area Control Zone), Level 3 (Supervisory Zone), and Level 4/5 (Enterprise/AI Zone) are isolated into distinct security subnets.
2. **Conduits**:
   - **L0/L1 -> L2/L3**: Microsecond deterministic DDS channels and direct UDP fast dump interlock conduit.
   - **L3 -> L4**: Apache Kafka secure streaming conduit with TLS 1.3 encryption.
   - **L4 -> L5**: Read-only REST and GraphQL endpoints for AI training and agent query without back-propagation permissions into control loops.
3. **Zero-Trust Envelope**: Every message carries a `proxima.telemetry.Envelope` header with nano-second timestamps, source node verification, sequence counters, and security tokens.

---

## 📁 Repository Structure

```
c:\Projects\tami-cama\
├── proto/
│   └── proxima_telemetry.proto          # Protobuf schema (Envelope, QuenchDiagnostic, DigitalTwinState, MacroStateCommand)
├── middleware_hub/                       # Purdue Level 3 Middleware Hub (Rust)
│   ├── Cargo.toml
│   ├── build.rs                          # Auto-compiles Protobuf with prost-build & vendored protoc
│   └── src/main.rs                       # Ingestion, rate-limiting, sequence check, and DDS/Kafka bridge
├── edge_quench/                          # Purdue Level 1 Edge Protection Kernel (Rust)
│   ├── Cargo.toml
│   ├── build.rs
│   └── src/main.rs                       # Sub-millisecond multi-sensor fusion (FOAS, dT/dt, NZPV) & microsecond fast dump
├── python_common/                        # Generated Python Protobuf package
│   ├── __init__.py
│   └── proxima_telemetry_pb2.py
├── synthetic_generator/                  # Purdue Level 0/1 Synthetic Sensor Generator (Python)
│   └── synthetic_data_gen.py             # 100 Hz simulation with triggerable REBCO quench runaway
├── digital_twin/                         # Purdue Level 4/5 Surrogate Engine (Python / PyTorch)
│   └── digital_twin_engine.py            # PINN surrogate reconstructing 3D flux mesh & MHD parameters
├── data_lake_api/                        # Purdue Level 4/5 Data Lake API & GraphQL (Python / FastAPI)
│   └── ai_ingestion_api.py               # HDF5 persistence (`tami_data_lake.h5`), REST & Strawberry GraphQL endpoints
├── run_demo.py                           # Master end-to-end demonstrator and orchestrator script
└── README.md
```

---

## ⚡ Quick Start & End-to-End Demonstration

To run the complete multi-tier system demonstration (all 6 Purdue levels simultaneously):

```bash
python run_demo.py
```

### Running Components Individually

1. **Level 1 Edge Protection Module (Rust)**:
   ```bash
   cd edge_quench
   cargo run --release
   ```

2. **Level 3 Supervisory Middleware Hub (Rust)**:
   ```bash
   cd middleware_hub
   cargo run --release
   ```

3. **Level 4/5 Data Lake API (Python / FastAPI)**:
   ```bash
   python data_lake_api/ai_ingestion_api.py
   ```
   - REST API Docs: `http://127.0.0.1:8000/docs`
   - GraphQL Playground: `http://127.0.0.1:8000/graphql`

4. **Level 4/5 Digital Twin PINN Engine (PyTorch)**:
   ```bash
   python digital_twin/digital_twin_engine.py
   ```

5. **Level 0/1 Synthetic Telemetry Generator (Python)**:
   ```bash
   python synthetic_generator/synthetic_data_gen.py --freq 100.0 --quench-after 3.0
   ```
