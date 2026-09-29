/**
 * BotX AI Trading Engine - Multi-Asset Interactive Dashboard Controller
 * Fully supports: BTC/USDT, ETH/USDT, XAUUSD, US100, XAUJPY, XAGUSD, and Forex/Indices.
 */

// Application State
const state = {
  currentSymbol: "BINANCE:BTCUSDT",
  currentDisplay: "BTC/USDT",
  currentPrice: "83,845.00",
  currentChange: "+0.82%",
  currentInterval: "15",
  activeTypeFilter: "all",    // 'all', 'FVG', 'OB', 'active'
  filterByAsset: true,        // When true, displays alerts specifically for currentDisplay

  // Multi-Asset Live SMC Setups
  alerts: [
    // --- BTC/USDT Setups ---
    {
      id: "btc-fvg-15m",
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
      id: "btc-ob-15m",
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
      id: "btc-fvg-1h",
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
      id: "btc-ob-1h",
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

    // --- ETH/USDT Setups ---
    {
      id: "eth-fvg-15m",
      symbol: "ETH/USDT",
      timeframe: "15M",
      type: "FVG",
      bias: "BULLISH",
      top: 2682.00,
      bottom: 2668.50,
      gapSize: 13.50,
      gapPct: 0.51,
      price: 2692.43,
      status: "Active (Untested)",
      timestamp: "2026-09-29 05:45:00 UTC",
      displacement: "+1.35%",
      fvgConfluence: true,
      unread: true,
    },
    {
      id: "eth-ob-1h",
      symbol: "ETH/USDT",
      timeframe: "1H",
      type: "OB",
      bias: "BULLISH",
      top: 2660.00,
      bottom: 2642.00,
      gapSize: 18.00,
      gapPct: 0.68,
      price: 2692.43,
      status: "Active (Untested)",
      timestamp: "2026-09-29 04:00:00 UTC",
      displacement: "+1.85%",
      fvgConfluence: true,
      unread: false,
    },
    {
      id: "eth-fvg-1h",
      symbol: "ETH/USDT",
      timeframe: "1H",
      type: "FVG",
      bias: "BEARISH",
      top: 2715.00,
      bottom: 2704.00,
      gapSize: 11.00,
      gapPct: 0.41,
      price: 2692.43,
      status: "Active (Untested)",
      timestamp: "2026-09-28 22:00:00 UTC",
      displacement: "-1.10%",
      fvgConfluence: false,
      unread: false,
    },

    // --- XAUUSD (Gold) Setups ---
    {
      id: "xau-fvg-15m",
      symbol: "XAUUSD",
      timeframe: "15M",
      type: "FVG",
      bias: "BULLISH",
      top: 4169.80,
      bottom: 4165.60,
      gapSize: 4.20,
      gapPct: 0.10,
      price: 4174.50,
      status: "Active (Untested)",
      timestamp: "2026-09-29 01:00:00 UTC",
      displacement: "+0.45%",
      fvgConfluence: true,
      unread: true,
    },
    {
      id: "xau-ob-1h",
      symbol: "XAUUSD",
      timeframe: "1H",
      type: "OB",
      bias: "BULLISH",
      top: 4165.00,
      bottom: 4155.90,
      gapSize: 9.10,
      gapPct: 0.22,
      price: 4174.50,
      status: "Active (Untested)",
      timestamp: "2026-09-29 00:00:00 UTC",
      displacement: "+0.51%",
      fvgConfluence: true,
      unread: true,
    },
    {
      id: "xau-fvg-1h",
      symbol: "XAUUSD",
      timeframe: "1H",
      type: "FVG",
      bias: "BEARISH",
      top: 4226.80,
      bottom: 4213.80,
      gapSize: 13.00,
      gapPct: 0.31,
      price: 4174.50,
      status: "Active (Untested)",
      timestamp: "2026-09-28 01:00:00 UTC",
      displacement: "-0.85%",
      fvgConfluence: true,
      unread: false,
    },

    // --- US100 (Nasdaq) Setups ---
    {
      id: "us100-ob-15m",
      symbol: "US100",
      timeframe: "15M",
      type: "OB",
      bias: "BULLISH",
      top: 30425.00,
      bottom: 30372.00,
      gapSize: 53.00,
      gapPct: 0.17,
      price: 30498.00,
      status: "Active (Untested)",
      timestamp: "2026-09-29 01:30:00 UTC",
      displacement: "+0.41%",
      fvgConfluence: true,
      unread: true,
    },
    {
      id: "us100-fvg-1h",
      symbol: "US100",
      timeframe: "1H",
      type: "FVG",
      bias: "BEARISH",
      top: 30791.50,
      bottom: 30759.75,
      gapSize: 31.75,
      gapPct: 0.10,
      price: 30498.00,
      status: "Active (Untested)",
      timestamp: "2026-09-27 21:00:00 UTC",
      displacement: "-0.62%",
      fvgConfluence: true,
      unread: false,
    },
    {
      id: "us100-ob-1h",
      symbol: "US100",
      timeframe: "1H",
      type: "OB",
      bias: "BEARISH",
      top: 30529.00,
      bottom: 30430.00,
      gapSize: 99.00,
      gapPct: 0.32,
      price: 30498.00,
      status: "Tested Zone",
      timestamp: "2026-09-28 21:00:00 UTC",
      displacement: "-0.32%",
      fvgConfluence: true,
      unread: false,
    },

    // --- XAGUSD (Silver) Setups ---
    {
      id: "xag-fvg-15m",
      symbol: "XAGUSD",
      timeframe: "15M",
      type: "FVG",
      bias: "BULLISH",
      top: 60.85,
      bottom: 60.60,
      gapSize: 0.25,
      gapPct: 0.41,
      price: 61.18,
      status: "Active (Untested)",
      timestamp: "2026-09-29 02:15:00 UTC",
      displacement: "+0.65%",
      fvgConfluence: true,
      unread: true,
    },
    {
      id: "xag-ob-1h",
      symbol: "XAGUSD",
      timeframe: "1H",
      type: "OB",
      bias: "BULLISH",
      top: 60.50,
      bottom: 59.95,
      gapSize: 0.55,
      gapPct: 0.92,
      price: 61.18,
      status: "Active (Untested)",
      timestamp: "2026-09-28 23:00:00 UTC",
      displacement: "+1.15%",
      fvgConfluence: true,
      unread: false,
    },

    // --- XAUJPY (Gold / Yen) Setups ---
    {
      id: "xaujpy-fvg-15m",
      symbol: "XAUJPY",
      timeframe: "15M",
      type: "FVG",
      bias: "BULLISH",
      top: 655800.00,
      bottom: 654200.00,
      gapSize: 1600.00,
      gapPct: 0.24,
      price: 656690.00,
      status: "Active (Untested)",
      timestamp: "2026-09-29 01:15:00 UTC",
      displacement: "+0.72%",
      fvgConfluence: true,
      unread: true,
    },
    {
      id: "xaujpy-ob-1h",
      symbol: "XAUJPY",
      timeframe: "1H",
      type: "OB",
      bias: "BULLISH",
      top: 654500.00,
      bottom: 652800.00,
      gapSize: 1700.00,
      gapPct: 0.26,
      price: 656690.00,
      status: "Active (Untested)",
      timestamp: "2026-09-29 00:00:00 UTC",
      displacement: "+0.85%",
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
  initScopeToggle();
  renderAlerts();
});

/**
 * Initialize or Reload TradingView Advanced Chart Widget
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
 * Handle Asset Watchlist Selection (Crypto, Metals, Indices, Forex)
 */
function initMarketSelectors() {
  const assetButtons = document.querySelectorAll(".asset-item");

  assetButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      assetButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const symbol = btn.getAttribute("data-symbol");
      const display = btn.getAttribute("data-display");
      const price = btn.getAttribute("data-price") || "---";
      const change = btn.getAttribute("data-change") || "+0.00%";

      state.currentSymbol = symbol;
      state.currentDisplay = display;
      state.currentPrice = price;
      state.currentChange = change;

      // Update Top Nav Header Badges
      const topTitle = document.getElementById("activeChartTitle");
      const topPair = document.getElementById("topActivePair");
      const topPrice = document.getElementById("topPrice");
      const topChange = document.getElementById("topChange");
      const exchangeBadge = document.getElementById("chartExchangeBadge");
      const alertAssetBadge = document.getElementById("currentAlertAssetBadge");

      if (topTitle) topTitle.textContent = display;
      if (topPair) topPair.textContent = display;
      if (topPrice) topPrice.textContent = `$${price}`;
      if (topChange) {
        topChange.textContent = change;
        topChange.className = change.startsWith("-") 
          ? "badge bg-danger-subtle text-danger fs-8 font-monospace"
          : "badge bg-success-subtle text-success fs-8 font-monospace";
      }

      if (exchangeBadge) {
        const parts = symbol.split(":");
        exchangeBadge.textContent = parts[0] || "MARKET";
      }

      if (alertAssetBadge) {
        alertAssetBadge.textContent = display;
      }

      // Re-render chart with selected symbol
      initTradingViewWidget(state.currentSymbol, state.currentInterval);

      // Re-render alerts panel specifically for the newly selected asset
      renderAlerts();

      showToast("Market Switched", `Chart & Live SMC feed switched to ${display}`);
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

      state.activeTypeFilter = btn.getAttribute("data-filter");
      renderAlerts();
    });
  });
}

