from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.schemas import (
    AnalyzeAndMintRequest,
    AnalyzeAndMintResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    MintRequest,
    MintResponse,
)
from app.services.ai_service import generate_report
from app.services.evidence_service import enrich_report
from app.services.storage_service import save_metadata, save_report
from app.services.web3_service import Web3ServiceError, mint_receipt

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Green Receipt API starting — AI_MODE=%s STORAGE=%s",
        settings.ai_mode,
        settings.storage_backend,
    )
    yield
    logger.info("Green Receipt API shutting down.")


app = FastAPI(
    title="Green Receipt API",
    description=(
        "AI-powered environmental forensic receipt platform. "
        "Generates verifiable green receipts anchored as NFTs on Monad."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_analysis(product_name: str, brand: str, product_url: str) -> dict:
    """Shared logic for both /analyze and /analyze-and-mint."""
    raw_report = await generate_report(product_name, brand, product_url)

    enriched_report, report_hash, merkle_root = enrich_report(raw_report)

    report_dict = enriched_report.model_dump()
    report_uri, _ = save_report(report_dict, report_hash)
    metadata_uri, _ = save_metadata(
        product_name=enriched_report.productName,
        brand=enriched_report.brand,
        score=enriched_report.score,
        grade=enriched_report.grade,
        report_hash=report_hash,
        evidence_merkle_root=merkle_root,
        report_uri=report_uri,
    )

    return {
        "report": enriched_report,
        "report_dict": report_dict,
        "report_hash": report_hash,
        "merkle_root": merkle_root,
        "report_uri": report_uri,
        "metadata_uri": metadata_uri,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    """Liveness check."""
    return {"status": "ok", "ai_mode": settings.ai_mode}


@app.post(
    "/api/receipts/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a product and generate a Green Receipt (no mint)",
    tags=["Receipts"],
)
async def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """
    Step 1 of the pipeline: generate an AI environmental report, hash evidences,
    build Merkle root, hash full report, and save files locally.

    Does **not** mint an NFT — useful for preview before committing on-chain.
    """
    try:
        result = await _run_analysis(body.productName, body.brand, body.productUrl)
    except Exception as exc:
        logger.exception("analyze failed")
        raise HTTPException(status_code=500, detail=str(exc))

    report = result["report"]
    return AnalyzeResponse(
        productName=report.productName,
        brand=report.brand,
        score=report.score,
        grade=report.grade,
        summary=report.summary,
        findings=report.findings,
        evidences=report.evidences,
        reportHash=result["report_hash"],
        evidenceMerkleRoot=result["merkle_root"],
        reportURI=result["report_uri"],
        metadataURI=result["metadata_uri"],
    )


@app.post(
    "/api/receipts/mint",
    response_model=MintResponse,
    status_code=status.HTTP_200_OK,
    summary="Mint a Green Receipt NFT from pre-computed hashes",
    tags=["Receipts"],
)
async def mint(body: MintRequest) -> MintResponse:
    """
    Step 2 of the pipeline: mint the NFT on Monad using previously computed
    reportHash, evidenceMerkleRoot, and metadataURI.

    Requires PRIVATE_KEY, CONTRACT_ADDRESS, and MONAD_RPC_URL to be configured.
    """
    try:
        token_id, tx_hash = mint_receipt(
            to=body.to,
            product_name=body.productName,
            brand=body.brand,
            score=body.score,
            grade=body.grade,
            report_hash_hex=body.reportHash,
            evidence_merkle_root_hex=body.evidenceMerkleRoot,
            metadata_uri=body.metadataURI,
        )
    except Web3ServiceError as exc:
        logger.error("mint failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("mint unexpected error")
        raise HTTPException(status_code=500, detail=str(exc))

    return MintResponse(
        tokenId=token_id,
        transactionHash=tx_hash,
        contractAddress=settings.contract_address,
    )


@app.post(
    "/api/receipts/analyze-and-mint",
    response_model=AnalyzeAndMintResponse,
    status_code=status.HTTP_200_OK,
    summary="Full pipeline: analyze → hash → save → mint NFT",
    tags=["Receipts"],
)
async def analyze_and_mint(body: AnalyzeAndMintRequest) -> AnalyzeAndMintResponse:
    """
    One-shot endpoint: product input → AI report → hashing → Merkle root →
    local storage → on-chain NFT mint → full response.
    """
    try:
        result = await _run_analysis(body.productName, body.brand, body.productUrl)
    except Exception as exc:
        logger.exception("analyze-and-mint: analysis phase failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    report = result["report"]

    try:
        token_id, tx_hash = mint_receipt(
            to=body.to,
            product_name=report.productName,
            brand=report.brand,
            score=report.score,
            grade=report.grade,
            report_hash_hex=result["report_hash"],
            evidence_merkle_root_hex=result["merkle_root"],
            metadata_uri=result["metadata_uri"],
        )
    except Web3ServiceError as exc:
        logger.error("analyze-and-mint: mint phase failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Mint failed: {exc}")
    except Exception as exc:
        logger.exception("analyze-and-mint: mint unexpected error")
        raise HTTPException(status_code=500, detail=f"Mint error: {exc}")

    return AnalyzeAndMintResponse(
        productName=report.productName,
        brand=report.brand,
        score=report.score,
        grade=report.grade,
        summary=report.summary,
        findings=report.findings,
        evidences=report.evidences,
        reportHash=result["report_hash"],
        evidenceMerkleRoot=result["merkle_root"],
        reportURI=result["report_uri"],
        metadataURI=result["metadata_uri"],
        tokenId=token_id,
        transactionHash=tx_hash,
        contractAddress=settings.contract_address,
    )
