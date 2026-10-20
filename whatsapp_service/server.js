/**
 * BotX Direct WhatsApp Bridge Server (v2 - Live WA Web Protocol + Pairing Code + QR).
 *
 * - Uses fetchLatestWaWebVersion() ([2, 3000, 1050063423]) + Browsers.ubuntu("Chrome")
 *   so WhatsApp mobile never shows "Check connection / Couldn't link device".
 * - Supports BOTH:
 *   1. Scanning QR Code on http://localhost:8090
 *   2. 8-Digit Phone Pairing Code ("Link with phone number instead")
 */

const http = require("http");
const fs = require("fs");
const path = require("path");
const QRCode = require("qrcode");
const pino = require("pino");
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestWaWebVersion,
  Browsers,
} = require("@whiskeysockets/baileys");

const PORT = 8090;
const AUTH_DIR = path.join(__dirname, "auth_info");

let sock = null;
let latestQrDataUrl = null;
let latestPairingCode = null;
let connectionStatus = "INITIALIZING"; // INITIALIZING | SCAN_QR | CONNECTED | DISCONNECTED
let connectedJid = null;
let welcomeSent = false;

async function startWhatsApp() {
  try {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    let version = [2, 3000, 1050063423];
    try {
      const latest = await fetchLatestWaWebVersion({});
      if (latest && latest.version) {
        version = latest.version;
      }
    } catch (_) {}

    console.log(`[WhatsApp Bridge] Using WA Web version: ${version.join(".")}`);

    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      logger: pino({ level: "silent" }),
      browser: Browsers.ubuntu("Chrome"),
      syncFullHistory: false,
      markOnlineOnConnect: false,
    });

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("messages.upsert", async (m) => {
      try {
        if (!m.messages || m.messages.length === 0) return;
        for (const msg of m.messages) {
          if (!msg.message || msg.key.fromMe) continue;
          const text = (
            msg.message.conversation ||
            (msg.message.extendedTextMessage && msg.message.extendedTextMessage.text) ||
            ""
          ).trim();

          if (!text) continue;
          const upper = text.toUpperCase();
          const senderJid = msg.key.remoteJid;
          console.log(`[WhatsApp Bridge] Received command from ${senderJid}: "${text}"`);

          if (
            upper === "CLOSE" ||
            upper === "EXIT" ||
            upper === "CLOSE ALL" ||
            upper === "BAND KAR" ||
            upper === "EXIT TRADE" ||
            upper === "CLOSE TRADE"
          ) {
            console.log(`[WhatsApp Bridge] Triggering manual trade close...`);
            try {
              const res = await fetch("http://localhost:8085/api/positions/close", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
              });
              const data = await res.json();
              let reply = "";
              if (data.closed && data.closed.length > 0) {
                const syms = data.closed.map((c) => c.symbol).join(", ");
                reply =
                  `⚡ *[TRADE CLOSED SUCCESSFULLY]* ⚡\n` +
                  `━━━━━━━━━━━━━━━━━━━━\n` +
                  `Bhai, aapke WhatsApp command par *${syms}* trade market price par turant close kar di gayi hai!\n` +
                  `💰 Profits lock ho gaye hain aur sabhi SL/TP orders cancel ho chuke hain.`;
              } else {
                reply = `ℹ️ Bhai, abhi koi open trade nahi hai jise close kiya jaye. (All positions 0).`;
              }
              await sock.sendMessage(senderJid, { text: reply });
            } catch (err) {
              console.error("[WhatsApp Bridge] Close API error:", err);
              await sock.sendMessage(senderJid, { text: `⚠️ Error closing trade: ${err.message}` });
            }
          } else if (
            upper === "STATUS" ||
            upper === "PNL" ||
            upper === "TRADE" ||
            upper === "TRADES" ||
            upper === "PROFIT"
          ) {
            try {
              const res = await fetch("http://localhost:8085/api/positions");
              const data = await res.json();
              let reply = "";
              if (data.positions && data.positions.length > 0) {
                reply = `📊 *[CURRENT LIVE TRADES]* 📊\n━━━━━━━━━━━━━━━━━━━━\n`;
                for (const p of data.positions) {
                  const sign = p.unrealized_pnl >= 0 ? "+" : "";
                  reply += `• *${p.symbol} (${p.side} ${p.leverage}x)*\n  Entry: $${p.entry_price.toFixed(2)} | Mark: $${p.mark_price.toFixed(2)}\n  PnL: *${sign}$${p.unrealized_pnl.toFixed(2)} USDT*\n\n`;
                }
                reply += `💵 Total Balance: $${data.balance.toFixed(2)} USDT\n\n_Trade close karne ke liye bas "CLOSE" type karke bhej do!_`;
              } else {
                reply = `ℹ️ Abhi koi open position nahi hai.\n💵 Balance: $${data.balance.toFixed(2)} USDT\nBot agle A+ setup ke liye scan kar raha hai!`;
              }
              await sock.sendMessage(senderJid, { text: reply });
            } catch (err) {
              await sock.sendMessage(senderJid, { text: `⚠️ Error fetching status: ${err.message}` });
            }
          } else if (
            upper.includes("STRATEGY") ||
            upper.includes("STRAT") ||
            upper === "RETEST" ||
            upper === "SWEEP"
          ) {
            try {
              if (upper.includes("RETEST") || upper.includes("VIDEO") || upper.includes("SCALPER")) {
                const res = await fetch("http://localhost:8085/api/strategy/switch", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ strategy_id: "funded_retest_scalper" }),
                });
                const data = await res.json();
                await sock.sendMessage(senderJid, {
                  text:
                    `🎯 *[ACTIVE STRATEGY SWITCHED]* 🎯\n` +
                    `━━━━━━━━━━━━━━━━━━━━\n` +
                    `Bhai, bot ab *Price Action Retest Scalper* (Video Strategy) par switch ho gaya hai!\n\n` +
                    `• *Timeframe:* 5M Entry + 1H Trend\n` +
                    `• *Setup:* 5M Break of Structure (BOS) + Retest + Rejection/Engulfing Wick\n` +
                    `• *Target:* 1:2 Risk to Reward\n` +
                    `• *Sizing:* $150 Margin @ 14x Leverage\n\n` +
                    `_Wapas purani strategy par jane ke liye "SWEEP" ya "STRATEGY SWEEP" bhejein._`,
                });
              } else if (upper.includes("SWEEP") || upper.includes("DEFAULT")) {
                const res = await fetch("http://localhost:8085/api/strategy/switch", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ strategy_id: "liquidity_sweep" }),
                });
                const data = await res.json();
                await sock.sendMessage(senderJid, {
                  text:
                    `🔄 *[DEFAULT STRATEGY RESTORED]* 🔄\n` +
                    `━━━━━━━━━━━━━━━━━━━━\n` +
                    `Bhai, bot wapas *Liquidity Sweep Strategy (Default)* par set ho gaya hai!\n\n` +
                    `• *Timeframe:* 15M + 1H HTF\n` +
                    `• *Setup:* Support/Resistance Liquidity Sweep + Rejection Pin Bar\n` +
                    `• *Target:* 1:3 RR + Cost-to-Cost Trailing\n` +
                    `• *Sizing:* $150 Margin @ 14x Leverage`,
                });
              } else {
                const res = await fetch("http://localhost:8085/api/strategy/active");
                const data = await res.json();
                await sock.sendMessage(senderJid, {
                  text:
                    `⚙️ *[ACTIVE STRATEGY STATUS]* ⚙️\n` +
                    `━━━━━━━━━━━━━━━━━━━━\n` +
                    `Abhi active strategy hai: *${data.name}*\n\n` +
                    `Strategy badalne ke liye reply karein:\n` +
                    `• *RETEST* ➔ Video Strategy (5M BOS + Retest 1:2 RR)\n` +
                    `• *SWEEP* ➔ Default Strategy (Liquidity Sweep 1:3 RR)`,
                });
              }
            } catch (err) {
              await sock.sendMessage(senderJid, { text: `⚠️ Error managing strategy: ${err.message}` });
            }
          }
        }
      } catch (err) {
        console.error("[WhatsApp Bridge] Incoming message error:", err);
      }
    });

    sock.ev.on("connection.update", async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        connectionStatus = "SCAN_QR";
        latestQrDataUrl = await QRCode.toDataURL(qr, { width: 300, margin: 2 });
        console.log("[WhatsApp Bridge] Fresh QR Code ready at http://localhost:8090");
      }

      if (connection === "open") {
        connectionStatus = "CONNECTED";
        latestQrDataUrl = null;
        latestPairingCode = null;
        connectedJid =
          sock.user && sock.user.id ? sock.user.id.split(":")[0] + "@s.whatsapp.net" : null;
        console.log(`[WhatsApp Bridge] SUCCESSFULLY CONNECTED as ${connectedJid}`);

        if (!welcomeSent && connectedJid) {
          welcomeSent = true;
          try {
            await sock.sendMessage(connectedJid, {
              text:
                "✅ *BOTX WHATSAPP ALERTS CONNECTED!* ✅\n" +
                "━━━━━━━━━━━━━━━━━━━━\n" +
                "Bhai, aapka *24/7 Liquidity Sweep Scanner* ab seedha aapke WhatsApp se connect ho gaya hai!\n\n" +
                "Jab bhi *Support Sweep (LONG)* ya *Resistance Sweep (SHORT)* 1:3 RR ke saath confirm hoga, aapko yahin trade setup ka message aayega.",
            });
            console.log("[WhatsApp Bridge] Sent welcome message to WhatsApp!");
          } catch (err) {
            console.error("[WhatsApp Bridge] Welcome message error:", err.message);
          }
        }
      }

      if (connection === "close") {
        const statusCode =
          lastDisconnect &&
          lastDisconnect.error &&
          lastDisconnect.error.output &&
          lastDisconnect.error.output.statusCode;

        console.log(`[WhatsApp Bridge] Connection closed (code=${statusCode}).`);
        connectionStatus = "DISCONNECTED";

        if (statusCode === DisconnectReason.loggedOut || statusCode === 401) {
          console.log("[WhatsApp Bridge] Clearing stale auth and restarting...");
          try {
            fs.rmSync(AUTH_DIR, { recursive: true, force: true });
          } catch (_) {}
        }
        setTimeout(startWhatsApp, 2500);
      }
    });
  } catch (err) {
    console.error("[WhatsApp Bridge] Startup error:", err);
    setTimeout(startWhatsApp, 4000);
  }
}

