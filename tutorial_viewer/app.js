// SKHY - TAMI Multi-Reactor Digital Twin, 2D Energy Diagram & Tutorial Engine
// Supports QI Stellarator, Advanced Tokamak, and Inertial Confinement Fusion (ICF)

document.addEventListener('DOMContentLoaded', () => {
    initReactorSelector();
    initTabNavigation();
    initQuenchSimulator();
    initSubsystemsTwin();
    init2DSankeySimulator();
    initPurdueInspector();
    init3DMultiReactorStudio();
    initSyntheticCockpit();
    initMarkdownTutorial();
});

/* ========================================================================== */
/* 0. Global Fusion Reactor Architecture State                                */
/* ========================================================================== */
let activeReactor = 'REACTOR_QI_STELLARATOR';
let activeMode = 'MODE_STEADY_STATE_NOMINAL';
let modeStartTime = Date.now();
let isAutoCycling = false;
let autoCycleTimer = null;
let cycleIdx = 0;

const REACTOR_MODES = {
    'REACTOR_QI_STELLARATOR': [
        { id: 'MODE_STEADY_STATE_NOMINAL', icon: '🟢', name: 'Steady-State Nominal', type: 'nominal' },
        { id: 'MODE_DIVERTOR_DETACHMENT_FAULT', icon: '🔥', name: 'Divertor Detachment Fault', type: 'anomaly' },
        { id: 'MODE_HTS_COIL_HOTSPOT_QUENCH', icon: '⚡', name: 'HTS Coil Hotspot Quench', type: 'critical' },
        { id: 'MODE_PELLET_REFUELING_BURST', icon: '❄️', name: 'Pellet Refueling Burst', type: 'nominal' },
        { id: 'MODE_IMPURITY_ACCUMULATION', icon: '⚠️', name: 'Core Tungsten Collapse', type: 'anomaly' },
        { id: 'MODE_STARTUP_RAMP', icon: '🚀', name: 'Startup Ignition Ramp', type: 'nominal' }
    ],
    'REACTOR_TOKAMAK': [
        { id: 'MODE_TOKAMAK_NOMINAL_BURNTIME', icon: '🟢', name: 'Tokamak Flattop Burn (Ip=15MA)', type: 'nominal' },
        { id: 'MODE_TOKAMAK_MAJOR_DISRUPTION', icon: '⚡', name: 'Major Disruption & Quench', type: 'critical' },
        { id: 'MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT', icon: '↕️', name: 'Vertical Displacement (VDE)', type: 'critical' },
        { id: 'MODE_TOKAMAK_UNMITIGATED_ELM_BURST', icon: '💥', name: 'Type-I ELM Burst (Pedestal)', type: 'anomaly' },
        { id: 'MODE_TOKAMAK_RUNAWAY_ELECTRON_AVALANCHE', icon: '☢️', name: 'Runaway Electron Beam (3.8MA)', type: 'critical' },
        { id: 'MODE_TOKAMAK_NEOCLASSICAL_TEARING_MODE', icon: '🌀', name: '2/1 NTM Magnetic Island', type: 'anomaly' }
    ],
    'REACTOR_ICF': [
        { id: 'MODE_ICF_NOMINAL_REPETITION_PULSE', icon: '🟢', name: '5Hz Repetition Pulse (G=85)', type: 'nominal' },
        { id: 'MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY', icon: '🌊', name: 'Rayleigh-Taylor Mix Fingers', type: 'critical' },
        { id: 'MODE_ICF_LASER_POWER_IMBALANCE_JITTER', icon: '🎯', name: 'Laser Beam Timing Jitter (>35ps)', type: 'anomaly' },
        { id: 'MODE_ICF_FINAL_OPTICS_DEBRIS_DAMAGE', icon: '🛡️', name: 'Final Optics Debris Degradation', type: 'anomaly' },
        { id: 'MODE_ICF_TARGET_TRACKING_INJECTION_MISS', icon: '❌', name: 'Target Tracking Miss (>40μm)', type: 'critical' },
        { id: 'MODE_ICF_CHAMBER_CLEARING_PRESSURE_CHOKE', icon: '💨', name: 'Chamber Vapor Pressure Choke', type: 'anomaly' }
    ]
};

function initReactorSelector() {
    const reactorBtns = document.querySelectorAll('.reactor-btn');
    const pillText = document.getElementById('active-reactor-pill-text');

    reactorBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const reactorId = btn.getAttribute('data-reactor');
            if (reactorId === activeReactor) return;

            reactorBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            activeReactor = reactorId;
            const defaultMode = REACTOR_MODES[reactorId][0].id;
            activeMode = defaultMode;
            modeStartTime = Date.now();

            const reactorNames = {
                'REACTOR_QI_STELLARATOR': 'QI Modular Stellarator Active',
                'REACTOR_TOKAMAK': 'Advanced Tokamak Active (Ip=15 MA)',
                'REACTOR_ICF': 'Inertial Confinement (ICF) Active (5 Hz)'
            };
            if (pillText) pillText.textContent = reactorNames[reactorId] || 'Reactor Active';

            // Post to backend API
            try {
                fetch(`/api/v1/reactor/set/${reactorId}`, { method: 'POST' }).catch(() => {});
            } catch (e) {}

            // Rebuild Mode Selector Strip
            buildModeSelectorStrip();

            // Switch 3D Model
            switch3DReactorModel(reactorId);

            // Update Sankey Defaults
            syncSankeyToReactor(reactorId);

            // Update Subsystem UI immediately
            updateSubsystemUI();
        });
    });

    buildModeSelectorStrip();
}

function buildModeSelectorStrip() {
    const container = document.querySelector('.mode-buttons-strip');
    if (!container) return;

    container.innerHTML = '';
    const modes = REACTOR_MODES[activeReactor] || REACTOR_MODES['REACTOR_QI_STELLARATOR'];

    modes.forEach((m, idx) => {
        const btn = document.createElement('button');
        btn.className = `mode-btn ${idx === 0 ? 'active' : ''} ${m.type === 'critical' ? 'btn-mode-quench' : (m.type === 'anomaly' ? 'btn-mode-div' : '')}`;
        btn.setAttribute('data-mode', m.id);
        btn.innerHTML = `<span>${m.icon}</span> ${m.name}`;

        btn.addEventListener('click', () => {
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            isAutoCycling = false;
            if (autoCycleTimer) clearInterval(autoCycleTimer);
            setOperationalMode(m.id);
        });

        container.appendChild(btn);
    });

    // Add Auto-Cycle Demo Button
    const autoBtn = document.createElement('button');
    autoBtn.className = 'mode-btn';
    autoBtn.setAttribute('data-mode', 'AUTO_CYCLE');
    autoBtn.innerHTML = `<span>🔄</span> Auto-Cycle Demo`;
    autoBtn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        autoBtn.classList.add('active');
        isAutoCycling = true;
        cycleIdx = 0;
        setOperationalMode(modes[0].id);
        startAutoCycle();
    });
    container.appendChild(autoBtn);
}

function startAutoCycle() {
    if (autoCycleTimer) clearInterval(autoCycleTimer);
    const modes = REACTOR_MODES[activeReactor] || REACTOR_MODES['REACTOR_QI_STELLARATOR'];
    autoCycleTimer = setInterval(() => {
        if (!isAutoCycling) return;
        cycleIdx = (cycleIdx + 1) % modes.length;
        setOperationalMode(modes[cycleIdx].id);
    }, 7000);
}

function setOperationalMode(modeId) {
    activeMode = modeId;
    modeStartTime = Date.now();

    const badgeName = document.getElementById('active-mode-name');
    const badgeDot = document.getElementById('active-mode-dot');
    const badgeContainer = document.getElementById('active-mode-badge');

    if (badgeName) badgeName.textContent = `MODE: ${modeId.replace('MODE_', '').replace('TOKAMAK_', '').replace('ICF_', '')}`;

    const isCritical = modeId.includes('DISRUPTION') || modeId.includes('QUENCH') || modeId.includes('TAYLOR') || modeId.includes('AVALANCHE') || modeId.includes('MISS');
    const isAnomaly = modeId.includes('FAULT') || modeId.includes('ELM') || modeId.includes('JITTER') || modeId.includes('DAMAGE') || modeId.includes('IMPURITY') || modeId.includes('CHOKE');

    if (badgeDot) {
        badgeDot.className = `status-indicator-dot ${isCritical ? 'dot-red' : (isAnomaly ? 'dot-yellow' : 'dot-green')}`;
    }
    if (badgeContainer) {
        if (isCritical || isAnomaly) badgeContainer.classList.add('alert-mode');
        else badgeContainer.classList.remove('alert-mode');
    }

    // Update 3D Alert Banner
    update3DAlertBanner(modeId, isCritical || isAnomaly);

    // Notify backend
    try {
        fetch(`/api/v1/mode/set/${modeId}`, { method: 'POST' }).catch(() => {});
    } catch (e) {}

    updateSubsystemUI();
    updateDynamicStateMachine();
}

/* ========================================================================== */
/* 1. Tab Navigation System                                                  */
/* ========================================================================== */
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

            if (targetTab === 'guide-doc') {
                renderMermaidDiagrams();
                renderMathFormulas();
            } else if (targetTab === 'power-balance') {
                renderSankeyDiagram();
            } else if (targetTab === 'digital-twin-studio' || targetTab === 'pinn-twin' || targetTab === 'subsystems-twin') {
                onWindowResize3D();
                updateDynamicStateMachine();
            }
        });
    });
}

/* ========================================================================== */
/* 2. Interactive REBCO Quench & Edge Interlock Simulator                    */
/* ========================================================================== */
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

    if (!tempSlider) return;

    function updateSimulation() {
        const temp = parseFloat(tempSlider.value);
        const foas = parseFloat(foasSlider.value);
        const cap = parseFloat(capSlider.value);

        tempVal.textContent = `${temp.toFixed(1)} K`;
        foasVal.textContent = `${Math.round(foas).toLocaleString()} Hz`;
        capVal.textContent = `${cap.toFixed(1)} pF/s`;

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

function renderWaveform(freqHz, isQuench) {
    const canvas = document.getElementById('waveform-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

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

/* ========================================================================== */
/* 2b. Live Synthetic Ingestion Cockpit & Adaptive Precursor Waveforms        */
/* ========================================================================== */
let waveBuffer1 = Array(45).fill(0);
let waveBuffer2 = Array(45).fill(0);
let waveBuffer3 = Array(45).fill(0);
let seqCounter = 10482;
let streamFreq = 10;
let lastTripTime = 0;
let tripsLog = [];
let isTimelineOpen = false;

function initSyntheticCockpit() {
    // Frequency buttons
    document.querySelectorAll('.freq-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.freq-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            streamFreq = parseInt(btn.getAttribute('data-freq') || '10', 10);
            const rateEl = document.getElementById('cockpit-packet-rate');
            if (rateEl) rateEl.textContent = `RATE: ${streamFreq}.0 Hz`;
        });
    });

    // Inject Anomaly Button
    const injectBtn = document.getElementById('btn-inject-anomaly');
    if (injectBtn) {
        injectBtn.addEventListener('click', () => {
            let anomalyMode = 'MODE_HTS_COIL_HOTSPOT_QUENCH';
            if (activeReactor === 'REACTOR_TOKAMAK') anomalyMode = 'MODE_TOKAMAK_MAJOR_DISRUPTION';
            else if (activeReactor === 'REACTOR_ICF') anomalyMode = 'MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY';
            setOperationalMode(anomalyMode);
        });
    }

    // Toggle Timeline Button
    const toggleBtn = document.getElementById('btn-toggle-timeline');
    const timelineEl = document.getElementById('cockpit-event-timeline');
    const toggleIcon = document.getElementById('timeline-toggle-icon');
    if (toggleBtn && timelineEl) {
        toggleBtn.addEventListener('click', () => {
            isTimelineOpen = !isTimelineOpen;
            timelineEl.style.display = isTimelineOpen ? 'block' : 'none';
            if (toggleIcon) toggleIcon.textContent = isTimelineOpen ? '▲' : '▼';
        });
    }

    // Clear Timeline Button
    const clearBtn = document.getElementById('btn-clear-timeline');
    if (clearBtn) {
        clearBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            tripsLog = [];
            renderTimelineEntries();
        });
    }
}

function updateAdaptiveWaveforms(val1, val2, val3, str1, str2, str3) {
    seqCounter += Math.floor(streamFreq / 2) || 1;
    const seqEl = document.getElementById('cockpit-seq-counter');
    if (seqEl) seqEl.textContent = `SEQ #${seqCounter.toLocaleString()}`;

    // Topology specific channel titles & trip limits
    let t1, t2, t3, thresh1, thresh2, thresh3, unit1, unit2, unit3;

    if (activeReactor === 'REACTOR_TOKAMAK') {
        t1 = 'Channel 1: Inductive Loop Voltage (V_loop)';
        t2 = 'Channel 2: Locked-Mode Perturbation (dB/dt)';
        t3 = 'Channel 3: Divertor Peak Heat Flux';
        thresh1 = 100.0; thresh2 = 50.0; thresh3 = 10.0;
        unit1 = 'Central Solenoid Induced'; unit2 = 'Pick-up Mirnov Coils'; unit3 = 'Tungsten Target Plate';
    } else if (activeReactor === 'REACTOR_ICF') {
        t1 = 'Channel 1: Laser Pulse Timing Jitter';
        t2 = 'Channel 2: Pellet Injection Displacement';
        t3 = 'Channel 3: Rayleigh-Taylor Mix RMS';
        thresh1 = 35.0; thresh2 = 40.0; thresh3 = 3.0;
        unit1 = 'Optical Delay Line (ps)'; unit2 = 'Target Chamber Offset (µm)'; unit3 = 'Hotspot Instability (%)';
    } else {
        t1 = 'Channel 1: FOAS Acoustic Emission';
        t2 = 'Channel 2: Capacitance Shift Rate (dC/dt)';
        t3 = 'Channel 3: Localized Hotspot Temp';
        thresh1 = 25.0; thresh2 = 15.0; thresh3 = 92.0;
        unit1 = 'Ultrasonic Acoustic (dB)'; unit2 = 'Stray Dielectric (pF/s)'; unit3 = 'REBCO HTS Critical (K)';
    }

    setEl('wave-1-title', t1);
    setEl('wave-2-title', t2);
    setEl('wave-3-title', t3);
    setEl('wave-1-val', str1);
    setEl('wave-2-val', str2);
    setEl('wave-3-val', str3);
    setEl('wave-1-thresh', `Trip Threshold: > ${thresh1.toFixed(1)}`);
    setEl('wave-2-thresh', `Trip Threshold: > ${thresh2.toFixed(1)}`);
    setEl('wave-3-thresh', `Trip Threshold: > ${thresh3.toFixed(1)}`);
    setEl('wave-1-unit', unit1);
    setEl('wave-2-unit', unit2);
    setEl('wave-3-unit', unit3);

    // Push to ring buffers
    waveBuffer1.push(val1); if (waveBuffer1.length > 45) waveBuffer1.shift();
    waveBuffer2.push(val2); if (waveBuffer2.length > 45) waveBuffer2.shift();
    waveBuffer3.push(val3); if (waveBuffer3.length > 45) waveBuffer3.shift();

    // Render 3 sparkline canvases
    drawSparkline('canvas-wave-1', waveBuffer1, thresh1, '#00F2FE');
    drawSparkline('canvas-wave-2', waveBuffer2, thresh2, '#A855F7');
    drawSparkline('canvas-wave-3', waveBuffer3, thresh3, '#F59E0B');

    // Trip detection check
    const isTripped = (val1 > thresh1) || (val2 > thresh2) || (val3 > thresh3);
    const now = Date.now();
    if (isTripped && (now - lastTripTime > 3500)) {
        lastTripTime = now;
        logInterlockTrip(val1, val2, val3, thresh1, thresh2, thresh3);
    }
}

