from __future__ import annotations

import io
import subprocess
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from ipaddress import ip_network, ip_address

import mss
from PIL import Image
from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pynput import keyboard, mouse

import config

try:
    import agent_client
except Exception:  # pragma: no cover - agent optional
    agent_client = None

USE_AGENT = bool(config.AGENT_ENABLED and agent_client is not None)

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY

mouse_controller = mouse.Controller()
keyboard_controller = keyboard.Controller()

login_attempts = defaultdict(list)
screen_lock = threading.Lock()
active_sessions = set()
keep_alive_running = threading.Event()
keep_alive_running.set()


def keep_alive_worker():
    """Background thread to prevent system sleep during active sessions."""
    while keep_alive_running.is_set():
        if active_sessions:
            try:
                # Try X11 DPMS keep-alive
                subprocess.run(
                    ['xset', 's', 'reset'],
                    timeout=2,
                    capture_output=True
                )
                # Try systemd inhibit (if available)
                subprocess.run(
                    ['loginctl', 'unlock-sessions'],
                    timeout=2,
                    capture_output=True
                )
            except Exception:
                pass
            if USE_AGENT:
                try:
                    agent_client.keep_alive()
                except Exception:
                    pass
        time.sleep(config.KEEP_ALIVE_INTERVAL)


keep_alive_thread = threading.Thread(target=keep_alive_worker, daemon=True)
keep_alive_thread.start()

try:
    with mss.mss() as sct:
        PRIMARY_MONITOR = sct.monitors[0]
        SCREEN_WIDTH = PRIMARY_MONITOR['width']
        SCREEN_HEIGHT = PRIMARY_MONITOR['height']
        SCREEN_LEFT = PRIMARY_MONITOR.get('left', 0)
        SCREEN_TOP = PRIMARY_MONITOR.get('top', 0)
except Exception as exc:  # pragma: no cover
    raise RuntimeError('Unable to initialize screen capture') from exc


def is_ip_allowed(addr: str) -> bool:
    try:
        ip = ip_address(addr)
    except ValueError:
        return False

    for network in config.ALLOWED_SUBNETS:
        try:
            if ip in ip_network(network.strip()):
                return True
        except ValueError:
            continue
    return False


@app.before_request
def restrict_networks():
    remote_addr = request.remote_addr or '127.0.0.1'
    if not is_ip_allowed(remote_addr):
        abort(403)


def purge_attempts(ip: str) -> None:
    window_start = datetime.utcnow() - timedelta(seconds=config.RATE_LIMIT_WINDOW)
    login_attempts[ip] = [ts for ts in login_attempts[ip] if ts >= window_start]


def record_attempt(ip: str) -> None:
    login_attempts[ip].append(datetime.utcnow())


def is_rate_limited(ip: str) -> bool:
    purge_attempts(ip)
    return len(login_attempts[ip]) >= config.RATE_LIMIT_ATTEMPTS


def authenticated() -> bool:
    return session.get('authenticated', False)


@app.route('/', methods=['GET', 'POST'])
def login():
    remote_addr = request.remote_addr or '127.0.0.1'
    error = None

    if request.method == 'POST':
        if is_rate_limited(remote_addr):
            error = 'Too many attempts. Please wait and try again.'
        else:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()

            if username == config.USERNAME and password == config.PASSWORD:
                session['authenticated'] = True
                login_attempts.pop(remote_addr, None)
                return redirect(url_for('dashboard'))
            else:
                record_attempt(remote_addr)
                error = 'Invalid username or password.'

    if authenticated():
        return redirect(url_for('dashboard'))

    return render_template('login.html', error=error)


@app.route('/dashboard')
def dashboard():
    if not authenticated():
        return redirect(url_for('login'))
    # Mark session as active for keep-alive
    session_id = session.get('_id', id(session))
    active_sessions.add(session_id)
    return render_template(
        'dashboard.html',
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        agent_enabled=USE_AGENT,
    )


def capture_frame() -> bytes:
    with screen_lock:
        with mss.mss() as sct:
            frame = sct.grab(PRIMARY_MONITOR)
        image = Image.frombytes('RGB', frame.size, frame.rgb)
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=config.IMAGE_QUALITY, optimize=True)
        return buffer.getvalue()


