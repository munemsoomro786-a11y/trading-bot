let currentSymbol = "BTC/USDT";
let currentTimeframe = "15m";
let tvChart = null;
let candleSeries = null;
let emaFastSeries = null;
let emaSlowSeries = null;
let volumeSeries = null;

document.addEventListener("DOMContentLoaded", () => {
    initChart();
    fetchDashboardData();
    fetchChartData();

    // Poll status every 3 seconds
    setInterval(fetchDashboardData, 3000);
    setInterval(fetchChartData, 5000);
});

// Initialize TradingView Lightweight Chart
function initChart() {
    const container = document.getElementById("tvChartContainer");
    if (!container) return;

    tvChart = LightweightCharts.createChart(container, {
        layout: {
            background: { type: 'solid', color: '#0D1117' },
            textColor: '#9CA3AF',
            fontFamily: "'Inter', sans-serif"
        },
        grid: {
            vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
            horzLines: { color: 'rgba(255, 255, 255, 0.04)' }
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: 'rgba(255, 255, 255, 0.08)',
        },
        timeScale: {
            borderColor: 'rgba(255, 255, 255, 0.08)',
            timeVisible: true,
            secondsVisible: false,
        },
    });

    candleSeries = tvChart.addCandlestickSeries({
        upColor: '#10B981',
        downColor: '#EF4444',
        borderUpColor: '#10B981',
        borderDownColor: '#EF4444',
        wickUpColor: '#10B981',
        wickDownColor: '#EF4444',
    });

    emaFastSeries = tvChart.addLineSeries({
        color: '#06B6D4',
        lineWidth: 2,
        title: 'EMA 9'
    });

    emaSlowSeries = tvChart.addLineSeries({
        color: '#F59E0B',
        lineWidth: 2,
        title: 'EMA 21'
    });
}

