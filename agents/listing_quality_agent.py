"""
Stage 4: Listing Quality Audit.

Uses Ollama (free, runs locally, no API key/cost) with a vision-capable model
(default: llava) to evaluate the top product's title, bullets, description,
and up to 3 images across 5 dimensions. Falls back to a zero-score default if
Ollama isn't running or the call fails -- never crashes the pipeline.
"""
from __future__ import annotations
import base64
import json

import httpx

import config
from schemas import ProductRecord, ListingQualityResult, DimensionAssessment, Verdict
from utils.logger import log

SYSTEM_PROMPT = """You are an e-commerce listing quality auditor. You evaluate a single \
Amazon product listing across exactly 5 dimensions: Title Quality, Visual Quality, \
Content Richness, Data Accuracy, Social Proof.

For each dimension return a verdict of GOOD, MODERATE, or BAD plus a one-sentence note \
citing concrete evidence (word counts, image counts, presence/absence of specs, etc).

Then return an overall score from 1-10 (10 = excellent) weighted roughly:
Title 15%, Visual 20%, Content Richness 25%, Data Accuracy 20%, Social Proof 20%.

Respond ONLY with valid JSON, no markdown fences, no commentary, matching exactly:
{
  "score": <int 1-10>,
  "summary": "<1-2 sentence overall summary of the weakest areas>",
  "dimensions": [
    {"dimension": "Title Quality", "verdict": "GOOD|MODERATE|BAD", "notes": "..."},
    {"dimension": "Visual Quality", "verdict": "GOOD|MODERATE|BAD", "notes": "..."},
    {"dimension": "Content Richness", "verdict": "GOOD|MODERATE|BAD", "notes": "..."},
    {"dimension": "Data Accuracy", "verdict": "GOOD|MODERATE|BAD", "notes": "..."},
    {"dimension": "Social Proof", "verdict": "GOOD|MODERATE|BAD", "notes": "..."}
  ]
}"""

WEIGHTS = {
    "Title Quality": 0.15,
    "Visual Quality": 0.20,
    "Content Richness": 0.25,
    "Data Accuracy": 0.20,
    "Social Proof": 0.20,
}

VERDICT_SCORES = {
    Verdict.GOOD: 9.0,
    Verdict.MODERATE: 5.5,
    Verdict.BAD: 2.0,
}


def _compute_weighted_score(dimensions: list[DimensionAssessment]) -> int:
    """Recomputes the 1-10 score from dimension verdicts using WEIGHTS,
    instead of trusting the LLM's self-reported score. Falls back to an
    even split across whatever dimensions are present if some are missing."""
    if not dimensions:
        return 0

    total_weight = 0.0
    weighted_sum = 0.0
    for d in dimensions:
        weight = WEIGHTS.get(d.dimension, 1.0 / len(dimensions))
        weighted_sum += VERDICT_SCORES.get(d.verdict, 5.0) * weight
        total_weight += weight

    if total_weight == 0:
        return 0

    score = weighted_sum / total_weight
    return max(1, min(10, round(score)))


async def audit_listing(product: ProductRecord | None) -> ListingQualityResult:
    if product is None or not product.title:
        log("listing_quality", "no product data available, defaulting to score 0", ok=False)
        return ListingQualityResult()

    try:
        
        user_prompt = _build_text_payload(product)

        payload = {
            "model": config.OLLAMA_TEXT_MODEL,
            "system": SYSTEM_PROMPT,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(f"{config.OLLAMA_HOST}/api/generate", json=payload)
            resp.raise_for_status()
            raw_text = resp.json().get("response", "")

        parsed = json.loads(raw_text.strip().strip("`"))

        dimensions = [
            DimensionAssessment(
                dimension=d["dimension"],
                verdict=Verdict(d["verdict"].upper()),
                notes=d.get("notes", ""),
            )
            for d in parsed.get("dimensions", [])
        ]

        computed_score = _compute_weighted_score(dimensions)
        result = ListingQualityResult(
            product_url=product.url,
            score=computed_score,
            summary=parsed.get("summary", ""),
            dimensions=dimensions,
        )
        log("listing_quality", f"score: {result.score}/10 (weighted from {len(dimensions)} dimensions)")
        return result

    except httpx.ConnectError:
        log("listing_quality", "Ollama not running at OLLAMA_HOST — start it with 'ollama serve'", ok=False)
        return ListingQualityResult(product_url=product.url)
    except httpx.ReadTimeout:
        log("listing_quality", "Ollama request timed out (model may be slow/cold) — try again or use a smaller model", ok=False)
        return ListingQualityResult(product_url=product.url)
    except Exception as e:
        log("listing_quality", f"LLM audit failed ({type(e).__name__}: {e}), defaulting to score 0", ok=False)
        return ListingQualityResult(product_url=product.url)


def _build_text_payload(product: ProductRecord) -> str:
    return f"""Audit this Amazon listing:

Title: {product.title}
Star rating: {product.star_rating}
Rating count: {product.rating_count}
Bullet points ({len(product.bullet_points)}):
{chr(10).join('- ' + b for b in product.bullet_points) or '(none found)'}

Description:
{product.description or '(none found)'}

Number of product images found: {len(product.image_urls)}
(Up to 3 images are attached, if available, for visual quality assessment.)"""


async def _fetch_images_as_b64(urls: list[str]) -> list[str]:
    images = []
    if not urls:
        return images
    async with httpx.AsyncClient(timeout=10) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                images.append(base64.b64encode(resp.content).decode())
            except Exception:
                continue  
    return images