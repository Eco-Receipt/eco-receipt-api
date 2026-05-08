"""
AI Service — generates Green Receipt data from a product name / URL.

Modes (controlled by AI_MODE env var):
  mock   → deterministic demo data, no external API needed
  openai → calls OpenAI Chat Completions with structured output

To add Tavily / SerpAPI / Exa / Perplexity later, implement a new _search_*()
function and wire it in generate_report().
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from app.config import settings
from app.models.schemas import Evidence, GreenReport

logger = logging.getLogger(__name__)


# ── Mock data ─────────────────────────────────────────────────────────────────

_MOCK_NIKE_REPORT = GreenReport(
    productName="Nike Pegasus Trail 5 DV3865-602",
    brand="Nike",
    score=62,
    grade="Medium Risk",
    summary=(
        "Nike has published brand-level sustainability commitments (Move to Zero) "
        "and uses recycled polyester in many product lines. However, product-specific "
        "Life Cycle Assessment (LCA) data for the Pegasus Trail 5 is not publicly "
        "available, limiting independent verification. The outsole rubber is not "
        "certified as sustainably sourced. Greenwashing risk is rated Medium due to "
        "the gap between marketing claims and verifiable product-level data."
    ),
    positiveSignals=[
        "Nike Move to Zero programme targets 70 % recycled polyester by 2025.",
        "Nike Grind recycled rubber used in some midsole compounds.",
        "Nike publishes annual Impact Report with scope 1 & 2 emissions data.",
        "Upper fabric reportedly contains ≥50 % recycled content (brand claim).",
    ],
    riskSignals=[
        "No product-level LCA or carbon footprint data found for DV3865-602.",
        "Outsole rubber: no FSC or rainforest-alliance certification evidence found.",
        "Dye & finish chemical disclosure not publicly available for this SKU.",
        "Supply chain tier-3/4 supplier list not disclosed.",
    ],
    greenwashingRisk="Medium",
    findings=[
        "Product-level LCA: NOT FOUND — Low Transparency",
        "Carbon footprint per pair: NOT FOUND — Low Transparency",
        "Recycled content upper: ~50 % (brand claim, not third-party verified)",
        "Outsole sustainability certification: NOT FOUND",
        "Chemical management (ZDHC gateway): NOT FOUND for this SKU",
        "Nike Move to Zero brand commitment: CONFIRMED (brand level only)",
    ],
    evidences=[
        Evidence(
            title="Nike Move to Zero — Sustainability Commitment",
            source="Nike Official Sustainability Page",
            url="https://www.nike.com/sustainability",
            excerpt=(
                "Nike's Move to Zero journey is our commitment to zero carbon and zero waste "
                "to help protect the future of sport. We're working toward 70% recycled "
                "polyester across all Nike products by 2025."
            ),
            claim="Nike targets 70 % recycled polyester across all products by 2025.",
            confidence="High",
        ),
        Evidence(
            title="Nike FY23 Impact Report — Scope Emissions",
            source="Nike Inc. FY2023 Impact Report",
            url="https://investors.nike.com/investors/financial-information/annual-reports",
            excerpt=(
                "Nike's scope 1 and 2 market-based GHG emissions decreased 69 % compared "
                "to our FY20 baseline, driven by renewable energy procurement across "
                "owned and operated facilities."
            ),
            claim="Nike reduced scope 1 & 2 emissions 69 % vs FY20 baseline (brand level).",
            confidence="High",
        ),
        Evidence(
            title="Nike Grind Recycled Materials Programme",
            source="Nike Official — Nike Grind",
            url="https://www.nike.com/help/a/nike-grind",
            excerpt=(
                "Nike Grind is a portfolio of premium recycled materials made from "
                "factory scraps and end-of-life athletic footwear. These materials are "
                "used in Nike products and surfaces worldwide."
            ),
            claim="Nike Grind recycled rubber may be used in Pegasus Trail 5 midsole compound.",
            confidence="Medium",
        ),
        Evidence(
            title="Product-Level LCA — NOT FOUND",
            source="Public Database Search (GaBi, ecoinvent, Nike disclosures)",
            url="",
            excerpt=(
                "No product-level Life Cycle Assessment (LCA) or Environmental Product "
                "Declaration (EPD) for Nike Pegasus Trail 5 DV3865-602 was found in "
                "publicly accessible databases as of the report date."
            ),
            claim="Product-specific LCA data is not publicly available — Low Transparency.",
            confidence="Unverified",
        ),
        Evidence(
            title="Outsole Rubber Certification — NOT FOUND",
            source="FSC, Rainforest Alliance, Nike Disclosures",
            url="",
            excerpt=(
                "No FSC or Rainforest Alliance certification for the outsole rubber "
                "used in Nike Pegasus Trail 5 was identified in publicly available "
                "supplier disclosures or certification registries."
            ),
            claim="Outsole rubber sustainability certification not found — Low Transparency.",
            confidence="Unverified",
        ),
    ],
    alternatives=[
        "Salomon Pulsar Trail (uses Doveil recycled PET upper with published material data)",
        "Merrell Agility Peak 5 (lists recycled content per component on product page)",
        "On Cloudultra 2 (publishes per-shoe CO₂e estimate)",
    ],
    createdAt=datetime.utcnow().isoformat(),
)


def _mock_report(product_name: str, brand: str) -> GreenReport:
    """Return mock data. For known products return rich data; otherwise a generic stub."""
    if "nike" in product_name.lower() or "pegasus" in product_name.lower():
        report = _MOCK_NIKE_REPORT.model_copy(deep=True)
        report.productName = product_name or report.productName
        report.brand = brand or report.brand
        report.createdAt = datetime.utcnow().isoformat()
        return report

    # Generic stub for any other product
    return GreenReport(
        productName=product_name,
        brand=brand or "Unknown Brand",
        score=50,
        grade="Medium Risk",
        summary=(
            f"Environmental assessment for '{product_name}' was generated in mock mode. "
            "No real search was performed. Data below is illustrative only."
        ),
        positiveSignals=["Brand has published a sustainability page (mock claim)."],
        riskSignals=[
            "No product-level LCA found (mock).",
            "Supply chain transparency data unavailable (mock).",
        ],
        greenwashingRisk="Medium",
        findings=[
            "Product-level LCA: NOT FOUND — Low Transparency (mock)",
            "Recycled content: Unknown (mock)",
        ],
        evidences=[
            Evidence(
                title="Mock Evidence — Sustainability Claim",
                source="Mock Source",
                url="",
                excerpt="This is mock evidence generated for demonstration purposes.",
                claim="No real claims verified — running in mock mode.",
                confidence="Unverified",
            )
        ],
        alternatives=["Consider products with published EPD or LCA data."],
        createdAt=datetime.utcnow().isoformat(),
    )


# ── OpenAI mode ───────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an environmental forensic analyst. Given a product name and optional URL,
research publicly known sustainability data and generate a structured Green Receipt report.

RULES:
1. Distinguish evidence (verifiable external sources) from inference (your reasoning).
2. If product-level LCA, carbon footprint, or certification data is not publicly known,
   explicitly mark it as "NOT FOUND / Low Transparency". Do NOT fabricate data.
3. Score 0-100: 0 = highly unsustainable / zero transparency, 100 = exemplary.
4. Grade options: "A (Low Risk)", "B (Medium-Low Risk)", "C (Medium Risk)",
   "D (High Risk)", "F (Critical Risk)".
5. Provide 3-6 evidence items. Each must have: title, source, url (empty string if none),
   excerpt, claim, confidence (High/Medium/Low/Unverified).
6. Return ONLY valid JSON matching the schema below. No markdown fences.

JSON schema:
{
  "productName": "string",
  "brand": "string",
  "score": 0-100,
  "grade": "string",
  "summary": "string",
  "positiveSignals": ["string"],
  "riskSignals": ["string"],
  "greenwashingRisk": "Low|Medium|High|Critical",
  "findings": ["string"],
  "evidences": [
    {
      "title": "string",
      "source": "string",
      "url": "string",
      "excerpt": "string",
      "claim": "string",
      "confidence": "High|Medium|Low|Unverified"
    }
  ],
  "alternatives": ["string"]
}
"""


