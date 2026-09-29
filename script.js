/**
 * BotX AI Trading Engine - Frontend Dashboard Interaction Controller
 */

// Application State
const state = {
  currentSymbol: "BINANCE:BTCUSDT",
  currentDisplay: "BTC/USDT",
  currentInterval: "15",
  activeFilter: "all",
  alerts: [
    {
      id: "alert-1",
      symbol: "BTC/USDT",
      timeframe: "15M",
      type: "FVG",
      bias: "BULLISH",
      top: 83420.01,
      bottom: 83326.83,
      gapSize: 93.18,
      gapPct: 0.11,
      price: 83845.00,
      status: "Active (Untested)",
      timestamp: "2026-09-29 05:45:00 UTC",
      displacement: "+0.85%",
      fvgConfluence: true,
      unread: true,
    },
    {
      id: "alert-2",
      symbol: "BTC/USDT",
      timeframe: "15M",
      type: "OB",
      bias: "BULLISH",
      top: 83326.83,
      bottom: 82971.00,
      gapSize: 355.83,
      gapPct: 0.43,
      price: 83845.00,
      status: "Active (Untested)",
      timestamp: "2026-09-29 05:30:00 UTC",
      displacement: "+1.05%",
      fvgConfluence: true,
      unread: true,
    },
    {
      id: "alert-3",
      symbol: "BTC/USDT",
      timeframe: "1H",
      type: "FVG",
      bias: "BULLISH",
      top: 83420.01,
      bottom: 83295.61,
      gapSize: 124.40,
      gapPct: 0.15,
      price: 83845.00,
      status: "Active (Untested)",
      timestamp: "2026-09-29 05:00:00 UTC",
      displacement: "+1.20%",
      fvgConfluence: false,
      unread: false,
    },
    {
      id: "alert-4",
      symbol: "BTC/USDT",
      timeframe: "1H",
      type: "OB",
      bias: "BEARISH",
      top: 84045.00,
      bottom: 83800.00,
      gapSize: 245.00,
      gapPct: 0.29,
      price: 83845.00,
      status: "Tested Zone",
      timestamp: "2026-09-28 18:00:00 UTC",
      displacement: "-0.59%",
      fvgConfluence: true,
      unread: false,
    },
    {
      id: "alert-5",
      symbol: "ETH/USDT",
      timeframe: "15M",
      type: "FVG",
      bias: "BULLISH",
      top: 3260.50,
      bottom: 3242.00,
      gapSize: 18.50,
      gapPct: 0.57,
      price: 3248.50,
      status: "Active (Untested)",
      timestamp: "2026-09-29 05:15:00 UTC",
      displacement: "+1.42%",
      fvgConfluence: true,
      unread: false,
    }
  ]
};

// DOM Ready Handler
document.addEventListener("DOMContentLoaded", () => {
  initClock();
  initTradingViewWidget(state.currentSymbol, state.currentInterval);
  initMarketSelectors();
  initTimeframeSelectors();
  initAlertFilters();
  initActionButtons();
  renderAlerts();
});

/**
 * Initialize / Reload TradingView Advanced Chart Widget
 */
function initTradingViewWidget(symbol, interval) {
  const container = document.getElementById("tv_chart_container");
  if (!container) return;

  container.innerHTML = ""; // Clear existing widget

  if (typeof TradingView !== "undefined") {
    new TradingView.widget({
      autosize: true,
      symbol: symbol,
      interval: interval,
      timezone: "Etc/UTC",
      theme: "dark",
      style: "1",
      locale: "en",
      toolbar_bg: "#0f141f",
      enable_publishing: false,
      hide_top_toolbar: false,
      allow_symbol_change: true,
      container_id: "tv_chart_container",
      studies: [
        "MASimple@tv-basicstudies",
        "RSI@tv-basicstudies"
      ],
      disabled_features: ["use_localstorage_for_settings"],
      enabled_features: ["study_templates"]
    });
  }
}

/**
 * Handle Asset Watchlist Selection (Crypto, Forex, Indian Markets)
 */
function initMarketSelectors() {
  const assetButtons = document.querySelectorAll(".asset-item");

  assetButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      assetButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const symbol = btn.getAttribute("data-symbol");
      const display = btn.getAttribute("data-display");

      state.currentSymbol = symbol;
      state.currentDisplay = display;

      // Update Top Nav Header Badges
      const topTitle = document.getElementById("activeChartTitle");
      const topPair = document.getElementById("topActivePair");
      const exchangeBadge = document.getElementById("chartExchangeBadge");

      if (topTitle) topTitle.textContent = display;
      if (topPair) topPair.textContent = display;
      if (exchangeBadge) {
        const parts = symbol.split(":");
        exchangeBadge.textContent = parts[0] || "MARKET";
      }

      // Re-render chart with selected symbol
      initTradingViewWidget(state.currentSymbol, state.currentInterval);
      showToast("Market Switched", `Chart updated to ${display} (${symbol})`);
    });
  });
}

