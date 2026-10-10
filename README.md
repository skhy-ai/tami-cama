# SKHY - TAMI (Telemetry, Analytics, Monitoring, & Integration) Architecture Stack

Enterprise Instrumentation and Control (I&C) stack and Multi-Reactor Digital Twin for **Quasi-Isodynamic (QI-HTS) Stellarators**, **Advanced Tokamaks**, and **Inertial Confinement Fusion (ICF)**, engineered by the Lead Systems Software Architecture & Staff Engineering team at SKHY.

---

## 🚀 Key Multi-Reactor Capabilities

1. **Multi-Reactor Digital Twin Studio (Three.js WebGL)**:
   - **Quasi-Isodynamic Stellarator**: 20 modular non-planar HTS coils, 5-period helical plasma flux surface, island divertor strike lines, and REBCO hotspot quench detection.
   - **Advanced Tokamak**: Central Solenoid cylinder, 16 D-shaped Toroidal Field (TF) coils, elongated D-shaped plasma ($\kappa \approx 1.6$), upper/lower poloidal divertors, and major disruption collapse FX.
   - **Inertial Confinement Fusion (ICF)**: Spherical armored reaction chamber, 16 converging pulsed UV laser beam cones, cryogenic DT pellet injection, 5 Hz microimplosion detonations, and Rayleigh-Taylor instability alerts.