function drawSparkline(canvasId, buffer, threshold, baseColor) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Background grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h * 0.33); ctx.lineTo(w, h * 0.33);
    ctx.moveTo(0, h * 0.66); ctx.lineTo(w, h * 0.66);
    ctx.stroke();

    // Scale calculation
    const maxVal = Math.max(threshold * 1.35, Math.max(...buffer, 1.0));
    const threshY = h - (threshold / maxVal) * (h - 8);

    // Draw red threshold dashed line
    ctx.strokeStyle = 'rgba(244, 63, 94, 0.65)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, threshY);
    ctx.lineTo(w, threshY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw Waveform curve
    const step = w / (buffer.length - 1);
    ctx.beginPath();
    buffer.forEach((v, idx) => {
        const x = idx * step;
        const y = h - (Math.max(0, v) / maxVal) * (h - 8);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });

    const isCurrentTripped = buffer[buffer.length - 1] > threshold;
    ctx.strokeStyle = isCurrentTripped ? '#FF3366' : baseColor;
    ctx.lineWidth = 2;
    ctx.shadowBlur = isCurrentTripped ? 10 : 4;
    ctx.shadowColor = isCurrentTripped ? '#FF3366' : baseColor;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Fill area under curve
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, isCurrentTripped ? 'rgba(255, 51, 102, 0.25)' : 'rgba(0, 242, 254, 0.15)');
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad;
    ctx.fill();
}

function logInterlockTrip(v1, v2, v3, th1, th2, th3) {
    const d = new Date();
    const timeStr = d.toTimeString().split(' ')[0] + '.' + String(d.getMilliseconds()).padStart(3, '0');
    let evt = 'INTERLOCK TRIP';
    let valStr = '';
    let act = 'Level 1 FPGA Triggered';

    if (activeReactor === 'REACTOR_TOKAMAK') {
        evt = 'MAJOR DISRUPTION PRECURSOR';
        valStr = `Vloop=${v1.toFixed(1)}V, dB/dt=${v2.toFixed(1)}T/s`;
        act = '<2 ms Shattered Pellet Injection (SPI) Neon Active';
    } else if (activeReactor === 'REACTOR_ICF') {
        evt = 'IMPLOSION ASYMMETRY TRIP';
        valStr = `Jitter=${v1.toFixed(1)}ps, Offset=${v2.toFixed(1)}µm`;
        act = '<50 µs Laser Interlock Abort to Calorimeter';
    } else {
        evt = 'HTS COIL QUENCH PRECURSOR';
        valStr = `FOAS=${v1.toFixed(1)}dB, dC/dt=${v2.toFixed(1)}pF/s, T=${v3.toFixed(1)}K`;
        act = '<22 µs Pyrotechnic Breaker Energy Dump Active';
    }

    tripsLog.unshift({
        time: timeStr,
        event: evt,
        val: valStr,
        action: act,
        status: 'MITIGATED'
    });

    if (tripsLog.length > 20) tripsLog.pop();
    renderTimelineEntries();
}

function renderTimelineEntries() {
    const emptyNotice = document.getElementById('timeline-empty-notice');
    const listEl = document.getElementById('timeline-list');
    const badge = document.getElementById('timeline-trip-count');

    if (badge) badge.textContent = `${tripsLog.length} Trips Logged`;

    if (!listEl || !emptyNotice) return;

    if (tripsLog.length === 0) {
        emptyNotice.style.display = 'block';
        listEl.style.display = 'none';
        listEl.innerHTML = '';
        return;
    }

    emptyNotice.style.display = 'none';
    listEl.style.display = 'block';
    listEl.innerHTML = tripsLog.map(t => `
        <div class="timeline-entry">
            <span class="tl-time">${t.time}</span>
            <span class="tl-event">${t.event}</span>
            <span class="tl-val">${t.val}</span>
            <span class="tl-action">${t.action}</span>
            <span class="tl-status">[${t.status}]</span>
        </div>
    `).join('');
}

/* ========================================================================== */
/* 3. Subsystems Digital Twin & Live Telemetry Poller                        */
/* ========================================================================== */
function initSubsystemsTwin() {
    updateDynamicStateMachine();
    setInterval(() => {
        fetch('/api/v1/subsystems/latest')
            .then(res => {
                if (!res.ok) throw new Error('Offline fallback');
                return res.json();
            })
            .then(data => {
                applyTelemetryDataToUI(data);
            })
            .catch(() => {
                updateSubsystemUI();
            });
    }, 600);
}

function updateSubsystemUI() {
    // Generate high-fidelity physics state client-side
    const elapsedSec = (Date.now() - modeStartTime) / 1000.0;
    const reactor = activeReactor;
    const mode = activeMode;

    let sub1 = {}, sub2 = {}, sub3 = {}, sub4 = {}, sub5 = {};

    if (reactor === 'REACTOR_TOKAMAK') {
        let ip = 15.0;
        let q95 = 3.25;
        let vloop = 0.12;
        let flux = 4.8;
        let isCritical = false;

        if (mode === 'MODE_TOKAMAK_MAJOR_DISRUPTION') {
            const collapse = Math.min(1.0, elapsedSec / 2.0);
            ip = Math.max(0.2, 15.0 * (1.0 - collapse));
            vloop = 185.0 * (1.0 - collapse * 0.7);
            flux = 22.5;
            isCritical = true;
        } else if (mode === 'MODE_TOKAMAK_UNMITIGATED_ELM_BURST') {
            flux = 16.4;
        }

        sub1 = {
            temp: '4.5 K', margin: '14.5 K', hePress: '4.80 bar',
            stress: (185.0 + (isCritical ? 95.0 : 0.0)).toFixed(1) + ' MPa',
            icRatio: '0.65', icPct: 65,
            status: isCritical ? 'Halo Current Stress Warning' : 'TF D-Coils Superconducting Nominal',
            isAlert: isCritical
        };
        sub2 = {
            temp: isCritical ? '0.8 / 0.6 keV' : '16.5 / 15.2 keV',
            density: (isCritical ? 0.3 : 1.45) + ' × 10²⁰ m⁻³',
            tau: isCritical ? '0.08 s' : '2.10 s',
            lawson: isCritical ? '0.04 keV·s·m⁻³' : '50.2 keV·s·m⁻³',
            lawsonPct: isCritical ? 2 : 92, beta: isCritical ? '0.15%' : '3.80%',
            status: isCritical ? 'THERMAL QUENCH COLLAPSE' : `Ip=${ip.toFixed(1)} MA | q95=${q95.toFixed(2)} | Vloop=${vloop.toFixed(2)}V`,
            isAlert: isCritical
        };
        sub3 = {
            flux: flux.toFixed(1) + ' MW/m²', fluxPct: Math.min(100, Math.round((flux / 10.0) * 100)),
            temp: (450 + flux * 25).toFixed(1) + ' °C',
            detach: isCritical ? 'ATTACHED (CRITICAL STRIKE)' : 'RADIATIVELY DETACHED',
            seeding: '2.10 Pa·m³/s',
            status: flux > 10.0 ? 'DIVERTOR OVERLOAD ALERT (>10 MW/m²)' : 'Divertor Target Safe',
            isAlert: flux > 10.0
        };
        sub4 = {
            temp: '360.0 / 510.0 °C', neutron: isCritical ? '0.05 MW/m²' : '2.10 MW/m²',
            tbr: isCritical ? '0.05' : '1.140', tbrPct: isCritical ? 5 : 98,
            tritium: isCritical ? '2.0 g/day' : '155.0 g/day', flow: '310.0 kg/s',
            status: isCritical ? 'Neutron Yield Halted' : 'Tritium Self-Sufficiency Sustained',
            isAlert: isCritical
        };
        sub5 = {
            qsci: isCritical ? '0.05' : '12.00', pfusion: isCritical ? '1.5 MW' : '360.0 MW',
            pgross: isCritical ? '2.0 MW' : '148.2 MW', precirc: '65.0 MW',
            pnet: isCritical ? '-63.0 MW (DEFICIT)' : '+83.2 MW',
            qeng: isCritical ? '0.03' : '2.28', qengPct: isCritical ? 3 : 76,
            status: isCritical ? 'GRID DEFICIT (DRAWING POWER)' : 'Surplus Power Exported to Public Grid',
            isAlert: isCritical
        };

    } else if (reactor === 'REACTOR_ICF') {
        let gain = 85.0;
        let elaser = 2.15;
        let isCritical = false;

        if (mode === 'MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY') {
            gain = 8.5;
            isCritical = true;
        } else if (mode === 'MODE_ICF_TARGET_TRACKING_INJECTION_MISS') {
            gain = 0.5;
            isCritical = true;
        }

        const pfus = elaser * gain * 5.0;
        const plaserElec = (elaser * 5.0) / 0.15;
        const pgross = pfus * 0.38;
        const pnet = pgross - plaserElec - 12.0;

        sub1 = {
            temp: '18.2 K', margin: '74.0 K', hePress: '1.20 bar',
            stress: '45.0 MPa', icRatio: '0.25', icPct: 25,
            status: 'Cryogenic DT Target Injector 18K Nominal', isAlert: false
        };
        sub2 = {
            temp: '25.0 / 22.0 keV', density: '850.0 × 10²⁰ m⁻³ (COMPRESSED)',
            tau: '0.12 ns', lawson: '75.0 keV·s·m⁻³', lawsonPct: 100, beta: 'N/A (INERTIAL)',
            status: isCritical ? 'RAYLEIGH-TAYLOR MIX: Hotspot Quenched' : `E_laser=2.15 MJ | Rep=5 Hz | Target Gain G=${gain.toFixed(1)}`,
            isAlert: isCritical
        };
        sub3 = {
            flux: '3.50 MW/m²', fluxPct: 35, temp: '320.0 °C',
            detach: 'TARGET CHAMBER VACUUM', seeding: 'N/A',
            status: 'Chamber First Wall Shield Protected', isAlert: false
        };
        sub4 = {
            temp: '380.0 / 525.0 °C', neutron: (2.45 * (pfus / 914.0)).toFixed(2) + ' MW/m²',
            tbr: '1.160', tbrPct: 100, tritium: (185.0 * (pfus / 914.0)).toFixed(1) + ' g/day', flow: '340.0 kg/s',
            status: 'Liquid Lithium Waterfall Breeding Active', isAlert: false
        };
        sub5 = {
            qsci: gain.toFixed(1), pfusion: pfus.toFixed(1) + ' MW',
            pgross: pgross.toFixed(1) + ' MW', precirc: plaserElec.toFixed(1) + ' MW',
            pnet: (pnet >= 0 ? '+' : '') + pnet.toFixed(1) + ' MW',
            qeng: (pgross / (plaserElec + 12.0)).toFixed(2),
            qengPct: Math.min(100, Math.round((pgross / (plaserElec + 12.0)) * 40)),
            status: pnet > 0 ? 'Surplus Power Exported to Public Grid' : 'GRID DEFICIT (INSUFFICIENT TARGET GAIN)',
            isAlert: pnet <= 0
        };

    } else {
        // Stellarator (QI Nominal / Faults)
        sub1 = {
            temp: '20.0 K', margin: '72.0 K', hePress: '5.20 bar',
            stress: '145.0 MPa', icRatio: '0.58', icPct: 58,
            status: 'Superconducting State Nominal', isAlert: false
        };
        sub2 = {
            temp: '14.8 / 14.2 keV', density: '1.85 × 10²⁰ m⁻³', tau: '1.65 s',
            lawson: '43.3 keV·s·m⁻³', lawsonPct: 87, beta: '4.25%',
            status: 'QI Omnigenous High-Confinement Flattop', isAlert: false
        };
        sub3 = {
            flux: '4.20 MW/m²', fluxPct: 42, temp: '485.0 °C',
            detach: 'RADIATIVELY DETACHED', seeding: '1.45 Pa·m³/s',
            status: 'Island Divertor Safe (<10 MW/m²)', isAlert: false
        };
        sub4 = {
            temp: '350.0 / 495.0 °C', neutron: '1.85 MW/m²', tbr: '1.150',
            tbrPct: 100, tritium: '142.0 g/day', flow: '280.0 kg/s',
            status: 'Tritium Self-Sufficiency Sustained', isAlert: false
        };
        sub5 = {
            qsci: '10.20', pfusion: '255.0 MW', pgross: '106.4 MW',
            precirc: '50.2 MW', pnet: '+56.2 MW', qeng: '2.12', qengPct: 71,
            status: 'Surplus Power Exported to Public Grid', isAlert: false
        };

        if (mode === 'MODE_HTS_COIL_HOTSPOT_QUENCH') {
            sub1.temp = '98.5 K'; sub1.margin = '0.0 K'; sub1.icRatio = '1.38'; sub1.icPct = 100;
            sub1.status = 'EMERGENCY QUENCH INTERLOCK ACTIVATED'; sub1.isAlert = true;
            sub5.pnet = '-24.0 MW'; sub5.status = 'FAST BREAKER DISCHARGE ACTIVE'; sub5.isAlert = true;
        } else if (mode === 'MODE_DIVERTOR_DETACHMENT_FAULT') {
            sub3.flux = '16.8 MW/m²'; sub3.fluxPct = 100; sub3.temp = '980.0 °C';
            sub3.detach = 'ATTACHMENT FAULT (NO RAD)'; sub3.status = 'THERMAL OVERLOAD ALERT (>10 MW/m²)'; sub3.isAlert = true;
        }
    }

    renderSubsystemValues(sub1, sub2, sub3, sub4, sub5);
    update3DPhysicsStats(sub1, sub2, sub3, sub4, sub5);

    // Calculate adaptive waveform values
    let w1 = 3.2, w2 = 0.12, w3 = 20.0;
    let s1 = '3.2 dB', s2 = '+0.12 pF/s', s3 = '20.0 K';
    if (reactor === 'REACTOR_TOKAMAK') {
        w1 = (mode === 'MODE_TOKAMAK_MAJOR_DISRUPTION') ? 185.0 : (0.12 + Math.random() * 0.05);
        w2 = (mode === 'MODE_TOKAMAK_MAJOR_DISRUPTION') ? 68.4 : ((mode === 'MODE_TOKAMAK_2_1_NTM_ISLAND') ? 24.2 : 1.2);
        w3 = parseFloat(sub3.flux) || 4.8;
        s1 = `${w1.toFixed(1)} V`;
        s2 = `${w2.toFixed(1)} T/s`;
        s3 = `${w3.toFixed(1)} MW/m²`;
    } else if (reactor === 'REACTOR_ICF') {
        w1 = mode.includes('JITTER') ? 42.5 : (6.2 + Math.random() * 2.0);
        w2 = mode.includes('MISS') ? 52.0 : (6.8 + Math.random() * 1.5);
        w3 = mode.includes('TAYLOR') ? 4.8 : (0.45 + Math.random() * 0.1);
        s1 = `${w1.toFixed(1)} ps`;
        s2 = `${w2.toFixed(1)} µm`;
        s3 = `${w3.toFixed(2)}%`;
    } else {
        const isQ = (mode === 'MODE_HTS_COIL_HOTSPOT_QUENCH');
        w1 = isQ ? (32.4 + Math.random() * 4.0) : (3.2 + Math.random() * 0.4);
        w2 = isQ ? (22.8 + Math.random() * 3.0) : (0.12 + Math.random() * 0.05);
        w3 = isQ ? 98.5 : 20.2;
        s1 = `${w1.toFixed(1)} dB`;
        s2 = `${w2.toFixed(2)} pF/s`;
        s3 = `${w3.toFixed(1)} K`;
    }
    updateAdaptiveWaveforms(w1, w2, w3, s1, s2, s3);
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
        status: data.coil_cryo.quench_warning ? 'EMERGENCY QUENCH INTERLOCK ACTIVATED' : 'Cryo & Coils Nominal',
        isAlert: data.coil_cryo.quench_warning
    };

    const sub2 = {
        temp: `${data.plasma_core.electron_temp_kev} / ${data.plasma_core.ion_temp_kev} keV`,
        density: `${data.plasma_core.electron_density_1e20_m3} × 10²⁰ m⁻³`,
        tau: `${data.plasma_core.energy_confinement_tau_s} s`,
        lawson: `${data.plasma_core.lawson_triple_product_kev_s_m3} keV·s·m⁻³`,
        lawsonPct: Math.min(100, Math.round((data.plasma_core.lawson_triple_product_kev_s_m3 / 50.0) * 100)),
        beta: `${data.plasma_core.toroidal_beta_percent}%`,
        status: data.mode_description || 'Plasma Confinement Active',
        isAlert: !data.plasma_core.mhd_quiescent
    };

    const sub3 = {
        flux: `${data.divertor.peak_heat_flux_mw_per_m2} MW/m²`,
        fluxPct: Math.min(100, Math.round((data.divertor.peak_heat_flux_mw_per_m2 / 10.0) * 100)),
        temp: `${data.divertor.target_surface_temp_c} °C`,
        detach: data.divertor.detachment_achieved ? 'RADIATIVELY DETACHED' : 'ATTACHMENT FAULT',
        seeding: `${data.divertor.impurity_seeding_rate_pa_m3_s} Pa·m³/s`,
        status: data.divertor.thermal_overload_alert ? 'THERMAL OVERLOAD ALERT (>10 MW/m²)' : 'Divertor Safe',
        isAlert: data.divertor.thermal_overload_alert
    };

    const sub4 = {
        temp: `${data.blanket.pb_li_inlet_temp_c} / ${data.blanket.pb_li_outlet_temp_c} °C`,
        neutron: `${data.blanket.neutron_wall_load_mw_per_m2} MW/m²`,
        tbr: `${data.blanket.tritium_breeding_ratio} (>1.05 Target)`,
        tbrPct: Math.min(100, Math.round((data.blanket.tritium_breeding_ratio / 1.15) * 100)),
        tritium: `${data.blanket.tritium_extraction_rate_g_per_day} g/day`,
        flow: `${data.blanket.coolant_flow_rate_kg_s} kg/s`,
        status: data.blanket.tritium_breeding_ratio >= 1.05 ? 'Tritium Self-Sufficiency Sustained' : 'TBR Low Warning',
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
    update3DPhysicsStats(sub1, sub2, sub3, sub4, sub5);
    updateDynamicStateMachine();

    // Pass live incoming telemetry into adaptive precursor waveforms
    let liveW1 = 3.2, liveW2 = 0.12, liveW3 = 20.0;
    let liveS1 = '3.2 dB', liveS2 = '+0.12 pF/s', liveS3 = '20.0 K';
    if (activeReactor === 'REACTOR_TOKAMAK' && data.tokamak_core) {
        liveW1 = data.tokamak_core.loop_voltage_v || 0.12;
        liveW2 = data.tokamak_core.locked_mode_amplitude_gauss || 1.2;
        liveW3 = data.divertor.peak_heat_flux_mw_per_m2 || 4.8;
        liveS1 = `${liveW1.toFixed(1)} V`;
        liveS2 = `${liveW2.toFixed(1)} T/s`;
        liveS3 = `${liveW3.toFixed(1)} MW/m²`;
    } else if (activeReactor === 'REACTOR_ICF' && data.icf_core) {
        liveW1 = data.icf_core.laser_jitter_ps || 6.5;
        liveW2 = 6.2;
        liveW3 = data.icf_core.rayleigh_taylor_growth_factor || 0.45;
        liveS1 = `${liveW1.toFixed(1)} ps`;
        liveS2 = `6.2 µm`;
        liveS3 = `${liveW3.toFixed(2)}%`;
    } else {
        liveW1 = data.coil_cryo.quench_warning ? 32.5 : (data.coil_cryo.foas_acoustic_db || 3.2);
        liveW2 = data.coil_cryo.quench_warning ? 22.4 : 0.12;
        liveW3 = data.coil_cryo.coil_temperature_k || 20.0;
        liveS1 = `${liveW1.toFixed(1)} dB`;
        liveS2 = `${liveW2.toFixed(2)} pF/s`;
        liveS3 = `${liveW3.toFixed(1)} K`;
    }
    updateAdaptiveWaveforms(liveW1, liveW2, liveW3, liveS1, liveS2, liveS3);
}

