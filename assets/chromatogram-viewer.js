function smoothChromatogramSignal(values) {
  const weights = [1, 2, 3, 2, 1];
  const radius = Math.floor(weights.length / 2);

  return values.map((_value, index) => {
    let weightedTotal = 0;
    let appliedWeight = 0;
    for (let offset = -radius; offset <= radius; offset++) {
      const sourceIndex = index + offset;
      if (sourceIndex < 0 || sourceIndex >= values.length) continue;
      const weight = weights[offset + radius];
      weightedTotal += (Number(values[sourceIndex]) || 0) * weight;
      appliedWeight += weight;
    }
    return appliedWeight ? weightedTotal / appliedWeight : 0;
  });
}

window.GeneGlassChromatogram = {
  render: function (trace, options = {}) {
    const section = document.getElementById("chromatogramSection");
    const canvas = document.getElementById("chromatogramCanvas");
    const detail = document.getElementById("chromatogramDetail");

    if (!section || !canvas || !detail) {
      throw new Error("Chromatogram viewer elements are missing.");
    }

    const n = trace.sequence?.length || 0;
    const positions = trace.base_positions || [];
    const channels = trace.channels || {};
    const quality = trace.quality_scores || [];

    if (
      !n ||
      positions.length < n ||
      ["A", "C", "G", "T"].some((base) => !channels[base]?.length)
    ) {
      throw new Error("Chromatogram data is incomplete.");
    }

    section.hidden = false;
    section.classList.add("gg-viewer-v2");
    const ctx = canvas.getContext("2d");
    const colors = {
      A: "#249e69",
      C: "#2588d1",
      G: "#333333",
      T: "#d84c4c"
    };
    const smoothedChannels = Object.fromEntries(
      ["A", "C", "G", "T"].map((base) => [
        base,
        smoothChromatogramSignal(channels[base])
      ])
    );

    let count = Math.min(30, n);
    const requestedTarget = Number(options.targetBase);
    let selected = Number.isInteger(requestedTarget) &&
      requestedTarget >= 1 && requestedTarget <= n
      ? requestedTarget - 1
      : null;
    let first = selected === null
      ? 0
      : Math.max(0, selected - Math.floor(count / 2));
    let labels = [];
    let drag = null;

    section.replaceChildren();
    const title = document.createElement("h2");
    title.textContent = "Chromatogram Viewer";

    const toolbar = document.createElement("div");
    toolbar.className = "gg-viewer-toolbar";
    toolbar.innerHTML = `
      <label class="gg-search-label">
        Go to AB1 base
        <span class="gg-search-row">
          <input class="gg-go-base" type="number" min="1" max="${n}" placeholder="e.g. 184">
          <button class="gg-go-button" type="button">Go</button>
        </span>
      </label>
      <label class="gg-signal-label">
        Signal View
        <select class="gg-signal-mode">
          <option value="original">Original signal</option>
          <option value="smoothed">Smoothed preview + original</option>
        </select>
      </label>
      <span class="gg-mouse-hint">Drag to move · Mouse wheel to zoom</span>
    `;

    const chartWrapper = document.createElement("div");
    chartWrapper.className = "gg-chart-with-scale";

    const scaleControl = document.createElement("div");
    scaleControl.className = "gg-scale-control";
    scaleControl.innerHTML = `
      <label>Vertical Scale</label>
      <input class="gg-vertical-scale" type="range" min="25" max="300" value="100" step="5">
      <span class="gg-vertical-value">100%</span>
    `;

    chartWrapper.append(canvas, scaleControl);

    const legend = document.createElement("div");
    legend.className = "gg-trace-legend";
    legend.innerHTML = `
      <span class="gg-a">● A</span>
      <span class="gg-c">● C</span>
      <span class="gg-g">● G</span>
      <span class="gg-t">● T</span>
    `;

    const overview = document.createElement("div");
    overview.className = "gg-overview";
    overview.innerHTML = `
      <span>Horizontal Scale</span>
      <input type="range" class="gg-overview-range" min="5" max="${Math.min(100, n)}" value="${count}">
      <span class="gg-total-bases"></span>
    `;

    const selectedInfo = document.createElement("div");
    selectedInfo.className = "gg-selected-base";

    section.append(title, toolbar, legend, chartWrapper, overview, selectedInfo, detail);

    const goInput = toolbar.querySelector(".gg-go-base");
    const signalMode = toolbar.querySelector(".gg-signal-mode");
    const verticalSlider = scaleControl.querySelector(".gg-vertical-scale");
    const verticalValue = scaleControl.querySelector(".gg-vertical-value");
    const horizontalSlider = overview.querySelector(".gg-overview-range");
    const horizontalValue = overview.querySelector(".gg-total-bases");

    function clampFirst(value) {
      return Math.max(0, Math.min(n - count, Math.round(value)));
    }

    function draw() {
      first = clampFirst(first);
      const last = first + count - 1;
      const left = Math.max(0, positions[first] - 15);
      const right = Math.min(channels.A.length - 1, positions[last] + 15);
      if (right <= left) return;

      const w = canvas.width;
      const h = canvas.height;
      const pad = 24;
      const top = 16;
      const bottom = h - 58;

      const x = sample =>
        pad + ((sample - left) / (right - left)) * (w - 2 * pad);

      let peak = 1;
      for (const base of ["A", "C", "G", "T"]) {
        for (let sample = left; sample <= right; sample++) {
          peak = Math.max(peak, channels[base][sample] || 0);
        }
      }

      const verticalScale = Number(verticalSlider.value) / 100;
      const y = signal =>
        bottom - ((signal || 0) / peak) * (bottom - top) * verticalScale;

      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, w, h);
      labels = [];

      for (let i = first; i <= last; i++) {
        const px = x(positions[i]);
        if (selected === i) {
          ctx.fillStyle = "rgba(0, 132, 139, .10)";
          ctx.fillRect(px - 8, top, 16, bottom - top + 22);
          ctx.strokeStyle = "#00848b";
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(px, top);
          ctx.lineTo(px, bottom);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        labels.push({ x: px, index: i });
      }

      function drawTrace(values, base, opacity, lineWidth) {
        ctx.beginPath();
        ctx.strokeStyle = colors[base];
        ctx.globalAlpha = opacity;
        ctx.lineWidth = lineWidth;

        for (let sample = left; sample <= right; sample++) {
          if (sample === left) {
            ctx.moveTo(x(sample), y(values[sample]));
          } else {
            ctx.lineTo(x(sample), y(values[sample]));
          }
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      for (const base of ["A", "C", "G", "T"]) {
        if (signalMode.value === "smoothed") {
          drawTrace(channels[base], base, 0.22, 0.8);
          drawTrace(smoothedChannels[base], base, 1, 1.5);
        } else {
          drawTrace(channels[base], base, 1, 1.35);
        }
      }

      // Keep all original signal peaks. Only thin text labels when there is
      // insufficient horizontal space, so letters/numbers never collide.
      const selectedX = selected !== null && selected >= first && selected <= last
        ? x(positions[selected]) : null;
      const baseFont = "bold 12px Arial";
      const numberFont = "10px Arial";
      ctx.textAlign = "center";
      const labelCandidates = labels.map(({ x: px, index }) => {
        const base = trace.sequence[index].toUpperCase();
        ctx.font = baseFont;
        const baseWidth = ctx.measureText(base).width;
        ctx.font = numberFont;
        const numberWidth = ctx.measureText(String(index + 1)).width;
        return { x: px, index, base, halfWidth: Math.max(baseWidth, numberWidth) / 2 + 5 };
      });

      let lastRight = -Infinity;
      for (const label of labelCandidates) {
        if (label.index === selected) continue;
        if (selectedX !== null &&
            Math.abs(label.x - selectedX) < label.halfWidth + 15) continue;
        if (label.x - label.halfWidth < lastRight) continue;
        if (label.x + label.halfWidth > w - 4) continue;
        ctx.font = baseFont;
        ctx.fillStyle = colors[label.base] || "#666";
        ctx.fillText(label.base, label.x, h - 35);
        ctx.font = numberFont;
        ctx.fillStyle = "#71858a";
        ctx.fillText(String(label.index + 1), label.x, h - 18);
        lastRight = label.x + label.halfWidth;
      }
      // The selected base remains visible even when zoomed far out.
      if (selectedX !== null) {
        ctx.font = baseFont;
        ctx.fillStyle = colors[trace.sequence[selected].toUpperCase()] || "#666";
        ctx.fillText(trace.sequence[selected], selectedX, h - 35);
        ctx.font = numberFont;
        ctx.fillStyle = "#00848b";
        ctx.fillText(String(selected + 1), selectedX, h - 18);
      }

      const signalDescription = signalMode.value === "smoothed"
        ? "Smoothed preview is displayed over a faint original trace. QC and target analysis still use the original signal."
        : "Original AB1 signal is displayed.";
      detail.textContent =
        `Showing AB1 bases ${first + 1}–${last + 1} of ${n}. ${signalDescription} Drag the trace or click a base to inspect it.`;

      horizontalSlider.value = String(count);
      horizontalValue.textContent = `${count} bases`;

      if (selected === null) {
        selectedInfo.textContent = "Click a base to view its quality and position.";
      } else {
        const q = quality[selected];
        selectedInfo.textContent =
          `${selected + 1 === requestedTarget ? "Target" : "Selected"} base ${selected + 1}: ${trace.sequence[selected]} · Phred Q${q ?? "N/A"} · Sample ${positions[selected]}`;
      }
    }

    function zoom(nextCount, anchor = first + (count - 1) / 2) {
      count = Math.max(Math.min(5, n), Math.min(Math.min(100, n), Math.round(nextCount)));
      first = clampFirst(anchor - Math.floor(count / 2));
      draw();
    }

    toolbar.querySelector(".gg-go-button").onclick = () => {
      const base = Number(goInput.value);
      if (!Number.isInteger(base) || base < 1 || base > n) {
        goInput.setCustomValidity(`Enter an AB1 base from 1 to ${n}`);
        goInput.reportValidity();
        return;
      }
      goInput.setCustomValidity("");
      selected = base - 1;
      first = clampFirst(selected - Math.floor(count / 2));
      draw();
    };

    goInput.onkeydown = event => {
      if (event.key === "Enter") {
        event.preventDefault();
        toolbar.querySelector(".gg-go-button").click();
      }
    };

    goInput.oninput = () => goInput.setCustomValidity("");

    signalMode.onchange = draw;

    horizontalSlider.oninput = () => {
      const anchor = selected ?? first + (count - 1) / 2;
      zoom(Number(horizontalSlider.value), anchor);
    };

    verticalSlider.oninput = () => {
      verticalValue.textContent = `${verticalSlider.value}%`;
      draw();
    };

    canvas.style.cursor = "grab";
    canvas.style.touchAction = "none";

    canvas.onpointerdown = event => {
      if (event.button !== 0) return;
      drag = { x: event.clientX, first, moved: false };
      canvas.setPointerCapture(event.pointerId);
      canvas.style.cursor = "grabbing";
    };

    canvas.onpointermove = event => {
      if (!drag) return;
      const dx = event.clientX - drag.x;
      if (Math.abs(dx) > 4) drag.moved = true;
      if (!drag.moved) return;

      const rect = canvas.getBoundingClientRect();
      const pixelsPerBase = Math.max(28, Math.min(65, rect.width / Math.max(1, count)));
      first = clampFirst(drag.first - dx / pixelsPerBase);
      selected = null;
      draw();
    };

    canvas.onpointerup = event => {
      if (!drag) return;
      const moved = drag.moved;
      drag = null;
      canvas.style.cursor = "grab";

      if (!moved && labels.length) {
        const rect = canvas.getBoundingClientRect();
        const px = ((event.clientX - rect.left) * canvas.width) / rect.width;
        selected = labels.reduce((a, b) =>
          Math.abs(a.x - px) < Math.abs(b.x - px) ? a : b
        ).index;
        draw();
      }
    };

    canvas.onpointercancel = () => {
      drag = null;
      canvas.style.cursor = "grab";
    };

    canvas.onwheel = event => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      selected = null;
      zoom(count + (event.deltaY > 0 ? 5 : -5), first + ratio * (count - 1));
    };

    draw();
  }
};
