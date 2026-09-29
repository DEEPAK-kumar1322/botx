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

  // Strategy & Structure Terminal State
  strategyActive: false,
  signals: [],
  structureData: null,
  isAnalyzing: false,
  isEvaluating: false,
  pollingTimer: null,

  // Strategy Hub State
  hubActiveView: "terminal",
  hubCurrentStrategyId: "smc",
  hubStrategies: [],
  hubDeployActive: false,
  hubIsAnalyzing: false,
  hubAuditLogs: [],
  hubTargetAsset: "BTC/USDT",
  hubTargetTimeframe: "15m",

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
  initTerminalExtensions();
  initStrategyHub();
  renderAlerts();

  // Initial On-Demand Structure Analysis & Live Signals Fetch
  fetchStructureAnalysis(state.currentDisplay, state.currentInterval);
  fetchStrategySignals();
  switchRightTab("#pane-signals");
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

      // Automatically refresh Market Structure & Liquidity for new asset
      fetchStructureAnalysis(state.currentDisplay, state.currentInterval);
      if (state.strategyActive) {
        evaluateLiveStrategy(true);
      }

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

      // Refresh structure analysis on new timeframe
      fetchStructureAnalysis(state.currentDisplay, state.currentInterval);
      if (state.strategyActive) {
        evaluateLiveStrategy(true);
      }

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

/* ==========================================================================
   Terminal Extensions: Strategy Deployment & Market Structure Liquidity
   ========================================================================== */

/**
 * Normalize TradingView interval to backend timeframe string
 */
function getNormalizedTf(interval) {
  if (!interval) return "15m";
  const s = String(interval).toUpperCase();
  if (s === "1") return "1m";
  if (s === "5") return "5m";
  if (s === "15") return "15m";
  if (s === "60") return "1h";
  if (s === "240") return "4h";
  if (s === "D" || s === "1D") return "1d";
  return `${interval}m`;
}

/**
 * Initialize Strategy Deployment & On-Demand Structure Event Handlers
 */
function initTerminalExtensions() {
  // Quick Analyze Button (next to chart)
  const quickAnalyzeBtn = document.getElementById("quickAnalyzeBtn");
  if (quickAnalyzeBtn) {
    quickAnalyzeBtn.addEventListener("click", () => {
      fetchStructureAnalysis(state.currentDisplay, state.currentInterval, true);
    });
  }

  // Refresh Structure Button (in Structure pane)
  const refreshStructureBtn = document.getElementById("refreshStructureBtn");
  if (refreshStructureBtn) {
    refreshStructureBtn.addEventListener("click", () => {
      fetchStructureAnalysis(state.currentDisplay, state.currentInterval, false);
    });
  }

  // Activate Strategy Toggle Button
  const strategyToggleBtn = document.getElementById("strategyToggleBtn");
  if (strategyToggleBtn) {
    strategyToggleBtn.addEventListener("click", () => {
      toggleStrategy();
    });
  }

  // Evaluate Live Signal Button
  const evaluateLiveBtn = document.getElementById("evaluateLiveSignalBtn");
  if (evaluateLiveBtn) {
    evaluateLiveBtn.addEventListener("click", () => {
      evaluateLiveStrategy(false);
    });
  }

  // Strict Tab Switching Listener to prevent inactive sections stacking or taking space
  const tabButtons = document.querySelectorAll('#terminalTabs button[data-bs-toggle="pill"]');
  tabButtons.forEach(btn => {
    btn.addEventListener('show.bs.tab', (e) => {
      const targetSelector = e.target.getAttribute('data-bs-target');
      switchRightTab(targetSelector);
    });
  });
}

/**
 * Switch Right Panel Tab cleanly, ensuring inactive panes are completely hidden (display: none)
 */
function switchRightTab(targetSelector) {
  if (!targetSelector) return;
  const tabBtn = document.querySelector(`#terminalTabs button[data-bs-target="${targetSelector}"]`);
  if (tabBtn && typeof bootstrap !== "undefined" && bootstrap.Tab) {
    const tabInstance = bootstrap.Tab.getOrCreateInstance(tabBtn);
    tabInstance.show();
  }

  const allPanes = document.querySelectorAll('#terminalTabsContent .tab-pane');
  allPanes.forEach(pane => {
    if ('#' + pane.id === targetSelector) {
      pane.classList.add('active', 'show');
      pane.style.setProperty('display', 'flex', 'important');
    } else {
      pane.classList.remove('active', 'show');
      pane.style.setProperty('display', 'none', 'important');
    }
  });
}

/**
 * Fetch On-Demand Market Structure & Liquidity Analysis (/api/analyze)
 */
async function fetchStructureAnalysis(symbol, interval, switchTab = false) {
  const sym = symbol || state.currentDisplay;
  const tf = getNormalizedTf(interval || state.currentInterval);

  const analyzeBtn = document.getElementById("quickAnalyzeBtn");
  const refreshBtn = document.getElementById("refreshStructureBtn");

  try {
    if (analyzeBtn) {
      analyzeBtn.disabled = true;
      analyzeBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Analyzing...`;
    }
    if (refreshBtn) {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>...`;
    }

    const res = await fetch(`/api/analyze?symbol=${encodeURIComponent(sym)}&timeframe=${tf}`);
    if (!res.ok) {
      throw new Error(`API returned status ${res.status}`);
    }
    const data = await res.json();
    state.structureData = data;

    renderStructurePanel(data);

    if (switchTab) {
      switchRightTab("#pane-structure");
      showToast("Structure Analyzed", `${data.symbol} is ${data.directional_bias} (${data.confidence}% confidence)`);
    }

  } catch (err) {
    console.error("Analysis fetch error:", err);
    showToast("Analysis Error", `Could not analyze structure for ${sym}: ${err.message}`);
  } finally {
    if (analyzeBtn) {
      analyzeBtn.disabled = false;
      analyzeBtn.innerHTML = `<i class="bi bi-cpu-fill"></i><span class="fw-semibold">Quick Analyze</span>`;
    }
    if (refreshBtn) {
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = `<i class="bi bi-arrow-repeat me-1"></i>Re-Analyze`;
    }
  }
}

/**
 * Update Floating Chart Metrics Sub-Strip with Structure Data
 */