2. **2D Interactive Sankey Energy Flow Simulator**:
   - Inspired directly by the [Fusion Energy Base Power Plant Simulator](https://www.fusionenergybase.com/fusion-power-plant-simulator).
   - Dynamic cubic Bézier power flow ribbons with animated particles.
   - **Continuous Steady-State Regime** (Stellarator & Tokamak): $Q_{\text{sci}}$, $P_{\text{heating}}$, $\eta_{\text{thermal}}$, $\eta_{\text{driver}}$, $M$, $P_{\text{aux}}$.
   - **Pulsed Driver Regime** (ICF): Driver energy $E_{\text{laser}}$ (MJ), repetition rate $f_{\text{rep}}$ (Hz), and target gain $G$.
   - Live commercial net electricity calculation ($P_{\text{net}} = P_{\text{gross}} - P_{\text{recirc}}$) and engineering gain ($Q_{\text{eng}}$).

3. **Polymorphic Protocol Buffers Schema (`proto/skhy_telemetry.proto`)**:
   - `ReactorType` enum: `REACTOR_QI_STELLARATOR`, `REACTOR_TOKAMAK`, `REACTOR_ICF`.
   - 18 operational and failure modes covering disruptions, VDEs, ELMs, runaway electrons, NTMs, Rayleigh-Taylor mixing, timing jitter, and optics degradation.
   - Polymorphic `oneof reactor_core { StellaratorCoreTelemetry; TokamakCoreTelemetry; IcfCoreTelemetry; }`.

---

## 🏛 Architecture Overview: The 6-Tier Purdue Model & IEC 62443 Conduits

```
  +-----------------------------------------------------------------------------------+
  | LEVEL 5: ENTERPRISE AGENTIC AI & MULTI-PHYSICS TRAINING                          |
  | - REST & GraphQL API (FastAPI / Strawberry)                                      |
  | - Multi-Reactor Dynamic Queries & PINN Surrogate Datasets                        |
  +-----------------------------------------------------------------------------------+
                                        ▲  ▲
                                        │  │ (Conduit: REST/GraphQL HTTP/2)
                                        ▼  ▼
  +-----------------------------------------------------------------------------------+
  | LEVEL 4: DIGITAL TWIN SURROGATE ENGINE & DATA LAKE PERSISTENCE                   |
  | - PyTorch Multi-Physics Surrogate Models (Stellarator, Tokamak, ICF)             |
  | - Three.js WebGL 3D Interactive Viewport & 2D Sankey Energy Canvas               |
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
  | - Cryogenic Flow Regulators & Laser Bank Timing Systems                           |
  +-----------------------------------------------------------------------------------+
                                        ▲  ▲
                                        │  │ (Conduit: Direct Sub-Millisecond Bus)
                                        ▼  ▼
  +-----------------------------------------------------------------------------------+
  | LEVEL 1: EDGE QUENCH PROTECTION MODULE (Rust / MTCA.4 MicroTCA FPGA)             |
  | - Zero-Allocation Microsecond Protection Kernel                                   |
  | - Multi-Sensor Fusion: FOAS (>25 kHz acoustic burst) + dT/dt (>5 K/s) + dC/dt     |
  | - REBCO Normal Zone Propagation Velocity (NZPV ~0.01 - 0.1 m/s) Tracking          |
  | - Immediate Hardware Fast Discharge Breaker Actuation (<50 μs)                    |
  +-----------------------------------------------------------------------------------+
                                        ▲  ▲
                                        │  │ (Level 0 Hardware Sensors & Actuators)
  +-----------------------------------------------------------------------------------+
  | LEVEL 0: PHYSICAL REACTOR HARDWARE & SENSORS                                      |
  | - Fiber-Optic Acoustic Sensing (FOAS) Strain Cables & REBCO Tape Coils            |
  | - Central Solenoid, TF D-Coils, Divertor Langmuir Probes, UV Laser Amplifiers     |
  +-----------------------------------------------------------------------------------+
```

---

## 🔒 Security Architecture (IEC 62443 Compliance)

1. **Zone Segregation**: Level 0/1 (Safety Interlock Zone), Level 2 (Area Control Zone), Level 3 (Supervisory Zone), and Level 4/5 (Enterprise/AI Zone) are isolated into distinct security subnets.
2. **Conduits**:
   - **L0/L1 -> L2/L3**: Microsecond deterministic DDS channels and direct UDP fast dump interlock conduit.
   - **L3 -> L4**: Apache Kafka secure streaming conduit with TLS 1.3 encryption.
   - **L4 -> L5**: Read-only REST and GraphQL endpoints for AI training and agent query without back-propagation permissions into control loops.
3. **Zero-Trust Envelope**: Every message carries a `skhy.telemetry.Envelope` header with nano-second timestamps, source node verification, sequence counters, and security tokens.

---

## 📁 Repository Structure

```
c:\Projects\tami-cama\
├── proto/
│   ├── skhy_telemetry.proto             # Multi-reactor Protobuf schema (Stellarator, Tokamak, ICF)
│   └── skhy_telemetry_pb2.py            # Compiled Python Protobuf classes
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
│   └── skhy_telemetry_pb2.py
├── synthetic_generator/                  # Purdue Level 0/1 Synthetic Sensor Generator (Python)
│   └── synthetic_data_gen.py             # Multi-reactor simulation with 18 distinct failure modes
├── digital_twin/                         # Purdue Level 4/5 Surrogate Engine (Python / PyTorch)
│   └── digital_twin_engine.py            # PINN surrogate reconstructing 3D flux mesh, Tokamak & ICF physics
├── tutorial_viewer/                     # Interactive Web Tutorial & Multi-Reactor Studio
│   ├── index.html                        # Glassmorphic UI with Three.js 3D Viewport & 2D Sankey Canvas
│   ├── style.css                         # Sleek responsive dark-theme design system
│   └── app.js                            # Three.js 3D procedural models & FEB-inspired Sankey flow engine
├── run_tutorial.py                       # One-click launcher for Tutorial Viewer & Web Studio
├── run_demo.py                           # Master end-to-end demonstrator and orchestrator script
├── TUTORIAL.md                           # Comprehensive comparative physics guide (KaTeX & Mermaid)
└── .gitignore                            # Clean ignores for Rust/Python/HDF5 build artifacts
```

---

## 🎓 Beginner Tutorial & Interactive Web Viewer

If you are new to nuclear fusion or real-time control software:

1. **Step-by-Step Written Guide**: Read [TUTORIAL.md](file:///c:/Projects/tami-cama/TUTORIAL.md) for a comprehensive explanation of fusion energy, stellarators, tokamaks, ICF, REBCO superconductor magnets, quench physics, and the 6 Purdue levels with Mermaid diagrams and $\LaTeX$ equations.
2. **Interactive Visual Tutorial Viewer**: Launch the interactive web dashboard with live quench sliders, 3D Three.js reactor models, and 2D Sankey energy flow diagram:
   ```bash
   python run_tutorial.py
   ```
   Or visit `http://127.0.0.1:8000/tutorial/` while the API service is active.

---

## ⚡ Quick Start & End-to-End Demonstration

To run the complete multi-tier system demonstration (all 6 Purdue levels simultaneously):

```bash
python run_demo.py
```

### Running Components Individually

1. **Interactive Tutorial Viewer & 3D Web Studio**:
   ```bash
   python run_tutorial.py
   ```

2. **Level 1 Edge Protection Module (Rust)**:
   ```bash
   cd edge_quench
   cargo run
   ```

3. **Level 3 Supervisory Middleware Hub (Rust)**:
   ```bash
   cd middleware_hub
   cargo run
   ```

4. **Level 4/5 Data Lake API & Tutorial Server (Python / FastAPI)**:
   ```bash
   python data_lake_api/ai_ingestion_api.py
   ```
   - Interactive Tutorial: `http://127.0.0.1:8000/tutorial/`
   - REST API Docs: `http://127.0.0.1:8000/docs`
   - GraphQL Playground: `http://127.0.0.1:8000/graphql`
   - Active Reactors: `http://127.0.0.1:8000/api/v1/reactors`

5. **Level 4/5 Digital Twin Engine (PyTorch)**:
   ```bash
   python digital_twin/digital_twin_engine.py
   ```

6. **Level 0/1 Synthetic Telemetry Generator (Python)**:
   ```bash
   # Run for Stellarator (default)
   python synthetic_generator/synthetic_data_gen.py --freq 100.0 --quench-after 3.0

   # Run for Tokamak
   python synthetic_generator/synthetic_data_gen.py --reactor REACTOR_TOKAMAK --mode MODE_TOKAMAK_MAJOR_DISRUPTION

   # Run for ICF
   python synthetic_generator/synthetic_data_gen.py --reactor REACTOR_ICF --mode MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY
   ```
