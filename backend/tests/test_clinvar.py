"""Tests for reducing ClinVar ESummary data to research annotations."""

from app.core.config import Settings
from app.services.clinvar import ClinVarClient, parse_clinvar_summary


def test_parse_clinvar_summary_keeps_classification_context() -> None:
    result = parse_clinvar_summary({
        "uid": "14662",
        "accession": "VCV000014662",
        "accession_version": "VCV000014662.144",
        "title": "NM_004972.4(JAK2):c.1849G>T (p.Val617Phe)",
        "obj_type": "single nucleotide variant",
        "variation_set": [{
            "variant_type": "single nucleotide variant",
            "canonical_spdi": "NC_000009.12:5073769:G:T",
        }],
        "germline_classification": {
            "description": "Pathogenic/Likely pathogenic",
            "review_status": "criteria provided, multiple submitters, no conflicts",
            "last_evaluated": "2026/07/07 00:00",
            "trait_set": [{"trait_name": "JAK2-related disorder"}],
        },
        "oncogenicity_classification": {
            "description": "Likely oncogenic",
            "review_status": "criteria provided, single submitter",
            "last_evaluated": "2026/10/26 00:00",
            "trait_set": [{"trait_name": "Acute myeloid leukemia"}],
        },
    })

    assert result["source_record_id"] == "14662"
    assert result["accession"] == "VCV000014662"
    assert result["canonical_spdi"] == "NC_000009.12:5073769:G:T"
    assert [item["type"] for item in result["classifications"]] == [
        "Germline",
        "Oncogenicity",
    ]
    assert result["conditions"] == [
        "JAK2-related disorder",
        "Acute myeloid leukemia",
    ]
    assert result["source_url"].endswith("/14662/")


def test_lookup_rejects_a_non_exact_clinvar_title(monkeypatch) -> None:
    client = ClinVarClient(Settings(_env_file=None))
    responses = iter([
        {"esearchresult": {"idlist": ["999"]}},
        {"result": {
            "999": {
                "uid": "999",
                "title": "NM_000000.1(OTHER):c.1849G>T",
                "variation_set": [],
            }
        }},
    ])
    monkeypatch.setattr(client, "_get_json", lambda *_args: next(responses))
    try:
        assert client.lookup_variant("NM_004972.4:c.1849G>T") is None
    finally:
        client._client.close()