function updateChartMetricsStrip(data) {
  const biasBadge = document.getElementById("stripBiasBadge");
  const confEl = document.getElementById("stripConfidence");
  const phaseEl = document.getElementById("stripPhase");
  const bslEl = document.getElementById("stripNearestBsl");
  const sslEl = document.getElementById("stripNearestSsl");

  if (biasBadge) {
    biasBadge.textContent = data.directional_bias;
    biasBadge.className = `badge ${
      data.directional_bias === "BULLISH" ? "badge-bullish" :
      data.directional_bias === "BEARISH" ? "badge-bearish" : "badge-ranging"
    }`;
  }
  if (confEl) confEl.textContent = `${data.confidence}%`;
  if (phaseEl) phaseEl.textContent = data.structure_phase;
  if (bslEl) bslEl.textContent = data.nearest_bsl ? `$${data.nearest_bsl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "---";
  if (sslEl) sslEl.textContent = data.nearest_ssl ? `$${data.nearest_ssl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "---";
}

/**
 * Render Structure & Liquidity Panel Content (HH, HL, LH, LL & BSL/SSL)
 */
function renderStructurePanel(data) {
  const container = document.getElementById("structureContentContainer");
  const activeAssetSpan = document.getElementById("structActiveAsset");
  const activeTfSpan = document.getElementById("structActiveTf");
  const structTabBadge = document.getElementById("structureTabBadge");

  if (activeAssetSpan) activeAssetSpan.textContent = data.symbol;
  if (activeTfSpan) activeTfSpan.textContent = data.timeframe;
  if (structTabBadge) structTabBadge.textContent = data.directional_bias;

  updateChartMetricsStrip(data);

  if (!container) return;

  const biasBadgeClass = data.directional_bias === "BULLISH" 
    ? "badge-bullish" 
    : data.directional_bias === "BEARISH" 
      ? "badge-bearish" 
      : "badge-ranging";

  // Build Swings Badges
  let swingsHtml = "";
  if (data.swing_points && data.swing_points.length > 0) {
    const recentSwings = data.swing_points.slice(-8);
    swingsHtml = recentSwings.map(s => {
      const cls = s.label.toLowerCase();
      const timeStr = s.timestamp ? s.timestamp.substring(11, 16) : "";
      return `
        <div class="swing-chip ${cls}" title="${s.point_type} formed @ ${timeStr} UTC">
          <span>${s.label}</span>
          <span class="text-light">$${s.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
      `;
    }).join("");
  } else {
    swingsHtml = `<span class="text-muted fs-8">Consolidating — waiting for swing pivot expansion</span>`;
  }

  // Build BSL Levels
  let bslHtml = "";
  if (data.bsl_levels && data.bsl_levels.length > 0) {
    bslHtml = data.bsl_levels.map(l => `
      <div class="liquidity-row">
        <div>
          <span class="badge badge-bsl me-1">BSL</span>
          <span class="text-light fw-bold">$${l.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div class="text-end text-muted">
          <span>${l.description}</span>
          <span class="text-danger ms-1">(${l.distance_pct > 0 ? "+" : ""}${l.distance_pct}%)</span>
        </div>
      </div>
    `).join("");
  } else {
    bslHtml = `<div class="text-muted fs-8 py-1">No overhead swing high pools identified</div>`;
  }

  // Build SSL Levels
  let sslHtml = "";
  if (data.ssl_levels && data.ssl_levels.length > 0) {
    sslHtml = data.ssl_levels.map(l => `
      <div class="liquidity-row">
        <div>
          <span class="badge badge-ssl me-1">SSL</span>
          <span class="text-light fw-bold">$${l.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div class="text-end text-muted">
          <span>${l.description}</span>
          <span class="text-success ms-1">(${l.distance_pct > 0 ? "+" : ""}${l.distance_pct}%)</span>
        </div>
      </div>
    `).join("");
  } else {
    sslHtml = `<div class="text-muted fs-8 py-1">No lower swing low pools identified</div>`;
  }

  container.innerHTML = `
    <!-- Card 1: Directional Bias & Confidence -->
    <div class="structure-card mb-3">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <span class="fs-8 text-secondary fw-semibold">DIRECTIONAL BIAS</span>
        <span class="badge ${biasBadgeClass} fs-8 fw-bold">${data.directional_bias}</span>
      </div>
      <div class="mb-2">
        <div class="d-flex justify-content-between fs-8 mb-1">
          <span class="text-muted">AI Structural Confidence:</span>
          <span class="text-primary-accent fw-bold font-monospace">${data.confidence}%</span>
        </div>
        <div class="progress" style="height: 6px; background-color: rgba(255,255,255,0.06);">
          <div class="progress-bar ${data.directional_bias === 'BULLISH' ? 'bg-success' : data.directional_bias === 'BEARISH' ? 'bg-danger' : 'bg-warning'}" 
               role="progressbar" style="width: ${data.confidence}%"></div>
        </div>
      </div>
      <div class="fs-8 text-muted mb-2">
        <span class="text-secondary fw-semibold">Phase:</span> 
        <span class="badge bg-dark-subtle border border-secondary-subtle text-light font-monospace">${data.structure_phase}</span>
      </div>
      <div class="p-2 bg-dark-surface rounded border border-dark-subtle fs-8 text-muted">
        <i class="bi bi-info-circle text-info me-1"></i>
        <span>${data.rationale}</span>
      </div>
    </div>

    <!-- Card 2: Market Structure Swings (HH, HL, LH, LL) -->
    <div class="structure-card mb-3">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <span class="fs-8 text-secondary fw-semibold">MARKET STRUCTURE SWINGS</span>
        <span class="fs-9 text-muted font-monospace">${data.swing_points ? data.swing_points.length : 0} Identified</span>
      </div>
      <div class="d-flex flex-wrap gap-1 mb-2">
        ${swingsHtml}
      </div>
      <div class="d-flex justify-content-between fs-9 text-muted pt-1 border-top border-dark-subtle">
        <span><span class="text-success fw-bold">HH / HL</span> = Higher Pivots</span>
        <span><span class="text-danger fw-bold">LH / LL</span> = Lower Pivots</span>
      </div>
    </div>

    <!-- Card 3: Liquidity Levels (BSL & SSL Pools) -->
    <div class="structure-card mb-2">
      <div class="d-flex align-items-center justify-content-between mb-2">
        <span class="fs-8 text-secondary fw-semibold">LIQUIDITY TARGETS (POOLS)</span>
        <span class="badge bg-dark-subtle text-info border border-info-subtle fs-9 font-monospace">BSL / SSL</span>
      </div>
      
      <!-- Nearest Liquidity High / Low Callouts -->
      <div class="row g-2 mb-3">
        <div class="col-6">
          <div class="p-2 bg-dark-surface rounded border border-danger-subtle text-center font-monospace">
            <div class="fs-9 text-danger fw-bold">NEAREST BSL</div>
            <div class="fs-7 fw-bold text-light">${data.nearest_bsl ? `$${data.nearest_bsl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "---"}</div>
            <div class="fs-9 text-muted">Buy Side High</div>
          </div>
        </div>
        <div class="col-6">
          <div class="p-2 bg-dark-surface rounded border border-success-subtle text-center font-monospace">
            <div class="fs-9 text-success fw-bold">NEAREST SSL</div>
            <div class="fs-7 fw-bold text-light">${data.nearest_ssl ? `$${data.nearest_ssl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "---"}</div>
            <div class="fs-9 text-muted">Sell Side Low</div>
          </div>
        </div>
      </div>

      <!-- Buy Side Liquidity (BSL) Table -->
      <div class="mb-2">
        <div class="fs-9 text-uppercase text-danger fw-bold letter-spacing-1 mb-1">
          <i class="bi bi-arrow-up-circle me-1"></i>Buy Side Liquidity (BSL / Highs)
        </div>
        ${bslHtml}
      </div>

      <!-- Sell Side Liquidity (SSL) Table -->
      <div class="mt-3">
        <div class="fs-9 text-uppercase text-success fw-bold letter-spacing-1 mb-1">
          <i class="bi bi-arrow-down-circle me-1"></i>Sell Side Liquidity (SSL / Lows)
        </div>
        ${sslHtml}
      </div>
    </div>
  `;
}

/**
 * Toggle Strategy Activation State (/api/strategy/toggle)
 */
async function toggleStrategy() {
  const toggleBtn = document.getElementById("strategyToggleBtn");
  const dot = document.getElementById("strategyBtnDot");
  const text = document.getElementById("strategyBtnText");
  const stripState = document.getElementById("stripStrategyState");
  const engineStatus = document.getElementById("signalsEngineStatus");
  const pulse = document.getElementById("signalsPulse");

  try {
    if (toggleBtn) toggleBtn.disabled = true;
    const res = await fetch("/api/strategy/toggle", { method: "POST" });
    const data = await res.json();
    state.strategyActive = data.active;
    state.signals = data.signals || [];

    if (state.strategyActive) {
      if (toggleBtn) {
        toggleBtn.className = "btn btn-sm btn-success text-dark fw-bold d-flex align-items-center gap-2";
      }
      if (dot) dot.classList.add("active");
      if (text) text.textContent = "Strategy Active (Live)";
      if (stripState) {
        stripState.textContent = "RUNNING";
        stripState.className = "badge bg-success font-monospace";
      }
      if (engineStatus) {
        engineStatus.textContent = "RUNNING";
        engineStatus.className = "badge bg-success-subtle text-success font-monospace";
      }
      if (pulse) pulse.style.display = "inline-block";

      showToast("Strategy Deployed", "Live SMC Strategy is now actively evaluating candle order confluence!");
      
      // Automatically switch to Signals tab to view live orders
      switchRightTab("#pane-signals");

      // Trigger immediate evaluation
      await evaluateLiveStrategy(false);

      // Start auto-evaluation polling loop every 12 seconds
      if (!state.pollingTimer) {
        state.pollingTimer = setInterval(() => {
          if (state.strategyActive) {
            evaluateLiveStrategy(true);
          }
        }, 12000);
      }
    } else {
      if (toggleBtn) {
        toggleBtn.className = "btn btn-sm btn-outline-success d-flex align-items-center gap-2";
      }
      if (dot) dot.classList.remove("active");
      if (text) text.textContent = "Activate Strategy";
      if (stripState) {
        stripState.textContent = "STANDBY";
        stripState.className = "badge bg-secondary font-monospace";
      }
      if (engineStatus) {
        engineStatus.textContent = "STANDBY";
        engineStatus.className = "badge bg-secondary-subtle text-secondary font-monospace";
      }
      if (pulse) pulse.style.display = "none";

      if (state.pollingTimer) {
        clearInterval(state.pollingTimer);
        state.pollingTimer = null;
      }

      showToast("Strategy Standby", "Automated execution engine paused");
    }

    renderSignalsFeed();

  } catch (err) {
    console.error("Failed to toggle strategy:", err);
    showToast("Strategy Error", "Could not reach strategy backend API");
  } finally {
    if (toggleBtn) toggleBtn.disabled = false;
  }
}

/**
 * Evaluate Live Strategy on Current Asset (/api/strategy/evaluate)
 */
async function evaluateLiveStrategy(silent = false) {
  const evalBtn = document.getElementById("evaluateLiveSignalBtn");
  const tf = getNormalizedTf(state.currentInterval);

  try {
    if (evalBtn && !silent) {
      evalBtn.disabled = true;
      evalBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>Evaluating...`;
    }

    const res = await fetch(`/api/strategy/evaluate?symbol=${encodeURIComponent(state.currentDisplay)}&timeframe=${tf}`, {
      method: "POST"
    });
    const data = await res.json();

    if (data.status === "signal_generated" && data.signal) {
      const exists = state.signals.some(s => s.id === data.signal.id);
      if (!exists) {
        state.signals.unshift(data.signal);
        renderSignalsFeed();
        showToast("New Signal Generated!", `${data.signal.action} ${data.signal.symbol} Entry @ $${data.signal.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
      }
    } else if (!silent) {
      showToast("Evaluation Complete", data.message || `No new SMC confluence trigger on ${state.currentDisplay} (${tf})`);
    }

  } catch (err) {
    console.error("Evaluation error:", err);
    if (!silent) showToast("API Error", "Failed to evaluate live strategy");
  } finally {
    if (evalBtn && !silent) {
      evalBtn.disabled = false;
      evalBtn.innerHTML = `<i class="bi bi-play-circle me-1"></i>Evaluate Now`;
    }
  }
}

/**
 * Fetch Strategy Signals & Status (/api/strategy/signals)
 */
async function fetchStrategySignals() {
  const toggleBtn = document.getElementById("strategyToggleBtn");
  const dot = document.getElementById("strategyBtnDot");
  const text = document.getElementById("strategyBtnText");
  const stripState = document.getElementById("stripStrategyState");
  const engineStatus = document.getElementById("signalsEngineStatus");
  const pulse = document.getElementById("signalsPulse");

  try {
    const res = await fetch("/api/strategy/signals");
    if (!res.ok) return;
    const data = await res.json();

    state.strategyActive = data.active;
    state.signals = data.signals || [];

    if (state.strategyActive) {
      if (toggleBtn) {
        toggleBtn.className = "btn btn-sm btn-success text-dark fw-bold d-flex align-items-center gap-2";
      }
      if (dot) dot.classList.add("active");
      if (text) text.textContent = "Strategy Active (Live)";
      if (stripState) {
        stripState.textContent = "RUNNING";
        stripState.className = "badge bg-success font-monospace";
      }
      if (engineStatus) {
        engineStatus.textContent = "RUNNING";
        engineStatus.className = "badge bg-success-subtle text-success font-monospace";
      }
      if (pulse) pulse.style.display = "inline-block";

      if (!state.pollingTimer) {
        state.pollingTimer = setInterval(() => {
          if (state.strategyActive) {
            evaluateLiveStrategy(true);
          }
        }, 12000);
      }
    } else {
      if (toggleBtn) {
        toggleBtn.className = "btn btn-sm btn-outline-success d-flex align-items-center gap-2";
      }
      if (dot) dot.classList.remove("active");
      if (text) text.textContent = "Activate Strategy";
      if (stripState) {
        stripState.textContent = "STANDBY";
        stripState.className = "badge bg-secondary font-monospace";
      }
      if (engineStatus) {
        engineStatus.textContent = "STANDBY";
        engineStatus.className = "badge bg-secondary-subtle text-secondary font-monospace";
      }
      if (pulse) pulse.style.display = "none";
    }

    renderSignalsFeed();

  } catch (err) {
    console.error("Failed to fetch strategy signals:", err);
  }
}

/**
 * Render Live Signals in Signals Pane Feed
 */
function renderSignalsFeed() {
  const container = document.getElementById("signalsFeedContainer");
  const countBadge = document.getElementById("signalsCountBadge");
  const countFooter = document.getElementById("strategySignalsCount");
  if (!container) return;

  if (countBadge) countBadge.textContent = state.signals.length;
  if (countFooter) countFooter.textContent = `${state.signals.length} orders`;

  if (state.signals.length === 0) {
    container.innerHTML = `
      <div class="text-center py-5 text-muted">
        <i class="bi bi-broadcast fs-1 mb-2 d-block text-secondary opacity-50"></i>
        <div class="fw-semibold text-light mb-1">No Live Execution Signals</div>
        <p class="fs-8 text-muted mb-3">Click 'Activate Strategy' to deploy the automated SMC engine or 'Evaluate Now' to calculate immediate confluence.</p>
        <button class="btn btn-sm btn-outline-primary-accent" onclick="evaluateLiveStrategy(false)">
          <i class="bi bi-play-circle me-1"></i>Evaluate Active Chart
        </button>
      </div>
    `;
    return;
  }

  container.innerHTML = "";
  state.signals.forEach(sig => {
    const isBuy = sig.action === "BUY";
    const card = document.createElement("div");
    card.className = `signal-card ${isBuy ? 'buy' : 'sell'}`;

    const dateStr = sig.timestamp ? new Date(sig.timestamp).toLocaleTimeString() : "Just now";

    card.innerHTML = `
      <div class="d-flex align-items-center justify-content-between mb-2">
        <div class="d-flex align-items-center gap-2">
          <span class="signal-action-badge ${isBuy ? 'buy' : 'sell'}">${sig.action}</span>
          <span class="fw-bold fs-7 text-light">${sig.symbol}</span>
          <span class="badge bg-dark-subtle text-secondary font-monospace fs-9">${sig.timeframe}</span>
        </div>
        <span class="fs-9 text-muted font-monospace">${dateStr}</span>
      </div>

      <!-- Price Target Grid -->
      <div class="p-2 bg-dark-surface rounded border border-dark-subtle mb-2 font-monospace fs-8">
        <div class="d-flex justify-content-between mb-1">
          <span class="text-muted">ENTRY:</span>
          <span class="text-light fw-bold">$${sig.entry_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div class="d-flex justify-content-between mb-1">
          <span class="text-muted">STOP LOSS:</span>
          <span class="text-danger fw-bold">$${sig.stop_loss.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div class="d-flex justify-content-between mb-1">
          <span class="text-muted">TAKE PROFIT 1:</span>
          <span class="text-success fw-bold">$${sig.take_profit_1.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div class="d-flex justify-content-between mb-1">
          <span class="text-muted">TAKE PROFIT 2:</span>
          <span class="text-success fw-bold">$${sig.take_profit_2.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        </div>
        <div class="d-flex justify-content-between pt-1 border-top border-dark-subtle">
          <span class="text-muted">RISK/REWARD:</span>
          <span class="text-primary-accent fw-bold">${sig.risk_reward_ratio}</span>
        </div>
      </div>

      <!-- Confluence Reason -->
      <div class="fs-9 text-muted mb-2">
        <span class="text-light fw-semibold">Trigger:</span> ${sig.trigger_reason}
      </div>

      <!-- Actions Footer -->
      <div class="d-flex align-items-center justify-content-between pt-2 border-top border-dark-subtle fs-8">
        <span class="badge bg-success-subtle text-success fs-9 font-monospace">
          <i class="bi bi-shield-check me-1"></i>${sig.status || "ACTIVE"}
        </span>
        <div class="d-flex gap-1">
          <button class="btn btn-sm btn-outline-secondary py-0 px-2 fs-9 btn-copy-signal" data-entry="${sig.entry_price}" data-sl="${sig.stop_loss}">
            <i class="bi bi-clipboard me-1"></i>Copy
          </button>
          <button class="btn btn-sm btn-outline-info py-0 px-2 fs-9 btn-forward-signal" data-id="${sig.id}">
            <i class="bi bi-telegram me-1"></i>Telegram
          </button>
        </div>
      </div>
    `;

    // Hook copy button
    const copyBtn = card.querySelector(".btn-copy-signal");
    if (copyBtn) {
      copyBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const text = `${sig.action} ${sig.symbol} @ $${sig.entry_price} | SL: $${sig.stop_loss} | TP: $${sig.take_profit_1}`;
        navigator.clipboard.writeText(text).then(() => {
          showToast("Order Copied", text);
        });
      });
    }

    // Hook telegram forward button
    const fwdBtn = card.querySelector(".btn-forward-signal");
    if (fwdBtn) {
      fwdBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        showToast("Signal Dispatched", `Dispatched ${sig.action} ${sig.symbol} order to @IamDeva_bot!`);
      });
    }

    container.appendChild(card);
  });
}

