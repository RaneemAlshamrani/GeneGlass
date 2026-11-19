
/* =========================================================
   GeneGlass Dashboard Integration
========================================================= */

let dashboardLoaded = false;
let dashboardLoading = false;

/* =========================================================
   HELPERS
========================================================= */

function formatDate(dateValue) {
  if (!dateValue) return "—";

  const date = new Date(dateValue);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/* =========================================================
   UPDATE STAT CARDS
========================================================= */

function updateStatCards(data) {
  const totalElement = document.getElementById("ggTotal");
  const positiveElement = document.getElementById("ggPositive");
  const negativeElement = document.getElementById("ggNegative");

  if (totalElement) {
    totalElement.textContent = data.total_analyses ?? 0;
  }

  if (positiveElement) {
    positiveElement.textContent = data.positive ?? 0;
  }

  if (negativeElement) {
    negativeElement.textContent = data.negative ?? 0;
  }
}

/* =========================================================
   RECENT ANALYSES TABLE
========================================================= */

function updateRecentAnalyses(analyses) {
  const tableBody = document.querySelector(
    ".recent-card table tbody"
  );

  if (!tableBody) return;

  tableBody.replaceChildren();

  if (!Array.isArray(analyses) || analyses.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 3;
    cell.textContent = "No analyses found yet.";
    cell.style.textAlign = "center";
    cell.style.padding = "25px";

    row.appendChild(cell);
    tableBody.appendChild(row);

    return;
  }

  analyses.forEach((analysis) => {
    const row = document.createElement("tr");

    // File name - clickable link to analysis details
    const fileCell = document.createElement("td");
    fileCell.className = "file-name";

    if (analysis.id !== undefined && analysis.id !== null) {
      const fileLink = document.createElement("a");

      fileLink.href =
        `../AnalysisDetailsPage/details.html?id=${encodeURIComponent(analysis.id)}`;

      fileLink.title = "Open analysis details";

      const fileIcon = document.createElement("i");
      fileIcon.className = "fa-solid fa-file-lines";

      fileLink.appendChild(fileIcon);
      fileLink.appendChild(
        document.createTextNode(
          ` ${analysis.file_name || "Unnamed file"}`
        )
      );

      fileCell.appendChild(fileLink);
    } else {
      fileCell.textContent =
        analysis.file_name || "Unnamed file";

      console.error(
        "Analysis ID is missing:",
        analysis
      );
    }

    row.appendChild(fileCell);

    // Date
    const dateCell = document.createElement("td");

    dateCell.textContent = formatDate(analysis.created_at);
    row.appendChild(dateCell);

    // Result
    const resultCell = document.createElement("td");
    const resultBadge = document.createElement("span");

    resultBadge.className = "result";

    const modelResult = analysis.ai_prediction;
    const needsReview = modelResult?.status === "Needs Review";
    const failed = analysis.status === "failed";

    if (!needsReview && !failed && modelResult?.prediction === "hetero") {
      resultBadge.classList.add("mutation-result");
      resultBadge.textContent = "Heterozygous";
      resultBadge.title = "Research model output — not a clinical diagnosis";
    } else if (!needsReview && !failed && modelResult?.prediction === "negative") {
      resultBadge.classList.add("normal-result");
      resultBadge.textContent = "Not Detected";
      resultBadge.title = "Research model output — not a clinical diagnosis";
    } else {
      resultBadge.classList.add("review-result");
      resultBadge.textContent = "Pending";
      if (needsReview) {
        resultBadge.title = "Needs review — open analysis details";
      } else if (failed) {
        resultBadge.title = "Analysis failed — open analysis details";
      }
    }

    resultCell.appendChild(resultBadge);
    row.appendChild(resultCell);


    tableBody.appendChild(row);
  });
}

/* =========================================================
   LOAD DASHBOARD DATA
========================================================= */

async function loadDashboardSummary() {
  if (dashboardLoaded || dashboardLoading) return;

  const token = window.GeneGlassAuth?.token;

  if (!token) {
    console.warn(
      "Dashboard: waiting for authentication."
    );
    return;
  }

  const apiBaseUrl = window.GeneGlassConfig?.apiBaseUrl;

  if (!apiBaseUrl) {
    console.error(
      "Dashboard: API base URL is missing."
    );
    return;
  }

  dashboardLoading = true;

  try {
    const response = await fetch(
      `${apiBaseUrl}/dashboard/summary`,
      {
        method: "GET",

        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));

      throw new Error(
        error.detail ||
        `Dashboard request failed: ${response.status}`
      );
    }

    const data = await response.json();

    updateStatCards(data);
    updateRecentAnalyses(data.recent_analyses);

    dashboardLoaded = true;

  } catch (error) {
    console.error(
      "Could not load dashboard statistics:",
      error
    );

  } finally {
    dashboardLoading = false;
  }
}

/* =========================================================
   INITIALIZATION
========================================================= */

document.addEventListener("DOMContentLoaded", () => {
  loadDashboardSummary();
});

document.addEventListener("geneglass:auth-ready", () => {
  loadDashboardSummary();
});
