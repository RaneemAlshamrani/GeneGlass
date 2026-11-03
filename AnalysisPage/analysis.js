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
    section.after(panel);
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
    const headers = { Authorization: `Bearer ${token}` };
    try {
      const form = new FormData();
      form.append("file", file);
      const upload = await fetch(`${base}/analyses`, { method: "POST", headers, body: form });
      const data = await upload.json();
      if (!upload.ok) throw new Error(data.detail || "Upload failed.");
      const traceResponse = await fetch(`${base}/analyses/${data.id}/chromatogram`, { headers });
      if (!traceResponse.ok) throw new Error("Chromatogram could not be loaded.");
      window.GeneGlassChromatogram.render(await traceResponse.json());
      document.querySelector(".upload-card").hidden = true;
      message.textContent = "";
      try {
        const targetResponse = await fetch(`${base}/analyses/${data.id}/jak2-target`, { headers });
        if (!targetResponse.ok) throw new Error("Target analysis unavailable.");
        showTarget(await targetResponse.json());
      } catch (error) {
        const note = document.createElement("p");
        note.id = "jak2TargetError";
        note.textContent = "JAK2 target analysis unavailable. No mutation conclusion can be made.";
        section.after(note);
      }
    } catch (error) {
      message.textContent = error.message || "Analysis failed.";
    } finally {
      button.disabled = false;
    }
  });
})();
