"""Evaluation Metrics - Common NLP and ML metrics."""

from __future__ import annotations

from typing import Optional
import re


def calculate_precision(
    true_positives: int,
    false_positives: int,
) -> float:
    """Calculate precision.

    Precision = TP / (TP + FP)
    """
    total = true_positives + false_positives
    if total == 0:
        return 0.0
    return true_positives / total


def calculate_recall(
    true_positives: int,
    false_negatives: int,
) -> float:
    """Calculate recall.

    Recall = TP / (TP + FN)
    """
    total = true_positives + false_negatives
    if total == 0:
        return 0.0
    return true_positives / total


def calculate_f1(
    precision: float,
    recall: float,
) -> float:
    """Calculate F1 score.

    F1 = 2 * (precision * recall) / (precision + recall)
    """
    total = precision + recall
    if total == 0:
        return 0.0
    return 2 * (precision * recall) / total


def calculate_f1_from_counts(
    true_positives: int,
    false_positives: int,
    false_negatives: int,
) -> float:
    """Calculate F1 score from counts."""
    precision = calculate_precision(true_positives, false_positives)
    recall = calculate_recall(true_positives, false_negatives)
    return calculate_f1(precision, recall)


def tokenize_simple(text: str) -> list[str]:
    """Simple tokenization for metric calculation."""
    # Lowercase and split on whitespace/punctuation
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def calculate_bleu(
    reference: str,
    candidate: str,
    max_n: int = 4,
    weights: Optional[list[float]] = None,
) -> float:
    """Calculate BLEU score.

    A simplified implementation of BLEU (Bilingual Evaluation Understudy).

    Args:
        reference: Reference/expected text
        candidate: Candidate/generated text
        max_n: Maximum n-gram size (default 4)
        weights: Weights for each n-gram level (default uniform)

    Returns:
        BLEU score between 0 and 1
    """
    if weights is None:
        weights = [1.0 / max_n] * max_n

    ref_tokens = tokenize_simple(reference)
    cand_tokens = tokenize_simple(candidate)

    if len(cand_tokens) == 0:
        return 0.0

    # Calculate n-gram precisions
    precisions = []

    for n in range(1, max_n + 1):
        ref_ngrams = _get_ngrams(ref_tokens, n)
        cand_ngrams = _get_ngrams(cand_tokens, n)

        if len(cand_ngrams) == 0:
            precisions.append(0.0)
            continue

        # Count matches
        matches = 0
        ref_ngram_counts = {}
        for ngram in ref_ngrams:
            ref_ngram_counts[ngram] = ref_ngram_counts.get(ngram, 0) + 1

        cand_ngram_counts = {}
        for ngram in cand_ngrams:
            cand_ngram_counts[ngram] = cand_ngram_counts.get(ngram, 0) + 1

        for ngram, count in cand_ngram_counts.items():
            ref_count = ref_ngram_counts.get(ngram, 0)
            matches += min(count, ref_count)

        precision = matches / len(cand_ngrams)
        precisions.append(precision)

    # Calculate brevity penalty
    bp = _brevity_penalty(len(ref_tokens), len(cand_tokens))

    # Calculate weighted geometric mean of precisions
    import math

    if all(p > 0 for p in precisions):
        log_sum = sum(w * math.log(p) for w, p in zip(weights, precisions))
        bleu = bp * math.exp(log_sum)
    else:
        bleu = 0.0

    return bleu


def _get_ngrams(tokens: list[str], n: int) -> list[tuple]:
    """Get n-grams from token list."""
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def _brevity_penalty(ref_len: int, cand_len: int) -> float:
    """Calculate brevity penalty for BLEU."""
    import math

    if cand_len >= ref_len:
        return 1.0
    if cand_len == 0:
        return 0.0
    return math.exp(1 - ref_len / cand_len)


def calculate_rouge(
    reference: str,
    candidate: str,
    rouge_type: str = "rouge_l",
) -> dict[str, float]:
    """Calculate ROUGE scores.

    ROUGE (Recall-Oriented Understudy for Gisting Evaluation)

    Args:
        reference: Reference/expected text
        candidate: Candidate/generated text
        rouge_type: Type of ROUGE ("rouge_1", "rouge_2", "rouge_l")

    Returns:
        Dictionary with precision, recall, and f1
    """
    ref_tokens = tokenize_simple(reference)
    cand_tokens = tokenize_simple(candidate)

    if rouge_type == "rouge_1":
        return _rouge_n(ref_tokens, cand_tokens, 1)
    elif rouge_type == "rouge_2":
        return _rouge_n(ref_tokens, cand_tokens, 2)
    elif rouge_type == "rouge_l":
        return _rouge_l(ref_tokens, cand_tokens)
    else:
        raise ValueError(f"Unknown ROUGE type: {rouge_type}")


