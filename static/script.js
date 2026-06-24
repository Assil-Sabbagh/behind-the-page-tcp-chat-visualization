/**
 * script.js — Behind The Page: TCP Chat
 *
 * Handles:
 *  1. WebSocket connection to the Flask-SocketIO server (app.py)
 *  2. Sending join / message events to app.py
 *  3. Receiving TCP events from the Python server and visualizing them
 *  4. Dashboard animations: handshake, op-badges, message flow, event log
 */

'use strict';

// ─────────────────────────────────────────────
//  SOCKET.IO CONNECTION (browser → Flask app)
// ─────────────────────────────────────────────
const socket = io();

// Current user state
let myUsername = null;
let isJoined = false;

// ─────────────────────────────────────────────
//  DOM REFERENCES
// ─────────────────────────────────────────────
const joinScreen     = document.getElementById('joinScreen');
const chatScreen     = document.getElementById('chatScreen');
const usernameInput  = document.getElementById('usernameInput');
const joinBtn        = document.getElementById('joinBtn');
const joinError      = document.getElementById('joinError');
const chatStatus     = document.getElementById('chatStatus');
const connectedAs    = document.getElementById('connectedAs');
const onlineCount    = document.getElementById('onlineCount');
const messageBox     = document.getElementById('messageBox');
const msgInput       = document.getElementById('msgInput');
const sendBtn        = document.getElementById('sendBtn');
const clearLogBtn    = document.getElementById('clearLogBtn');
const eventLog       = document.getElementById('eventLog');
const clientList     = document.getElementById('clientList');

// Stats
const statClients     = document.getElementById('statClients');
const statMessages    = document.getElementById('statMessages');
const statConnections = document.getElementById('statConnections');
const statUptime      = document.getElementById('statUptime');

// Handshake steps
const hsSyn         = document.getElementById('hsSyn');
const hsSynAck      = document.getElementById('hsSynAck');
const hsAck         = document.getElementById('hsAck');
const hsEstablished = document.getElementById('hsEstablished');

// Flow nodes
const flowClient = document.getElementById('flowClient');
const flowServer = document.getElementById('flowServer');
const flowOthers = document.getElementById('flowOthers');
const flowArrow1 = document.getElementById('flowArrow1');
const flowArrow2 = document.getElementById('flowArrow2');


// ═══════════════════════════════════════════════
//  JOIN CHAT
// ═══════════════════════════════════════════════
function joinChat() {
  const username = usernameInput.value.trim();
  if (!username) {
    showJoinError('Please enter a username.');
    return;
  }
  joinBtn.disabled = true;
  joinBtn.textContent = 'Connecting…';
  joinError.style.display = 'none';
  socket.emit('join_chat', { username });
}

joinBtn.addEventListener('click', joinChat);
usernameInput.addEventListener('keydown', e => { if (e.key === 'Enter') joinChat(); });


// ═══════════════════════════════════════════════
//  SEND MESSAGE
// ═══════════════════════════════════════════════
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || !isJoined) return;
  socket.emit('send_message', { text });
  msgInput.value = '';
}

sendBtn.addEventListener('click', sendMessage);
msgInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });


// ═══════════════════════════════════════════════
//  SOCKET.IO EVENTS FROM SERVER
// ═══════════════════════════════════════════════

// Successfully joined
socket.on('joined', data => {
  if (!data.success) return;
  myUsername = data.username;
  isJoined = true;

  joinScreen.style.display = 'none';
  chatScreen.style.display = 'flex';
  chatStatus.textContent = 'Connected';
  chatStatus.className = 'status-badge online';
  connectedAs.innerHTML = `Connected as <strong style="color:var(--green)">${myUsername}</strong>`;

  // Animate socket creation op badges
  flashOp('socket_create', 'active-green', 1200);
  flashOp('bind',          'active-green', 1600);
  flashOp('listen',        'active-green', 2000);
  flashOp('accept',        'active-green', 2400);
  flashOp('connect',       'active-blue',  2800);
});

