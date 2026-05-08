"""
Binary Merkle Tree using keccak256 — Solidity/OpenZeppelin compatible.

Leaf hashing strategy:
  leaf = keccak256(keccak256(data))   ← OpenZeppelin MerkleProof standard

For MVP simplicity we accept pre-hashed leaf values (evidence hashes already
computed by hash_service) and build the tree from those.  If the number of
leaves is odd, the last leaf is duplicated before each merge step — matching
the common Solidity implementation convention.
"""
from __future__ import annotations

from eth_hash.auto import keccak


def _keccak256(data: bytes) -> bytes:
    return keccak(data)


def _hash_pair(a: bytes, b: bytes) -> bytes:
    """Sort + hash a sibling pair (matches OpenZeppelin's MerkleProof sorting)."""
    if a <= b:
        return _keccak256(a + b)
    return _keccak256(b + a)


def build_merkle_root(evidence_hashes: list[str]) -> str:
    """
    Build a Merkle root from a list of '0x'-prefixed evidence hash strings.

    Returns '0x'-prefixed 64-char hex string.
    Raises ValueError if the input list is empty.
    """
    if not evidence_hashes:
        raise ValueError("Cannot build Merkle root from empty evidence list.")

    # Convert hex strings → bytes
    leaves: list[bytes] = [bytes.fromhex(h.removeprefix("0x")) for h in evidence_hashes]

    # Single leaf — root is the leaf itself
    if len(leaves) == 1:
        return "0x" + leaves[0].hex()

    current_layer = leaves

    while len(current_layer) > 1:
        next_layer: list[bytes] = []
        # Pad odd-length layers by duplicating the last element
        if len(current_layer) % 2 == 1:
            current_layer = current_layer + [current_layer[-1]]

        for i in range(0, len(current_layer), 2):
            next_layer.append(_hash_pair(current_layer[i], current_layer[i + 1]))

        current_layer = next_layer

    return "0x" + current_layer[0].hex()


def get_merkle_proof(evidence_hashes: list[str], index: int) -> list[str]:
    """
    Return the Merkle proof (sibling hashes) for the leaf at *index*.
    Useful for on-chain verification via OpenZeppelin MerkleProof.verify().
    """
    if not evidence_hashes:
        raise ValueError("Empty evidence list.")

    leaves: list[bytes] = [bytes.fromhex(h.removeprefix("0x")) for h in evidence_hashes]
    proof: list[str] = []
    current_layer = leaves
    current_index = index

    while len(current_layer) > 1:
        if len(current_layer) % 2 == 1:
            current_layer = current_layer + [current_layer[-1]]

        if current_index % 2 == 0:
            sibling_index = current_index + 1
        else:
            sibling_index = current_index - 1

        proof.append("0x" + current_layer[sibling_index].hex())

        next_layer: list[bytes] = []
        for i in range(0, len(current_layer), 2):
            next_layer.append(_hash_pair(current_layer[i], current_layer[i + 1]))

        current_layer = next_layer
        current_index //= 2

    return proof
