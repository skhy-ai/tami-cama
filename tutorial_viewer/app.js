// Proxima Fusion - TAMI Interactive Tutorial Viewer Engine

document.addEventListener('DOMContentLoaded', () => {
    initTabNavigation();
    initQuenchSimulator();
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
            document.getElementById(targetTab).classList.add('active');

            if (targetTab === 'guide-doc') {
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
                <p>Welcome to the Proxima Fusion TAMI Architecture Tutorial. For full offline reading, inspect the <a href="/TUTORIAL.md" target="_blank">TUTORIAL.md</a> file in the root directory.</p>
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
                startOnLoad: true,
                theme: 'dark',
                securityLevel: 'loose'
            });
            mermaid.init(undefined, document.querySelectorAll('.mermaid'));
        } catch (e) {
            console.log("Mermaid render note:", e);
        }
    }
}