function renderSubsystemValues(sub1, sub2, sub3, sub4, sub5) {
    setEl('sub1-temp', sub1.temp);
    setEl('sub1-margin', sub1.margin);
    setEl('sub1-he-press', sub1.hePress);
    setEl('sub1-stress', sub1.stress);
    setEl('sub1-ic-ratio', sub1.icRatio);
    setEl('sub1-ic-pct', `${sub1.icPct}%`);
    setEl('sub1-status', sub1.status);
    setBar('sub1-ic-bar', sub1.icPct, sub1.isAlert ? 'bg-red' : 'bg-cyan');
    setDot('sub1-dot', sub1.isAlert ? 'dot-red' : 'dot-green');

    setEl('sub2-temp', sub2.temp);
    setEl('sub2-density', sub2.density);
    setEl('sub2-tau', sub2.tau);
    setEl('sub2-lawson', sub2.lawson);
    setEl('sub2-lawson-pct', `${sub2.lawsonPct}%`);
    setEl('sub2-beta', sub2.beta);
    setEl('sub2-status', sub2.status);
    setBar('sub2-lawson-bar', sub2.lawsonPct, sub2.isAlert ? 'bg-red' : 'bg-purple');
    setDot('sub2-dot', sub2.isAlert ? 'dot-red' : 'dot-green');

    setEl('sub3-flux', sub3.flux);
    setEl('sub3-temp', sub3.temp);
    setEl('sub3-detach', sub3.detach);
    setEl('sub3-seeding', sub3.seeding);
    setEl('sub3-load-pct', `${sub3.fluxPct}%`);
    setEl('sub3-status', sub3.status);
    setBar('sub3-flux-bar', sub3.fluxPct, sub3.isAlert ? 'bg-red' : 'bg-green');
    setDot('sub3-dot', sub3.isAlert ? 'dot-red' : 'dot-green');

    setEl('sub4-temp', sub4.temp);
    setEl('sub4-neutron', sub4.neutron);
    setEl('sub4-tbr', sub4.tbr);
    setEl('sub4-tritium', sub4.tritium);
    setEl('sub4-flow', sub4.flow);
    setEl('sub4-tbr-pct', `${sub4.tbrPct}%`);
    setEl('sub4-status', sub4.status);
    setBar('sub4-tbr-bar', sub4.tbrPct, sub4.isAlert ? 'bg-red' : 'bg-green');
    setDot('sub4-dot', sub4.isAlert ? 'dot-red' : 'dot-green');

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

/* ========================================================================== */
/* Dynamic State Machine Engine (Coupled Multi-Physics Transitions)           */
/* ========================================================================== */
const STATE_MACHINE_CONFIG = {
    'REACTOR_QI_STELLARATOR': {
        badge: 'QI-HTS',
        states: [
            {
                id: 'MODE_STARTUP_RAMP',
                name: '1. Startup Ignition',
                icon: '🚀',
                type: 'nominal',
                trigger: 'Coils 0->5.5T | ECRH 140GHz Break',
                action: 'Purdue L2 Magnetic Energization Ramp',
                statusPill: 'RAMP UP'
            },
            {
                id: 'MODE_STEADY_STATE_NOMINAL',
                name: '2. Steady-State Flattop',
                icon: '⚡',
                type: 'nominal',
                trigger: 'Omnigenous Cage | Q_sci=10.5 | P_net=+58MW',
                action: 'Nominal High-Confinement Export',
                statusPill: 'STEADY STATE'
            },
            {
                id: 'MODE_PELLET_REFUELING_BURST',
                name: '3. Cryo Pellet Refuel',
                icon: '🧊',
                type: 'nominal',
                trigger: 'D-T Ice Pellet 1.2 km/s | Density Spike',
                action: 'Core Alpha Heating Maintenance',
                statusPill: 'REFUELING'
            },
            {
                id: 'MODE_DIVERTOR_DETACHMENT_FAULT',
                name: '4. Divertor Detachment Fault',
                icon: '🔥',
                type: 'anomaly',
                trigger: 'Strike-Point Heat >16.8 MW/m²',
                action: 'Level 2 Neon/Argon Gas Puff Throttle',
                statusPill: 'HEAT OVERLOAD'
            },
            {
                id: 'MODE_CORE_TUNGSTEN_COLLAPSE',
                name: '5. Tungsten Impurity Collapse',
                icon: '🌪️',
                type: 'anomaly',
                trigger: 'Radiation Loss Prad > 35 MW',
                action: 'ECRH Central Heating Flush',
                statusPill: 'IMPURITY SURGE'
            },
            {
                id: 'MODE_HTS_COIL_HOTSPOT_QUENCH',
                name: '6. HTS Hotspot Quench',
                icon: '🚨',
                type: 'critical',
                trigger: 'FOAS Acoustic >25kHz | dC/dt >15 pF/s',
                action: 'Level 1 Pyro-Breaker Dump <22µs',
                statusPill: 'QUENCH INTERLOCK'
            }
        ]
    },
    'REACTOR_TOKAMAK': {
        badge: 'TOKAMAK-CS',
        states: [
            {
                id: 'MODE_TOKAMAK_NOMINAL_FLATTOP',
                name: '1. Nominal Flattop Burn',
                icon: '⚡',
                type: 'nominal',
                trigger: 'Ip=15 MA | q95=3.25 | H98y2=1.05',
                action: 'Inductive Current Sustainment',
                statusPill: 'FLATTOP BURN'
            },
            {
                id: 'MODE_TOKAMAK_2_1_NTM_ISLAND',
                name: '2. 2/1 NTM Tearing Island',
                icon: '🌀',
                type: 'anomaly',
                trigger: 'Magnetic Island w > 4.5 cm | Confinement -40%',
                action: 'Steerable ECCD Current Drive Healing',
                statusPill: 'NTM ACTIVE'
            },
            {
                id: 'MODE_TOKAMAK_UNMITIGATED_ELM_BURST',
                name: '3. Type-I ELM Burst',
                icon: '💥',
                type: 'anomaly',
                trigger: 'Edge Pedestal Collapse | Heat 16.4 MW/m²',
                action: 'Resonant Magnetic Perturbation (RMP)',
                statusPill: 'ELM CRASH'
            },
            {
                id: 'MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT',
                name: '4. Vertical Drift (VDE)',
                icon: '↕️',
                type: 'anomaly',
                trigger: 'Delta-Z Drift >40mm into Vessel Wall',
                action: 'Fast In-Vessel Stabilizing Coil Kick',
                statusPill: 'VERTICAL DRIFT'
            },
            {
                id: 'MODE_TOKAMAK_MAJOR_DISRUPTION',
                name: '5. Major Disruption',
                icon: '⚡',
                type: 'critical',
                trigger: 'Thermal Quench (<1ms) | Vloop Spike 185V',
                action: 'Shattered Pellet Injection (SPI) Neon',
                statusPill: 'DISRUPTION'
            },
            {
                id: 'MODE_TOKAMAK_RUNAWAY_ELECTRON_AVALANCHE',
                name: '6. Runaway Electron Beam',
                icon: '☢️',
                type: 'critical',
                trigger: 'Relativistic 3.8 MA Beam | Gamma Burst',
                action: 'Massive Deuterium Injection (MGI)',
                statusPill: 'RUNAWAY BEAM'
            }
        ]
    },
    'REACTOR_ICF': {
        badge: 'ICF-LASER',
        states: [
            {
                id: 'MODE_ICF_NOMINAL_REPETITION_PULSE',
                name: '1. 5 Hz Nominal Rep Pulse',
                icon: '🎯',
                type: 'nominal',
                trigger: '2.15 MJ Laser | Target Gain G=85 | Pfus=914MW',
                action: 'Continuous 5 Hz Microimplosion Cycle',
                statusPill: '5 HZ PULSE'
            },
            {
                id: 'MODE_ICF_CHAMBER_CLEARING_CHOKE',
                name: '2. Chamber Vapor Choke',
                icon: '🌫️',
                type: 'anomaly',
                trigger: 'Residual Metal Vapor > 0.15 Pa',
                action: 'Pulse Delay +100ms for Condensation',
                statusPill: 'CLEARING PAUSE'
            },
            {
                id: 'MODE_ICF_FINAL_OPTICS_DEBRIS_DAMAGE',
                name: '3. Final Optics Debris Damage',
                icon: '🛡️',
                type: 'anomaly',
                trigger: 'Debris Shrapnel | Transmission < 80%',
                action: 'Automated Debris Cassette Advance',
                statusPill: 'DEBRIS FAULT'
            },
            {
                id: 'MODE_ICF_LASER_TIMING_JITTER',
                name: '4. Laser Timing Jitter',
                icon: '⏱️',
                type: 'anomaly',
                trigger: 'Beam Arrival Jitter > 35 ps Out of Sync',
                action: 'Piezo Optical Delay Line Calibration',
                statusPill: 'TIMING JITTER'
            },
            {
                id: 'MODE_ICF_TARGET_TRACKING_INJECTION_MISS',
                name: '5. Target Injection Miss',
                icon: '❌',
                type: 'critical',
                trigger: 'Pellet Offset >40µm off Target Chamber Center',
                action: 'Fast Trigger Abort: Beam Dump Calorimeter',
                statusPill: 'TARGET MISSED'
            },
            {
                id: 'MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY',
                name: '6. Rayleigh-Taylor Asymmetry',
                icon: '🌊',
                type: 'critical',
                trigger: 'Ablator Mix Spike into Core | Yield Drop 90%',
                action: 'Laser Pulse Shaping Fuel Adiabat Adjust',
                statusPill: 'RT INSTABILITY'
            }
        ]
    }
};

function updateDynamicStateMachine() {
    const config = STATE_MACHINE_CONFIG[activeReactor] || STATE_MACHINE_CONFIG['REACTOR_QI_STELLARATOR'];
    const badgeEl = document.getElementById('sm-badge-topology');
    if (badgeEl) badgeEl.textContent = config.badge;

    const bannerEl = document.getElementById('sm-active-banner');
    const nameEl = document.getElementById('sm-active-name');
    const pillEl = document.getElementById('sm-status-pill');
    const dotEl = document.getElementById('sm-pulse-dot');
    const triggerEl = document.getElementById('sm-interlock-trigger');
    const actionEl = document.getElementById('sm-interlock-action');
    const footerDot = document.getElementById('sm-footer-dot');
    const footerText = document.getElementById('sm-footer-text');

    const activeStateObj = config.states.find(s => s.id === activeMode) || config.states[1];

    if (nameEl) nameEl.textContent = activeMode;
    if (pillEl) {
        pillEl.textContent = activeStateObj.statusPill;
        pillEl.className = `sm-status-pill ${activeStateObj.type === 'critical' ? 'pill-critical' : (activeStateObj.type === 'anomaly' ? 'pill-warning' : '')}`;
    }
    if (dotEl) {
        dotEl.className = `sm-pulse-dot ${activeStateObj.type === 'critical' ? 'dot-critical' : (activeStateObj.type === 'anomaly' ? 'dot-warning' : '')}`;
    }
    if (bannerEl) {
        bannerEl.className = `sm-active-banner ${activeStateObj.type === 'critical' ? 'is-critical' : (activeStateObj.type === 'anomaly' ? 'is-anomaly' : '')}`;
    }

    if (triggerEl) triggerEl.textContent = activeStateObj.trigger;
    if (actionEl) {
        actionEl.textContent = activeStateObj.action;
        actionEl.className = `sm-interlock-val ${activeStateObj.type === 'critical' ? 'highlight-red' : (activeStateObj.type === 'anomaly' ? 'highlight-gold' : 'highlight-green')}`;
    }

    if (footerDot) {
        footerDot.className = `status-indicator-dot ${activeStateObj.type === 'critical' ? 'dot-red' : (activeStateObj.type === 'anomaly' ? 'dot-yellow' : 'dot-green')}`;
    }
    if (footerText) {
        footerText.textContent = activeStateObj.type === 'critical' ? 'Level 1 Fast Interlock Triggered' : (activeStateObj.type === 'anomaly' ? 'Level 2 Mitigating Feedback Active' : 'State Machine Active & Deterministic');
    }

    const gridEl = document.getElementById('sm-states-grid');
    if (!gridEl) return;
    gridEl.innerHTML = '';

    config.states.forEach(s => {
        const btn = document.createElement('div');
        const isActive = (s.id === activeMode);
        btn.className = `sm-node-btn ${isActive ? 'active-node' : ''} ${s.type === 'critical' ? 'node-critical' : (s.type === 'anomaly' ? 'node-warning' : '')}`;
        btn.innerHTML = `
            <div class="sm-node-top">
                <span class="sm-node-icon">${s.icon}</span>
                <span class="sm-node-badge">${isActive ? 'ACTIVE' : s.type}</span>
            </div>
            <div class="sm-node-name">${s.name}</div>
            <div class="sm-node-trigger">${s.trigger}</div>
        `;
        btn.addEventListener('click', () => {
            isAutoCycling = false;
            if (autoCycleTimer) clearInterval(autoCycleTimer);
            setOperationalMode(s.id);
        });
        gridEl.appendChild(btn);
    });
}

/* ========================================================================== */
/* 4. 2D Interactive Sankey Power Flow Simulator Engine                       */
/*    Directly inspired by Fusion Energy Base Simulator                       */
/* ========================================================================== */
let sankeyRegime = 'steady'; // 'steady' or 'pulsed'
let sankeyFuel = 'DT';       // 'DT', 'DD', 'PB11'
let sankeyParticles = [];

function init2DSankeySimulator() {
    // Regime toggle buttons
    const btnSteady = document.getElementById('btn-regime-steady');
    const btnPulsed = document.getElementById('btn-regime-pulsed');
    const steadyGroup = document.getElementById('steady-controls-group');
    const pulsedGroup = document.getElementById('pulsed-controls-group');
    const modeLabel = document.getElementById('sankey-mode-label');

    btnSteady.addEventListener('click', () => {
        btnSteady.classList.add('active');
        btnPulsed.classList.remove('active');
        sankeyRegime = 'steady';
        steadyGroup.style.display = 'block';
        pulsedGroup.style.display = 'none';
        if (modeLabel) modeLabel.textContent = `Regime: Continuous Steady-State • ${sankeyFuel} Cycle`;
        updateSankeyPhysics();
    });

    btnPulsed.addEventListener('click', () => {
        btnPulsed.classList.add('active');
        btnSteady.classList.remove('active');
        sankeyRegime = 'pulsed';
        steadyGroup.style.display = 'none';
        pulsedGroup.style.display = 'block';
        if (modeLabel) modeLabel.textContent = `Regime: Pulsed Inertial Driver (MJ & Rep-Rate) • ${sankeyFuel} Cycle`;
        updateSankeyPhysics();
    });

    // Fuel toggle buttons
    const fuelBtns = [
        document.getElementById('btn-fuel-dt'),
        document.getElementById('btn-fuel-dd'),
        document.getElementById('btn-fuel-pb')
    ];
    fuelBtns.forEach(btn => {
        if (!btn) return;
        btn.addEventListener('click', () => {
            fuelBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            sankeyFuel = btn.getAttribute('data-fuel');
            if (modeLabel) modeLabel.textContent = `Regime: ${sankeyRegime === 'steady' ? 'Continuous Steady-State' : 'Pulsed Driver'} • ${sankeyFuel} Cycle`;

            // Adjust Blanket Multiplier default according to fuel neutron fraction
            const mSlider = document.getElementById('blanketm-slider');
            if (mSlider) {
                if (sankeyFuel === 'DT') mSlider.value = 1.15;
                else if (sankeyFuel === 'DD') mSlider.value = 1.05;
                else if (sankeyFuel === 'PB11') mSlider.value = 1.00;
            }
            updateSankeyPhysics();
        });
    });

    // Slider Listeners
    const sliders = [
        'qsci-slider', 'pheat-slider', 'elaser-slider', 'frep-slider',
        'targetgain-slider', 'etath-slider', 'etaheat-slider', 'blanketm-slider', 'paux-slider'
    ];
    sliders.forEach(sId => {
        const slider = document.getElementById(sId);
        if (slider) slider.addEventListener('input', updateSankeyPhysics);
    });

    // Research Paper Presets Listeners
    const presetBtns = document.querySelectorAll('.preset-card-btn');
    presetBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            presetBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const key = btn.getAttribute('data-paper-preset');
            loadResearchPaperPreset(key);
        });
    });

    // Init Particle Flow
    for (let i = 0; i < 45; i++) {
        sankeyParticles.push({
            ribbon: Math.floor(Math.random() * 4),
            t: Math.random(),
            speed: 0.003 + Math.random() * 0.004,
            size: 2.5 + Math.random() * 2.0
        });
    }

    updateSankeyPhysics();
    requestAnimationFrame(animateSankeyCanvas);
}

