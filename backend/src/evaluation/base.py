"""Base classes and data structures for the Evaluation Framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class EvaluationType(str, Enum):
    """Types of evaluation."""
    QUALITY = "quality"           # Overall response quality
    ACCURACY = "accuracy"         # Factual correctness
    RELEVANCE = "relevance"       # Response relevance to query
    HELPFULNESS = "helpfulness"   # How helpful the response is
    SAFETY = "safety"             # Safety and toxicity checks
    LATENCY = "latency"           # Response time benchmarks
    COST = "cost"                 # Token usage and cost
    REGRESSION = "regression"     # Compare against baseline
    AB_TEST = "ab_test"           # A/B comparison between models


class EvaluationStatus(str, Enum):
    """Status of an evaluation run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricType(str, Enum):
    """Types of evaluation metrics."""
    # LLM-as-judge metrics
    LLM_JUDGE_SCORE = "llm_judge_score"
    LLM_JUDGE_REASONING = "llm_judge_reasoning"
    # Similarity metrics
    EXACT_MATCH = "exact_match"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    BLEU = "bleu"
    ROUGE_L = "rouge_l"
    # Classification metrics
    PRECISION = "precision"
    RECALL = "recall"
    F1 = "f1"
    # RAG-specific metrics
    CONTEXT_RELEVANCE = "context_relevance"
    CONTEXT_PRECISION = "context_precision"
    ANSWER_FAITHFULNESS = "answer_faithfulness"
    # Safety metrics
    TOXICITY_SCORE = "toxicity_score"
    BIAS_SCORE = "bias_score"
    # Performance metrics
    LATENCY_MS = "latency_ms"
    TOKENS_USED = "tokens_used"
    COST_USD = "cost_usd"


@dataclass
class TestCase:
    """A single test case for evaluation."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""

    # Input
    input_text: str = ""
    input_messages: list[dict] = field(default_factory=list)
    context: list[str] = field(default_factory=list)  # For RAG evaluation

    # Expected output (optional - for comparison)
    expected_output: Optional[str] = None
    expected_keywords: list[str] = field(default_factory=list)
    expected_facts: list[str] = field(default_factory=list)

    # Configuration
    assistant_id: Optional[UUID] = None
    model: Optional[str] = None
    temperature: float = 0.0  # Use 0 for reproducibility

    # Metadata
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TestSuite:
    """Collection of test cases."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""

    # Test cases
    test_cases: list[TestCase] = field(default_factory=list)

    # Configuration
    evaluation_types: list[EvaluationType] = field(default_factory=list)
    default_model: Optional[str] = None
    default_assistant_id: Optional[UUID] = None

    # Metadata
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MetricScore:
    """A single metric score."""
    metric_type: MetricType
    value: float
    details: dict = field(default_factory=dict)  # Additional info (e.g., reasoning)


@dataclass
class EvaluationResult:
    """Result of evaluating a single test case."""
    id: UUID = field(default_factory=uuid4)
    test_case_id: UUID = field(default_factory=uuid4)
    run_id: UUID = field(default_factory=uuid4)

    # Model output
    actual_output: str = ""
    model_used: str = ""

    # Scores
    scores: list[MetricScore] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = True

    # Performance
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    # Error info
    error: Optional[str] = None

    # Timestamps
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def add_score(self, metric_type: MetricType, value: float, details: dict = None):
        """Add a metric score."""
        self.scores.append(MetricScore(
            metric_type=metric_type,
            value=value,
            details=details or {},
        ))

    def get_score(self, metric_type: MetricType) -> Optional[float]:
        """Get a specific metric score."""
        for score in self.scores:
            if score.metric_type == metric_type:
                return score.value
        return None


@dataclass
class EvaluationRun:
    """An evaluation run across multiple test cases."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""

    # Configuration
    test_suite_id: Optional[UUID] = None
    test_case_ids: list[UUID] = field(default_factory=list)
    evaluation_types: list[EvaluationType] = field(default_factory=list)

    # Model configuration
    model: Optional[str] = None
    model_config: dict = field(default_factory=dict)

    # For A/B testing
    baseline_model: Optional[str] = None
    challenger_model: Optional[str] = None

    # Status
    status: EvaluationStatus = EvaluationStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0

    # Results
    results: list[EvaluationResult] = field(default_factory=list)

    # Aggregate metrics
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    error_tests: int = 0
    average_score: float = 0.0
    average_latency_ms: float = 0.0
    total_cost_usd: float = 0.0

    # Metadata
    created_by: Optional[UUID] = None
    metadata: dict = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def calculate_aggregates(self):
        """Calculate aggregate metrics from results."""
        if not self.results:
            return

        self.total_tests = len(self.results)
        self.passed_tests = sum(1 for r in self.results if r.passed)
        self.failed_tests = sum(1 for r in self.results if not r.passed and not r.error)
        self.error_tests = sum(1 for r in self.results if r.error)

        scores = [r.overall_score for r in self.results if r.overall_score is not None]
        self.average_score = sum(scores) / len(scores) if scores else 0.0

        latencies = [r.latency_ms for r in self.results if r.latency_ms > 0]
        self.average_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

        self.total_cost_usd = sum(r.cost_usd for r in self.results)


@dataclass
class EvaluationConfig:
    """Configuration for running evaluations."""
    # Evaluation types to run
    evaluation_types: list[EvaluationType] = field(default_factory=lambda: [
        EvaluationType.QUALITY,
        EvaluationType.LATENCY,
    ])

    # Thresholds for pass/fail
    min_quality_score: float = 0.7
    max_latency_ms: float = 5000.0
    max_toxicity_score: float = 0.1

    # LLM Judge configuration
    judge_model: str = "gpt-4o"
    judge_temperature: float = 0.0

    # Concurrency
    max_concurrent: int = 5
    timeout_seconds: float = 60.0

    # Retry configuration
    max_retries: int = 2
    retry_delay_seconds: float = 1.0

    # Cost limits
    max_cost_per_run_usd: float = 10.0

    # Sampling (for large test suites)
    sample_size: Optional[int] = None
    sample_seed: Optional[int] = None
