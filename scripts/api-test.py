from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import requests


DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_PRODUCT_NAME = "Nike Pegasus Trail 5 DV3865-602"
DEFAULT_PRODUCT_URL = ""
DEFAULT_BRAND = "Nike"
DEFAULT_TIMEOUT = 180


class ApiTestError(RuntimeError):
    pass


def print_section(title: str) -> None:
    print(f"\n{'=' * 80}")
    print(title)
    print("=" * 80)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def parse_json_response(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout: int,
    json_body: dict[str, Any] | None = None,
) -> Any:
    print(f"{method} {url}")
    if json_body is not None:
        print("Request:")
        print_json(json_body)

    response = session.request(method, url, json=json_body, timeout=timeout)
    body = parse_json_response(response)

    print(f"Status: {response.status_code}")
    print("Response:")
    print_json(body)

    if response.status_code >= 400:
        raise ApiTestError(f"Request failed: {method} {url} -> {response.status_code}")

    return body


def test_health(session: requests.Session, base_url: str, timeout: int) -> dict[str, Any]:
    print_section("Health Check")
    return request_json(session, "GET", f"{base_url}/health", timeout=timeout)


def test_analyze(
    session: requests.Session,
    base_url: str,
    timeout: int,
    *,
    product_name: str,
    product_url: str,
    brand: str,
) -> dict[str, Any]:
    print_section("Analyze Receipt")
    payload = {
        "productName": product_name,
        "productUrl": product_url,
        "brand": brand,
    }
    return request_json(
        session,
        "POST",
        f"{base_url}/api/receipts/analyze",
        timeout=timeout,
        json_body=payload,
    )


def test_mint(
    session: requests.Session,
    base_url: str,
    timeout: int,
    *,
    analyze_result: dict[str, Any],
    to: str,
) -> dict[str, Any]:
    print_section("Mint Receipt")
    payload = {
        "to": to,
        "productName": analyze_result["productName"],
        "brand": analyze_result["brand"],
        "score": analyze_result["score"],
        "grade": analyze_result["grade"],
        "reportHash": analyze_result["reportHash"],
        "evidenceMerkleRoot": analyze_result["evidenceMerkleRoot"],
        "metadataURI": analyze_result["metadataURI"],
    }
    return request_json(
        session,
        "POST",
        f"{base_url}/api/receipts/mint",
        timeout=timeout,
        json_body=payload,
    )


def test_analyze_and_mint(
    session: requests.Session,
    base_url: str,
    timeout: int,
    *,
    product_name: str,
    product_url: str,
    brand: str,
    to: str,
) -> dict[str, Any]:
    print_section("Analyze And Mint Receipt")
    payload = {
        "productName": product_name,
        "productUrl": product_url,
        "brand": brand,
        "to": to,
    }
    return request_json(
        session,
        "POST",
        f"{base_url}/api/receipts/analyze-and-mint",
        timeout=timeout,
        json_body=payload,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Call Green Receipt API endpoints with Python requests."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL. Default: {DEFAULT_BASE_URL!r} or API_BASE_URL env.",
    )
    parser.add_argument(
        "--product-name",
        default=DEFAULT_PRODUCT_NAME,
        help=f"Product name for analyze endpoints. Default: {DEFAULT_PRODUCT_NAME!r}.",
    )
    parser.add_argument(
        "--product-url",
        default=DEFAULT_PRODUCT_URL,
        help="Product URL for analyze endpoints. Default: empty string.",
    )
    parser.add_argument(
        "--brand",
        default=DEFAULT_BRAND,
        help=f"Brand for analyze endpoints. Default: {DEFAULT_BRAND!r}.",
    )
    parser.add_argument(
        "--to",
        default=os.getenv("TEST_RECIPIENT", ""),
        help="NFT recipient address. Required for --mint or --analyze-and-mint. Can also use TEST_RECIPIENT env.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds. Default: {DEFAULT_TIMEOUT}.",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Skip GET /health.",
    )
    parser.add_argument(
        "--skip-analyze",
        action="store_true",
        help="Skip POST /api/receipts/analyze.",
    )
    parser.add_argument(
        "--mint",
        action="store_true",
        help="After analyze succeeds, call POST /api/receipts/mint.",
    )
    parser.add_argument(
        "--analyze-and-mint",
        action="store_true",
        help="Call POST /api/receipts/analyze-and-mint.",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if (args.mint or args.analyze_and_mint) and not args.to:
        raise ApiTestError(
            "--to is required for mint tests. Example: --to 0x1111111111111111111111111111111111111111"
        )
    if args.mint and args.skip_analyze:
        raise ApiTestError("--mint depends on analyze result, so it cannot be used with --skip-analyze.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        validate_args(args)
    except ApiTestError as exc:
        parser.error(str(exc))

    base_url = args.base_url.rstrip("/")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    analyze_result: dict[str, Any] | None = None

    try:
        if not args.skip_health:
            test_health(session, base_url, args.timeout)

        if not args.skip_analyze:
            analyze_result = test_analyze(
                session,
                base_url,
                args.timeout,
                product_name=args.product_name,
                product_url=args.product_url,
                brand=args.brand,
            )

        if args.mint:
            if analyze_result is None:
                raise ApiTestError("Analyze result is missing.")
            test_mint(
                session,
                base_url,
                args.timeout,
                analyze_result=analyze_result,
                to=args.to,
            )

        if args.analyze_and_mint:
            test_analyze_and_mint(
                session,
                base_url,
                args.timeout,
                product_name=args.product_name,
                product_url=args.product_url,
                brand=args.brand,
                to=args.to,
            )

    except requests.RequestException as exc:
        print(f"\nHTTP request failed: {exc}", file=sys.stderr)
        return 1
    except ApiTestError as exc:
        print(f"\nAPI test failed: {exc}", file=sys.stderr)
        return 1

    print_section("Done")
    print("All selected API tests completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