const RESEARCH_PAPER_PRESETS = {
    'skhy_qi': {
        name: 'SKHY Commercial QI Stellarator',
        regime: 'steady',
        fuel: 'DT',
        qsci: 10.5,
        pheat: 25.0,
        etath: 38,
        etaheat: 60,
        blanketm: 1.15,
        paux: 10.0,
        reactor: 'REACTOR_QI_STELLARATOR'
    },
    'jet_dt': {
        name: 'JET D-T Fusion Record (1997)',
        regime: 'steady',
        fuel: 'DT',
        qsci: 0.67,
        pheat: 24.0,
        etath: 33,
        etaheat: 50,
        blanketm: 1.0,
        paux: 15.0,
        reactor: 'REACTOR_TOKAMAK'
    },
    'iter_baseline': {
        name: 'ITER Baseline Design Target',
        regime: 'steady',
        fuel: 'DT',
        qsci: 10.0,
        pheat: 50.0,
        etath: 35,
        etaheat: 55,
        blanketm: 1.10,
        paux: 25.0,
        reactor: 'REACTOR_TOKAMAK'
    },
    'sparc_cfs': {
        name: 'SPARC High-Field Tokamak (CFS)',
        regime: 'steady',
        fuel: 'DT',
        qsci: 11.2,
        pheat: 12.5,
        etath: 38,
        etaheat: 60,
        blanketm: 1.15,
        paux: 8.0,
        reactor: 'REACTOR_TOKAMAK'
    },
    'nif_ignition': {
        name: 'NIF Laser Target Ignition (2022/23)',
        regime: 'pulsed',
        fuel: 'DT',
        elaser: 2.05,
        frep: 1.0,
        targetgain: 1.89,
        etath: 30,
        etaheat: 15,
        blanketm: 1.0,
        paux: 5.0,
        reactor: 'REACTOR_ICF'
    },
    'ife_plant': {
        name: 'IFE Commercial Power Plant',
        regime: 'pulsed',
        fuel: 'DT',
        elaser: 2.15,
        frep: 5.0,
        targetgain: 85.0,
        etath: 38,
        etaheat: 15,
        blanketm: 1.15,
        paux: 12.0,
        reactor: 'REACTOR_ICF'
    },
    'w7x_record': {
        name: 'Wendelstein 7-X Triple Product',
        regime: 'steady',
        fuel: 'DD',
        qsci: 0.15,
        pheat: 7.0,
        etath: 30,
        etaheat: 60,
        blanketm: 1.0,
        paux: 12.0,
        reactor: 'REACTOR_QI_STELLARATOR'
    }
};

function loadResearchPaperPreset(presetKey) {
    const p = RESEARCH_PAPER_PRESETS[presetKey];
    if (!p) return;

    // Set regime
    const btnSteady = document.getElementById('btn-regime-steady');
    const btnPulsed = document.getElementById('btn-regime-pulsed');
    if (p.regime === 'pulsed' && btnPulsed) btnPulsed.click();
    else if (btnSteady) btnSteady.click();

    // Set fuel
    const fuelBtn = document.getElementById(`btn-fuel-${p.fuel.toLowerCase()}`);
    if (fuelBtn) fuelBtn.click();

    // Set slider values
    if (p.qsci !== undefined) {
        const el = document.getElementById('qsci-slider');
        if (el) el.value = p.qsci;
    }
    if (p.pheat !== undefined) {
        const el = document.getElementById('pheat-slider');
        if (el) el.value = p.pheat;
    }
    if (p.elaser !== undefined) {
        const el = document.getElementById('elaser-slider');
        if (el) el.value = p.elaser;
    }
    if (p.frep !== undefined) {
        const el = document.getElementById('frep-slider');
        if (el) el.value = p.frep;
    }
    if (p.targetgain !== undefined) {
        const el = document.getElementById('targetgain-slider');
        if (el) el.value = p.targetgain;
    }
    if (p.etath !== undefined) {
        const el = document.getElementById('etath-slider');
        if (el) el.value = p.etath;
    }
    if (p.etaheat !== undefined) {
        const el = document.getElementById('etaheat-slider');
        if (el) el.value = p.etaheat;
    }
    if (p.blanketm !== undefined) {
        const el = document.getElementById('blanketm-slider');
        if (el) el.value = p.blanketm;
    }
    if (p.paux !== undefined) {
        const el = document.getElementById('paux-slider');
        if (el) el.value = p.paux;
    }

    // Switch reactor if different
    if (p.reactor && p.reactor !== activeReactor) {
        const rBtn = document.querySelector(`.reactor-btn[data-reactor="${p.reactor}"]`);
        if (rBtn) rBtn.click();
    }

    updateSankeyPhysics();
}

function syncSankeyToReactor(reactorId) {
    const btnSteady = document.getElementById('btn-regime-steady');
    const btnPulsed = document.getElementById('btn-regime-pulsed');
    const qSlider = document.getElementById('qsci-slider');
    const gainSlider = document.getElementById('targetgain-slider');
    const etaHeatSlider = document.getElementById('etaheat-slider');

    if (reactorId === 'REACTOR_ICF') {
        if (btnPulsed) btnPulsed.click();
        if (gainSlider) gainSlider.value = 85.0;
        if (etaHeatSlider) etaHeatSlider.value = 15;
    } else {
        if (btnSteady) btnSteady.click();
        if (qSlider) qSlider.value = reactorId === 'REACTOR_TOKAMAK' ? 12.0 : 10.2;
        if (etaHeatSlider) etaHeatSlider.value = reactorId === 'REACTOR_TOKAMAK' ? 65 : 60;
    }
    updateSankeyPhysics();
}

let sankeyState = {
    pInjected: 25.0,
    pFusion: 250.0,
    pThermal: 312.5,
    pGross: 118.8,
    pDriverElec: 41.7,
    pAux: 10.0,
    pRecirc: 51.7,
    pNet: 67.1,
    qEng: 2.30,
    recircFrac: 43.5
};

function updateSankeyPhysics() {
    const qsci = parseFloat(document.getElementById('qsci-slider')?.value || 10.0);
    const pheat = parseFloat(document.getElementById('pheat-slider')?.value || 25.0);
    const elaser = parseFloat(document.getElementById('elaser-slider')?.value || 2.15);
    const frep = parseFloat(document.getElementById('frep-slider')?.value || 5.0);
    const targetGain = parseFloat(document.getElementById('targetgain-slider')?.value || 85.0);
    const etaTh = parseFloat(document.getElementById('etath-slider')?.value || 38.0) / 100.0;
    const etaDriver = parseFloat(document.getElementById('etaheat-slider')?.value || 60.0) / 100.0;
    const blanketM = parseFloat(document.getElementById('blanketm-slider')?.value || 1.15);
    const pAux = parseFloat(document.getElementById('paux-slider')?.value || 10.0);

    // Update Slider Badges
    setEl('qsci-val', qsci.toFixed(1));
    setEl('pheat-val', `${Math.round(pheat)} MW`);
    setEl('elaser-val', `${elaser.toFixed(2)} MJ`);
    setEl('frep-val', `${frep.toFixed(1)} Hz`);
    setEl('targetgain-val', targetGain.toFixed(1));
    setEl('etath-val', `${Math.round(etaTh * 100)}%`);
    setEl('etaheat-val', `${Math.round(etaDriver * 100)}%`);
    setEl('blanketm-val', blanketM.toFixed(2));
    setEl('paux-val', `${pAux.toFixed(1)} MW`);

    let pInjected = 0.0;
    let pFusion = 0.0;

    if (sankeyRegime === 'steady') {
        pInjected = pheat;
        pFusion = qsci * pInjected;
    } else {
        // Pulsed ICF driver
        pInjected = elaser * frep; // Average driver beam power in MW
        pFusion = pInjected * targetGain;
    }

    // Fuel neutron / alpha partition
    let neutronFrac = 0.80;
    if (sankeyFuel === 'DD') neutronFrac = 0.66;
    else if (sankeyFuel === 'PB11') neutronFrac = 0.001;

    const pNeutrons = pFusion * neutronFrac;
    const pCharged = pFusion * (1.0 - neutronFrac);

    // Blanket exothermic multiplication applies to neutron capture
    const pBlanketNeutronHeat = pNeutrons * blanketM;
    const pThermal = pBlanketNeutronHeat + pCharged + pInjected;

    const pGross = pThermal * etaTh;
    const pDriverElec = pInjected / etaDriver;
    const pRecirc = pDriverElec + pAux;
    const pNet = pGross - pRecirc;
    const qEng = pGross / Math.max(0.1, pRecirc);
    const recircFrac = (pRecirc / Math.max(0.1, pGross)) * 100.0;

    sankeyState = {
        pInjected, pFusion, pThermal, pGross, pDriverElec, pAux, pRecirc, pNet, qEng, recircFrac
    };

    // Update Metrics HUD
    setEl('pfusion-val', `${pFusion.toFixed(1)} MW`);
    setEl('pexit-val', `${pThermal.toFixed(1)} MW`);
    setEl('pgross-val', `${pGross.toFixed(1)} MW`);
    setEl('pdriver-elec-val', `${pDriverElec.toFixed(1)} MW`);
    setEl('precirc-val', `${pRecirc.toFixed(1)} MW`);
    setEl('pnet-val', `${pNet >= 0 ? '+' : ''}${pNet.toFixed(1)} MW`);
    setEl('qeng-val', qEng.toFixed(2));
    setEl('recirc-frac-val', `${Math.min(999, Math.max(0, recircFrac)).toFixed(1)}%`);

    const statusBox = document.getElementById('power-status-box');
    const statusTitle = document.getElementById('power-status-title');
    const statusSub = document.getElementById('power-status-sub');
    const pNetEl = document.getElementById('pnet-val');

    if (pNet > 0) {
        if (statusBox) statusBox.classList.remove('quench-tripped');
        if (statusTitle) {
            statusTitle.textContent = `NET ELECTRICITY DELIVERED: +${pNet.toFixed(1)} MW`;
            statusTitle.style.color = '#00E676';
        }
        if (statusSub) statusSub.textContent = `Commercial Surplus Exported to Grid! Engineering Gain Q_eng = ${qEng.toFixed(2)}`;
        if (pNetEl) pNetEl.className = 'metric-value highlight-green';
    } else {
        if (statusBox) statusBox.classList.add('quench-tripped');
        if (statusTitle) {
            statusTitle.textContent = `GRID POWER DEFICIT: ${pNet.toFixed(1)} MW (DRAWING POWER)`;
            statusTitle.style.color = '#FF3366';
        }
        if (statusSub) statusSub.textContent = `Plant consumes more electricity than it generates! Increase Gain or Driver Efficiency.`;
        if (pNetEl) pNetEl.className = 'metric-value highlight-red';
    }
}

function animateSankeyCanvas() {
    renderSankeyDiagram();
    requestAnimationFrame(animateSankeyCanvas);
}