/**
 * Timeframe Button Group Handler
 */
function initTimeframeSelectors() {
  const tfButtons = document.querySelectorAll("#timeframeButtonGroup button");

  tfButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tfButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const interval = btn.getAttribute("data-interval");
      state.currentInterval = interval;

      initTradingViewWidget(state.currentSymbol, state.currentInterval);
      showToast("Timeframe Changed", `Switched to ${btn.textContent.trim()} candle interval`);
    });
  });
}

/**
 * Alert Filter Handler (All, FVG, OB, Active)
 */
function initAlertFilters() {
  const filterBtns = document.querySelectorAll("#alertFilterGroup button");

  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      state.activeFilter = btn.getAttribute("data-filter");
      renderAlerts();
    });
  });
}

/**
 * Render Live SMC Alerts in the Right Panel
 */
function renderAlerts() {
  const container = document.getElementById("alertsListContainer");
  const counter = document.getElementById("alertsCounter");
  const unreadBadge = document.getElementById("unreadBadge");
  if (!container) return;

  container.innerHTML = "";

  const filtered = state.alerts.filter(a => {
    if (state.activeFilter === "FVG") return a.type === "FVG";
    if (state.activeFilter === "OB") return a.type === "OB";
    if (state.activeFilter === "active") return a.status.includes("Active");
    return true; // 'all'
  });

  const activeCount = state.alerts.filter(a => a.status.includes("Active")).length;
  if (counter) counter.textContent = `${activeCount} Active`;
  if (unreadBadge) unreadBadge.textContent = state.alerts.filter(a => a.unread).length;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="text-center py-5 text-muted">
        <i class="bi bi-inbox fs-2 mb-2 d-block"></i>
        <p class="fs-8 m-0">No alerts match the selected filter.</p>
      </div>
    `;
    return;
  }

  filtered.forEach(item => {
    const card = document.createElement("div");
    const biasClass = item.bias.toLowerCase();
    card.className = `alert-card ${biasClass}`;
    card.setAttribute("data-id", item.id);

    const typeBadge = item.type === "FVG" 
      ? `<span class="badge badge-fvg fs-9 fw-semibold font-monospace">FVG</span>`
      : `<span class="badge badge-ob fs-9 fw-semibold font-monospace">ORDER BLOCK</span>`;

    const biasBadge = item.bias === "BULLISH"
      ? `<span class="badge badge-bullish fs-9 font-monospace">🟢 BULLISH</span>`
      : `<span class="badge badge-bearish fs-9 font-monospace">🔴 BEARISH</span>`;

    const statusBadge = item.status.includes("Active")
      ? `<span class="badge bg-success-subtle text-success border border-success-subtle fs-9">${item.status}</span>`
      : `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle fs-9">${item.status}</span>`;

    card.innerHTML = `
      <div class="d-flex justify-content-between align-items-center mb-1">
        <div class="d-flex align-items-center gap-2">
          <span class="fw-bold fs-7 text-light">${item.symbol}</span>
          <span class="badge bg-dark-subtle text-secondary font-monospace fs-9">${item.timeframe}</span>
          ${typeBadge}
        </div>
        ${biasBadge}
      </div>

      <div class="d-flex justify-content-between align-items-center my-2 font-monospace fs-8">
        <div>
          <span class="text-muted">Zone:</span>
          <span class="text-light fw-semibold">$${item.bottom.toLocaleString()} - $${item.top.toLocaleString()}</span>
        </div>
        <div class="text-end text-primary-accent fw-bold">
          ${item.gapSize ? `$${item.gapSize.toFixed(2)} (${item.gapPct}%)` : item.displacement}
        </div>
      </div>

      <div class="d-flex justify-content-between align-items-center pt-1 border-top border-dark-subtle fs-9 text-muted font-monospace">
        <span>${item.timestamp.split(" ")[1]} UTC</span>
        ${statusBadge}
      </div>
    `;

    // Click handler to open detail modal
    card.addEventListener("click", () => {
      item.unread = false;
      openAlertModal(item);
      renderAlerts();
    });

    container.appendChild(card);
  });
}

/**
 * Open Alert Detail Modal
 */
