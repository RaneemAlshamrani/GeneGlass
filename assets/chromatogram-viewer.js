
window.GeneGlassChromatogram = {
  render: function (trace) {
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

    let first = 0;
    let count = Math.min(30, n);
    let selected = null;
    let labels = [];
    let drag = null;

    section.replaceChildren();

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
      <div class="gg-zoom-controls">
        <span>Zoom</span>
        <button class="gg-zoom-out" type="button">−</button>
        <button class="gg-zoom-in" type="button">+</button>
      </div>
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
      <span class="gg-low">▧ Low quality (Q &lt; 20)</span>
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

    section.append(toolbar, legend, chartWrapper, overview, selectedInfo, detail);

    const goInput = toolbar.querySelector(".gg-go-base");
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

        if ((quality[i] ?? 0) < 20) {
          const l = i === 0 ? positions[i] - 7 : (positions[i - 1] + positions[i]) / 2;
          const r = i === n - 1 ? positions[i] + 7 : (positions[i] + positions[i + 1]) / 2;
          const a = x(Math.max(left, l));
          const b = x(Math.min(right, r));

          if (b > a) {
            ctx.fillStyle = "rgba(235, 176, 46, .16)";
            ctx.fillRect(a, top, b - a, bottom - top);
          }
        }

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

        ctx.fillStyle = colors[trace.sequence[i].toUpperCase()] || "#666";
        ctx.font = "bold 12px Arial";
        ctx.textAlign = "center";
        ctx.fillText(trace.sequence[i], px, h - 35);
        ctx.fillStyle = "#71858a";
        ctx.font = "10px Arial";
        ctx.fillText(String(i + 1), px, h - 18);
        labels.push({ x: px, index: i });
      }

      for (const base of ["A", "C", "G", "T"]) {
        ctx.beginPath();
        ctx.strokeStyle = colors[base];
        ctx.lineWidth = 1.35;

        for (let sample = left; sample <= right; sample++) {
          if (sample === left) {
            ctx.moveTo(x(sample), y(channels[base][sample]));
          } else {
            ctx.lineTo(x(sample), y(channels[base][sample]));
          }
        }
        ctx.stroke();
      }

      detail.textContent =
        `Showing AB1 bases ${first + 1}–${last + 1} of ${n}. Drag the trace or click a base to inspect it.`;

      horizontalSlider.value = String(count);
      horizontalValue.textContent = `${count} bases`;

      if (selected === null) {
        selectedInfo.textContent = "Click a base to view its quality and position.";
      } else {
        const q = quality[selected];
        selectedInfo.textContent =
          `Selected base ${selected + 1}: ${trace.sequence[selected]} · Phred Q${q ?? "N/A"} · Sample ${positions[selected]}`;
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

    toolbar.querySelector(".gg-zoom-in").onclick = () => zoom(count - 10);
    toolbar.querySelector(".gg-zoom-out").onclick = () => zoom(count + 10);

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
