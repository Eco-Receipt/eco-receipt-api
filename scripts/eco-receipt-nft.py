from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ABI_PATH = PROJECT_ROOT / "abi" / "EcoReceiptNFT.abi.json"
DEFAULT_CONTRACT_ADDRESS = "0x5dceddd6fd5a9f770b7585b9194ffa5b40a13f4d"
DEFAULT_RPC_URL = "https://testnet-rpc.monad.xyz"

RECEIPT_FIELDS = [
    "tokenId",
    "productName",
    "brand",
    "score",
    "grade",
    "reportHash",
    "evidenceMerkleRoot",
    "metadataURI",
    "timestamp",
    "creator",
    "auditor",
]

INTERFACES = {
    "ERC165": "0x01ffc9a7",
    "ERC721": "0x80ac58cd",
    "ERC721Metadata": "0x5b5e139f",
    "ERC4906MetadataUpdate": "0x49064906",
}


class NftStatusError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def print_section(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print("=" * 80)


def print_json(data: Any) -> None:
    print(json.dumps(to_jsonable(data), ensure_ascii=False, indent=2))


def timestamp_to_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def call_view(label: str, fn: Callable[[], Any], *, required: bool = False) -> Any | None:
    try:
        return fn()
    except ContractLogicError as exc:
        if required:
            raise NftStatusError(f"{label} reverted: {exc}") from exc
        print(f"[WARN] {label} reverted: {exc}")
    except Exception as exc:
        if required:
            raise NftStatusError(f"{label} failed: {exc}") from exc
        print(f"[WARN] {label} failed: {exc}")
    return None


def connect(rpc_url: str, contract_address: str, abi_path: Path):
    if not abi_path.exists():
        raise NftStatusError(f"ABI file not found: {abi_path}")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise NftStatusError(f"Cannot connect to RPC endpoint: {rpc_url}")

    checksum_address = Web3.to_checksum_address(contract_address)
    abi = load_json(abi_path)
    contract = w3.eth.contract(address=checksum_address, abi=abi)
    return w3, contract


def query_chain_status(w3: Web3, contract_address: str) -> None:
    print_section("Chain / Contract")
    code = w3.eth.get_code(contract_address)
    data = {
        "connected": True,
        "chainId": w3.eth.chain_id,
        "latestBlock": w3.eth.block_number,
        "gasPriceWei": w3.eth.gas_price,
        "contractAddress": contract_address,
        "contractHasCode": len(code) > 0,
        "contractCodeSizeBytes": len(code),
    }
    print_json(data)


def query_contract_status(contract) -> None:
    print_section("NFT Basic Status")

    data = {
        "name": call_view("name()", lambda: contract.functions.name().call()),
        "symbol": call_view("symbol()", lambda: contract.functions.symbol().call()),
        "owner": call_view("owner()", lambda: contract.functions.owner().call()),
        "interfaces": {},
    }

    for name, interface_id in INTERFACES.items():
        data["interfaces"][name] = call_view(
            f"supportsInterface({interface_id})",
            lambda interface_id=interface_id: contract.functions.supportsInterface(
                bytes.fromhex(interface_id.removeprefix("0x"))
            ).call(),
        )

    print_json(data)


def query_address_status(contract, address: str) -> None:
    checksum_address = Web3.to_checksum_address(address)

    print_section(f"Address Status: {checksum_address}")
    data = {
        "address": checksum_address,
        "balanceOf": call_view(
            "balanceOf(address)",
            lambda: contract.functions.balanceOf(checksum_address).call(),
        ),
        "isAuditor": call_view(
            "isAuditor(address)",
            lambda: contract.functions.isAuditor(checksum_address).call(),
        ),
    }
    print_json(data)


def query_token_status(contract, token_id: int) -> None:
    print_section(f"Token Status: #{token_id}")

    exists = call_view("exists(tokenId)", lambda: contract.functions.exists(token_id).call())
    data: dict[str, Any] = {
        "tokenId": token_id,
        "exists": exists,
    }

    if exists:
        data["ownerOf"] = call_view("ownerOf(tokenId)", lambda: contract.functions.ownerOf(token_id).call())
        data["tokenURI"] = call_view("tokenURI(tokenId)", lambda: contract.functions.tokenURI(token_id).call())
        data["approved"] = call_view(
            "getApproved(tokenId)",
            lambda: contract.functions.getApproved(token_id).call(),
        )

        receipt = call_view("getReceipt(tokenId)", lambda: contract.functions.getReceipt(token_id).call())
        if receipt is not None:
            receipt_data = dict(zip(RECEIPT_FIELDS, to_jsonable(receipt), strict=False))
            timestamp = receipt_data.get("timestamp")
            if isinstance(timestamp, int) and timestamp > 0:
                receipt_data["timestampISO"] = timestamp_to_iso(timestamp)
            data["receipt"] = receipt_data

    print_json(data)


def query_recent_receipt_events(w3: Web3, contract, blocks: int) -> None:
    latest_block = w3.eth.block_number
    from_block = max(0, latest_block - blocks + 1)

    print_section(f"Recent ReceiptMinted Events: blocks {from_block}..{latest_block}")

    try:
        events = contract.events.ReceiptMinted().get_logs(
            fromBlock=from_block,
            toBlock=latest_block,
        )
    except Exception as exc:
        print_json(
            {
                "error": str(exc),
                "hint": "Try a smaller --events-blocks value if the RPC endpoint limits log ranges.",
            }
        )
        return

    data = []
    for event in events:
        args = dict(event["args"])
        data.append(
            {
                "blockNumber": event["blockNumber"],
                "transactionHash": to_jsonable(event["transactionHash"]),
                "logIndex": event["logIndex"],
                "args": to_jsonable(args),
            }
        )

    print_json(
        {
            "fromBlock": from_block,
            "toBlock": latest_block,
            "count": len(data),
            "events": data,
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query EcoReceiptNFT contract status.")
    parser.add_argument(
        "--rpc-url",
        default=os.getenv("MONAD_RPC_URL", DEFAULT_RPC_URL),
        help="RPC endpoint. Defaults to MONAD_RPC_URL from .env or Monad testnet RPC.",
    )
    parser.add_argument(
        "--contract",
        default=os.getenv("ECO_RECEIPT_NFT_ADDRESS", DEFAULT_CONTRACT_ADDRESS),
        help="EcoReceiptNFT contract address.",
    )
    parser.add_argument(
        "--abi",
        type=Path,
        default=DEFAULT_ABI_PATH,
        help=f"ABI path. Default: {DEFAULT_ABI_PATH}.",
    )
    parser.add_argument(
        "--address",
        help="Optional wallet address to query balanceOf and isAuditor.",
    )
    parser.add_argument(
        "--token-id",
        type=int,
        help="Optional token id to query exists, ownerOf, tokenURI and getReceipt.",
    )
    parser.add_argument(
        "--events",
        action="store_true",
        help="Query recent ReceiptMinted events.",
    )
    parser.add_argument(
        "--events-blocks",
        type=int,
        default=2_000,
        help="Block range for --events. Default: 2000.",
    )
    return parser


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    parser = build_parser()
    args = parser.parse_args()

    try:
        w3, contract = connect(args.rpc_url, args.contract, args.abi)
        query_chain_status(w3, contract.address)
        query_contract_status(contract)

        if args.address:
            query_address_status(contract, args.address)

        if args.token_id is not None:
            query_token_status(contract, args.token_id)

        if args.events:
            query_recent_receipt_events(w3, contract, args.events_blocks)

    except NftStatusError as exc:
        print(f"Error: {exc}")
        return 1
    except ValueError as exc:
        print(f"Invalid value: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