function renderSankeyDiagram() {
    const canvas = document.getElementById('sankey-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;

    ctx.clearRect(0, 0, W, H);

    // Subtle dark grid background
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
    ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 40) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = 0; y < H; y += 40) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    const { pInjected, pFusion, pThermal, pGross, pDriverElec, pAux, pRecirc, pNet } = sankeyState;

    // Node Positions (x, y, w, h)
    const nRecirc = { x: 50, y: 190, w: 120, h: 70, label: 'Driver Recirculation', val: `${pDriverElec.toFixed(1)} MW`, col: '#D09030' };
    const nDriver = { x: 230, y: 190, w: 130, h: 70, label: sankeyRegime === 'steady' ? 'RF / ECRH Heating' : 'UV Laser Bank', val: `${pInjected.toFixed(1)} MW`, col: '#E08020' };
    const nCore   = { x: 420, y: 170, w: 140, h: 90, label: sankeyRegime === 'steady' ? 'Plasma Fusion Core' : 'DT Pellet Implosion', val: `${pFusion.toFixed(1)} MW`, col: '#3CB8E0' };
    const nBlanket= { x: 620, y: 170, w: 140, h: 90, label: 'Blanket & Shielding', val: `${pThermal.toFixed(1)} MW`, col: '#2299AA' };
    const nGen    = { x: 810, y: 180, w: 130, h: 80, label: 'Turbine Generator', val: `${pGross.toFixed(1)} MW`, col: '#2299AA' };

    // Net Grid Node (far right top)
    const isNetPositive = pNet >= 0;
    const nGrid   = { x: 810, y: 50, w: 140, h: 70, label: 'Public Power Grid', val: `${isNetPositive ? '+' : ''}${pNet.toFixed(1)} MW`, col: isNetPositive ? '#22AA77' : '#DD4444' };

    // Aux node (bottom left)
    const nAux    = { x: 50, y: 340, w: 120, h: 55, label: 'Cryo / Aux Loads', val: `${pAux.toFixed(1)} MW`, col: '#D09030' };

    // Function to draw sleek curved ribbons
    function drawRibbon(x1, y1, x2, y2, thickness, colorStart, colorEnd) {
        ctx.beginPath();
        const cp1x = x1 + (x2 - x1) * 0.5;
        const cp2x = x1 + (x2 - x1) * 0.5;

        ctx.moveTo(x1, y1 - thickness / 2);
        ctx.bezierCurveTo(cp1x, y1 - thickness / 2, cp2x, y2 - thickness / 2, x2, y2 - thickness / 2);
        ctx.lineTo(x2, y2 + thickness / 2);
        ctx.bezierCurveTo(cp2x, y2 + thickness / 2, cp1x, y1 + thickness / 2, x1, y1 + thickness / 2);
        ctx.closePath();

        const grad = ctx.createLinearGradient(x1, y1, x2, y2);
        grad.addColorStop(0, colorStart);
        grad.addColorStop(1, colorEnd);
        ctx.fillStyle = grad;
        ctx.fill();

        // Edge stroke
        ctx.strokeStyle = colorEnd;
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    // 1. Recirc -> Driver Ribbon
    const thickRecirc = Math.min(35, Math.max(6, (pDriverElec / 200.0) * 40));
    drawRibbon(nRecirc.x + nRecirc.w, nRecirc.y + nRecirc.h / 2, nDriver.x, nDriver.y + nDriver.h / 2, thickRecirc, 'rgba(208, 144, 48, 0.45)', 'rgba(224, 128, 32, 0.7)');

    // 2. Driver -> Core Ribbon
    const thickInjected = Math.min(30, Math.max(6, (pInjected / 200.0) * 40));
    drawRibbon(nDriver.x + nDriver.w, nDriver.y + nDriver.h / 2, nCore.x, nCore.y + nCore.h / 2, thickInjected, 'rgba(224, 128, 32, 0.7)', 'rgba(60, 184, 224, 0.8)');

    // 3. Core -> Blanket Ribbon
    const thickFusion = Math.min(65, Math.max(12, (pFusion / 600.0) * 60));
    drawRibbon(nCore.x + nCore.w, nCore.y + nCore.h / 2, nBlanket.x, nBlanket.y + nBlanket.h / 2, thickFusion, 'rgba(60, 184, 224, 0.8)', 'rgba(34, 153, 170, 0.8)');

    // 4. Blanket -> Turbine Ribbon
    const thickThermal = Math.min(55, Math.max(10, (pThermal / 600.0) * 55));
    drawRibbon(nBlanket.x + nBlanket.w, nBlanket.y + nBlanket.h / 2, nGen.x, nGen.y + nGen.h / 2, thickThermal, 'rgba(34, 153, 170, 0.8)', 'rgba(34, 153, 170, 0.85)');

    // 5. Generator -> Grid Ribbon (Top curve)
    const thickNet = Math.min(45, Math.max(6, (Math.abs(pNet) / 300.0) * 40));
    const netColor = isNetPositive ? 'rgba(34, 170, 119, 0.85)' : 'rgba(221, 68, 68, 0.85)';
    drawRibbon(nGen.x + nGen.w / 2, nGen.y, nGrid.x + nGrid.w / 2, nGrid.y + nGrid.h, thickNet, 'rgba(34, 153, 170, 0.7)', netColor);

    // 6. Generator -> Recirc Feedback Loop (curving back along bottom)
    const thickFeedback = Math.min(35, Math.max(6, (pRecirc / 200.0) * 35));
    ctx.beginPath();
    ctx.moveTo(nGen.x + nGen.w / 2, nGen.y + nGen.h);
    ctx.bezierCurveTo(nGen.x + nGen.w / 2, 380, 200, 380, nRecirc.x + nRecirc.w / 2, nRecirc.y + nRecirc.h);
    ctx.strokeStyle = 'rgba(208, 144, 48, 0.6)';
    ctx.lineWidth = thickFeedback;
    ctx.stroke();

    // 7. Aux -> Recirc Ribbon
    drawRibbon(nAux.x + nAux.w, nAux.y + nAux.h / 2, nRecirc.x + nRecirc.w / 2, nRecirc.y + nRecirc.h, 6, 'rgba(208, 144, 48, 0.4)', 'rgba(208, 144, 48, 0.7)');

    // Animated particle ribbons
    sankeyParticles.forEach(p => {
        p.t = (p.t + p.speed) % 1.0;
        let px = 0, py = 0;

        if (p.ribbon === 0) {
            // Recirc -> Driver
            px = nRecirc.x + nRecirc.w + (nDriver.x - (nRecirc.x + nRecirc.w)) * p.t;
            py = nDriver.y + nDriver.h / 2;
        } else if (p.ribbon === 1) {
            // Driver -> Core
            px = nDriver.x + nDriver.w + (nCore.x - (nDriver.x + nDriver.w)) * p.t;
            py = nCore.y + nCore.h / 2;
        } else if (p.ribbon === 2) {
            // Core -> Blanket
            px = nCore.x + nCore.w + (nBlanket.x - (nCore.x + nCore.w)) * p.t;
            py = nBlanket.y + nBlanket.h / 2;
        } else if (p.ribbon === 3) {
            // Blanket -> Generator
            px = nBlanket.x + nBlanket.w + (nGen.x - (nBlanket.x + nBlanket.w)) * p.t;
            py = nGen.y + nGen.h / 2;
        }

        ctx.fillStyle = '#FFFFFF';
        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fill();
    });

    // Draw Nodes
    const nodes = [nRecirc, nDriver, nCore, nBlanket, nGen, nGrid, nAux];
    nodes.forEach(node => {
        // Node Box
        ctx.fillStyle = 'rgba(14, 20, 32, 0.9)';
        ctx.strokeStyle = node.col;
        ctx.lineWidth = 2;
        roundRect(ctx, node.x, node.y, node.w, node.h, 8, true, true);

        // Header accent line
        ctx.fillStyle = node.col;
        roundRect(ctx, node.x, node.y, node.w, 4, 2, true, false);

        // Text
        ctx.font = '600 11px Inter, sans-serif';
        ctx.fillStyle = '#94A3B8';
        ctx.textAlign = 'center';
        ctx.fillText(node.label, node.x + node.w / 2, node.y + 24);

        ctx.font = '800 15px Outfit, sans-serif';
        ctx.fillStyle = node.col;
        ctx.fillText(node.val, node.x + node.w / 2, node.y + 48);
    });
}

function roundRect(ctx, x, y, width, height, radius, fill, stroke) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
    if (fill) ctx.fill();
    if (stroke) ctx.stroke();
}

/* ========================================================================== */
/* 5. Three.js WebGL 3D Multi-Reactor Studio & 2.5D Fallback Engine           */
/* ========================================================================== */
let scene3D, camera3D, renderer3D, controls3D;
let stellaratorGroup, tokamakGroup, icfGroup;
let currentReactorGroup = null;
let animReq3D = null;
let icfPulseTimer = 0;
let quenchSparks = null;
let disruptionFilaments = null;

// 2.5D Canvas Compatibility Fallback State
let isCanvas2DFallback = false;
let fallbackCanvas = null;
let fallbackCtx = null;
let fallbackRotX = 0.35;
let fallbackRotY = 0.45;
let fallbackZoom = 1.0;
let isDraggingFallback = false;
let dragStartX = 0;
let dragStartY = 0;
let fallbackAnimReq = null;
let showLayerCoils = true;
let showLayerPlasma = true;
let showLayerDivertor = true;
let showLayerHeat = true;
let fallbackSparks = [];
let fallbackYaw = 0;

function init3DMultiReactorStudio() {
    const container = document.getElementById('threejs-container');
    if (!container) return;

    // Attach Camera & Layer HUD controls early so they function in both modes
    attachStudioHUDListeners();

    let webglUsable = false;

    // Attempt WebGL initialization if Three.js is loaded
    if (window.THREE) {
        try {
            // Test WebGL capability on a transient canvas first
            const testCanvas = document.createElement('canvas');
            const gl = testCanvas.getContext('webgl') || testCanvas.getContext('experimental-webgl');
            if (!gl) {
                throw new Error("WebGL context creation unavailable on current graphics driver");
            }

            // 1. Scene, Camera, Renderer
            scene3D = new THREE.Scene();
            scene3D.fog = new THREE.FogExp2(0x05070D, 0.003);

            const width = container.clientWidth || 700;
            const height = container.clientHeight || 480;

            camera3D = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
            camera3D.position.set(0, 18, 42);

            renderer3D = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'default' });
            renderer3D.setSize(width, height);
            renderer3D.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
            renderer3D.shadowMap.enabled = true;
            container.appendChild(renderer3D.domElement);

            // 2. OrbitControls
            if (THREE.OrbitControls) {
                controls3D = new THREE.OrbitControls(camera3D, renderer3D.domElement);
                controls3D.enableDamping = true;
                controls3D.dampingFactor = 0.05;
                controls3D.maxDistance = 120;
                controls3D.minDistance = 8;
                controls3D.target.set(0, 0, 0);
            }

            // 3. Lighting
            const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
            scene3D.add(ambientLight);

            const keyLight = new THREE.DirectionalLight(0x00F2FE, 1.8);
            keyLight.position.set(30, 40, 30);
            scene3D.add(keyLight);

            const fillLight = new THREE.DirectionalLight(0x7B2CBF, 1.2);
            fillLight.position.set(-30, -20, -30);
            scene3D.add(fillLight);

            const coreLight = new THREE.PointLight(0x00F2FE, 3.0, 50);
            coreLight.position.set(0, 0, 0);
            scene3D.add(coreLight);

            // 4. Build 3D Models Procedurally
            buildStellaratorModel();
            buildTokamakModel();
            buildIcfModel();

            // Set initial active model
            switch3DReactorModel(activeReactor);

            window.addEventListener('resize', onWindowResize3D);

            // Start WebGL render loop
            animate3D();
            webglUsable = true;
        } catch (webglErr) {
            console.warn("WebGL is unavailable in this environment, activating 2.5D Canvas Studio:", webglErr);
            webglUsable = false;
        }
    }

    if (!webglUsable) {
        init2DFallbackStudio(container);
    }
}

function attachStudioHUDListeners() {
    const camBtns = {
        'btn-cam-persp': () => {
            if (isCanvas2DFallback) {
                fallbackRotX = 0.35; fallbackRotY = 0.45; fallbackZoom = 1.0;
            } else {
                setCameraPosition(0, 18, 42);
            }
        },
        'btn-cam-top': () => {
            if (isCanvas2DFallback) {
                fallbackRotX = Math.PI / 2 - 0.05; fallbackRotY = 0; fallbackZoom = 1.0;
            } else {
                setCameraPosition(0, 48, 0.1);
            }
        },
        'btn-cam-front': () => {
            if (isCanvas2DFallback) {
                fallbackRotX = 0; fallbackRotY = 0; fallbackZoom = 1.0;
            } else {
                setCameraPosition(0, 0, 45);
            }
        },
        'btn-cam-iso': () => {
            if (isCanvas2DFallback) {
                fallbackRotX = 0.55; fallbackRotY = 0.75; fallbackZoom = 1.0;
            } else {
                setCameraPosition(28, 28, 28);
            }
        },
        'btn-cam-reset': () => {
            if (isCanvas2DFallback) {
                fallbackRotX = 0.35; fallbackRotY = 0.45; fallbackZoom = 1.0;
            } else {
                controls3D?.reset(); setCameraPosition(0, 18, 42);
            }
        }
    };

    Object.keys(camBtns).forEach(id => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.threejs-camera-hud .hud-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                camBtns[id]();
            });
        }
    });

    document.getElementById('layer-coils')?.addEventListener('change', e => {
        showLayerCoils = e.target.checked;
        toggleLayer('coils', e.target.checked);
    });
    document.getElementById('layer-plasma')?.addEventListener('change', e => {
        showLayerPlasma = e.target.checked;
        toggleLayer('plasma', e.target.checked);
    });
    document.getElementById('layer-divertor')?.addEventListener('change', e => {
        showLayerDivertor = e.target.checked;
        toggleLayer('divertor', e.target.checked);
    });
    document.getElementById('layer-heat')?.addEventListener('change', e => {
        showLayerHeat = e.target.checked;
        toggleLayer('heat', e.target.checked);
    });
}

function setCameraPosition(x, y, z) {
    if (!camera3D || !controls3D) return;
    camera3D.position.set(x, y, z);
    controls3D.target.set(0, 0, 0);
    controls3D.update();
}

function toggleLayer(layerName, visible) {
    if (!currentReactorGroup) return;
    currentReactorGroup.traverse(child => {
        if (child.userData && child.userData.layer === layerName) {
            child.visible = visible;
        }
    });
}

function onWindowResize3D() {
    const container = document.getElementById('threejs-container');
    if (!container || !renderer3D || !camera3D) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    camera3D.aspect = w / h;
    camera3D.updateProjectionMatrix();
    renderer3D.setSize(w, h);
}

/* ========================================================================== */
/* 5b. 2.5D Canvas Studio Compatibility Engine (No WebGL Dependencies)        */
/* ========================================================================== */
function init2DFallbackStudio(container) {
    isCanvas2DFallback = true;

    // Update status indicators on HUD
    const fpsTag = document.getElementById('webgl-fps-tag');
    if (fpsTag) {
        fpsTag.textContent = '60 FPS 2.5D CANVAS';
        fpsTag.className = 'live-tag highlight-gold';
    }

    const orbitTag = container.parentElement?.querySelector('.highlight-cyan');
    if (orbitTag) {
        orbitTag.textContent = '2.5D INTERACTIVE ENGINE';
    }

    // Clean container of any stale elements
    const oldCanvas = container.querySelector('canvas');
    if (oldCanvas) oldCanvas.remove();

    fallbackCanvas = document.createElement('canvas');
    fallbackCanvas.id = 'canvas-2d-fallback';
    fallbackCanvas.style.width = '100%';
    fallbackCanvas.style.height = '100%';
    fallbackCanvas.style.display = 'block';
    fallbackCanvas.style.cursor = 'grab';
    container.appendChild(fallbackCanvas);

    fallbackCtx = fallbackCanvas.getContext('2d');

    function resizeFallback() {
        if (!container || !fallbackCanvas || !fallbackCtx) return;
        const rect = container.getBoundingClientRect();
        const w = rect.width || 700;
        const h = rect.height || 480;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        fallbackCanvas.width = w * dpr;
        fallbackCanvas.height = h * dpr;
        fallbackCtx.setTransform(1, 0, 0, 1, 0, 0);
        fallbackCtx.scale(dpr, dpr);
    }

    resizeFallback();
    window.addEventListener('resize', resizeFallback);

    // Mouse interactive drag rotation
    fallbackCanvas.addEventListener('mousedown', (e) => {
        isDraggingFallback = true;
        dragStartX = e.clientX;
        dragStartY = e.clientY;
        fallbackCanvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDraggingFallback) return;
        const dx = e.clientX - dragStartX;
        const dy = e.clientY - dragStartY;
        dragStartX = e.clientX;
        dragStartY = e.clientY;

        fallbackRotY += dx * 0.008;
        fallbackRotX = Math.max(-1.42, Math.min(1.42, fallbackRotX + dy * 0.008));
    });

    window.addEventListener('mouseup', () => {
        if (isDraggingFallback) {
            isDraggingFallback = false;
            if (fallbackCanvas) fallbackCanvas.style.cursor = 'grab';
        }
    });

    // Mouse wheel zoom
    fallbackCanvas.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        fallbackZoom = Math.max(0.4, Math.min(2.6, fallbackZoom + delta));
    }, { passive: false });

    // Touch events for mobile/trackpads
    let touchStartX = 0, touchStartY = 0;
    fallbackCanvas.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        }
    });
    fallbackCanvas.addEventListener('touchmove', (e) => {
        if (e.touches.length === 1) {
            const dx = e.touches[0].clientX - touchStartX;
            const dy = e.touches[0].clientY - touchStartY;
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            fallbackRotY += dx * 0.01;
            fallbackRotX = Math.max(-1.42, Math.min(1.42, fallbackRotX + dy * 0.01));
        }
    });

    // Start 2.5D animation render loop
    animate2DFallback();
}

