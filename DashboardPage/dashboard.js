/* =========================================================
   Activity — Sunday to Thursday
========================================================= */

const activityCanvas = document.getElementById("activityChart");

const activityChart = new Chart(activityCanvas, {
  type: "bar",

  data: {
    labels: ["Sun", "Mon", "Tue", "Wed", "Thu"],

    datasets: [
      {
        label: "Normal",
        data: [1, 3, 1, 3, 1],
        backgroundColor: "#10b59b",
        borderRadius: 5,
        borderSkipped: false,
      },
      {
        label: "Mutation",
        data: [1, 2, 1, 2, 1],
        backgroundColor: "#ed3f46",
        borderRadius: 5,
        borderSkipped: false,
      },
      {
        label: "QC Review",
        data: [1, 0.5, 1, 0.5, 1],
        backgroundColor: "#f3a316",
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
        displayColors: true,
      },
    },

    scales: {
      x: {
        stacked: true,

        grid: {
          display: false,
        },

        border: {
          display: false,
        },

        ticks: {
          color: "#789095",
          font: {
            size: 11,
          },
        },
      },

      y: {
        stacked: true,

        beginAtZero: true,

        suggestedMax: 6,

        ticks: {
          stepSize: 2,

          color: "#789095",

          font: {
            size: 10,
          },
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

/* =========================================================
   GENE DISTRIBUTION
========================================================= */

const geneCanvas = document.getElementById("geneChart");

const geneChart = new Chart(geneCanvas, {
  type: "doughnut",

  data: {
    labels: ["JAK2", "CALR", "MPL"],

    datasets: [
      {
        data: [14, 9, 5],

        backgroundColor: ["#056d70", "#0ca9a2", "#79d8d4"],

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
