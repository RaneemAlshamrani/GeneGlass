/* GeneGlass History: backend integration */
(() => {
  const rows = document.getElementById("historyRows");
  const empty = document.getElementById("emptyState");
  const count = document.getElementById("resultCount");
  const search = document.getElementById("searchInput");
  const filter = document.getElementById("resultFilter");
  const message = document.getElementById("historyMessage");
  const API_URL = `${window.GeneGlassConfig.apiBaseUrl}/analyses`;
  const PAGE_SIZE = 10;
  let currentPage = 1;
  let totalPages = 0;
  let requestNumber = 0;
  const savedQc = new Map();
  // Add pagination controls.
  const pagination = document.createElement("div");
  pagination.id = "historyPagination";
  pagination.className = "history-pagination";
  pagination.hidden = true;
  const previousButton = document.createElement("button");
  previousButton.type = "button";
  previousButton.textContent = "Previous";
  const pageInfo = document.createElement("span");
  const nextButton = document.createElement("button");
  nextButton.type = "button";
  nextButton.textContent = "Next";
  pagination.append(previousButton, pageInfo, nextButton);
  document.querySelector(".table-wrapper")
    .insertAdjacentElement("afterend", pagination);

  function getToken() {
    return window.GeneGlassAuth?.token;
  }

  function getResultLabel(analysis) {
    const qc = savedQc.get(Number(analysis.id));
    if (qc?.target_found === false) return "Target Not Found";
    if (qc?.decision === "request_repeat") return "Repeat Requested";
    const output = analysis.ai_prediction;
    if (output?.prediction === "hetero") return "Heterozygous Pattern";
    if (output?.prediction === "negative") return "Not Detected";
    if (output?.status === "Needs Review" || analysis.qc_status === "needs_review") return "Needs Review";
    if (analysis.status === "pending" || analysis.status === "processing" || analysis.qc_status === "pending") return "Pending QC Decision";
    return "Not available";
  }

  function formatDate(dateValue) {
    if (!dateValue) return "—";
    const date = new Date(dateValue);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleDateString();
  }

  function setLoading() {
    rows.replaceChildren();
    empty.hidden = false;
    empty.querySelector("h3").textContent = "Loading analyses...";
    empty.querySelector("p").textContent =
      "Please wait while your analysis history is loading.";
    message.textContent = "";
    pagination.hidden = true;
  }

  function setError(errorMessage) {
    rows.replaceChildren();
    empty.hidden = false;
    empty.querySelector("h3").textContent =
      "Unable to load analyses";
    empty.querySelector("p").textContent = errorMessage;
    message.textContent = "Please try again.";
    pagination.hidden = true;
    count.textContent = "0 analyses";
  }

  function setEmptyState(isFiltered) {
    empty.hidden = false;
    empty.querySelector("h3").textContent = isFiltered
      ? "No matching analyses"
      : "No saved analyses yet";
    empty.querySelector("p").textContent = isFiltered
      ? "Try another search or filter."
      : "Completed analyses will appear here when available.";
    pagination.hidden = true;
  }

  function createCell(value) {
    const td = document.createElement("td");
    td.textContent = value ?? "—";
    return td;
  }

  async function downloadReport(analysis, button) {
    const token = getToken();
    const path = analysis.report?.download_url;
    if (!token || !path) return;
    const previewWindow = window.open("", "_blank");
    button.disabled = true;
    button.textContent = "Opening...";
    try {
      const apiOrigin = window.GeneGlassConfig.apiBaseUrl.replace(/\/api$/, "");
      const response = await fetch(`${apiOrigin}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("The saved report could not be downloaded.");
      const blobUrl = URL.createObjectURL(await response.blob());
      if (previewWindow) {
        previewWindow.opener = null;
        previewWindow.location.href = blobUrl;
      }
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (error) {
      if (previewWindow) previewWindow.close();
      message.textContent = error.message;
    } finally {
      button.disabled = false;
      button.innerHTML = '<i class="fa-solid fa-file-pdf"></i> Download';
    }
  }

  function createReportCell(analysis) {
    const td = document.createElement("td");
    td.className = "history-report-cell";
    const report = analysis.report || { status: "awaiting_decision" };
    const qc = savedQc.get(Number(analysis.id));
    if (report.status !== "finalized" && (qc?.target_found === false || qc?.decision === "request_repeat")) {
      td.classList.add("history-report-unavailable");
      td.textContent = qc?.target_found === false ? "Not available" : "Repeat requested";
      return td;
    }
    if (report.status === "finalized") {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "history-report-btn";
      button.innerHTML = '<i class="fa-solid fa-file-pdf"></i> Download';
      button.addEventListener("click", () => downloadReport(analysis, button));
      td.appendChild(button);
      return td;
    }
    const complete = document.createElement("a");
    complete.href = `../AnalysisPage/analysis.html?id=${analysis.id}&report=1`;
    complete.textContent = report.status === "needs_update" ? "Update PDF" : "Complete";
    td.appendChild(complete);
    return td;
  }

  async function deleteAnalysis(analysis, button) {
    const confirmed = window.confirm(
      `Delete “${analysis.original_file_name}” from History?\n\n` +
      "The AB1 file, reviews, model results, and saved PDF reports for this analysis will be permanently deleted."
    );
    if (!confirmed) return;
    const token = getToken();
    if (!token) return;
    button.disabled = true;
    button.textContent = "Deleting...";
    try {
      const response = await fetch(`${API_URL}/${analysis.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "The analysis could not be deleted.");
      }
      if (rows.children.length === 1 && currentPage > 1) currentPage--;
      await loadHistory();
      message.textContent = "Analysis deleted from History.";
    } catch (error) {
      message.textContent = error.message;
      button.disabled = false;
      button.textContent = "Delete";
    }
  }

  function renderRows(analyses) {
    rows.replaceChildren();
    for (const analysis of analyses) {
      const tr = document.createElement("tr");
      tr.append(
        createCell(analysis.original_file_name),
        createCell(getResultLabel(analysis)),
        createCell(formatDate(analysis.created_at)),
        createReportCell(analysis),
      );
      const actions = document.createElement("td");
      actions.className = "history-actions";
      const viewButton = document.createElement("button");
      viewButton.type = "button";
      viewButton.textContent = "View";
      viewButton.className = "history-view-btn";
      viewButton.addEventListener("click", () => {
        window.location.href =
          `../AnalysisDetailsPage/details.html?id=${analysis.id}`;
      });
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.textContent = "Delete";
      deleteButton.className = "history-delete-btn";
      deleteButton.addEventListener("click", () => deleteAnalysis(analysis, deleteButton));
      actions.append(viewButton, deleteButton);
      tr.appendChild(actions);
      rows.appendChild(tr);
    }
  }
  function updatePagination() {
    pageInfo.textContent =
      totalPages > 0
        ? `Page ${currentPage} of ${totalPages}`
        : "No pages";
    previousButton.disabled = currentPage <= 1;
    nextButton.disabled =
      totalPages === 0 || currentPage >= totalPages;
    pagination.hidden = totalPages <= 1;
  }

  async function loadHistory() {
    const token = getToken();
    if (!token) return;
    const thisRequest = ++requestNumber;
    setLoading();
    const params = new URLSearchParams({
      page: String(currentPage),
      page_size: String(PAGE_SIZE),
      search: search.value.trim(),
      result: filter.value,
    });
    try {
      const response = await fetch(`${API_URL}?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        throw new Error(
          response.status === 401
            ? "Your session has expired. Please log in again."
            : "Something went wrong while loading your history.",
        );
      }
      const data = await response.json();
      // Ignore older requests if a newer search has started.
      if (thisRequest !== requestNumber) return;
      totalPages = data.total_pages;
      currentPage = data.page;
      count.textContent =
        `${data.total} ${data.total === 1 ? "analysis" : "analyses"}`;
      if (data.items.length === 0) {
        rows.replaceChildren();
        setEmptyState(
          Boolean(
            search.value.trim() ||
            filter.value !== "all"
          ),
        );
        return;
      }
      empty.hidden = true;
      // The per-analysis QC endpoint distinguishes Target Not Found from generic Needs Review.
      await Promise.all(data.items.map(async (item) => {
        try {
          const qcResponse = await fetch(`${API_URL}/${item.id}/preliminary-qc-decision`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!qcResponse.ok) return;
          const qc = await qcResponse.json();
          if (thisRequest === requestNumber) savedQc.set(Number(item.id), qc);
        } catch (error) {
          console.warn("QC status unavailable for analysis", item.id, error);
        }
      }));
      if (thisRequest !== requestNumber) return;
      renderRows(data.items);
      updatePagination();
      message.textContent = "";
    } catch (error) {
      if (thisRequest !== requestNumber) return;
      setError(error.message);
    }
  }
  search.addEventListener("input", () => {
    currentPage = 1;
    loadHistory();
  });
  filter.addEventListener("change", () => {
    currentPage = 1;
    loadHistory();
  });
  previousButton.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      loadHistory();
    }
  });
  nextButton.addEventListener("click", () => {
    if (currentPage < totalPages) {
      currentPage++;
      loadHistory();
    }
  });

  // Wait until authentication has been verified.
  document.addEventListener("geneglass:auth-ready", loadHistory);
  // Handle the case where authentication is already available.
  if (window.GeneGlassAuth?.token) {
    loadHistory();
  }
})();