function openAlertModal(item) {
  const modalTitle = document.getElementById("modalAlertTitle");
  const modalBody = document.getElementById("modalAlertBody");
  const modalSendBtn = document.getElementById("modalSendTelegramBtn");

  if (modalTitle) {
    modalTitle.innerHTML = `
      <span>${item.symbol} ${item.timeframe} - ${item.type === "FVG" ? "Fair Value Gap" : "Order Block"}</span>
      <span class="badge ${item.bias === "BULLISH" ? "badge-bullish" : "badge-bearish"} ms-2">${item.bias}</span>
    `;
  }

  if (modalBody) {
    modalBody.innerHTML = `
      <div class="p-3 bg-dark-surface rounded border border-dark-subtle mb-3">
        <div class="row g-2">
          <div class="col-6 text-muted">Asset Symbol:</div>
          <div class="col-6 text-end text-light fw-bold">${item.symbol}</div>

          <div class="col-6 text-muted">Analysis Interval:</div>
          <div class="col-6 text-end text-light">${item.timeframe}</div>

          <div class="col-6 text-muted">Current Market Price:</div>
          <div class="col-6 text-end text-light fw-bold">$${item.price.toLocaleString()}</div>

          <div class="col-6 text-muted">Zone Top:</div>
          <div class="col-6 text-end text-danger fw-bold">$${item.top.toLocaleString()}</div>

          <div class="col-6 text-muted">Zone Bottom:</div>
          <div class="col-6 text-end text-success fw-bold">$${item.bottom.toLocaleString()}</div>

          <div class="col-6 text-muted">Magnitude:</div>
          <div class="col-6 text-end text-primary-accent">${item.gapSize ? `$${item.gapSize.toFixed(2)} (${item.gapPct}%)` : item.displacement}</div>

          <div class="col-6 text-muted">FVG Confluence:</div>
          <div class="col-6 text-end">${item.fvgConfluence ? "YES (High Probability)" : "NO"}</div>

          <div class="col-6 text-muted">Mitigation Status:</div>
          <div class="col-6 text-end"><span class="badge bg-success-subtle text-success">${item.status}</span></div>

          <div class="col-6 text-muted">Detected UTC:</div>
          <div class="col-6 text-end">${item.timestamp}</div>
        </div>
      </div>
      <p class="fs-9 text-muted m-0">Recommended Action: Monitor price action inside the $${item.bottom.toLocaleString()} - $${item.top.toLocaleString()} zone for institutional reaction.</p>
    `;
  }

  if (modalSendBtn) {
    modalSendBtn.onclick = () => {
      showToast("Telegram Forward", `Alert for ${item.symbol} forwarded to @IamDeva_bot!`);
      const modalEl = document.getElementById("alertDetailModal");
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    };
  }

  const modalEl = document.getElementById("alertDetailModal");
  if (modalEl) {
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
  }
}

/**
 * Action Buttons (Scan SMC, Send Telegram Alert, Clear)
 */
function initActionButtons() {
  // Trigger SMC Scan
  const scanBtn = document.getElementById("triggerScanBtn");
  if (scanBtn) {
    scanBtn.addEventListener("click", () => {
      scanBtn.disabled = true;
      scanBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Scanning...`;

      setTimeout(() => {
        scanBtn.disabled = false;
        scanBtn.innerHTML = `<i class="bi bi-search me-1"></i>Scan SMC`;

        // Inject simulated new live setup
        const newAlert = {
          id: `alert-${Date.now()}`,
          symbol: state.currentDisplay,
          timeframe: `${state.currentInterval === "D" ? "1D" : state.currentInterval + "M"}`,
          type: Math.random() > 0.5 ? "FVG" : "OB",
          bias: Math.random() > 0.3 ? "BULLISH" : "BEARISH",
          top: 83920.00,
          bottom: 83850.00,
          gapSize: 70.00,
          gapPct: 0.08,
          price: 83880.00,
          status: "Active (Untested)",
          timestamp: new Date().toISOString().replace("T", " ").substring(0, 19) + " UTC",
          displacement: "+0.92%",
          fvgConfluence: true,
          unread: true,
        };

        state.alerts.unshift(newAlert);
        renderAlerts();
        showToast("Scan Complete", `New ${newAlert.bias} ${newAlert.type} setup identified on ${newAlert.symbol}!`);
      }, 900);
    });
  }

  // Dispatch Telegram Alert
  const dispatchBtn = document.getElementById("dispatchTelegramBtn");
  if (dispatchBtn) {
    dispatchBtn.addEventListener("click", () => {
      showToast("Telegram Alert Dispatched", `Sent active SMC setups to Telegram (@IamDeva_bot)`);
    });
  }

  // Clear Alerts
  const clearBtn = document.getElementById("clearAlertsBtn");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      state.alerts = [];
      renderAlerts();
      showToast("Alerts Cleared", "Cleared all notifications from panel");
    });
  }
}

/**
 * Toast Notification Utility
 */
function showToast(title, message) {
  const toastEl = document.getElementById("liveToast");
  const toastTitle = document.getElementById("toastTitle");
  const toastMsg = document.getElementById("toastMessage");

  if (toastEl && toastTitle && toastMsg) {
    toastTitle.textContent = title;
    toastMsg.textContent = message;
    const toast = new bootstrap.Toast(toastEl, { delay: 3500 });
    toast.show();
  }
}

/**
 * UTC Clock in Header
 */
function initClock() {
  const clockEl = document.getElementById("liveUtcClock");
  if (!clockEl) return;

  function update() {
    const now = new Date();
    const utcStr = now.toUTCString().split(" ")[4];
    clockEl.textContent = `${utcStr} UTC`;
  }
  update();
  setInterval(update, 1000);
}