// Incoming chat message (from TCP server via app.py)
socket.on('chat_message', data => {
  if (data.type === 'message') {
    appendMessage(data.username, data.text, data.timestamp,
                  data.username === myUsername ? 'mine' : 'others');
    if (data.active_clients !== undefined) updateOnlineCount(data.active_clients);
    if (data.total_messages !== undefined) bumpStat(statMessages, data.total_messages);
    flashOp('recv', 'active-purple', 800);
  } else if (data.type === 'system' || data.type === 'welcome') {
    appendSystemMessage(data.text, data.timestamp);
    if (data.active_clients !== undefined) updateOnlineCount(data.active_clients);
  }
});

// Error from server
socket.on('error', data => {
  showJoinError(data.message || 'An error occurred.');
  joinBtn.disabled = false;
  joinBtn.textContent = 'Connect';
});

// Stats snapshot
socket.on('stats_update', data => {
  bumpStat(statClients, data.active_clients);
  bumpStat(statMessages, data.total_messages);
  bumpStat(statConnections, data.total_connections);
  statUptime.textContent = formatUptime(data.uptime);
  renderClientList(data.clients || []);
  updateOnlineCount(data.active_clients);
});

// TCP events from the Python server → dashboard animations
socket.on('tcp_event', payload => {
  const { type, data, timestamp } = payload;
  handleTcpEvent(type, data, timestamp);
});


// ═══════════════════════════════════════════════
//  TCP EVENT HANDLER — drives all animations
// ═══════════════════════════════════════════════
function handleTcpEvent(type, data, ts) {
  switch (type) {

    case 'server_start':
      addLog(ts, 'START', 'green', `TCP server bound to port ${data.port}`, 'ev-accept');
      flashOp('socket_create', 'active-green', 1000);
      flashOp('bind',          'active-green', 1400);
      flashOp('listen',        'active-green', 1800);
      break;

    case 'handshake_syn':
      hsSyn.classList.add('active');
      addLog(ts, 'SYN', 'yellow', `${data.addr} → SYN sent`, 'ev-handshake');
      break;

    case 'handshake_syn_ack':
      hsSynAck.classList.add('active');
      addLog(ts, 'SYN-ACK', 'yellow', `Server → SYN-ACK`, 'ev-handshake');
      break;

    case 'handshake_ack':
      hsAck.classList.add('active');
      addLog(ts, 'ACK', 'yellow', `${data.addr} → ACK sent`, 'ev-handshake');
      break;

    case 'connection_established':
      hsEstablished.classList.add('active');
      addLog(ts, 'CONNECT', 'green', `${data.addr} — connection established`, 'ev-accept');
      flashOp('accept', 'active-green', 400);
      // Reset handshake after 4 seconds for next connection
      setTimeout(resetHandshake, 4000);
      break;

    case 'accept':
      addLog(ts, 'ACCEPT', 'green',
        `accept() → ${data.username} from ${data.addr} (clients: ${data.active_clients})`,
        'ev-accept');
      flashOp('accept', 'active-green', 600);
      break;

    case 'recv':
      addLog(ts, 'RECV', 'purple',
        `recv() ← ${data.from} @ ${data.addr} (${data.bytes}B)`, 'ev-recv');
      flashOp('recv', 'active-purple', 600);
      break;

    case 'send':
      addLog(ts, 'SEND', 'blue',
        `send() → ${data.to} @ ${data.addr} (${data.bytes}B)`, 'ev-send');
      flashOp('send', 'active-blue', 600);
      break;

    case 'message_flow':
      addLog(ts, 'MSG', 'blue',
        `"${data.text}" from ${data.from} — total: ${data.total_messages}`, 'ev-message');
      animateMessageFlow();
      break;

    case 'close':
      addLog(ts, 'CLOSE', 'red',
        `close() ← ${data.username} @ ${data.addr} (active: ${data.active_clients})`,
        'ev-close');
      flashOp('close', 'active-red', 600);
      break;

    default:
      addLog(ts, type.toUpperCase(), 'blue', JSON.stringify(data).slice(0, 80), 'ev-message');
  }

  // Always request a fresh stats update after any event
  socket.emit('request_stats');
}


// ═══════════════════════════════════════════════
//  MESSAGE FLOW ANIMATION
// ═══════════════════════════════════════════════
function animateMessageFlow() {
  const delay = ms => new Promise(r => setTimeout(r, ms));

  async function run() {
    flowClient.classList.add('lit');
    await delay(300);

    flowArrow1.classList.add('lit');
    await delay(250);

    flowServer.classList.add('lit');
    await delay(300);

    flowArrow2.classList.add('lit');
    await delay(250);

    flowOthers.classList.add('lit');
    await delay(700);

    // Reset all
    [flowClient, flowArrow1, flowServer, flowArrow2, flowOthers]
      .forEach(el => el.classList.remove('lit'));
  }

  run();
}


