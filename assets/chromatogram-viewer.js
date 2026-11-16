const DNA_IUPAC = Object.freeze({
  A: "A", C: "C", G: "G", T: "T",
  R: "AG", Y: "CT", S: "GC", W: "AT", K: "GT", M: "AC",
  B: "CGT", D: "AGT", H: "ACT", V: "ACG", N: "ACGT"
});

const DNA_COMPLEMENT = Object.freeze({
  A: "T", C: "G", G: "C", T: "A",
  R: "Y", Y: "R", S: "S", W: "W", K: "M", M: "K",
  B: "V", D: "H", H: "D", V: "B", N: "N"
});

function normalizeDnaQuery(value) {
  return String(value || "")
    .toUpperCase()
    .replace(/5['’]?|3['’]?/g, "")
    .replace(/[\s\-_]/g, "");
}

function reverseComplement(sequence) {
  return [...sequence].reverse().map((base) => DNA_COMPLEMENT[base] || "").join("");
}

function findSequenceMatches(readSequence, query, direction) {
  // Search the sequence currently displayed, not both strand orientations.
  const pattern = [...query].map((base) => `[${DNA_IUPAC[base]}]`).join("");
  const regex = new RegExp(`(?=(${pattern}))`, "g");
  return [...readSequence.matchAll(regex)].map((match) => ({
    start: match.index,
    end: match.index + query.length - 1,
    orientation: direction
  }));
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
    const rawSequence = String(trace.sequence || "").toUpperCase();
    const rawPositions = trace.base_positions || [];
    const rawChannels = trace.channels || {};
    const rawQuality = trace.quality_scores || [];

    if (
      !n ||
      rawPositions.length < n ||
      ["A", "C", "G", "T"].some((base) => !rawChannels[base]?.length)
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
    const rawDirection = String(options.readDirection || "Forward").toLowerCase() === "reverse"
      ? "Reverse" : "Forward";
    const sampleEnd = rawChannels.A.length - 1;
    const rawData = {
      sequence: rawSequence,
      positions: rawPositions,
      channels: rawChannels,
      quality: rawQuality
    };
    const flippedData = {
      sequence: reverseComplement(rawSequence),
      positions: [...rawPositions].reverse().map((position) => sampleEnd - position),
      channels: {
        A: [...rawChannels.T].reverse(),
        C: [...rawChannels.G].reverse(),
        G: [...rawChannels.C].reverse(),
        T: [...rawChannels.A].reverse()
      },
      quality: [...rawQuality].reverse()
    };
    let showingFlipped = false;
    let sequence = rawData.sequence;
    let positions = rawData.positions;
    let channels = rawData.channels;
    let quality = rawData.quality;
    let displayDirection = rawDirection;
    const requestedTarget = Number(options.targetBase);
    const rawTargetIndex = Number.isInteger(requestedTarget) &&
      requestedTarget >= 1 && requestedTarget <= n
      ? requestedTarget - 1
      : null;
    const requestedCount = Number(options.initialBaseCount);
    let count = Math.min(
      Number.isInteger(requestedCount) ? Math.max(5, requestedCount) : 30,
      n
    );
    let selected = rawTargetIndex;
    let focusedFeature = null;
    let focusedValue = null;
    let beforeInspection = null;
    let highlightStart = Number(options.highlightRange?.startBase) - 1;
    let highlightEnd = Number(options.highlightRange?.endBase) - 1;
    let hasHighlight = Number.isInteger(highlightStart) &&
      Number.isInteger(highlightEnd) && highlightStart >= 0 &&
      highlightEnd >= highlightStart && highlightEnd < n;
    const initialAnchor = hasHighlight
      ? (highlightStart + highlightEnd) / 2
      : selected;
    let first = initialAnchor === null
      ? 0
      : Math.max(0, initialAnchor - Math.floor(count / 2));
    let labels = [];
    let drag = null;

    section.replaceChildren();
    const title = options.showTitle === false
      ? null
      : document.createElement("h2");
    if (title) title.textContent = "Chromatogram Viewer";

    const toolbar = document.createElement("div");
    toolbar.className = "gg-viewer-toolbar";
    toolbar.innerHTML = `
      <label class="gg-sequence-label">
        Find primer or sequence
        <span class="gg-sequence-row">
          <input class="gg-sequence-query" type="text" maxlength="80" spellcheck="false" autocomplete="off" placeholder="e.g. ACAT or primer sequence" aria-describedby="ggSequenceStatus">
          <button class="gg-find-sequence" type="button">Find</button>
        </span>
        <small id="ggSequenceStatus" class="gg-sequence-status" aria-live="polite"></small>
      </label>
      <label class="gg-search-label">
        Displayed base
        <span class="gg-search-row">
          <input class="gg-go-base" type="number" min="1" max="${n}" placeholder="e.g. 184">
          <button class="gg-go-button" type="button">Go</button>
        </span>
      </label>
      <div class="gg-direction-control">
        <span>Display orientation</span>
        <button class="gg-toggle-direction" type="button"></button>
      </div>
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

    section.append(
      ...[
        title,
        toolbar,
        legend,
        chartWrapper,
        overview,
        selectedInfo,
        detail,
      ].filter(Boolean)
    );

    const goInput = toolbar.querySelector(".gg-go-base");
    const sequenceInput = toolbar.querySelector(".gg-sequence-query");
    const sequenceStatus = toolbar.querySelector(".gg-sequence-status");
    const findSequenceButton = toolbar.querySelector(".gg-find-sequence");
    const directionButton = toolbar.querySelector(".gg-toggle-direction");
    const verticalSlider = scaleControl.querySelector(".gg-vertical-scale");
    const verticalValue = scaleControl.querySelector(".gg-vertical-value");
    const horizontalSlider = overview.querySelector(".gg-overview-range");
    const horizontalValue = overview.querySelector(".gg-total-bases");

    function clampFirst(value) {
      return Math.max(0, Math.min(n - count, Math.round(value)));
    }

    function updateDirectionButton() {
      const nextDirection = displayDirection === "Forward" ? "Reverse" : "Forward";
      directionButton.textContent = `Current: ${displayDirection} · Switch to ${nextDirection}`;
      directionButton.setAttribute(
        "aria-label",
        `Currently showing ${displayDirection}. Switch chromatogram to ${nextDirection}.`
      );
      directionButton.dataset.direction = displayDirection.toLowerCase();
    }

    let lastSequenceQuery = "";
    let sequenceMatches = [];
    let sequenceMatchIndex = -1;

    function showPatternNotFoundNotification() {
      const existing = document.getElementById("gg-pattern-not-found");
      if (existing) existing.remove();

      if (!document.getElementById("gg-pattern-not-found-style")) {
        const style = document.createElement("style");
        style.id = "gg-pattern-not-found-style";
        style.textContent = `
#gg-pattern-not-found {
  position: fixed;
  inset: 50% auto auto 50%;
  transform: translate(-50%, -50%);
  margin: 0;
  width: min(360px, calc(100vw - 40px));
  max-height: calc(100vh - 40px);
  padding: 0;
  border: 1px solid #d7e1e2;
  border-radius: 8px;
  color: #29484d;
  box-shadow: 0 12px 35px rgba(20, 45, 50, .22);
  font: 14px Arial, sans-serif;
}
          #gg-pattern-not-found::backdrop {
            background: rgba(20, 35, 38, .28);
          }
          #gg-pattern-not-found .gg-notification-content {
            padding: 18px 20px 16px;
          }
          #gg-pattern-not-found .gg-notification-title {
            display: flex;
            align-items: center;
            gap: 9px;
            margin-bottom: 14px;
            font-size: 15px;
            font-weight: 700;
          }
          #gg-pattern-not-found .gg-notification-title i {
            color: #c58a20;
          }
          #gg-pattern-not-found p {
            margin: 0 0 18px;
            line-height: 1.5;
            font-weight: 600;
          }
          #gg-pattern-not-found button {
            display: block;
            min-width: 76px;
            margin-left: auto;
            padding: 7px 18px;
            border: 1px solid #aebfc1;
            border-radius: 4px;
            background: #f7faf9;
            color: #29484d;
            font-weight: 600;
            cursor: pointer;
          }
          #gg-pattern-not-found button:hover {
            background: #eaf2f1;
          }
        `;
        document.head.appendChild(style);
      }

      const dialog = document.createElement("dialog");
      dialog.id = "gg-pattern-not-found";
      dialog.innerHTML = `
        <div class="gg-notification-content">
          <div class="gg-notification-title">
            <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
            <span>GeneGlass</span>
          </div>
          <p>PATTERN NOT FOUND THROUGH END OF FILE</p>
          <button type="button">OK</button>
        </div>
      `;
      document.body.appendChild(dialog);
      dialog.querySelector("button").addEventListener("click", () => dialog.close());
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
      dialog.addEventListener("close", () => dialog.remove(), { once: true });
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        window.alert("PATTERN NOT FOUND THROUGH END OF FILE");
        dialog.remove();
      }
    }

    function runSequenceSearch() {
      const query = normalizeDnaQuery(sequenceInput.value);
      if (query.length < 3) {
        sequenceStatus.textContent = "Enter at least 3 DNA bases.";
        sequenceStatus.dataset.state = "error";
        return;
      }
      if ([...query].some((base) => !DNA_IUPAC[base])) {
        sequenceStatus.textContent = "Use valid IUPAC DNA bases only.";
        sequenceStatus.dataset.state = "error";
        return;
      }
      if (query !== lastSequenceQuery) {
        sequenceMatches = findSequenceMatches(sequence, query, displayDirection);
        sequenceMatchIndex = -1;
        lastSequenceQuery = query;
      }
      if (!sequenceMatches.length) {
        sequenceStatus.textContent = "";
        sequenceStatus.dataset.state = "";
        showPatternNotFoundNotification();
        return;
      }
      sequenceMatchIndex = (sequenceMatchIndex + 1) % sequenceMatches.length;
      const match = sequenceMatches[sequenceMatchIndex];
      highlightStart = match.start;
      highlightEnd = match.end;
      hasHighlight = true;
      selected = match.start;
      const matchLength = match.end - match.start + 1;
      if (matchLength + 4 > count) count = Math.min(n, Math.max(9, matchLength + 4));
      first = clampFirst((match.start + match.end) / 2 - Math.floor(count / 2));
      // Keep the search result visible on the chromatogram without showing
      // the green "Match found" message under the primer field.
      sequenceStatus.textContent = "";
      sequenceStatus.dataset.state = "";
      draw();
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
        if (hasHighlight && i >= highlightStart && i <= highlightEnd) {
          const previous = i === 0 ? positions[i] - 8 : (positions[i - 1] + positions[i]) / 2;
          const next = i === n - 1 ? positions[i] + 8 : (positions[i] + positions[i + 1]) / 2;
          ctx.fillStyle = "rgba(238, 177, 45, .13)";
          ctx.fillRect(x(previous), top, Math.max(1, x(next) - x(previous)), bottom - top + 22);
        }
        if (selected === i) {
          ctx.fillStyle = "rgba(0, 132, 139, .10)";
          ctx.fillRect(px - 8, top, 16, bottom - top + 22);
          ctx.strokeStyle = "#00848b";
          ctx.lineWidth = 1;
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

      const referenceBase = displayDirection === "Reverse" ? "C" : "G";
      const alternativeBase = displayDirection === "Reverse" ? "A" : "T";
      const highlightedSignals = focusedFeature === "alternative_peak"
        ? [alternativeBase]
        : focusedFeature === "reference_peak"
          ? [referenceBase]
          : ["alternative_ratio", "peak_overlap_score"].includes(focusedFeature)
            ? [referenceBase, alternativeBase]
            : null;

      for (const base of ["A", "C", "G", "T"]) {
        const emphasized = !highlightedSignals || highlightedSignals.includes(base);
        drawTrace(
          channels[base], base,
          emphasized ? 1 : 0.12,
          highlightedSignals && emphasized ? 3.8 : 1.35
        );
      }

      // GeneGlassSHAPTargetMarker: mark actual channel peaks near the mapped target.
      if (focusedFeature && selected !== null && selected >= first && selected <= last) {
        const targetSample = Math.round(positions[selected]);
        ctx.save();
        ctx.strokeStyle = "#b88219";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x(targetSample), top);
        ctx.lineTo(x(targetSample), bottom);
        ctx.stroke();
        ctx.setLineDash([]);

        for (const base of (highlightedSignals || [])) {
          const values = channels[base];
          const center = Math.max(left, Math.min(right, targetSample));
          let strongest = center;
          for (let sample = Math.max(left, center - 3); sample <= Math.min(right, center + 3); sample++) {
            if ((Number(values[sample]) || 0) > (Number(values[strongest]) || 0)) {
              strongest = sample;
            }
          }
          const px = x(strongest);
          const py = y(values[strongest]);
          ctx.beginPath();
          ctx.arc(px, py, 7, 0, Math.PI * 2);
          ctx.fillStyle = "#ffffff";
          ctx.fill();
          ctx.lineWidth = 3;
          ctx.strokeStyle = colors[base];
          ctx.stroke();

          const label = `${base === alternativeBase ? "ALT" : "REF"} (${base})`;
          ctx.font = "bold 12px Arial";
          ctx.textAlign = "left";
          const labelWidth = ctx.measureText(label).width;
          const labelX = Math.max(6, Math.min(w - labelWidth - 6, px + 11));
          const labelY = py > top + 30 ? py - 12 : py + 24;
          ctx.fillStyle = colors[base];
          ctx.fillText(label, labelX, Math.max(13, Math.min(bottom - 2, labelY)));
        }
        ctx.restore();
      }

      // Quality is attached to the base call, not to a particular colored peak.
      // Noise is a local numerical summary: do not invent a noise threshold on the trace.
      if (focusedFeature === "phred_quality" &&
          selected !== null && selected >= first && selected <= last) {
        const px = x(positions[selected]);
        const label = focusedValue === null
          ? `Base quality Q${quality[selected] ?? "N/A"}`
          : `Base quality Q${Math.round(focusedValue)}`;
        ctx.save();
        ctx.strokeStyle = "#087e85";
        ctx.lineWidth = 2.5;
        ctx.strokeRect(px - 11, top, 22, bottom - top + 12);
        ctx.font = "bold 12px Arial";
        const boxWidth = Math.min(w - pad * 2, ctx.measureText(label).width + 20);
        const boxX = Math.max(pad, Math.min(w - pad - boxWidth, px - boxWidth / 2));
        ctx.fillStyle = "#087e85";
        ctx.fillRect(boxX, top + 5, boxWidth, 25);
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "center";
        ctx.fillText(label, boxX + boxWidth / 2, top + 22);
        ctx.restore();
      }

      // Keep all original signal peaks. Only thin text labels when there is
      // insufficient horizontal space, so letters/numbers never collide.
      const selectedX = selected !== null && selected >= first && selected <= last
        ? x(positions[selected]) : null;
      const baseFont = "bold 12px Arial";
      const numberFont = "10px Arial";
      ctx.textAlign = "center";
      const labelCandidates = labels.map(({ x: px, index }) => {
        const base = sequence[index].toUpperCase();
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
        ctx.fillStyle = colors[sequence[selected].toUpperCase()] || "#666";
        ctx.fillText(sequence[selected], selectedX, h - 35);
        ctx.font = numberFont;
        ctx.fillStyle = "#00848b";
        ctx.fillText(String(selected + 1), selectedX, h - 18);
      }

      detail.textContent = options.compact
        ? `${displayDirection} · bases ${first + 1}–${last + 1}`
        : `Showing AB1 bases ${first + 1}–${last + 1} of ${n}.`;

      horizontalSlider.value = String(count);
      horizontalValue.textContent = `${count} bases`;

      if (selected === null) {
        selectedInfo.textContent = "Select a base to inspect its quality.";
      } else {
        const q = quality[selected];
        selectedInfo.textContent =
          `Base ${selected + 1} · ${sequence[selected]} · Q${q ?? "N/A"} · ${displayDirection}`;
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

    sequenceInput.value = options.initialSequence || "";
    findSequenceButton.onclick = runSequenceSearch;
    sequenceInput.onkeydown = event => {
      if (event.key === "Enter") {
        event.preventDefault();
        runSequenceSearch();
      }
    };
    sequenceInput.oninput = () => {
      sequenceStatus.textContent = "";
      sequenceStatus.dataset.state = "";
    };

    goInput.onkeydown = event => {
      if (event.key === "Enter") {
        event.preventDefault();
        toolbar.querySelector(".gg-go-button").click();
      }
    };

    goInput.oninput = () => goInput.setCustomValidity("");

    updateDirectionButton();
    directionButton.onclick = () => {
      const previousCenter = first + (count - 1) / 2;
      showingFlipped = !showingFlipped;
      const data = showingFlipped ? flippedData : rawData;
      sequence = data.sequence;
      positions = data.positions;
      channels = data.channels;
      quality = data.quality;
      displayDirection = showingFlipped
        ? (rawDirection === "Forward" ? "Reverse" : "Forward")
        : rawDirection;
      selected = selected === null ? null : n - 1 - selected;
      if (hasHighlight) {
        const previousStart = highlightStart;
        highlightStart = n - 1 - highlightEnd;
        highlightEnd = n - 1 - previousStart;
      }
      // The highlighted bases were mapped to their mirrored indices above.
      // Keep that same physical region highlighted when switching strands;
      // do not search the typed primer again, because its reverse complement
      // may have a different letter sequence.
      first = clampFirst(n - 1 - previousCenter - Math.floor(count / 2));
      lastSequenceQuery = "";
      sequenceMatches = [];
      sequenceMatchIndex = -1;
      sequenceStatus.textContent = "";
      sequenceStatus.dataset.state = "";
      updateDirectionButton();
      draw();
    };

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

    return Object.freeze({
      focusFeature(feature, value) {
        if (rawTargetIndex === null) return false;
        if (beforeInspection === null) {
          beforeInspection = {
            selected, first, count, hasHighlight, highlightStart, highlightEnd,
            showingFlipped
          };
        }
        focusedFeature = feature;
        focusedValue = value === null || value === undefined ? null : Number(value);
        if (!Number.isFinite(focusedValue)) focusedValue = null;
        return this.focusTarget();
      },
      focusTarget() {
        if (rawTargetIndex === null) return false;
        selected = showingFlipped ? n - 1 - rawTargetIndex : rawTargetIndex;
        highlightStart = selected;
        highlightEnd = selected;
        hasHighlight = true;
        first = clampFirst(selected - Math.floor(count / 2));
        draw();
        return true;
      },
      clearEvidence() {
        focusedFeature = null;
        focusedValue = null;
        if (beforeInspection !== null) {
          const old = beforeInspection;
          selected = old.selected;
          first = old.first;
          count = old.count;
          hasHighlight = old.hasHighlight;
          highlightStart = old.highlightStart;
          highlightEnd = old.highlightEnd;
          showingFlipped = old.showingFlipped;
          const data = showingFlipped ? flippedData : rawData;
          sequence = data.sequence;
          positions = data.positions;
          channels = data.channels;
          quality = data.quality;
          displayDirection = showingFlipped
            ? (rawDirection === "Forward" ? "Reverse" : "Forward")
            : rawDirection;
          updateDirectionButton();
          beforeInspection = null;
        }
        draw();
      },
      canInspect() { return rawTargetIndex !== null; }
    });
  }
};
