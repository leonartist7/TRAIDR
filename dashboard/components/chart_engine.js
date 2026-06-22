(function () {
  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function insufficient(container, reason) {
    clear(container);
    container.style.cssText = "height:620px;background:#080b10;color:#d8dee9;border:1px solid #252b36;border-radius:8px;display:flex;align-items:center;justify-content:center;font-family:Inter,system-ui,sans-serif;";
    const panel = document.createElement("div");
    panel.style.cssText = "text-align:center;max-width:560px;padding:24px;";
    panel.innerHTML = "<h2 style='margin:0 0 8px;font-size:24px;'>INSUFFICIENT_DATA</h2><p style='margin:0;color:#99a3b3;'>"
      + escapeHtml(reason || "Missing or unsafe Bitunix market data.")
      + "</p><p style='margin:14px 0 0;color:#7f8a9b;'>can_execute_trades: false</p>";
    container.appendChild(panel);
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (char) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[char];
    });
  }

  function drawLine(svg, x1, y1, x2, y2, color, width, dash) {
    if ([x1, y1, x2, y2].some((v) => v === null || Number.isNaN(v))) return;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", x1);
    line.setAttribute("y1", y1);
    line.setAttribute("x2", x2);
    line.setAttribute("y2", y2);
    line.setAttribute("stroke", color || "#facc15");
    line.setAttribute("stroke-width", width || "2");
    if (dash) line.setAttribute("stroke-dasharray", dash);
    svg.appendChild(line);
  }

  function drawRect(svg, x, y, width, height, fill, stroke) {
    if ([x, y, width, height].some((v) => v === null || Number.isNaN(v))) return;
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", Math.min(x, x + width));
    rect.setAttribute("y", Math.min(y, y + height));
    rect.setAttribute("width", Math.abs(width));
    rect.setAttribute("height", Math.abs(height));
    rect.setAttribute("fill", fill || "rgba(250, 204, 21, 0.12)");
    rect.setAttribute("stroke", stroke || "rgba(250, 204, 21, 0.65)");
    rect.setAttribute("stroke-width", "1");
    svg.appendChild(rect);
  }

  function drawLabel(svg, x, y, text, color) {
    if (x === null || y === null || Number.isNaN(x) || Number.isNaN(y)) return;
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", x + 6);
    label.setAttribute("y", y - 6);
    label.setAttribute("fill", color || "#d8dee9");
    label.setAttribute("font-size", "12");
    label.setAttribute("font-family", "Inter,system-ui,sans-serif");
    label.textContent = text || "";
    svg.appendChild(label);
  }

  function drawOverlay(svg, chart, series, payload) {
    clear(svg);
    const timeScale = chart.timeScale();
    const width = svg.clientWidth;

    (payload.support_resistance || []).forEach((level) => {
      const y = series.priceToCoordinate(level.price);
      drawLine(svg, 0, y, width, y, level.color || "#38bdf8", 1, "4 5");
      drawLabel(svg, 6, y, level.label || "S/R", level.color || "#38bdf8");
    });

    (payload.fvg_zones || []).forEach((zone) => {
      const x1 = timeScale.timeToCoordinate(zone.start_time);
      const x2 = timeScale.timeToCoordinate(zone.end_time);
      const yHigh = series.priceToCoordinate(zone.high);
      const yLow = series.priceToCoordinate(zone.low);
      drawRect(svg, x1, yHigh, x2 - x1, yLow - yHigh, "rgba(250, 204, 21, 0.13)", "rgba(250, 204, 21, 0.58)");
      drawLabel(svg, x1, yHigh, zone.label || "FVG", "#facc15");
    });

    (payload.overlays || []).forEach((line) => {
      const x1 = timeScale.timeToCoordinate(line.start_time);
      const x2 = timeScale.timeToCoordinate(line.end_time);
      const y1 = series.priceToCoordinate(line.start_price);
      const y2 = series.priceToCoordinate(line.end_price);
      drawLine(svg, x1, y1, x2, y2, line.color || "#22d3ee", 2, line.dash || null);
      drawLabel(svg, x2, y2, line.label || line.kind || "line", line.color || "#22d3ee");
    });

    (payload.risk_reward_boxes || []).forEach((box) => {
      const x1 = timeScale.timeToCoordinate(box.start_time);
      const x2 = timeScale.timeToCoordinate(box.end_time);
      const entryY = series.priceToCoordinate(box.entry);
      const targetY = series.priceToCoordinate(box.target);
      const stopY = series.priceToCoordinate(box.stop);
      drawRect(svg, x1, targetY, x2 - x1, entryY - targetY, "rgba(16, 185, 129, 0.12)", "rgba(16, 185, 129, 0.68)");
      drawRect(svg, x1, entryY, x2 - x1, stopY - entryY, "rgba(239, 68, 68, 0.11)", "rgba(239, 68, 68, 0.68)");
      drawLine(svg, x1, entryY, x2, entryY, "#e5e7eb", 1, "3 4");
      drawLabel(svg, x1, entryY, box.label || "Research RR", "#e5e7eb");
    });
  }

  window.renderTRAIDRBitunixChart = function renderTRAIDRBitunixChart(containerId, payload) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!payload || payload.can_execute_trades !== false || !Array.isArray(payload.candles) || payload.candles.length === 0) {
      insufficient(container, payload && payload.reason ? payload.reason : "No chartable candles were provided.");
      return;
    }
    if (!window.LightweightCharts) {
      insufficient(container, "Lightweight Charts failed to load.");
      return;
    }

    clear(container);
    container.style.cssText = "position:relative;height:620px;background:#080b10;border:1px solid #252b36;border-radius:8px;overflow:hidden;";
    const chartHost = document.createElement("div");
    chartHost.style.cssText = "position:absolute;inset:0;";
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:5;";
    container.appendChild(chartHost);
    container.appendChild(svg);

    const chart = LightweightCharts.createChart(chartHost, {
      layout: { background: { color: "#080b10" }, textColor: "#d8dee9" },
      grid: { vertLines: { color: "#161b22" }, horzLines: { color: "#161b22" } },
      rightPriceScale: { borderColor: "#2d3441" },
      timeScale: { borderColor: "#2d3441", timeVisible: true, secondsVisible: false },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#00c084",
      downColor: "#ff4d4f",
      borderUpColor: "#00c084",
      borderDownColor: "#ff4d4f",
      wickUpColor: "#00c084",
      wickDownColor: "#ff4d4f",
    });
    series.setData(payload.candles);
    chart.timeScale().fitContent();

    const redraw = function () { drawOverlay(svg, chart, series, payload); };
    setTimeout(redraw, 60);
    chart.timeScale().subscribeVisibleTimeRangeChange(redraw);
    new ResizeObserver(function () {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
      redraw();
    }).observe(container);
  };
})();
