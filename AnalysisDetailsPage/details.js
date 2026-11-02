
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


      chromatogram.textContent =
        "Chromatogram will appear here.";

      jak2Details.textContent =
        "JAK2 target analysis will appear here.";

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
