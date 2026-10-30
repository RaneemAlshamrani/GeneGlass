
/* =========================================================
   GeneGlass Dashboard Integration
========================================================= */

let activityChart = null;
let geneChart = null;
let dashboardLoaded = false;
let dashboardLoading = false;

/* =========================================================
   HELPERS
========================================================= */

function updateText(selector, value) {
  const element = document.querySelector(selector);

  if (element) {
    element.textContent = value ?? "—";
  }
}

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
  const cards = document.querySelectorAll(
    ".stats-grid .stat-card"
  );

  if (cards.length < 3) return;

  const totalElement = cards[0].querySelector(".stat-info h2");
  const resultElement = cards[1].querySelector(".stat-info h2");
  const qcElement = cards[2].querySelector(".stat-info h2");

  if (totalElement) {
    totalElement.textContent = data.total_analyses ?? 0;
  }

  if (resultElement) {
    resultElement.textContent =
      `${data.positive ?? 0} / ${data.negative ?? 0}`;
  }

  if (qcElement) {
    qcElement.textContent =
      `${data.qc_success_rate ?? 0}%`;
  }
}

/* =========================================================
   GENE DISTRIBUTION CHART
========================================================= */

function updateGeneChart(data) {
  const canvas = document.getElementById("geneChart");

  if (!canvas || typeof Chart === "undefined") {
    console.error("Gene chart canvas or Chart.js is missing.");
    return;
  }

  const distribution = data.gene_distribution || {};

  const jak2 = distribution.JAK2 ?? 0;
  const calr = distribution.CALR ?? 0;
  const mpl = distribution.MPL ?? 0;

  if (geneChart) {
    geneChart.destroy();
  }

  geneChart = new Chart(canvas, {
    type: "doughnut",

    data: {
      labels: ["JAK2", "CALR", "MPL"],

      datasets: [
        {
          data: [jak2, calr, mpl],
          backgroundColor: [
            "#056d70",
            "#0ca9a2",
            "#79d8d4",
          ],
          borderWidth: 0,
          hoverOffset: 3,
        },
      ],
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "70%",

      plugins: {
        legend: {
          display: false,
        },
      },
    },
  });

  updateText(
    ".donut-center strong",
    data.total_analyses ?? 0
  );

  const geneValues = document.querySelectorAll(
    ".gene-list > div strong"
  );

  if (geneValues.length >= 3) {
    geneValues[0].textContent = jak2;
    geneValues[1].textContent = calr;
    geneValues[2].textContent = mpl;
  }
}

/* =========================================================
   ACTIVITY CHART
========================================================= */

function updateActivityChart(data) {
  const canvas = document.getElementById("activityChart");

  if (!canvas || typeof Chart === "undefined") {
    console.error("Activity chart canvas or Chart.js is missing.");
    return;
  }

  const activityCount = data.activity_last_7_days ?? 0;

  if (activityChart) {
    activityChart.destroy();
  }

  activityChart = new Chart(canvas, {
    type: "bar",

    data: {
      labels: ["Last 7 Days"],

      datasets: [
        {
          label: "Analyses",
          data: [activityCount],
          backgroundColor: "#10b59b",
          borderRadius: 5,
          borderSkipped: false,
        },
      ],
    },

    options: {
      responsive: true,
      maintainAspectRatio: false,

      plugins: {
        legend: {
          display: false,
        },

        tooltip: {
          displayColors: false,
        },
      },

      scales: {
        x: {
          grid: {
            display: false,
          },

          border: {
            display: false,
          },

          ticks: {
            color: "#789095",
          },
        },

        y: {
          beginAtZero: true,

          ticks: {
            precision: 0,
            color: "#789095",
          },

          grid: {
            color: "rgba(88, 124, 128, 0.10)",
          },

          border: {
            display: false,
          },
        },
      },
    },
  });
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

    cell.colSpan = 7;
    cell.textContent = "No analyses found yet.";
    cell.style.textAlign = "center";
    cell.style.padding = "25px";

    row.appendChild(cell);
    tableBody.appendChild(row);

    return;
  }

  analyses.forEach((analysis) => {
    const row = document.createElement("tr");

    // File name
    const fileCell = document.createElement("td");
    fileCell.className = "file-name";

    const fileIcon = document.createElement("i");
    fileIcon.className = "fa-solid fa-file-lines";

    fileCell.appendChild(fileIcon);
    fileCell.appendChild(
      document.createTextNode(
        ` ${analysis.file_name || "Unnamed file"}`
      )
    );

    row.appendChild(fileCell);

    // Gene
    const geneCell = document.createElement("td");
    const geneName = document.createElement("strong");

    geneName.textContent = analysis.gene || "—";
    geneCell.appendChild(geneName);
    row.appendChild(geneCell);

    // Target position
    const targetCell = document.createElement("td");
    targetCell.textContent = analysis.target_variant || "—";
    row.appendChild(targetCell);

    // Result
    const resultCell = document.createElement("td");
    const resultBadge = document.createElement("span");

    resultBadge.className = "result";

    if (analysis.v617f_detected === true) {
      resultBadge.classList.add("mutation-result");
      resultBadge.textContent = "Mutation Detected";
    } else if (
      analysis.v617f_detected === false &&
      (analysis.gene || "").toUpperCase() === "JAK2"
    ) {
      resultBadge.classList.add("normal-result");
      resultBadge.textContent = "Normal Sequence";
    } else if (analysis.status === "failed") {
      resultBadge.classList.add("review-result");
      resultBadge.textContent = "Analysis Failed";
    } else {
      resultBadge.classList.add("review-result");
      resultBadge.textContent = "Result Pending";
    }

    resultCell.appendChild(resultBadge);
    row.appendChild(resultCell);

    // QC status
    const qcCell = document.createElement("td");
    const qcBadge = document.createElement("span");

    qcBadge.className = "qc-badge";

    const qcStatus = analysis.qc_status || "pending";

    if (qcStatus === "passed") {
      qcBadge.classList.add("passed");
      qcBadge.textContent = "Passed";
    } else if (qcStatus === "needs_review") {
      qcBadge.classList.add("review");
      qcBadge.textContent = "Review";
    } else if (qcStatus === "failed") {
      qcBadge.classList.add("review");
      qcBadge.textContent = "Failed";
    } else {
      qcBadge.textContent = "Pending";
    }

    qcCell.appendChild(qcBadge);
    row.appendChild(qcCell);

    // Date
    const dateCell = document.createElement("td");
    dateCell.textContent = formatDate(analysis.created_at);
    row.appendChild(dateCell);

    // Actions (not connected yet)
    const actionsCell = document.createElement("td");
    actionsCell.className = "actions";
    actionsCell.textContent = "—";
    row.appendChild(actionsCell);

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
    updateGeneChart(data);
    updateActivityChart(data);
    updateRecentAnalyses(data.recent_analyses);

    dashboardLoaded = true;

    console.log(
      "Dashboard statistics loaded successfully.",
      data
    );

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

