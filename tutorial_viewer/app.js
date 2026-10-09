// SKHY - TAMI Interactive Tutorial Viewer Engine

document.addEventListener('DOMContentLoaded', () => {
    initTabNavigation();
    initQuenchSimulator();
    initSubsystemsTwin();
    initPowerBalanceSimulator();
    initPurdueInspector();
    init3DDigitalTwinCanvas();
    initMarkdownTutorial();
});

/* -------------------------------------------------------------------------- */
/* 1. Tab Navigation System                                                  */
/* -------------------------------------------------------------------------- */
function initTabNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');

            navButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));

            btn.classList.add('active');
            const targetEl = document.getElementById(targetTab);
            if (targetEl) targetEl.classList.add('active');

            if (targetTab === 'guide-doc' || targetTab === 'subsystems-twin') {
                renderMermaidDiagrams();
            }
        });
    });
}

/* -------------------------------------------------------------------------- */
/* 2. Interactive REBCO Quench & FOAS Simulator                              */
/* -------------------------------------------------------------------------- */
let animFrameId = null;

function initQuenchSimulator() {
    const tempSlider = document.getElementById('temp-slider');
    const foasSlider = document.getElementById('foas-slider');
    const capSlider = document.getElementById('cap-slider');

    const tempVal = document.getElementById('temp-val');
    const foasVal = document.getElementById('foas-val');
    const capVal = document.getElementById('cap-val');

    const statusBox = document.getElementById('status-box');
    const statusTitle = document.getElementById('status-title');
    const statusSub = document.getElementById('status-sub');
    const nzpvVal = document.getElementById('nzpv-val');
    const latencyVal = document.getElementById('latency-val');
    const acousticStatus = document.getElementById('acoustic-status');
    const breakerStatus = document.getElementById('breaker-status');

    const btnNominal = document.getElementById('btn-preset-nominal');
    const btnQuench = document.getElementById('btn-preset-quench');

    function updateSimulation() {
        const temp = parseFloat(tempSlider.value);
        const foas = parseFloat(foasSlider.value);
        const cap = parseFloat(capSlider.value);

        tempVal.textContent = `${temp.toFixed(1)} K`;
        foasVal.textContent = `${Math.round(foas).toLocaleString()} Hz`;
        capVal.textContent = `${cap.toFixed(1)} pF/s`;

        // Physics Threshold Evaluation (Level 1 Edge Interlock Logic)
        const acousticTripped = foas >= 25000;
        const tempTripped = temp >= 90.0;
        const capTripped = cap >= 15.0;

        let nzpv = 0.0;
        if (temp > 70.0) {
            nzpv = Math.min(0.085, 0.02 + 0.001 * (temp - 70.0));
        }

        const isQuench = acousticTripped || tempTripped || capTripped;

        if (isQuench) {
            statusBox.classList.add('quench-tripped');
            statusTitle.textContent = 'SYSTEM STATE: EMERGENCY_QUENCH_DUMP';
            statusTitle.style.color = '#FF3366';

            let reason = [];
            if (acousticTripped) reason.push(`FOAS Stress Burst (${Math.round(foas)} Hz)`);
            if (tempTripped) reason.push(`Critical Temp (${temp.toFixed(1)} K)`);
            if (capTripped) reason.push(`Dielectric Shift (${cap.toFixed(1)} pF/s)`);

            statusSub.textContent = `INTERLOCK TRIPPED! Reason: ${reason.join(' + ')}`;
            nzpvVal.textContent = `${nzpv.toFixed(4)} m/s`;
            nzpvVal.style.color = '#FF3366';
            latencyVal.textContent = '21.4 μs';
            acousticStatus.textContent = acousticTripped ? 'STRESS BURST (>25 kHz)' : 'Elevated';
            acousticStatus.style.color = '#FF3366';
            breakerStatus.textContent = 'TRIPPED (DISCHARGED)';
            breakerStatus.style.color = '#FF3366';
        } else {
            statusBox.classList.remove('quench-tripped');
            statusTitle.textContent = 'SYSTEM STATE: STEADY_STATE_BURN (NOMINAL)';
            statusTitle.style.color = '#00E676';
            statusSub.textContent = 'Superconducting state active. Zero electrical resistance.';
            nzpvVal.textContent = '0.0000 m/s';
            nzpvVal.style.color = '#00F2FE';
            latencyVal.textContent = '14.2 μs';
            acousticStatus.textContent = 'Normal (<25 kHz)';
            acousticStatus.style.color = '#00E676';
            breakerStatus.textContent = 'CLOSED (Energized)';
            breakerStatus.style.color = '#00E676';
        }

        renderWaveform(foas, isQuench);
    }

    tempSlider.addEventListener('input', updateSimulation);
    foasSlider.addEventListener('input', updateSimulation);
    capSlider.addEventListener('input', updateSimulation);

    btnNominal.addEventListener('click', () => {
        tempSlider.value = 20;
        foasSlider.value = 1200;
        capSlider.value = 0.2;
        updateSimulation();
    });

    btnQuench.addEventListener('click', () => {
        tempSlider.value = 94.5;
        foasSlider.value = 31200;
        capSlider.value = 24.5;
        updateSimulation();
    });

    updateSimulation();
}