function projectPoint(x, y, z, cx, cy, rotX, rotY, zoom) {
    // 1. Rotate around Y axis
    const cosY = Math.cos(rotY);
    const sinY = Math.sin(rotY);
    const x1 = x * cosY + z * sinY;
    const z1 = -x * sinY + z * cosY;

    // 2. Rotate around X axis
    const cosX = Math.cos(rotX);
    const sinX = Math.sin(rotX);
    const y2 = y * cosX - z1 * sinX;
    const z2 = y * sinX + z1 * cosX;

    // 3. Perspective projection
    const cameraDist = 44;
    const pz = z2 + cameraDist;
    const fov = 440 * zoom;
    const depthScale = fov / (pz > 4 ? pz : 4);

    return {
        x: cx + x1 * depthScale,
        y: cy - y2 * depthScale,
        z: z2,
        scale: depthScale
    };
}

function animate2DFallback() {
    fallbackAnimReq = requestAnimationFrame(animate2DFallback);

    if (!fallbackCanvas || !fallbackCtx) return;
    const rect = fallbackCanvas.getBoundingClientRect();
    const w = rect.width || 700;
    const h = rect.height || 480;
    const cx = w / 2;
    const cy = h / 2;
    const time = Date.now() * 0.001;

    // Smooth subtle continuous orbit if user is not dragging
    if (!isDraggingFallback) {
        fallbackYaw += 0.003;
    }
    const currentRotY = fallbackRotY + fallbackYaw;
    const currentRotX = fallbackRotX;

    // Clear Canvas with sleek dark radial gradient
    fallbackCtx.clearRect(0, 0, w, h);
    const bgGrad = fallbackCtx.createRadialGradient(cx, cy, 20, cx, cy, Math.max(w, h));
    bgGrad.addColorStop(0, '#0D1424');
    bgGrad.addColorStop(1, '#05070D');
    fallbackCtx.fillStyle = bgGrad;
    fallbackCtx.fillRect(0, 0, w, h);

    // Subtle Perspective Floor Grid for 3D depth perception
    fallbackCtx.strokeStyle = 'rgba(0, 242, 254, 0.08)';
    fallbackCtx.lineWidth = 1;
    for (let gx = -24; gx <= 24; gx += 8) {
        const p1 = projectPoint(gx, -14, -24, cx, cy, currentRotX, currentRotY, fallbackZoom);
        const p2 = projectPoint(gx, -14, 24, cx, cy, currentRotX, currentRotY, fallbackZoom);
        fallbackCtx.beginPath();
        fallbackCtx.moveTo(p1.x, p1.y);
        fallbackCtx.lineTo(p2.x, p2.y);
        fallbackCtx.stroke();
    }
    for (let gz = -24; gz <= 24; gz += 8) {
        const p1 = projectPoint(-24, -14, gz, cx, cy, currentRotX, currentRotY, fallbackZoom);
        const p2 = projectPoint(24, -14, gz, cx, cy, currentRotX, currentRotY, fallbackZoom);
        fallbackCtx.beginPath();
        fallbackCtx.moveTo(p1.x, p1.y);
        fallbackCtx.lineTo(p2.x, p2.y);
        fallbackCtx.stroke();
    }

    // Render Active Fusion Topology
    if (activeReactor === 'REACTOR_TOKAMAK') {
        render2DTokamak(cx, cy, currentRotX, currentRotY, time);
    } else if (activeReactor === 'REACTOR_ICF') {
        render2DIcf(cx, cy, currentRotX, currentRotY, time);
    } else {
        render2DStellarator(cx, cy, currentRotX, currentRotY, time);
    }
}

/* --- 2.5D Renderer: QI Modular Stellarator --- */
function render2DStellarator(cx, cy, rotX, rotY, time) {
    const numCoils = 20;
    const majorR = 14.0;
    const minorR = 4.8;
    const isQuench = activeMode === 'MODE_HTS_COIL_HOTSPOT_QUENCH';
    const isDetachment = activeMode === 'MODE_DIVERTOR_DETACHMENT_FAULT';

    // 1. Draw 20 Modular Non-Planar HTS Coils
    if (showLayerCoils) {
        for (let i = 0; i < numCoils; i++) {
            const phi = (i / numCoils) * Math.PI * 2;
            const isQuenchCoil = (i === 0 && isQuench);

            fallbackCtx.beginPath();
            const segments = 32;
            for (let j = 0; j <= segments; j++) {
                const theta = (j / segments) * Math.PI * 2;
                const r = majorR + minorR * Math.cos(theta);
                const zTwist = Math.sin(theta * 2 + phi * 5) * 1.6;
                const x = r * Math.cos(phi) - Math.sin(phi) * 1.2 * Math.sin(theta * 2);
                const y = minorR * Math.sin(theta) + zTwist;
                const z = r * Math.sin(phi) + Math.cos(phi) * 1.2 * Math.sin(theta * 2);

                const proj = projectPoint(x, y, z, cx, cy, rotX, rotY, fallbackZoom);
                if (j === 0) fallbackCtx.moveTo(proj.x, proj.y);
                else fallbackCtx.lineTo(proj.x, proj.y);
            }

            if (isQuenchCoil) {
                const pulse = 0.5 + 0.5 * Math.sin(time * 16.0);
                fallbackCtx.strokeStyle = `rgba(255, 51, 102, ${0.8 + pulse * 0.2})`;
                fallbackCtx.lineWidth = 3.5;
                fallbackCtx.shadowBlur = 18;
                fallbackCtx.shadowColor = '#FF3366';
            } else {
                fallbackCtx.strokeStyle = 'rgba(0, 242, 254, 0.55)';
                fallbackCtx.lineWidth = 1.8;
                fallbackCtx.shadowBlur = 6;
                fallbackCtx.shadowColor = '#00F2FE';
            }
            fallbackCtx.stroke();
            fallbackCtx.shadowBlur = 0;
        }

        // Quench Spark Particles
        if (isQuench) {
            const hotspot = projectPoint(majorR + minorR, 0, 0, cx, cy, rotX, rotY, fallbackZoom);
            for (let s = 0; s < 12; s++) {
                const angle = time * 8.0 + s * (Math.PI / 6);
                const dist = 14 + 10 * Math.sin(time * 12.0 + s);
                fallbackCtx.fillStyle = '#FFE600';
                fallbackCtx.beginPath();
                fallbackCtx.arc(hotspot.x + Math.cos(angle) * dist, hotspot.y + Math.sin(angle) * dist, 2.5, 0, Math.PI * 2);
                fallbackCtx.fill();
            }
        }
    }

    // 2. Draw Helical Plasma Core Column
    if (showLayerPlasma) {
        fallbackCtx.beginPath();
        const plasmaSegs = 72;
        for (let p = 0; p <= plasmaSegs; p++) {
            const u = (p / plasmaSegs) * Math.PI * 2;
            const r = majorR;
            const y = 1.2 * Math.sin(u * 5);
            const x = r * Math.cos(u);
            const z = r * Math.sin(u);

            const proj = projectPoint(x, y, z, cx, cy, rotX, rotY, fallbackZoom);
            if (p === 0) fallbackCtx.moveTo(proj.x, proj.y);
            else fallbackCtx.lineTo(proj.x, proj.y);
        }
        fallbackCtx.strokeStyle = 'rgba(0, 242, 254, 0.85)';
        fallbackCtx.lineWidth = 6.0;
        fallbackCtx.shadowBlur = 22;
        fallbackCtx.shadowColor = '#00F2FE';
        fallbackCtx.stroke();
        fallbackCtx.shadowBlur = 0;
    }

    // 3. Draw Divertor Plates
    if (showLayerDivertor) {
        for (let d = 0; d < 5; d++) {
            const phi = (d / 5) * Math.PI * 2;
            const p1 = projectPoint(majorR * Math.cos(phi), -minorR * 1.1, majorR * Math.sin(phi), cx, cy, rotX, rotY, fallbackZoom);
            const p2 = projectPoint((majorR + 2.5) * Math.cos(phi), -minorR * 1.1, (majorR + 2.5) * Math.sin(phi), cx, cy, rotX, rotY, fallbackZoom);

            fallbackCtx.beginPath();
            fallbackCtx.moveTo(p1.x, p1.y);
            fallbackCtx.lineTo(p2.x, p2.y);
            fallbackCtx.strokeStyle = isDetachment ? '#FF9900' : '#4ADE80';
            fallbackCtx.lineWidth = 3.5;
            fallbackCtx.stroke();
        }
    }
}

/* --- 2.5D Renderer: Advanced Axisymmetric Tokamak --- */
function render2DTokamak(cx, cy, rotX, rotY, time) {
    const isDisruption = activeMode === 'MODE_TOKAMAK_MAJOR_DISRUPTION';
    const isVde = activeMode === 'MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT';

    // 1. Central Solenoid (Stacked Cylinder Rings)
    if (showLayerCoils) {
        fallbackCtx.strokeStyle = '#F59E0B';
        fallbackCtx.lineWidth = 2.0;
        for (let ringY = -10; ringY <= 10; ringY += 2.5) {
            fallbackCtx.beginPath();
            for (let a = 0; a <= 20; a++) {
                const ang = (a / 20) * Math.PI * 2;
                const p = projectPoint(2.8 * Math.cos(ang), ringY, 2.8 * Math.sin(ang), cx, cy, rotX, rotY, fallbackZoom);
                if (a === 0) fallbackCtx.moveTo(p.x, p.y);
                else fallbackCtx.lineTo(p.x, p.y);
            }
            fallbackCtx.stroke();
        }

        // 2. 16 D-Shaped Toroidal Field (TF) Coils
        const numTf = 16;
        for (let t = 0; t < numTf; t++) {
            const phi = (t / numTf) * Math.PI * 2;
            fallbackCtx.beginPath();

            // Inner vertical leg
            const pBot = projectPoint(4.0 * Math.cos(phi), -10, 4.0 * Math.sin(phi), cx, cy, rotX, rotY, fallbackZoom);
            const pTop = projectPoint(4.0 * Math.cos(phi), 10, 4.0 * Math.sin(phi), cx, cy, rotX, rotY, fallbackZoom);
            fallbackCtx.moveTo(pBot.x, pBot.y);
            fallbackCtx.lineTo(pTop.x, pTop.y);

            // Outer curved D arc
            for (let arc = 0; arc <= 16; arc++) {
                const th = -Math.PI / 2 + (arc / 16) * Math.PI;
                const rArc = 4.0 + 14.5 * Math.cos(th);
                const yArc = 10.0 * Math.sin(th);
                const pArc = projectPoint(rArc * Math.cos(phi), yArc, rArc * Math.sin(phi), cx, cy, rotX, rotY, fallbackZoom);
                fallbackCtx.lineTo(pArc.x, pArc.y);
            }
            fallbackCtx.lineTo(pBot.x, pBot.y);

            fallbackCtx.strokeStyle = 'rgba(0, 242, 254, 0.45)';
            fallbackCtx.lineWidth = 1.6;
            fallbackCtx.stroke();
        }

        // 3. Poloidal Field (PF) Ring Coils
        const pfConfigs = [{ r: 18, y: 11 }, { r: 18, y: -11 }, { r: 21, y: 3 }, { r: 21, y: -3 }];
        fallbackCtx.strokeStyle = '#38BDF8';
        fallbackCtx.lineWidth = 2.2;
        pfConfigs.forEach(pf => {
            fallbackCtx.beginPath();
            for (let a = 0; a <= 24; a++) {
                const ang = (a / 24) * Math.PI * 2;
                const p = projectPoint(pf.r * Math.cos(ang), pf.y, pf.r * Math.sin(ang), cx, cy, rotX, rotY, fallbackZoom);
                if (a === 0) fallbackCtx.moveTo(p.x, p.y);
                else fallbackCtx.lineTo(p.x, p.y);
            }
            fallbackCtx.stroke();
        });
    }

    // 4. Glowing Plasma Torus
    if (showLayerPlasma) {
        const vdeOffset = isVde ? 3.5 * Math.sin(time * 5.0) : 0;
        const majorR = 11.5;

        fallbackCtx.beginPath();
        for (let a = 0; a <= 48; a++) {
            const ang = (a / 48) * Math.PI * 2;
            const p = projectPoint(majorR * Math.cos(ang), vdeOffset, majorR * Math.sin(ang), cx, cy, rotX, rotY, fallbackZoom);
            if (a === 0) fallbackCtx.moveTo(p.x, p.y);
            else fallbackCtx.lineTo(p.x, p.y);
        }

        if (isDisruption) {
            const flash = Math.abs(Math.sin(time * 18.0));
            fallbackCtx.strokeStyle = `rgba(255, ${Math.floor(100 * flash)}, 50, 0.95)`;
            fallbackCtx.lineWidth = 4.0 + flash * 4.0;
            fallbackCtx.shadowBlur = 30;
            fallbackCtx.shadowColor = '#FF3366';
        } else {
            fallbackCtx.strokeStyle = 'rgba(0, 242, 254, 0.85)';
            fallbackCtx.lineWidth = 7.0;
            fallbackCtx.shadowBlur = 24;
            fallbackCtx.shadowColor = '#00F2FE';
        }
        fallbackCtx.stroke();
        fallbackCtx.shadowBlur = 0;

        // Disruption Electrical Filament Arcs
        if (isDisruption) {
            fallbackCtx.strokeStyle = '#FFFFFF';
            fallbackCtx.lineWidth = 2.0;
            for (let arc = 0; arc < 6; arc++) {
                const ang = arc * (Math.PI / 3) + time * 12.0;
                const p1 = projectPoint(majorR * Math.cos(ang), vdeOffset, majorR * Math.sin(ang), cx, cy, rotX, rotY, fallbackZoom);
                const p2 = projectPoint(17.5 * Math.cos(ang + 0.3), vdeOffset + 4 * Math.sin(time * 10), 17.5 * Math.sin(ang + 0.3), cx, cy, rotX, rotY, fallbackZoom);
                fallbackCtx.beginPath();
                fallbackCtx.moveTo(p1.x, p1.y);
                fallbackCtx.lineTo(p2.x, p2.y);
                fallbackCtx.stroke();
            }
        }
    }
}

