"""
Web3 Service — interacts with the GreenReceiptNFT contract on Monad.

Key behaviours:
  • Reads ABI from abi/GreenReceiptNFT.json
  • Signs and broadcasts mintReceipt() via the configured PRIVATE_KEY
  • Waits for transaction receipt
  • Parses tokenId from ReceiptMinted event log
  • Raises descriptive errors on common failure modes
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from web3 import Web3
from web3.exceptions import ContractLogicError

from app.config import settings
from app.services.hash_service import hex_to_bytes32

logger = logging.getLogger(__name__)


class Web3ServiceError(Exception):
    """Raised for any Web3 / contract interaction error."""


def _load_abi() -> list[dict]:
    abi_path: Path = settings.abi_path
    if not abi_path.exists():
        raise Web3ServiceError(
            f"ABI file not found at {abi_path}. "
            "Copy your compiled ABI JSON into abi/GreenReceiptNFT.json."
        )
    raw = json.loads(abi_path.read_text(encoding="utf-8"))
    # Support both bare array and {"abi": [...]} formats
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "abi" in raw:
        return raw["abi"]
    raise Web3ServiceError("Unexpected ABI format. Expected a JSON array or {'abi': [...]}.")


def _get_web3() -> Web3:
    if not settings.monad_rpc_url:
        raise Web3ServiceError("MONAD_RPC_URL is not configured.")
    w3 = Web3(Web3.HTTPProvider(settings.monad_rpc_url))
    if not w3.is_connected():
        raise Web3ServiceError(
            f"Cannot connect to RPC endpoint: {settings.monad_rpc_url}"
        )
    return w3


def _get_account(w3: Web3):
    if not settings.private_key:
        raise Web3ServiceError("PRIVATE_KEY is not configured.")
    return w3.eth.account.from_key(settings.private_key)


def _get_contract(w3: Web3):
    if not settings.contract_address:
        raise Web3ServiceError("CONTRACT_ADDRESS is not configured.")
    address = Web3.to_checksum_address(settings.contract_address)
    abi = _load_abi()
    return w3.eth.contract(address=address, abi=abi)


def mint_receipt(
    to: str,
    product_name: str,
    brand: str,
    score: int,
    grade: str,
    report_hash_hex: str,
    evidence_merkle_root_hex: str,
    metadata_uri: str,
) -> tuple[int, str]:
    """
    Call mintReceipt() on the GreenReceiptNFT contract.

    Parameters
    ----------
    to : str
        Recipient wallet address (checksummed or plain hex).
    product_name, brand, score, grade : report fields
    report_hash_hex : '0x'-prefixed 64-char hex (bytes32)
    evidence_merkle_root_hex : '0x'-prefixed 64-char hex (bytes32)
    metadata_uri : URI string stored in the NFT

    Returns
    -------
    (token_id, transaction_hash_hex)
    """
    w3 = _get_web3()
    account = _get_account(w3)
    contract = _get_contract(w3)

    to_address = Web3.to_checksum_address(to)
    report_hash_bytes = hex_to_bytes32(report_hash_hex)
    merkle_root_bytes = hex_to_bytes32(evidence_merkle_root_hex)

    nonce = w3.eth.get_transaction_count(account.address, "pending")

    try:
        tx = contract.functions.mintReceipt(
            to_address,
            product_name,
            brand,
            score,
            grade,
            report_hash_bytes,
            merkle_root_bytes,
            metadata_uri,
        ).build_transaction(
            {
                "from": account.address,
                "nonce": nonce,
                "chainId": settings.chain_id,
                "gas": 1_500_000,
                "gasPrice": w3.eth.gas_price,
            }
        )
    except ContractLogicError as exc:
        raise Web3ServiceError(f"Contract reverted while building transaction: {exc}") from exc

    signed_tx = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    logger.info("mintReceipt tx sent: %s", tx_hash.hex())

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] != 1:
        raise Web3ServiceError(
            f"Transaction {tx_hash.hex()} reverted on-chain. "
            "Check gas, contract state, and caller permissions."
        )

    token_id = _parse_token_id(contract, receipt)
    logger.info("mintReceipt success tokenId=%d tx=%s", token_id, tx_hash.hex())
    return token_id, "0x" + tx_hash.hex()


def _parse_token_id(contract, receipt) -> int:
    """Extract tokenId from the ReceiptMinted event in the transaction receipt."""
    try:
        events = contract.events.ReceiptMinted().process_receipt(receipt)
        if events:
            return events[0]["args"]["tokenId"]
    except Exception as exc:
        logger.warning("Could not decode ReceiptMinted event: %s", exc)

    # Fallback: scan raw logs for Transfer event (ERC-721 standard)
    # Transfer(address indexed from, address indexed to, uint256 indexed tokenId)
    transfer_topic = Web3.keccak(text="Transfer(address,address,uint256)")
    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if topics and topics[0] == transfer_topic and len(topics) >= 4:
            return int(topics[3].hex(), 16)

    raise Web3ServiceError("Could not extract tokenId from transaction receipt.")
