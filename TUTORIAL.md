# Beginner's Guide: Nuclear Fusion, Multi-Reactor Topologies, and TAMI Control Architecture

Welcome! If you are new to nuclear fusion, magnetics, laser drivers, or real-time control software, this tutorial is designed for you. You do not need an advanced degree in plasma physics or decades of industrial automation experience to understand how this code works.

This guide breaks down every concept step-by-step using clear physical analogies, rigorous mathematical formulas rendered via $\LaTeX$, interactive Mermaid architecture diagrams, and real-world citations from [Fusion Energy Base](https://www.fusionenergybase.com/articles?tag=physics).

---

## 📚 Table of Contents

1. [What is Nuclear Fusion?](#1-what-is-nuclear-fusion)
2. [Fusion Reactor Architectures: Stellarators, Tokamaks, and ICF](#2-fusion-reactor-architectures-stellarators-tokamaks-and-icf)
   - 2.1 [The Three Major Confinement Topologies](#21-the-three-major-confinement-topologies)
   - 2.2 [Tokamak Electromagnetics & Operational Limits](#22-tokamak-electromagnetics--operational-limits)
   - 2.3 [Quasi-Isodynamic (QI) Modular Stellarators](#23-quasi-isodynamic-qi-modular-stellarators)
   - 2.4 [Laser Inertial Confinement Fusion (ICF)](#24-laser-inertial-confinement-fusion-icf)
   - 2.5 [The Lawson Criteria: Magnetic Confinement vs. Areal Density](#25-the-lawson-criteria-magnetic-confinement-vs-areal-density)
   - 2.6 [Plant Power Balance & 2D Sankey Energy Flow](#26-plant-power-balance--2d-sankey-energy-flow)
   - 2.7 [Cross-Reactor Failure Modes & Edge Protection Matrix](#27-cross-reactor-failure-modes--edge-protection-matrix)
3. [High-Temperature Superconductors (HTS) & REBCO Magnet Coils](#3-high-temperature-superconductors-hts--rebco-magnet-coils)
4. [The Critical Failure: What is a Magnet Quench?](#4-the-critical-failure-what-is-a-magnet-quench)
5. [How We Detect Quenches: FOAS & Stray Capacitance](#5-how-we-detect-quenches-foas--stray-capacitance)
6. [The Software Architecture: Purdue 6-Tier Model & IEC 62443 Security](#6-the-software-architecture-purdue-6-tier-model--iec-62443-security)
7. [Digital Twins, Three.js 3D Rendering & Physics-Informed Neural Networks (PINN)](#7-digital-twins-threejs-3d-rendering--physics-informed-neural-networks-pinn)
8. [Codebase Execution Flow: Step-by-Step Telemetry Journey](#8-codebase-execution-flow-step-by-step-telemetry-journey)
9. [External References & Scientific Citations](#9-external-references--scientific-citations)

---

## 1. What is Nuclear Fusion?

At its core, **nuclear fusion** is the power source of the Sun and stars.

As explained on [Fusion Energy Base - What is Fusion Energy?](https://www.fusionenergybase.com/articles/what-is-fusion-energy):
> *"When two light atomic nuclei like Deuterium and Tritium (two isotopes of hydrogen) fuse into a heavier element like Helium and a free neutron, energy is released. The energy comes from converting a small fraction of the mass of the reactants into kinetic energy via Einstein's mass-energy equivalence $E = \Delta m \cdot c^2$."*

```
   Deuterium (²H)  \
                     ===>  [ FUSION REACTION ] ===>  Helium-4 (⁴He, 3.52 MeV) + Free Neutron (n, 14.06 MeV)
   Tritium (³H)    /
```

### Why is Controlled Fusion Challenging?
1. **Coulomb Repulsion**: Both hydrogen nuclei carry a positive electric charge. Like charges violently repel each other.
2. **Extreme Thermal Energies**: To overcome this electrostatic barrier and bring nuclei close enough for the Strong Nuclear Force to bind them ($\sim 10^{-15}\text{ m}$), the fuel must be heated to over **$100\text{--}150\text{ Million }^\circ\text{C}$** ($10\text{--}15\text{ keV}$).
3. **Plasma State**: At these temperatures, matter exists as an electrically conductive ionized fluid of stripped electrons and ions called **Plasma**.

---

## 2. Fusion Reactor Architectures: Stellarators, Tokamaks, and ICF

No physical solid material can directly contact a $150\text{ Million }^\circ\text{C}$ plasma without vaporizing immediately. The global fusion effort has developed three primary physical approaches:

```mermaid
graph TD
    A["Nuclear Fusion Approaches"] --> B["Magnetic Confinement Fusion (MCF)"]
    A --> C["Inertial Confinement Fusion (ICF)"]
    
    B --> B1["Advanced Tokamak"]
    B --> B2["Quasi-Isodynamic Stellarator"]
    
    B1 --> T1["Central Solenoid Inductive Driver"]
    B1 --> T2["Toroidal Plasma Current Ip ~ 15 MA"]
    B1 --> T3["Subject to Major Disruptions"]
    
    B2 --> S1["3D Modular Non-Planar HTS Coils"]
    B2 --> S2["Zero Driven Net Plasma Current"]
    B2 --> S3["Disruption-Free Continuous Flattop"]
    
    C --> I1["High-Repetition UV Laser Banks (5 Hz)"]
    I1 --> I2["Cryogenic DT Fuel Pellet Compression"]
    I1 --> I3["Ablative Rocket Implosion to 1000x Solid Density"]
```

---

### 2.1 The Three Major Confinement Topologies

| Engineering Metric | Advanced Tokamak | QI Modular Stellarator | Laser Inertial Confinement (ICF) |
| :--- | :--- | :--- | :--- |
| **Confinement Mechanism** | Magnetic (Toroidal + Poloidal Fields) | Magnetic (3D Omnigenous Coils) | Inertial (Ablation Drive Pressure) |
| **Operational Duty Cycle** | Pulsed / Inductive ($\sim 10^3\text{ s}$) | Continuous Steady-State ($10^6\text{ s}$) | High-Repetition Pulsed ($5\text{--}10\text{ Hz}$) |
| **Plasma Current ($I_p$)** | High ($15\text{--}20\text{ MA}$) | Zero ($I_{\text{net}} \approx 0\text{ kA}$) | Zero (Target microcapsule) |
| **Major Disruption Risk** | **High** (Current collapse $<15\text{ ms}$) | **Zero** (Inherently stable) | None (Hydrodynamic instabilities instead) |
| **Primary Driver System** | Central Solenoid + NBI + RF ($65\%$) | ECRH Gyrotrons + ICRH ($60\%$) | Diode-Pumped UV Solid-State Lasers ($15\%$) |
| **Scientific Gain ($Q_{\text{sci}}$ / $G$)** | $Q_{\text{sci}} \approx 10\text{--}15$ | $Q_{\text{sci}} \approx 10\text{--}12$ | Target Gain $G \approx 80\text{--}120$ |
| **Exhaust / First Wall** | Single/Double Null Poloidal Divertor | Helical Island Divertor | Spherical Chamber w/ Liquid Li Waterfall |

---

### 2.2 Tokamak Electromagnetics & Operational Limits

An **Advanced Tokamak** achieves magnetic twist by driving a massive toroidal electric current $I_p$ directly through the plasma using an inductive transformer called the **Central Solenoid**.

#### Fundamental Physics Equations:
1. **Safety Factor ($q_{95}$)**:
   Measures the helical pitch of magnetic field lines at the 95% normalized flux surface. To avoid violent kink instabilities, the safety factor must satisfy the Kruskal-Shafranov limit:
   $$q_{95} \approx \frac{5 a^2 B_T}{R_0 I_p} \left( \frac{1 + \kappa^2}{2} \right) \ge 2.5\text{--}3.0$$
   Where $a$ is minor radius, $R_0$ is major radius, $B_T$ is toroidal field, and $\kappa$ is vertical plasma elongation ($\sim 1.7$).

2. **Greenwald Density Limit ($n_G$)**:
   The maximum line-averaged electron density before radiative edge cooling triggers a total plasma disruption:
   $$n_G = \frac{I_p}{\pi a^2} \times 10^{20} \text{ m}^{-3}$$
   Operating at $n_e / n_G > 0.85$ requires aggressive fueling and edge-localized mode (ELM) mitigation.

3. **Loop Voltage & Inductive Flux**:
   $$V_{\text{loop}} = \frac{d\Phi_{\text{CS}}}{dt} = L_p \frac{dI_p}{dt} + R_p I_p$$
   During nominal flattop, $V_{\text{loop}} \approx 0.1\text{ V}$. During a **Major Disruption**, the sudden current collapse ($\frac{dI_p}{dt} \approx -10^9\text{ A/s}$) induces a destructive voltage spike:
   $$V_{\text{loop,disrupt}} > 150\text{--}200\text{ Volts}$$

---

### 2.3 Quasi-Isodynamic (QI) Modular Stellarators

In a **Quasi-Isodynamic Stellarator** (championed by **SKHY**), the entire helical twisting field is generated completely by external **3D non-planar superconducting modular coils**, requiring **zero net plasma current** ($I_p = 0$).

#### Key Physical Advantages:
1. **Intrinsic Disruption Immunity**: Since there is no multi-megampere plasma current, current-driven disruptions, vertical displacement events (VDEs), and locked modes are physically impossible.
2. **Omnigenity & Reduced Neoclassical Ripple**:
   In classic stellarators, 3D field ripples caused trapped particles to drift outward. Quasi-isodynamic optimization guarantees that the bounce-averaged radial drift velocity vanishes:
   $$\overline{v_{dr}} = \frac{1}{\tau_b} \oint \frac{v_\parallel \times \nabla B}{\Omega} \cdot \nabla \psi \, dt = 0$$
   This reduces neoclassical heat transport to levels comparable to axisymmetric tokamaks.
3. **Resonant Island Divertor**:
   The magnetic field naturally forms closed magnetic islands at rational rotational transform boundaries ($\iota = n/m = 5/5$). Heat and helium ash flow gently into target plates along these island legs, achieving radiative detachment at heat fluxes $\le 5\text{ MW/m}^2$.

---

### 2.4 Laser Inertial Confinement Fusion (ICF)

Instead of holding plasma magnetically for seconds, **Inertial Confinement Fusion** compresses a frozen Deuterium-Tritium pellet ($r \approx 1\text{ mm}$) to immense densities using high-energy laser pulses.

```mermaid
sequenceDiagram
    autonumber
    participant Lasers as 16 UV Laser Beams (2.15 MJ)
    participant Pellet as Cryogenic D-T Target Capsule
    participant Hotspot as Core Ignition Spark Hotspot
    participant Grid as Thermal Turbine & Power Grid
    
    Lasers->>Pellet: 1. Laser Flash: Ablator surface vaporizes instantly
    Note over Pellet: Rocket effect produces 180 Mbar ablation pressure
    Pellet->>Hotspot: 2. Implosion: Fuel compressed to >1000x solid density (350 km/s)
    Note over Hotspot: Central spark reaches 10 keV & rho*R > 3 g/cm2
    Hotspot->>Hotspot: 3. Thermonuclear Burn Wave: Gain G = 85 (E_fus = 182.75 MJ)
    Hotspot->>Grid: 4. 14.1 MeV Neutrons absorbed by Liquid Li blanket @ 5 Hz
    Note over Grid: Average Fusion Power = 914 MW | Net Grid Export = +85 MW
```

#### Key Physics Quantities:
1. **Target Gain ($G$)**:
   $$G = \frac{E_{\text{fusion}}}{E_{\text{driver}}} = \frac{182.75\text{ MJ}}{2.15\text{ MJ}} \approx 85.0$$
2. **Implosion Velocity & Stagnation Pressure**:
   The ablator rocket velocity exceeds $v_{\text{imp}} \approx 350\text{--}400\text{ km/s}$, driving ablation pressures $P_{\text{abl}} \approx 100\text{--}250\text{ Mbar}$.
3. **Repetition Rate ($f_{\text{rep}}$) & Average Power**:
   To generate steady commercial power, targets are injected and zapped at $f_{\text{rep}} \approx 5.0\text{ Hz}$:
   $$P_{\text{fusion,avg}} = E_{\text{laser}} \cdot G \cdot f_{\text{rep}} = 2.15\text{ MJ} \cdot 85 \cdot 5\text{ s}^{-1} \approx 913.75\text{ MW}$$

---

### 2.5 The Lawson Criteria: Magnetic Confinement vs. Areal Density

To achieve net energy release, the fusion reaction must generate enough alpha particle self-heating ($E_\alpha = 3.52\text{ MeV}$) to overcome Bremsstrahlung radiation and thermal conduction losses.

#### 1. Magnetic Confinement (Lawson Triple Product):
$$n \cdot T \cdot \tau_E \ge 3 \times 10^{21} \text{ keV}\cdot\text{s}\cdot\text{m}^{-3}$$
- High Confinement Time ($\tau_E \approx 1.5\text{--}3.0\text{ s}$)
- Moderate Density ($n_e \approx 1\text{--}3 \times 10^{20}\text{ m}^{-3}$)
- Core Temperature ($T_i \approx 10\text{--}20\text{ keV}$)

#### 2. Inertial Confinement (Areal Density $\rho R$):
$$\rho R \ge 3.0 \text{ g/cm}^2$$
- Ultra-Short Confinement Time ($\tau_{\text{inertial}} \approx \frac{R}{c_s} \approx 0.1\text{ nanoseconds}$)
- Ultra-High Density ($\rho \approx 300\text{--}1000\text{ g/cm}^3$, or $10^{26}\text{ m}^{-3}$)

---

### 2.6 Plant Power Balance & 2D Sankey Energy Flow

As demonstrated in the interactive **2D Sankey Simulator** (inspired directly by the [Fusion Energy Base Simulator](https://www.fusionenergybase.com/fusion-power-plant-simulator)), a commercial power plant must balance electrical inputs against thermal and electric conversion efficiencies.

```mermaid
flowchart LR
    P_driver_elec["Driver Wall-Plug Power: P_inj / eta_driver"] --> DriverSys["Heating / Laser System (eta_driver)"]
    P_aux["Cryogenics & Aux Loads P_aux"] --> RecircSum["Total Recirculating Power P_recirc"]
    P_driver_elec --> RecircSum
    
    DriverSys -->|Injected Power P_inj| Core["Fusion Reaction Core: Q_sci = P_fus / P_inj"]
    Core -->|Fusion Yield P_fusion| Blanket["Breeding Blanket (Multiplier M ~ 1.15)"]
    DriverSys -->|Residual Thermal Heat| Blanket
    
    Blanket -->|Total Thermal Power P_th| Turbine["Turbine Generator (eta_thermal ~ 38%)"]
    Turbine -->|Gross Electricity P_gross| SplitNode{"Electrical Split"}
    
    SplitNode -->|Recirculation Loop| RecircSum
    SplitNode -->|Surplus P_net > 0| Grid["Public Municipal Power Grid"]
```

#### Core Mathematical Equations:
1. **Scientific Gain ($Q_{\text{sci}}$) vs. Target Gain ($G$)**:
   $$Q_{\text{sci}} = \frac{P_{\text{fusion}}}{P_{\text{injected}}} \quad\text{or}\quad G = \frac{E_{\text{fusion}}}{E_{\text{laser}}}$$
2. **Total Thermal Power into Steam Cycle**:
   $$P_{\text{thermal}} = P_{\text{fusion}} \cdot M + P_{\text{injected}}$$
   Where $M \approx 1.15$ is the blanket energy multiplier from exothermic Lithium-6 neutron capture:
   $$\text{n} + {}^6\text{Li} \to {}^4\text{He} + {}^3\text{H} + 4.78\text{ MeV}$$
3. **Gross Electricity Generated**:
   $$P_{\text{gross}} = P_{\text{thermal}} \cdot \eta_{\text{thermal}}$$
4. **Total Recirculating Electrical Power**:
   $$P_{\text{recirc}} = \frac{P_{\text{injected}}}{\eta_{\text{driver}}} + P_{\text{aux}}$$
5. **Net Electric Power to Grid**:
   $$P_{\text{net}} = P_{\text{gross}} - P_{\text{recirc}}$$
6. **Engineering Gain ($Q_{\text{eng}}$)**:
   $$Q_{\text{eng}} = \frac{P_{\text{gross}}}{P_{\text{recirc}}}$$

> [!IMPORTANT]
> **Why $Q_{\text{sci}} = 1.0$ is insufficient for electricity generation**:
> For a laser-driven ICF system with $\eta_{\text{driver}} = 15\%$ and $\eta_{\text{th}} = 38\%$, the engineering breakeven ($P_{\text{net}} > 0$) requires:
> $$G > \frac{1}{\eta_{\text{driver}} \cdot \eta_{\text{thermal}}} \approx \frac{1}{0.15 \cdot 0.38} \approx 17.5$$
> For commercial economics ($Q_{\text{eng}} \ge 2.5$), the target gain must exceed **$G \ge 80\text{--}100$**!

---

### 2.7 Cross-Reactor Failure Modes & Edge Protection Matrix

| Reactor Type | Failure Mode | Physical Root Cause | Microsecond Sensor Signature | Edge Actuator Action |
| :--- | :--- | :--- | :--- | :--- |
| **Tokamak** | **Major Disruption** | Resistive tearing modes lock to vessel; thermal collapse | Pick-up coils ($dB/dt$), loop voltage spike $>150\text{ V}$ | Massive Gas Injection (MGI) / Shattered Pellet |
| **Tokamak** | **Vertical Displacement (VDE)** | Axisymmetric positional feedback saturation | Vertical position error $\Delta Z > 30\text{ mm}$ | Fast coil stabilization & emergency rampdown |
| **Tokamak** | **Runaway Electron Beam** | Electric field exceeds Dreicer limit during current quench | Hard X-ray detectors & photoneutron emissions | Deuterium killer pellet injection |
| **Stellarator** | **HTS Hotspot Quench** | Cryogenic helium cooling void in REBCO modular coil | FOAS acoustic emission $>25\text{ kHz}$, $dC/dt > 15\text{ pF/s}$ | Fast energy extraction dump breaker ($<50\text{ \mu s}$) |
| **Stellarator** | **Divertor Detachment Fault** | Impurity seeding line clogged; radiative cooling lost | Strike tile thermocouple $>900^\circ\text{C}$, heat flux $>15\text{ MW/m}^2$ | Secondary gas puff actuator burst |
| **ICF** | **Rayleigh-Taylor Instability** | Ablation-front perturbation grows exponentially: $\gamma = \sqrt{kg}$ | X-ray pinhole camera asymmetry RMS $>2.5\%$ | Laser beam balance trimming & adiabat shaping |
| **ICF** | **Target Tracking Miss** | Target injection trajectory deviation at chamber center | Optical laser position gate error $>30\text{ \mu m}$ | Laser shot abort / dump beam to calorimeters |

---

## 3. High-Temperature Superconductors (HTS) & REBCO Magnet Coils

To create 5.5 to 15 Tesla magnetic fields without melting copper wires from Joule heating ($I^2 R$), magnetic confinement reactors use **Superconducting Magnets**.

- Standard copper wire dissipates gigawatts of heat in resistive losses.
- **Superconductors** carry electric current with **strictly ZERO electrical resistance** when cooled below their critical temperature ($T_c$).

We utilize **REBCO (Rare-Earth Barium Copper Oxide)** high-temperature superconductor tape (operated at **$20\text{ Kelvin}$** using supercritical helium). A single 4mm-wide REBCO tape ribbon can carry over **$500\text{ Amperes}$** of current!

---

## 4. The Critical Failure: What is a Magnet Quench?

A **Quench** is a thermal runaway event where a localized section of superconductor loses its superconducting state:

```mermaid
sequenceDiagram
    autonumber
    participant Tape as REBCO Superconducting Tape (20K)
    participant Hotspot as 1mm Hotspot (>92K)
    participant Edge as Level 1 Edge Interlock (Rust MTCA.4)
    participant Breaker as Fast Discharge Pyro-Breaker
    
    Tape->>Hotspot: Mechanical strain, epoxy crack, or cooling fluctuation
    Note over Hotspot: Temperature exceeds Tc ~ 92K (Superconductivity Lost!)
    Hotspot->>Hotspot: Electrical resistance appears! Intense Joule heating (I^2 * R)
    Hotspot->>Tape: Normal Zone Propagation Velocity (NZPV ~ 2-5 cm/s)
    Edge->>Edge: FOAS Acoustic Burst (>25 kHz) + Capacitance Shift detected
    Edge->>Breaker: Actuator Trigger: < 22 Microseconds!
    Breaker->>Tape: Disconnects power supply & dumps energy into resistor bank
```

Because REBCO has a very low **Normal Zone Propagation Velocity (NZPV $\approx 0.01\text{--}0.08\text{ m/s}$)**, the resistive heat does not spread quickly along the coil—it concentrates violently in a 1-millimeter hotspot. If not discharged within **$50\text{ milliseconds}$**, the coil will permanently melt through!

---

## 5. How We Detect Quenches: FOAS & Stray Capacitance

To detect hotspot inception before voltages become dangerous, TAMI employs dual complementary physical diagnostics:

1. **Fiber-Optic Acoustic Sensing (FOAS)**:
   Fiber cables are co-wound inside the magnet winding pack. When crystalline REBCO experiences micro-fractures or Lorentz strain relaxation prior to quench, it emits ultrasonic acoustic bursts:
   $$f_{\text{acoustic}} \ge 25\text{--}35\text{ kHz}$$
2. **Stray Capacitance Dielectric Sensing**:
   Capacitive probes track the dielectric permittivity of cryogenic helium coolant ($dC/dt$). Boiling helium bubbles from localized warming create immediate capacitance drops.

---

## 6. The Software Architecture: Purdue 6-Tier Model & IEC 62443 Security

The TAMI control infrastructure is structured strictly under the **Purdue Model (ISA-95)** and compliant with **IEC 62443** industrial cybersecurity zones:

```mermaid
flowchart TD
    subgraph Level5 [Level 5: Enterprise Agentic AI]
        L5[FastAPI & Strawberry GraphQL Telemetry Endpoints]
    end
    
    subgraph Level4 [Level 4: Plant Management & Digital Twin]
        L4_1[PyTorch PINN 3D Equilibrium Surrogate Model]
        L4_2[HDF5 High-Volume Data Lake Storage]
    end
    
    subgraph Level3 [Level 3: TAMI Supervisory Control Hub]
        L3[Rust Supervisory Middleware: DDS-to-Kafka Bridge & Rate Limiter]
    end
    
    subgraph Level2 [Level 2: Area Control Zone]
        L2[Magnet Power Supplies & Cryogenic PLCs]
    end
    
    subgraph Level1 [Level 1: Edge Safety Interlocks]
        L1[Rust Microsecond Safety Kernel - MTCA.4 FPGA]
    end
    
    subgraph Level0 [Level 0: Physical Fusion Hardware]
        L0[HTS Coils, TF/CS Magnets, FOAS Fiber Cables, Laser Drivers]
    end
    
    L0 <-->|Microsecond Sensor Signals| L1
    L1 <-->|Hardwired Interlock Bus| L2
    L2 <-->|DDS Real-Time Bus| L3
    L3 -->|Kafka Streaming Bridge| L4_1
    L3 -->|Kafka Streaming Bridge| L4_2
    L4_1 -->|Read-Only REST/GraphQL| L5
    L4_2 -->|Read-Only REST/GraphQL| L5
```

- **Level 1 (Edge Protection)**: Written in **Rust** (`edge_quench`). Guarantees zero-heap allocations and evaluates interlock logic in **$< 50\text{ \mu s}$**.
- **Level 3 (Supervisory Middleware)**: Written in **Rust** (`middleware_hub`). Enforces token-bucket rate limiting ($100\text{ msgs/s}$) and bridges DDS real-time buses to enterprise Kafka.
- **Level 4 (Digital Twin & Data Lake)**: Python PyTorch surrogate models and HDF5 storage (`tami_data_lake.h5`).
- **Level 5 (Enterprise AI Ingestion)**: FastAPI and Strawberry GraphQL (`ai_ingestion_api.py`) exposing read-only data for training AI agent models.

---

## 7. Digital Twins, Three.js 3D Rendering & Physics-Informed Neural Networks (PINN)

The TAMI digital twin runs an interactive **Three.js WebGL 3D Studio** and a **PyTorch Physics-Informed Neural Network (PINN)**:

### 1. Three.js Procedural 3D Visualizer:
- **QI Stellarator**: Renders 20 non-planar modular HTS coils with sinusoidal out-of-plane twist, helical twisted plasma flux surface, and localized hotspot quench sparks.
- **Advanced Tokamak**: Renders the central solenoid cylinder, 16 D-shaped toroidal field coils, elongated D-torus plasma, and disruption collapse effects.
- **Laser ICF**: Renders the spherical chamber, 16 converging UV laser beam cones, cryogenic fuel pellet, 5 Hz pulsed shot detonations, and Rayleigh-Taylor asymmetry fingers.

### 2. PINN Multi-Physics Loss Function:
A PINN enforces fundamental MHD and conservation laws directly into the neural network's loss function:
$$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{sensors}} + \lambda_{\text{MHD}} \mathcal{L}_{\text{Grad-Shafranov}} + \lambda_{\text{thermal}} \mathcal{L}_{\text{heat}}$$

Where the Grad-Shafranov equilibrium equation dictates:
$$\Delta^* \psi = -\mu_0 R^2 \frac{dp}{d\psi} - F \frac{dF}{d\psi}$$

---

## 8. Codebase Execution Flow: Step-by-Step Telemetry Journey

When running the TAMI demonstration pipeline (`run_demo.py`):

```mermaid
sequenceDiagram
    autonumber
    participant Gen as Synthetic Generator (synthetic_data_gen.py)
    participant Edge as Level 1 Edge Kernel (Rust)
    participant Hub as Level 3 Middleware Hub (Rust)
    participant Twin as Level 4 Digital Twin Engine (PyTorch)
    participant API as Level 4/5 Data Lake API (FastAPI)
    participant Viewer as Interactive Web Studio (Three.js / Sankey)

    Gen->>Edge: UDP Telemetry Stream (Port 9003)
    Gen->>Hub: TCP Protobuf Envelopes (Port 9001)
    Gen->>Twin: UDP Telemetry Stream (Port 9004)
    Twin->>API: SubsystemTelemetryReport (Port 9005)
    API->>API: Persists Record into HDF5 ('tami_data_lake.h5')
    Viewer->>API: Polls GET /api/v1/subsystems/latest (every 600ms)
    Viewer->>Viewer: Updates 3D Model, 2D Sankey Ribbons, and Metrics HUD
```

---

## 9. External References & Scientific Citations

1. **Fusion Physics & Power Plant Simulators**:
   - [Fusion Energy Base - Fusion Power Plant Simulator](https://www.fusionenergybase.com/fusion-power-plant-simulator)
   - [Fusion Energy Base - Scientific Gain and Fusion Power Plants](https://www.fusionenergybase.com/articles/fusion-physics-part-1-scientific-gain-and-fusion-power-plants)
2. **Lawson Criteria & Breakeven Progress**:
   - [Fusion Energy Base - Progress Toward Fusion Breakeven](https://www.fusionenergybase.com/articles/continuing-progress-toward-fusion-energy-breakeven-and-gain-as-measured-against-the-lawson-criteria)
3. **High-Temperature Superconductors (HTS) in Fusion Magnets**:
   - [Fusion Energy Base - HTS Commercial Orders & Magnet Designs](https://www.fusionenergybase.com/articles/cfs-places-largest-ever-hts-tape-order-with-fujikura-for-arc-power-plant)
4. **General Plasma Physics Articles**:
   - [Fusion Energy Base - Physics Tagged Research Archive](https://www.fusionenergybase.com/articles?tag=physics)
