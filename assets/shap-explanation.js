(function () {
  const FEATURE_LABELS = Object.freeze({
    alignment_score: "Reference alignment",
    reference_peak: "Reference peak",
    alternative_peak: "Alternative peak",
    alternative_ratio: "Alternative signal ratio",
    phred_quality: "Phred quality",
    peak_overlap_score: "Peak overlap",
    local_noise_ratio: "Local background ratio",
  });

  function percent(value) {
    return `${(Number(value) * 100).toFixed(1)}%`;
  }

  function featureValue(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) {
      return "Unavailable";
    }
    return Number(value).toLocaleString(undefined, {
      maximumFractionDigits: 3,
    });
  }

  function create(explanation) {
    if (!explanation || explanation.available !== true) return null;
    const contributions = Array.isArray(explanation.contributions)
      ? explanation.contributions
      : [];
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
    small.textContent = "Feature impact on the Hetero probability";
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
    overview.textContent = `Baseline ${percent(explanation.base_value)} → Hetero output ${percent(explanation.output_value)}`;
    body.appendChild(overview);

    const maxImpact = Math.max(
      ...contributions.map((item) => Math.abs(Number(item.impact) || 0)),
      0.000001,
    );
    const list = document.createElement("div");
    list.className = "shap-contribution-list";
    for (const item of contributions) {
      const impact = Number(item.impact) || 0;
      const towardHetero = impact >= 0;
      const row = document.createElement("div");
      row.className = "shap-contribution";
      row.dataset.direction = towardHetero ? "hetero" : "negative";

      const label = document.createElement("div");
      label.className = "shap-feature-label";
      const name = document.createElement("strong");
      name.textContent = FEATURE_LABELS[item.feature] || item.feature;
      const value = document.createElement("small");
      value.textContent = `Value: ${featureValue(item.value)}`;
      label.append(name, value);

      const track = document.createElement("div");
      track.className = "shap-impact-track";
      const fill = document.createElement("span");
      fill.className = "shap-impact-fill";
      fill.style.width = `${Math.max(2, Math.abs(impact) / maxImpact * 50)}%`;
      track.appendChild(fill);

      const result = document.createElement("div");
      result.className = "shap-impact-value";
      const points = `${impact >= 0 ? "+" : ""}${(impact * 100).toFixed(1)} pp`;
      const direction = towardHetero ? "toward Hetero" : "toward Negative";
      result.innerHTML = `<strong>${points}</strong><small>${direction}</small>`;
      row.append(label, track, result);
      list.appendChild(row);
    }
    body.appendChild(list);

    const provenance = document.createElement("p");
    provenance.className = "shap-provenance";
    provenance.textContent = `${explanation.method || "SHAP"} · ${explanation.background_sample_count} training background samples · SHAP ${explanation.shap_version || "version unavailable"}`;
    body.appendChild(provenance);

    const caution = document.createElement("p");
    caution.className = "shap-caution";
    caution.innerHTML = '<i class="fa-solid fa-circle-info" aria-hidden="true"></i><span>Explains this model output only. It does not establish biological causality, clinical validity, or replace specialist review. Correlated signal features may share attribution.</span>';
    body.appendChild(caution);

    disclosure.append(summary, body);
    return disclosure;
  }

  window.GeneGlassShapExplanation = Object.freeze({ create });
})();