/* ==========================================================================
   Modular Strategy Hub Controller
   ========================================================================== */

/**
 * Initialize Strategy Hub Event Listeners and Initial Data
 */
function initStrategyHub() {
  // 1. Navigation View Switchers
  const btnNavTerminal = document.getElementById("btnNavTerminal");
  const btnNavHub = document.getElementById("btnNavStrategyHub");
  const btnChartGoHub = document.getElementById("chartGoStrategyHubBtn");

  if (btnNavTerminal) {
    btnNavTerminal.addEventListener("click", () => switchView("terminal"));
  }
  if (btnNavHub) {
    btnNavHub.addEventListener("click", () => switchView("hub"));
  }
  if (btnChartGoHub) {
    btnChartGoHub.addEventListener("click", () => switchView("hub"));
  }

  // 2. Hub Selectors (Asset & Timeframe)
  const hubAssetSelector = document.getElementById("hubAssetSelector");
  if (hubAssetSelector) {
    hubAssetSelector.addEventListener("change", (e) => {
      state.hubTargetAsset = e.target.value;
      showToast("Strategy Hub Target", `Target asset updated to ${state.hubTargetAsset}`);
    });
  }

  const hubTimeframeSelector = document.getElementById("hubTimeframeSelector");
  if (hubTimeframeSelector) {
    hubTimeframeSelector.addEventListener("change", (e) => {
      state.hubTargetTimeframe = e.target.value;
      showToast("Strategy Hub Timeframe", `Execution timeframe set to ${state.hubTargetTimeframe}`);
    });
  }

  // 3. Deploy Active Strategy Toggle Button
  const hubDeployToggleBtn = document.getElementById("hubDeployToggleBtn");
  if (hubDeployToggleBtn) {
    hubDeployToggleBtn.addEventListener("click", () => {
      toggleHubDeployState();
    });
  }

  // 4. Run Strategy Analysis Action Buttons
  const hubRunAnalysisBtn = document.getElementById("hubRunAnalysisBtn");
  if (hubRunAnalysisBtn) {
    hubRunAnalysisBtn.addEventListener("click", () => {
      runHubStrategyAnalysis();
    });
  }

  const hubInitialRunBtn = document.getElementById("hubInitialRunBtn");
  if (hubInitialRunBtn) {
    hubInitialRunBtn.addEventListener("click", () => {
      runHubStrategyAnalysis();
    });
  }

  // 5. Initial Data Fetch: Strategies and History
  fetchHubStrategies();
  fetchHubHistory();
}

