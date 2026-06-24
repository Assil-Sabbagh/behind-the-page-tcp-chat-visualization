"""
tcp_client.py - TCP Client Logic

This module manages a TCP client connection from the web server side.
Each browser session that joins the chat gets its own TCPClient instance,
which connects to the TCP server using raw Python sockets.

Socket operations used here:
  - socket()   : Create a TCP socket
  - connect()  : Connect to the server's IP:port 
  - send()     : Send JSON-encoded messages to the server
  - recv()     : Receive messages from the server (in a background thread)
  - close()    : Clean up when the user disconnects
"""

import socket
import threading
import json
import time
import logging

logger = logging.getLogger(__name__)

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 9999
BUFFER_SIZE = 4096


class TCPClient:
    """
    Represents one browser user's TCP connection to the chat server.

    Lifecycle:
      1. __init__()  — allocates state
      2. connect()   — creates socket, calls connect(), sends registration
      3. listen()    — background thread calls recv() in a loop
      4. send_message() — calls send() to push chat messages
      5. disconnect()   — calls close()
    """

    def __init__(self, username: str, sid: str, on_message_cb):
        """
        username      : display name chosen by the user
        sid           : Flask-SocketIO session ID (used to route responses back)
        on_message_cb : called with (sid, message_dict) when server sends data
        """
        self.username = username
        self.sid = sid
        self.on_message = on_message_cb
        self.sock = None
        self.connected = False
        self._listener_thread = None

    # ─────────────────────────────────────────────
    #  CONNECT TO SERVER
    # ─────────────────────────────────────────────
    def connect(self) -> bool:
        """
        Creates a TCP socket and connects to the chat server.
        Returns True on success, False on failure.
        """
        try:
            # ── SOCKET OPERATION: socket() ────────────────────────────────
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)  # 10-second connect timeout

            # ── SOCKET OPERATION: connect() ───────────────────────────────
            # Initiates the TCP three-way handshake with the server.
            # Under the hood this sends SYN, waits for SYN-ACK, sends ACK.
            self.sock.connect((SERVER_HOST, SERVER_PORT))

            # Remove timeout after connect; recv() should block indefinitely
            self.sock.settimeout(None)
            self.connected = True

            logger.info(f"[TCPClient] {self.username} connected to {SERVER_HOST}:{SERVER_PORT}")

            # ── SOCKET OPERATION: send() ──────────────────────────────────
            # First packet: register our username with the server
            register_msg = json.dumps({
                'type': 'register',
                'username': self.username,
            }).encode('utf-8')
            self.sock.send(register_msg)

            # Start a background thread to listen for incoming messages
            self._listener_thread = threading.Thread(
                target=self._listen_loop,
                daemon=True,
            )
            self._listener_thread.start()

            return True

        except (ConnectionRefusedError, OSError, socket.timeout) as e:
            logger.error(f"[TCPClient] Connection failed for {self.username}: {e}")
            self.connected = False
            return False

    # ─────────────────────────────────────────────
    #  LISTEN LOOP (background thread)
    # ─────────────────────────────────────────────
    def _listen_loop(self):
        """
        Continuously calls recv() to receive data from the server.
        Parses JSON packets and fires on_message callback.
        Exits when the connection is closed.
        """
        while self.connected:
            try:
                # ── SOCKET OPERATION: recv() ──────────────────────────────
                # Blocks until the server sends data, or the connection drops.
                raw = self.sock.recv(BUFFER_SIZE)

                if not raw:
                    # Server closed connection
                    logger.info(f"[TCPClient] Server closed connection for {self.username}")
                    break

                try:
                    data = json.loads(raw.decode('utf-8'))
                    self.on_message(self.sid, data)
                except json.JSONDecodeError:
                    logger.warning(f"[TCPClient] Bad JSON from server: {raw[:80]}")

            except OSError:
                # Socket was closed (likely by disconnect())
                break

        self.connected = False

    # ─────────────────────────────────────────────
    #  SEND A CHAT MESSAGE
    # ─────────────────────────────────────────────
    def send_message(self, text: str) -> bool:
        """
        Sends a chat message to the server via TCP.
        Returns True on success.
        """
        if not self.connected or not self.sock:
            return False
        try:
            payload = json.dumps({
                'type': 'message',
                'text': text,
            }).encode('utf-8')

            # ── SOCKET OPERATION: send() ──────────────────────────────────
            self.sock.send(payload)
            return True
        except OSError as e:
            logger.error(f"[TCPClient] send failed for {self.username}: {e}")
            self.connected = False
            return False

    # ─────────────────────────────────────────────
    #  DISCONNECT
    # ─────────────────────────────────────────────
    def disconnect(self):
        """
        Gracefully closes the TCP connection.
        """
        self.connected = False
        if self.sock:
            try:
                # ── SOCKET OPERATION: close() ─────────────────────────────
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        logger.info(f"[TCPClient] {self.username} disconnected")
