(() => {
  const fileInput = document.getElementById("ab1");
  const fileInfo = document.getElementById("fileInfo");
  const button = document.getElementById("analyze");
  const message = document.getElementById("message");
  const section = document.getElementById("chromatogramSection");
  const uploadCard = document.querySelector(".upload-card");
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

  const apiBaseUrl = window.GeneGlassConfig?.apiBaseUrl;
  let activeAnalysisId = null;
  let activeTrace = null;
  let latestReviewDecision = null;
  let savedReport = null;

  const REVIEW_NOTES = {
    positive: [
      "The chromatogram supports a Positive JAK2 V617F result.",
      "The target peak pattern is consistent with a Positive JAK2 V617F result.",
    ],
    negative: [
      "The chromatogram supports a Negative JAK2 V617F result.",
      "No convincing variant peak is present at the JAK2 V617F target.",
    ],
    needs_more_data: [
      "Repeat testing is required because the target signal is inconclusive.",
      "A new specimen or sequencing run is required for confirmation.",
    ],
  };

  const DEFAULT_INTERPRETATIONS = {
    positive: "JAK2 V617F was detected in the tested specimen based on specialist review of the available technical evidence.",
    negative: "JAK2 V617F was not detected in the tested specimen based on specialist review of the available technical evidence.",
  };

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
    if (decision === "positive") return "Positive";
    if (decision === "negative") return "Negative";
    if (decision === "needs_more_data") return "More data requested";
    return "Not reviewed";
  }

  function populateReviewTemplates(decision) {
    reviewTemplate.replaceChildren(new Option("Choose a ready note or write below", ""));
    for (const note of REVIEW_NOTES[decision] || []) {
      reviewTemplate.add(new Option(note, note));
    }
  }

  function setReportAvailability() {
    const decisionIsFinal = ["positive", "negative"].includes(latestReviewDecision);
    const finalized = savedReport?.status === "finalized";
    reportBadge.textContent = finalized
      ? `Final · v${savedReport.version}`
      : decisionIsFinal ? "Ready" : "Locked";
    reportBadge.dataset.decision = finalized
      ? savedReport.final_decision : (latestReviewDecision || "pending");
    reportDecision.classList.toggle("locked", !decisionIsFinal);
    reportDecision.innerHTML = decisionIsFinal
      ? `<i class="fa-solid fa-user-doctor"></i><span>Specialist decision: <strong>${decisionLabel(latestReviewDecision)}</strong></span>`
      : '<i class="fa-solid fa-lock"></i><span>Save a Positive or Negative Specialist Review first.</span>';
    reportForm.hidden = finalized;
    existingReportActions.hidden = !finalized;
    for (const control of reportForm.elements) {
      control.disabled = !decisionIsFinal || finalized;
    }
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
    finalizationWorkspace.hidden = false;
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

  function makeGeneGlassNoiseNotice(noise) {
    const node = document.createElement("section");
    node.className = "geneglass-noise-notice";
    node.style.cssText = "border:1px solid #b8dfe2;border-radius:12px;padding:15px 18px;margin:14px 0;background:#f6fbfc;color:#183e43;";
    const heading = document.createElement("strong");
    heading.textContent = "Signal Quality — Target Region (Research Only)";
    node.append(heading);
    const text = document.createElement("p");
    text.style.margin = "9px 0 0";
    if (!noise || noise.available !== true) {
      text.textContent = "Local signal measurements unavailable. Specialist should inspect the original chromatogram.";
    } else {
      const lowQ = Number.isFinite(Number(noise.min_flank_phred)) && Number(noise.min_flank_phred) < 20;
      const ratio = noise.mean_flank_secondary_ratio == null
        ? "N/A" : Number(noise.mean_flank_secondary_ratio).toFixed(3);
      const q = noise.min_flank_phred == null ? "N/A" : String(noise.min_flank_phred);
      text.textContent = `Bases ${noise.window_start_ab1_base_number}–${noise.window_end_ab1_base_number}: lowest neighboring Phred Q${q}; mean neighboring secondary/primary peak ratio ${ratio}. `
        + (lowQ ? "Some neighboring base calls are below the provisional Q20 quality threshold. Inspect the original peaks." : "Measurements shown for specialist inspection; these numbers alone do not confirm clean or noisy signal.")
        + " AI classification and existing QC status are unchanged.";
    }
    node.append(text);
    return node;
  }

  function showTarget(data) {
    document.getElementById("jak2ResultsPanel")?.remove();
    const result = data.result || {};
    const panel = document.createElement("section");
    panel.id = "jak2ResultsPanel";
    panel.className = "dashboard-card";
    const title = document.createElement("h3");
    title.textContent = "JAK2 V617F — Target Analysis";
    const text = document.createElement("p");
    text.textContent = result.ab1_base_number
      ? `Target location: AB1 base ${result.ab1_base_number} (${result.direction || "Unknown"} direction). Preliminary analysis only; mutation status is not determined until model validation.`
      : "Target location could not be determined.";
    panel.append(title, text);

    const reasons = Array.isArray(result.review_reasons)
      ? result.review_reasons.filter(reason => typeof reason === "string" && reason.trim())
      : [];
    if (!result.found && reasons.length === 0) {
      reasons.push(result.reason || "Target position could not be mapped.");
    }
    const requiresReview = result.needs_review === true || !result.found || reasons.length > 0;
    const status = document.createElement("p");
    status.style.fontWeight = "700";
    status.style.color = requiresReview ? "#9a5b14" : "#167b72";
    status.textContent = requiresReview ? "Review Status: Needs Review" : "Review Status: No QC Review Flag";
    panel.append(status);
    panel.append(makeGeneGlassNoiseNotice(result.noise_assessment));

    if (requiresReview) {
      const explanation = document.createElement("p");
      explanation.textContent = reasons.length
        ? `Reason${reasons.length > 1 ? "s" : ""}: ${reasons.join("; ")}`
        : "Review required; the backend did not provide a specific reason.";
      panel.append(explanation);
    } else {
      const explanation = document.createElement("p");
      explanation.textContent = "No preliminary review issues detected. This does not confirm a normal result.";
      panel.append(explanation);
    }

    const reference = result.reference_evidence;
    if (reference?.url) {
      const referenceLink = document.createElement("a");
      referenceLink.href = reference.url;
      referenceLink.target = "_blank";
      referenceLink.rel = "noopener noreferrer";
      referenceLink.textContent = `${reference.source || "ClinVar"}: ${reference.transcript || "JAK2"}:${reference.hgvs_c || "c.1849G>T"}`;
      const referenceNote = document.createElement("p");
      referenceNote.append("Reference evidence: ", referenceLink, ". This link does not replace specialist review.");
      panel.append(referenceNote);
    }
    section.after(panel);
  }

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
    const meta = document.createElement("p");
    meta.className = "analysis-ai-metadata";
    meta.textContent = `Model: ${data?.model_name || "GeneGlass"} · Version: ${data?.model_version || "Unavailable"} · Orientation: ${data?.orientation || "Unavailable"}`;
    panel.append(meta);
    const notice = document.createElement("p");
    notice.className = "analysis-ai-disclaimer";
    notice.textContent = "Research use only; not a clinical diagnosis. The model was trained on Negative and Hetero, not Homo or Noise. These scores are not clinical certainty.";
    panel.append(notice);
    // The chromatogram already marks the mapped target with targetBase.
    section.insertAdjacentElement("afterend", panel);
  }

  async function loadAnalysis(analysisId, uploadResult = null) {
    const headers = authHeaders();
    if (!headers || !apiBaseUrl) throw new Error("Please sign in again; API configuration is unavailable.");
    activeAnalysisId = Number(analysisId);
    const [detailsResponse, traceResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}`, { headers }),
      fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/chromatogram`, { headers }),
    ]);
    await responseJson(detailsResponse, "Analysis could not be loaded.");
    activeTrace = await responseJson(traceResponse, "Chromatogram could not be loaded.");
    section.hidden = false;
    uploadCard.hidden = true;
    window.GeneGlassChromatogram.render(activeTrace);

    try {
      const targetResponse = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/jak2-target`, { headers });
      const targetData = await responseJson(targetResponse, "Target analysis unavailable.");
      showTarget(targetData);
      const targetBase = Number(targetData.result?.ab1_base_number);
      if (Number.isInteger(targetBase) && targetBase > 0) {
        window.GeneGlassChromatogram.render(activeTrace, { targetBase });
      }
    } catch (error) {
      const note = document.createElement("p");
      note.id = "jak2TargetError";
      note.textContent = "JAK2 target analysis unavailable. No mutation conclusion can be made.";
      section.after(note);
    }

    try {
      let prediction = uploadResult?.ai_prediction;
      if (!prediction) {
        const predictionResponse = await fetch(`${apiBaseUrl}/analyses/${activeAnalysisId}/ai-prediction`, { headers });
        prediction = await responseJson(predictionResponse, "AI prediction is unavailable.");
      }
      renderAiResult(prediction);
    } catch (error) {
      renderAiResult({ status: "Needs Review", reason: `AI result unavailable: ${error.message || "Unknown error"}` });
    }
    await loadWorkflowState(activeAnalysisId);
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

  async function createReport(event) {
    event.preventDefault();
    if (!activeAnalysisId || !["positive", "negative"].includes(latestReviewDecision)) return;
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
    document.getElementById("jak2ResultsPanel")?.remove();
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

  async function resumeFromUrl() {
    const analysisId = Number(new URLSearchParams(window.location.search).get("id"));
    if (!Number.isInteger(analysisId) || analysisId <= 0 || !window.GeneGlassAuth?.token) return;
    message.textContent = "Loading saved analysis...";
    try {
      await loadAnalysis(analysisId);
      message.textContent = "";
    } catch (error) {
      message.textContent = error.message;
      uploadCard.hidden = false;
    }
  }

  document.addEventListener("geneglass:auth-ready", resumeFromUrl);
  if (window.GeneGlassAuth?.token) resumeFromUrl();
})();
