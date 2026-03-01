"""Evaluation Framework - Test and benchmark AI assistant quality.

Features:
- Test case management
- Automated evaluation runs
- Quality metrics (relevance, accuracy, helpfulness)
- A/B testing support
- Regression detection
- Performance benchmarking
- Human feedback collection
"""

from src.evaluation.base import (
    EvaluationType,
    EvaluationStatus,
    MetricType,
    TestCase,
    TestSuite,
    EvaluationRun,
    EvaluationResult,
    MetricScore,
)
from src.evaluation.evaluators import (
    BaseEvaluator,
    LLMJudgeEvaluator,
    ExactMatchEvaluator,
    SemanticSimilarityEvaluator,
    FactualityEvaluator,
    ToxicityEvaluator,
    LatencyEvaluator,
)
from src.evaluation.runner import EvaluationRunner
from src.evaluation.metrics import (
    calculate_precision,
    calculate_recall,
    calculate_f1,
    calculate_bleu,
    calculate_rouge,
)

__all__ = [
    # Enums
    "EvaluationType",
    "EvaluationStatus",
    "MetricType",
    # Data classes
    "TestCase",
    "TestSuite",
    "EvaluationRun",
    "EvaluationResult",
    "MetricScore",
    # Evaluators
    "BaseEvaluator",
    "LLMJudgeEvaluator",
    "ExactMatchEvaluator",
    "SemanticSimilarityEvaluator",
    "FactualityEvaluator",
    "ToxicityEvaluator",
    "LatencyEvaluator",
    # Runner
    "EvaluationRunner",
    # Metrics
    "calculate_precision",
    "calculate_recall",
    "calculate_f1",
    "calculate_bleu",
    "calculate_rouge",
]