/* Oscilloscope Waveform Renderer */
function renderWaveform(freqHz, isQuench) {
    const canvas = document.getElementById('waveform-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Draw grid background
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 30) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
    }
    for (let y = 0; y < height; y += 20) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    // Draw sine wave
    ctx.strokeStyle = isQuench ? '#FF3366' : '#00F2FE';
    ctx.lineWidth = 2;
    ctx.beginPath();

    const time = Date.now() * 0.005;
    const frequencyFactor = Math.min(0.2, 0.02 + (freqHz / 40000) * 0.18);
    const amplitude = isQuench ? 35 : 12;

    for (let x = 0; x < width; x++) {
        const noise = (Math.random() - 0.5) * (isQuench ? 15 : 3);
        const y = height / 2 + Math.sin(x * frequencyFactor + time) * amplitude + noise;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();
}

/* -------------------------------------------------------------------------- */
/* 2b. Scientific Gain Q_sci & Power Balance Simulator (Sam Wurzel Model)     */
/* -------------------------------------------------------------------------- */
function initPowerBalanceSimulator() {
    const qsciSlider = document.getElementById('qsci-slider');
    const pheatSlider = document.getElementById('pheat-slider');
    const etathSlider = document.getElementById('etath-slider');
    const etaheatSlider = document.getElementById('etaheat-slider');

    const qsciVal = document.getElementById('qsci-val');
    const pheatVal = document.getElementById('pheat-val');
    const etathVal = document.getElementById('etath-val');
    const etaheatVal = document.getElementById('etaheat-val');

    const statusBox = document.getElementById('power-status-box');
    const statusTitle = document.getElementById('power-status-title');
    const statusSub = document.getElementById('power-status-sub');

    const pfusionVal = document.getElementById('pfusion-val');
    const pexitVal = document.getElementById('pexit-val');
    const pgrossVal = document.getElementById('pgross-val');
    const precircVal = document.getElementById('precirc-val');
    const qengVal = document.getElementById('qeng-val');
    const recircFracVal = document.getElementById('recirc-frac-val');

    if (!qsciSlider) return;

    function updatePowerBalance() {
        const qsci = parseFloat(qsciSlider.value);
        const pheat = parseFloat(pheatSlider.value);
        const etath = parseFloat(etathSlider.value) / 100.0;
        const etaheat = parseFloat(etaheatSlider.value) / 100.0;

        qsciVal.textContent = qsci.toFixed(1);
        pheatVal.textContent = `${Math.round(pheat)} MW`;
        etathVal.textContent = `${Math.round(etath * 100)}%`;
        etaheatVal.textContent = `${Math.round(etaheat * 100)}%`;

        // Physical Power Balance Equations
        const pfusion = qsci * pheat;
        const pexit = pfusion + pheat;
        const pgross = pexit * etath;
        const precircHeat = pheat / etaheat;
        const pcryo = 8.5; // HTS Magnet cryogenic refrigeration load
        const ptotalRecirc = precircHeat + pcryo;
        const pnet = pgross - ptotalRecirc;
        const qeng = pgross / ptotalRecirc;
        const recircFrac = (ptotalRecirc / pgross) * 100.0;

        pfusionVal.textContent = `${pfusion.toFixed(1)} MW`;
        pexitVal.textContent = `${pexit.toFixed(1)} MW`;
        pgrossVal.textContent = `${pgross.toFixed(1)} MW`;
        precircVal.textContent = `${ptotalRecirc.toFixed(1)} MW`;
        qengVal.textContent = `${qeng.toFixed(2)}`;
        recircFracVal.textContent = `${Math.min(999, Math.max(0, recircFrac)).toFixed(1)}%`;

        if (pnet > 0) {
            statusBox.classList.remove('quench-tripped');
            statusTitle.textContent = `NET ELECTRICITY DELIVERED: +${pnet.toFixed(1)} MW`;
            statusTitle.style.color = '#00E676';
            statusSub.textContent = `Surplus electricity exported to public grid! Engineering Gain Q_eng = ${qeng.toFixed(2)}`;
            qengVal.style.color = '#00E676';
        } else {
            statusBox.classList.add('quench-tripped');
            statusTitle.textContent = `GRID DEFICIT: ${pnet.toFixed(1)} MW (DRAWING POWER)`;
            statusTitle.style.color = '#FF3366';
            statusSub.textContent = `Insufficient gain! Plant requires more electrical power to operate than it generates.`;
            qengVal.style.color = '#FF3366';
        }
    }

    qsciSlider.addEventListener('input', updatePowerBalance);
    pheatSlider.addEventListener('input', updatePowerBalance);
    etathSlider.addEventListener('input', updatePowerBalance);
    etaheatSlider.addEventListener('input', updatePowerBalance);

    updatePowerBalance();
}

