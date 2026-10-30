
(() => {
  const fileInput = document.getElementById("ab1");
  const fileInfo = document.getElementById("fileInfo");
  const analyzeButton = document.getElementById("analyze");
  const message = document.getElementById("message");

  function showQualityResults(data) {
    const qc = data.quality_control;

    message.replaceChildren();

    const heading = document.createElement("strong");
    heading.textContent = "Quality Control Results";
    message.appendChild(heading);

    const results = [
      ["Analysis ID", data.id],
      ["Sequence length", qc.sequence_length],
      ["Cleaned sequence length", qc.cleaned_sequence_length],
      ["Average quality", qc.average_quality],
      ["Minimum quality", qc.minimum_quality],
      ["Maximum quality", qc.maximum_quality],
      ["Low-quality bases", qc.low_quality_count],
      ["Low-quality percentage", `${qc.low_quality_percentage}%`],
      ["Retained percentage", `${qc.retained_percentage}%`],
      ["Quality assessment", qc.quality_assessment],
      ["QC status", data.qc_status],
      ["Variant detection", "Pending"],
    ];

    const list = document.createElement("ul");

    results.forEach(([label, value]) => {
      const item = document.createElement("li");
      item.textContent = `${label}: ${value}`;
      list.appendChild(item);
    });

    message.appendChild(list);
  }

  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];

    if (!file) {
      fileInfo.textContent = "No file selected";
      analyzeButton.disabled = true;
      message.textContent = "";
      return;
    }

    if (!/\.ab1$/i.test(file.name)) {
      fileInfo.textContent = "Please select a .ab1 file.";
      analyzeButton.disabled = true;
      message.textContent = "";
      fileInput.value = "";
      return;
    }

    fileInfo.textContent = `Selected: ${file.name}`;
    analyzeButton.disabled = false;
    message.textContent = "";
  });

  analyzeButton.addEventListener("click", async () => {
    const file = fileInput.files?.[0];

    if (!file) return;

    const token = window.GeneGlassAuth?.token;
    const apiBaseUrl = window.GeneGlassConfig?.apiBaseUrl;

    if (!token || !apiBaseUrl) {
      message.textContent =
        "Authentication or API configuration is unavailable. Please sign in again.";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    analyzeButton.disabled = true;
    message.textContent = "Uploading file and checking quality...";

    try {
      const response = await fetch(`${apiBaseUrl}/analyses`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "The file could not be processed."
        );
      }

      fileInfo.textContent = `Uploaded: ${data.file_name}`;
      showQualityResults(data);
    } catch (error) {
      message.textContent = error.message;
    } finally {
      analyzeButton.disabled = false;
    }
  });
})();