// Fetch Chart Data
async function fetchChartData() {
    try {
        const resp = await fetch(`/api/chart?symbol=${encodeURIComponent(currentSymbol)}&timeframe=${currentTimeframe}&limit=120`);
        const data = await resp.json();
        if (data.candles && data.candles.length > 0) {
            const candleData = data.candles.map(c => ({
                time: c.time,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close
            }));

            const emaFastData = data.candles
                .filter(c => c.ema_fast !== null)
                .map(c => ({ time: c.time, value: c.ema_fast }));

            const emaSlowData = data.candles
                .filter(c => c.ema_slow !== null)
                .map(c => ({ time: c.time, value: c.ema_slow }));

            candleSeries.setData(candleData);
            emaFastSeries.setData(emaFastData);
            emaSlowSeries.setData(emaSlowData);

            const lastPrice = data.candles[data.candles.length - 1].close;
            document.getElementById("livePriceVal").innerText = `$${lastPrice.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

            // Update Signal Banner
            if (data.analysis) {
                updateSignalBanner(data.analysis);
            }
        }
    } catch (e) {
        console.error("Error fetching chart data:", e);
    }
}

// Update Signal Banner
function updateSignalBanner(analysis) {
    const badge = document.getElementById("signalBadge");
    const reason = document.getElementById("signalReason");
    const targets = document.getElementById("signalTargets");
    const chipRsi = document.getElementById("chipRsi");
    const chipFast = document.getElementById("chipEmaFast");
    const chipSlow = document.getElementById("chipEmaSlow");

    const sig = analysis.signal || "HOLD";
    badge.className = `signal-badge ${sig.toLowerCase()}`;
    
    if (sig === "BUY") {
        badge.innerHTML = `<i class="fa-solid fa-circle-up"></i> AI SIGNAL: BULLISH LONG`;
    } else if (sig === "SELL") {
        badge.innerHTML = `<i class="fa-solid fa-circle-down"></i> AI SIGNAL: BEARISH SHORT`;
    } else {
        badge.innerHTML = `<i class="fa-solid fa-compass"></i> AI SIGNAL: HOLD / MONITOR`;
    }

    reason.innerText = analysis.reason || "Scanning candle confluences...";
    
    if (sig !== "HOLD" && analysis.stop_loss) {
        targets.innerText = `🎯 SL Target: $${analysis.stop_loss} | TP Target: $${analysis.take_profit}`;
    } else {
        targets.innerText = "";
    }

    chipRsi.innerText = analysis.rsi || "--";
    chipFast.innerText = analysis.ema_fast || "--";
    chipSlow.innerText = analysis.ema_slow || "--";
}

// Fetch Status & Dashboard Data
async function fetchDashboardData() {
    try {
        const resp = await fetch('/api/status');
        const data = await resp.json();

        // Status Badge
        const statusText = document.getElementById("statusText");
        const statusBadge = document.getElementById("statusBadge");
        if (data.is_running) {
            statusText.innerText = "BOT LIVE";
            statusBadge.className = "status-badge";
        } else {
            statusText.innerText = "BOT PAUSED";
            statusBadge.className = "status-badge paused";
        }

        // Stats Cards
        const stats = data.stats;
        document.getElementById("equityVal").innerText = `$${stats.equity.toLocaleString(undefined, {minimumFractionDigits: 2})}`;
        document.getElementById("initialBalanceVal").innerText = `${stats.initial_balance.toLocaleString()}`;
        document.getElementById("netPnlVal").innerText = `$${stats.net_pnl >= 0 ? '+' : ''}${stats.net_pnl.toFixed(2)}`;
        
        const netPnlValEl = document.getElementById("netPnlVal");
        netPnlValEl.className = stats.net_pnl >= 0 ? "metric-value pnl-positive" : "metric-value pnl-negative";

        document.getElementById("unrealizedPnlVal").innerText = `${stats.unrealized_pnl >= 0 ? '+' : ''}${stats.unrealized_pnl.toFixed(2)}`;
        
        const pnlBadge = document.getElementById("pnlBadge");
        pnlBadge.innerText = `${stats.pnl_pct >= 0 ? '+' : ''}${stats.pnl_pct.toFixed(2)}%`;
        pnlBadge.style.background = stats.pnl_pct >= 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)';
        pnlBadge.style.color = stats.pnl_pct >= 0 ? '#10B981' : '#EF4444';

        document.getElementById("winRateVal").innerText = `${stats.win_rate}%`;
        document.getElementById("winCountVal").innerText = stats.winning_trades;
        document.getElementById("lossCountVal").innerText = stats.losing_trades;

        document.getElementById("profitFactorVal").innerText = stats.profit_factor;
        document.getElementById("totalTradesVal").innerText = stats.total_trades;
        document.getElementById("activePositionsVal").innerText = `${stats.open_positions_count} / ${data.config.max_open_positions || 3}`;

        // Fetch Positions, History, and Logs
        fetchPositions();
        fetchHistory();
        fetchLogs();

    } catch (e) {
        console.error("Error fetching status:", e);
    }
}

// Fetch Active Positions Table
async function fetchPositions() {
    try {
        const resp = await fetch('/api/positions');
        const data = await resp.json();
        const positions = data.positions || [];

        document.getElementById("tabPositionsCount").innerText = positions.length;
        const tbody = document.getElementById("positionsTableBody");

        if (positions.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" class="empty-msg">No active open positions right now. Bot is scanning for entry signals.</td></tr>`;
            return;
        }

        tbody.innerHTML = positions.map(p => `
            <tr class="clickable-row" title="Click to view ${p.symbol} live chart" onclick="selectSymbol('${p.symbol}')">
                <td><span class="clickable-symbol"><i class="fa-solid fa-chart-line"></i> ${p.symbol}</span></td>
                <td><span class="${p.side === 'BUY' ? 'badge-long' : 'badge-short'}">${p.side === 'BUY' ? 'LONG' : 'SHORT'}</span></td>
                <td>$${p.entry_price}</td>
                <td>$${p.current_price}</td>
                <td style="color: var(--red); font-weight:600;">$${p.stop_loss}</td>
                <td style="color: var(--green); font-weight:600;">$${p.take_profit}</td>
                <td>$${p.position_value}</td>
                <td class="${p.unrealized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">$${p.unrealized_pnl >= 0 ? '+' : ''}${p.unrealized_pnl}</td>
                <td class="${p.unrealized_pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}">${p.unrealized_pnl_pct >= 0 ? '+' : ''}${p.unrealized_pnl_pct}%</td>
                <td onclick="event.stopPropagation();">
                    <button class="btn btn-outline" style="padding: 4px 8px; font-size: 11px;" onclick="closePositionManually('${p.id}')"><i class="fa-solid fa-xmark"></i> Close</button>
                </td>
            </tr>
        `).join('');

    } catch (e) {
        console.error("Error fetching positions:", e);
    }
}