/* -------------------------------------------------------------------------- */
/* 3. Purdue 6-Tier Architecture Inspector                                   */
/* -------------------------------------------------------------------------- */
const PURDUE_DATA = {
    5: {
        title: "Level 5: Enterprise Agentic AI & Multi-Physics Query API",
        file: "data_lake_api/ai_ingestion_api.py",
        desc: "Provides isolated read-only REST (/api/v1/telemetry/latest) and Strawberry GraphQL (/graphql) endpoints. Designed for Agentic AI models to query multi-physics historical data, FOAS acoustic stress emissions, and 3D equilibrium flux reconstructions for training.",
        security: "IEC 62443 Zone 5 - Read-Only Isolated Subnet. No direct back-propagation into control loops."
    },
    4: {
        title: "Level 4: Plant Management & Digital Twin Data Lake",
        file: "digital_twin/digital_twin_engine.py & tami_data_lake.h5",
        desc: "Executes a PyTorch Physics-Informed Neural Network (PINN) surrogate model reconstructing 3D flux surface mesh (R, Z, Phi), toroidal beta, and peak magnet strain. Persists high-volume time-series telemetry into HDF5 datasets.",
        security: "IEC 62443 Zone 4 - Streaming Kafka Egress Conduit from Level 3."
    },
    3: {
        title: "Level 3: TAMI Supervisory Control Middleware Hub",
        file: "middleware_hub/src/main.rs (Rust)",
        desc: "High-throughput supervisory routing hub. Validates Protobuf envelopes, verifies monotonically increasing sequence numbers, enforces token-bucket rate limiting (100 msgs/sec), and broadcasts emergency DDS alert commands.",
        security: "IEC 62443 Zone 3 - Zero-Trust Security Token Verification."
    },
    2: {
        title: "Level 2: Area Control & Magnet Power Supply PLCs",
        file: "DDS Real-time Area Control Zone",
        desc: "Manages deterministic magnet power supply currents, cryogenic liquid helium pumps, and vacuum vessel pressure regulators.",
        security: "IEC 62443 Zone 2 - Deterministic Real-time Control Network."
    },
    1: {
        title: "Level 1: Edge Quench Protection Node (MTCA.4 FPGA)",
        file: "edge_quench/src/main.rs (Rust)",
        desc: "Zero-allocation microsecond safety kernel. Subscribes directly to high-frequency FOAS acoustic sensing (>25 kHz) and stray capacitance (dC/dt) streams. Triggers fast discharge breaker coils in < 50 microseconds!",
        security: "IEC 62443 Level 1 - Direct Hardwired Actuator Safety Zone."
    },
    0: {
        title: "Level 0: Physical Stellarator Hardware & Sensors",
        file: "REBCO HTS Coils & FOAS Strain Fiber Cables",
        desc: "Physical quasi-isodynamic stellarator magnet coils carrying >10,000A electric current at 20 Kelvin. Embedded fiber-optic strain cables and capacitive diagnostic tiles.",
        security: "Physical Equipment Zone."
    }
};

function initPurdueInspector() {
    const purdueCards = document.querySelectorAll('.purdue-card');
    const titleEl = document.getElementById('inspector-title');
    const bodyEl = document.getElementById('inspector-body');

    purdueCards.forEach(card => {
        card.addEventListener('click', () => {
            purdueCards.forEach(c => c.classList.remove('active-layer'));
            card.classList.add('active-layer');

            const level = card.getAttribute('data-level');
            const info = PURDUE_DATA[level];

            titleEl.textContent = info.title;
            bodyEl.innerHTML = `
                <p><strong>Primary Implementation:</strong> <code>${info.file}</code></p>
                <p><strong>Functional Description:</strong> ${info.desc}</p>
                <p><strong>IEC 62443 Safety Boundary:</strong> <span style="color: var(--accent-gold);">${info.security}</span></p>
            `;
        });
    });

    // Select Level 1 by default
    document.querySelector('.purdue-card.level-1').click();
}

/* -------------------------------------------------------------------------- */
/* 4. 3D PINN Stellarator Digital Twin Canvas Renderer                        */
/* -------------------------------------------------------------------------- */
function init3DDigitalTwinCanvas() {
    const canvas = document.getElementById('canvas-3d');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let angle = 0;

    function drawToroidalMesh() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const R0 = 140; // Major radius
        const r0 = 50;  // Minor radius

        angle += 0.015;

        // Draw 3D wireframe torus with QI stellarator helical twist
        for (let u = 0; u < Math.PI * 2; u += Math.PI / 16) {
            ctx.beginPath();
            ctx.strokeStyle = `hsla(${(u * 57.3 + angle * 50) % 360}, 80%, 65%, 0.6)`;
            ctx.lineWidth = 1.5;

            for (let v = 0; v <= Math.PI * 2; v += Math.PI / 32) {
                // Add quasi-isodynamic 3D helical distortion
                const twist = Math.sin(u * 3 + angle);
                const x3d = (R0 + (r0 + twist * 8) * Math.cos(v)) * Math.cos(u + angle * 0.2);
                const y3d = (r0 + twist * 8) * Math.sin(v);
                const z3d = (R0 + (r0 + twist * 8) * Math.cos(v)) * Math.sin(u + angle * 0.2);

                // Simple 3D projection
                const scale = 300 / (300 + z3d);
                const projX = centerX + x3d * scale;
                const projY = centerY + y3d * scale;

                if (v === 0) ctx.moveTo(projX, projY);
                else ctx.lineTo(projX, projY);
            }
            ctx.stroke();
        }

        requestAnimationFrame(drawToroidalMesh);
    }

    drawToroidalMesh();
}

/* -------------------------------------------------------------------------- */
/* 5. Fetch TUTORIAL.md & Initialize Mermaid Diagrams                        */
/* -------------------------------------------------------------------------- */
function initMarkdownTutorial() {
    const viewer = document.getElementById('markdown-viewer');
    if (!viewer) return;

    fetch('/TUTORIAL.md')
        .then(res => {
            if (!res.ok) throw new Error('Local tutorial markdown file');
            return res.text();
        })
        .then(md => {
            viewer.innerHTML = parseMarkdownToHTML(md);
            renderMermaidDiagrams();
        })
        .catch(err => {
            // Fallback content if standalone page load
            viewer.innerHTML = `
                <h2>📖 Beginner's Tutorial Loaded</h2>
                <p>Welcome to the SKHY TAMI Architecture Tutorial. For full offline reading, inspect the <a href="/TUTORIAL.md" target="_blank">TUTORIAL.md</a> file in the root directory.</p>
                <blockquote>All fusion physics concepts are sourced from <a href="https://www.fusionenergybase.com/articles?tag=physics" target="_blank">Fusion Energy Base</a>.</blockquote>
            `;
        });
}