async def _openai_report(product_name: str, brand: str, product_url: str) -> GreenReport:
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed. Run: pip install openai") from exc

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    user_message = f"Product: {product_name}"
    if brand:
        user_message += f"\nBrand: {brand}"
    if product_url:
        user_message += f"\nProduct URL: {product_url}"

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)
    data["createdAt"] = datetime.utcnow().isoformat()

    # Normalise evidences into Evidence objects (strip 'hash' if present)
    evidences = [Evidence(**{k: v for k, v in e.items() if k != "hash"}) for e in data.get("evidences", [])]
    data["evidences"] = evidences
    return GreenReport(**data)


# ── Public interface ───────────────────────────────────────────────────────────

async def generate_report(product_name: str, brand: str = "", product_url: str = "") -> GreenReport:
    """
    Entry point for AI report generation.

    Respects AI_MODE setting:
      mock   → returns deterministic mock data (no API calls)
      openai → calls OpenAI Chat Completions
    """
    mode = settings.ai_mode.lower()
    logger.info("generate_report mode=%s product=%r", mode, product_name)

    if mode == "mock":
        return _mock_report(product_name, brand)
    elif mode == "openai":
        return await _openai_report(product_name, brand, product_url)
    else:
        raise ValueError(f"Unknown AI_MODE: {mode!r}. Choose 'mock' or 'openai'.")
