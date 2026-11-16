(() => {
  const fileInput = document.getElementById("ab1");
  const fileInfo = document.getElementById("fileInfo");
  const button = document.getElementById("analyze");
  const message = document.getElementById("message");
  const workflow = document.getElementById("analysisWorkflow");
  const workflowProgressStatus = document.getElementById("workflowProgressStatus");
  const workflowStages = [...document.querySelectorAll("[data-workflow-stage]")];
  const workflowIndicators = [...document.querySelectorAll("[data-workflow-indicator]")];
  const section = document.getElementById("chromatogramSection");
  const uploadCard = document.querySelector(".upload-card");
  const initialQcCard = document.getElementById("initialQcCard");
  const initialQcBadge = document.getElementById("initialQcBadge");
  const initialQcTarget = document.getElementById("initialQcTarget");
  const initialQcMetrics = document.getElementById("initialQcMetrics");
  const initialQcComment = document.getElementById("initialQcComment");
  const initialQcContinue = document.getElementById("initialQcContinue");
  const initialQcRepeat = document.getElementById("initialQcRepeat");
  const initialQcMessage = document.getElementById("initialQcMessage");
  const initialQcRepeatConfirmation = document.getElementById("initialQcRepeatConfirmation");
  const aiResultMount = document.getElementById("analysisAiResultMount");
  const modelBack = document.getElementById("modelBack");
  const modelNext = document.getElementById("modelNext");
  const reviewBack = document.getElementById("reviewBack");
  const openReportStep = document.getElementById("openReportStep");
  const skipReportStep = document.getElementById("skipReportStep");
  const reportBack = document.getElementById("reportBack");
  const finalizationWorkspace = document.getElementById("finalizationWorkspace");
  const reviewForm = document.getElementById("analysisReviewForm");
  const reviewTemplate = document.getElementById("analysisReviewTemplate");
  const reviewComment = document.getElementById("analysisReviewComment");
  const reviewStatus = document.getElementById("analysisReviewStatus");
  const reviewSubmit = document.getElementById("analysisReviewSubmit");
  const reviewBadge = document.getElementById("analysisReviewBadge");
  const reportForm = document.getElementById("analysisReportForm");
  const reportStatus = document.getElementById("analysisReportStatus");
  const reportSubmit = document.getElementById("analysisGenerateReport");
  const reportBadge = document.getElementById("analysisReportBadge");
  const reportDecision = document.getElementById("analysisReportDecision");
  const reportInterpretation = document.getElementById("analysisReportInterpretation");
  const normalControl = document.getElementById("analysisNormalControl");
  const normalControlState = document.getElementById("analysisNormalControlState");
  const existingReportActions = document.getElementById("existingReportActions");
const downloadReportButton = document.getElementById("analysisDownloadReport");
let editReportButton = null;
let isEditingFinalizedReport = false;

  const apiBaseUrl = window.GeneGlassConfig?.apiBaseUrl;
  let activeAnalysisId = null;
  let activeTrace = null;
  let chromatogramController = null;
  let latestReviewDecision = null;
  let savedReport = null;
  let currentQc = null;
  let currentTarget = null;
  let qcSaving = false;
  let modelReady = false;

  const WORKFLOW_LABELS = {
    1: "Signal & QC",
    2: "AI Result",
    3: "Specialist Decision",
    4: "PDF Report",
  };

  function showWorkflowStep(step, { focus = true } = {}) {
    const requested = Math.max(1, Math.min(4, Number(step) || 1));
    section.hidden = requested === 4 || !activeTrace;
    for (const stage of workflowStages) {
      stage.hidden = Number(stage.dataset.workflowStage) !== requested;
    }
    finalizationWorkspace.hidden = requested < 3;
    for (const indicator of workflowIndicators) {
      const indicatorStep = Number(indicator.dataset.workflowIndicator);
      indicator.classList.toggle("is-active", indicatorStep === requested);
      indicator.classList.toggle("is-complete", indicatorStep < requested);
      if (indicatorStep === requested) indicator.setAttribute("aria-current", "step");
      else indicator.removeAttribute("aria-current");
    }
    workflowProgressStatus.textContent = `Step ${requested} of 4 · ${WORKFLOW_LABELS[requested]}`;
    if (focus) {
      workflow.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  const REVIEW_NOTES = {
    not_detected: [
      "No convincing JAK2 V617F variant signal is detected at the target position.",
      "The chromatogram supports a Not Detected JAK2 V617F result.",
    ],
    heterozygous: [
      "The target peak pattern supports a Heterozygous JAK2 V617F result.",
      "Reference and variant signals are both present at the target position.",
    ],
    homozygous: [
      "The target peak pattern supports a Homozygous JAK2 V617F result.",
      "The variant signal predominates at the target position without a convincing reference peak.",
    ],
    inconclusive: [
      "The available signal is insufficient for a conclusive JAK2 V617F result.",
      "Repeat testing or additional evidence is required before final interpretation.",
    ],
  };

  const DEFAULT_INTERPRETATIONS = {
    not_detected: "JAK2 V617F was not detected in the tested specimen based on specialist review of the available technical evidence.",
    heterozygous: "A heterozygous JAK2 V617F pattern was identified in the tested specimen based on specialist review of the available technical evidence.",
    homozygous: "A homozygous JAK2 V617F pattern was identified in the tested specimen based on specialist review of the available technical evidence.",
    inconclusive: "The JAK2 V617F result is inconclusive based on the available technical evidence; repeat or additional testing is recommended.",
  };

  const REPORTABLE_DECISIONS = new Set([
    "not_detected",
    "heterozygous",
    "homozygous",
    "inconclusive",
  ]);

  function authHeaders() {
    const token = window.GeneGlassAuth?.token;
    return token ? { Authorization: `Bearer ${token}` } : null;
  }

  async function responseJson(response, fallback) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || fallback);
    return data;
  }

  function decisionLabel(decision) {
    if (decision === "not_detected") return "Not Detected";
    if (decision === "heterozygous") return "Heterozygous";
    if (decision === "homozygous") return "Homozygous";
    if (decision === "inconclusive") return "Inconclusive";
    return "Not reviewed";
  }

  function findNearbyMotif(sequence, targetBase, motif = "ACAT") {
    if (!sequence) return null;
    const normalized = sequence.toUpperCase();
    const anchor = Number.isInteger(targetBase) ? targetBase - 1 : Math.floor(normalized.length / 2);
    const from = Number.isInteger(targetBase) ? Math.max(0, anchor - 18) : 0;
    const to = Number.isInteger(targetBase) ? Math.min(normalized.length, anchor + 22) : normalized.length;
    let best = null;
    let index = normalized.indexOf(motif, from);
    while (index !== -1 && index < to) {
      const distance = Math.abs(index - anchor);
      if (!best || distance < best.distance) best = { start: index, distance };
      index = normalized.indexOf(motif, index + 1);
    }
    return best ? { startBase: best.start + 1, endBase: best.start + motif.length } : null;
  }

  function chromatogramOptions(trace, targetBase, readDirection = "Forward") {
    return {
      targetBase: Number.isInteger(targetBase) && targetBase > 0 ? targetBase : undefined,
      initialBaseCount: 9,
      initialSequence: "ACAT",
      highlightRange: findNearbyMotif(trace.sequence, targetBase, "ACAT"),
      readDirection,
      compact: true,
    };
  }

  function inspectValue(feature, value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "Unavailable";
    const number = Number(value);
    if (["peak_overlap_score", "alternative_ratio", "local_noise_ratio"].includes(feature)) {
      return `${(number * 100).toFixed(1)}%`;
    }
    if (feature === "phred_quality") return `Q${Math.round(number)}`;
    return number.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }

  function openShapInspector(explanation, trigger) {
    if (!chromatogramController?.canInspect?.() || !section?.isConnected ||
        !Array.isArray(explanation?.contributions) || !explanation.contributions.length) {
      return false;
    }
    if (document.querySelector(".gg-evidence-dialog")) return true;

    const featureData = new Map(explanation.contributions.map(item => [item.feature, item]));
    const peakFeature = featureData.get("peak_overlap_score") || featureData.get("alternative_ratio");
    const qualityFeature = featureData.get("phred_quality");
    if (!peakFeature && !qualityFeature) return false;

    const placeholder = document.createComment("GeneGlass chromatogram location");
    const originalParent = section.parentNode;
    originalParent.insertBefore(placeholder, section);

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
    subtitle.textContent = "Choose what to inspect on the original AB1 chromatogram.";
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
    viewerSlot.append(section);
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
      currentImpact.textContent = "Four related model measurements from the SAME TWO peaks";
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
      currentNote.textContent = "Phred quality describes reliability of the called base. It does not prove whether the alternative peak is a mutation or background noise.";
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
      defaultButton = addChoice("Target peak signals", "Reference, alternative and their ratios", showPeaks);
    }
    if (qualityFeature) {
      const qualityButton = addChoice("Base reading quality", inspectValue("phred_quality", qualityFeature.value), showQuality);
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
        ["local_noise_ratio", "Background noise", "Summarizes nearby background signals; no specific peak is identified as noise."],
        ["alignment_score", "Sequence alignment", "Measures sequence alignment against the reference; not an individual chromatogram peak."]
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

    dialog.addEventListener("close", () => {
      chromatogramController.clearEvidence();
      placeholder.replaceWith(section);
      dialog.remove();
      trigger?.focus();
    }, { once: true });
    dialog.addEventListener("click", event => {
      if (event.target === dialog) dialog.close();
    });
    if (typeof dialog.showModal !== "function") {
      placeholder.replaceWith(section);
      dialog.remove();
      return false;
    }

    dialog.showModal();
    defaultButton.click();
    close.focus();
    return true;
  }

  function populateReviewTemplates(decision) {
    reviewTemplate.replaceChildren(new Option("Choose a ready note or write below", ""));
    for (const note of REVIEW_NOTES[decision] || []) {
      reviewTemplate.add(new Option(note, note));
    }
  }

function setReportAvailability() {
  const decisionIsFinal = REPORTABLE_DECISIONS.has(latestReviewDecision);

  const reportIsCurrent = savedReport?.status === "finalized"
    && savedReport.final_decision === latestReviewDecision;

  const showFinalizedReportActions = reportIsCurrent && !isEditingFinalizedReport;

  const reportNeedsUpdate = savedReport?.status === "finalized"
    && decisionIsFinal
    && savedReport.final_decision !== latestReviewDecision;

  reportBadge.textContent = reportIsCurrent
    ? `Final · v${savedReport.version}`
    : reportNeedsUpdate ? "Update required" : decisionIsFinal ? "Ready" : "Locked";

  reportBadge.dataset.decision = reportIsCurrent
    ? savedReport.final_decision : (latestReviewDecision || "pending");

  reportDecision.classList.toggle("locked", !decisionIsFinal);

  reportDecision.innerHTML = reportNeedsUpdate
    ? `<i class="fa-solid fa-rotate"></i><span>The decision changed to <strong>${decisionLabel(latestReviewDecision)}</strong>. Generate a new PDF version.</span>`
    : decisionIsFinal
      ? `<i class="fa-solid fa-user-doctor"></i><span>Specialist decision: <strong>${decisionLabel(latestReviewDecision)}</strong></span>`
      : '<i class="fa-solid fa-lock"></i><span>Save the Specialist Review result first.</span>';

  reportForm.hidden = !decisionIsFinal || showFinalizedReportActions;
  existingReportActions.hidden = !showFinalizedReportActions;

  openReportStep.disabled = !decisionIsFinal;
  skipReportStep.disabled = !latestReviewDecision;

  for (const control of reportForm.elements) {
    control.disabled = !decisionIsFinal || (reportIsCurrent && !isEditingFinalizedReport);
  }

  reportSubmit.innerHTML = isEditingFinalizedReport
    ? '<i class="fa-solid fa-floppy-disk"></i> Save Changes &amp; Finalize New PDF'
    : '<i class="fa-solid fa-file-pdf"></i> Finalize &amp; Open PDF';

  if (decisionIsFinal) {
    const defaults = Object.values(DEFAULT_INTERPRETATIONS);

    if (!reportInterpretation.value.trim() || defaults.includes(reportInterpretation.value.trim())) {
      reportInterpretation.value = DEFAULT_INTERPRETATIONS[latestReviewDecision];
    }
  }
}

  function populateReportDraft(report) {
    if (!report) return;
    const values = {
      patient_name: report.patient_name,
      medical_record_number: report.medical_record_number,
      gender: report.gender,
      date_of_birth: report.date_of_birth,
      physician_name: report.physician_name,
      report_number: report.report_number,
      received_date: report.received_date,
      submitted_date: report.submitted_date,
      specimen_type: report.specimen_type,
      clinical_history: report.clinical_history,
      interpretation: report.interpretation,
    };
    for (const [name, value] of Object.entries(values)) {
      const control = reportForm.elements.namedItem(name);
      if (control && value != null) control.value = value;
    }
    normalControlState.textContent = report.normal_control_uploaded
      ? "A normal-control AB1 is already saved. Choose another file only to replace it."
      : "Upload the control used for this case.";
  }

  async function loadWorkflowState(analysisId) {
    const headers = authHeaders();
    if (!headers) return;
    const [reviewsResponse, reportResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/analyses/${analysisId}/reviews`, { headers }),
      fetch(`${apiBaseUrl}/analyses/${analysisId}/report`, { headers }),
    ]);
    const reviews = await responseJson(reviewsResponse, "Specialist Review could not be loaded.");
    const reportData = await responseJson(reportResponse, "Report information could not be loaded.");
    latestReviewDecision = reviews.latest_decision || null;
    savedReport = reportData.report;
    reviewBadge.textContent = decisionLabel(latestReviewDecision);
    reviewBadge.dataset.decision = latestReviewDecision || "pending";
    const currentChoice = reviewForm.querySelector(`input[value="${latestReviewDecision}"]`);
    if (currentChoice) currentChoice.checked = true;
    populateReviewTemplates(latestReviewDecision);
    populateReportDraft(savedReport);
    setReportAvailability();
  }

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    const valid = !!file && /\.ab1$/i.test(file.name);
    fileInfo.textContent = valid ? `Selected: ${file.name}` : (file ? "Please select a .ab1 file." : "No file selected");
    button.disabled = !valid;
    message.textContent = "";
  });

  function renderAiResult(data) {
    document.getElementById("analysisAiResult")?.remove();
    const panel = document.createElement("section");
    panel.id = "analysisAiResult";
    panel.className = "dashboard-card analysis-ai-result";
    panel.setAttribute("aria-live", "polite");
    const title = document.createElement("h3");
    title.textContent = "AI Prediction — JAK2 V617F";
    panel.append(title);
    const status = String(data?.status || "Needs Review");
    const needsReview = status.toLowerCase() === "needs review";
    const state = document.createElement("strong");
    state.className = `analysis-ai-status ${needsReview ? "review" : status.toLowerCase() === "hetero" ? "hetero" : "negative"}`;
    state.textContent = needsReview ? "Needs Review" : status;
    panel.append(state);
    const summary = document.createElement("p");
    summary.textContent = needsReview
      ? "This analysis needs specialist review; a definitive classification is not provided."
      : status.toLowerCase() === "hetero"
        ? "The binary research model favors a heterozygous pattern."
        : "The binary research model favors a negative pattern.";
    panel.append(summary);
    if (data?.reason) {
      const reason = document.createElement("p");
      reason.className = "analysis-ai-reason";
      reason.textContent = `Review reason: ${data.reason}`;
      panel.append(reason);
    }
    const probs = data?.probabilities;
    if (probs && Number.isFinite(Number(probs.negative)) && Number.isFinite(Number(probs.hetero))) {
      const metrics = document.createElement("div");
      metrics.className = "analysis-ai-metrics";
      for (const [key, name] of [["negative", "Negative"], ["hetero", "Heterozygous"]]) {
        const value = Math.max(0, Math.min(1, Number(probs[key])));
        const metric = document.createElement("div");
        const heading = document.createElement("div");
        heading.className = "analysis-ai-metric-label";
        const nameNode = document.createElement("span");
        nameNode.textContent = name;
        const valueNode = document.createElement("strong");
        valueNode.textContent = `${(value * 100).toFixed(1)}%`;
        heading.append(nameNode, valueNode);
        const bar = document.createElement("div");
        bar.className = "analysis-ai-meter";
        const fill = document.createElement("div");
        fill.className = `analysis-ai-fill ${key}`;
        fill.style.width = `${value * 100}%`;
        bar.append(fill);
        metric.append(heading, bar);
        metrics.append(metric);
      }
      panel.append(metrics);
    }
    const explanation = window.GeneGlassShapExplanation?.create(
      data?.explanation,
      (shapData, trigger) => openShapInspector(shapData, trigger)
    );
    if (explanation) panel.append(explanation);
    // The chromatogram already marks the mapped target with targetBase.
    aiResultMount.replaceChildren(panel);
    modelReady = true;
    modelNext.disabled = false;
  }


  function qcMetric(label, value) {
    const item = document.createElement("div");
    item.className = "initial-qc-metric";
    const name = document.createElement("span");
    name.textContent = label;
    const data = document.createElement("strong");
    data.textContent = value == null || value === "" ? "N/A" : String(value);
    item.append(name, data);
    initialQcMetrics.append(item);
  }

  function showQcState(qc, details, targetResult, targetLoadError = null) {
    currentQc = qc;
    const mapped = qc.target_found === true;
    // Do not enable continuation if the target evidence could not be retrieved.
    const readableTarget = mapped && targetResult?.found === true;
    initialQcCard.hidden = false;
    initialQcBadge.dataset.state = !mapped ? "target_not_found" : qc.decision;
    initialQcBadge.textContent = !mapped ? "Target Not Found"
      : qc.decision === "continue_analysis" ? "Continue approved"
      : qc.decision === "request_repeat" ? "Repeat requested" : "Pending specialist decision";
    initialQcTarget.dataset.state = readableTarget ? "found" : "missing";
    initialQcTarget.textContent = !mapped
      ? "Target Not Found — JAK2 V617F could not be reliably located; AI classification is blocked."
      : !readableTarget
        ? `Target evidence unavailable — ${targetLoadError || "check target mapping before continuing"}.`
        : "Target Found — examine signal quality before authorizing AI analysis.";

    initialQcMetrics.replaceChildren();
    const quality = details.quality_control || {};
    qcMetric("Preliminary quality indicator", String(quality.quality_assessment || "unavailable").replaceAll("_", " "));
    qcMetric("Average Phred", Number.isFinite(Number(quality.average_quality)) && quality.average_quality != null
      ? Number(quality.average_quality).toFixed(1) : "N/A");
    qcMetric("Low-quality bases", quality.low_quality_percentage != null
      ? `${Number(quality.low_quality_percentage).toFixed(1)}%` : "N/A");
    qcMetric("Retained bases", quality.retained_percentage != null
      ? `${Number(quality.retained_percentage).toFixed(1)}%` : "N/A");
    const noise = targetResult?.noise_assessment;
    if (noise?.available === true) {
      qcMetric("Lowest neighboring Phred", noise.min_flank_phred != null ? `Q${noise.min_flank_phred}` : "N/A");
      qcMetric("Mean secondary/primary peak", noise.mean_flank_secondary_ratio != null
        ? Number(noise.mean_flank_secondary_ratio).toFixed(3) : "N/A");
    }
    initialQcComment.value = qc.comment || "";
    const repeatRequested = qc.decision === "request_repeat";
    initialQcContinue.disabled = !readableTarget;
    initialQcRepeat.disabled = repeatRequested;
    initialQcRepeat.title = repeatRequested ? "Repeat request already saved" : "Request another sequencing run";
    initialQcRepeatConfirmation.hidden = !repeatRequested;
    initialQcMessage.textContent = qc.decision === "continue_analysis"
      ? "Specialist permission is recorded. Research-only AI analysis may run."
      : repeatRequested
        ? "QC decision recorded in the audit trail."
        : "";
    if (qc.decision === "pending" && details.ai_prediction && readableTarget) {
      initialQcMessage.textContent = "Historical AI result detected (created before the QC approval step). A new AI run still requires your decision.";
    }
  }

  function renderAiNotice(title, content) {
    document.getElementById("analysisAiResult")?.remove();
    const panel = document.createElement("section");
    panel.className = "dashboard-card analysis-ai-result";
    panel.id = "analysisAiResult";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const note = document.createElement("p");
    note.textContent = content;
    panel.append(heading, note);
    aiResultMount.replaceChildren(panel);
    modelReady = false;
    modelNext.disabled = true;
  }

  async function saveQcChoice(decision) {
    if (!activeAnalysisId || !currentQc || qcSaving) return;
    // Prevent duplicate repeat requests from repeated clicks.
    if (decision === "request_repeat" && currentQc.decision === "request_repeat") return;
    const mapped = currentQc.target_found === true && currentTarget?.found === true;
    if (decision === "continue_analysis" && !mapped) {
      initialQcMessage.textContent = "Target Not Found or mapping unavailable. AI analysis cannot continue.";
      return;
    }
    const comment = initialQcComment.value.trim();
    const needsReason = decision === "request_repeat"
      || (decision === "continue_analysis" && currentQc.preliminary_qc_status !== "passed");
    if (needsReason && !comment) {
      initialQcMessage.textContent = "Enter a specialist reason before saving this decision.";
      initialQcComment.focus();
      return;
    }
    qcSaving = true;
    initialQcContinue.disabled = true;
    initialQcRepeat.disabled = true;
    initialQcMessage.textContent = "Saving specialist QC decision...";
    try {
      const response = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/preliminary-qc-decision`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ decision, comment }),
      });
      await responseJson(response, "Could not save the QC decision.");
      // The refreshed QC state displays a persistent confirmation for repeat requests.
      await loadAnalysis(activeAnalysisId, null, decision === "continue_analysis" ? 2 : 1);
      if (decision === "continue_analysis") {
        initialQcMessage.textContent = "QC approval saved.";
      }
    } catch (error) {
      initialQcMessage.textContent = error.message || "Could not save the QC decision.";
      initialQcContinue.disabled = !(currentQc.target_found === true && currentTarget?.found === true);
      initialQcRepeat.disabled = currentQc.decision === "request_repeat";
    } finally {
      qcSaving = false;
    }
  }

  async function loadAnalysis(analysisId, uploadResult = null, requestedStep = 1) {
    const headers = authHeaders();
    if (!headers || !apiBaseUrl) throw new Error("Please sign in again; API configuration is unavailable.");
    activeAnalysisId = Number(analysisId);
    activeTrace = null;
    workflow.hidden = false;
    showWorkflowStep(1, { focus: false });
    modelReady = false;
    modelNext.disabled = true;
    const [detailsResponse, traceResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}`, { headers }),
      fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/chromatogram`, { headers }),
    ]);
    const details = await responseJson(detailsResponse, "Analysis could not be loaded.");
    activeTrace = await responseJson(traceResponse, "Chromatogram could not be loaded.");
    section.hidden = false;
    uploadCard.hidden = true;
    finalizationWorkspace.hidden = true;
    document.getElementById("analysisAiResult")?.remove();
    document.getElementById("jak2TargetError")?.remove();
    chromatogramController = window.GeneGlassChromatogram.render(activeTrace, chromatogramOptions(activeTrace));

    let targetResult = null;
    let targetLoadError = null;
    try {
      const targetResponse = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/jak2-target`, { headers });
      const targetData = await responseJson(targetResponse, "Target analysis unavailable.");
      targetResult = targetData.result || null;
      const targetBase = Number(targetResult?.ab1_base_number);
      chromatogramController = window.GeneGlassChromatogram.render(
        activeTrace,
        chromatogramOptions(activeTrace, targetBase, targetResult?.direction || "Forward"),
      );
    } catch (error) {
      targetLoadError = error.message || "Target evidence unavailable";
    }
    currentTarget = targetResult;

    const qcResponse = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/preliminary-qc-decision`, { headers });
    const qc = await responseJson(qcResponse, "Preliminary QC decision could not be loaded.");
    showQcState(qc, details, targetResult, targetLoadError);
    // Repeat decisions are communicated by the QC confirmation instead of an extra AI card.
    if (qc.decision === "request_repeat") {
      showWorkflowStep(1, { focus: requestedStep !== 1 });
      return;
    }
    if (qc.target_found !== true) {
      renderAiNotice("Target Not Found", "JAK2 V617F could not be mapped. A Negative/Hetero result cannot be generated.");
      showWorkflowStep(1, { focus: false });
      return;
    }
    if (targetResult?.found !== true) {
      renderAiNotice("Target evidence unavailable", "The mapped target could not be inspected. AI classification remains unavailable.");
      showWorkflowStep(1, { focus: false });
      return;
    }
    const historical = qc.decision === "pending" && Boolean(details.ai_prediction);
    if (qc.decision !== "continue_analysis" && !historical) {
      renderAiNotice("Awaiting Initial QC Decision", "Review the original signal above, then select Continue Analysis or Request Repeat.");
      showWorkflowStep(1, { focus: false });
      return;
    }

    try {
      let prediction = qc.decision === "continue_analysis" ? uploadResult?.ai_prediction : null;
      if (!prediction) {
        const predictionResponse = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/ai-prediction`, { headers });
        prediction = await responseJson(predictionResponse, "AI prediction is unavailable.");
      }
      renderAiResult(prediction);
      if (historical) {
        const note = document.createElement("p");
        note.className = "analysis-ai-disclaimer";
        note.textContent = "Historical model output — saved before the Initial QC approval workflow. No new model run is permitted until specialist approval.";
        document.getElementById("analysisAiResult").append(note);
      }
    } catch (error) {
      renderAiNotice("AI prediction unavailable", error.message || "Model output could not be loaded.");
      showWorkflowStep(qc.decision === "continue_analysis" ? 2 : 1, { focus: false });
      return;
    }
    if (qc.decision === "continue_analysis") {
      await loadWorkflowState(activeAnalysisId);
    }
    showWorkflowStep(requestedStep, { focus: requestedStep !== 1 });
  }

  async function saveReview(event) {
    event.preventDefault();
    if (!activeAnalysisId) return;
    const headers = authHeaders();
    const choice = reviewForm.querySelector('input[name="reviewDecision"]:checked');
    const comment = reviewComment.value.trim();
    if (!choice || comment.length < 3) {
      reviewStatus.textContent = "Choose a decision and add a short review note.";
      return;
    }
    reviewSubmit.disabled = true;
    reviewStatus.textContent = "Saving decision...";
    try {
      const response = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/reviews`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ decision: choice.value, comment }),
      });
      await responseJson(response, "The specialist decision could not be saved.");
      reviewStatus.textContent = "Decision saved in the audit history.";
      await loadWorkflowState(activeAnalysisId);
    } catch (error) {
      reviewStatus.textContent = error.message;
    } finally {
      reviewSubmit.disabled = false;
    }
  }

  async function downloadSavedReport() {
    if (!activeAnalysisId || !savedReport?.download_url) return;
    const previewWindow = window.open("", "_blank");
    downloadReportButton.disabled = true;
    try {
      const response = await fetch(
        `${apiBaseUrl}/analyses/${activeAnalysisId}/report.pdf?version=${savedReport.version}`,
        { headers: authHeaders() },
      );
      if (!response.ok) throw new Error("The saved PDF could not be downloaded.");
      const pdfUrl = URL.createObjectURL(await response.blob());
      if (previewWindow) {
        previewWindow.opener = null;
        previewWindow.location.href = pdfUrl;
      }
      window.setTimeout(() => URL.revokeObjectURL(pdfUrl), 60000);
    } catch (error) {
      if (previewWindow) previewWindow.close();
      reportStatus.textContent = error.message;
    } finally {
      downloadReportButton.disabled = false;
    }
  }

