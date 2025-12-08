const streamImg = document.getElementById('screen-stream');
const surface = document.getElementById('control-surface');
const refreshBtn = document.getElementById('refresh-stream');
const wakeBtn = document.getElementById('wake-display');
const cursorIndicator = document.getElementById('cursor-indicator');
const statusBanner = document.getElementById('status-banner');

if (!streamImg || !surface) {
    console.error('Remote desktop dashboard failed to load required elements.');
} else {
    let statusTimer;
    const state = {
        inputArmed: false,
        lastMoveTs: 0,
        lastFrameTs: Date.now(),
        tipShown: false,
        agentLastStatus: null,
    };
    const agentEnabled = Boolean(window.AGENT_ENABLED === true || window.AGENT_ENABLED === 'true');

    const showStatus = (message, { autoHideMs } = {}) => {
        if (!statusBanner) return;
        statusBanner.textContent = message;
        statusBanner.hidden = false;
        if (statusTimer) clearTimeout(statusTimer);
        if (autoHideMs) {
            statusTimer = setTimeout(() => {
                statusBanner.hidden = true;
            }, autoHideMs);
        }
    };

    const hideStatus = () => {
        if (!statusBanner) return;
        statusBanner.hidden = true;
        if (statusTimer) clearTimeout(statusTimer);
    };

    const sendEvent = async (payload) => {
        try {
            await fetch('/api/input', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload),
            });
        } catch (err) {
            console.error('Failed sending event', err);
            showStatus('Input channel lost. Reconnecting…', { autoHideMs: 3000 });
            throw err;
        }
    };

    const transmit = (payload) => {
        sendEvent(payload).catch(() => {});
    };

    const clamp = (value) => Math.min(Math.max(value, 0), 1);

    const normalize = (event) => {
        const rect = surface.getBoundingClientRect();
        const width = rect.width || 1;
        const height = rect.height || 1;
        const x = (event.clientX - rect.left) / width;
        const y = (event.clientY - rect.top) / height;
        return {
            x: clamp(x),
            y: clamp(y),
        };
    };

    const setCursorIndicator = (pos, mode) => {
        if (!cursorIndicator) return;
        if (pos) {
            cursorIndicator.style.left = `${pos.x * 100}%`;
            cursorIndicator.style.top = `${pos.y * 100}%`;
            cursorIndicator.classList.add('cursor-visible');
        } else {
            cursorIndicator.classList.remove('cursor-visible');
        }
        cursorIndicator.classList.remove('cursor-hover', 'cursor-click');
        if (mode) {
            cursorIndicator.classList.add(mode);
        }
    };

    const setSurfaceFlags = ({ armed, hover, clicking } = {}) => {
        if (typeof armed === 'boolean') surface.classList.toggle('surface-armed', armed);
        if (typeof hover === 'boolean') surface.classList.toggle('is-hovering', hover);
        if (typeof clicking === 'boolean') surface.classList.toggle('is-clicking', clicking);
    };

    const armInput = () => {
        state.inputArmed = true;
        setSurfaceFlags({ armed: true });
        surface.focus({ preventScroll: true });
    };

    const disarmInput = () => {
        state.inputArmed = false;
        setSurfaceFlags({ armed: false, clicking: false, hover: false });
        setCursorIndicator(null);
    };

    const isInputActive = () => {
        if (!document.hasFocus()) return false;
        return state.inputArmed || surface === document.activeElement || surface.matches(':hover');
    };

    let reconnectTimer;
    const refreshStream = ({ silent = false } = {}) => {
        if (!silent) {
            showStatus('Refreshing stream…');
        }
        streamImg.src = `/stream?_=${Date.now()}`;
        state.lastFrameTs = Date.now();
        if (reconnectTimer) clearTimeout(reconnectTimer);
    };

    const checkAgentHealth = async () => {
        if (!agentEnabled) return;
        try {
            const response = await fetch('/api/agent/health', { credentials: 'include' });
            const data = await response.json();
            if (response.ok) {
                if (state.agentLastStatus !== 'ok') {
                    showStatus('Host agent online', { autoHideMs: 2000 });
                    state.agentLastStatus = 'ok';
                }
            } else {
                throw new Error(data.detail || 'Agent unhealthy');
            }
        } catch (err) {
            if (state.agentLastStatus !== 'error') {
                showStatus('Host agent unreachable', { autoHideMs: 5000 });
                state.agentLastStatus = 'error';
            }
        }
    };

    const wakeHost = async (auto = false) => {
        if (!auto) {
            showStatus('Sending wake signal…');
        }
        try {
            const response = await fetch('/api/host/wake', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
            });
            const data = await response.json();
            armInput();
            if (!auto) {
                showStatus(data.message || 'Wake signal sent. Waiting for frames…', { autoHideMs: 4000 });
            }
            return true;
        } catch (err) {
            console.error('Wake request failed', err);
            if (!auto) {
                showStatus('Wake failed. Ensure host permissions allow it.', { autoHideMs: 5000 });
            }
            return false;
        }
    };

    // Auto-wake detection: check if stream appears black/idle
    let blackScreenCheckCount = 0;
    const checkBlackScreen = () => {
        if (!streamImg.complete || streamImg.naturalWidth === 0) return;
        
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = Math.min(streamImg.naturalWidth, 100);
        canvas.height = Math.min(streamImg.naturalHeight, 100);
        
        try {
            ctx.drawImage(streamImg, 0, 0, canvas.width, canvas.height);
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const pixels = imageData.data;
            let darkPixels = 0;
            
            for (let i = 0; i < pixels.length; i += 4) {
                const r = pixels[i];
                const g = pixels[i + 1];
                const b = pixels[i + 2];
                const brightness = (r + g + b) / 3;
                if (brightness < 10) darkPixels++;
            }
            
            const darkRatio = darkPixels / (pixels.length / 4);
            if (darkRatio > 0.95 && Date.now() - state.lastFrameTs > 3000) {
                blackScreenCheckCount++;
                if (blackScreenCheckCount >= 3) {
                    console.log('Detected black screen, auto-waking...');
                    wakeHost(true);
                    blackScreenCheckCount = 0;
                }
            } else {
                blackScreenCheckCount = 0;
            }
        } catch (err) {
            // Canvas may fail due to CORS, ignore
        }
    };

    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => refreshStream());
    }

    if (wakeBtn) {
        wakeBtn.addEventListener('click', wakeHost);
    }

    surface.addEventListener('mouseenter', (event) => {
        setSurfaceFlags({ hover: true });
        setCursorIndicator(normalize(event), 'cursor-hover');
    });

    surface.addEventListener('mouseleave', () => {
        setSurfaceFlags({ hover: false, clicking: false });
        setCursorIndicator(null);
        if (!surface.matches(':focus')) {
            state.inputArmed = false;
        }
    });

    surface.addEventListener('mousemove', (event) => {
        const now = Date.now();
        if (now - state.lastMoveTs < 40) return;
        state.lastMoveTs = now;
        const pos = normalize(event);
        setCursorIndicator(pos, surface.classList.contains('is-clicking') ? 'cursor-click' : undefined);
        transmit({ type: 'mouse', action: 'move', ...pos });
    });

    surface.addEventListener('pointerdown', (event) => {
        if (event.detail > 1) return;
        event.preventDefault();
        armInput();
        setSurfaceFlags({ clicking: true });
        const pos = normalize(event);
        setCursorIndicator(pos, 'cursor-click');
        transmit({ type: 'mouse', action: 'move', ...pos });
        const buttonMap = ['left', 'middle', 'right'];
        const button = buttonMap[event.button] || 'left';
        transmit({ type: 'mouse', action: 'click', button });
    });

    surface.addEventListener('pointerup', (event) => {
        setSurfaceFlags({ clicking: false });
        if (surface.matches(':hover')) {
            setCursorIndicator(normalize(event), 'cursor-hover');
        } else {
            setCursorIndicator(null);
        }
    });

    surface.addEventListener('contextmenu', (event) => {
        event.preventDefault();
        armInput();
        const pos = normalize(event);
        setCursorIndicator(pos, 'cursor-click');
        transmit({ type: 'mouse', action: 'move', ...pos });
        transmit({ type: 'mouse', action: 'click', button: 'right' });
    });

    surface.addEventListener('dblclick', (event) => {
        event.preventDefault();
        const pos = normalize(event);
        setCursorIndicator(pos, 'cursor-click');
        transmit({ type: 'mouse', action: 'move', ...pos });
        transmit({ type: 'mouse', action: 'click', button: 'left', double: true });
    });

    surface.addEventListener('wheel', (event) => {
        event.preventDefault();
        const pos = normalize(event);
        setCursorIndicator(pos);
        transmit({ type: 'mouse', action: 'scroll', deltaY: event.deltaY });
    });

    const handleKey = (event, eventType) => {
        if (!isInputActive()) return;
        event.preventDefault();
        transmit({ type: 'keyboard', key: event.key, code: event.code, eventType });
    };

    document.addEventListener('keydown', (event) => handleKey(event, 'down'));
    document.addEventListener('keyup', (event) => handleKey(event, 'up'));
    window.addEventListener('blur', () => disarmInput());

    streamImg.addEventListener('load', () => {
        state.lastFrameTs = Date.now();
        blackScreenCheckCount = 0; // Reset on successful load
        if (!state.tipShown) {
            state.tipShown = true;
            showStatus('Tip: Keep the host awake/plugged in for best results.', { autoHideMs: 7000 });
        } else {
            hideStatus();
        }
        // Check for black screen after load
        setTimeout(checkBlackScreen, 1000);
    });

    streamImg.addEventListener('error', () => {
        showStatus('Stream unreachable. Retrying…');
        reconnectTimer = setTimeout(() => refreshStream({ silent: true }), 1500);
    });

    setInterval(() => {
        if (Date.now() - state.lastFrameTs > 7000) {
            showStatus('Stream idle. Attempting to reconnect…');
            refreshStream({ silent: true });
        }
        // Periodic black screen check
        checkBlackScreen();
    }, 4000);

    window.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            refreshStream({ silent: true });
            checkAgentHealth();
        }
    });

    window.addEventListener('load', () => {
        refreshStream();
        setTimeout(() => armInput(), 350);
        if (agentEnabled) {
            checkAgentHealth();
            setInterval(checkAgentHealth, 15000);
        }
    });
}
