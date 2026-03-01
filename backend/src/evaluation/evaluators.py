"""Evaluators - Different methods for scoring AI outputs."""

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.evaluation.base import (
    EvaluationResult,
    MetricScore,
    MetricType,
    TestCase,
)


class BaseEvaluator(ABC):
    """Base class for all evaluators."""

    name: str = "base"
    metric_type: MetricType = MetricType.LLM_JUDGE_SCORE

    @abstractmethod
    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Evaluate the output and return a score.

        Args:
            test_case: The test case being evaluated
            actual_output: The model's actual output
            **kwargs: Additional context (e.g., latency, tokens)

        Returns:
            MetricScore with value and optional details
        """
        pass


class LLMJudgeEvaluator(BaseEvaluator):
    """Use an LLM as a judge to score responses."""

    name = "llm_judge"
    metric_type = MetricType.LLM_JUDGE_SCORE

    # Evaluation criteria templates
    CRITERIA = {
        "quality": """
Rate the overall quality of the response on a scale of 1-10.
Consider:
- Accuracy of information
- Clarity and coherence
- Completeness
- Helpfulness

Response to evaluate:
{response}

Expected response (if provided):
{expected}

User query:
{query}

Provide your rating as JSON: {{"score": <1-10>, "reasoning": "<explanation>"}}
""",
        "relevance": """
Rate how relevant the response is to the query on a scale of 1-10.
A score of 10 means the response directly and completely addresses the query.
A score of 1 means the response is completely off-topic.

Query: {query}
Response: {response}

Provide your rating as JSON: {{"score": <1-10>, "reasoning": "<explanation>"}}
""",
        "helpfulness": """
Rate how helpful the response is on a scale of 1-10.
Consider:
- Does it solve the user's problem?
- Is it actionable?
- Is it easy to understand?

Query: {query}
Response: {response}

Provide your rating as JSON: {{"score": <1-10>, "reasoning": "<explanation>"}}
""",
        "accuracy": """
Rate the factual accuracy of the response on a scale of 1-10.
If expected facts are provided, check if they are correctly stated.

Query: {query}
Response: {response}
Expected facts: {expected_facts}

Provide your rating as JSON: {{"score": <1-10>, "reasoning": "<explanation>", "incorrect_facts": [<list of any incorrect statements>]}}
""",
    }

    def __init__(
        self,
        llm_provider: Any,
        model: str = "gpt-4o",
        criteria: str = "quality",
        temperature: float = 0.0,
    ):
        self.llm = llm_provider
        self.model = model
        self.criteria = criteria
        self.temperature = temperature

    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Evaluate using LLM as judge."""
        try:
            # Get the appropriate prompt template
            template = self.CRITERIA.get(self.criteria, self.CRITERIA["quality"])

            # Build the prompt
            prompt = template.format(
                response=actual_output,
                expected=test_case.expected_output or "Not provided",
                query=test_case.input_text or str(test_case.input_messages),
                expected_facts=", ".join(test_case.expected_facts) if test_case.expected_facts else "Not provided",
            )

            # Call the LLM
            from src.llm.providers.base import CompletionRequest, Message

            request = CompletionRequest(
                messages=[
                    Message(role="system", content="You are an expert evaluator. Provide accurate, unbiased ratings."),
                    Message(role="user", content=prompt),
                ],
                model=self.model,
                temperature=self.temperature,
                max_tokens=500,
            )

            response = await self.llm.complete(request)

            # Parse the JSON response
            content = response.content or ""

            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = float(result.get("score", 5)) / 10.0  # Normalize to 0-1
                reasoning = result.get("reasoning", "")
            else:
                # Fallback: try to extract a number
                numbers = re.findall(r'\b([1-9]|10)\b', content)
                score = float(numbers[0]) / 10.0 if numbers else 0.5
                reasoning = content

            return MetricScore(
                metric_type=MetricType.LLM_JUDGE_SCORE,
                value=score,
                details={
                    "criteria": self.criteria,
                    "reasoning": reasoning,
                    "raw_response": content,
                },
            )

        except Exception as e:
            return MetricScore(
                metric_type=MetricType.LLM_JUDGE_SCORE,
                value=0.0,
                details={"error": str(e)},
            )


