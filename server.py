"""
server.py - Core TCP Server using Python's socket library

This is the heart of the project. It demonstrates raw TCP socket programming:
  - socket()   : Creates a TCP socket
  - bind()     : Binds the socket to an IP and port
  - listen()   : Puts the socket in listening mode for incoming connections 
  - accept()   : Accepts a new client connection (blocking call)
  - recv()     : Receives data from a connected client
  - send()     : Sends data to a connected client
  - close()    : Closes the socket connection

Threading is used so multiple clients can connect and chat simultaneously.
"""

import socket
import threading
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='[SERVER] %(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  SERVER CONFIGURATION
# ─────────────────────────────────────────────
HOST = '0.0.0.0'   # Listen on all available network interfaces
PORT = 9999         # TCP port the server will bind to
BUFFER_SIZE = 4096  # Maximum bytes to receive in one recv() call

# ─────────────────────────────────────────────
#  SHARED STATE (thread-safe with a lock)
# ─────────────────────────────────────────────
clients = {}          # { conn: { 'username': str, 'addr': tuple, 'joined': float } }
clients_lock = threading.Lock()

stats = {
    'total_messages': 0,
    'total_connections': 0,
    'server_start_time': time.time(),
}

# Callback hook: app.py registers this to push events to the web dashboard
event_callback = None


def register_event_callback(callback):
    """
    app.py calls this once at startup to register a function that forwards
    TCP events to the Flask-SocketIO dashboard in real time.
    """
    global event_callback
    event_callback = callback


def emit_event(event_type, data):
    """
    Fires an event toward the web dashboard.
    If no callback is registered (e.g. running server standalone), just log.
    """
    if event_callback:
        event_callback(event_type, data)
    logger.info(f"EVENT [{event_type}] {data}")


# ─────────────────────────────────────────────
#  BROADCAST: send a message to all clients
# ─────────────────────────────────────────────
def broadcast(message_dict, exclude_conn=None):
    """
    Serialize a message dict to JSON and call send() on every connected client.
    Clients that fail to receive are queued for removal.
    """
    payload = json.dumps(message_dict).encode('utf-8')
    dead = []

    with clients_lock:
        for conn, info in clients.items():
            if conn == exclude_conn:
                continue
            try:
                # ── SOCKET OPERATION: send() ──────────────────────────────
                # send() writes bytes into the TCP stream toward the client.
                conn.send(payload)

                emit_event('send', {
                    'to': info['username'],
                    'addr': f"{info['addr'][0]}:{info['addr'][1]}",
                    'bytes': len(payload),
                })
            except (BrokenPipeError, ConnectionResetError, OSError):
                dead.append(conn)

    # Clean up disconnected clients after releasing the lock
    for conn in dead:
        remove_client(conn)


# ─────────────────────────────────────────────
#  REMOVE CLIENT
# ─────────────────────────────────────────────
def remove_client(conn):
    """
    Remove a client from the registry and close its socket.
    Notifies all remaining clients about the departure.
    """
    with clients_lock:
        if conn not in clients:
            return
        info = clients.pop(conn)

    username = info['username']
    addr = info['addr']

    emit_event('close', {
        'username': username,
        'addr': f"{addr[0]}:{addr[1]}",
        'active_clients': len(clients),
    })

    # ── SOCKET OPERATION: close() ─────────────────────────────────────────
    try:
        conn.close()
    except OSError:
        pass

    # Notify remaining users
    broadcast({
        'type': 'system',
        'text': f'{username} has left the chat.',
        'timestamp': time.strftime('%H:%M:%S'),
        'active_clients': len(clients),
    })

    logger.info(f"Client removed: {username} @ {addr}")