function editSavedReport() {
  if (!savedReport || savedReport.status !== "finalized") return;

  isEditingFinalizedReport = true;

  populateReportDraft(savedReport);
  setReportAvailability();

  reportStatus.textContent =
    "Editing a new version. The previously finalized PDF will remain unchanged.";

  reportForm.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}

  async function createReport(event) {
    event.preventDefault();
    if (!activeAnalysisId || !REPORTABLE_DECISIONS.has(latestReviewDecision)) return;
    if (!reportForm.reportValidity()) return;
    const previewWindow = window.open("", "_blank");
    reportSubmit.disabled = true;
    reportStatus.textContent = "Saving and finalizing report...";
    try {
      const form = new FormData(reportForm);
      if (!normalControl.files?.[0]) form.delete("normal_control");
      const saveResponse = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/report`, {
        method: "PUT",
        headers: authHeaders(),
        body: form,
      });
      const saved = await responseJson(saveResponse, "The report draft could not be saved.");
      const finalizeResponse = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/report/finalize`, {
        method: "POST",
        headers: authHeaders(),
      });
      const finalized = await responseJson(finalizeResponse, "The report could not be finalized.");
      savedReport = finalized.report || saved.report;
      isEditingFinalizedReport = false;
      reportStatus.textContent = "Final report saved. Opening PDF...";
      setReportAvailability();
      const pdfResponse = await fetch(
        `${apiBaseUrl}/analyses/${activeAnalysisId}/report.pdf?version=${savedReport.version}`,
        { headers: authHeaders() },
      );
      if (!pdfResponse.ok) throw new Error("The report was saved, but the PDF preview could not be opened.");
      const pdfUrl = URL.createObjectURL(await pdfResponse.blob());
      if (previewWindow) {
        previewWindow.opener = null;
        previewWindow.location.href = pdfUrl;
      }
      window.setTimeout(() => URL.revokeObjectURL(pdfUrl), 60000);
    } catch (error) {
      if (previewWindow) previewWindow.close();
      reportStatus.textContent = error.message;
    } finally {
      reportSubmit.disabled = false;
    }
  }

  button.addEventListener("click", async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    const headers = authHeaders();
    if (!headers || !apiBaseUrl) {
      message.textContent = "Please sign in again; API configuration is unavailable.";
      return;
    }
    button.disabled = true;
    message.textContent = "Analyzing file...";
    section.hidden = true;
    workflow.hidden = true;
    initialQcCard.hidden = true;
    finalizationWorkspace.hidden = true;
    document.getElementById("jak2TargetError")?.remove();
    document.getElementById("analysisAiResult")?.remove();
    try {
      const form = new FormData();
      form.append("file", file);
      const upload = await fetch(`${apiBaseUrl}/analyses`, { method: "POST", headers, body: form });
      const data = await responseJson(upload, "Upload failed.");
      window.history.replaceState(null, "", `?id=${data.id}`);
      await loadAnalysis(data.id, data);
      message.textContent = "";
    } catch (error) {
      message.textContent = error.message || "Analysis failed.";
    } finally {
      button.disabled = false;
    }
  });

  initialQcContinue.addEventListener("click", () => {
    if (currentQc?.decision === "continue_analysis") {
      showWorkflowStep(2);
      return;
    }
    saveQcChoice("continue_analysis");
  });
  initialQcRepeat.addEventListener("click", () => saveQcChoice("request_repeat"));
  modelBack.addEventListener("click", () => showWorkflowStep(1));
  modelNext.addEventListener("click", () => {
    if (modelReady) showWorkflowStep(3);
  });
  reviewBack.addEventListener("click", () => showWorkflowStep(2));
  openReportStep.addEventListener("click", () => {
    if (REPORTABLE_DECISIONS.has(latestReviewDecision)) showWorkflowStep(4);
  });
  skipReportStep.addEventListener("click", () => {
    if (!latestReviewDecision) return;
    window.location.href = "../HistoryPage/history.html";
  });
  reportBack.addEventListener("click", () => showWorkflowStep(3));

  reviewForm.addEventListener("change", (event) => {
    if (event.target.name === "reviewDecision") populateReviewTemplates(event.target.value);
  });
  reviewTemplate.addEventListener("change", () => {
    if (reviewTemplate.value) reviewComment.value = reviewTemplate.value;
  });
  normalControl.addEventListener("change", () => {
    normalControlState.textContent = normalControl.files?.[0]
      ? `Selected: ${normalControl.files[0].name}`
      : "Upload the control used for this case.";
  });
  reviewForm.addEventListener("submit", saveReview);
  reportForm.addEventListener("submit", createReport);
  downloadReportButton.addEventListener("click", downloadSavedReport);
  editReportButton = document.createElement("button");
