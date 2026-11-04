"""Minimal NCBI ClinVar client for research-only variant annotations."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import Settings

EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CLINVAR_SOURCE = "NCBI ClinVar"


class ClinVarServiceError(RuntimeError):
    """Raised when ClinVar cannot be reached or returns invalid data."""


def _classification_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    keys = {
        "germline_classification": "Germline",
        "clinical_impact_classification": "Somatic clinical impact",
        "oncogenicity_classification": "Oncogenicity",
    }
    items = []
    for key, label in keys.items():
        value = summary.get(key) or {}
        description = str(value.get("description") or "").strip()
        if not description:
            continue
        items.append({
            "type": label,
            "description": description,
            "review_status": str(value.get("review_status") or "").strip() or None,
            "last_evaluated": str(value.get("last_evaluated") or "").strip() or None,
        })
    return items


def parse_clinvar_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Reduce an NCBI ESummary record to fields safe for local display."""

    classifications = _classification_items(summary)
    conditions = []
    for key in (
        "germline_classification",
        "clinical_impact_classification",
        "oncogenicity_classification",
    ):
        for trait in (summary.get(key) or {}).get("trait_set") or []:
            name = str(trait.get("trait_name") or "").strip()
            if name and name.lower() != "not provided" and name not in conditions:
                conditions.append(name)

    variation = next(iter(summary.get("variation_set") or []), {})
    review_statuses = []
    for item in classifications:
        status = item.get("review_status")
        if status and status not in review_statuses:
            review_statuses.append(status)

    variation_id = str(summary.get("uid") or "").strip()
    return {
        "source": CLINVAR_SOURCE,
        "lookup_status": "matched",
        "source_record_id": variation_id or None,
        "accession": summary.get("accession"),
        "accession_version": summary.get("accession_version"),
        "title": summary.get("title"),
        "variant_type": variation.get("variant_type") or summary.get("obj_type"),
        "canonical_spdi": variation.get("canonical_spdi"),
        "classifications": classifications,
        "conditions": conditions,
        "review_status": "; ".join(review_statuses) or None,
        "source_url": (
            f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{variation_id}/"
            if variation_id else None
        ),
    }


class ClinVarClient:
    """Rate-limited client using NCBI ESearch followed by ESummary."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_request = 0.0
        self._minimum_interval = 0.11 if settings.ncbi_api_key else 0.34
        self._client = httpx.Client(
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": f"{settings.ncbi_tool}/0.1"},
        )

    def __enter__(self) -> "ClinVarClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self._client.close()

    def _common_params(self) -> dict[str, str]:
        params = {"tool": self.settings.ncbi_tool}
        if self.settings.ncbi_email:
            params["email"] = self.settings.ncbi_email
        if self.settings.ncbi_api_key:
            params["api_key"] = self.settings.ncbi_api_key
        return params

    def _get_json(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._minimum_interval:
            time.sleep(self._minimum_interval - elapsed)

        try:
            response = self._client.get(
                f"{EUTILS_BASE_URL}/{endpoint}",
                params={**self._common_params(), **params},
            )
            self._last_request = time.monotonic()
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ClinVarServiceError("ClinVar request failed") from exc

        if not isinstance(payload, dict):
            raise ClinVarServiceError("ClinVar returned an unexpected response")
        return payload

    def lookup_variant(self, hgvs: str) -> dict[str, Any] | None:
        """Look up one normalized HGVS expression without sending AB1 data."""

        search = self._get_json(
            "esearch.fcgi",
            {
                "db": "clinvar",
                "term": hgvs,
                "retmode": "json",
                "retmax": "5",
            },
        )
        identifiers = (search.get("esearchresult") or {}).get("idlist") or []
        if not identifiers:
            return None

        summaries = self._get_json(
            "esummary.fcgi",
            {
                "db": "clinvar",
                "id": ",".join(str(value) for value in identifiers),
                "retmode": "json",
            },
        ).get("result") or {}

        records = [
            summaries.get(str(identifier))
            for identifier in identifiers
            if isinstance(summaries.get(str(identifier)), dict)
        ]
        if not records:
            raise ClinVarServiceError("ClinVar returned no usable summaries")

        accession, change = (part.lower() for part in hgvs.split(":", 1))
        exact = next(
            (
                record for record in records
                if accession in str(record.get("title") or "").lower()
                and change in str(record.get("title") or "").lower()
            ),
            None,
        )
        return parse_clinvar_summary(exact) if exact is not None else None
