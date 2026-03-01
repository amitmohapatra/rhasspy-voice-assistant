"""Embedding endpoints - BGE-M3 dense+sparse embeddings + late chunking + ColSmol visual."""

from __future__ import annotations

import asyncio
import base64
import io
import logging

from fastapi import APIRouter, HTTPException, Request

from src.inference.schemas import (
    EmbedTripleRequest,
    EmbedTripleResponse,
    TripleEmbeddingResponse,
    LateBatchRequest,
    LateBatchResponse,
    VisualEmbedRequest,
    VisualEmbedResponse,
    VisualQueryRequest,
    VisualQueryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/embed-triple", response_model=EmbedTripleResponse)
async def embed_triple(request: Request, body: EmbedTripleRequest) -> EmbedTripleResponse:
    """Generate BGE-M3 embeddings (dense + sparse)."""
    model_manager = request.app.state.model_manager
    model = model_manager.get_bge_m3()

    if model is None:
        raise HTTPException(status_code=503, detail="BGE-M3 model not loaded")

    if not body.texts:
        return EmbedTripleResponse(embeddings=[])

    loop = asyncio.get_event_loop()
    settings = model_manager.settings

    def _encode():
        return model.encode(
            body.texts,
            batch_size=settings.bge_m3_batch_size,
            max_length=body.max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )

    output = await loop.run_in_executor(None, _encode)

    dense_vecs = output["dense_vecs"]
    sparse_weights = output.get("lexical_weights", [{}] * len(body.texts))

    embeddings = []
    for i in range(len(body.texts)):
        dense = (
            dense_vecs[i].tolist()
            if hasattr(dense_vecs[i], "tolist")
            else list(dense_vecs[i])
        )

        sparse: dict[int, float] = {}
        if i < len(sparse_weights) and sparse_weights[i]:
            sw = sparse_weights[i]
            if isinstance(sw, dict):
                for token_key, weight in sw.items():
                    if isinstance(token_key, str):
                        sparse[hash(token_key) % (2**31)] = float(weight)
                    else:
                        sparse[int(token_key)] = float(weight)

        embeddings.append(TripleEmbeddingResponse(
            dense=dense,
            sparse=sparse,
        ))

    return EmbedTripleResponse(embeddings=embeddings)


@router.post("/embed-late-chunk", response_model=LateBatchResponse)
async def embed_late_chunk(request: Request, body: LateBatchRequest) -> LateBatchResponse:
    """Late chunking: embed full document, then pool into chunk boundaries.

    Instead of embedding each chunk independently, this:
    1. Tokenizes the full document text
    2. Runs ONE forward pass through BGE-M3's transformer
    3. Pools token-level embeddings back into chunk boundaries
    4. Each chunk embedding has full document context — no LLM enrichment needed

    Input: full document text + list of [start_char, end_char] boundaries
    Output: list of TripleEmbedding (one per chunk, with document context)
    """
    model_manager = request.app.state.model_manager
    model = model_manager.get_bge_m3()

    if model is None:
        raise HTTPException(status_code=503, detail="BGE-M3 model not loaded")

    if not body.chunk_boundaries:
        return LateBatchResponse(embeddings=[])

    loop = asyncio.get_event_loop()
    settings = model_manager.settings

    def _late_chunk():
        import torch
        from bisect import bisect_left

        text = body.document_text
        boundaries = body.chunk_boundaries
        max_length = min(body.max_length, settings.bge_m3_max_length)

        # Model hierarchy:
        # model = BGEM3FlagModel (M3Embedder) — has .model, .tokenizer
        # model.model = EncoderOnlyEmbedderM3ModelForInference — has .model, .sparse_linear, .colbert_linear
        # model.model.model = actual HuggingFace transformer (XLM-RoBERTa)
        m3_wrapper = getattr(model, "model", None)  # EncoderOnlyEmbedderM3ModelForInference
        if m3_wrapper is None:
            return _fallback_independent_embed(model, settings, text, boundaries)

        actual_transformer = getattr(m3_wrapper, "model", None)  # HuggingFace transformer
        tokenizer = getattr(model, "tokenizer", None) or getattr(m3_wrapper, "tokenizer", None)
        if actual_transformer is None or tokenizer is None:
            return _fallback_independent_embed(model, settings, text, boundaries)

        encoded = tokenizer(
            text,
            max_length=max_length,
            truncation=True,
            return_tensors="pt",
            return_offsets_mapping=True,
        )

        offset_mapping = encoded.pop("offset_mapping")[0]  # (seq_len, 2)
        input_ids = encoded["input_ids"][0]  # (seq_len,) — needed for sparse token IDs

        # Single forward pass through the actual transformer (not the wrapper)
        with torch.no_grad():
            device = next(actual_transformer.parameters()).device
            inputs = {k: v.to(device) for k, v in encoded.items()}

            outputs = actual_transformer(**inputs, return_dict=True)
            # token_embeddings: (seq_len, hidden_dim)
            token_embeddings = outputs.last_hidden_state[0]

        # Pre-compute valid offsets (skip special tokens) for binary search
        valid_offsets = []  # list of (tok_start, tok_end, tok_idx)
        for tok_idx in range(len(offset_mapping)):
            ts = offset_mapping[tok_idx][0].item()
            te = offset_mapping[tok_idx][1].item()
            if ts == 0 and te == 0:
                continue  # skip [CLS], [SEP], [PAD]
            valid_offsets.append((ts, te, tok_idx))
        tok_starts = [o[0] for o in valid_offsets]

        # Get sparse projection layer from the M3 wrapper
        sparse_linear = getattr(m3_wrapper, "sparse_linear", None)

        # Pre-compute sparse scores from same forward pass
        all_sparse_scores = None

        if sparse_linear is not None:
            with torch.no_grad():
                sparse_out = sparse_linear(token_embeddings)
                if sparse_out.shape[-1] == 1:
                    all_sparse_scores = torch.relu(sparse_out.squeeze(-1))
                else:
                    sparse_linear = None  # unexpected shape, skip fused sparse

        fused = all_sparse_scores is not None
        if fused:
            logger.debug("Late chunking: fused single-pass (dense+sparse from one forward pass)")

        # Map chunk boundaries → token indices using binary search, then build embeddings
        results = []
        partial_dense = []  # used only in fallback path

        for boundary in boundaries:
            start_char, end_char = boundary[0], boundary[1]

            # Binary search for first potentially overlapping token
            left = bisect_left(tok_starts, start_char)
            while left > 0 and valid_offsets[left - 1][1] > start_char:
                left -= 1

            token_indices = []
            for i in range(left, len(valid_offsets)):
                ts, te, tidx = valid_offsets[i]
                if ts >= end_char:
                    break
                if te > start_char:
                    token_indices.append(tidx)

            # Dense: mean pool with document context (always from full-doc pass)
            if token_indices:
                dense = token_embeddings[token_indices].mean(dim=0).cpu().numpy().tolist()
            else:
                dense = token_embeddings[0].cpu().numpy().tolist()

            if fused:
                # Sparse: aggregate per-token scores by token ID
                sparse: dict[int, float] = {}
                if token_indices:
                    chunk_ids = input_ids[token_indices]
                    chunk_scores = all_sparse_scores[token_indices]
                    for tid, score in zip(chunk_ids, chunk_scores):
                        s = score.item()
                        if s > 0:
                            t = tid.item()
                            sparse[t] = max(sparse.get(t, 0.0), s)

                results.append(TripleEmbeddingResponse(
                    dense=dense, sparse=sparse,
                ))
            else:
                partial_dense.append(dense)

        if not fused:
            # Fallback: second pass for sparse only
            chunk_texts = [text[b[0]:b[1]] for b in boundaries]
            standard_output = model.encode(
                chunk_texts,
                batch_size=settings.bge_m3_batch_size,
                max_length=max_length,
                return_dense=False,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            sparse_weights = standard_output.get("lexical_weights", [{}] * len(boundaries))

            for i in range(len(boundaries)):
                sparse: dict[int, float] = {}
                if i < len(sparse_weights) and sparse_weights[i]:
                    sw = sparse_weights[i]
                    if isinstance(sw, dict):
                        for token_key, weight in sw.items():
                            if isinstance(token_key, str):
                                sparse[hash(token_key) % (2**31)] = float(weight)
                            else:
                                sparse[int(token_key)] = float(weight)

                results.append(TripleEmbeddingResponse(
                    dense=partial_dense[i], sparse=sparse,
                ))

        return results

    embeddings = await loop.run_in_executor(None, _late_chunk)
    return LateBatchResponse(embeddings=embeddings)


def _fallback_independent_embed(model, settings, text, boundaries):
    """Fallback: embed each chunk independently if late chunking can't access internals."""
    chunk_texts = [text[b[0]:b[1]] for b in boundaries]
    output = model.encode(
        chunk_texts,
        batch_size=settings.bge_m3_batch_size,
        max_length=settings.bge_m3_max_length,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )

    dense_vecs = output["dense_vecs"]
    sparse_weights = output.get("lexical_weights", [{}] * len(boundaries))

    results = []
    for i in range(len(boundaries)):
        dense = dense_vecs[i].tolist() if hasattr(dense_vecs[i], "tolist") else list(dense_vecs[i])

        sparse: dict[int, float] = {}
        if i < len(sparse_weights) and sparse_weights[i]:
            sw = sparse_weights[i]
            if isinstance(sw, dict):
                for token_key, weight in sw.items():
                    if isinstance(token_key, str):
                        sparse[hash(token_key) % (2**31)] = float(weight)
                    else:
                        sparse[int(token_key)] = float(weight)

        results.append(TripleEmbeddingResponse(
            dense=dense,
            sparse=sparse,
        ))

    return results


@router.post("/embed-visual", response_model=VisualEmbedResponse)
async def embed_visual(request: Request, body: VisualEmbedRequest) -> VisualEmbedResponse:
    """Embed page images as multi-vectors using ColSmol-256M.

    Each page image produces ~1030 patch vectors of 128 dimensions.
    Used for visual page-level retrieval (MaxSim in Qdrant).
    """
    model_manager = request.app.state.model_manager
    model, processor = model_manager.get_colsmol()

    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="ColSmol model not loaded")

    if not body.images:
        return VisualEmbedResponse(embeddings=[])

    loop = asyncio.get_event_loop()
    settings = model_manager.settings
    batch_size = settings.colsmol_batch_size

    def _encode_images():
        import torch
        from PIL import Image

        all_embeddings = []

        for i in range(0, len(body.images), batch_size):
            batch_b64 = body.images[i:i + batch_size]
            pil_images = []
            for img_b64 in batch_b64:
                img_bytes = base64.b64decode(img_b64)
                pil_images.append(Image.open(io.BytesIO(img_bytes)).convert("RGB"))

            try:
                batch_inputs = processor.process_images(pil_images)
                # Move tensors to model device
                device = next(model.parameters()).device
                batch_inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in batch_inputs.items()}

                with torch.no_grad():
                    outputs = model(**batch_inputs)

                # outputs shape: (batch, num_patches, 128)
                for j in range(outputs.shape[0]):
                    page_vecs = outputs[j].cpu().numpy().tolist()
                    all_embeddings.append(page_vecs)
            finally:
                for img in pil_images:
                    img.close()

        return all_embeddings

    embeddings = await loop.run_in_executor(None, _encode_images)
    return VisualEmbedResponse(embeddings=embeddings)


@router.post("/embed-visual-query", response_model=VisualQueryResponse)
async def embed_visual_query(request: Request, body: VisualQueryRequest) -> VisualQueryResponse:
    """Embed a text query as multi-vectors for visual page search.

    The text query is tokenized and encoded into multi-vectors that can
    be compared against page image embeddings using MaxSim.
    """
    model_manager = request.app.state.model_manager
    model, processor = model_manager.get_colsmol()

    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="ColSmol model not loaded")

    loop = asyncio.get_event_loop()

    def _encode_query():
        import torch

        batch_inputs = processor.process_queries([body.query])
        device = next(model.parameters()).device
        batch_inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in batch_inputs.items()}

        with torch.no_grad():
            outputs = model(**batch_inputs)

        # outputs shape: (1, num_tokens, 128)
        return outputs[0].cpu().numpy().tolist()

    embedding = await loop.run_in_executor(None, _encode_query)
    return VisualQueryResponse(embedding=embedding)