/**
 * Toggle Between Selected Asset vs All Assets in Alerts Feed
 */
function initScopeToggle() {
  const scopeBtn = document.getElementById("toggleAssetScopeBtn");
  const scopeText = document.getElementById("scopeBtnText");
  const alertAssetBadge = document.getElementById("currentAlertAssetBadge");

  if (scopeBtn) {
    scopeBtn.addEventListener("click", () => {
      state.filterByAsset = !state.filterByAsset;

      if (state.filterByAsset) {
        if (scopeText) scopeText.textContent = "Show All Assets";
        if (alertAssetBadge) alertAssetBadge.textContent = state.currentDisplay;
      } else {
        if (scopeText) scopeText.textContent = `Filter by ${state.currentDisplay}`;
        if (alertAssetBadge) alertAssetBadge.textContent = "ALL ASSETS";
      }

      renderAlerts();
      showToast("Alert Scope Updated", state.filterByAsset ? `Filtering alerts for ${state.currentDisplay}` : "Showing alerts for all assets");
    });
  }
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

  // Filter 1: By Asset (if filterByAsset is true)
  let list = state.alerts;
  if (state.filterByAsset) {
    list = list.filter(a => a.symbol === state.currentDisplay);
  }

  // Filter 2: By Type (All, FVG, OB, Active)
  const filtered = list.filter(a => {
    if (state.activeTypeFilter === "FVG") return a.type === "FVG";
    if (state.activeTypeFilter === "OB") return a.type === "OB";
    if (state.activeTypeFilter === "active") return a.status.includes("Active");
    return true; // 'all'
  });

  const activeCount = filtered.filter(a => a.status.includes("Active")).length;
  if (counter) counter.textContent = `${activeCount} Active`;
  if (unreadBadge) unreadBadge.textContent = state.alerts.filter(a => a.unread).length;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="text-center py-5 text-muted">
        <i class="bi bi-inbox fs-2 mb-2 d-block"></i>
        <p class="fs-8 m-0">No alerts match for ${state.filterByAsset ? state.currentDisplay : "the selected filter"}.</p>
        ${state.filterByAsset ? `<button class="btn btn-sm btn-link text-info fs-8 mt-2" onclick="document.getElementById('toggleAssetScopeBtn').click()">Show All Assets</button>` : ""}
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
      <p class="fs-9 text-muted m-0">Institutional Trading Recommendation: Monitor reaction within the $${item.bottom.toLocaleString()} - $${item.top.toLocaleString()} zone on lower timeframes (1m-5m) for confirmation.</p>
    `;
  }

  if (modalSendBtn) {
    modalSendBtn.onclick = () => {
      showToast("Telegram Forward", `Alert for ${item.symbol} (${item.timeframe}) forwarded to @IamDeva_bot!`);
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
  // Trigger SMC Scan for Current Asset
  const scanBtn = document.getElementById("triggerScanBtn");
  if (scanBtn) {
    scanBtn.addEventListener("click", () => {
      scanBtn.disabled = true;
      scanBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Scanning...`;

      setTimeout(() => {
        scanBtn.disabled = false;
        scanBtn.innerHTML = `<i class="bi bi-search me-1"></i>Scan SMC`;

        // Calculate realistic price range based on current asset
        const numPrice = parseFloat(state.currentPrice.replace(/,/g, "")) || 100.0;
        const delta = numPrice * 0.003;
        const top = Math.round((numPrice + delta) * 100) / 100;
        const bottom = Math.round((numPrice - delta) * 100) / 100;

        const newAlert = {
          id: `alert-${Date.now()}`,
          symbol: state.currentDisplay,
          timeframe: `${state.currentInterval === "D" ? "1D" : state.currentInterval + "M"}`,
          type: Math.random() > 0.5 ? "FVG" : "OB",
          bias: Math.random() > 0.35 ? "BULLISH" : "BEARISH",
          top: top,
          bottom: bottom,
          gapSize: Math.round((top - bottom) * 100) / 100,
          gapPct: 0.12,
          price: numPrice,
          status: "Active (Untested)",
          timestamp: new Date().toISOString().replace("T", " ").substring(0, 19) + " UTC",
          displacement: "+0.88%",
          fvgConfluence: true,
          unread: true,
        };

        state.alerts.unshift(newAlert);
        renderAlerts();
        showToast("Scan Complete", `New ${newAlert.bias} ${newAlert.type} setup identified on ${newAlert.symbol}!`);
      }, 750);
    });
  }

  // Dispatch Telegram Alert for Current Asset
  const dispatchBtn = document.getElementById("dispatchTelegramBtn");
  if (dispatchBtn) {
    dispatchBtn.addEventListener("click", () => {
      showToast("Telegram Alert Dispatched", `Sent active ${state.currentDisplay} SMC setups to Telegram (@IamDeva_bot)`);
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