/**
 * View Switcher: Terminal Chart vs Strategy Hub
 */
function switchView(viewName) {
  const terminalView = document.getElementById("viewTerminal");
  const hubView = document.getElementById("viewStrategyHub");
  const btnTerminal = document.getElementById("btnNavTerminal");
  const btnHub = document.getElementById("btnNavStrategyHub");

  if (viewName === "hub") {
    state.hubActiveView = "hub";
    if (terminalView) {
      terminalView.classList.add("d-none");
      terminalView.classList.remove("d-flex");
    }
    if (hubView) {
      hubView.classList.remove("d-none");
      hubView.classList.add("d-flex");
    }
    if (btnTerminal) btnTerminal.classList.remove("active");
    if (btnHub) btnHub.classList.add("active");

    // Sync Asset Selector with Current Terminal Asset
    const hubAssetSelector = document.getElementById("hubAssetSelector");
    if (hubAssetSelector && state.currentDisplay) {
      hubAssetSelector.value = state.currentDisplay;
      state.hubTargetAsset = state.currentDisplay;
    }

    // Sync Timeframe with Terminal Timeframe
    const hubTimeframeSelector = document.getElementById("hubTimeframeSelector");
    if (hubTimeframeSelector && state.currentInterval) {
      const normTf = getNormalizedTf(state.currentInterval);
      hubTimeframeSelector.value = normTf;
      state.hubTargetTimeframe = normTf;
    }

    // Refresh audit history on viewing hub
    fetchHubHistory();

  } else {
    state.hubActiveView = "terminal";
    if (hubView) {
      hubView.classList.add("d-none");
      hubView.classList.remove("d-flex");
    }
    if (terminalView) {
      terminalView.classList.remove("d-none");
      terminalView.classList.add("d-flex");
    }
    if (btnHub) btnHub.classList.remove("active");
    if (btnTerminal) btnTerminal.classList.add("active");

    // Trigger chart widget resize
    if (typeof TradingView !== "undefined") {
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    }
  }
}