function parseMarkdownToHTML(md) {
    let html = md
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
        .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
        .replace(/\*(.*)\*/gim, '<em>$1</em>')
        .replace(/`([^`]+)`/gim, '<code>$1</code>')
        .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" target="_blank">$1</a>')
        .replace(/\n\n/gim, '<br>');

    // Convert ```mermaid block to <pre class="mermaid">
    html = html.replace(/```mermaid\n([\s\S]*?)\n```/gim, '<pre class="mermaid">$1</pre>');
    return html;
}

function renderMermaidDiagrams() {
    if (window.mermaid) {
        try {
            mermaid.initialize({
                startOnLoad: false,
                theme: 'dark',
                securityLevel: 'loose',
                themeVariables: {
                    primaryColor: '#121826',
                    primaryTextColor: '#F0F4F8',
                    primaryBorderColor: '#00F2FE',
                    lineColor: '#00F2FE',
                    secondaryColor: '#1A2234',
                    tertiaryColor: '#0A0D14'
                }
            });
            // Re-render any unrendered mermaid elements
            const mermaidEls = document.querySelectorAll('.mermaid');
            mermaidEls.forEach((el, idx) => {
                // If not already processed into svg
                if (!el.getAttribute('data-processed')) {
                    el.setAttribute('id', `mermaid-diagram-${idx}-${Date.now()}`);
                    try {
                        mermaid.init(undefined, el);
                        el.setAttribute('data-processed', 'true');
                    } catch (err) {
                        console.log("Mermaid init note:", err);
                    }
                }
            });
        } catch (e) {
            console.log("Mermaid global note:", e);
        }
    }
}

/* -------------------------------------------------------------------------- */
/* 6. Stellarator Subsystems Digital Twin & Feature Modes Engine              */
/* -------------------------------------------------------------------------- */
let activeStellaratorMode = 'MODE_STEADY_STATE_NOMINAL';
let isAutoCycling = false;
let autoCycleTimer = null;
let modeStartTime = Date.now();

const MODE_CYCLE_LIST = [
    'MODE_STARTUP_RAMP',
    'MODE_STEADY_STATE_NOMINAL',
    'MODE_PELLET_REFUELING_BURST',
    'MODE_STEADY_STATE_NOMINAL',
    'MODE_DIVERTOR_DETACHMENT_FAULT',
    'MODE_STEADY_STATE_NOMINAL',
    'MODE_IMPURITY_ACCUMULATION',
    'MODE_HTS_COIL_HOTSPOT_QUENCH'
];
let cycleIdx = 0;

function initSubsystemsTwin() {
    const modeButtons = document.querySelectorAll('.mode-btn');
    const badgeName = document.getElementById('active-mode-name');
    const badgeDot = document.getElementById('active-mode-dot');
    const badgeContainer = document.getElementById('active-mode-badge');

    if (!modeButtons.length) return;

    modeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.getAttribute('data-mode');

            modeButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            if (mode === 'AUTO_CYCLE') {
                isAutoCycling = true;
                cycleIdx = 0;
                setMode(MODE_CYCLE_LIST[0]);
                startAutoCycleTimer();
            } else {
                isAutoCycling = false;
                if (autoCycleTimer) clearInterval(autoCycleTimer);
                setMode(mode);
            }
        });
    });

    function startAutoCycleTimer() {
        if (autoCycleTimer) clearInterval(autoCycleTimer);
        autoCycleTimer = setInterval(() => {
            if (!isAutoCycling) return;
            cycleIdx = (cycleIdx + 1) % MODE_CYCLE_LIST.length;
            const nextMode = MODE_CYCLE_LIST[cycleIdx];
            setMode(nextMode);
        }, 8000);
    }

    function setMode(mode) {
        activeStellaratorMode = mode;
        modeStartTime = Date.now();

        // Update mode status badge
        if (badgeName) badgeName.textContent = `MODE: ${mode.replace('MODE_', '')}`;

        const isAlert = mode.includes('QUENCH') || mode.includes('FAULT') || mode.includes('IMPURITY');
        if (badgeDot) {
            badgeDot.className = `status-indicator-dot ${isAlert ? 'dot-red' : (mode.includes('PELLET') ? 'dot-yellow' : 'dot-green')}`;
        }
        if (badgeContainer) {
            if (isAlert) badgeContainer.classList.add('alert-mode');
            else badgeContainer.classList.remove('alert-mode');
        }

        // Notify backend API if accessible
        try {
            fetch(`/api/v1/mode/set/${mode}`, { method: 'POST' }).catch(() => {});
        } catch (e) {}

        // Immediate UI refresh
        updateSubsystemUI();
    }

    // Set up continuous 500ms physics update loop
    setInterval(() => {
        // Try fetching live telemetry from Data Lake API first
        fetch('/api/v1/subsystems/latest')
            .then(res => {
                if (!res.ok) throw new Error('API not streaming yet');
                return res.json();
            })
            .then(data => {
                applyTelemetryDataToUI(data);
            })
            .catch(() => {
                // Client-side high-fidelity fallback simulation
                updateSubsystemUI();
            });
    }, 600);
}