class ExactMatchEvaluator(BaseEvaluator):
    """Check for exact match with expected output."""

    name = "exact_match"
    metric_type = MetricType.EXACT_MATCH

    def __init__(self, case_sensitive: bool = False, strip_whitespace: bool = True):
        self.case_sensitive = case_sensitive
        self.strip_whitespace = strip_whitespace

    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Check for exact match."""
        if not test_case.expected_output:
            return MetricScore(
                metric_type=MetricType.EXACT_MATCH,
                value=0.0,
                details={"error": "No expected output provided"},
            )

        expected = test_case.expected_output
        actual = actual_output

        if self.strip_whitespace:
            expected = expected.strip()
            actual = actual.strip()

        if not self.case_sensitive:
            expected = expected.lower()
            actual = actual.lower()

        is_match = expected == actual

        return MetricScore(
            metric_type=MetricType.EXACT_MATCH,
            value=1.0 if is_match else 0.0,
            details={
                "match": is_match,
                "expected_length": len(expected),
                "actual_length": len(actual),
            },
        )


class SemanticSimilarityEvaluator(BaseEvaluator):
    """Compare semantic similarity using embeddings."""

    name = "semantic_similarity"
    metric_type = MetricType.SEMANTIC_SIMILARITY

    def __init__(self, embedding_provider: Any, threshold: float = 0.8):
        self.embeddings = embedding_provider
        self.threshold = threshold

    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Calculate semantic similarity."""
        if not test_case.expected_output:
            return MetricScore(
                metric_type=MetricType.SEMANTIC_SIMILARITY,
                value=0.0,
                details={"error": "No expected output provided"},
            )

        try:
            # Get embeddings for both
            embeddings = await self.embeddings.embed([
                test_case.expected_output,
                actual_output,
            ])

            # Calculate cosine similarity
            import numpy as np

            vec1 = np.array(embeddings[0])
            vec2 = np.array(embeddings[1])

            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            similarity = float(similarity)

            return MetricScore(
                metric_type=MetricType.SEMANTIC_SIMILARITY,
                value=similarity,
                details={
                    "threshold": self.threshold,
                    "passed": similarity >= self.threshold,
                },
            )

        except Exception as e:
            return MetricScore(
                metric_type=MetricType.SEMANTIC_SIMILARITY,
                value=0.0,
                details={"error": str(e)},
            )


class FactualityEvaluator(BaseEvaluator):
    """Check if expected facts are present in the response."""

    name = "factuality"
    metric_type = MetricType.ANSWER_FAITHFULNESS

    def __init__(self, llm_provider: Any = None, model: str = "gpt-4o"):
        self.llm = llm_provider
        self.model = model

    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Check for presence of expected facts."""
        if not test_case.expected_facts:
            return MetricScore(
                metric_type=MetricType.ANSWER_FAITHFULNESS,
                value=1.0,  # No facts to check
                details={"message": "No expected facts provided"},
            )

        # Simple keyword-based checking
        actual_lower = actual_output.lower()
        found_facts = []
        missing_facts = []

        for fact in test_case.expected_facts:
            fact_lower = fact.lower()
            # Check if the fact (or key words from it) appear
            words = fact_lower.split()
            key_words = [w for w in words if len(w) > 3]  # Filter short words

            if key_words:
                found = sum(1 for w in key_words if w in actual_lower) / len(key_words)
                if found >= 0.5:
                    found_facts.append(fact)
                else:
                    missing_facts.append(fact)
            else:
                if fact_lower in actual_lower:
                    found_facts.append(fact)
                else:
                    missing_facts.append(fact)

        score = len(found_facts) / len(test_case.expected_facts)

        return MetricScore(
            metric_type=MetricType.ANSWER_FAITHFULNESS,
            value=score,
            details={
                "found_facts": found_facts,
                "missing_facts": missing_facts,
                "total_facts": len(test_case.expected_facts),
            },
        )


class ToxicityEvaluator(BaseEvaluator):
    """Check for toxic or harmful content."""

    name = "toxicity"
    metric_type = MetricType.TOXICITY_SCORE

    # Simple keyword-based toxicity detection (in production, use a proper classifier)
    TOXIC_PATTERNS = [
        r'\b(hate|kill|die|stupid|idiot|dumb)\b',
        r'\b(racist|sexist|homophobic)\b',
        r'profanity_placeholder',  # Would be actual profanity in production
    ]

    def __init__(self, classifier: Any = None):
        self.classifier = classifier

    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Check for toxicity."""
        if self.classifier:
            # Use provided classifier
            try:
                result = await self.classifier.classify(actual_output)
                return MetricScore(
                    metric_type=MetricType.TOXICITY_SCORE,
                    value=result.get("toxicity_score", 0.0),
                    details=result,
                )
            except Exception as e:
                return MetricScore(
                    metric_type=MetricType.TOXICITY_SCORE,
                    value=0.0,
                    details={"error": str(e)},
                )

        # Simple pattern-based detection
        actual_lower = actual_output.lower()
        matches = []

        for pattern in self.TOXIC_PATTERNS:
            found = re.findall(pattern, actual_lower, re.IGNORECASE)
            matches.extend(found)

        # Score: 0 = no toxicity, 1 = highly toxic
        toxicity_score = min(len(matches) * 0.2, 1.0)

        return MetricScore(
            metric_type=MetricType.TOXICITY_SCORE,
            value=toxicity_score,
            details={
                "matches": matches,
                "safe": toxicity_score < 0.1,
            },
        )


