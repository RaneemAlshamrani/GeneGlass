(function () {
  const FEATURE_LABELS = Object.freeze({
    alignment_score: "Sequence match to reference",
    reference_peak: "Reference peak (original signal)",
    alternative_peak: "Alternative peak (other signal)",
    alternative_ratio: "Alternative signal percentage",
    phred_quality: "Base reading quality",
    peak_overlap_score: "Overlapping signal peaks",
    local_noise_ratio: "Background signal noise",
  });

  function percent(value) {
    return Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(1)}%` : "N/A";
  }

  function featureValue(feature, value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "Unavailable";
    const n = Number(value);
    if (["alternative_ratio", "peak_overlap_score", "local_noise_ratio"].includes(feature)) {
      return percent(n);
    }
    if (feature === "phred_quality") return `Q${Math.round(n)}`;
    return n.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }

  function create(explanation, onInspect = null) {
    if (!explanation || explanation.available !== true) return null;
    const contributions = Array.isArray(explanation.contributions)
      ? explanation.contributions : [];
    if (!contributions.length) return null;

    const disclosure = document.createElement("details");
    disclosure.className = "shap-explanation";
    const summary = document.createElement("summary");
    const title = document.createElement("span");
    title.className = "shap-summary-title";
    const icon = document.createElement("i");
    icon.className = "fa-solid fa-chart-bar";
    icon.setAttribute("aria-hidden", "true");
    const text = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = "Why did the model produce this result?";
    const small = document.createElement("small");
    small.textContent = "Understand the AI estimate; inspect the actual signals only when needed";
    text.append(strong, small);
    title.append(icon, text);
    const badge = document.createElement("span");
    badge.className = "shap-method-badge";
    badge.textContent = explanation.method || "SHAP";
    summary.append(title, badge);

    const body = document.createElement("div");
    body.className = "shap-explanation-body";
    const overview = document.createElement("p");
    overview.className = "shap-overview";
    overview.textContent = `Model's Heterozygous estimate: ${percent(explanation.output_value)}. The bars below explain the estimate, not a confirmed mutation.`;
    body.appendChild(overview);

    if (typeof onInspect === "function") {
      const action = document.createElement("div");
      action.className = "gg-inspect-action";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "gg-open-inspector";
      button.textContent = "Inspect evidence on chromatogram";
      const state = document.createElement("span");
      state.className = "gg-inspect-action-status";
      state.setAttribute("role", "status");
      button.addEventListener("click", () => {
        state.textContent = onInspect(explanation, button) === false
          ? "Chromatogram or mapped target is not available for inspection."
          : "";
      });
      action.append(button, state);
      body.append(action);
    }

    const maxImpact = Math.max(
      ...contributions.map((item) => Math.abs(Number(item.impact) || 0)), 0.000001
    );
    const list = document.createElement("div");
    list.className = "shap-contribution-list";
    for (const item of contributions) {
      const impact = Number(item.impact) || 0;
      const row = document.createElement("div");
      row.className = "shap-contribution";
      row.dataset.direction = impact >= 0 ? "hetero" : "negative";
      const label = document.createElement("div");
      label.className = "shap-feature-label";
      const name = document.createElement("strong");
      name.textContent = FEATURE_LABELS[item.feature] || item.feature;
      const value = document.createElement("small");
      value.textContent = `Measured: ${featureValue(item.feature, item.value)}`;
      label.append(name, value);

      const track = document.createElement("div");
      track.className = "shap-impact-track";
      const fill = document.createElement("span");
      fill.className = "shap-impact-fill";
      fill.style.width = `${Math.max(2, Math.abs(impact) / maxImpact * 50)}%`;
      track.appendChild(fill);
      const result = document.createElement("div");
      result.className = "shap-impact-value";
      const points = document.createElement("strong");
      points.textContent = `${Math.abs(impact * 100).toFixed(1)} points`;
      const direction = document.createElement("small");
      direction.textContent = impact >= 0 ? "Raises Heterozygous estimate" : "Lowers Heterozygous estimate";
      result.append(points, direction);
      row.append(label, track, result);
      list.appendChild(row);
    }
    const note = document.createElement("p");
    note.className = "gg-shap-plain-note";
    note.textContent = "Four model features describe the same two target peaks. Explore them together in the inspector.";
    body.append(note);

    const technical = document.createElement("div");
    technical.className = "gg-shap-technical";
    const provenance = document.createElement("p");
    provenance.className = "shap-provenance";
    provenance.textContent = `SHAP baseline ${percent(explanation.base_value)}; model output ${percent(explanation.output_value)}. ${explanation.method || "SHAP"} · ${explanation.background_sample_count ?? "N/A"} training background samples · SHAP ${explanation.shap_version || "version unavailable"}.`;
    technical.append(provenance, list);
    body.append(technical);

    const caution = document.createElement("p");
    caution.className = "shap-caution";
    caution.innerHTML = '<i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>SHAP explains the model estimate, not biological causality or a clinical diagnosis. Signal features can be correlated.</span>';
    body.append(caution);

    disclosure.append(summary, body);
    return disclosure;
  }

  window.GeneGlassShapExplanation = Object.freeze({ create });
})();