function updateSubsystemUI() {
    const elapsedSec = (Date.now() - modeStartTime) / 1000.0;
    const mode = activeStellaratorMode;

    let sub1 = {}, sub2 = {}, sub3 = {}, sub4 = {}, sub5 = {};

    if (mode === 'MODE_STEADY_STATE_NOMINAL') {
        sub1 = {
            temp: (20.0 + (Math.random() - 0.5) * 0.1).toFixed(1) + ' K',
            margin: '72.0 K',
            hePress: '5.20 bar',
            stress: '145.0 MPa',
            icRatio: '0.58',
            icPct: 58,
            status: 'Superconducting State Nominal',
            isAlert: false
        };
        sub2 = {
            temp: '14.8 / 14.2 keV',
            density: '1.85 × 10²⁰ m⁻³',
            tau: '1.65 s',
            lawson: '43.3 keV·s·m⁻³',
            lawsonPct: 87,
            beta: '4.25%',
            status: 'MHD Quiescent Equilibrium',
            isAlert: false
        };
        sub3 = {
            flux: '4.20 MW/m²',
            fluxPct: 42,
            temp: '485.0 °C',
            detach: 'RADIATIVELY DETACHED',
            seeding: '1.45 Pa·m³/s',
            status: 'Divertor Target Safe (<10 MW/m²)',
            isAlert: false
        };
        sub4 = {
            temp: '350.0 / 495.0 °C',
            neutron: '1.85 MW/m²',
            tbr: '1.150 (>1.05 Target)',
            tbrPct: 100,
            tritium: '142.0 g/day',
            flow: '280.0 kg/s',
            status: 'Tritium Self-Sufficiency Sustained',
            isAlert: false
        };
        sub5 = {
            qsci: '10.20',
            pfusion: '255.0 MW',
            pgross: '106.4 MW',
            precirc: '50.2 MW',
            pnet: '+56.2 MW',
            qeng: '2.12',
            qengPct: 71,
            status: 'Surplus Power Exported to Public Grid',
            isAlert: false
        };
    } else if (mode === 'MODE_DIVERTOR_DETACHMENT_FAULT') {
        const surge = Math.min(1.0, elapsedSec / 4.0);
        const heatFlux = 4.2 + 12.6 * surge;
        const targetTemp = 485.0 + 510.0 * surge;

        sub1 = {
            temp: '20.2 K', margin: '71.8 K', hePress: '5.22 bar',
            stress: '146.0 MPa', icRatio: '0.59', icPct: 59,
            status: 'Magnets Nominal', isAlert: false
        };
        sub2 = {
            temp: '14.5 / 13.9 keV', density: '1.80 × 10²⁰ m⁻³', tau: '1.60 s',
            lawson: '40.1 keV·s·m⁻³', lawsonPct: 80, beta: '4.15%',
            status: 'Core Stable | Edge Radiative Dip', isAlert: false
        };
        sub3 = {
            flux: heatFlux.toFixed(2) + ' MW/m²',
            fluxPct: Math.min(100, Math.round((heatFlux / 10.0) * 100)),
            temp: targetTemp.toFixed(1) + ' °C',
            detach: 'ATTACHMENT FAULT (NO RAD)',
            seeding: '0.12 Pa·m³/s (LINE CLOGGED)',
            status: 'THERMAL OVERLOAD ALERT (>10 MW/m²)',
            isAlert: true
        };
        sub4 = {
            temp: '350.0 / 490.0 °C', neutron: '1.80 MW/m²', tbr: '1.140',
            tbrPct: 99, tritium: '138.0 g/day', flow: '280.0 kg/s',
            status: 'Blanket Nominal', isAlert: false
        };
        sub5 = {
            qsci: '9.80', pfusion: '245.0 MW', pgross: '102.6 MW',
            precirc: '50.2 MW', pnet: '+52.4 MW', qeng: '2.04',
            qengPct: 68, status: 'Exporting Power | Divertor Interlock Imminent',
            isAlert: false
        };
    } else if (mode === 'MODE_HTS_COIL_HOTSPOT_QUENCH') {
        const temp = Math.min(105.0, 20.0 + 9.0 * elapsedSec + 1.5 * (elapsedSec ** 2));
        const margin = Math.max(0.0, 92.0 - temp);
        const icRatio = Math.min(1.45, 0.58 + 0.15 * elapsedSec);

        sub1 = {
            temp: temp.toFixed(1) + ' K',
            margin: margin.toFixed(1) + ' K',
            hePress: (5.2 + 2.1 * elapsedSec).toFixed(2) + ' bar',
            stress: Math.min(320.0, 145.0 + 25.0 * elapsedSec).toFixed(1) + ' MPa',
            icRatio: icRatio.toFixed(2),
            icPct: Math.min(100, Math.round(icRatio * 100)),
            status: 'EMERGENCY QUENCH INTERLOCK ACTIVATED',
            isAlert: true
        };
        sub2 = {
            temp: '2.5 / 2.2 keV', density: '0.45 × 10²⁰ m⁻³', tau: '0.15 s',
            lawson: '0.15 keV·s·m⁻³', lawsonPct: 3, beta: '0.20%',
            status: 'Plasma Quenched / Extinguished', isAlert: true
        };
        sub3 = {
            flux: '0.50 MW/m²', fluxPct: 5, temp: '180.0 °C',
            detach: 'STANDBY', seeding: '0.00 Pa·m³/s',
            status: 'Vessel Discharging Safely', isAlert: false
        };
        sub4 = {
            temp: '300.0 / 310.0 °C', neutron: '0.00 MW/m²', tbr: '0.000',
            tbrPct: 0, tritium: '0.0 g/day', flow: '50.0 kg/s',
            status: 'Neutron Production Stopped', isAlert: false
        };
        sub5 = {
            qsci: '0.00', pfusion: '0.0 MW', pgross: '1.9 MW',
            precirc: '22.8 MW', pnet: '-20.9 MW (DEFICIT)', qeng: '0.08',
            qengPct: 8, status: 'Drawing Grid Power for Fast Breakers',
            isAlert: true
        };
    } else if (mode === 'MODE_PELLET_REFUELING_BURST') {
        const wave = Math.sin(Math.min(Math.PI, elapsedSec * 0.8));
        const dens = 1.85 + 1.35 * wave;
        const qsci = 10.2 + 6.3 * wave;
        const pfusion = qsci * 25.0;
        const pgross = (pfusion + 25.0) * 0.38;
        const pnet = pgross - 50.2;

        sub1 = {
            temp: '20.0 K', margin: '72.0 K', hePress: '5.20 bar',
            stress: '152.0 MPa', icRatio: '0.60', icPct: 60,
            status: 'Magnets Rigid & Stable', isAlert: false
        };
        sub2 = {
            temp: (14.8 - 2.8 * wave).toFixed(1) + ' / ' + (14.2 - 2.2 * wave).toFixed(1) + ' keV',
            density: dens.toFixed(2) + ' × 10²⁰ m⁻³',
            tau: '1.92 s', lawson: (dens * 12.0 * 1.92).toFixed(1) + ' keV·s·m⁻³',
            lawsonPct: 100, beta: '5.65%',
            status: 'Pellet Wave Alpha Heating Burst', isAlert: false
        };
        sub3 = {
            flux: '5.80 MW/m²', fluxPct: 58, temp: '535.0 °C',
            detach: 'RADIATIVELY DETACHED', seeding: '2.10 Pa·m³/s',
            status: 'SOL Density High | Well Shielded', isAlert: false
        };
        sub4 = {
            temp: '350.0 / 530.0 °C', neutron: (1.85 * (pfusion / 255.0)).toFixed(2) + ' MW/m²',
            tbr: '1.180', tbrPct: 100, tritium: (142.0 * (pfusion / 255.0)).toFixed(1) + ' g/day',
            flow: '280.0 kg/s', status: 'Tritium Harvest Surging (+25%)', isAlert: false
        };
        sub5 = {
            qsci: qsci.toFixed(2), pfusion: pfusion.toFixed(1) + ' MW',
            pgross: pgross.toFixed(1) + ' MW', precirc: '50.2 MW',
            pnet: '+' + pnet.toFixed(1) + ' MW', qeng: (pgross / 50.2).toFixed(2),
            qengPct: 95, status: 'Peak Grid Power Generation Wave', isAlert: false
        };
    } else if (mode === 'MODE_IMPURITY_ACCUMULATION') {
        const decay = Math.min(1.0, elapsedSec / 8.0);
        const te = Math.max(3.5, 14.8 - 11.3 * decay);
        const qsci = Math.max(0.8, 10.2 - 8.4 * decay);
        const pfusion = qsci * 25.0;
        const pgross = (pfusion + 25.0) * 0.38;
        const pnet = pgross - 50.2;

        sub1 = {
            temp: '20.0 K', margin: '72.0 K', hePress: '5.20 bar',
            stress: '144.0 MPa', icRatio: '0.58', icPct: 58,
            status: 'Cryo Coils Unaffected', isAlert: false
        };
        sub2 = {
            temp: te.toFixed(1) + ' / 3.8 keV', density: '0.90 × 10²⁰ m⁻³',
            tau: '0.40 s', lawson: '1.3 keV·s·m⁻³', lawsonPct: 15, beta: '1.10%',
            status: 'Tungsten Core Radiative Collapse', isAlert: true
        };
        sub3 = {
            flux: '1.50 MW/m²', fluxPct: 15, temp: '260.0 °C',
            detach: 'DETACHED (COLD)', seeding: '0.50 Pa·m³/s',
            status: 'Core Cooling Inward', isAlert: false
        };
        sub4 = {
            temp: '320.0 / 340.0 °C', neutron: '0.30 MW/m²', tbr: '0.350',
            tbrPct: 35, tritium: '25.0 g/day', flow: '280.0 kg/s',
            status: 'Tritium Sub-Breakeven Warning', isAlert: true
        };
        sub5 = {
            qsci: qsci.toFixed(2), pfusion: pfusion.toFixed(1) + ' MW',
            pgross: pgross.toFixed(1) + ' MW', precirc: '50.2 MW',
            pnet: (pnet >= 0 ? '+' : '') + pnet.toFixed(1) + ' MW',
            qeng: (pgross / 50.2).toFixed(2), qengPct: Math.max(5, Math.round((pgross / 50.2) * 35)),
            status: pnet < 0 ? 'GRID DEFICIT (DRAWING POWER)' : 'Degraded Gain',
            isAlert: pnet < 0
        };
    } else if (mode === 'MODE_STARTUP_RAMP') {
        const ramp = Math.min(1.0, elapsedSec / 10.0);
        const qsci = 0.2 + 10.0 * ramp;
        const pfusion = qsci * (5.0 + 20.0 * ramp);
        const pheat = 5.0 + 20.0 * ramp;
        const pgross = (pfusion + pheat) * 0.38;
        const precirc = pheat / 0.60 + 8.5;
        const pnet = pgross - precirc;

        sub1 = {
            temp: (18.5 + 1.5 * ramp).toFixed(1) + ' K', margin: '72.0 K',
            hePress: '5.20 bar', stress: (20.0 + 125.0 * ramp).toFixed(1) + ' MPa',
            icRatio: (0.10 + 0.48 * ramp).toFixed(2),
            icPct: Math.round((0.10 + 0.48 * ramp) * 100),
            status: 'Energizing Magnet Coils (0 -> 5.5T)', isAlert: false
        };
        sub2 = {
            temp: (1.0 + 13.8 * ramp).toFixed(1) + ' / ' + (0.8 + 13.4 * ramp).toFixed(1) + ' keV',
            density: (0.20 + 1.65 * ramp).toFixed(2) + ' × 10²⁰ m⁻³',
            tau: (0.30 + 1.35 * ramp).toFixed(2) + ' s',
            lawson: ((0.20 + 1.65 * ramp) * (0.8 + 13.4 * ramp) * (0.30 + 1.35 * ramp)).toFixed(1) + ' keV·s·m⁻³',
            lawsonPct: Math.round(ramp * 87), beta: (0.50 + 3.75 * ramp).toFixed(2) + '%',
            status: 'ECRH Gyrotron Microwave Ionization', isAlert: false
        };
        sub3 = {
            flux: (0.50 + 3.70 * ramp).toFixed(2) + ' MW/m²', fluxPct: Math.round((0.50 + 3.70 * ramp) * 10),
            temp: (150.0 + 335.0 * ramp).toFixed(1) + ' °C',
            detach: 'DETACHING REGIME', seeding: (0.2 + 1.25 * ramp).toFixed(2) + ' Pa·m³/s',
            status: 'Establishing Radiative Boundary', isAlert: false
        };
        sub4 = {
            temp: '350.0 / ' + (350.0 + 145.0 * ramp).toFixed(1) + ' °C',
            neutron: (1.85 * ramp).toFixed(2) + ' MW/m²',
            tbr: (0.10 + 1.05 * ramp).toFixed(3),
            tbrPct: Math.round((0.10 + 1.05 * ramp) * 100),
            tritium: (142.0 * ramp).toFixed(1) + ' g/day',
            flow: '280.0 kg/s', status: 'Heating PbLi Primary Loop', isAlert: false
        };
        sub5 = {
            qsci: qsci.toFixed(2), pfusion: pfusion.toFixed(1) + ' MW',
            pgross: pgross.toFixed(1) + ' MW', precirc: precirc.toFixed(1) + ' MW',
            pnet: (pnet >= 0 ? '+' : '') + pnet.toFixed(1) + ' MW',
            qeng: (pgross / precirc).toFixed(2),
            qengPct: Math.min(100, Math.round((pgross / precirc) * 50)),
            status: ramp < 0.85 ? 'Auxiliary Power Inflow' : 'Breakeven Achieved!',
            isAlert: pnet < 0
        };
    }

    renderSubsystemValues(sub1, sub2, sub3, sub4, sub5);
}

