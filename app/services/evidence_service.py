"""
Evidence Service — attaches keccak256 hashes to evidence objects and drives
the full report enrichment pipeline.
"""
from __future__ import annotations

from app.models.schemas import Evidence, GreenReport
from app.services.hash_service import hash_evidence, hash_report
from app.services.merkle_service import build_merkle_root


def enrich_report(report: GreenReport) -> tuple[GreenReport, str, str]:
    """
    Given a raw GreenReport (from AI service):
      1. Hash each evidence item and attach the hash.
      2. Build the Merkle root from evidence hashes.
      3. Hash the full report JSON (including evidence hashes).

    Returns:
        (enriched_report, report_hash_hex, evidence_merkle_root_hex)
    """
    enriched_evidences: list[Evidence] = []
    for ev in report.evidences:
        ev_dict = ev.model_dump(exclude={"hash"})
        ev_hash = hash_evidence(ev_dict)
        enriched_evidences.append(ev.model_copy(update={"hash": ev_hash}))

    enriched_report = report.model_copy(update={"evidences": enriched_evidences})

    # Build Merkle root from evidence hashes
    ev_hashes = [ev.hash for ev in enriched_evidences]
    merkle_root = build_merkle_root(ev_hashes)

    # Hash the full enriched report
    report_dict = enriched_report.model_dump()
    r_hash = hash_report(report_dict)

    return enriched_report, r_hash, merkle_root