async function sendWhatsAppMessage(phone, message) {
  if (!sock || connectionStatus !== "CONNECTED") {
    throw new Error("WhatsApp is not connected yet. Open http://localhost:8090 to link.");
  }

  let targetJid = connectedJid;
  if (phone && phone.trim().length >= 8) {
    const digits = phone.replace(/\D/g, "");
    if (digits.length >= 10) {
      targetJid = `${digits}@s.whatsapp.net`;
    }
  }

  if (!targetJid) {
    throw new Error("No target WhatsApp JID available.");
  }

  await sock.sendMessage(targetJid, { text: message });
  return targetJid;
}

const server = http.createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(200);
    return res.end();
  }

  if (req.url === "/status" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(
      JSON.stringify({
        status: connectionStatus,
        connected_user: connectedJid,
        qr_data_url: latestQrDataUrl,
        pairing_code: latestPairingCode,
      })
    );
  }

  if (req.url === "/pair-code" && req.method === "POST") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", async () => {
      try {
        const data = JSON.parse(body || "{}");
        let digits = (data.phone || "").replace(/\D/g, "");
        if (digits.length === 10) digits = "91" + digits; // Default India +91 if 10 digits given
        if (digits.length < 11) {
          res.writeHead(400, { "Content-Type": "application/json" });
          return res.end(JSON.stringify({ ok: false, error: "Enter valid 10-digit mobile number" }));
        }
        const code = await sock.requestPairingCode(digits);
        latestPairingCode = code?.match(/.{1,4}/g)?.join("-") || code;
        console.log(`[WhatsApp Bridge] Generated Pairing Code for ${digits}: ${latestPairingCode}`);
        res.writeHead(200, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ ok: true, code: latestPairingCode }));
      } catch (err) {
        res.writeHead(500, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  if ((req.url === "/send" || req.url === "/webhook") && req.method === "POST") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", async () => {
      try {
        const data = JSON.parse(body || "{}");
        const text = data.message || data.text || "";
        const phone = data.phone || "";
        if (!text) {
          res.writeHead(400, { "Content-Type": "application/json" });
          return res.end(JSON.stringify({ ok: false, error: "Missing message field" }));
        }
        const jid = await sendWhatsAppMessage(phone, text);
        res.writeHead(200, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ ok: true, delivered_to: jid }));
      } catch (err) {
        res.writeHead(503, { "Content-Type": "application/json" });
        return res.end(JSON.stringify({ ok: false, error: err.message }));
      }
    });
    return;
  }

  // Interactive Setup Page (Smooth AJAX polling, no flicker, supports QR + Phone Pairing Code)
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>BotX WhatsApp Direct Connect</title>
  <style>
    body {
      background: #0b0f19;
      color: #f1f5f9;
      font-family: system-ui, -apple-system, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }
    .card {
      background: #131b2e;
      border: 1px solid #263554;
      border-radius: 16px;
      padding: 28px 32px;
      max-width: 480px;
      width: 92%;
      text-align: center;
      box-shadow: 0 20px 50px rgba(0,0,0,0.5);
    }
    h1 { font-size: 22px; margin: 0 0 8px; color: #22c55e; }
    p { font-size: 14px; color: #94a3b8; line-height: 1.5; margin: 6px 0; }
    .qr-box {
      background: #ffffff;
      padding: 12px;
      border-radius: 12px;
      display: inline-block;
      margin: 14px 0;
    }
    .badge {
      display: inline-block;
      padding: 6px 14px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 13px;
      margin-bottom: 10px;
    }
    .connected { background: rgba(34,197,94,0.2); color: #4ade80; border: 1px solid #22c55e; }
    .waiting { background: rgba(234,179,8,0.2); color: #facc15; border: 1px solid #eab308; }
    .pair-section {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid #1e293b;
    }
    input {
      padding: 10px 14px;
      border-radius: 8px;
      border: 1px solid #334155;
      background: #0f172a;
      color: #fff;
      font-size: 15px;
      width: 190px;
      margin-right: 8px;
    }
    button {
      padding: 10px 16px;
      border-radius: 8px;
      border: none;
      background: #22c55e;
      color: #052e16;
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
    }
    button:hover { background: #4ade80; }
    .code-display {
      font-size: 28px;
      letter-spacing: 4px;
      font-weight: 800;
      color: #38bdf8;
      background: #0f172a;
      padding: 12px 20px;
      border-radius: 10px;
      border: 1px dashed #38bdf8;
      margin-top: 12px;
      display: none;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>BotX WhatsApp Direct Connect</h1>
    <div id="status-badge" class="badge waiting">⏳ Connecting...</div>

    <div id="connected-view" style="display:none;">
      <p style="font-size:16px; color:#4ade80; font-weight:600;">🎉 WhatsApp Successfully Linked!</p>
      <p id="connected-num"></p>
      <p>Ab aapka 24/7 Liquidity Sweep Bot seedha aapke WhatsApp par trade alerts bhejega!</p>
    </div>

    <div id="qr-view">
      <div class="qr-box">
        <img id="qr-img" src="" alt="Loading QR..." width="260" height="260" />
      </div>
      <p><b>Option 1:</b> WhatsApp &rarr; Linked Devices &rarr; Link a Device se QR scan karein.</p>

      <div class="pair-section">
        <p><b>Option 2 (Bina Camera Scan Kiye):</b> Apna 10-digit WhatsApp Number daal kar <b>8-Digit Code</b> lein:</p>
        <div style="margin-top:8px;">
          <input type="text" id="phone-input" placeholder="e.g. 9876543210" />
          <button onclick="getPairingCode()">Get Code</button>
        </div>
        <div id="pair-code-box" class="code-display"></div>
        <p id="pair-help" style="display:none; font-size:12.5px; color:#cbd5e1;">
          Phone ke WhatsApp mein <b>"Link with phone number instead"</b> par tap karke yeh 8-digit code daal dein!
        </p>
      </div>
    </div>
  </div>

  <script>
    async function pollStatus() {
      try {
        const res = await fetch('/status');
        const data = await res.json();
        const badge = document.getElementById('status-badge');
        const qrView = document.getElementById('qr-view');
        const connView = document.getElementById('connected-view');
        const qrImg = document.getElementById('qr-img');

        if (data.status === 'CONNECTED') {
          badge.className = 'badge connected';
          badge.textContent = '✅ WHATSAPP CONNECTED';
          qrView.style.display = 'none';
          connView.style.display = 'block';
          document.getElementById('connected-num').textContent = 'Account: ' + (data.connected_user || 'Active');
        } else {
          badge.className = 'badge waiting';
          badge.textContent = '📱 SCAN QR OR USE PHONE CODE';
          qrView.style.display = 'block';
          connView.style.display = 'none';
          if (data.qr_data_url) {
            qrImg.src = data.qr_data_url;
          }
        }
      } catch (e) {}
    }

    async function getPairingCode() {
      const phone = document.getElementById('phone-input').value.trim();
      if (!phone) return alert('Apna WhatsApp number daalo bhai!');
      const box = document.getElementById('pair-code-box');
      box.style.display = 'block';
      box.textContent = 'Generating...';
      try {
        const res = await fetch('/pair-code', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone })
        });
        const data = await res.json();
        if (data.ok && data.code) {
          box.textContent = data.code;
          document.getElementById('pair-help').style.display = 'block';
        } else {
          box.textContent = 'Error: ' + (data.error || 'Try again');
        }
      } catch (err) {
        box.textContent = 'Error generating code';
      }
    }

    pollStatus();
    setInterval(pollStatus, 2500);
  </script>
</body>
</html>`);
});

server.listen(PORT, () => {
  console.log(`[WhatsApp Bridge] Server listening at http://localhost:${PORT}`);
  startWhatsApp();
});
