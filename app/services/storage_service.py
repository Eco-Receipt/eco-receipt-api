"""
Storage Service — persists report and ERC-721 metadata JSON files.

Reports are always saved locally because they can be large.
Metadata uses STORAGE_BACKEND:
  - "local"  writes to app/data/metadata/.
  - "pinata" uploads JSON to IPFS through Pinata.

URI scheme:
  - reports:        "local://reports/<filename>"
  - local metadata: "local://metadata/<filename>"
  - pinata metadata:"ipfs://<cid>"
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.hash_service import hash_report


class StorageServiceError(Exception):
    """Raised when JSON persistence or remote pinning fails."""


def _write_json(directory: Path, filename: str, data: dict[str, Any]) -> str:
    """Write *data* as pretty-printed JSON to *directory/filename*."""
    directory.mkdir(parents=True, exist_ok=True)
    filepath = directory / filename
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(filepath)


def _storage_backend() -> str:
    return settings.storage_backend.strip().lower()


def _report_filename(report_hash: str) -> str:
    slug = report_hash.removeprefix("0x")[:16]
    return f"{slug}.json"


def _pinata_headers() -> dict[str, str]:
    if settings.pinata_jwt:
        return {"Authorization": f"Bearer {settings.pinata_jwt}"}

    if settings.pinata_api_key and settings.pinata_secret_api_key:
        return {
            "pinata_api_key": settings.pinata_api_key,
            "pinata_secret_api_key": settings.pinata_secret_api_key,
        }

    raise StorageServiceError(
        "Pinata credentials are not configured. Set PINATA_JWT or "
        "PINATA_API_KEY + PINATA_SECRET_API_KEY."
    )


def _pin_json_to_pinata(data: dict[str, Any], filename: str) -> tuple[str, str]:
    payload = {
        "pinataMetadata": {"name": filename},
        "pinataContent": data,
    }

    try:
        response = httpx.post(
            settings.pinata_api_url,
            headers=_pinata_headers(),
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise StorageServiceError(
            f"Pinata upload failed with HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise StorageServiceError(f"Pinata upload failed: {exc}") from exc

    result = response.json()
    cid = result.get("IpfsHash")
    if not cid:
        raise StorageServiceError(f"Pinata response missing IpfsHash: {result}")

    return f"ipfs://{cid}", cid


def _persist_metadata(data: dict[str, Any], filename: str) -> tuple[str, str]:
    backend = _storage_backend()
    local_uri = f"local://metadata/{filename}"

    if backend == "local":
        _write_json(settings.metadata_dir, filename, data)
        return local_uri, filename

    if backend in {"pinata", "ipfs"}:
        # Keep a local copy for debugging even when the canonical metadata URI is IPFS.
        _write_json(settings.metadata_dir, filename, data)
        return _pin_json_to_pinata(data, filename)

    raise StorageServiceError(
        f"Unknown STORAGE_BACKEND: {settings.storage_backend!r}. Choose 'local' or 'pinata'."
    )


def save_report(report_dict: dict[str, Any], report_hash: str) -> tuple[str, str]:
    """
    Save the full report JSON.

    Returns:
        (uri, filename) e.g. ("local://reports/abc123.json", "abc123.json")
    """
    # Use first 16 chars of hash as deterministic filename component
    filename = _report_filename(report_hash)
    _write_json(settings.reports_dir, filename, report_dict)
    return f"local://reports/{filename}", filename


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
        (uri, identifier)
        local:  ("local://metadata/abc123_meta.json", "abc123_meta.json")
        pinata: ("ipfs://<cid>", "<cid>")
    """
    slug = report_hash.removeprefix("0x")[:16]
    filename = f"{slug}_meta.json"

    metadata: dict[str, Any] = {
        "name": f"Green Receipt - {product_name}",
        "description": "AI-generated environmental forensic receipt anchored on Monad",
        "image": "",
        "reportHash": report_hash,
        "evidenceMerkleRoot": evidence_merkle_root,
        "reportURI": report_uri,
        "attributes": [
            {"trait_type": "Brand", "value": brand},
            {"trait_type": "Score", "value": score},
            {"trait_type": "Grade", "value": grade},
            {"trait_type": "Evidence Root", "value": evidence_merkle_root},
            {"trait_type": "Report Hash", "value": report_hash},
        ],
    }

    return _persist_metadata(metadata, filename)


def load_report(filename: str) -> dict[str, Any] | None:
    """Load a saved report JSON by filename. Returns None if not found."""
    filepath = settings.reports_dir / filename
    if not filepath.exists():
        return None
    return json.loads(filepath.read_text(encoding="utf-8"))


def load_report_by_hash(report_hash: str) -> tuple[dict[str, Any], str] | None:
    """
    Load a saved report by its canonical report hash.

    The filename is derived from the first 16 hex chars of the hash, then the
    stored JSON is re-hashed to ensure the local file still matches the request.
    """
    filename = _report_filename(report_hash)
    report = load_report(filename)
    if report is None:
        return None

    actual_hash = hash_report(report)
    if actual_hash.lower() != report_hash.lower():
        raise StorageServiceError(
            f"Stored report hash mismatch for {filename}: expected {report_hash}, got {actual_hash}"
        )

    return report, f"local://reports/{filename}"


def load_metadata(filename: str) -> dict[str, Any] | None:
    """Load a saved metadata JSON by filename. Returns None if not found."""
    filepath = settings.metadata_dir / filename
    if not filepath.exists():
        return None
    return json.loads(filepath.read_text(encoding="utf-8"))
