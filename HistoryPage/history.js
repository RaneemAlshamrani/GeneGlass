
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

  // Add QC filter without changing the HTML file.
  const qcFilter = document.createElement("select");
  qcFilter.id = "qcFilter";
  qcFilter.setAttribute("aria-label", "Filter by QC status");

  qcFilter.innerHTML = `
    <option value="all">All QC Statuses</option>
    <option value="pending">QC Pending</option>
    <option value="passed">QC Passed</option>
    <option value="needs_review">Needs Review</option>
    <option value="failed">QC Failed</option>
  `;

  filter.insertAdjacentElement("afterend", qcFilter);

  // Add pagination controls.
  const pagination = document.createElement("div");
  pagination.id = "historyPagination";
  pagination.className = "history-pagination";
 pagination.style.setProperty("display", "none", "important");
  pagination.style.justifyContent = "center";
  pagination.style.alignItems = "center";
  pagination.style.gap = "12px";
  pagination.style.marginTop = "20px";

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
    if (analysis.qc_status === "needs_review") {
      return "Needs Review";
    }

    if (
      analysis.status === "pending" ||
      analysis.status === "processing" ||
      analysis.qc_status === "pending"
    ) {
      return "Pending";
    }

    if (
      analysis.status === "completed" &&
      analysis.gene === "JAK2" &&
      analysis.v617f_detected === true
    ) {
      return "Mutation Detected";
    }

    if (
      analysis.status === "completed" &&
      analysis.gene === "JAK2" &&
      analysis.v617f_detected === false
    ) {
      return "Normal";
    }

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

  async function showAnalysisDetails(analysisId, button) {
    const token = getToken();

    if (!token) return;

    button.disabled = true;
    button.textContent = "Loading...";

    try {
      const response = await fetch(`${API_URL}/${analysisId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Unable to load analysis details.");
      }

      const details = await response.json();

      const detailText = [
        `File: ${details.original_file_name}`,
        `Gene: ${details.gene}`,
        `Target: ${details.target_variant}`,
        `Result: ${getResultLabel(details)}`,
        `QC Status: ${details.qc_status}`,
        `Status: ${details.status}`,
        `Summary: ${details.result_summary || "Not available"}`,
      ];

      message.textContent = detailText.join(" | ");
    } catch (error) {
      message.textContent = error.message;
    } finally {
      button.disabled = false;
      button.textContent = "View";
    }
  }

  function renderRows(analyses) {
    rows.replaceChildren();

    for (const analysis of analyses) {
      const tr = document.createElement("tr");

      tr.append(
        createCell(analysis.original_file_name),
        createCell(analysis.gene),
        createCell(analysis.target_variant),
        createCell(getResultLabel(analysis)),
        createCell(analysis.qc_status),
        createCell(formatDate(analysis.created_at)),
      );

      const actions = document.createElement("td");
      const viewButton = document.createElement("button");

      viewButton.type = "button";
      viewButton.textContent = "View";

      viewButton.addEventListener("click", () => {
        showAnalysisDetails(analysis.id, viewButton);
      });

      actions.appendChild(viewButton);
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

  if (totalPages > 1) {
    pagination.style.setProperty("display", "flex", "important");
  } else {
    pagination.style.setProperty("display", "none", "important");
  }
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

    if (qcFilter.value !== "all") {
      params.set("qc_status", qcFilter.value);
    }

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
            filter.value !== "all" ||
            qcFilter.value !== "all"
          ),
        );
        return;
      }

      empty.hidden = true;
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

  qcFilter.addEventListener("change", () => {
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