/* --- 2.5D Renderer: Inertial Confinement Fusion (ICF) --- */
function render2DIcf(cx, cy, rotX, rotY, time) {
    const isRt = activeMode === 'MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY';
    const isMiss = activeMode === 'MODE_ICF_TARGET_TRACKING_INJECTION_MISS';

    // 1. Spherical Target Chamber Geodesic Rings
    if (showLayerDivertor) {
        fallbackCtx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
        fallbackCtx.lineWidth = 1.2;
        const sphereR = 19;

        // Equator ring
        fallbackCtx.beginPath();
        for (let a = 0; a <= 32; a++) {
            const ang = (a / 32) * Math.PI * 2;
            const p = projectPoint(sphereR * Math.cos(ang), 0, sphereR * Math.sin(ang), cx, cy, rotX, rotY, fallbackZoom);
            if (a === 0) fallbackCtx.moveTo(p.x, p.y);
            else fallbackCtx.lineTo(p.x, p.y);
        }
        fallbackCtx.stroke();

        // Meridian rings
        [0, Math.PI / 4, Math.PI / 2, 3 * Math.PI / 4].forEach(phi => {
            fallbackCtx.beginPath();
            for (let a = 0; a <= 32; a++) {
                const th = (a / 32) * Math.PI * 2;
                const p = projectPoint(sphereR * Math.sin(th) * Math.cos(phi), sphereR * Math.cos(th), sphereR * Math.sin(th) * Math.sin(phi), cx, cy, rotX, rotY, fallbackZoom);
                if (a === 0) fallbackCtx.moveTo(p.x, p.y);
                else fallbackCtx.lineTo(p.x, p.y);
            }
            fallbackCtx.stroke();
        });
    }

    // 2. 16 UV Laser Beams & 5 Hz Pulsed Microimplosions
    const pulseCycle = (time * 1.5) % 1.5; // 5 Hz pulse frequency cycle
    const isFiring = (pulseCycle < 0.22);
    const laserIntensity = isFiring ? (1.0 - pulseCycle / 0.22) : 0.25;

    // Target coordinate (off-center if miss)
    const targetX = isMiss ? 3.8 : 0;
    const targetY = isMiss ? 2.5 : 0;
    const targetZ = 0;
    const targetP = projectPoint(targetX, targetY, targetZ, cx, cy, rotX, rotY, fallbackZoom);

    if (showLayerCoils) {
        const numBeams = 16;
        for (let b = 0; b < numBeams; b++) {
            const phi = (b / numBeams) * Math.PI * 2;
            const theta = (b % 2 === 0) ? 0.8 : -0.8;
            const bx = 19 * Math.cos(theta) * Math.cos(phi);
            const by = 19 * Math.sin(theta);
            const bz = 19 * Math.cos(theta) * Math.sin(phi);

            const launchP = projectPoint(bx, by, bz, cx, cy, rotX, rotY, fallbackZoom);

            fallbackCtx.beginPath();
            fallbackCtx.moveTo(launchP.x, launchP.y);
            fallbackCtx.lineTo(targetP.x, targetP.y);

            if (isFiring) {
                fallbackCtx.strokeStyle = `rgba(0, 242, 254, ${0.4 + laserIntensity * 0.6})`;
                fallbackCtx.lineWidth = 1.5 + laserIntensity * 2.5;
                fallbackCtx.shadowBlur = 18;
                fallbackCtx.shadowColor = '#00F2FE';
            } else {
                fallbackCtx.strokeStyle = 'rgba(0, 242, 254, 0.2)';
                fallbackCtx.lineWidth = 1.0;
                fallbackCtx.shadowBlur = 0;
            }
            fallbackCtx.stroke();
            fallbackCtx.shadowBlur = 0;
        }
    }

    // 3. Cryogenic DT Fuel Pellet & Microimplosion Flash
    if (showLayerPlasma) {
        if (isFiring) {
            // High-energy blast flash
            const blastR = pulseCycle * 65.0 * (isRt ? 0.4 : 1.0);
            fallbackCtx.fillStyle = isRt ? 'rgba(255, 150, 50, 0.7)' : 'rgba(255, 255, 255, 0.9)';
            fallbackCtx.beginPath();
            fallbackCtx.arc(targetP.x, targetP.y, Math.max(3, blastR), 0, Math.PI * 2);
            fallbackCtx.fill();
        } else {
            // Quiescent cryogenic pellet
            fallbackCtx.fillStyle = isMiss ? '#FF3366' : '#E0F2FE';
            fallbackCtx.beginPath();
            fallbackCtx.arc(targetP.x, targetP.y, 4.5, 0, Math.PI * 2);
            fallbackCtx.fill();

            // Rayleigh-Taylor Asymmetric perturbation spikes
            if (isRt) {
                fallbackCtx.strokeStyle = '#FF3366';
                fallbackCtx.lineWidth = 2.0;
                for (let sp = 0; sp < 8; sp++) {
                    const ang = sp * (Math.PI / 4) + time * 3.0;
                    fallbackCtx.beginPath();
                    fallbackCtx.moveTo(targetP.x, targetP.y);
                    fallbackCtx.lineTo(targetP.x + Math.cos(ang) * 12, targetP.y + Math.sin(ang) * 12);
                    fallbackCtx.stroke();
                }
            }
        }
    }
}

/* --- Build QI Stellarator Procedural Model --- */
function buildStellaratorModel() {
    stellaratorGroup = new THREE.Group();
    stellaratorGroup.name = 'stellarator';

    // 1. Five-period modular non-planar HTS coils
    const numCoils = 20;
    const majorR = 14.0;
    const minorR = 4.8;

    const coilMaterial = new THREE.MeshStandardMaterial({
        color: 0x00F2FE,
        metalness: 0.85,
        roughness: 0.25,
        emissive: 0x002B3D,
        wireframe: false
    });

    for (let i = 0; i < numCoils; i++) {
        const phi = (i / numCoils) * Math.PI * 2;
        // Generate non-planar twisted coil path
        const points = [];
        const coilSegments = 64;
        for (let j = 0; j <= coilSegments; j++) {
            const theta = (j / coilSegments) * Math.PI * 2;
            // Out-of-plane sinusoidal distortion for quasi-isodynamic geometry
            const zTwist = Math.sin(theta * 2 + phi * 5) * 1.6;
            const rTwist = Math.cos(theta * 2 + phi * 5) * 1.2;

            const r = majorR + (minorR + rTwist) * Math.cos(theta);
            const x = r * Math.cos(phi + (theta * 0.1));
            const y = (minorR + rTwist) * Math.sin(theta) + zTwist;
            const z = r * Math.sin(phi + (theta * 0.1));
            points.push(new THREE.Vector3(x, y, z));
        }

        const curve = new THREE.CatmullRomCurve3(points);
        curve.closed = true;
        const tubeGeom = new THREE.TubeGeometry(curve, 64, 0.35, 8, true);
        const coilMesh = new THREE.Mesh(tubeGeom, coilMaterial.clone());
        coilMesh.userData = { layer: 'coils', coilId: i };

        // Mark Coil 3 as hotspot candidate
        if (i === 3) {
            coilMesh.name = 'quench_coil';
        }
        stellaratorGroup.add(coilMesh);
    }

    // 2. Helical Twisted Plasma Flux Surface (V3FIT Equilibrium)
    const plasmaGeom = new THREE.TorusGeometry(14.0, 3.2, 32, 100);
    const plasmaMat = new THREE.MeshPhysicalMaterial({
        color: 0x9D4EDD,
        emissive: 0x7B2CBF,
        emissiveIntensity: 0.6,
        roughness: 0.1,
        transmission: 0.65,
        thickness: 2.0,
        transparent: true,
        opacity: 0.85
    });
    const plasmaMesh = new THREE.Mesh(plasmaGeom, plasmaMat);
    plasmaMesh.rotation.x = Math.PI / 2;
    plasmaMesh.userData = { layer: 'plasma' };
    plasmaMesh.name = 'stellarator_plasma';
    stellaratorGroup.add(plasmaMesh);

    // 3. Island Divertor Target Plates
    const divertorMat = new THREE.MeshStandardMaterial({
        color: 0x5A6B7C,
        metalness: 0.7,
        roughness: 0.4
    });
    for (let k = 0; k < 5; k++) {
        const dAngle = (k / 5) * Math.PI * 2;
        const divPlate = new THREE.Mesh(new THREE.BoxGeometry(2.5, 0.4, 4.0), divertorMat);
        divPlate.position.set(Math.cos(dAngle) * 17.5, (k % 2 === 0 ? 3.0 : -3.0), Math.sin(dAngle) * 17.5);
        divPlate.rotation.y = -dAngle;
        divPlate.userData = { layer: 'divertor' };
        stellaratorGroup.add(divPlate);
    }

    // 4. Spark Particle System for Quench
    const sparkCount = 80;
    const sparkGeom = new THREE.BufferGeometry();
    const sparkPositions = new Float32Array(sparkCount * 3);
    for (let s = 0; s < sparkCount * 3; s++) sparkPositions[s] = (Math.random() - 0.5) * 4.0;
    sparkGeom.setAttribute('position', new THREE.BufferAttribute(sparkPositions, 3));
    const sparkMat = new THREE.PointsMaterial({ color: 0xFF3366, size: 0.6, transparent: true, opacity: 0 });
    quenchSparks = new THREE.Points(sparkGeom, sparkMat);
    quenchSparks.position.set(14.0, 2.0, 0);
    quenchSparks.name = 'quench_sparks';
    stellaratorGroup.add(quenchSparks);

    scene3D.add(stellaratorGroup);
}

/* --- Build Advanced Tokamak Procedural Model --- */
function buildTokamakModel() {
    tokamakGroup = new THREE.Group();
    tokamakGroup.name = 'tokamak';

    // 1. Central Solenoid Cylinder (Inductive Current Driver)
    const csGeom = new THREE.CylinderGeometry(2.8, 2.8, 22, 32);
    const csMat = new THREE.MeshStandardMaterial({
        color: 0xD4AF37,
        metalness: 0.9,
        roughness: 0.25,
        wireframe: false
    });
    const csMesh = new THREE.Mesh(csGeom, csMat);
    csMesh.userData = { layer: 'coils' };
    tokamakGroup.add(csMesh);

    // 2. D-Shaped Toroidal Field (TF) Coils (16 Coils)
    const numTf = 16;
    const tfMat = new THREE.MeshStandardMaterial({
        color: 0x4A90E2,
        metalness: 0.8,
        roughness: 0.3
    });

    for (let i = 0; i < numTf; i++) {
        const phi = (i / numTf) * Math.PI * 2;
        // Procedural D-curve
        const points = [];
        const segs = 48;
        for (let j = 0; j <= segs; j++) {
            const t = (j / segs) * Math.PI * 2;
            // D-shape parametric elongation
            const rInner = 3.6;
            const rOuter = 16.5;
            const h = 10.5;

            let xLocal, yLocal;
            if (Math.cos(t) <= 0) {
                // Straight inner leg near central solenoid
                xLocal = rInner;
                yLocal = (t > Math.PI ? 1 : -1) * (Math.abs(Math.sin(t)) * h);
            } else {
                // Outer curved D-belly
                xLocal = rInner + (rOuter - rInner) * Math.cos(t);
                yLocal = Math.sin(t) * h;
            }
            points.push(new THREE.Vector3(xLocal, yLocal, 0));
        }

        const curve = new THREE.CatmullRomCurve3(points);
        curve.closed = true;
        const tfGeom = new THREE.TubeGeometry(curve, 48, 0.45, 8, true);
        const tfMesh = new THREE.Mesh(tfGeom, tfMat);
        tfMesh.rotation.y = phi;
        tfMesh.userData = { layer: 'coils' };
        tokamakGroup.add(tfMesh);
    }

    // 3. Elongated D-Torus Plasma Core (Ip ~ 15 MA)
    const plasmaGeom = new THREE.TorusGeometry(10.5, 3.8, 32, 100);
    const plasmaMat = new THREE.MeshPhysicalMaterial({
        color: 0x00F2FE,
        emissive: 0x0088CC,
        emissiveIntensity: 0.7,
        roughness: 0.1,
        transmission: 0.6,
        thickness: 2.5,
        transparent: true,
        opacity: 0.9
    });
    const plasmaMesh = new THREE.Mesh(plasmaGeom, plasmaMat);
    plasmaMesh.rotation.x = Math.PI / 2;
    plasmaMesh.scale.set(1.0, 1.0, 1.6); // D-shaped vertical elongation kappa ~ 1.7
    plasmaMesh.userData = { layer: 'plasma' };
    plasmaMesh.name = 'tokamak_plasma';
    tokamakGroup.add(plasmaMesh);

    // 4. Poloidal Divertor Target Rings (Upper & Lower Single/Double Null)
    const divMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.6, roughness: 0.4 });
    const lowerDiv = new THREE.Mesh(new THREE.TorusGeometry(10.5, 0.8, 16, 64), divMat);
    lowerDiv.position.y = -6.8;
    lowerDiv.rotation.x = Math.PI / 2;
    lowerDiv.userData = { layer: 'divertor' };
    tokamakGroup.add(lowerDiv);

    const upperDiv = lowerDiv.clone();
    upperDiv.position.y = 6.8;
    upperDiv.userData = { layer: 'divertor' };
    tokamakGroup.add(upperDiv);

    scene3D.add(tokamakGroup);
}

/* --- Build Inertial Confinement Fusion (ICF) Procedural Model --- */
function buildIcfModel() {
    icfGroup = new THREE.Group();
    icfGroup.name = 'icf';

    // 1. Spherical Target Chamber Armor Shell
    const chamberGeom = new THREE.SphereGeometry(18.0, 32, 32);
    const chamberMat = new THREE.MeshStandardMaterial({
        color: 0x1E293B,
        metalness: 0.75,
        roughness: 0.35,
        wireframe: true,
        transparent: true,
        opacity: 0.35
    });
    const chamberMesh = new THREE.Mesh(chamberGeom, chamberMat);
    chamberMesh.userData = { layer: 'divertor' };
    icfGroup.add(chamberMesh);

    // 2. Converging Laser Beam Cones (16 UV Laser Beams pointing to (0,0,0))
    const beamCount = 16;
    const beamMat = new THREE.MeshBasicMaterial({
        color: 0x00F2FE,
        transparent: true,
        opacity: 0.45,
        wireframe: false
    });

    for (let b = 0; b < beamCount; b++) {
        const phi = Math.acos(-1 + (2 * b) / beamCount);
        const theta = Math.sqrt(beamCount * Math.PI) * phi;

        const dir = new THREE.Vector3(
            Math.cos(theta) * Math.sin(phi),
            Math.sin(theta) * Math.sin(phi),
            Math.cos(phi)
        ).normalize();

        const beamLength = 17.5;
        const coneGeom = new THREE.ConeGeometry(0.7, beamLength, 12, 1, true);
        const coneMesh = new THREE.Mesh(coneGeom, beamMat.clone());

        coneMesh.position.copy(dir.clone().multiplyScalar(beamLength / 2));
        coneMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), dir);
        coneMesh.userData = { layer: 'coils' };
        coneMesh.name = `laser_beam_${b}`;
        icfGroup.add(coneMesh);
    }

    // 3. Central Cryogenic DT Fuel Target Pellet (0,0,0)
    const pelletGeom = new THREE.SphereGeometry(1.6, 32, 32);
    const pelletMat = new THREE.MeshStandardMaterial({
        color: 0xFFD700,
        emissive: 0xFF8800,
        emissiveIntensity: 0.5,
        metalness: 0.8,
        roughness: 0.15
    });
    const pelletMesh = new THREE.Mesh(pelletGeom, pelletMat);
    pelletMesh.userData = { layer: 'plasma' };
    pelletMesh.name = 'icf_pellet';
    icfGroup.add(pelletMesh);

    // 4. Fusion Detonation Expansion Sphere Flash
    const blastGeom = new THREE.SphereGeometry(2.0, 32, 32);
    const blastMat = new THREE.MeshBasicMaterial({
        color: 0xFFFFFF,
        transparent: true,
        opacity: 0
    });
    const blastMesh = new THREE.Mesh(blastGeom, blastMat);
    blastMesh.name = 'icf_blast';
    icfGroup.add(blastMesh);

    scene3D.add(icfGroup);
}

function switch3DReactorModel(reactorId) {
    if (stellaratorGroup) stellaratorGroup.visible = (reactorId === 'REACTOR_QI_STELLARATOR');
    if (tokamakGroup) tokamakGroup.visible = (reactorId === 'REACTOR_TOKAMAK');
    if (icfGroup) icfGroup.visible = (reactorId === 'REACTOR_ICF');

    if (reactorId === 'REACTOR_QI_STELLARATOR') currentReactorGroup = stellaratorGroup;
    else if (reactorId === 'REACTOR_TOKAMAK') currentReactorGroup = tokamakGroup;
    else if (reactorId === 'REACTOR_ICF') currentReactorGroup = icfGroup;

    // Update Header Titles
    const titleEl = document.getElementById('canvas-reactor-title');
    const badgeEl = document.getElementById('twin-topology-badge');
    const infoEl = document.getElementById('twin-physics-info');

    if (reactorId === 'REACTOR_TOKAMAK') {
        if (titleEl) titleEl.textContent = '3D TWIN: ADVANCED AXISYMMETRIC TOKAMAK';
        if (badgeEl) badgeEl.textContent = 'TOKAMAK-CS';
        if (infoEl) infoEl.innerHTML = '<strong>Inductive Confinement:</strong> Central Solenoid drives toroidal plasma current $I_p \\approx 15\\text{ MA}$ creating poloidal field, with D-shaped TF coils stabilizing high-beta equilibria.';
    } else if (reactorId === 'REACTOR_ICF') {
        if (titleEl) titleEl.textContent = '3D TWIN: INERTIAL CONFINEMENT FUSION (ICF)';
        if (badgeEl) badgeEl.textContent = 'ICF-LASER';
        if (infoEl) infoEl.innerHTML = '<strong>Inertial Microimplosions:</strong> 16 UV laser beams converge on cryogenic DT fuel capsule at 5 Hz, compressing fuel to $>1000\\times$ solid density with target gain $G = 85$.';
    } else {
        if (titleEl) titleEl.textContent = '3D TWIN: QI MODULAR STELLARATOR';
        if (badgeEl) badgeEl.textContent = 'QI-HTS';
        if (infoEl) infoEl.innerHTML = '<strong>Quasi-Isodynamic Optimization:</strong> Modular coils produce omnigenous magnetic surfaces with zero net current, eliminating disruptions and 1/nu ripple losses.';
    }
}