class LatencyEvaluator(BaseEvaluator):
    """Evaluate response latency."""

    name = "latency"
    metric_type = MetricType.LATENCY_MS

    def __init__(self, max_acceptable_ms: float = 5000.0):
        self.max_acceptable_ms = max_acceptable_ms

    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Evaluate latency performance."""
        latency_ms = kwargs.get("latency_ms", 0.0)

        # Score: 1.0 if under threshold, decreasing as it exceeds
        if latency_ms <= self.max_acceptable_ms:
            score = 1.0
        else:
            # Linearly decrease score as latency increases beyond threshold
            excess_ratio = (latency_ms - self.max_acceptable_ms) / self.max_acceptable_ms
            score = max(0.0, 1.0 - excess_ratio)

        return MetricScore(
            metric_type=MetricType.LATENCY_MS,
            value=latency_ms,
            details={
                "threshold_ms": self.max_acceptable_ms,
                "passed": latency_ms <= self.max_acceptable_ms,
                "performance_score": score,
            },
        )


class ContextRelevanceEvaluator(BaseEvaluator):
    """Evaluate relevance of retrieved context (for RAG)."""

    name = "context_relevance"
    metric_type = MetricType.CONTEXT_RELEVANCE

    def __init__(self, llm_provider: Any, model: str = "gpt-4o"):
        self.llm = llm_provider
        self.model = model

    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Evaluate if retrieved context is relevant to the query."""
        if not test_case.context:
            return MetricScore(
                metric_type=MetricType.CONTEXT_RELEVANCE,
                value=1.0,
                details={"message": "No context provided"},
            )

        try:
            from src.llm.providers.base import CompletionRequest, Message

            prompt = f"""
Rate how relevant each piece of context is to answering the query.

Query: {test_case.input_text}

Context pieces:
{chr(10).join(f'{i+1}. {ctx}' for i, ctx in enumerate(test_case.context))}

For each context piece, rate its relevance from 0-10 where:
- 10 = Highly relevant, directly answers the query
- 5 = Somewhat relevant, provides useful background
- 0 = Not relevant at all

Respond with JSON: {{"relevance_scores": [<score1>, <score2>, ...], "average": <average_score>}}
"""

            request = CompletionRequest(
                messages=[Message(role="user", content=prompt)],
                model=self.model,
                temperature=0.0,
                max_tokens=200,
            )

            response = await self.llm.complete(request)
            content = response.content or ""

            # Parse response
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                avg_score = result.get("average", 5) / 10.0
                scores = result.get("relevance_scores", [])
            else:
                avg_score = 0.5
                scores = []

            return MetricScore(
                metric_type=MetricType.CONTEXT_RELEVANCE,
                value=avg_score,
                details={
                    "individual_scores": scores,
                    "context_count": len(test_case.context),
                },
            )

        except Exception as e:
            return MetricScore(
                metric_type=MetricType.CONTEXT_RELEVANCE,
                value=0.0,
                details={"error": str(e)},
            )


class KeywordEvaluator(BaseEvaluator):
    """Check for presence of expected keywords."""

    name = "keywords"
    metric_type = MetricType.RECALL

    async def evaluate(
        self,
        test_case: TestCase,
        actual_output: str,
        **kwargs,
    ) -> MetricScore:
        """Check keyword presence."""
        if not test_case.expected_keywords:
            return MetricScore(
                metric_type=MetricType.RECALL,
                value=1.0,
                details={"message": "No keywords provided"},
            )

        actual_lower = actual_output.lower()
        found = []
        missing = []

        for keyword in test_case.expected_keywords:
            if keyword.lower() in actual_lower:
                found.append(keyword)
            else:
                missing.append(keyword)

        recall = len(found) / len(test_case.expected_keywords)

        return MetricScore(
            metric_type=MetricType.RECALL,
            value=recall,
            details={
                "found_keywords": found,
                "missing_keywords": missing,
                "total_keywords": len(test_case.expected_keywords),
            },
        )
