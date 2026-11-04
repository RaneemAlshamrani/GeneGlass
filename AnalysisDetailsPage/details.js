

/* GeneGlass - Saved Analysis Details */

(() => {
  const fileDetails = document.getElementById("fileDetails");
  const chromatogram = document.getElementById("detailsChromatogram");
  const jak2Details = document.getElementById("jak2Details");
  const message = document.getElementById("detailsMessage");

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
    targetBase: Number.isInteger(targetBase) && targetBase > 0 ? targetBase : undefined
  });
  document.getElementById("chromatogramLoading").hidden = true;
} catch (error) {
  console.error("Chromatogram / JAK2 error:", error);
  document.getElementById("chromatogramLoading").textContent =
    "Chromatogram could not be loaded: " + error.message;
}



      message.textContent = "";
    } catch (error) {
      message.textContent = error.message;
    }
  }

  document.addEventListener("geneglass:auth-ready", loadDetails);

  if (window.GeneGlassAuth?.token) {
    loadDetails();
  }
})();
