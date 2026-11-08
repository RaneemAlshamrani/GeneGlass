

/* GeneGlass - Saved Analysis Details */

(() => {
  const fileDetails = document.getElementById("fileDetails");
  const chromatogram = document.getElementById("detailsChromatogram");
  const jak2Details = document.getElementById("jak2Details");
  const jak2Summary = document.getElementById("jak2Summary");
  const evidenceBadge = document.getElementById("evidenceBadge");
  const message = document.getElementById("detailsMessage");
  const researchButton = document.getElementById("researchLookupButton");
  const researchStatus = document.getElementById("researchStatus");
  const researchResults = document.getElementById("researchResults");
  const researchMatchBadge = document.getElementById("researchMatchBadge");
  const reviewForm = document.getElementById("reviewForm");
  const reviewComment = document.getElementById("reviewComment");
  const reviewQuickNotes = document.getElementById("reviewQuickNotes");
  const reviewSubmitButton = document.getElementById("reviewSubmitButton");
  const reviewStatus = document.getElementById("reviewStatus");
  const reviewHistory = document.getElementById("reviewHistory");
  const reviewHistoryCount = document.getElementById("reviewHistoryCount");
  const latestReviewBadge = document.getElementById("latestReviewBadge");
  const auditCount = document.getElementById("auditCount");
  const auditStatus = document.getElementById("auditStatus");
  const auditTimeline = document.getElementById("auditTimeline");

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

  function formatPercent(value) {
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}%` : "N/A";
  }

  function formatRatio(value) {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(3) : "N/A";
  }

  function findNearbyMotif(sequence, targetBase, motif = "ACAT") {
    if (!sequence || !Number.isInteger(targetBase)) return null;
    const normalized = sequence.toUpperCase();
    const targetIndex = targetBase - 1;
    const from = Math.max(0, targetIndex - 12);
    const to = Math.min(normalized.length, targetIndex + 16);
    let best = null;
    let index = normalized.indexOf(motif, from);
    while (index !== -1 && index < to) {
      const distance = Math.abs(index - targetIndex);
      if (!best || distance < best.distance) best = { start: index, distance };
      index = normalized.indexOf(motif, index + 1);
    }
    return best ? { startBase: best.start + 1, endBase: best.start + motif.length } : null;
  }

  function renderEvidenceSummary(result) {
    const status = result.needs_review ? "Needs review" : "Technical evidence ready";
    evidenceBadge.textContent = status;
    evidenceBadge.dataset.status = result.needs_review ? "review" : "ready";
    const items = [
      ["Target", result.genomic_position ? `NC_000009.12:g.${result.genomic_position}` : "JAK2 V617F"],
      ["Read base", `${result.observed_base || "N/A"} · Q${result.quality_score ?? "N/A"}`],
      ["Alignment", `${formatPercent(result.alignment_identity_percentage)} identity`],
      ["Coverage", formatPercent(result.alignment_coverage_percentage)],
    ];
    jak2Summary.replaceChildren();
    items.forEach(([label, value], index) => {
      const item = document.createElement("div");
      item.className = index === 0 ? "evidence-summary-item evidence-summary-target" : "evidence-summary-item";
      const name = document.createElement("span");
      name.textContent = label;
      const content = document.createElement("strong");
      content.textContent = value;
      item.append(name, content);
      jak2Summary.appendChild(item);
    });
    const pending = document.createElement("div");
    pending.className = "classification-pending";
    pending.innerHTML = '<i class="fa-solid fa-flask"></i><span><strong>Classification pending</strong><small>No predictive model is applied at this stage.</small></span>';
    jak2Summary.appendChild(pending);
  }

  function appendResearchField(container, label, value) {
    const row = document.createElement("div");
    row.className = "research-field";
    const name = document.createElement("span");
    name.textContent = label;
    const content = document.createElement("strong");
    content.textContent = value || "N/A";
    row.append(name, content);
    container.appendChild(row);
  }

  const reviewLabels = {
    approved: "Evidence accepted",
    rejected: "Evidence rejected",
    needs_more_data: "More data requested",
  };

  const reviewNoteTemplates = {
    approved: [
      "Chromatogram peaks are clear and the available QC metrics are acceptable for technical review.",
      "Target-region coverage and signal quality are sufficient for technical review.",
      "The technical evidence is consistent across the chromatogram and QC results.",
    ],
    needs_more_data: [
      "Overlapping peaks near the target region require confirmation with a repeat sequencing run.",
      "Sequence quality around the target region is insufficient; additional data are required.",
      "The available read does not provide enough evidence for technical review.",
    ],
    rejected: [
      "Chromatogram quality is insufficient for reliable technical interpretation.",
      "Technical artefacts prevent reliable review of the target region.",
      "Target-region coverage is inadequate for this analysis.",
    ],
  };

  function syncQuickNoteSelection() {
    reviewQuickNotes.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("selected", button.dataset.note === reviewComment.value.trim());
    });
  }

  function renderQuickNotes(decision) {
    reviewQuickNotes.replaceChildren();
    const notes = reviewNoteTemplates[decision] || [];
    if (!notes.length) {
      const hint = document.createElement("p");
      hint.className = "quick-note-hint";
      hint.textContent = "Choose a decision to see suggested notes.";
      reviewQuickNotes.appendChild(hint);
      return;
    }
    notes.forEach((note) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "quick-note-button";
      button.dataset.note = note;
      button.textContent = note;
      button.addEventListener("click", () => {
        reviewComment.value = note;
        reviewComment.dispatchEvent(new Event("input", { bubbles: true }));
      });
      reviewQuickNotes.appendChild(button);
    });
    syncQuickNoteSelection();
  }

  const auditLabels = {
    "analysis.uploaded": "Analysis uploaded",
    "analysis.preliminary_evidence_recalculated": "JAK2 evidence recalculated",
    "analysis.review_created": "Specialist review recorded",
    "analysis.clinvar_refreshed": "ClinVar research lookup completed",
  };

  function formatAuditDetails(details) {
    if (!details || typeof details !== "object") return "";
    const readable = [];
    if (details.decision) {
      readable.push(`Decision: ${reviewLabels[details.decision] || details.decision}`);
    }
    if (Number.isInteger(details.screened_candidate_count)) {
      readable.push(`Candidates screened: ${details.screened_candidate_count}`);
    }
    if (Number.isInteger(details.matched_annotation_count)) {
      readable.push(`ClinVar matches: ${details.matched_annotation_count}`);
    }
    if (details.qc_status) readable.push(`QC: ${details.qc_status}`);
    return readable.join(" · ");
  }

  function renderAuditTrail(data) {
    const events = Array.isArray(data.events) ? data.events : [];
    auditTimeline.replaceChildren();
    auditCount.textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;
    auditStatus.textContent = events.length
      ? "Audit records are read-only."
      : "No audit events are recorded for this analysis yet.";

    events.forEach((event) => {
      const entry = document.createElement("article");
      entry.className = "audit-entry";
      const marker = document.createElement("span");
      marker.className = "audit-marker";
      marker.setAttribute("aria-hidden", "true");
      const content = document.createElement("div");
      const heading = document.createElement("div");
      heading.className = "audit-entry-heading";
      const action = document.createElement("strong");
      action.textContent = auditLabels[event.action] || event.action;
      const time = document.createElement("time");
      time.dateTime = event.created_at;
      time.textContent = new Date(event.created_at).toLocaleString();
      heading.append(action, time);
      const actor = document.createElement("p");
      actor.textContent = `${event.actor_name} · ${event.actor_role}`;
      content.append(heading, actor);
      const details = formatAuditDetails(event.details);
      if (details) {
        const detail = document.createElement("small");
        detail.textContent = details;
        content.appendChild(detail);
      }
      entry.append(marker, content);
      auditTimeline.appendChild(entry);
    });
  }

  async function loadAuditTrail(token) {
    const response = await fetch(
      `${apiBaseUrl}/analyses/${analysisId}/audit-events`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) throw new Error("Unable to load audit trail.");
    renderAuditTrail(await response.json());
  }

  function renderReviewHistory(data) {
    const reviews = Array.isArray(data.reviews) ? data.reviews : [];
    reviewHistory.replaceChildren();
    reviewHistoryCount.textContent = String(reviews.length);
    latestReviewBadge.textContent = data.latest_decision
      ? reviewLabels[data.latest_decision] || data.latest_decision
      : "Not reviewed";
    latestReviewBadge.dataset.decision = data.latest_decision || "none";

    if (!reviews.length) {
      const empty = document.createElement("p");
      empty.className = "review-empty";
      empty.textContent = "No specialist review has been recorded yet.";
      reviewHistory.appendChild(empty);
      return;
    }

    reviews.forEach((review) => {
      const entry = document.createElement("article");
      entry.className = "review-entry";
      const heading = document.createElement("div");
      heading.className = "review-entry-heading";
      const decision = document.createElement("strong");
      decision.textContent = reviewLabels[review.decision] || review.decision;
      const time = document.createElement("time");
      time.dateTime = review.created_at;
      time.textContent = new Date(review.created_at).toLocaleString();
      heading.append(decision, time);

      const comment = document.createElement("p");
      comment.textContent = review.comment;
      const reviewer = document.createElement("small");
      reviewer.textContent = `${review.reviewer_name} · ${review.reviewer_role}`;
      entry.append(heading, comment, reviewer);
      reviewHistory.appendChild(entry);
    });
  }

  async function loadReviewHistory(token) {
    const response = await fetch(
      `${apiBaseUrl}/analyses/${analysisId}/reviews`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) {
      throw new Error("Unable to load specialist review history.");
    }
    renderReviewHistory(await response.json());
  }

  async function submitReview(event) {
    event.preventDefault();
    const token = window.GeneGlassAuth?.token;
    if (!token || !analysisId) return;
    const selectedDecision = reviewForm.querySelector(
      'input[name="reviewDecision"]:checked'
    );
    if (!selectedDecision) {
      reviewStatus.textContent = "Choose a review decision before saving.";
      reviewForm.querySelector('input[name="reviewDecision"]')?.focus();
      return;
    }

    reviewSubmitButton.disabled = true;
    reviewStatus.textContent = "Saving review…";
    try {
      const response = await fetch(`${apiBaseUrl}/analyses/${analysisId}/reviews`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          decision: selectedDecision.value,
          comment: reviewComment.value.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join("; ")
          : data.detail;
        throw new Error(detail || "Review could not be saved.");
      }
      reviewForm.reset();
      renderQuickNotes("");
      reviewStatus.textContent = "Review saved as a new history entry.";
      await loadReviewHistory(token);
      await loadAuditTrail(token);
    } catch (error) {
      reviewStatus.textContent = error.message;
    } finally {
      reviewSubmitButton.disabled = false;
    }
  }

  function renderResearchResults(data) {
    researchResults.replaceChildren();
    const candidates = (Array.isArray(data.candidates) ? data.candidates : [])
      .filter((candidate) => (candidate.external_annotations || []).some(
        (item) => item.source === "NCBI ClinVar" && item.lookup_status === "matched"
      ));
    if (!candidates.length) {
      researchMatchBadge.textContent = "0 exact matches";
      researchMatchBadge.dataset.state = "empty";
      const empty = document.createElement("p");
      empty.className = "research-empty";
      empty.textContent =
        "No exact ClinVar-matched variants were found among the eligible candidates. " +
        "Unmatched and Needs Review candidates are not displayed as external results.";
      researchResults.appendChild(empty);
      return;
    }

    candidates.forEach((candidate) => {
      const card = document.createElement("article");
      card.className = "research-variant";
      const title = document.createElement("h3");
      title.textContent = candidate.hgvs;
      card.appendChild(title);
      appendResearchField(card, "AB1 base", String(candidate.ab1_base_number));
      if (candidate.genomic_position) {
        appendResearchField(
          card,
          "Genomic position",
          `NC_000009.12:g.${candidate.genomic_position}`
        );
      }
      appendResearchField(card, "Read direction", candidate.direction);
      appendResearchField(card, "Raw AB1 change", candidate.raw_ab1_change);
      appendResearchField(
        card,
        "Reference-oriented change",
        candidate.reference_oriented_change
      );
      appendResearchField(card, "Phred", candidate.phred_quality == null
        ? "N/A" : `Q${candidate.phred_quality}`);
      appendResearchField(card, "Candidate status", candidate.review_status);

      const annotations = Array.isArray(candidate.external_annotations)
        ? candidate.external_annotations : [];
      const clinvar = annotations.find((item) => item.source === "NCBI ClinVar");
      if (clinvar?.lookup_status === "matched") {
        appendResearchField(card, "ClinVar accession", clinvar.accession_version || clinvar.accession);
        const classifications = (clinvar.classifications || []).map((item) =>
          `${item.type}: ${item.description}${item.review_status ? ` (${item.review_status})` : ""}`
        );
        appendResearchField(card, "Published classifications", classifications.join(" · "));
        appendResearchField(card, "Associated conditions", (clinvar.conditions || []).join("; "));
        if (clinvar.source_url) {
          const link = document.createElement("a");
          link.className = "research-source-link";
          link.href = clinvar.source_url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "Open the matched ClinVar record";
          card.appendChild(link);
        }
      }
      researchResults.appendChild(card);
    });
    researchMatchBadge.textContent = `${candidates.length} exact match${candidates.length === 1 ? "" : "es"}`;
    researchMatchBadge.dataset.state = "matched";
  }

  async function loadSavedResearchResults(token) {
    const response = await fetch(
      `${apiBaseUrl}/analyses/${analysisId}/research-variants`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) return;
    const data = await response.json();
    researchStatus.textContent = data.candidate_count > 0
      ? `${data.candidate_count} saved ClinVar-matched variant(s). Research use only.`
      : "No exact ClinVar-matched variants are saved for this analysis.";
    researchMatchBadge.textContent = data.candidate_count > 0
      ? `${data.candidate_count} exact match${data.candidate_count === 1 ? "" : "es"}`
      : "Not searched";
    renderResearchResults(data);
  }

  async function refreshResearchResults() {
    const token = window.GeneGlassAuth?.token;
    if (!token || !analysisId) return;
    researchButton.disabled = true;
    researchButton.textContent = "Searching…";
    researchStatus.textContent =
      "Extracting eligible JAK2 base-call candidates and querying ClinVar by HGVS only…";
    try {
      const response = await fetch(
        `${apiBaseUrl}/analyses/${analysisId}/research-variants/refresh`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Research lookup failed.");
      }
      researchStatus.textContent = data.candidate_count
        ? `${data.candidate_count} candidate(s) displayed; eligible candidates were checked in ClinVar. Research use only.`
        : "No exact ClinVar-matched variants were found. Unmatched candidates are not displayed.";
      renderResearchResults(data);
    } catch (error) {
      researchStatus.textContent = error.message;
    } finally {
      researchButton.disabled = false;
      researchButton.textContent = "Search ClinVar";
    }
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
        ["AB1 file", details.original_file_name],
        ["Uploaded", details.created_at
          ? new Date(details.created_at).toLocaleDateString()
          : "N/A"],
        ["QC status", String(details.qc_status || "pending").replaceAll("_", " ")],
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
  let readDirection = "Forward";
  if (jak2Response.ok) {
    const jak2Data = await jak2Response.json();
    const result = jak2Data.result || {};
    const peaks = result.peak_analysis || {};
    const heights = peaks.peak_heights || {};
    const reasons = Array.isArray(result.review_reasons)
      ? result.review_reasons.filter(Boolean).join("; ")
      : "";
    targetBase = Number(result.ab1_base_number);
    readDirection = result.direction || "Forward";
    renderEvidenceSummary(result);
    showCards(jak2Details, [
      ["AB1 Position", result.ab1_base_number],
      ["Genomic Coordinate", result.genomic_position
        ? `NC_000009.12:g.${result.genomic_position}` : "N/A"],
      ["Transcript Coordinate", result.coding_position
        ? `NM_004972.4:c.${result.coding_position}` : "N/A"],
      ["Direction", result.direction],
      ["Observed Base", result.observed_base],
      ["Target Phred Quality", result.quality_score],
      ["Alignment Identity", formatPercent(result.alignment_identity_percentage)],
      ["Read Coverage", formatPercent(result.alignment_coverage_percentage)],
      ["A Peak", heights.A],
      ["C Peak", heights.C],
      ["G Peak", heights.G],
      ["T Peak", heights.T],
      ["Primary Peak", peaks.primary_base],
      ["Secondary Peak", peaks.secondary_base],
      ["Secondary / Primary", formatRatio(peaks.overlap_ratio)],
      ["Review Status", result.needs_review ? "Needs Review" : "Not flagged"],
      ["Review Reason", reasons || "No preliminary QC review reason"],
      ["Pipeline Version", result.pipeline_version]
    ]);
    const reference = result.reference_evidence;
    if (reference?.url) {
      const referenceCard = document.createElement("div");
      referenceCard.className = "details-item";
      const label = document.createElement("span");
      label.className = "details-label";
      label.textContent = "External Reference";
      const link = document.createElement("a");
      link.className = "details-value";
      link.href = reference.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `${reference.source}: ${reference.accession}`;
      referenceCard.append(label, link);
      jak2Details.append(referenceCard);
    }
  } else {
    jak2Details.textContent = "JAK2 target analysis could not be loaded.";
  }

  if (!traceResponse.ok) throw new Error("Unable to load chromatogram.");
  const trace = await traceResponse.json();
  if (!window.GeneGlassChromatogram) throw new Error("Chromatogram viewer script missing.");
  const motifRange = findNearbyMotif(trace.sequence, targetBase, "ACAT");
  await window.GeneGlassChromatogram.render(trace, {
    targetBase: Number.isInteger(targetBase) && targetBase > 0 ? targetBase : undefined,
    showTitle: false,
    initialBaseCount: 9,
    highlightRange: motifRange,
    initialSequence: "ACAT",
    readDirection,
    compact: true
  });
  document.getElementById("chromatogramLoading").hidden = true;
} catch (error) {
  console.error("Chromatogram / JAK2 error:", error);
  document.getElementById("chromatogramLoading").textContent =
    "Chromatogram could not be loaded: " + error.message;
}



      message.textContent = "";
      await Promise.all([
        loadSavedResearchResults(token),
        loadReviewHistory(token),
        loadAuditTrail(token),
      ]);
    } catch (error) {
      message.textContent = error.message;
    }
  }

  document.addEventListener("geneglass:auth-ready", loadDetails);
  researchButton.addEventListener("click", refreshResearchResults);
  reviewForm.addEventListener("submit", submitReview);
  reviewForm.addEventListener("change", (event) => {
    if (event.target.matches('input[name="reviewDecision"]')) {
      renderQuickNotes(event.target.value);
    }
  });
  reviewComment.addEventListener("input", syncQuickNoteSelection);
  renderQuickNotes(
    reviewForm.querySelector('input[name="reviewDecision"]:checked')?.value || ""
  );

  if (window.GeneGlassAuth?.token) {
    loadDetails();
  }
})();