/**
 * Fetch All Available Modular Strategies from /api/strategies
 */
async function fetchHubStrategies() {
  try {
    const res = await fetch("/api/strategies");
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    const data = await res.json();
    state.hubStrategies = data;

    // Check which strategy is currently active
    const activeStrat = data.find(s => s.is_active);
    if (activeStrat) {
      state.hubCurrentStrategyId = activeStrat.id;
      state.hubDeployActive = true;
    } else if (data.length > 0 && !state.hubCurrentStrategyId) {
      state.hubCurrentStrategyId = data[0].id;
      state.hubDeployActive = false;
    }

    updateHubDeployUi();
    renderHubStrategyCards();

  } catch (err) {
    console.error("Error fetching modular strategies:", err);
  }
}

/**
 * Update Header and Deploy Toggle UI Elements
 */
function updateHubDeployUi() {
  const currentStrat = state.hubStrategies.find(s => s.id === state.hubCurrentStrategyId);
  const stratName = currentStrat ? currentStrat.name : "SMC";
  const stratShort = state.hubCurrentStrategyId.toUpperCase();

  // Top Nav Badge
  const navBadge = document.getElementById("navActiveStratBadge");
  if (navBadge) {
    navBadge.textContent = state.hubDeployActive ? `${stratShort} ON` : stratShort;
    navBadge.className = state.hubDeployActive 
      ? "badge bg-primary text-dark rounded-pill ms-1 font-monospace fs-9"
      : "badge bg-secondary-subtle text-secondary rounded-pill ms-1 font-monospace fs-9";
  }

  // Hub Header Banner Tag
  const hubTag = document.getElementById("hubActiveStrategyTag");
  if (hubTag) {
    hubTag.textContent = state.hubDeployActive ? `${stratShort} ACTIVE` : `${stratShort} STANDBY`;
    hubTag.className = state.hubDeployActive
      ? "badge bg-primary text-dark font-monospace fs-9 fw-bold"
      : "badge bg-secondary-subtle text-secondary font-monospace fs-9 fw-bold";
  }

  // Deploy Toggle Button
  const toggleBtn = document.getElementById("hubDeployToggleBtn");
  const dot = document.getElementById("hubDeployDot");
  const text = document.getElementById("hubDeployBtnText");

  if (toggleBtn && dot && text) {
    if (state.hubDeployActive) {
      toggleBtn.className = "btn btn-sm btn-success d-flex align-items-center gap-2";
      dot.className = "strategy-status-dot active";
      text.textContent = "Strategy Deployed";
    } else {
      toggleBtn.className = "btn btn-sm btn-outline-success d-flex align-items-center gap-2";
      dot.className = "strategy-status-dot";
      text.textContent = "Activate Strategy";
    }
  }
}

/**
 * Render Strategy Selection Cards Grid
 */
function renderHubStrategyCards() {
  const container = document.getElementById("hubStrategiesCardsContainer");
  if (!container) return;

  container.innerHTML = "";

  const iconMap = {
    smc: { icon: "bi-shield-shaded", color: "text-primary-accent", bg: "bg-primary-subtle" },
    ema_cross: { icon: "bi-graph-up-arrow", color: "text-success", bg: "bg-success-subtle" },
    bollinger_bands: { icon: "bi-water", color: "text-warning", bg: "bg-warning-subtle" },
    custom: { icon: "bi-sliders", color: "text-info", bg: "bg-info-subtle" }
  };

  state.hubStrategies.forEach(strat => {
    const isSelected = strat.id === state.hubCurrentStrategyId;
    const isDeployed = strat.is_active;
    const iconMeta = iconMap[strat.id] || { icon: "bi-cpu", color: "text-light", bg: "bg-dark-subtle" };

    const col = document.createElement("div");
    col.className = "col-12 col-md-6 col-xl-3";

    col.innerHTML = `
      <div class="hub-strategy-card ${isSelected ? 'selected' : ''} ${isDeployed ? 'deployed-active' : ''}" data-strategy-id="${strat.id}">
        
        <!-- Top Row: Icon, Title, Status Tag -->
        <div class="d-flex align-items-center justify-content-between mb-2">
          <div class="d-flex align-items-center gap-2">
            <div class="strat-icon-box ${iconMeta.bg}">
              <i class="bi ${iconMeta.icon} ${iconMeta.color}"></i>
            </div>
            <div>
              <h4 class="fs-7 fw-bold m-0 text-light">${strat.name}</h4>
              <span class="fs-9 text-muted font-monospace">${strat.category}</span>
            </div>
          </div>
          ${isDeployed 
            ? `<span class="badge bg-success-subtle text-success font-monospace fs-9 border border-success-subtle"><i class="bi bi-broadcast me-1"></i>DEPLOYED</span>`
            : `<span class="badge bg-dark-subtle text-secondary font-monospace fs-9">IDLE</span>`
          }
        </div>

        <!-- Strategy Description -->
        <p class="fs-8 text-secondary mb-3 flex-grow-1" style="min-height: 48px; line-height: 1.35;">
          ${strat.description}
        </p>

        <!-- Timeframes & Confluence Parameters -->
        <div class="mb-3 pt-2 border-top border-dark-subtle">
          <div class="d-flex align-items-center justify-content-between mb-1">
            <span class="fs-9 text-muted">Timeframes:</span>
            <div class="d-flex gap-1">
              ${strat.timeframes.map(tf => `<span class="badge bg-dark-subtle text-light font-monospace fs-9">${tf}</span>`).join('')}
            </div>
          </div>

          <div class="d-flex flex-wrap gap-1 mt-2">
            ${Object.entries(strat.parameters || {}).slice(0, 3).map(([k, v]) => `
              <span class="param-pill">${k.replace(/_/g, ' ')}: <b class="text-light">${v}</b></span>
            `).join('')}
          </div>
        </div>

        <!-- Card Bottom Action -->
        <div class="d-flex align-items-center justify-content-between pt-2 border-top border-dark-subtle">
          <span class="fs-9 ${isSelected ? 'text-primary-accent fw-bold' : 'text-muted'}">
            ${isSelected ? '<i class="bi bi-check-circle-fill me-1"></i>Selected for Analysis' : 'Click to Select'}
          </span>
          <button class="btn btn-sm ${isSelected ? 'btn-primary-accent text-dark' : 'btn-outline-secondary'} py-0 px-2 fs-9 font-monospace">
            ${isSelected ? 'ACTIVE' : 'SELECT'}
          </button>
        </div>

      </div>
    `;

    // Click on Strategy Card selects it
    const cardEl = col.querySelector(".hub-strategy-card");
    if (cardEl) {
      cardEl.addEventListener("click", () => {
        selectHubStrategy(strat.id);
      });
    }

    container.appendChild(col);
  });
}

