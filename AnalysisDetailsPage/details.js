
/* GeneGlass - Saved Analysis Details */

(() => {
  const fileDetails = document.getElementById("fileDetails");
  const qcDetails = document.getElementById("qcDetails");
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
        ["Gene", details.gene],
        ["Target Variant", details.target_variant],
        ["Analysis Status", details.status],
        ["QC Status", details.qc_status],
        ["Date", details.created_at
          ? new Date(details.created_at).toLocaleDateString()
          : "N/A"],
      ]);

      
const qc = details.quality_control || {};

showCards(qcDetails, [
  ["Sequence Length", qc.sequence_length],
  ["Average Quality", qc.average_quality],
  ["Low Quality Bases", qc.low_quality_count],
  ["Retained Percentage",
    qc.retained_percentage != null
      ? `${qc.retained_percentage}%`
      : "N/A"],
  ["Quality Assessment", qc.quality_assessment],
  ["QC Status", details.qc_status],
]);


     
try {
  const traceResponse = await fetch(
    `${apiBaseUrl}/analyses/${analysisId}/chromatogram`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );

  if (!traceResponse.ok) {
    throw new Error("Unable to load chromatogram.");
  }

  const trace = await traceResponse.json();

  window.GeneGlassChromatogram.render(trace);

  document.getElementById("chromatogramLoading").hidden = true;

} catch (traceError) {
  console.error("Chromatogram error:", traceError);

  document.getElementById("chromatogramLoading").textContent =
    "Chromatogram could not be loaded.";
}


      
try {
  const jak2Response = await fetch(
    `${apiBaseUrl}/analyses/${analysisId}/jak2-target`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );

  if (!jak2Response.ok) {
    throw new Error("Unable to load JAK2 target analysis.");
  }

  const jak2Data = await jak2Response.json();
  const result = jak2Data.result;

  showCards(jak2Details, [
    ["AB1 Position", result.ab1_base_number],
    ["Direction", result.direction],
    ["Observed Base", result.observed_base],
    ["Target Phred", result.quality_score],
    ["Review Status", result.needs_review ? "Needs Review" : "Not flagged"]
  ]);

} catch (jak2Error) {
  console.error("JAK2 analysis error:", jak2Error);
  jak2Details.textContent =
    "JAK2 target analysis could not be loaded.";
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