function applyTelemetryDataToUI(data) {
    if (!data || !data.coil_cryo) return;

    const sub1 = {
        temp: `${data.coil_cryo.coil_temperature_k} K`,
        margin: `${data.coil_cryo.quench_margin_k} K`,
        hePress: `${data.coil_cryo.helium_pressure_bar} bar`,
        stress: `${data.coil_cryo.peak_coil_stress_mpa} MPa`,
        icRatio: `${data.coil_cryo.critical_current_ratio}`,
        icPct: Math.min(100, Math.round(data.coil_cryo.critical_current_ratio * 100)),
        status: data.coil_cryo.quench_warning ? 'EMERGENCY QUENCH INTERLOCK ACTIVATED' : 'Superconducting State Nominal',
        isAlert: data.coil_cryo.quench_warning
    };

    const sub2 = {
        temp: `${data.plasma_core.electron_temp_kev} / ${data.plasma_core.ion_temp_kev} keV`,
        density: `${data.plasma_core.electron_density_1e20_m3} × 10²⁰ m⁻³`,
        tau: `${data.plasma_core.energy_confinement_tau_s} s`,
        lawson: `${data.plasma_core.lawson_triple_product_kev_s_m3} keV·s·m⁻³`,
        lawsonPct: Math.min(100, Math.round((data.plasma_core.lawson_triple_product_kev_s_m3 / 50.0) * 100)),
        beta: `${data.plasma_core.toroidal_beta_percent}%`,
        status: data.plasma_core.mhd_quiescent ? 'MHD Quiescent Equilibrium' : 'Plasma Confinement Degraded',
        isAlert: !data.plasma_core.mhd_quiescent
    };

    const sub3 = {
        flux: `${data.divertor.peak_heat_flux_mw_per_m2} MW/m²`,
        fluxPct: Math.min(100, Math.round((data.divertor.peak_heat_flux_mw_per_m2 / 10.0) * 100)),
        temp: `${data.divertor.target_surface_temp_c} °C`,
        detach: data.divertor.detachment_achieved ? 'RADIATIVELY DETACHED' : 'ATTACHMENT FAULT (NO RAD)',
        seeding: `${data.divertor.impurity_seeding_rate_pa_m3_s} Pa·m³/s`,
        status: data.divertor.thermal_overload_alert ? 'THERMAL OVERLOAD ALERT (>10 MW/m²)' : 'Divertor Target Safe (<10 MW/m²)',
        isAlert: data.divertor.thermal_overload_alert
    };

    const sub4 = {
        temp: `${data.blanket.pb_li_inlet_temp_c} / ${data.blanket.pb_li_outlet_temp_c} °C`,
        neutron: `${data.blanket.neutron_wall_load_mw_per_m2} MW/m²`,
        tbr: `${data.blanket.tritium_breeding_ratio} (>1.05 Target)`,
        tbrPct: Math.min(100, Math.round((data.blanket.tritium_breeding_ratio / 1.15) * 100)),
        tritium: `${data.blanket.tritium_extraction_rate_g_per_day} g/day`,
        flow: `${data.blanket.coolant_flow_rate_kg_s} kg/s`,
        status: data.blanket.tritium_breeding_ratio >= 1.05 ? 'Tritium Self-Sufficiency Sustained' : 'Tritium Sub-Breakeven Warning',
        isAlert: data.blanket.tritium_breeding_ratio < 1.05
    };

    const sub5 = {
        qsci: `${data.power_balance.scientific_gain_q_sci}`,
        pfusion: `${data.power_balance.fusion_power_mw} MW`,
        pgross: `${data.power_balance.gross_electric_power_mw} MW`,
        precirc: `${data.power_balance.recirculating_power_mw} MW`,
        pnet: `${data.power_balance.net_electric_power_mw > 0 ? '+' : ''}${data.power_balance.net_electric_power_mw} MW`,
        qeng: `${data.power_balance.engineering_gain_q_eng}`,
        qengPct: Math.min(100, Math.round((data.power_balance.engineering_gain_q_eng / 3.0) * 100)),
        status: data.power_balance.net_electricity_achieved ? 'Surplus Power Exported to Public Grid' : 'GRID DEFICIT (DRAWING POWER)',
        isAlert: !data.power_balance.net_electricity_achieved
    };

    renderSubsystemValues(sub1, sub2, sub3, sub4, sub5);
}