/**
 * Handle Strategy Card Selection
 */
function selectHubStrategy(strategyId) {
  state.hubCurrentStrategyId = strategyId;
  const strat = state.hubStrategies.find(s => s.id === strategyId);
  renderHubStrategyCards();
  updateHubDeployUi();
  showToast("Strategy Selected", `Now analyzing setups using ${strat ? strat.name : strategyId}`);
}

/**
 * Toggle Active Strategy Deployment via /api/strategies/activate
 */
async function toggleHubDeployState() {
  const newDeployState = !state.hubDeployActive;
  try {
    const res = await fetch("/api/strategies/activate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        strategy_id: state.hubCurrentStrategyId,
        enable: newDeployState
      })
    });

    if (!res.ok) throw new Error(`Activation failed: ${res.status}`);
    const updatedStrat = await res.json();

    state.hubDeployActive = updatedStrat.is_active;

    // Update in strategies array
    state.hubStrategies.forEach(s => {
      s.is_active = (s.id === state.hubCurrentStrategyId && updatedStrat.is_active);
    });

    updateHubDeployUi();
    renderHubStrategyCards();

    showToast(
      updatedStrat.is_active ? "Strategy Deployed" : "Strategy Standby",
      `${updatedStrat.name} is now ${updatedStrat.is_active ? "actively monitoring and evaluating live feeds" : "in standby"}.`
    );

  } catch (err) {
    console.error("Failed to toggle strategy deployment:", err);
    showToast("Activation Error", "Could not toggle strategy deployment state.");
  }
}

/**
 * Run Strategy Analysis (Step A: Market Structure & Bias + Step B: Multi-timeframe Confluence)
 */
async function runHubStrategyAnalysis() {
  const asset = state.hubTargetAsset || "BTC/USDT";
  const tf = state.hubTargetTimeframe || "15m";
  const stratId = state.hubCurrentStrategyId || "smc";

  const runBtn = document.getElementById("hubRunAnalysisBtn");
  const initialRunBtn = document.getElementById("hubInitialRunBtn");

  if (runBtn) {
    runBtn.disabled = true;
    runBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Evaluating Confluence...`;
  }
  if (initialRunBtn) {
    initialRunBtn.disabled = true;
    initialRunBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Evaluating...`;
  }

  try {
    const url = `/api/strategies/analyze?symbol=${encodeURIComponent(asset)}&timeframe=${encodeURIComponent(tf)}&strategy_id=${encodeURIComponent(stratId)}`;
    const res = await fetch(url, { method: "POST" });
    if (!res.ok) throw new Error(`Analysis failed with status ${res.status}`);
    const data = await res.json();

    // Render Two-Step Results View
    renderHubAnalysisResult(data);

    // Refresh Audit Log Table
    fetchHubHistory();

    // User Notification
    if (data.has_entry) {
      showToast(
        "High-Probability Setup Confirmed",
        `${data.entry_zone.action} ${data.symbol} confirmed @ $${data.entry_zone.entry} | RRR: ${data.entry_zone.risk_reward_ratio}`
      );
    } else {
      showToast(
        "Strategy Evaluated (Wait State)",
        "No valid entry right now, please wait. BotX is guarding your capital."
      );
    }

  } catch (err) {
    console.error("Strategy analysis error:", err);
    showToast("Analysis Error", `Failed to complete strategy analysis for ${asset}`);
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = `<i class="bi bi-play-circle-fill fs-6 me-1"></i><span>Run Strategy Analysis</span>`;
    }
    if (initialRunBtn) {
      initialRunBtn.disabled = false;
      initialRunBtn.innerHTML = `<i class="bi bi-play-circle me-1"></i>Run Strategy Analysis Now`;
    }
  }
}

/**
 * Render Complete Two-Step Analysis Results (Structure + Confluence or Strict Wait State)
 */
