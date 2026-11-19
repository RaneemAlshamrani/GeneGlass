/* GeneGlass - Saved Analysis Details */

(() => {
  const fileDetails = document.getElementById("fileDetails");
  const chromatogram = document.getElementById("detailsChromatogram");
  let chromatogramController = null;
  const jak2Details = document.getElementById("jak2Details");
  const jak2Summary = document.getElementById("jak2Summary");
  const evidenceBadge = document.getElementById("evidenceBadge");
  const aiPrediction = document.getElementById("aiPrediction");
  const message = document.getElementById("detailsMessage");
  const detailsQcCard = document.getElementById("detailsQcCard");
  const detailsQcBadge = document.getElementById("detailsQcBadge");
  const detailsQcMessage = document.getElementById("detailsQcMessage");
  const detailsQcNote = document.getElementById("detailsQcNote");
  const detailsQcLink = document.getElementById("detailsQcLink");
  const reviewHistory = document.getElementById("reviewHistory");
  const reviewHistoryCount = document.getElementById("reviewHistoryCount");
  const latestReviewBadge = document.getElementById("latestReviewBadge");
  const auditCount = document.getElementById("auditCount");
  const auditStatus = document.getElementById("auditStatus");
  const auditTimeline = document.getElementById("auditTimeline");
  const printAuditButton = document.getElementById("printAuditButton");
  const auditPrintReference = document.getElementById("auditPrintReference");
  const reportBadge = document.getElementById("reportBadge");
  const reportArchiveTitle = document.getElementById("reportArchiveTitle");
  const reportArchiveMessage = document.getElementById("reportArchiveMessage");
  const downloadReportButton = document.getElementById("downloadReportButton");
  const editReportButton = document.getElementById("editReportButton");
  const continueReportLink = document.getElementById("continueReportLink");
  let savedReport = null;

  const apiBaseUrl = window.GeneGlassConfig.apiBaseUrl;

  const params = new URLSearchParams(window.location.search);
  const analysisId = params.get("id");

  const reviewLabels = {
    not_detected: "Not Detected",
    heterozygous: "Heterozygous",
    homozygous: "Homozygous",
    inconclusive: "Inconclusive",
  };

  function showCards(container, fields) {
    container.replaceChildren();

    fields.forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "details-item";

      const labelElement = document.createElement("span");
      labelElement.className = "details-label";
      labelElement.textContent = label;

      const valueElement = document.createElement("strong");
      valueElement.className = "details-value";
      valueElement.textContent = value ?? "N/A";

      card.append(labelElement, valueElement);
      container.appendChild(card);
    });
  }

  function formatPercent(value) {
    return Number.isFinite(Number(value))
      ? `${Number(value).toFixed(2)}%`
      : "N/A";
  }

  function formatRatio(value) {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(3) : "N/A";
  }

  function findNearbyMotif(sequence, targetBase, motif = "ACAT") {
    if (!sequence || !Number.isInteger(targetBase)) return null;
    const normalized = sequence.toUpperCase();
    const targetIndex = targetBase - 1;
    const from = Math.max(0, targetIndex - 12);
    const to = Math.min(normalized.length, targetIndex + 16);
    let best = null;
    let index = normalized.indexOf(motif, from);

    while (index !== -1 && index < to) {
      const distance = Math.abs(index - targetIndex);
      if (!best || distance < best.distance) best = { start: index, distance };
      index = normalized.indexOf(motif, index + 1);
    }

    return best
      ? { startBase: best.start + 1, endBase: best.start + motif.length }
      : null;
  }

  function inspectValue(feature, value) {
    if (
      value === null ||
      value === undefined ||
      !Number.isFinite(Number(value))
    )
      return "Unavailable";
    const number = Number(value);
    if (
      ["peak_overlap_score", "alternative_ratio", "local_noise_ratio"].includes(
        feature,
      )
    ) {
      return `${(number * 100).toFixed(1)}%`;
    }
    if (feature === "phred_quality") return `Q${Math.round(number)}`;
    return number.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }

  function openShapInspector(explanation, trigger) {
    if (
      !chromatogramController?.canInspect?.() ||
      !chromatogram?.isConnected ||
      !Array.isArray(explanation?.contributions) ||
      !explanation.contributions.length
    ) {
      return false;
    }
    if (document.querySelector(".gg-evidence-dialog")) return true;

    const featureData = new Map(
      explanation.contributions.map((item) => [item.feature, item]),
    );
    const peakFeature =
      featureData.get("peak_overlap_score") ||
      featureData.get("alternative_ratio");
    const qualityFeature = featureData.get("phred_quality");
    if (!peakFeature && !qualityFeature) return false;

    const placeholder = document.createComment(
      "GeneGlass chromatogram location",
    );
    const originalParent = chromatogram.parentNode;
    originalParent.insertBefore(placeholder, chromatogram);

    const dialog = document.createElement("dialog");
    dialog.className = "gg-evidence-dialog";
    dialog.setAttribute("aria-label", "Inspect GeneGlass AI evidence");
    const frame = document.createElement("div");
    frame.className = "gg-evidence-frame";
    const header = document.createElement("div");
    header.className = "gg-evidence-header";
    const heading = document.createElement("div");
    const title = document.createElement("h2");
    title.textContent = "Inspect AI evidence";
    const subtitle = document.createElement("p");
    subtitle.textContent =
      "Choose what to inspect on the original AB1 chromatogram.";
    heading.append(title, subtitle);
    const close = document.createElement("button");
    close.type = "button";
    close.className = "gg-evidence-close";
    close.textContent = "Close ×";
    close.setAttribute("aria-label", "Close AI evidence inspector");
    close.addEventListener("click", () => dialog.close());
    header.append(heading, close);

    const layout = document.createElement("div");
    layout.className = "gg-evidence-layout";
    const selector = document.createElement("nav");
    selector.className = "gg-evidence-selector";
    selector.setAttribute("aria-label", "Visual evidence options");
    const chooserHeading = document.createElement("h3");
    chooserHeading.textContent = "Inspect visually";
    selector.append(chooserHeading);

    const inspection = document.createElement("div");
    inspection.className = "gg-evidence-inspection";
    const measured = document.createElement("div");
    measured.className = "gg-evidence-measurement";
    const currentName = document.createElement("h3");
    const currentValue = document.createElement("strong");
    const currentImpact = document.createElement("span");
    const currentNote = document.createElement("p");
    measured.append(currentName, currentValue, currentImpact, currentNote);
    const viewerSlot = document.createElement("div");
    viewerSlot.className = "gg-evidence-viewer";
    viewerSlot.append(chromatogram);
    inspection.append(measured, viewerSlot);
    layout.append(selector, inspection);
    frame.append(header, layout);
    dialog.append(frame);
    originalParent.append(dialog);

    const buttons = [];
    function setActive(button) {
      for (const candidate of buttons) {
        const active = candidate === button;
        candidate.classList.toggle("active", active);
        candidate.setAttribute("aria-pressed", String(active));
      }
    }

    function showPeaks(button) {
      setActive(button);
      const reference = featureData.get("reference_peak")?.value;
      const alternative = featureData.get("alternative_peak")?.value;
      const altPercent = featureData.get("alternative_ratio")?.value;
      const overlap = featureData.get("peak_overlap_score")?.value;
      currentName.textContent = "Target peak signals";
      currentValue.textContent = `Reference: ${inspectValue("reference_peak", reference)}  |  Alternative: ${inspectValue("alternative_peak", alternative)}`;
      currentImpact.textContent =
        "Four related model measurements from the SAME TWO peaks";
      currentNote.textContent = `Alternative is ${inspectValue("alternative_ratio", altPercent)} of their combined intensity, and ${inspectValue("peak_overlap_score", overlap)} as strong as the reference. These are two ratios of the same signals, not separate peaks.`;
      chromatogramController.focusFeature("peak_overlap_score", overlap);
    }

    function showQuality(button) {
      setActive(button);
      const item = featureData.get("phred_quality");
      const impact = Number(item?.impact) || 0;
      currentName.textContent = "Base reading quality";
      currentValue.textContent = `Measured: ${inspectValue("phred_quality", item?.value)}`;
      currentImpact.textContent = `${Math.abs(impact * 100).toFixed(1)} points ${impact >= 0 ? "raising" : "lowering"} the model's Heterozygous estimate`;
      currentNote.textContent =
        "Phred quality describes reliability of the called base. It does not prove whether the alternative peak is a mutation or background noise.";
      chromatogramController.focusFeature("phred_quality", item?.value);
    }

    function addChoice(title, subtitle, handler) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "gg-evidence-feature";
      const name = document.createElement("strong");
      name.textContent = title;
      const note = document.createElement("small");
      note.textContent = subtitle;
      button.append(name, note);
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => handler(button));
      selector.append(button);
      buttons.push(button);
      return button;
    }

    let defaultButton = null;
    if (peakFeature) {
      defaultButton = addChoice(
        "Target peak signals",
        "Reference, alternative and their ratios",
        showPeaks,
      );
    }
    if (qualityFeature) {
      const qualityButton = addChoice(
        "Base reading quality",
        inspectValue("phred_quality", qualityFeature.value),
        showQuality,
      );
      if (!defaultButton) defaultButton = qualityButton;
    }

    const background = featureData.get("local_noise_ratio");
    const alignment = featureData.get("alignment_score");
    if (background || alignment) {
      const extra = document.createElement("details");
      extra.className = "gg-evidence-context";
      const extraHeading = document.createElement("summary");
      extraHeading.textContent = "Other model measurements (no single peak)";
      extra.append(extraHeading);
      for (const [feature, label, explanationText] of [
        [
          "local_noise_ratio",
          "Background noise",
          "Summarizes nearby background signals; no specific peak is identified as noise.",
        ],
        [
          "alignment_score",
          "Sequence alignment",
          "Measures sequence alignment against the reference; not an individual chromatogram peak.",
        ],
      ]) {
        const item = featureData.get(feature);
        if (!item) continue;
        const row = document.createElement("div");
        row.className = "gg-evidence-context-item";
        const name = document.createElement("strong");
        name.textContent = `${label}: ${inspectValue(feature, item.value)}`;
        const note = document.createElement("p");
        note.textContent = explanationText;
        row.append(name, note);
        extra.append(row);
      }
      selector.append(extra);
    }

    dialog.addEventListener(
      "close",
      () => {
        chromatogramController.clearEvidence();
        placeholder.replaceWith(chromatogram);
        dialog.remove();
        trigger?.focus();
      },
      { once: true },
    );
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    if (typeof dialog.showModal !== "function") {
      placeholder.replaceWith(chromatogram);
      dialog.remove();
      return false;
    }

    dialog.showModal();
    defaultButton.click();
    close.focus();
    return true;
  }

  function showUnsupportedTargetAdvisory(pattern) {
    document.getElementById("geneglassUnsupportedNotice")?.remove();
    if (!pattern?.review_recommended) return;

    const box = document.createElement("section");
    box.id = "geneglassUnsupportedNotice";
    box.setAttribute("role", "alert");
    box.style.cssText =
      "border:1px solid #dfa74c;border-left:5px solid #bd7916;border-radius:12px;padding:15px 18px;margin:12px 0;background:#fff7e7;color:#443218;";

    const title = document.createElement("strong");
    title.textContent =
      "Possible Unsupported Target Pattern — Specialist Review Required";

    const explanation = document.createElement("p");
    explanation.style.margin = "8px 0 0";
    explanation.textContent =
      "Predominantly alternative signal at JAK2 V617F (raw " +
      pattern.raw_alternative_channel +
      " vs " +
      pattern.raw_reference_channel +
      "; other/alternative ratio " +
      Number(pattern.max_other_to_alternative_ratio).toFixed(3) +
      "). The binary AI model cannot establish a homozygous genotype. " +
      "Do not accept the AI prediction without specialist verification. Research advisory only.";

    box.append(title, explanation);

    aiPrediction.insertAdjacentElement("afterend", box);

    // This is a visual review recommendation, NOT a stored QC or review decision.
    evidenceBadge.textContent = "Specialist review recommended";
    evidenceBadge.dataset.status = "review";
  }

  function renderEvidenceSummary(result) {
    const notFound = result.found === false;
    const status = notFound
      ? "Target Not Found"
      : result.needs_review
        ? "Needs review"
        : "Technical evidence available";

    evidenceBadge.textContent = status;
    evidenceBadge.dataset.status =
      notFound || result.needs_review ? "review" : "ready";

    if (notFound) {
      jak2Summary.replaceChildren();
      const note = document.createElement("p");
      note.className = "evidence-unavailable";
      note.textContent =
        "The JAK2 V617F target was not reliably mapped. No AI classification is available.";
      jak2Summary.appendChild(note);
      return;
    }

    const items = [
      [
        "Target",
        result.genomic_position
          ? `NC_000009.12:g.${result.genomic_position}`
          : "JAK2 V617F",
      ],
      [
        "Read base",
        `${result.observed_base || "N/A"} · Q${result.quality_score ?? "N/A"}`,
      ],
      [
        "Alignment",
        `${formatPercent(result.alignment_identity_percentage)} identity`,
      ],
      ["Coverage", formatPercent(result.alignment_coverage_percentage)],
    ];

    jak2Summary.replaceChildren();

    items.forEach(([label, value], index) => {
      const item = document.createElement("div");
      item.className =
        index === 0
          ? "evidence-summary-item evidence-summary-target"
          : "evidence-summary-item";

      const name = document.createElement("span");
      name.textContent = label;

      const content = document.createElement("strong");
      content.textContent = value;

      item.append(name, content);
      jak2Summary.appendChild(item);
    });
  }

  function probabilityLabel(value) {
    const number = Number(value);
    return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : "N/A";
  }

  function createPredictionMetric(label, value, tone) {
    const metric = document.createElement("div");
    metric.className = "prediction-metric";

    const heading = document.createElement("div");
    const name = document.createElement("span");
    const amount = document.createElement("strong");

    name.textContent = label;
    amount.textContent = probabilityLabel(value);
    heading.append(name, amount);

    const track = document.createElement("div");
    track.className = "prediction-meter";

    const fill = document.createElement("span");
    fill.className = `prediction-meter-fill ${tone}`;
    fill.style.width = `${Math.max(0, Math.min(100, Number(value) * 100 || 0))}%`;

    track.append(fill);
    metric.append(heading, track);
    return metric;
  }

  function renderAiPrediction(data) {
    aiPrediction.classList.remove("ai-gate-notice");
    aiPrediction.replaceChildren();
    aiPrediction.setAttribute("aria-busy", "false");

    const status = String(data.status || "Needs Review");
    const normalized = status.toLowerCase().replaceAll(" ", "-");
    const isHetero = data.prediction === "hetero";
    const isNegative = data.prediction === "negative";

    const displayStatus = isHetero
      ? "Heterozygous pattern"
      : isNegative
        ? "Not Detected"
        : "Model result needs review";

    const header = document.createElement("div");
    header.className = "ai-prediction-header";

    const titleGroup = document.createElement("div");
    titleGroup.className = "ai-prediction-title";

    const icon = document.createElement("span");
    icon.className = "ai-model-icon";
    icon.innerHTML = '<i class="fa-solid fa-microchip" aria-hidden="true"></i>';

    const titleText = document.createElement("div");
    const title = document.createElement("strong");

    title.textContent = "AI Prediction";
    titleText.append(title);
    titleGroup.append(icon, titleText);

    const badge = document.createElement("span");
    badge.className = "ai-status-badge";
    badge.dataset.status = normalized;
    badge.textContent = displayStatus;

    header.append(titleGroup, badge);

    const body = document.createElement("div");
    body.className = "ai-prediction-body";

    const summary = document.createElement("div");
    summary.className = "ai-result-summary";

    const resultLabel = document.createElement("span");
    resultLabel.textContent = "Model output";

    const resultValue = document.createElement("strong");
    resultValue.textContent = displayStatus;

    const orientation = document.createElement("small");
    orientation.textContent = data.orientation
      ? `Read orientation: ${data.orientation}`
      : "Read orientation unavailable";

    summary.append(resultLabel, resultValue, orientation);

    if (data.reason) {
      const reason = document.createElement("p");
      reason.className = "ai-review-reason";
      reason.textContent = data.reason;
      summary.appendChild(reason);
    }

    body.appendChild(summary);

    if (data.probabilities) {
      const metrics = document.createElement("div");
      metrics.className = "prediction-metrics";

      metrics.append(
        createPredictionMetric(
          "Heterozygous",
          data.probabilities.hetero,
          "hetero",
        ),
        createPredictionMetric(
          "Not Detected",
          data.probabilities.negative,
          "negative",
        ),
      );

      body.appendChild(metrics);
    }

    const explanation = window.GeneGlassShapExplanation?.create(
      data.explanation,
      (shapData, trigger) => openShapInspector(shapData, trigger),
    );

    if (explanation) body.appendChild(explanation);

    aiPrediction.append(header, body);
  }

  function renderAiPredictionError(messageText) {
    renderAiPrediction({
      status: "Needs Review",
      prediction: null,
      reason: messageText || "Model prediction is currently unavailable.",
      research_use_only: true,
    });
  }

  async function loadAiPrediction(token) {
    try {
      const response = await fetch(
        `${apiBaseUrl}/analyses/${analysisId}/ai-prediction`,
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Model prediction is currently unavailable.",
        );
      }

      renderAiPrediction(data);
    } catch (error) {
      console.error("AI prediction error:", error);
      renderAiPredictionError(error.message);
    }
  }

  function renderInitialQcState(qc, details) {
    detailsQcCard.hidden = false;
    detailsQcLink.href = `../AnalysisPage/analysis.html?id=${analysisId}`;
    detailsQcLink.hidden =
      qc.target_found !== true || qc.decision !== "pending";
    detailsQcLink.textContent = "Complete pending QC review";

    detailsQcBadge.dataset.state =
      qc.target_found !== true ? "target_not_found" : qc.decision;
    detailsQcBadge.textContent =
      qc.target_found !== true
        ? "Target Not Found"
        : qc.decision === "continue_analysis"
          ? "Continue approved"
          : qc.decision === "request_repeat"
            ? "Repeat requested"
            : "Pending decision";

    detailsQcMessage.textContent =
      qc.target_found !== true
        ? "Target Not Found — AI classification is unavailable because JAK2 V617F could not be mapped."
        : qc.decision === "continue_analysis"
          ? "The specialist authorized AI analysis after examining the original chromatogram."
          : qc.decision === "request_repeat"
            ? "A repeat was requested. New AI classification is blocked."
            : "Initial QC is awaiting the specialist's Continue Analysis or Request Repeat decision.";

    detailsQcNote.textContent = qc.comment
      ? `Specialist note: ${qc.comment}`
      : qc.decision === "pending" && details.ai_prediction
        ? "This analysis has a historical AI output saved before the new QC approval workflow."
        : "";

    const blocked =
      qc.target_found !== true || qc.decision === "request_repeat";

    if (qc.target_found !== true) {
      evidenceBadge.textContent = "Target Not Found";
      evidenceBadge.dataset.status = "review";
    }

    // No unapproved molecular report can be completed for a blocked sample.
    if (blocked && savedReport?.status !== "finalized") {
      reportBadge.textContent = "Unavailable";
      reportArchiveTitle.textContent = "No report available";
      reportArchiveMessage.textContent =
        qc.target_found !== true
          ? "Target Not Found: AI-based reporting is unavailable for this read."
          : "A repeat was requested. AI-based reporting is blocked for this read.";
      downloadReportButton.hidden = true;
      editReportButton.hidden = true;
      continueReportLink.hidden = true;
    }
  }

  function renderAiGateNotice(title, messageText) {
    aiPrediction.classList.add("ai-gate-notice");
    aiPrediction.replaceChildren();
    aiPrediction.setAttribute("aria-busy", "false");

    const titleNode = document.createElement("strong");
    titleNode.textContent = title;

    const note = document.createElement("p");
    note.textContent = messageText;

    aiPrediction.append(titleNode, note);
  }

  function renderSavedReport(report) {
    savedReport = report;
    continueReportLink.href = `../AnalysisPage/analysis.html?id=${analysisId}&report=1`;

    if (report?.status === "needs_update") {
      reportBadge.textContent = "Update required";
      reportBadge.dataset.decision = report.decision || "pending";
      reportArchiveTitle.textContent = "PDF decision is outdated";
      reportArchiveMessage.textContent =
        "The Specialist Review decision changed. Open New Analysis to generate a new PDF version.";
      downloadReportButton.hidden = true;
      editReportButton.hidden = true;
      continueReportLink.hidden = false;
      continueReportLink.innerHTML =
        '<i class="fa-solid fa-rotate"></i> Update PDF';
      return;
    }

    if (!report || report.status !== "finalized") {
      reportBadge.textContent = "Not created";
      reportBadge.dataset.decision = "pending";
      reportArchiveTitle.textContent = "No finalized report";
      reportArchiveMessage.textContent = "";
      downloadReportButton.hidden = true;
      editReportButton.hidden = true;
      continueReportLink.hidden = false;
      continueReportLink.innerHTML =
        '<i class="fa-solid fa-arrow-up-right-from-square"></i> Open in New Analysis';
      return;
    }

    const storedDecision = report.final_decision || report.decision;
    const decision =
      reviewLabels[storedDecision] || storedDecision || "Unavailable";

    reportBadge.textContent = `Final · v${report.version}`;
    reportBadge.dataset.decision = storedDecision || "pending";
    reportArchiveTitle.textContent = `Final report · ${decision}`;
    reportArchiveMessage.textContent =
      "The finalized PDF is stored and ready to download.";

    downloadReportButton.hidden = false;
    editReportButton.hidden = false;
    continueReportLink.hidden = true;
  }

  async function downloadSavedReport() {
    const token = window.GeneGlassAuth?.token;
    if (!token || !savedReport?.download_url) return;

    const previewWindow = window.open("", "_blank");

    downloadReportButton.disabled = true;
    downloadReportButton.textContent = "Opening...";

    try {
      const response = await fetch(
        `${apiBaseUrl}/analyses/${analysisId}/report.pdf?version=${savedReport.version}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );

      if (!response.ok)
        throw new Error("The saved report could not be downloaded.");

      const pdfUrl = URL.createObjectURL(await response.blob());

      if (previewWindow) {
        previewWindow.opener = null;
        previewWindow.location.href = pdfUrl;
      }

      window.setTimeout(() => URL.revokeObjectURL(pdfUrl), 60000);
    } catch (error) {
      if (previewWindow && previewWindow.location.href === "about:blank") {
        previewWindow.close();
      }

      reportArchiveMessage.textContent = error.message;
    } finally {
      downloadReportButton.disabled = false;
      downloadReportButton.innerHTML =
        '<i class="fa-solid fa-file-pdf"></i> Download PDF';
    }
  }

  const auditLabels = {
    "analysis.uploaded": "Analysis uploaded",
    "analysis.preliminary_evidence_recalculated": "JAK2 evidence recalculated",
    "analysis.review_created": "Specialist review recorded",
    "analysis.qc_decision_recorded": "Initial QC decision recorded",
  };

  function formatAuditDetails(details) {
    if (!details || typeof details !== "object") return "";

    const readable = [];

    if (details.decision) {
      const qcLabels = {
        continue_analysis: "Continue Analysis",
        request_repeat: "Request Repeat",
      };
      readable.push(
        `Decision: ${qcLabels[details.decision] || reviewLabels[details.decision] || details.decision}`,
      );
    }

    if (details.qc_status) readable.push(`QC: ${details.qc_status}`);

    return readable.join(" · ");
  }

  function renderAuditTrail(data) {
    const events = Array.isArray(data.events) ? data.events : [];

    auditTimeline.replaceChildren();
    auditCount.textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;
    auditStatus.textContent = events.length
      ? ""
      : "No audit events are recorded for this analysis yet.";

    events.forEach((event) => {
      const entry = document.createElement("article");
      entry.className = "audit-entry";

      const marker = document.createElement("span");
      marker.className = "audit-marker";
      marker.setAttribute("aria-hidden", "true");

      const content = document.createElement("div");
      const heading = document.createElement("div");
      heading.className = "audit-entry-heading";

      const action = document.createElement("strong");
      action.textContent = auditLabels[event.action] || event.action;

      const time = document.createElement("time");
      time.dateTime = event.created_at;
      time.textContent = new Date(event.created_at).toLocaleString();

      heading.append(action, time);

      const actor = document.createElement("p");
      actor.textContent = `${event.actor_name} · ${event.actor_role}`;

      content.append(heading, actor);

      const details = formatAuditDetails(event.details);

      if (details) {
        const detail = document.createElement("small");
        detail.textContent = details;
        content.appendChild(detail);
      }

      entry.append(marker, content);
      auditTimeline.appendChild(entry);
    });
    printAuditButton.disabled = false;
  }

  function printAuditTrail() {
    const disclosure = document.querySelector(".audit-disclosure");
    const wasOpen = disclosure?.open === true;
    if (disclosure) disclosure.open = true;
    document.body.classList.add("printing-audit");
    window.addEventListener(
      "afterprint",
      () => {
        document.body.classList.remove("printing-audit");
        if (disclosure && !wasOpen) disclosure.open = false;
      },
      { once: true },
    );
    window.print();
  }

  async function loadAuditTrail(token) {
    const response = await fetch(
      `${apiBaseUrl}/analyses/${analysisId}/audit-events`,
      { headers: { Authorization: `Bearer ${token}` } },
    );

    if (!response.ok) throw new Error("Unable to load audit trail.");

    renderAuditTrail(await response.json());
  }

  function renderReviewHistory(data) {
    const reviews = Array.isArray(data.reviews) ? data.reviews : [];

    reviewHistory.replaceChildren();
    reviewHistoryCount.textContent = String(reviews.length);

    latestReviewBadge.textContent = data.latest_decision
      ? reviewLabels[data.latest_decision] || data.latest_decision
      : "Not reviewed";

    latestReviewBadge.dataset.decision = data.latest_decision || "none";

    if (
      !reviews.length &&
      ["target_not_found", "request_repeat"].includes(
        detailsQcBadge.dataset.state,
      )
    ) {
      latestReviewBadge.textContent = "Not applicable";
    }

    if (!reviews.length) {
      const empty = document.createElement("p");
      empty.className = "review-empty";
      empty.textContent = "No specialist review has been recorded yet.";
      reviewHistory.appendChild(empty);
      return;
    }

    reviews.forEach((review) => {
      const entry = document.createElement("article");
      entry.className = "review-entry";

      const heading = document.createElement("div");
      heading.className = "review-entry-heading";

      const decision = document.createElement("strong");
      decision.textContent = reviewLabels[review.decision] || review.decision;

      const time = document.createElement("time");
      time.dateTime = review.created_at;
      time.textContent = new Date(review.created_at).toLocaleString();

      heading.append(decision, time);

      const comment = document.createElement("p");
      comment.textContent = review.comment;

      const reviewer = document.createElement("small");
      reviewer.textContent = `${review.reviewer_name} · ${review.reviewer_role}`;

      entry.append(heading, comment, reviewer);
      reviewHistory.appendChild(entry);
    });
  }

  async function loadReviewHistory(token) {
    const response = await fetch(
      `${apiBaseUrl}/analyses/${analysisId}/reviews`,
      { headers: { Authorization: `Bearer ${token}` } },
    );

    if (!response.ok) {
      throw new Error("Unable to load specialist review history.");
    }

    renderReviewHistory(await response.json());
  }

  async function loadDetails() {
    const token = window.GeneGlassAuth?.token;

    if (!token) return;

    if (!analysisId || !/^\d+$/.test(analysisId)) {
      message.textContent = "Invalid analysis ID.";
      return;
    }

    try {
      const response = await fetch(`${apiBaseUrl}/analyses/${analysisId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Unable to load analysis details.");
      }

      const details = await response.json();
      renderSavedReport(details.report);
      auditPrintReference.textContent = `Analysis #${analysisId} | ${details.original_file_name || "AB1 file"}`;

      showCards(fileDetails, [
        ["AB1 file", details.original_file_name],
        [
          "Uploaded",
          details.created_at
            ? new Date(details.created_at).toLocaleDateString()
            : "N/A",
        ],
        [
          "QC status",
          String(details.qc_status || "pending").replaceAll("_", " "),
        ],
      ]);

      try {
        const [traceResponse, jak2Response] = await Promise.all([
          fetch(`${apiBaseUrl}/analyses/${analysisId}/chromatogram`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${apiBaseUrl}/analyses/${analysisId}/jak2-target`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
        ]);

        let targetBase = null;
        let readDirection = "Forward";

        if (jak2Response.ok) {
          const jak2Data = await jak2Response.json();
          const result = jak2Data.result || {};
          const peaks = result.peak_analysis || {};
          const heights = peaks.peak_heights || {};

          const reasons = Array.isArray(result.review_reasons)
            ? result.review_reasons.filter(Boolean).join("; ")
            : "";

          targetBase = Number(result.ab1_base_number);
          readDirection = result.direction || "Forward";

          renderEvidenceSummary(result);

          document.getElementById("geneglassUnsupportedNotice")?.remove();
          if (result.found === true) {
            showUnsupportedTargetAdvisory(result.unsupported_target_pattern);
          }

          showCards(jak2Details, [
            ["AB1 Position", result.ab1_base_number],
            [
              "Genomic Coordinate",
              result.genomic_position
                ? `NC_000009.12:g.${result.genomic_position}`
                : "N/A",
            ],
            [
              "Transcript Coordinate",
              result.coding_position
                ? `NM_004972.4:c.${result.coding_position}`
                : "N/A",
            ],
            ["Direction", result.direction],
            ["Observed Base", result.observed_base],
            ["Target Phred Quality", result.quality_score],
            [
              "Alignment Identity",
              formatPercent(result.alignment_identity_percentage),
            ],
            [
              "Read Coverage",
              formatPercent(result.alignment_coverage_percentage),
            ],
            ["A Peak", heights.A],
            ["C Peak", heights.C],
            ["G Peak", heights.G],
            ["T Peak", heights.T],
            ["Primary Peak", peaks.primary_base],
            ["Secondary Peak", peaks.secondary_base],
            ["Secondary / Primary", formatRatio(peaks.overlap_ratio)],
            [
              "Target QC Review",
              result.found === false
                ? "Target Not Found"
                : result.needs_review
                  ? "Needs Review"
                  : "No target QC flag",
            ],
            [
              "Target QC Reason",
              reasons || "No target mapping or peak review reason",
            ],
            ["Pipeline Version", result.pipeline_version],
          ]);
        } else {
          // A failed target endpoint should not leave a misleading 'Loading' message.
          evidenceBadge.textContent = "Evidence unavailable";
          evidenceBadge.dataset.status = "review";

          jak2Summary.replaceChildren();

          const unavailable = document.createElement("p");
          unavailable.className = "evidence-unavailable";
          unavailable.textContent =
            "Target evidence could not be loaded. Refer to the Initial QC decision for target-mapping status.";

          jak2Summary.appendChild(unavailable);
          jak2Details.textContent =
            "No mapped JAK2 V617F target evidence available.";
        }

        if (!traceResponse.ok) throw new Error("Unable to load chromatogram.");

        const trace = await traceResponse.json();

        if (!window.GeneGlassChromatogram)
          throw new Error("Chromatogram viewer script missing.");

        const motifRange = findNearbyMotif(trace.sequence, targetBase, "ACAT");

        chromatogramController = await window.GeneGlassChromatogram.render(
          trace,
          {
            targetBase:
              Number.isInteger(targetBase) && targetBase > 0
                ? targetBase
                : undefined,
            showTitle: false,
            initialBaseCount: 9,
            highlightRange: motifRange,
            initialSequence: "ACAT",
            readDirection,
            compact: true,
          },
        );

        document.getElementById("chromatogramLoading").hidden = true;
      } catch (error) {
        console.error("Chromatogram / JAK2 error:", error);
        document.getElementById("chromatogramLoading").textContent =
          "Chromatogram could not be loaded: " + error.message;
      }

      const qcResponse = await fetch(
        `${apiBaseUrl}/analyses/${analysisId}/preliminary-qc-decision`,
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );

      if (!qcResponse.ok)
        throw new Error("Unable to load Initial QC decision.");

      const qc = await qcResponse.json();
      renderInitialQcState(qc, details);

      if (qc.target_found !== true) {
        renderAiGateNotice(
          "Target Not Found",
          "AI prediction and SHAP are unavailable without mapped JAK2 V617F target evidence.",
        );
      } else if (qc.decision === "request_repeat") {
        renderAiGateNotice(
          "Request Repeat",
          "A specialist requested a new sequencing run. AI classification is not displayed.",
        );
      } else if (qc.decision === "pending" && !details.ai_prediction) {
        renderAiGateNotice(
          "Awaiting Initial QC Decision",
          "Open New Analysis to inspect the signal and choose Continue Analysis or Request Repeat.",
        );
      } else {
        await loadAiPrediction(token);
      }

      message.textContent = "";

      await Promise.all([loadReviewHistory(token), loadAuditTrail(token)]);
    } catch (error) {
      message.textContent = error.message;
    }
  }

  document.addEventListener("geneglass:auth-ready", loadDetails);
  printAuditButton.addEventListener("click", printAuditTrail);
  downloadReportButton.addEventListener("click", downloadSavedReport);

  // Open the saved report in edit mode without starting a new analysis.
  editReportButton.addEventListener("click", () => {
    if (!savedReport || savedReport.status !== "finalized") return;

    window.location.href = `../AnalysisPage/analysis.html?id=${analysisId}&editReport=1`;
  });

  if (window.GeneGlassAuth?.token) {
    loadDetails();
  }
})();