# ─────────────────────────────────────────────
#  CLIENT HANDLER THREAD
# ─────────────────────────────────────────────
def handle_client(conn, addr):
    """
    Runs in its own thread for each connected client.

    Flow:
      1. recv() the username registration message
      2. Loop: recv() chat messages and broadcast them
      3. On disconnect / error: call remove_client()
    """
    logger.info(f"New thread started for {addr}")

    # ── Simulate TCP Handshake events (conceptual visualization) ──────────
    # The actual SYN/SYN-ACK/ACK happens at the OS level when accept() returns.
    # We emit these events so the dashboard can animate the handshake steps.
    emit_event('handshake_syn', {'addr': f"{addr[0]}:{addr[1]}"})
    time.sleep(0.15)
    emit_event('handshake_syn_ack', {'addr': f"{addr[0]}:{addr[1]}"})
    time.sleep(0.15)
    emit_event('handshake_ack', {'addr': f"{addr[0]}:{addr[1]}"})
    time.sleep(0.1)
    emit_event('connection_established', {'addr': f"{addr[0]}:{addr[1]}"})

    username = None

    try:
        # ── SOCKET OPERATION: recv() ──────────────────────────────────────
        # The first message from the client is always a JSON registration packet
        # containing the chosen username.
        raw = conn.recv(BUFFER_SIZE)
        if not raw:
            conn.close()
            return

        data = json.loads(raw.decode('utf-8'))

        if data.get('type') != 'register':
            conn.close()
            return

        username = data['username'].strip()[:20] or 'Anonymous'

        # Store client in shared registry
        with clients_lock:
            clients[conn] = {
                'username': username,
                'addr': addr,
                'joined': time.time(),
            }
            stats['total_connections'] += 1
            active = len(clients)

        emit_event('accept', {
            'username': username,
            'addr': f"{addr[0]}:{addr[1]}",
            'active_clients': active,
        })

        # Welcome the new user to everyone
        broadcast({
            'type': 'system',
            'text': f'{username} joined the chat! 👋',
            'timestamp': time.strftime('%H:%M:%S'),
            'active_clients': active,
        })

        # Send a private welcome message back to the new client
        welcome = json.dumps({
            'type': 'welcome',
            'text': f'Welcome, {username}! You are now connected.',
            'timestamp': time.strftime('%H:%M:%S'),
        }).encode('utf-8')
        conn.send(welcome)  # ── SOCKET OPERATION: send() ──

        # ── MAIN MESSAGE LOOP ─────────────────────────────────────────────
        while True:
            # ── SOCKET OPERATION: recv() ──────────────────────────────────
            # Block here until the client sends data or disconnects.
            raw = conn.recv(BUFFER_SIZE)

            if not raw:
                # Empty bytes = client closed the connection gracefully
                break

            emit_event('recv', {
                'from': username,
                'addr': f"{addr[0]}:{addr[1]}",
                'bytes': len(raw),
            })

            try:
                data = json.loads(raw.decode('utf-8'))
            except json.JSONDecodeError:
                continue

            if data.get('type') == 'message':
                stats['total_messages'] += 1

                msg_packet = {
                    'type': 'message',
                    'username': username,
                    'text': data['text'],
                    'timestamp': time.strftime('%H:%M:%S'),
                    'total_messages': stats['total_messages'],
                    'active_clients': len(clients),
                }

                emit_event('message_flow', {
                    'from': username,
                    'addr': f"{addr[0]}:{addr[1]}",
                    'text': data['text'][:60],
                    'total_messages': stats['total_messages'],
                })

                # Relay the message to ALL connected clients (including sender)
                broadcast(msg_packet)

    except (ConnectionResetError, BrokenPipeError, OSError) as e:
        logger.warning(f"Connection error for {addr}: {e}")
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error from {addr}: {e}")
    finally:
        if username:
            remove_client(conn)
        else:
            try:
                conn.close()
            except OSError:
                pass


# ─────────────────────────────────────────────
#  START THE TCP SERVER
# ─────────────────────────────────────────────
def start_server():
    """
    Creates the TCP server socket, binds it, and enters the accept() loop.
    Each accepted connection is handled in a new daemon thread.
    """

    # ── SOCKET OPERATION: socket() ────────────────────────────────────────
    # AF_INET  = IPv4 addressing
    # SOCK_STREAM = TCP (reliable, ordered, connection-based)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # SO_REUSEADDR allows the port to be reused immediately after restart
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # ── SOCKET OPERATION: bind() ──────────────────────────────────────────
    # Associate the socket with the host:port address
    server_sock.bind((HOST, PORT))

    # ── SOCKET OPERATION: listen() ────────────────────────────────────────
    # Start listening; backlog=10 means up to 10 pending connections queued
    server_sock.listen(10)

    logger.info(f"TCP server listening on {HOST}:{PORT}")

    emit_event('server_start', {
        'host': HOST,
        'port': PORT,
        'timestamp': time.strftime('%H:%M:%S'),
    })

    try:
        while True:
            # ── SOCKET OPERATION: accept() ────────────────────────────────
            # Blocks until a client connects; returns (conn, addr).
            # conn is a NEW socket dedicated to this client.
            # addr is the client's (IP, port) tuple.
            conn, addr = server_sock.accept()

            logger.info(f"Accepted connection from {addr}")

            # Spawn a thread so this client doesn't block others
            t = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True,  # Thread exits when the main program exits
            )
            t.start()

    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    finally:
        # ── SOCKET OPERATION: close() ─────────────────────────────────────
        server_sock.close()


def get_stats():
    """Return current server statistics for the dashboard."""
    return {
        'active_clients': len(clients),
        'total_messages': stats['total_messages'],
        'total_connections': stats['total_connections'],
        'uptime': int(time.time() - stats['server_start_time']),
        'clients': [
            {
                'username': v['username'],
                'addr': f"{v['addr'][0]}:{v['addr'][1]}",
                'joined': time.strftime('%H:%M:%S', time.localtime(v['joined'])),
            }
            for v in clients.values()
        ],
    }


if __name__ == '__main__':
    # Run the server standalone (without Flask) for testing
    start_server()
