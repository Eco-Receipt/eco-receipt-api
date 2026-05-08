"""
keccak256 hashing utilities — Solidity-compatible.

All hashes are returned as '0x'-prefixed hex strings (64 hex chars after 0x).
Evidence hashes are derived from canonicalized JSON so the same data always
produces the same hash regardless of key insertion order.
"""
from __future__ import annotations

import json
from typing import Any

from eth_hash.auto import keccak


def _keccak256(data: bytes) -> str:
    """Return '0x' + keccak256(data) hex string."""
    return "0x" + keccak(data).hex()


def hash_evidence(evidence_dict: dict[str, Any]) -> str:
    """
    Produce a stable keccak256 hash for a single evidence object.

    Keys are sorted and the value is serialised with compact separators so the
    same logical evidence always yields the same hash (matches on-chain
    behaviour when the backend is the canonical source).
    """
    # Exclude the 'hash' field itself to avoid circular dependency
    clean = {k: v for k, v in evidence_dict.items() if k != "hash"}
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _keccak256(canonical.encode("utf-8"))


def hash_report(report_dict: dict[str, Any]) -> str:
    """
    Produce a keccak256 hash of the full report JSON.

    Evidences are included with their computed hashes so the report hash
    covers the complete Merkle leaf set.
    """
    canonical = json.dumps(report_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _keccak256(canonical.encode("utf-8"))


def hex_to_bytes32(hex_str: str) -> bytes:
    """Convert a '0x'-prefixed 64-char hex string to a 32-byte bytes object."""
    return bytes.fromhex(hex_str.removeprefix("0x"))
