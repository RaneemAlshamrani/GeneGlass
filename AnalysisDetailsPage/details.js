

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
    targetBase = Number(result.ab1_base_number);
    showCards(jak2Details, [
      ["AB1 Position", result.ab1_base_number],
      ["Direction", result.direction],
      ["Review Status", result.needs_review ? "Needs Review" : "Not flagged"]
    ]);
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
