import os

# Authentication
USERNAME = os.environ.get('REMOTE_DESKTOP_USER', 'admin')
PASSWORD = os.environ.get('REMOTE_DESKTOP_PASSWORD', 'changeme')

# Flask session secret
SECRET_KEY = os.environ.get('REMOTE_DESKTOP_SECRET', 'replace-with-random-secret')

# Streaming / capture settings
CAPTURE_INTERVAL = float(os.environ.get('REMOTE_DESKTOP_INTERVAL', 0.8))  # seconds
IMAGE_QUALITY = int(os.environ.get('REMOTE_DESKTOP_JPEG_QUALITY', 60))

# Rate limiting (per IP)
RATE_LIMIT_WINDOW = int(os.environ.get('REMOTE_DESKTOP_RATE_WINDOW', 60))  # seconds
RATE_LIMIT_ATTEMPTS = int(os.environ.get('REMOTE_DESKTOP_RATE_ATTEMPTS', 5))

# Network restrictions (CIDR blocks)
ALLOWED_SUBNETS = os.environ.get(
    'REMOTE_DESKTOP_ALLOWED_SUBNETS',
    '127.0.0.1/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16'
).split(',')

# Commands invoked when the dashboard requests a wake (semicolon-separated)
# Tries multiple methods: X11 DPMS, Wayland, systemd, and direct input simulation
WAKE_COMMANDS = [
    cmd.strip() for cmd in os.environ.get(
        'REMOTE_DESKTOP_WAKE_COMMANDS',
        'xset dpms force on;xset s reset;loginctl unlock-sessions 2>/dev/null;setterm -blank 0 -powerdown 0 2>/dev/null'
    ).split(';') if cmd.strip()
]

# Keep-alive interval (seconds) - prevents system from sleeping during active sessions
KEEP_ALIVE_INTERVAL = float(os.environ.get('REMOTE_DESKTOP_KEEP_ALIVE', 30.0))

# Host agent integration
AGENT_BASE_URL = os.environ.get('REMOTE_AGENT_BASE_URL', 'http://127.0.0.1:8787')
AGENT_TOKEN = os.environ.get('REMOTE_AGENT_TOKEN', 'replace-this-agent-token')
AGENT_TIMEOUT = float(os.environ.get('REMOTE_AGENT_TIMEOUT', 5.0))
AGENT_ENABLED = os.environ.get('REMOTE_AGENT_ENABLED', 'false').lower() in {'1', 'true', 'yes'}