function renderSubsystemValues(sub1, sub2, sub3, sub4, sub5) {
    // 1. Coil
    setEl('sub1-temp', sub1.temp);
    setEl('sub1-margin', sub1.margin);
    setEl('sub1-he-press', sub1.hePress);
    setEl('sub1-stress', sub1.stress);
    setEl('sub1-ic-ratio', sub1.icRatio);
    setEl('sub1-ic-pct', `${sub1.icPct}%`);
    setEl('sub1-status', sub1.status);
    setBar('sub1-ic-bar', sub1.icPct, sub1.isAlert ? 'bg-red' : 'bg-cyan');
    setDot('sub1-dot', sub1.isAlert ? 'dot-red' : 'dot-green');

    // 2. Plasma
    setEl('sub2-temp', sub2.temp);
    setEl('sub2-density', sub2.density);
    setEl('sub2-tau', sub2.tau);
    setEl('sub2-lawson', sub2.lawson);
    setEl('sub2-lawson-pct', `${sub2.lawsonPct}%`);
    setEl('sub2-beta', sub2.beta);
    setEl('sub2-status', sub2.status);
    setBar('sub2-lawson-bar', sub2.lawsonPct, sub2.isAlert ? 'bg-red' : 'bg-purple');
    setDot('sub2-dot', sub2.isAlert ? 'dot-red' : 'dot-green');

    // 3. Divertor
    setEl('sub3-flux', sub3.flux);
    setEl('sub3-temp', sub3.temp);
    setEl('sub3-detach', sub3.detach);
    setEl('sub3-seeding', sub3.seeding);
    setEl('sub3-load-pct', `${sub3.fluxPct}%`);
    setEl('sub3-status', sub3.status);
    setBar('sub3-flux-bar', sub3.fluxPct, sub3.isAlert ? 'bg-red' : 'bg-green');
    setDot('sub3-dot', sub3.isAlert ? 'dot-red' : 'dot-green');

    // 4. Blanket
    setEl('sub4-temp', sub4.temp);
    setEl('sub4-neutron', sub4.neutron);
    setEl('sub4-tbr', sub4.tbr);
    setEl('sub4-tritium', sub4.tritium);
    setEl('sub4-flow', sub4.flow);
    setEl('sub4-tbr-pct', `${sub4.tbrPct}%`);
    setEl('sub4-status', sub4.status);
    setBar('sub4-tbr-bar', sub4.tbrPct, sub4.isAlert ? 'bg-red' : 'bg-green');
    setDot('sub4-dot', sub4.isAlert ? 'dot-red' : 'dot-green');

    // 5. Power Balance
    setEl('sub5-qsci', sub5.qsci);
    setEl('sub5-pfusion', sub5.pfusion);
    setEl('sub5-pgross', sub5.pgross);
    setEl('sub5-precirc', sub5.precirc);
    setEl('sub5-pnet', sub5.pnet);
    setEl('sub5-qeng', sub5.qeng);
    setEl('sub5-qeng-bar', `${sub5.qengPct}%`);
    setEl('sub5-status', sub5.status);
    setBar('sub5-qeng-bar', sub5.qengPct, sub5.isAlert ? 'bg-red' : 'bg-gold');
    setDot('sub5-dot', sub5.isAlert ? 'dot-red' : 'dot-green');
}

function setEl(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function setBar(id, pct, bgClass) {
    const el = document.getElementById(id);
    if (el) {
        el.style.width = `${Math.min(100, Math.max(0, pct))}%`;
        el.className = `gauge-bar-fill ${bgClass}`;
    }
}

function setDot(id, dotClass) {
    const el = document.getElementById(id);
    if (el) el.className = `status-indicator-dot ${dotClass}`;
}

