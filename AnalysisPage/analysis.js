(() => {
  const fileInput = document.getElementById("ab1");
  const fileInfo = document.getElementById("fileInfo");
  const button = document.getElementById("analyze");
  const message = document.getElementById("message");
  const section = document.getElementById("chromatogramSection");

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

  button.addEventListener("click", async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    const token = window.GeneGlassAuth?.token;
    const base = window.GeneGlassConfig?.apiBaseUrl;
    if (!token || !base) {
      message.textContent = "Please sign in again; API configuration is unavailable.";
      return;
    }
    button.disabled = true;
    message.textContent = "Analyzing file...";
    section.hidden = true;
    document.getElementById("jak2ResultsPanel")?.remove();
    document.getElementById("jak2TargetError")?.remove();
    document.getElementById("analysisAiResult")?.remove();
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const form = new FormData();
      form.append("file", file);
      const upload = await fetch(`${base}/analyses`, { method: "POST", headers, body: form });
      const data = await upload.json();
      if (!upload.ok) throw new Error(data.detail || "Upload failed.");
      const traceResponse = await fetch(`${base}/analyses/${data.id}/chromatogram`, { headers });
      if (!traceResponse.ok) throw new Error("Chromatogram could not be loaded.");
      const trace = await traceResponse.json();
      window.GeneGlassChromatogram.render(trace);
      document.querySelector(".upload-card").hidden = true;
      message.textContent = "";
      try {
        const targetResponse = await fetch(`${base}/analyses/${data.id}/jak2-target`, { headers });
        if (!targetResponse.ok) throw new Error("Target analysis unavailable.");
        const targetData = await targetResponse.json();
        showTarget(targetData);
        const targetBase = Number(targetData.result?.ab1_base_number);
        if (Number.isInteger(targetBase) && targetBase > 0) {
          window.GeneGlassChromatogram.render(trace, { targetBase });
        }
      } catch (error) {
        const note = document.createElement("p");
        note.id = "jak2TargetError";
        note.textContent = "JAK2 target analysis unavailable. No mutation conclusion can be made.";
        section.after(note);
      }
      try {
        let prediction = data.ai_prediction;
        if (!prediction) {
          const response = await fetch(`${base}/analyses/${data.id}/ai-prediction`, { headers });
          if (!response.ok) throw new Error("AI prediction is unavailable.");
          prediction = await response.json();
        }
        renderAiResult(prediction);
      } catch (error) {
        renderAiResult({ status: "Needs Review", reason: `AI result unavailable: ${error.message || "Unknown error"}` });
      }
    } catch (error) {
      message.textContent = error.message || "Analysis failed.";
    } finally {
      button.disabled = false;
    }
  });
})();
