(() => {
  const fileInput = document.getElementById("ab1");
  const fileInfo = document.getElementById("fileInfo");
  const analyzeButton = document.getElementById("analyze");
  const message = document.getElementById("message");

  function showQualityResults(data) {
    const qc = data.quality_control;

    message.replaceChildren();

    const heading = document.createElement("strong");
    heading.textContent = "Quality Control Results";
    message.appendChild(heading);

    const results = [
      ["Analysis ID", data.id],
      ["Sequence length", qc.sequence_length],
      ["Cleaned sequence length", qc.cleaned_sequence_length],
      ["Average quality", qc.average_quality],
      ["Minimum quality", qc.minimum_quality],
      ["Maximum quality", qc.maximum_quality],
      ["Low-quality bases", qc.low_quality_count],
      ["Low-quality percentage", `${qc.low_quality_percentage}%`],
      ["Retained percentage", `${qc.retained_percentage}%`],
      ["Quality assessment", qc.quality_assessment],
      ["QC status", data.qc_status],
      ["Variant detection", "Pending"],
    ];

    const grid = document.createElement("div");
    grid.className = "qc-results-grid";
    results.forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "qc-result-card";

      const cardLabel = document.createElement("span");
      cardLabel.className = "qc-result-label";
      cardLabel.textContent = label;

      const cardValue = document.createElement("strong");
      cardValue.className = "qc-result-value";
      cardValue.textContent = value ?? "N/A";

      card.append(cardLabel, cardValue);
      grid.appendChild(card);
    });

    message.appendChild(grid);
    const chromSection = document.getElementById("chromatogramSection");
    let qcPanel = document.getElementById("ggQualityPanel");
    if (!qcPanel) {
      qcPanel = document.createElement("section");
      qcPanel.id = "ggQualityPanel";
      qcPanel.className = "dashboard-card gg-quality-panel";
      chromSection.after(qcPanel);
    }
    qcPanel.appendChild(message);
  }

  // geneglass-viewer-v2: drag, wheel zoom, search and overview slider.
  function showChromatogram(trace) {
    const section = document.getElementById("chromatogramSection");
    const canvas = document.getElementById("chromatogramCanvas");
    const ctx = canvas.getContext("2d");
    const startInput = document.getElementById("chromStart");
    const countInput = document.getElementById("chromCount");
    const detail = document.getElementById("chromatogramDetail");
    const n = trace.sequence.length;
    const positions = trace.base_positions || [];
    const channels = trace.channels || {};
    const quality = trace.quality_scores || [];
    if (
      !n ||
      positions.length < n ||
      ["A", "C", "G", "T"].some((b) => !channels[b]?.length)
    ) {
      throw new Error("Chromatogram data is incomplete.");
    }
    section.hidden = false;
    section.classList.add("gg-viewer-v2");
    const colors = { A: "#249e69", C: "#2588d1", G: "#333333", T: "#d84c4c" };
    const visibleMin = Math.min(5, n);
    const visibleMax = Math.min(100, n);
    let count = Math.min(30, n);
    let first = 0;
    let selected = null;
    let labels = [];
    let drag = null;
    // Create navigation only once; the viewer is re-used for successive analyses.
    let toolbar = section.querySelector(".gg-viewer-toolbar");
    if (!toolbar) {
      toolbar = document.createElement("div");
      toolbar.className = "gg-viewer-toolbar";
      toolbar.innerHTML = `
        <label class="gg-search-label">Go to AB1 base
          <span class="gg-search-row"><input class="gg-go-base" type="number" min="1" placeholder="e.g. 184" aria-label="Go to AB1 base"><button class="gg-go-button" type="button">Go</button></span>
        </label>
        <div class="gg-zoom-controls"><span>Zoom</span><button type="button" class="gg-zoom-out" aria-label="Zoom out">−</button><button type="button" class="gg-zoom-in" aria-label="Zoom in">+</button></div>
        <span class="gg-mouse-hint">Drag to move · Mouse wheel to zoom</span>
      `;
      canvas.parentElement.before(toolbar);

      const verticalControl = document.createElement("div");
      verticalControl.className = "gg-scale-control";

      verticalControl.innerHTML = `
  <label for="ggVerticalScale">Vertical Scale</label>
  <input
    id="ggVerticalScale"
    type="range"
    min="25"
    max="300"
    value="100"
    step="5"
  >
  <span id="ggVerticalValue">100%</span>
`;

      const chartWrapper = document.createElement("div");
      chartWrapper.className = "gg-chart-with-scale";

      canvas.parentElement.insertBefore(chartWrapper, canvas);
      chartWrapper.appendChild(canvas);
      chartWrapper.appendChild(verticalControl);

      const legend = document.createElement("div");
      legend.className = "gg-trace-legend";
      legend.innerHTML =
        '<span class="gg-a">● A</span><span class="gg-c">● C</span><span class="gg-g">● G</span><span class="gg-t">● T</span><span class="gg-low">▧ Low quality (Q &lt; 20)</span>';
      toolbar.after(legend);
      const overview = document.createElement("div");
      overview.className = "gg-overview";
      overview.innerHTML =
        '<span>Horizontal Scale</span><input type="range" class="gg-overview-range" min="5" max="100" value="30" aria-label="Horizontal Scale"><span class="gg-total-bases"></span>';
      canvas.parentElement.after(overview);
      const info = document.createElement("div");
      info.className = "gg-selected-base";
      info.setAttribute("aria-live", "polite");
      overview.after(info);
    }
    // Hide the old Previous / Next and numeric controls without removing their markup.
    for (const id of ["chromPrevious", "chromNext"]) {
      const el = document.getElementById(id);
      if (el) el.hidden = true;
    }
    startInput.hidden = true;
    countInput.hidden = true;

    const goInput = toolbar.querySelector(".gg-go-base");
    const verticalSlider = document.getElementById("ggVerticalScale");
    const verticalValue = document.getElementById("ggVerticalValue");

    verticalSlider.oninput = () => {
      verticalValue.textContent = `${verticalSlider.value}%`;
      draw();
    };
    const overview = section.querySelector(".gg-overview-range");
    const horizontalLabel = section.querySelector(".gg-overview > span:first-child");
    const horizontalValue = section.querySelector(".gg-total-bases");

    overview.min = String(visibleMin);
    overview.max = String(visibleMax);
    overview.step = "1";
    overview.setAttribute("aria-label", "Horizontal Scale");

    if (horizontalLabel) {
      horizontalLabel.textContent = "Horizontal Scale";
    }
    const selectedInfo = section.querySelector(".gg-selected-base");
    goInput.max = String(n);

    function clampFirst(v) {
      return Math.max(0, Math.min(n - count, Math.round(v)));
    }
    function draw() {
      first = clampFirst(first);
      startInput.value = String(first + 1);
      countInput.value = String(count);
      const last = first + count - 1;
      const left = Math.max(0, positions[first] - 15);
      const right = Math.min(channels.A.length - 1, positions[last] + 15);
      if (right <= left) return;
      const w = canvas.width,
        h = canvas.height;
      const pad = 24,
        bottom = h - 58,
        top = 16;
      const x = (sample) =>
        pad + ((sample - left) / (right - left)) * (w - 2 * pad);
      let peak = 1;
      for (const base of ["A", "C", "G", "T"]) {
        for (let s = left; s <= right; s++)
          peak = Math.max(peak, channels[base][s] || 0);
      }
      const verticalScale =
        Number(document.getElementById("ggVerticalScale")?.value || 100) / 100;

      const y = (signal) =>
        bottom - ((signal || 0) / peak) * (bottom - top) * verticalScale;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, w, h);
      labels = [];
      for (let i = first; i <= last; i++) {
        const px = x(positions[i]);
        if ((quality[i] ?? 0) < 20) {
          const l =
            i === 0 ? positions[i] - 7 : (positions[i - 1] + positions[i]) / 2;
          const r =
            i === n - 1
              ? positions[i] + 7
              : (positions[i] + positions[i + 1]) / 2;
          const a = x(Math.max(left, l)),
            b = x(Math.min(right, r));
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
        for (let s = left; s <= right; s++) {
          if (s === left) ctx.moveTo(x(s), y(channels[base][s]));
          else ctx.lineTo(x(s), y(channels[base][s]));
        }
        ctx.stroke();
      }
      detail.textContent = `Showing AB1 bases ${first + 1}–${last + 1} of ${n}. Drag the trace or click a base to inspect it.`;
      overview.value = String(count);
      horizontalValue.textContent = `${count} bases`;
      if (selected === null) {
        selectedInfo.textContent =
          "Click a base to view its quality and position.";
      } else {
        const q = quality[selected];
        selectedInfo.textContent = `Selected base ${selected + 1}: ${trace.sequence[selected]} · Phred Q${q ?? "N/A"} · Sample ${positions[selected]} · ${q == null ? "Quality unavailable" : q < 20 ? "Low quality — review recommended" : "Quality at or above Q20"}`;
      }
    }
    function zoom(nextCount, anchor = first + (count - 1) / 2) {
      const newCount = Math.max(
        visibleMin,
        Math.min(visibleMax, Math.round(nextCount)),
      );

      count = newCount;

      // Keep the same base centered during zoom.
      first = clampFirst(anchor - Math.floor(count / 2));

      draw();
    }
    function goToBase() {
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
    }
    toolbar.querySelector(".gg-go-button").onclick = goToBase;
    goInput.onkeydown = (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        goToBase();
      }
    };
    goInput.oninput = () => goInput.setCustomValidity("");
    toolbar.querySelector(".gg-zoom-in").onclick = () => zoom(count - 10);
    toolbar.querySelector(".gg-zoom-out").onclick = () => zoom(count + 10);
    overview.oninput = () => {
      const newCount = Number(overview.value);

      // Keep the selected base in the center when zooming.
      const anchor =
        selected !== null && selected >= first && selected < first + count
          ? selected
          : first + (count - 1) / 2;

      zoom(newCount, anchor);
    };
    canvas.style.cursor = "grab";
    canvas.style.touchAction = "none";
    canvas.style.userSelect = "none";
    canvas.onpointerdown = (e) => {
      if (e.button !== 0) return;
      drag = { x: e.clientX, first, moved: false };
      canvas.setPointerCapture(e.pointerId);
      canvas.style.cursor = "grabbing";
    };
    canvas.onpointermove = (e) => {
      if (!drag) return;

      const dx = e.clientX - drag.x;

      if (Math.abs(dx) > 4) drag.moved = true;
      if (!drag.moved) return;

      const rect = canvas.getBoundingClientRect();
      // A fixed drag distance per base keeps mouse panning usable at high zoom.
      const pixelsPerBase = Math.max(28, Math.min(65, rect.width / Math.max(1, count)));
      const nextFirst = clampFirst(drag.first - dx / pixelsPerBase);
      if (nextFirst !== first) {
        first = nextFirst;
        selected = null; // Panning must not leave an off-screen zoom anchor.
        draw();
      }
    };
    canvas.onpointerup = (e) => {
      if (!drag) return;
      const moved = drag.moved;
      drag = null;
      canvas.style.cursor = "grab";
      if (!moved && labels.length) {
        const rect = canvas.getBoundingClientRect();
        const px = ((e.clientX - rect.left) * canvas.width) / rect.width;
        selected = labels.reduce((a, b) =>
          Math.abs(a.x - px) < Math.abs(b.x - px) ? a : b,
        ).index;
        draw();
      }
    };
    canvas.onpointercancel = () => {
      drag = null;
      canvas.style.cursor = "grab";
    };
    canvas.onwheel = (e) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.max(
        0,
        Math.min(1, (e.clientX - rect.left) / rect.width),
      );
      const anchor = first + ratio * (count - 1);
      selected = null;
      zoom(count + (e.deltaY > 0 ? 5 : -5), anchor);
    };
    selected = null;
    first = 0;
    draw();
  }

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];

    if (!file) {
      fileInfo.textContent = "No file selected";
      analyzeButton.disabled = true;
      message.textContent = "";
      return;
    }

    if (!/\.ab1$/i.test(file.name)) {
      fileInfo.textContent = "Please select a .ab1 file.";
      analyzeButton.disabled = true;
      message.textContent = "";
      fileInput.value = "";
      return;
    }

    fileInfo.textContent = `Selected: ${file.name}`;
    analyzeButton.disabled = false;
    message.textContent = "";
  });

  analyzeButton.addEventListener("click", async () => {
    const file = fileInput.files?.[0];

    if (!file) return;

    const token = window.GeneGlassAuth?.token;
    const apiBaseUrl = window.GeneGlassConfig?.apiBaseUrl;

    if (!token || !apiBaseUrl) {
      message.textContent =
        "Authentication or API configuration is unavailable. Please sign in again.";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    analyzeButton.disabled = true;
    message.textContent = "Uploading file and checking quality...";

    try {
      const response = await fetch(`${apiBaseUrl}/analyses`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "The file could not be processed.");
      }

      fileInfo.textContent = `Uploaded: ${data.file_name}`;
      showQualityResults(data);

      const uploadCard = document.querySelector(".upload-card");
      if (uploadCard) {
        uploadCard.hidden = true;
      }
      try {
        const traceResponse = await fetch(
          `${apiBaseUrl}/analyses/${data.id}/chromatogram`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        if (!traceResponse.ok)
          throw new Error("Chromatogram could not be loaded.");
        showChromatogram(await traceResponse.json());
      } catch (traceError) {
        document.getElementById("chromatogramSection").hidden = true;
        const note = document.createElement("p");
        note.textContent = traceError.message;
        message.appendChild(note);
      }
    } catch (error) {
      message.textContent = error.message;
    } finally {
      analyzeButton.disabled = false;
    }
  });
})();