def _rouge_n(ref_tokens: list[str], cand_tokens: list[str], n: int) -> dict[str, float]:
    """Calculate ROUGE-N score."""
    ref_ngrams = set(_get_ngrams(ref_tokens, n))
    cand_ngrams = set(_get_ngrams(cand_tokens, n))

    if len(cand_ngrams) == 0 or len(ref_ngrams) == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    overlap = ref_ngrams.intersection(cand_ngrams)

    precision = len(overlap) / len(cand_ngrams)
    recall = len(overlap) / len(ref_ngrams)
    f1 = calculate_f1(precision, recall)

    return {"precision": precision, "recall": recall, "f1": f1}


def _rouge_l(ref_tokens: list[str], cand_tokens: list[str]) -> dict[str, float]:
    """Calculate ROUGE-L score using Longest Common Subsequence."""
    lcs_length = _lcs_length(ref_tokens, cand_tokens)

    if len(cand_tokens) == 0 or len(ref_tokens) == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    precision = lcs_length / len(cand_tokens)
    recall = lcs_length / len(ref_tokens)
    f1 = calculate_f1(precision, recall)

    return {"precision": precision, "recall": recall, "f1": f1}


def _lcs_length(seq1: list, seq2: list) -> int:
    """Calculate length of Longest Common Subsequence."""
    m, n = len(seq1), len(seq2)

    # Dynamic programming table
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i-1] == seq2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    return dp[m][n]


def calculate_exact_match(reference: str, candidate: str, normalize: bool = True) -> float:
    """Calculate exact match score.

    Args:
        reference: Reference text
        candidate: Candidate text
        normalize: Whether to normalize (lowercase, strip whitespace)

    Returns:
        1.0 if exact match, 0.0 otherwise
    """
    if normalize:
        reference = reference.lower().strip()
        candidate = candidate.lower().strip()

    return 1.0 if reference == candidate else 0.0


def calculate_token_overlap(reference: str, candidate: str) -> dict[str, float]:
    """Calculate token overlap metrics.

    Returns precision, recall, and F1 for token overlap.
    """
    ref_tokens = set(tokenize_simple(reference))
    cand_tokens = set(tokenize_simple(candidate))

    if len(cand_tokens) == 0 or len(ref_tokens) == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    overlap = ref_tokens.intersection(cand_tokens)

    precision = len(overlap) / len(cand_tokens)
    recall = len(overlap) / len(ref_tokens)
    f1 = calculate_f1(precision, recall)

    return {"precision": precision, "recall": recall, "f1": f1}


def calculate_answer_relevancy(
    question: str,
    answer: str,
) -> dict[str, float]:
    """Calculate answer relevancy based on question-answer overlap.

    This is a simple heuristic. For better results, use LLM-based evaluation.
    """
    q_tokens = set(tokenize_simple(question))
    a_tokens = set(tokenize_simple(answer))

    # Remove common stop words
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why", "when", "where", "who"}
    q_tokens = q_tokens - stop_words
    a_tokens = a_tokens - stop_words

    if len(q_tokens) == 0:
        return {"relevancy": 0.5, "overlap_ratio": 0.0}

    overlap = q_tokens.intersection(a_tokens)
    overlap_ratio = len(overlap) / len(q_tokens)

    # Simple heuristic: some overlap is good, but not too much (parrot)
    if overlap_ratio > 0.8:
        relevancy = 0.7  # Might be too similar to question
    elif overlap_ratio > 0.3:
        relevancy = 0.9  # Good overlap
    elif overlap_ratio > 0.1:
        relevancy = 0.6  # Some relevance
    else:
        relevancy = 0.3  # Low relevance

    return {"relevancy": relevancy, "overlap_ratio": overlap_ratio}


def calculate_factual_consistency(
    source: str,
    summary: str,
) -> dict[str, float]:
    """Calculate factual consistency between source and summary.

    This is a simple n-gram based check. For better results, use NLI models.
    """
    source_ngrams = set(_get_ngrams(tokenize_simple(source), 3))
    summary_tokens = tokenize_simple(summary)
    summary_ngrams = set(_get_ngrams(summary_tokens, 3))

    if len(summary_ngrams) == 0:
        return {"consistency": 0.0, "supported_ratio": 0.0}

    # Check what fraction of summary n-grams appear in source
    supported = summary_ngrams.intersection(source_ngrams)
    supported_ratio = len(supported) / len(summary_ngrams)

    # Higher supported ratio = more consistent
    consistency = min(supported_ratio * 1.5, 1.0)  # Scale up but cap at 1.0

    return {"consistency": consistency, "supported_ratio": supported_ratio}