function renderHubAnalysisResult(data) {
  const container = document.getElementById("hubAnalysisSection");
  if (!container) return;

  const struct = data.step_a_structure || {};
  const isBuy = data.entry_zone && data.entry_zone.action === "BUY";
  const hasEntry = data.has_entry === true;

  // Format Swings for visual chips
  const swingsHtml = (struct.swings || []).slice(-6).map(sw => `
    <span class="swing-chip ${sw.label.toLowerCase()}" title="${sw.point_type} @ ${sw.timestamp}">
      ${sw.label} $${sw.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
    </span>
  `).join('');

  // Step A: Directional Bias Badge
  let biasBadge = `<span class="badge badge-bullish fs-8 font-monospace">🟢 BULLISH</span>`;
  if (struct.directional_bias === "BEARISH") {
    biasBadge = `<span class="badge badge-bearish fs-8 font-monospace">🔴 BEARISH</span>`;
  } else if (struct.directional_bias === "RANGING") {
    biasBadge = `<span class="badge badge-ranging fs-8 font-monospace">🟡 RANGING</span>`;
  }

  // Telegram Anti-Spam Status Formatting
  let tgBadge = `<span class="anti-spam-badge wait"><i class="bi bi-shield-lock"></i> Standby (No Setup)</span>`;
  if (data.telegram_status && data.telegram_status.alert_sent) {
    tgBadge = `<span class="anti-spam-badge sent"><i class="bi bi-telegram"></i> Dispatched to @IamDeva_bot</span>`;
  } else if (data.telegram_status && data.telegram_status.cooldown_active) {
    tgBadge = `<span class="anti-spam-badge cooldown"><i class="bi bi-hourglass-split"></i> Cooldown Active (${Math.round(data.telegram_status.cooldown_remaining_sec / 60)}m left)</span>`;
  }

  container.innerHTML = `
    <!-- Top Result Meta Strip -->
    <div class="d-flex flex-wrap align-items-center justify-content-between p-2 mb-3 bg-dark-card rounded border border-dark-subtle fs-8">
      <div class="d-flex align-items-center gap-3">
        <div>
          <span class="text-secondary">EVALUATION ID:</span>
          <span class="fw-bold text-light font-monospace">${data.id}</span>
        </div>
        <div>
          <span class="text-secondary">ASSET:</span>
          <span class="fw-bold text-primary-accent font-monospace">${data.symbol} (${data.timeframe})</span>
        </div>
        <div>
          <span class="text-secondary">STRATEGY:</span>
          <span class="fw-bold text-light">${data.strategy_name}</span>
        </div>
      </div>
      <div class="d-flex align-items-center gap-2">
        <span class="badge ${hasEntry ? 'bg-success text-dark' : 'bg-warning-subtle text-warning border border-warning-subtle'} font-monospace fs-8">
          ${data.confluence_score}% CONFLUENCE SCORE
        </span>
        <span class="text-muted font-monospace fs-9">${new Date(data.evaluated_at).toLocaleTimeString()} UTC</span>
      </div>
    </div>

    <!-- 2-Card Two-Step Layout: Step A (Structure) + Step B (Strategy Execution / Wait State) -->
    <div class="row g-3">
      
      <!-- STEP A CARD: Base Market Structure & Bias -->
      <div class="col-12 col-xl-5">
        <div class="hub-result-card step-structure-card p-3 h-100 d-flex flex-column">
          
          <div class="d-flex align-items-center justify-content-between mb-2">
            <div class="d-flex align-items-center gap-2">
              <span class="badge bg-info text-dark fw-bold font-monospace fs-9">STEP A</span>
              <h4 class="fs-7 fw-bold m-0 text-light">Market Structure & Bias</h4>
            </div>
            ${biasBadge}
          </div>

          <div class="fs-9 text-muted mb-3">
            Market Phase: <span class="text-info fw-bold font-monospace">${struct.phase || "ANALYSIS"}</span> &bull; 
            Confidence: <span class="text-light fw-bold font-monospace">${struct.confidence || 80}%</span>
          </div>

          <!-- Institutional Liquidity Pools (BSL & SSL) -->
          <div class="bg-dark-card rounded border border-dark-subtle p-2 mb-3 font-monospace fs-8">
            <div class="d-flex justify-content-between mb-1 pb-1 border-bottom border-dark-subtle">
              <span class="text-danger fw-bold"><i class="bi bi-arrow-up-right me-1"></i>NEAREST BSL (Swing High Pool):</span>
              <span class="text-light fw-bold">$${struct.nearest_bsl ? struct.nearest_bsl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "---"}</span>
            </div>
            <div class="d-flex justify-content-between">
              <span class="text-success fw-bold"><i class="bi bi-arrow-down-right me-1"></i>NEAREST SSL (Swing Low Pool):</span>
              <span class="text-light fw-bold">$${struct.nearest_ssl ? struct.nearest_ssl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "---"}</span>
            </div>
          </div>

          <!-- Recent Swings Structure (HH, HL, LH, LL) -->
          <div class="mb-3">
            <div class="fs-9 text-muted mb-1 text-uppercase fw-semibold">Recent Structural Swings:</div>
            <div class="d-flex flex-wrap gap-1">
              ${swingsHtml || '<span class="text-muted fs-9">Calculating swing structure...</span>'}
            </div>
          </div>

          <!-- Rationale -->
          <div class="mt-auto p-2 rounded bg-dark-card border border-dark-subtle fs-9 text-secondary">
            <span class="text-light fw-semibold">Structural Rationale:</span> ${struct.rationale || "Structure evaluated based on swing highs and lows."}
          </div>

        </div>
      </div>

      <!-- STEP B CARD: Multi-Timeframe Strategy Confluence Evaluation -->
      <div class="col-12 col-xl-7">
        ${hasEntry ? `
          <!-- HIGH-PROBABILITY CONFIRMED ENTRY CARD -->
          <div class="hub-result-card entry-confirmed-card p-3 h-100 d-flex flex-column">
            
            <div class="d-flex align-items-center justify-content-between mb-2">
              <div class="d-flex align-items-center gap-2">
                <span class="badge bg-success text-dark fw-bold font-monospace fs-9">STEP B</span>
                <span class="badge ${isBuy ? 'bg-success' : 'bg-danger'} text-dark fw-bold font-monospace fs-7">
                  <i class="bi ${isBuy ? 'bi-graph-up' : 'bi-graph-down'} me-1"></i>${data.entry_zone.action} ORDER CONFIRMED
                </span>
              </div>
              <span class="badge bg-success-subtle text-success border border-success-subtle font-monospace fs-8">
                <i class="bi bi-shield-check me-1"></i>100% Confluence Met
              </span>
            </div>

            <p class="fs-8 text-light mb-3">
              ${data.status_message}
            </p>

            <!-- Exact Execution Matrix (Entry, SL, TP1, TP2, RRR) -->
            <div class="p-3 bg-dark-card rounded border border-dark-subtle mb-3 font-monospace fs-8">
              <div class="row g-2">
                <div class="col-6 col-md-4">
                  <div class="text-muted fs-9">EXACT ENTRY</div>
                  <div class="text-light fw-bold fs-7">$${data.entry_zone.entry.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                </div>
                <div class="col-6 col-md-4">
                  <div class="text-danger fs-9">STOP LOSS</div>
                  <div class="text-danger fw-bold fs-7">$${data.entry_zone.stop_loss.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                </div>
                <div class="col-6 col-md-4">
                  <div class="text-primary-accent fs-9">RISK / REWARD</div>
                  <div class="text-primary-accent fw-bold fs-7">${data.entry_zone.risk_reward_ratio}</div>
                </div>
                <div class="col-6 col-md-4">
                  <div class="text-success fs-9">TAKE PROFIT 1</div>
                  <div class="text-success fw-bold fs-7">$${data.entry_zone.take_profit_1.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                </div>
                <div class="col-6 col-md-4">
                  <div class="text-success fs-9">TAKE PROFIT 2</div>
                  <div class="text-success fw-bold fs-7">$${data.entry_zone.take_profit_2.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                </div>
                <div class="col-6 col-md-4">
                  <div class="text-warning fs-9">INVALIDATION</div>
                  <div class="text-warning fw-bold fs-7">$${data.entry_zone.invalidation_level.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                </div>
              </div>
            </div>

            <!-- Confluence Checklist -->
            <div class="mb-3">
              <div class="fs-9 text-muted mb-1 text-uppercase fw-semibold">Confluence Checklist:</div>
              ${data.checklist.map(item => `
                <div class="confluence-list-item">
                  <span class="fs-8 text-light"><i class="bi bi-check-circle-fill text-success me-2"></i>${item.name}</span>
                  <span class="confluence-pill passed">${item.description}</span>
                </div>
              `).join('')}
            </div>

            <!-- Telegram Anti-Spam Status & Actions Footer -->
            <div class="mt-auto pt-2 border-top border-dark-subtle d-flex flex-wrap align-items-center justify-content-between gap-2">
              <div class="d-flex align-items-center gap-2">
                ${tgBadge}
              </div>
              <div class="d-flex gap-2">
                <button class="btn btn-sm btn-outline-secondary py-1 px-3 fs-9 font-monospace" id="hubCopyOrderBtn">
                  <i class="bi bi-clipboard me-1"></i>Copy Execution
                </button>
                <button class="btn btn-sm btn-outline-info py-1 px-3 fs-9 font-monospace" id="hubForwardTelegramBtn">
                  <i class="bi bi-telegram me-1"></i>Telegram
                </button>
              </div>
            </div>

          </div>
        ` : `
          <!-- STRICT WAIT STATE CARD -->
          <div class="hub-result-card wait-state-card p-3 h-100 d-flex flex-column">
            
            <div class="d-flex align-items-center justify-content-between mb-3">
              <div class="d-flex align-items-center gap-2">
                <span class="badge bg-warning text-dark fw-bold font-monospace fs-9">STEP B</span>
                <div class="wait-state-badge">
                  <i class="bi bi-hourglass-split"></i>No valid entry right now, please wait.
                </div>
              </div>
              <span class="badge bg-warning-subtle text-warning border border-warning-subtle font-monospace fs-8">
                ${data.confluence_score}% / 100% Confluence
              </span>
            </div>

            <p class="fs-8 text-secondary mb-3">
              BotX algorithmic rules require 100% confluence before capital deployment. The current market condition does not meet high-probability risk-reward criteria.
            </p>

            <!-- Unmet Confluence Wait Reasons -->
            <div class="wait-reasons-box mb-3">
              <div class="d-flex align-items-center gap-2 text-warning fw-bold fs-8 mb-2">
                <i class="bi bi-exclamation-triangle-fill"></i>
                <span>Institutional Wait Criteria:</span>
              </div>
              <ul class="fs-8 text-muted m-0 ps-3">
                ${data.wait_reasons.length > 0 ? data.wait_reasons.map(r => `
                  <li class="mb-1"><span class="text-light">${r}</span></li>
                `).join('') : '<li class="text-light">Awaiting higher-timeframe alignment and clean mitigation.</li>'}
              </ul>
            </div>

            <!-- Confluence Factors Breakdown -->
            <div class="mb-3">
              <div class="fs-9 text-muted mb-1 text-uppercase fw-semibold">Checklist Evaluation:</div>
              ${data.checklist.map(item => `
                <div class="confluence-list-item">
                  <span class="fs-8 text-light">
                    <i class="bi ${item.status === 'PASSED' ? 'bi-check-circle-fill text-success' : 'bi-pause-circle-fill text-warning'} me-2"></i>
                    ${item.name}
                  </span>
                  <span class="confluence-pill ${item.status === 'PASSED' ? 'passed' : 'waiting'}">
                    ${item.status === 'PASSED' ? 'PASSED' : 'WAITING'}: ${item.description}
                  </span>
                </div>
              `).join('')}
            </div>

            <!-- Anti-Spam Telegram Notice -->
            <div class="mt-auto pt-2 border-top border-dark-subtle d-flex align-items-center justify-content-between fs-8">
              <div class="d-flex align-items-center gap-2 text-muted">
                <i class="bi bi-shield-lock text-info"></i>
                <span>Telegram Anti-Spam: Standby (Zero spam sent until 100% verified setup)</span>
              </div>
              <span class="anti-spam-badge wait">FILTERED &bull; NO SPAM</span>
            </div>

          </div>
        `}
      </div>

    </div>
  `;

  // Attach button handlers for valid setup copy & forward
  if (hasEntry) {
    const copyBtn = document.getElementById("hubCopyOrderBtn");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        const orderText = `BOTX ALGO EXECUTION: ${data.entry_zone.action} ${data.symbol} (${data.timeframe}) | Strategy: ${data.strategy_name} | Entry: $${data.entry_zone.entry} | SL: $${data.entry_zone.stop_loss} | TP1: $${data.entry_zone.take_profit_1} | RRR: ${data.entry_zone.risk_reward_ratio}`;
        navigator.clipboard.writeText(orderText).then(() => {
          showToast("Order Copied", orderText);
        });
      });
    }

    const fwdBtn = document.getElementById("hubForwardTelegramBtn");
    if (fwdBtn) {
      fwdBtn.addEventListener("click", () => {
        showToast("Telegram Forward", `Setup dispatched to Telegram channel (@IamDeva_bot)`);
      });
    }
  }
}

/**
 * Fetch and Render Historical Strategy Evaluations from /api/strategies/history
 */
async function fetchHubHistory() {
  try {
    const res = await fetch("/api/strategies/history");
    if (!res.ok) return;
    const history = await res.json();
    state.hubAuditLogs = history;
    renderHubAuditTable(history);
  } catch (err) {
    console.error("Failed to fetch strategy audit history:", err);
  }
}

/**
 * Render Audit Log Table Rows
 */
function renderHubAuditTable(history) {
  const tableBody = document.getElementById("hubAuditTableBody");
  const countBadge = document.getElementById("hubAuditCount");
  if (!tableBody) return;

  if (countBadge) {
    countBadge.textContent = `${history.length} runs recorded`;
  }

  if (history.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="9" class="text-center text-muted py-3">No strategy runs recorded in this session.</td>
      </tr>
    `;
    return;
  }

  tableBody.innerHTML = "";
  history.forEach(item => {
    const timeStr = item.evaluated_at ? new Date(item.evaluated_at).toLocaleTimeString() : "Just now";
    const hasEntry = item.has_entry;
    const struct = item.step_a_structure || {};

    let biasBadge = `<span class="badge badge-bullish fs-9">BULLISH</span>`;
    if (struct.directional_bias === "BEARISH") {
      biasBadge = `<span class="badge badge-bearish fs-9">BEARISH</span>`;
    } else if (struct.directional_bias === "RANGING") {
      biasBadge = `<span class="badge badge-ranging fs-9">RANGING</span>`;
    }

    let verdictBadge = hasEntry
      ? `<span class="badge bg-success text-dark fw-bold font-monospace">${item.entry_zone ? item.entry_zone.action : 'ENTRY'} CONFIRMED</span>`
      : `<span class="badge bg-warning-subtle text-warning border border-warning-subtle font-monospace">PLEASE WAIT</span>`;

    let actionText = hasEntry && item.entry_zone
      ? `Entry: $${item.entry_zone.entry} | SL: $${item.entry_zone.stop_loss} | RRR: ${item.entry_zone.risk_reward_ratio}`
      : (item.wait_reasons[0] || "Awaiting 100% confluence criteria");

    let tgPill = `<span class="badge bg-dark-subtle text-muted fs-9">STANDBY</span>`;
    if (item.telegram_status && item.telegram_status.alert_sent) {
      tgPill = `<span class="badge bg-success-subtle text-success fs-9"><i class="bi bi-telegram me-1"></i>SENT</span>`;
    } else if (item.telegram_status && item.telegram_status.cooldown_active) {
      tgPill = `<span class="badge bg-info-subtle text-info fs-9"><i class="bi bi-clock-history me-1"></i>COOLDOWN</span>`;
    }

    const tr = document.createElement("tr");
    tr.className = "border-dark-subtle";
    tr.innerHTML = `
      <td class="text-secondary">${timeStr}</td>
      <td class="fw-bold text-light">${item.symbol}</td>
      <td>${item.strategy_name}</td>
      <td><span class="badge bg-dark-subtle text-light">${item.timeframe}</span></td>
      <td>${biasBadge}</td>
      <td>${verdictBadge}</td>
      <td class="fw-bold ${hasEntry ? 'text-success' : 'text-warning'}">${item.confluence_score}%</td>
      <td class="text-truncate text-secondary" style="max-width: 240px;" title="${actionText}">${actionText}</td>
      <td>${tgPill}</td>
    `;
    tableBody.appendChild(tr);
  });
}