@app.route('/stream')
def stream():
    if not authenticated():
        return abort(401)
    
    # Mark session as active
    session_id = session.get('_id', id(session))
    active_sessions.add(session_id)

    def generate():
        while True:
            try:
                frame = capture_frame()
                active_sessions.add(session_id)  # Keep session active
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(config.CAPTURE_INTERVAL)
            except Exception:
                break
        active_sessions.discard(session_id)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


def clamp_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))


MOUSE_BUTTON_MAP = {
    'left': mouse.Button.left,
    'right': mouse.Button.right,
    'middle': mouse.Button.middle,
}

SPECIAL_KEYS = {
    'enter': keyboard.Key.enter,
    'esc': keyboard.Key.esc,
    'escape': keyboard.Key.esc,
    'tab': keyboard.Key.tab,
    'backspace': keyboard.Key.backspace,
    'delete': keyboard.Key.delete,
    'space': keyboard.Key.space,
    'shift': keyboard.Key.shift,
    'ctrl': keyboard.Key.ctrl,
    'alt': keyboard.Key.alt,
    'cmd': keyboard.Key.cmd,
    'win': keyboard.Key.cmd,
    'meta': keyboard.Key.cmd,
    'up': keyboard.Key.up,
    'down': keyboard.Key.down,
    'left': keyboard.Key.left,
    'right': keyboard.Key.right,
    'home': keyboard.Key.home,
    'end': keyboard.Key.end,
    'pageup': keyboard.Key.page_up,
    'pagedown': keyboard.Key.page_down,
}

CODE_KEY_MAP = {
    'space': keyboard.Key.space,
    'shiftleft': keyboard.Key.shift,
    'shiftright': keyboard.Key.shift,
    'controlleft': keyboard.Key.ctrl,
    'controlright': keyboard.Key.ctrl,
    'altleft': keyboard.Key.alt,
    'altright': keyboard.Key.alt,
    'metaleft': keyboard.Key.cmd,
    'metaright': keyboard.Key.cmd,
    'contextmenu': keyboard.Key.menu,
    'digit0': '0',
    'digit1': '1',
    'digit2': '2',
    'digit3': '3',
    'digit4': '4',
    'digit5': '5',
    'digit6': '6',
    'digit7': '7',
    'digit8': '8',
    'digit9': '9',
    'numpad0': '0',
    'numpad1': '1',
    'numpad2': '2',
    'numpad3': '3',
    'numpad4': '4',
    'numpad5': '5',
    'numpad6': '6',
    'numpad7': '7',
    'numpad8': '8',
    'numpad9': '9',
    'numpadadd': '+',
    'numpadsubtract': '-',
    'numpadmultiply': '*',
    'numpaddivide': '/',
    'numpaddecimal': '.',
    'bracketleft': '[',
    'bracketright': ']',
    'backslash': '\\\\',
    'quote': '\'',
    'semicolon': ';',
    'comma': ',',
    'period': '.',
    'slash': '/',
    'minus': '-',
    'equal': '=',
    'backquote': '`',
}


def to_screen_coords(payload: dict) -> tuple[int, int]:
    x_ratio = clamp_ratio(float(payload.get('x', 0)))
    y_ratio = clamp_ratio(float(payload.get('y', 0)))
    x = int(x_ratio * SCREEN_WIDTH) + SCREEN_LEFT
    y = int(y_ratio * SCREEN_HEIGHT) + SCREEN_TOP
    return x, y


def handle_mouse_event(payload: dict) -> None:
    action = payload.get('action')

    if action == 'move':
        mouse_controller.position = to_screen_coords(payload)
        return

    if action == 'click':
        button = MOUSE_BUTTON_MAP.get(payload.get('button', 'left'))
        if button is None:
            return
        count = 2 if payload.get('double') else 1
        for _ in range(count):
            mouse_controller.click(button, 1)
        return

    if action == 'scroll':
        delta_y = float(payload.get('deltaY', 0))
        mouse_controller.scroll(0, -delta_y)
        return


