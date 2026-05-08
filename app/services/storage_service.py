"""
Storage Service — persists report and ERC-721 metadata JSON files.

Backend: "local" (default) writes to app/data/reports/ and app/data/metadata/.
         Replace save_report() / save_metadata() bodies to switch to IPFS/Arweave.

URI scheme: "local://reports/<filename>" and "local://metadata/<filename>"
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.config import settings


def _write_json(directory: Path, filename: str, data: dict[str, Any]) -> str:
    """Write *data* as pretty-printed JSON to *directory/filename*."""
    directory.mkdir(parents=True, exist_ok=True)
    filepath = directory / filename
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(filepath)


def save_report(report_dict: dict[str, Any], report_hash: str) -> tuple[str, str]:
    """
    Save the full report JSON.

    Returns:
        (uri, filename)  e.g. ("local://reports/abc123.json", "abc123.json")
    """
    # Use first 16 chars of hash as deterministic filename component
    slug = report_hash.removeprefix("0x")[:16]
    filename = f"{slug}.json"
    _write_json(settings.reports_dir, filename, report_dict)
    uri = f"local://reports/{filename}"
    return uri, filename


def save_metadata(
    product_name: str,
    brand: str,
    score: int,
    grade: str,
    report_hash: str,
    evidence_merkle_root: str,
    report_uri: str,
) -> tuple[str, str]:
    """
    Save ERC-721 compliant metadata JSON.

    Returns:
        (uri, filename)  e.g. ("local://metadata/abc123_meta.json", "abc123_meta.json")
    """
    slug = report_hash.removeprefix("0x")[:16]
    filename = f"{slug}_meta.json"

    metadata: dict[str, Any] = {
        "name": f"Green Receipt - {product_name}",
        "description": "AI-generated environmental forensic receipt anchored on Monad",
        "image": "",
        "attributes": [
            {"trait_type": "Brand", "value": brand},
            {"trait_type": "Score", "value": score},
            {"trait_type": "Grade", "value": grade},
            {"trait_type": "Evidence Root", "value": evidence_merkle_root},
            {"trait_type": "Report Hash", "value": report_hash},
        ],
        "reportURI": report_uri,
    }

    _write_json(settings.metadata_dir, filename, metadata)
    uri = f"local://metadata/{filename}"
    return uri, filename


def load_report(filename: str) -> dict[str, Any] | None:
    """Load a saved report JSON by filename. Returns None if not found."""
    filepath = settings.reports_dir / filename
    if not filepath.exists():
        return None
    return json.loads(filepath.read_text(encoding="utf-8"))


def load_metadata(filename: str) -> dict[str, Any] | None:
    """Load a saved metadata JSON by filename. Returns None if not found."""
    filepath = settings.metadata_dir / filename
    if not filepath.exists():
        return None
    return json.loads(filepath.read_text(encoding="utf-8"))