// ═══════════════════════════════════════════════
//  HANDSHAKE HELPERS
// ═══════════════════════════════════════════════
function resetHandshake() {
  [hsSyn, hsSynAck, hsAck, hsEstablished].forEach(el => el.classList.remove('active'));
}


// ═══════════════════════════════════════════════
//  OP BADGE FLASH
// ═══════════════════════════════════════════════
function flashOp(opId, colorClass, duration = 800) {
  const el = document.getElementById(`op-${opId}`);
  if (!el) return;
  el.classList.add(colorClass);
  setTimeout(() => el.classList.remove(colorClass), duration);
}


// ═══════════════════════════════════════════════
//  EVENT LOG
// ═══════════════════════════════════════════════
const MAX_LOG_ENTRIES = 120;

function addLog(ts, type, colorClass, detail, evClass) {
  const entry = document.createElement('div');
  entry.className = `log-entry ${evClass}`;
  entry.innerHTML =
    `<span class="log-time">${ts}</span>` +
    `<span class="log-type ${colorClass}">${type}</span>` +
    `<span class="log-detail">${escapeHtml(detail)}</span>`;
  eventLog.prepend(entry);  // newest on top

  // Trim old entries
  while (eventLog.children.length > MAX_LOG_ENTRIES) {
    eventLog.removeChild(eventLog.lastChild);
  }
}

clearLogBtn.addEventListener('click', () => { eventLog.innerHTML = ''; });


// ═══════════════════════════════════════════════
//  CHAT MESSAGES
// ═══════════════════════════════════════════════
function appendMessage(username, text, timestamp, type) {
  const div = document.createElement('div');
  div.className = `msg ${type}`;

  if (type !== 'system') {
    div.innerHTML =
      `<div class="msg-header">
        <span>${escapeHtml(username)}</span>
        <span>${timestamp}</span>
      </div>
      <div class="msg-bubble">${escapeHtml(text)}</div>`;
  } else {
    div.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
  }

  messageBox.appendChild(div);
  messageBox.scrollTop = messageBox.scrollHeight;
}

function appendSystemMessage(text, timestamp) {
  appendMessage('', text, timestamp || '', 'system');
}


// ═══════════════════════════════════════════════
//  CLIENT LIST
// ═══════════════════════════════════════════════
function renderClientList(clients) {
  if (!clients.length) {
    clientList.innerHTML = '<div class="empty-state">No clients connected yet.</div>';
    return;
  }
  clientList.innerHTML = clients.map(c =>
    `<div class="client-row">
      <div class="client-dot"></div>
      <span class="client-name">${escapeHtml(c.username)}</span>
      <span class="client-addr">${escapeHtml(c.addr)} · ${escapeHtml(c.joined)}</span>
    </div>`
  ).join('');
}


// ═══════════════════════════════════════════════
//  STAT HELPERS
// ═══════════════════════════════════════════════
function bumpStat(el, value) {
  if (el.textContent === String(value)) return;
  el.textContent = value;
  el.classList.add('bump');
  setTimeout(() => el.classList.remove('bump'), 400);
}

function updateOnlineCount(n) {
  onlineCount.textContent = `${n} online`;
}

function formatUptime(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}


// ═══════════════════════════════════════════════
//  UI HELPERS
// ═══════════════════════════════════════════════
function showJoinError(msg) {
  joinError.textContent = msg;
  joinError.style.display = 'block';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}


// ═══════════════════════════════════════════════
//  UPTIME TICKER (client-side)
// ═══════════════════════════════════════════════
let uptimeBase = null;
socket.on('stats_update', data => {
  if (uptimeBase === null) uptimeBase = Date.now() - data.uptime * 1000;
});
setInterval(() => {
  if (uptimeBase !== null) {
    const secs = Math.floor((Date.now() - uptimeBase) / 1000);
    statUptime.textContent = formatUptime(secs);
  }
}, 1000);


// ═══════════════════════════════════════════════
//  REQUEST INITIAL STATS ON LOAD
// ═══════════════════════════════════════════════
socket.emit('request_stats');