"""Reranking endpoint - BGE-reranker-v2-m3."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from src.inference.schemas import (
    RerankRequest,
    RerankResponse,
    RankedDocument,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/rerank", response_model=RerankResponse)
async def rerank(request: Request, body: RerankRequest) -> RerankResponse:
    """Rerank documents using BGE-reranker-v2-m3."""
    model_manager = request.app.state.model_manager
    model, tokenizer = model_manager.get_reranker()

    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Reranker model not loaded")

    if not body.documents:
        return RerankResponse(documents=[])

    pairs = [[body.query, doc.content] for doc in body.documents]
    settings = model_manager.settings

    loop = asyncio.get_event_loop()

    def compute_scores():
        import torch

        with torch.no_grad():
            scores = []
            batch_size = settings.reranker_batch_size
            for i in range(0, len(pairs), batch_size):
                batch = pairs[i : i + batch_size]
                inputs = tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )
                if settings.device != "cpu":
                    inputs = {k: v.to(settings.device) for k, v in inputs.items()}

                outputs = model(**inputs)
                batch_scores = outputs.logits.squeeze(-1).tolist()

                if isinstance(batch_scores, float):
                    batch_scores = [batch_scores]

                scores.extend(batch_scores)

            return scores

    scores = await loop.run_in_executor(None, compute_scores)

    # Pair documents with scores and sort
    scored = list(zip(body.documents, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    # Normalize scores to 0-1
    max_score = max(scores) if scores else 1.0
    min_score = min(scores) if scores else 0.0
    score_range = max_score - min_score if max_score != min_score else 1.0

    top_k = body.top_k or len(scored)
    results = []
    for doc, score in scored[:top_k]:
        normalized = (score - min_score) / score_range
        results.append(RankedDocument(
            id=doc.id,
            content=doc.content,
            score=max(0.0, min(1.0, normalized)),
        ))

    return RerankResponse(documents=results)
