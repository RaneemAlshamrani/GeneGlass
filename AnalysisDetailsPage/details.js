

/* GeneGlass - Saved Analysis Details */

(() => {
  const fileDetails = document.getElementById("fileDetails");
  const chromatogram = document.getElementById("detailsChromatogram");
  const jak2Details = document.getElementById("jak2Details");
  const message = document.getElementById("detailsMessage");
  const researchButton = document.getElementById("researchLookupButton");
  const researchStatus = document.getElementById("researchStatus");
  const researchResults = document.getElementById("researchResults");

  const apiBaseUrl = window.GeneGlassConfig.apiBaseUrl;

  const params = new URLSearchParams(window.location.search);
  const analysisId = params.get("id");

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
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}%` : "N/A";
  }

  function formatRatio(value) {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(3) : "N/A";
  }

  function appendResearchField(container, label, value) {
    const row = document.createElement("div");
    row.className = "research-field";
    const name = document.createElement("span");
    name.textContent = label;
    const content = document.createElement("strong");
    content.textContent = value || "N/A";
    row.append(name, content);
    container.appendChild(row);
  }

  function renderResearchResults(data) {
    researchResults.replaceChildren();
    const candidates = (Array.isArray(data.candidates) ? data.candidates : [])
      .filter((candidate) => (candidate.external_annotations || []).some(
        (item) => item.source === "NCBI ClinVar" && item.lookup_status === "matched"
      ));
    if (!candidates.length) {
      const empty = document.createElement("p");
      empty.className = "research-empty";
      empty.textContent =
        "No exact ClinVar-matched variants were found among the eligible candidates. " +
        "Unmatched and Needs Review candidates are not displayed as external results.";
      researchResults.appendChild(empty);
      return;
    }

    candidates.forEach((candidate) => {
      const card = document.createElement("article");
      card.className = "research-variant";
      const title = document.createElement("h3");
      title.textContent = candidate.hgvs;
      card.appendChild(title);
      appendResearchField(card, "AB1 base", String(candidate.ab1_base_number));
      appendResearchField(card, "Read direction", candidate.direction);
      appendResearchField(card, "Raw AB1 change", candidate.raw_ab1_change);
      appendResearchField(
        card,
        "Reference-oriented change",
        candidate.reference_oriented_change
      );
      appendResearchField(card, "Phred", candidate.phred_quality == null
        ? "N/A" : `Q${candidate.phred_quality}`);
      appendResearchField(card, "Candidate status", candidate.review_status);

      const annotations = Array.isArray(candidate.external_annotations)
        ? candidate.external_annotations : [];
      const clinvar = annotations.find((item) => item.source === "NCBI ClinVar");
      if (clinvar?.lookup_status === "matched") {
        appendResearchField(card, "ClinVar accession", clinvar.accession_version || clinvar.accession);
        const classifications = (clinvar.classifications || []).map((item) =>
          `${item.type}: ${item.description}${item.review_status ? ` (${item.review_status})` : ""}`
        );
        appendResearchField(card, "Published classifications", classifications.join(" · "));
        appendResearchField(card, "Associated conditions", (clinvar.conditions || []).join("; "));
        if (clinvar.source_url) {
          const link = document.createElement("a");
          link.className = "research-source-link";
          link.href = clinvar.source_url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "Open the matched ClinVar record";
          card.appendChild(link);
        }
      }
      researchResults.appendChild(card);
    });
  }

  async function loadSavedResearchResults(token) {
    const response = await fetch(
      `${apiBaseUrl}/analyses/${analysisId}/research-variants`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) return;
    const data = await response.json();
    researchStatus.textContent = data.candidate_count > 0
      ? `${data.candidate_count} saved ClinVar-matched variant(s). Research use only.`
      : "No exact ClinVar-matched variants are saved for this analysis.";
    renderResearchResults(data);
  }

  async function refreshResearchResults() {
    const token = window.GeneGlassAuth?.token;
    if (!token || !analysisId) return;
    researchButton.disabled = true;
    researchButton.textContent = "Searching…";
    researchStatus.textContent =
      "Extracting eligible JAK2 base-call candidates and querying ClinVar by HGVS only…";
    try {
      const response = await fetch(
        `${apiBaseUrl}/analyses/${analysisId}/research-variants/refresh`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Research lookup failed.");
      }
      researchStatus.textContent = data.candidate_count
        ? `${data.candidate_count} candidate(s) displayed; eligible candidates were checked in ClinVar. Research use only.`
        : "No exact ClinVar-matched variants were found. Unmatched candidates are not displayed.";
      renderResearchResults(data);
    } catch (error) {
      researchStatus.textContent = error.message;
    } finally {
      researchButton.disabled = false;
      researchButton.textContent = "Search ClinVar";
    }
  }

  async function loadDetails() {
    const token = window.GeneGlassAuth?.token;

    if (!token) return;

    if (!analysisId || !/^\d+$/.test(analysisId)) {
      message.textContent = "Invalid analysis ID.";
      return;
    }

    try {
      const response = await fetch(
        `${apiBaseUrl}/analyses/${analysisId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error("Unable to load analysis details.");
      }

      const details = await response.json();

      showCards(fileDetails, [
        ["File Name", details.original_file_name],
        ["Date", details.created_at
          ? new Date(details.created_at).toLocaleDateString()
          : "N/A"],
      ]);


     
try {
  const [traceResponse, jak2Response] = await Promise.all([
    fetch(`${apiBaseUrl}/analyses/${analysisId}/chromatogram`, {
      headers: { Authorization: `Bearer ${token}` }
    }),
    fetch(`${apiBaseUrl}/analyses/${analysisId}/jak2-target`, {
      headers: { Authorization: `Bearer ${token}` }
    })
  ]);

  let targetBase = null;
  if (jak2Response.ok) {
    const jak2Data = await jak2Response.json();
    const result = jak2Data.result || {};
    const peaks = result.peak_analysis || {};
    const heights = peaks.peak_heights || {};
    const reasons = Array.isArray(result.review_reasons)
      ? result.review_reasons.filter(Boolean).join("; ")
      : "";
    targetBase = Number(result.ab1_base_number);
    showCards(jak2Details, [
      ["AB1 Position", result.ab1_base_number],
      ["Direction", result.direction],
      ["Observed Base", result.observed_base],
      ["Target Phred Quality", result.quality_score],
      ["Alignment Identity", formatPercent(result.alignment_identity_percentage)],
      ["Read Coverage", formatPercent(result.alignment_coverage_percentage)],
      ["A Peak", heights.A],
      ["C Peak", heights.C],
      ["G Peak", heights.G],
      ["T Peak", heights.T],
      ["Primary Peak", peaks.primary_base],
      ["Secondary Peak", peaks.secondary_base],
      ["Secondary / Primary", formatRatio(peaks.overlap_ratio)],
      ["Review Status", result.needs_review ? "Needs Review" : "Not flagged"],
      ["Review Reason", reasons || "No preliminary QC review reason"]
    ]);
    const reference = result.reference_evidence;
    if (reference?.url) {
      const referenceCard = document.createElement("div");
      referenceCard.className = "details-item";
      const label = document.createElement("span");
      label.className = "details-label";
      label.textContent = "External Reference";
      const link = document.createElement("a");
      link.className = "details-value";
      link.href = reference.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `${reference.source}: ${reference.accession}`;
      referenceCard.append(label, link);
      jak2Details.append(referenceCard);
    }
  } else {
    jak2Details.textContent = "JAK2 target analysis could not be loaded.";
  }

  if (!traceResponse.ok) throw new Error("Unable to load chromatogram.");
  const trace = await traceResponse.json();
  if (!window.GeneGlassChromatogram) throw new Error("Chromatogram viewer script missing.");
  await window.GeneGlassChromatogram.render(trace, {
    targetBase: Number.isInteger(targetBase) && targetBase > 0 ? targetBase : undefined,
    showTitle: false
  });
  document.getElementById("chromatogramLoading").hidden = true;
} catch (error) {
  console.error("Chromatogram / JAK2 error:", error);
  document.getElementById("chromatogramLoading").textContent =
    "Chromatogram could not be loaded: " + error.message;
}



      message.textContent = "";
      await loadSavedResearchResults(token);
    } catch (error) {
      message.textContent = error.message;
    }
  }

  document.addEventListener("geneglass:auth-ready", loadDetails);
  researchButton.addEventListener("click", refreshResearchResults);

  if (window.GeneGlassAuth?.token) {
    loadDetails();
  }
})();
