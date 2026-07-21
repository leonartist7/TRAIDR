(function () {
  "use strict";

  const COLORS = {
    bg: "#080b10", panel: "#0a0f16", grid: "#17202b", text: "#d8dee9",
    muted: "#8b98aa", up: "#00c084", down: "#ff4d4f", accent: "#22d3ee"
  };

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[char]
    ));
  }

  function insufficient(container, reason) {
    container.innerHTML = "<div style='height:660px;background:#080b10;color:#d8dee9;" +
      "border:1px solid #252b36;border-radius:10px;display:flex;align-items:center;" +
      "justify-content:center;font:14px Inter,system-ui,sans-serif'><div style='text-align:center;" +
      "max-width:580px;padding:28px'><h2>INSUFFICIENT_DATA</h2><p style='color:#99a3b3'>" +
      escapeHtml(reason || "Missing, stale, or unsafe public market data.") +
      "</p><p style='color:#7f8a9b'>can_execute_trades: false</p></div></div>";
  }

  function intervalSeconds(interval) {
    return ({ "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400 })[interval] || 0;
  }

  window.renderTRAIDRBitunixChart = function renderTRAIDRBitunixChart(containerId, payload) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!payload || payload.can_execute_trades !== false || !Array.isArray(payload.candles) || !payload.candles.length) {
      insufficient(container, payload && (payload.reason || (payload.reason_codes || []).join(", ")));
      return;
    }

    container.innerHTML = "";
    container.style.cssText = "height:680px;background:#080b10;border:1px solid #252b36;" +
      "border-radius:10px;overflow:hidden;position:relative;color:#d8dee9;font:12px Inter,system-ui,sans-serif";

    const header = document.createElement("div");
    header.style.cssText = "height:39px;border-bottom:1px solid #252b36;display:flex;align-items:center;" +
      "justify-content:space-between;padding:0 12px;background:#0b1119";
    const mode = payload.data_mode || "unknown";
    header.innerHTML = "<div><strong>" + escapeHtml(payload.symbol || "TRAIDR") + "</strong> · " +
      escapeHtml(payload.interval || "") + " · <span style='color:" + (mode === "preview" ? "#f59e0b" : "#22d3ee") + "'>" +
      escapeHtml(mode) + "</span></div><div style='color:#8b98aa'>Wheel: zoom · Drag: pan · Crosshair: inspect</div>";

    const canvas = document.createElement("canvas");
    canvas.style.cssText = "display:block;width:100%;height:640px;cursor:crosshair;touch-action:none";
    const tooltip = document.createElement("div");
    tooltip.style.cssText = "position:absolute;display:none;pointer-events:none;background:rgba(8,11,16,.94);" +
      "border:1px solid #334155;border-radius:6px;padding:7px 9px;z-index:4;white-space:nowrap;color:#d8dee9";
    container.appendChild(header);
    container.appendChild(canvas);
    container.appendChild(tooltip);

    const candles = payload.candles.slice().sort((a, b) => Number(a.time) - Number(b.time));
    const state = {
      start: Math.max(0, candles.length - 120), end: candles.length,
      pointerX: null, pointerY: null, dragging: false, dragX: 0, dragStart: 0
    };
    const ctx = canvas.getContext("2d");

    function resize() {
      const ratio = Math.max(1, window.devicePixelRatio || 1);
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.round(rect.width * ratio);
      canvas.height = Math.round(rect.height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      draw();
    }

    function draw() {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const pad = { left: 16, right: 76, top: 16, bottom: 28 };
      const volumeHeight = 105;
      const priceBottom = height - pad.bottom - volumeHeight;
      const plotWidth = width - pad.left - pad.right;
      const visible = candles.slice(state.start, state.end);
      if (!visible.length) return;

      const extraPrices = [];
      (payload.support_resistance || []).forEach((x) => extraPrices.push(Number(x.price)));
      (payload.risk_reward_boxes || []).forEach((x) => extraPrices.push(Number(x.entry), Number(x.stop), Number(x.target)));
      (payload.paper_positions || []).forEach((x) => extraPrices.push(Number(x.entry), Number(x.stop), Number(x.liquidation)));
      (payload.paper_fills || []).forEach((x) => extraPrices.push(Number(x.price)));
      const lows = visible.map((x) => Number(x.low));
      const highs = visible.map((x) => Number(x.high));
      let minPrice = Math.min.apply(null, lows.concat(extraPrices));
      let maxPrice = Math.max.apply(null, highs.concat(extraPrices));
      const margin = Math.max((maxPrice - minPrice) * 0.08, maxPrice * 0.001);
      minPrice -= margin;
      maxPrice += margin;
      const priceSpan = Math.max(maxPrice - minPrice, 1e-12);
      const slot = plotWidth / visible.length;
      const bodyWidth = Math.max(2, Math.min(12, slot * 0.62));
      const maxVolume = Math.max.apply(null, visible.map((x) => Number(x.volume || 0)).concat([1]));
      const xAt = (localIndex) => pad.left + slot * (localIndex + 0.5);
      const yAt = (price) => pad.top + (maxPrice - Number(price)) / priceSpan * (priceBottom - pad.top);
      const localForTime = (time) => {
        const target = Number(time);
        let best = 0;
        let distance = Infinity;
        visible.forEach((candle, index) => {
          const next = Math.abs(Number(candle.time) - target);
          if (next < distance) { best = index; distance = next; }
        });
        return best;
      };

      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = COLORS.bg;
      ctx.fillRect(0, 0, width, height);
      ctx.fillStyle = COLORS.panel;
      ctx.fillRect(pad.left, pad.top, plotWidth, priceBottom - pad.top);

      ctx.strokeStyle = COLORS.grid;
      ctx.fillStyle = COLORS.muted;
      ctx.font = "11px Inter,system-ui,sans-serif";
      ctx.textAlign = "left";
      for (let i = 0; i <= 6; i += 1) {
        const y = pad.top + (priceBottom - pad.top) * i / 6;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
        const price = maxPrice - priceSpan * i / 6;
        ctx.fillText(price.toLocaleString(undefined, { maximumFractionDigits: 6 }), width - pad.right + 7, y + 4);
      }

      function band(x1, x2, y1, y2, fill, stroke) {
        ctx.fillStyle = fill; ctx.strokeStyle = stroke;
        ctx.fillRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
        ctx.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1));
      }

      (payload.fvg_zones || []).forEach((zone) => {
        const x1 = xAt(localForTime(zone.start_time));
        const x2 = xAt(localForTime(zone.end_time));
        band(x1, x2, yAt(zone.high), yAt(zone.low), "rgba(250,204,21,.10)", "rgba(250,204,21,.58)");
      });
      (payload.risk_reward_boxes || []).forEach((box) => {
        const x1 = xAt(localForTime(box.start_time));
        const x2 = xAt(localForTime(box.end_time));
        band(x1, x2, yAt(box.target), yAt(box.entry), "rgba(16,185,129,.12)", "rgba(16,185,129,.65)");
        band(x1, x2, yAt(box.entry), yAt(box.stop), "rgba(239,68,68,.11)", "rgba(239,68,68,.65)");
      });
      (payload.paper_positions || []).forEach((position) => {
        const levels = [
          [position.entry, "#f8fafc", `${position.direction} paper entry`],
          [position.stop, "#fb7185", "paper stop"],
          [position.liquidation, "#f97316", "paper liquidation estimate"],
        ];
        levels.forEach(([price, color, label]) => {
          const y = yAt(price);
          ctx.save(); ctx.setLineDash([8, 5]); ctx.strokeStyle = color;
          ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
          ctx.fillStyle = color; ctx.fillText(label, pad.left + 7, y - 5); ctx.restore();
        });
      });

      const expected = intervalSeconds(payload.interval);
      visible.forEach((candle, index) => {
        const x = xAt(index);
        const open = yAt(candle.open), close = yAt(candle.close), high = yAt(candle.high), low = yAt(candle.low);
        const up = Number(candle.close) >= Number(candle.open);
        ctx.strokeStyle = up ? COLORS.up : COLORS.down;
        ctx.fillStyle = ctx.strokeStyle;
        ctx.beginPath(); ctx.moveTo(x, high); ctx.lineTo(x, low); ctx.stroke();
        ctx.fillRect(x - bodyWidth / 2, Math.min(open, close), bodyWidth, Math.max(2, Math.abs(close - open)));
        const volume = Number(candle.volume || 0);
        const volumeY = height - pad.bottom - (volume / maxVolume) * (volumeHeight - 12);
        ctx.globalAlpha = 0.45;
        ctx.fillRect(x - bodyWidth / 2, volumeY, bodyWidth, height - pad.bottom - volumeY);
        ctx.globalAlpha = 1;
        if (expected && index > 0 && Number(candle.time) - Number(visible[index - 1].time) > expected * 1.8) {
          ctx.save(); ctx.setLineDash([4, 4]); ctx.strokeStyle = "#f59e0b";
          ctx.beginPath(); ctx.moveTo(x - slot / 2, pad.top); ctx.lineTo(x - slot / 2, height - pad.bottom); ctx.stroke();
          ctx.restore();
        }
      });

      (payload.paper_fills || []).forEach((fill) => {
        const localIndex = localForTime(fill.time);
        const x = xAt(localIndex), y = yAt(fill.price);
        const longFill = fill.direction === "LONG";
        ctx.fillStyle = longFill ? COLORS.up : COLORS.down;
        ctx.beginPath();
        if (longFill) {
          ctx.moveTo(x, y - 9); ctx.lineTo(x - 7, y + 5); ctx.lineTo(x + 7, y + 5);
        } else {
          ctx.moveTo(x, y + 9); ctx.lineTo(x - 7, y - 5); ctx.lineTo(x + 7, y - 5);
        }
        ctx.closePath(); ctx.fill();
      });

      (payload.support_resistance || []).forEach((level) => {
        const y = yAt(level.price);
        ctx.save(); ctx.setLineDash([6, 5]); ctx.strokeStyle = level.color || "#38bdf8";
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(width - pad.right, y); ctx.stroke();
        ctx.fillStyle = ctx.strokeStyle; ctx.fillText(level.label || "S/R", pad.left + 5, y - 5); ctx.restore();
      });
      (payload.overlays || []).forEach((line) => {
        ctx.strokeStyle = line.color || COLORS.accent; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(xAt(localForTime(line.start_time)), yAt(line.start_price));
        ctx.lineTo(xAt(localForTime(line.end_time)), yAt(line.end_price)); ctx.stroke(); ctx.lineWidth = 1;
      });

      if (mode === "preview") {
        ctx.save(); ctx.translate(width / 2, height / 2); ctx.rotate(-0.22);
        ctx.fillStyle = "rgba(245,158,11,.16)"; ctx.font = "bold 64px Inter,system-ui,sans-serif";
        ctx.textAlign = "center"; ctx.fillText("PREVIEW · SYNTHETIC", 0, 0); ctx.restore();
      }

      if (state.pointerX !== null && state.pointerX >= pad.left && state.pointerX <= width - pad.right) {
        const index = Math.max(0, Math.min(visible.length - 1, Math.floor((state.pointerX - pad.left) / slot)));
        const candle = visible[index];
        const x = xAt(index);
        ctx.save(); ctx.setLineDash([3, 3]); ctx.strokeStyle = "rgba(226,232,240,.55)";
        ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, height - pad.bottom); ctx.stroke();
        if (state.pointerY !== null) { ctx.beginPath(); ctx.moveTo(pad.left, state.pointerY); ctx.lineTo(width - pad.right, state.pointerY); ctx.stroke(); }
        ctx.restore();
        tooltip.style.display = "block";
        tooltip.style.left = Math.min(width - 220, Math.max(8, x + 10)) + "px";
        tooltip.style.top = Math.max(48, Math.min(height - 80, state.pointerY || 60)) + "px";
        tooltip.innerHTML = new Date(Number(candle.time) * 1000).toISOString() + "<br>" +
          "O " + escapeHtml(candle.open) + " H " + escapeHtml(candle.high) + "<br>" +
          "L " + escapeHtml(candle.low) + " C " + escapeHtml(candle.close) + " V " + escapeHtml(candle.volume || 0);
      } else {
        tooltip.style.display = "none";
      }
    }

    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      const count = state.end - state.start;
      const target = Math.max(20, Math.min(candles.length, Math.round(count * (event.deltaY > 0 ? 1.18 : 0.84))));
      const ratio = Math.max(0, Math.min(1, event.offsetX / Math.max(canvas.clientWidth, 1)));
      const anchor = state.start + Math.round(count * ratio);
      state.start = Math.max(0, Math.min(candles.length - target, anchor - Math.round(target * ratio)));
      state.end = state.start + target;
      draw();
    }, { passive: false });
    canvas.addEventListener("pointerdown", (event) => {
      state.dragging = true; state.dragX = event.clientX; state.dragStart = state.start;
      canvas.setPointerCapture(event.pointerId); canvas.style.cursor = "grabbing";
    });
    canvas.addEventListener("pointerup", (event) => {
      state.dragging = false; canvas.releasePointerCapture(event.pointerId); canvas.style.cursor = "crosshair";
    });
    canvas.addEventListener("pointermove", (event) => {
      const rect = canvas.getBoundingClientRect(); state.pointerX = event.clientX - rect.left; state.pointerY = event.clientY - rect.top;
      if (state.dragging) {
        const visible = state.end - state.start;
        const shift = Math.round((state.dragX - event.clientX) / Math.max(rect.width / visible, 1));
        state.start = Math.max(0, Math.min(candles.length - visible, state.dragStart + shift)); state.end = state.start + visible;
      }
      draw();
    });
    canvas.addEventListener("pointerleave", () => { if (!state.dragging) { state.pointerX = null; state.pointerY = null; draw(); } });
    new ResizeObserver(resize).observe(container);
    resize();
  };
})();
