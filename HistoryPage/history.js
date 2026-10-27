/* GeneGlass History: no fabricated results. Future API integration point. */
const rows = document.getElementById("historyRows");
const empty = document.getElementById("emptyState");
const count = document.getElementById("resultCount");
const search = document.getElementById("searchInput");
const filter = document.getElementById("resultFilter");
const message = document.getElementById("historyMessage");

// Once the backend is ready, replace this array with GET /api/cases response.
const savedAnalyses = [];

function renderHistory() {
  const q = search.value.trim().toLowerCase();
  const status = filter.value;
  const filtered = savedAnalyses.filter((item) => {
    const matchesText = `${item.fileName || ""} ${item.gene || ""}`
      .toLowerCase()
      .includes(q);
    return matchesText && (status === "all" || item.resultKey === status);
  });
  rows.replaceChildren();
  count.textContent = `${filtered.length} ${filtered.length === 1 ? "analysis" : "analyses"}`;
  empty.hidden = filtered.length > 0;
  if (filtered.length === 0) {
    empty.querySelector("h3").textContent = savedAnalyses.length
      ? "No matching analyses"
      : "No saved analyses yet";
    empty.querySelector("p").textContent = savedAnalyses.length
      ? "Try another search or filter."
      : "Completed analyses will appear here after the backend and database are connected.";
  }
  for (const item of filtered) {
    const tr = document.createElement("tr");
    for (const value of [
      item.fileName,
      item.gene,
      item.targetPosition,
      item.result,
      item.qcStatus,
      item.date,
    ]) {
      const td = document.createElement("td");
      td.textContent = value ?? "—";
      tr.appendChild(td);
    }
    const actions = document.createElement("td");
    actions.textContent = "Available after backend integration";
    tr.appendChild(actions);
    rows.appendChild(tr);
  }
  message.textContent = "";
}
search.addEventListener("input", renderHistory);
filter.addEventListener("change", renderHistory);
renderHistory();
