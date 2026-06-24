"""
app.py - Flask + Flask-SocketIO Web Application

This file is the bridge between:
  1. The raw TCP server (server.py)  — handles real socket communication
  2. The web browser (index.html)    — displays the chat UI and dashboard

Role of Flask here:
  - Serve the HTML page
  - Use Flask-SocketIO (WebSocket) ONLY for browser ↔ web-server communication
  - The real chat traffic flows through Python TCP sockets in server.py / tcp_client.py

Architecture:
  Browser ←─WebSocket─→ app.py ←─TCP Socket─→ server.py ←─TCP Socket─→ other browsers
"""

import threading
import time
import logging

from flask import Flask, render_template
from flask_socketio import SocketIO, emit, disconnect

import server as tcp_server
from tcp_client import TCPClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  FLASK + SOCKETIO SETUP
# ─────────────────────────────────────────────
app = Flask(__name__)
app.config['SECRET_KEY'] = 'behind_the_page_secret_2024'

# async_mode='threading' is required when using Python's socket library (blocking I/O)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')

# Map of Flask-SocketIO session IDs → TCPClient instances
active_clients = {}   # { sid: TCPClient }


# ─────────────────────────────────────────────
#  EVENT CALLBACK: server.py → dashboard
# ─────────────────────────────────────────────
def tcp_event_handler(event_type: str, data: dict):
    """
    Registered with the TCP server so it can push events to the web dashboard.
    Runs in the TCP server's thread → uses socketio.emit (thread-safe).
    """
    payload = {'type': event_type, 'data': data, 'timestamp': time.strftime('%H:%M:%S')}

    # Broadcast to ALL connected browser dashboards
    socketio.emit('tcp_event', payload)

    # Keep the stats panel updated
    socketio.emit('stats_update', tcp_server.get_stats())


# Register the callback with the TCP server module
tcp_server.register_event_callback(tcp_event_handler)


# ─────────────────────────────────────────────
#  START TCP SERVER IN BACKGROUND THREAD
# ─────────────────────────────────────────────
def launch_tcp_server():
    """Start the TCP server in a daemon thread so it doesn't block Flask."""
    t = threading.Thread(target=tcp_server.start_server, daemon=True)
    t.start()
    logger.info("TCP server thread launched")


# ─────────────────────────────────────────────
#  FLASK ROUTES
# ─────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


# ─────────────────────────────────────────────
#  FLASK-SOCKETIO EVENTS (browser ↔ app.py)
# ─────────────────────────────────────────────

@socketio.on('connect')
def on_browser_connect():
    """Called when a browser opens a WebSocket connection to this Flask app."""
    logger.info(f"Browser connected: sid={request_sid()}")
    # Send current stats immediately so the dashboard isn't blank
    emit('stats_update', tcp_server.get_stats())


@socketio.on('disconnect')
def on_browser_disconnect():
    """Called when a browser disconnects (tab closed, refresh, etc.)."""
    sid = request_sid()
    logger.info(f"Browser disconnected: sid={sid}")
    if sid in active_clients:
        active_clients[sid].disconnect()
        del active_clients[sid]


@socketio.on('join_chat')
def on_join_chat(data):
    """
    Browser sends { username } to join the chat.
    We create a TCPClient that connects to our TCP server.
    """
    sid = request_sid()
    username = str(data.get('username', 'Anonymous')).strip()[:20]

    if not username:
        emit('error', {'message': 'Username cannot be empty'})
        return

    if sid in active_clients:
        # Already connected — ignore duplicate joins
        return

    def on_tcp_message(client_sid, msg_data):
        """Called by TCPClient when a message arrives from the TCP server."""
        socketio.emit('chat_message', msg_data, to=client_sid)

    client = TCPClient(username, sid, on_tcp_message)
    success = client.connect()

    if success:
        active_clients[sid] = client
        emit('joined', {'username': username, 'success': True})
        logger.info(f"User '{username}' (sid={sid}) joined via TCP")
    else:
        emit('error', {'message': 'Could not connect to TCP server. Is it running?'})


@socketio.on('send_message')
def on_send_message(data):
    """
    Browser sends { text } → we forward via TCP to the server.
    """
    sid = request_sid()
    text = str(data.get('text', '')).strip()

    if not text:
        return

    if sid not in active_clients:
        emit('error', {'message': 'You are not connected. Please join first.'})
        return

    client = active_clients[sid]
    ok = client.send_message(text)

    if not ok:
        emit('error', {'message': 'Failed to send message. Connection may be lost.'})
        if sid in active_clients:
            del active_clients[sid]


@socketio.on('request_stats')
def on_request_stats():
    """Browser asks for a fresh stats snapshot."""
    emit('stats_update', tcp_server.get_stats())


# ─────────────────────────────────────────────
#  HELPER: get current SocketIO session ID
# ─────────────────────────────────────────────
def request_sid():
    from flask import request
    return request.sid


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == '__main__':
    launch_tcp_server()
    logger.info("Starting Flask app on http://0.0.0.0:5000")
    # use_reloader=False prevents the TCP server thread from launching twice
    socketio.run(app, host='0.0.0.0', port=5000, use_reloader=False, debug=False)