editReportButton.type = "button";
editReportButton.id = "analysisEditReport";
editReportButton.className = downloadReportButton.className;
editReportButton.innerHTML =
  '<i class="fa-solid fa-pen-to-square"></i> Edit Report';

editReportButton.addEventListener("click", editSavedReport);

existingReportActions.appendChild(editReportButton);


async function resumeFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const analysisId = Number(params.get("id"));
  const editReport = params.get("editReport") === "1";
  const openReport = params.get("report") === "1";

  if (
    !Number.isInteger(analysisId) ||
    analysisId <= 0 ||
    !window.GeneGlassAuth?.token
  ) {
    return;
  }

  message.textContent = "Loading saved analysis...";

  try {
    await loadAnalysis(analysisId, null, editReport || openReport ? 4 : 1);

    if (editReport) {
      if (
        !savedReport ||
        savedReport.status !== "finalized" ||
        !REPORTABLE_DECISIONS.has(latestReviewDecision)
      ) {
        throw new Error("A finalized report is not available for editing.");
      }

      isEditingFinalizedReport = true;

      populateReportDraft(savedReport);
      setReportAvailability();

      reportStatus.textContent =
        "Editing a new version. The previously finalized PDF will remain unchanged.";

      showWorkflowStep(4);
      reportForm.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    } else if (openReport && modelReady) {
      if (REPORTABLE_DECISIONS.has(latestReviewDecision)) {
        showWorkflowStep(4);
        reportForm.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
      } else {
        showWorkflowStep(3);
        reviewStatus.textContent = "Save the Specialist Review result before generating the PDF.";
        reviewForm.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
      }
    }

    message.textContent = "";
  } catch (error) {
    message.textContent = error.message;
    uploadCard.hidden = false;
  }
}

document.addEventListener("geneglass:auth-ready", resumeFromUrl);

if (window.GeneGlassAuth?.token) {
  resumeFromUrl();
}

})();
