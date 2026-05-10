from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Evidence ──────────────────────────────────────────────────────────────────

class Evidence(BaseModel):
    title: str
    source: str
    url: str = ""
    excerpt: str
    claim: str
    confidence: Literal["High", "Medium", "Low", "Unverified"] = "Medium"
    hash: str = ""  # populated after hashing


# ── Report ────────────────────────────────────────────────────────────────────

class GreenReport(BaseModel):
    productName: str
    brand: str
    score: int = Field(ge=0, le=100)
    grade: str
    summary: str
    positiveSignals: list[str] = []
    riskSignals: list[str] = []
    greenwashingRisk: Literal["Low", "Medium", "High", "Critical"] = "Medium"
    findings: list[str] = []
    evidences: list[Evidence] = []
    alternatives: list[str] = []
    createdAt: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Request bodies ────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    productName: str = Field(..., min_length=1, examples=["Nike Pegasus Trail 5 DV3865-602"])
    productUrl: str = ""
    brand: str = ""


class MintRequest(BaseModel):
    to: str = Field(..., pattern=r"^0x[0-9a-fA-F]{40}$")
    productName: str
    brand: str
    score: int = Field(ge=0, le=100)
    grade: str
    reportHash: str = Field(..., pattern=r"^0x[0-9a-fA-F]{64}$")
    evidenceMerkleRoot: str = Field(..., pattern=r"^0x[0-9a-fA-F]{64}$")
    metadataURI: str


class AnalyzeAndMintRequest(BaseModel):
    productName: str = Field(..., min_length=1, examples=["Nike Pegasus Trail 5 DV3865-602"])
    productUrl: str = ""
    brand: str = ""
    to: str = Field(..., pattern=r"^0x[0-9a-fA-F]{40}$")


# ── Response bodies ───────────────────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    productName: str
    brand: str
    score: int
    grade: str
    summary: str
    findings: list[str]
    evidences: list[Evidence]
    reportHash: str
    evidenceMerkleRoot: str
    reportURI: str
    metadataURI: str


class MintResponse(BaseModel):
    tokenId: int
    transactionHash: str
    contractAddress: str


class AnalyzeAndMintResponse(BaseModel):
    # report fields
    productName: str
    brand: str
    score: int
    grade: str
    summary: str
    findings: list[str]
    evidences: list[Evidence]
    reportHash: str
    evidenceMerkleRoot: str
    reportURI: str
    metadataURI: str
    # mint fields
    tokenId: int
    transactionHash: str
    contractAddress: str


class ReportLookupResponse(BaseModel):
    reportHash: str
    reportURI: str
    report: GreenReport


class ErrorResponse(BaseModel):
    detail: str
    code: str = "INTERNAL_ERROR"