// Fetch Trade History Table
async function fetchHistory() {
    try {
        const resp = await fetch('/api/trades');
        const data = await resp.json();
        const trades = data.trades || [];

        document.getElementById("tabHistoryCount").innerText = trades.length;
        const tbody = document.getElementById("historyTableBody");

        if (trades.length === 0) {
            tbody.innerHTML = `<tr><td colspan="10" class="empty-msg">No completed trade history yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = trades.map(t => `
            <tr class="clickable-row" title="Click to view ${t.symbol} live chart" onclick="selectSymbol('${t.symbol}')">
                <td><span class="clickable-symbol"><i class="fa-solid fa-chart-line"></i> ${t.symbol}</span></td>
                <td><span class="${t.side === 'BUY' ? 'badge-long' : 'badge-short'}">${t.side === 'BUY' ? 'LONG' : 'SHORT'}</span></td>
                <td>${t.opened_at}</td>
                <td>${t.closed_at}</td>
                <td>$${t.entry_price}</td>
                <td>$${t.exit_price}</td>
                <td><span style="font-size:11px; opacity:0.8;">${t.close_reason}</span></td>
                <td class="${t.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">$${t.pnl >= 0 ? '+' : ''}${t.pnl}</td>
                <td class="${t.pnl_pct >= 0 ? 'pnl-positive' : 'pnl-negative'}">${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct}%</td>
                <td>
                    <span class="${t.is_win ? 'badge-long' : 'badge-short'}">${t.is_win ? 'WIN' : 'LOSS'}</span>
                </td>
            </tr>
        `).join('');

    } catch (e) {
        console.error("Error fetching trades:", e);
    }
}

// Fetch Execution Logs
async function fetchLogs() {
    try {
        const resp = await fetch('/api/logs');
        const data = await resp.json();
        const logs = data.logs || [];

        const container = document.getElementById("logsContainer");
        if (logs.length > 0) {
            container.innerHTML = logs.map(l => `
                <div class="log-entry ${l.level}">
                    <span class="log-time">[${l.timestamp}]</span> ${l.message}
                </div>
            `).join('');
        }
    } catch (e) {
        console.error("Error fetching logs:", e);
    }
}

// Select/Switch Active Chart Symbol
function selectSymbol(symbol) {
    if (!symbol) return;
    currentSymbol = symbol;
    
    const select = document.getElementById("symbolSelect");
    if (select) select.value = symbol;
    
    document.getElementById("chartSymbol").innerText = symbol;

    // Toggle active state on quick coin pills
    document.querySelectorAll(".quick-coin-pill").forEach(pill => pill.classList.remove("active"));
    const baseCoin = symbol.split('/')[0];
    const targetPill = document.getElementById(`pill-${baseCoin}`);
    if (targetPill) targetPill.classList.add("active");

    fetchChartData();
}

// Change Active Chart Symbol via dropdown
function changeSymbol() {
    currentSymbol = document.getElementById("symbolSelect").value;
    document.getElementById("chartSymbol").innerText = currentSymbol;
    fetchChartData();
}

// Change Timeframe
function changeTimeframe(tf) {
    currentTimeframe = tf;
    document.querySelectorAll(".tf-btn").forEach(btn => btn.classList.remove("active"));
    event.target.classList.add("active");
    fetchChartData();
}

// Switch Tabs
function switchTab(tab) {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    
    if (tab === 'positions') {
        document.querySelectorAll(".tab-btn")[0].classList.add("active");
        document.getElementById("tabPositions").classList.add("active");
    } else {
        document.querySelectorAll(".tab-btn")[1].classList.add("active");
        document.getElementById("tabHistory").classList.add("active");
    }
}

// Bot Control Actions
async function startBot() {
    await fetch('/api/bot/start', { method: 'POST' });
    fetchDashboardData();
}

async function pauseBot() {
    await fetch('/api/bot/pause', { method: 'POST' });
    fetchDashboardData();
}

async function resetAccount() {
    if (confirm("Reset Paper Account balance to $50.00 and clear trade history?")) {
        await fetch('/api/bot/reset', { method: 'POST' });
        fetchDashboardData();
    }
}

async function closePositionManually(posId) {
    if (confirm("Manually close this open position at market price?")) {
        await fetch('/api/position/close', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ position_id: posId })
        });
        fetchDashboardData();
    }
}

// Backtest Modal Controls
function openBacktestModal() {
    document.getElementById("backtestModal").classList.add("active");
}

function closeBacktestModal() {
    document.getElementById("backtestModal").classList.remove("active");
}

async function executeBacktest() {
    const symbol = document.getElementById("btSymbol").value;
    const timeframe = document.getElementById("btTimeframe").value;

    const resultsEl = document.getElementById("btResults");
    resultsEl.style.display = "block";
    resultsEl.querySelector("h4").innerText = "Running historical backtest simulation...";

    try {
        const resp = await fetch('/api/backtest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol, timeframe, limit: 500 })
        });

        const data = await resp.json();
        if (data.error) {
            alert(data.error);
            return;
        }

        resultsEl.querySelector("h4").innerText = `Backtest Results for ${symbol} (${timeframe})`;
        document.getElementById("btWinRate").innerText = `${data.win_rate}%`;
        document.getElementById("btNetProfit").innerText = `$${data.net_profit} (${data.net_profit_pct}%)`;
        document.getElementById("btProfitFactor").innerText = data.profit_factor;
        document.getElementById("btTotalTrades").innerText = `${data.total_trades} (${data.winning_trades} W / ${data.losing_trades} L)`;

    } catch (e) {
        console.error("Backtest error:", e);
    }
}