def resolve_basic_key(key_name: str | None):
    if not key_name:
        return None
    key_lower = key_name.lower()
    if key_lower in SPECIAL_KEYS:
        return SPECIAL_KEYS[key_lower]
    if len(key_name) == 1:
        return key_name
    return None


def resolve_key_from_code(code: str | None):
    if not code:
        return None
    return CODE_KEY_MAP.get(code.lower())


def resolve_key(payload: dict):
    key_name = payload.get('key')
    key_obj = resolve_basic_key(key_name)
    if key_obj is not None:
        return key_obj
    return resolve_key_from_code(payload.get('code'))


def handle_keyboard_event(payload: dict) -> None:
    key_obj = resolve_key(payload)
    if key_obj is None:
        return

    event_type = payload.get('eventType', 'press')

    if event_type == 'down':
        keyboard_controller.press(key_obj)
    elif event_type == 'up':
        keyboard_controller.release(key_obj)
    else:
        keyboard_controller.press(key_obj)
        keyboard_controller.release(key_obj)


def run_wake_commands() -> bool:
    ran_any = False
    for cmd in config.WAKE_COMMANDS:
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                check=False,
                timeout=5,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                ran_any = True
        except (subprocess.TimeoutExpired, Exception):
            continue
    return ran_any


def aggressive_wake_input():
    """Perform aggressive mouse/keyboard movements to wake display."""
    import random
    center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
    
    # Move mouse in a small pattern
    for offset in [(0, 0), (5, 5), (-5, -5), (0, 0)]:
        try:
            mouse_controller.position = (
                center_x + offset[0] + SCREEN_LEFT,
                center_y + offset[1] + SCREEN_TOP
            )
            time.sleep(0.05)
        except Exception:
            pass
    
    # Press and release multiple keys
    wake_keys = [keyboard.Key.shift, keyboard.Key.ctrl, keyboard.Key.space]
    for key in wake_keys:
        try:
            keyboard_controller.press(key)
            time.sleep(0.02)
            keyboard_controller.release(key)
            time.sleep(0.02)
        except Exception:
            continue


@app.route('/api/host/wake', methods=['POST'])
def wake_host():
    if not authenticated():
        return jsonify({'error': 'Unauthorized'}), 401

    if USE_AGENT:
        try:
            result = agent_client.wake_host()
            return jsonify(result)
        except Exception as exc:
            return jsonify({'error': str(exc)}), 502

    # Try system commands first
    ran_commands = run_wake_commands()
    
    # Always perform aggressive input simulation as fallback
    try:
        aggressive_wake_input()
    except Exception:
        pass
    
    # Additional X11-specific wake (if DISPLAY is set)
    import os
    if os.environ.get('DISPLAY'):
        try:
            subprocess.run(
                ['xset', 'dpms', 'force', 'on'],
                timeout=2,
                capture_output=True
            )
            subprocess.run(
                ['xset', 's', 'reset'],
                timeout=2,
                capture_output=True
            )
        except Exception:
            pass

    return jsonify({
        'status': 'ok',
        'commands_run': ran_commands,
        'message': 'Wake signal sent. Display should activate shortly.'
    })


@app.route('/api/agent/health')
def agent_health():
    if not USE_AGENT:
        return jsonify({'status': 'disabled'}), 200
    try:
        result = agent_client.health()
        return jsonify(result)
    except Exception as exc:
        return jsonify({'status': 'error', 'detail': str(exc)}), 502


@app.route('/api/input', methods=['POST'])
def receive_input():
    if not authenticated():
        return jsonify({'error': 'Unauthorized'}), 401

    payload = request.get_json(silent=True) or {}
    if USE_AGENT:
        try:
            result = agent_client.send_input(payload)
            return jsonify(result)
        except Exception as exc:
            return jsonify({'error': str(exc)}), 502

    event_type = payload.get('type')

    if event_type == 'mouse':
        handle_mouse_event(payload)
    elif event_type == 'keyboard':
        handle_keyboard_event(payload)

    return jsonify({'status': 'ok'})


@app.route('/logout')
def logout():
    session_id = session.get('_id', id(session))
    active_sessions.discard(session_id)
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
