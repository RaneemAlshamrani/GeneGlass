# JAK2 Reference Provenance

- `JAK2_NC_000009.12_5073170_5074370.fasta`: GRCh38 chromosome 9 window, 1-based inclusive coordinates 5,073,170–5,074,370, retrieved from NCBI E-utilities on 2026-11-05. SHA-256: `76db990850d1067e97bcc0b3bf7ce983b77a3480a86867079fbf89b707ddb201`. This is the alignment reference for genomic PCR/Sanger reads.
- `JAK2_NM_004972.4.fasta`: JAK2 transcript reference used to convert exonic genomic coordinates to transcript/coding HGVS. SHA-256: `676750c5ac6f5a8245201ef0091aae9f8bd98e6563d8c94d07af242719e51994`.

The V617F target is pinned to `NC_000009.12:g.5073770G>T`, corresponding to `NM_004972.4:c.1849G>T`. Runtime analysis uses only these local pinned files; it does not download a changing reference during a request.