function update3DAlertBanner(modeId, isAlert) {
    const banner = document.getElementById('threejs-alert-banner');
    const text = document.getElementById('threejs-alert-text');
    const subTitle = document.getElementById('canvas-mode-subtitle');

    if (!banner || !text) return;

    if (subTitle) subTitle.textContent = `Mode: ${modeId.replace('MODE_', '').replace('TOKAMAK_', '').replace('ICF_', '')}`;

    if (isAlert) {
        banner.style.display = 'flex';
        const alertMessages = {
            'MODE_HTS_COIL_HOTSPOT_QUENCH': '⚡ HTS REBCO HOTSPOT QUENCH: Acoustic stress > 25 kHz, fast discharge dump active!',
            'MODE_DIVERTOR_DETACHMENT_FAULT': '🔥 DIVERTOR ATTACHMENT FAULT: Heat flux surging past 10 MW/m² limit to ~16.8 MW/m²!',
            'MODE_TOKAMAK_MAJOR_DISRUPTION': '⚡ MAJOR DISRUPTION: Thermal quench (<1ms) & 185V inductive loop voltage spike!',
            'MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT': '↕️ VERTICAL DISPLACEMENT EVENT: Axisymmetric Delta-Z surge >40mm into vessel!',
            'MODE_TOKAMAK_UNMITIGATED_ELM_BURST': '💥 TYPE-I ELM BURST: Pedestal collapse, divertor peak heat flux spikes to 16.4 MW/m²!',
            'MODE_TOKAMAK_RUNAWAY_ELECTRON_AVALANCHE': '☢️ RUNAWAY ELECTRON AVALANCHE: Relativistic 3.8 MA beam wall collision warning!',
            'MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY': '🌊 RAYLEIGH-TAYLOR INSTABILITY: Mix fingers penetrate fuel hotspot, target gain collapses 90%!',
            'MODE_ICF_TARGET_TRACKING_INJECTION_MISS': '❌ TARGET INJECTION MISS: Pellet off-center >40μm, dud ignition shot!'
        };
        text.textContent = alertMessages[modeId] || `ANOMALY ALERT: ${modeId}`;
    } else {
        banner.style.display = 'none';
    }
}

function update3DPhysicsStats(sub1, sub2, sub3, sub4, sub5) {
    if (activeReactor === 'REACTOR_TOKAMAK') {
        setEl('stat-1-name', 'Plasma Current (I_p)');
        setEl('stat-1-val', sub2.status.includes('Ip=') ? sub2.status.split('|')[0].trim() : '15.0 MA');
        setEl('stat-2-name', 'Safety Factor (q_95)');
        setEl('stat-2-val', '3.25');
        setEl('stat-3-name', 'Peak Magnet Stress');
        setEl('stat-3-val', sub1.stress);
        setEl('stat-4-name', 'Loop Voltage (V_loop)');
        setEl('stat-4-val', activeMode.includes('DISRUPTION') ? '185.0 V (SPIKE)' : '0.12 V');
        setEl('stat-5-name', 'Disruption Alarm');
        setEl('stat-5-val', activeMode.includes('DISRUPTION') || activeMode.includes('VDE') ? 'TRIPPED' : 'CLEAR');
    } else if (activeReactor === 'REACTOR_ICF') {
        setEl('stat-1-name', 'Driver Energy (E_laser)');
        setEl('stat-1-val', '2.15 MJ');
        setEl('stat-2-name', 'Repetition Rate');
        setEl('stat-2-val', '5.0 Hz');
        setEl('stat-3-name', 'Target Gain (G)');
        setEl('stat-3-val', sub5.qsci);
        setEl('stat-4-name', 'Implosion Symmetry RMS');
        setEl('stat-4-val', activeMode.includes('TAYLOR') ? '4.8% (ASYMMETRIC)' : '0.65%');
        setEl('stat-5-name', 'Rayleigh-Taylor Alert');
        setEl('stat-5-val', activeMode.includes('TAYLOR') ? 'TRIPPED' : 'QUIESCENT');
    } else {
        setEl('stat-1-name', 'Toroidal Beta (β)');
        setEl('stat-1-val', sub2.beta);
        setEl('stat-2-name', 'Magnetic Axis Shift');
        setEl('stat-2-val', '+1.82 mm');
        setEl('stat-3-name', 'Peak Magnet Stress');
        setEl('stat-3-val', sub1.stress);
        setEl('stat-4-name', 'PINN Residual Loss');
        setEl('stat-4-val', '0.00124');
        setEl('stat-5-name', 'Equilibrium Status');
        setEl('stat-5-val', 'CONVERGED');
    }
}

function animate3D() {
    animReq3D = requestAnimationFrame(animate3D);

    if (controls3D) controls3D.update();

    const time = Date.now() * 0.001;

    // 1. Stellarator Animation
    if (stellaratorGroup && stellaratorGroup.visible) {
        stellaratorGroup.rotation.y += 0.003;

        // Quench Visual FX
        const quenchCoil = stellaratorGroup.getObjectByName('quench_coil');
        const isQuench = activeMode === 'MODE_HTS_COIL_HOTSPOT_QUENCH';

        if (quenchCoil) {
            if (isQuench) {
                const pulse = 0.5 + 0.5 * Math.sin(time * 12.0);
                quenchCoil.material.color.setRGB(1.0, 0.1, 0.1);
                quenchCoil.material.emissive.setRGB(pulse, 0.0, 0.0);
            } else {
                quenchCoil.material.color.setHex(0x00F2FE);
                quenchCoil.material.emissive.setHex(0x002B3D);
            }
        }

        if (quenchSparks) {
            quenchSparks.material.opacity = isQuench ? (0.6 + 0.4 * Math.sin(time * 20.0)) : 0;
            if (isQuench) quenchSparks.rotation.y += 0.05;
        }
    }

    // 2. Tokamak Animation
    if (tokamakGroup && tokamakGroup.visible) {
        tokamakGroup.rotation.y += 0.002;

        const plasma = tokamakGroup.getObjectByName('tokamak_plasma');
        const isDisruption = activeMode === 'MODE_TOKAMAK_MAJOR_DISRUPTION';
        const isVde = activeMode === 'MODE_TOKAMAK_VERTICAL_DISPLACEMENT_EVENT';

        if (plasma) {
            if (isDisruption) {
                const flash = Math.abs(Math.sin(time * 15.0));
                plasma.material.color.setRGB(flash, flash * 0.5, flash * 0.2);
                plasma.material.emissive.setRGB(flash, flash * 0.2, 0.1);
                plasma.scale.set(0.6, 0.6, 0.8);
            } else if (isVde) {
                plasma.position.y = 2.5 * Math.sin(time * 4.0);
                plasma.scale.set(1.0, 1.0, 1.6);
            } else {
                plasma.position.y = 0;
                plasma.scale.set(1.0, 1.0, 1.6);
                plasma.material.color.setHex(0x00F2FE);
                plasma.material.emissive.setHex(0x0088CC);
            }
        }
    }

    // 3. ICF Animation
    if (icfGroup && icfGroup.visible) {
        icfPulseTimer += 0.035;

        const pellet = icfGroup.getObjectByName('icf_pellet');
        const blast = icfGroup.getObjectByName('icf_blast');
        const isRt = activeMode === 'MODE_ICF_RAYLEIGH_TAYLOR_ASYMMETRY';

        // 5 Hz pulsed firing tempo
        const cycle = icfPulseTimer % 1.5; // Every 1.5 seconds a pulse arrives
        if (cycle < 0.2) {
            // Laser beam flare & compression
            const intensity = 1.0 - (cycle / 0.2);
            for (let b = 0; b < 16; b++) {
                const beam = icfGroup.getObjectByName(`laser_beam_${b}`);
                if (beam) beam.material.opacity = 0.3 + intensity * 0.7;
            }
            if (pellet) {
                const s = 1.6 * (1.0 - intensity * 0.6);
                pellet.scale.set(s, isRt ? s * 1.5 : s, s);
            }
            if (blast) {
                blast.scale.set(cycle * 15.0, cycle * 15.0, cycle * 15.0);
                blast.material.opacity = isRt ? (1.0 - cycle * 5.0) * 0.2 : (1.0 - cycle * 5.0) * 0.9;
            }
        } else {
            for (let b = 0; b < 16; b++) {
                const beam = icfGroup.getObjectByName(`laser_beam_${b}`);
                if (beam) beam.material.opacity = 0.35;
            }
            if (pellet) pellet.scale.set(1.0, 1.0, 1.0);
            if (blast) blast.material.opacity = 0;
        }

        icfGroup.rotation.y += 0.0015;
    }

    if (renderer3D && scene3D && camera3D) {
        renderer3D.render(scene3D, camera3D);
    }
}

/* ========================================================================== */
/* 6. Purdue 6-Tier Architecture Inspector                                   */
/* ========================================================================== */
const PURDUE_DATA = {
    5: {
        title: "Level 5: Enterprise Agentic AI & Multi-Physics Query API",
        file: "data_lake_api/ai_ingestion_api.py",
        desc: "Provides isolated read-only REST (/api/v1/reactors, /api/v1/subsystems/latest) and Strawberry GraphQL (/graphql) endpoints. Enables Agentic AI models to query multi-reactor historical telemetry, disruption precursors, and 3D equilibrium flux reconstructions for training.",
        security: "IEC 62443 Zone 5 - Read-Only Isolated Subnet. Zero direct back-propagation into real-time control loops."
    },
    4: {
        title: "Level 4: Plant Management & Digital Twin Data Lake",
        file: "digital_twin/digital_twin_engine.py & tami_data_lake.h5",
        desc: "Executes a PyTorch Physics-Informed Neural Network (PINN) surrogate model reconstructing 3D flux surface mesh (R, Z, Phi), toroidal beta, and Lorentz strain for Stellarators, Tokamaks, and ICF. Persists high-volume time-series telemetry into HDF5 datasets.",
        security: "IEC 62443 Zone 4 - Streaming Kafka Egress Conduit from Level 3."
    },
    3: {
        title: "Level 3: TAMI Supervisory Control Middleware Hub",
        file: "middleware_hub/src/main.rs (Rust)",
        desc: "High-throughput supervisory routing hub. Validates Protobuf envelopes with cryptographic tokens, verifies monotonically increasing sequence numbers, enforces token-bucket rate limiting (100 msgs/sec), and bridges DDS to Kafka.",
        security: "IEC 62443 Zone 3 - Zero-Trust Security Token Verification."
    },
    2: {
        title: "Level 2: Area Control & Magnet Power Supply PLCs",
        file: "DDS Real-time Area Control Zone",
        desc: "Manages deterministic magnet power supplies (TF/PF/CS coils), cryogenic liquid helium pumps, pellet injection pneumatic railguns, and laser bank capacitors.",
        security: "IEC 62443 Zone 2 - Deterministic Real-time Control Network."
    },
    1: {
        title: "Level 1: Edge Quench & Disruption Interlock (MTCA.4 FPGA)",
        file: "edge_quench/src/main.rs (Rust)",
        desc: "Zero-allocation microsecond safety kernel. Subscribes directly to high-frequency FOAS acoustic sensing (>25 kHz), stray capacitance (dC/dt), and Tokamak locked-mode magnetic pick-up coils. Triggers fast dump breakers in < 50 microseconds!",
        security: "IEC 62443 Level 1 - Direct Hardwired Actuator Safety Zone."
    },
    0: {
        title: "Level 0: Physical Fusion Reactor Hardware & Sensors",
        file: "REBCO Coils, Central Solenoid, Laser Driver, Diagnostics",
        desc: "Physical superconducting magnets carrying >10,000A at 20 Kelvin, cryogenic DT target injectors, and optical debris shields.",
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
    const l1 = document.querySelector('.purdue-card.level-1');
    if (l1) l1.click();
}

/* ========================================================================== */
/* 7. Tutorial Viewer Initialization: KaTeX Math & Mermaid Diagrams          */
/* ========================================================================== */
function initMarkdownTutorial() {
    renderMermaidDiagrams();
    renderMathFormulas();
}

function renderMathFormulas() {
    if (!window.katex) return;

    const root = document.getElementById('markdown-viewer') || document.body;

    // 1. Try official KaTeX auto-render extension first
    if (typeof window.renderMathInElement === 'function') {
        try {
            window.renderMathInElement(root, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false }
                ],
                throwOnError: false,
                ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"]
            });
            return;
        } catch (e) {
            console.warn("KaTeX auto-render notice:", e);
        }
    }

    // 2. Render display math cards directly
    document.querySelectorAll('.math-card').forEach(el => {
        if (el.getAttribute('data-math-rendered') === 'true') return;
        const raw = el.textContent.trim();
        const formula = raw.replace(/^\$\$/g, '').replace(/\$\$$/g, '').trim();
        try {
            katex.render(formula, el, {
                displayMode: true,
                throwOnError: false
            });
            el.setAttribute('data-math-rendered', 'true');
        } catch (e) {
            console.warn("KaTeX display render notice:", e);
        }
    });

    // 3. Render inline math safely
    const walker = document.createTreeWalker(
        root,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );

    const nodesToReplace = [];
    let node;
    while ((node = walker.nextNode())) {
        if (node.nodeValue && node.nodeValue.includes('$')) {
            if (!node.parentElement.closest('.math-card') && 
                !node.parentElement.closest('.mermaid') && 
                !node.parentElement.closest('pre') && 
                !node.parentElement.closest('code')) {
                nodesToReplace.push(node);
            }
        }
    }

    nodesToReplace.forEach(textNode => {
        const text = textNode.nodeValue;
        if (!/\$([^\$\n]+?)\$/.test(text)) return;

        const span = document.createElement('span');
        span.innerHTML = text.replace(/\$([^\$\n]+?)\$/g, (match, formula) => {
            try {
                return katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false });
            } catch (err) {
                return match;
            }
        });
        textNode.parentNode.replaceChild(span, textNode);
    });
}

async function renderMermaidDiagrams() {
    if (!window.mermaid) return;

    try {
        mermaid.initialize({
            startOnLoad: false,
            theme: 'default',
            securityLevel: 'loose',
            themeVariables: {
                fontFamily: "'Inter', sans-serif",
                fontSize: '13px',
                primaryColor: '#F0F9FF',
                primaryBorderColor: '#0284C7',
                primaryTextColor: '#0F172A',
                lineColor: '#0284C7',
                secondaryColor: '#F8FAFC',
                secondaryBorderColor: '#94A3B8',
                secondaryTextColor: '#1E293B',
                tertiaryColor: '#FFFFFF',
                tertiaryBorderColor: '#CBD5E1',
                tertiaryTextColor: '#334155'
            }
        });

        const elements = document.querySelectorAll('.mermaid:not([data-processed="true"])');
        for (const el of elements) {
            try {
                if (typeof mermaid.run === 'function') {
                    await mermaid.run({ nodes: [el] });
                    el.setAttribute('data-processed', 'true');
                } else if (typeof mermaid.init === 'function') {
                    mermaid.init(undefined, el);
                    el.setAttribute('data-processed', 'true');
                }
            } catch (diagErr) {
                console.warn("Mermaid diagram render notice:", diagErr);
                el.setAttribute('data-processed', 'true');
            }
        }
    } catch (err) {
        console.warn("Mermaid render notice:", err);
    }
}
