"""Evaluation Runner - Execute evaluations across test suites."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from src.evaluation.base import (
    EvaluationConfig,
    EvaluationResult,
    EvaluationRun,
    EvaluationStatus,
    EvaluationType,
    MetricType,
    TestCase,
    TestSuite,
)
from src.evaluation.evaluators import (
    BaseEvaluator,
    LLMJudgeEvaluator,
    ExactMatchEvaluator,
    SemanticSimilarityEvaluator,
    FactualityEvaluator,
    ToxicityEvaluator,
    LatencyEvaluator,
    ContextRelevanceEvaluator,
    KeywordEvaluator,
)

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Runner for executing evaluation test suites.

    Example:
        >>> runner = EvaluationRunner(llm_provider, embedding_provider)
        >>> result = await runner.run_suite(test_suite, config)
        >>> print(f"Average score: {result.average_score}")
    """

    def __init__(
        self,
        llm_provider: Any,
        embedding_provider: Any = None,
        assistant_runner: Callable = None,
        config: EvaluationConfig = None,
    ):
        """Initialize the evaluation runner.

        Args:
            llm_provider: LLM provider for running tests and LLM-as-judge
            embedding_provider: Embedding provider for semantic similarity
            assistant_runner: Callable to run assistant (takes test_case, returns output)
            config: Evaluation configuration
        """
        self.llm = llm_provider
        self.embeddings = embedding_provider
        self.assistant_runner = assistant_runner
        self.config = config or EvaluationConfig()

        # Initialize evaluators
        self.evaluators: dict[EvaluationType, list[BaseEvaluator]] = {
            EvaluationType.QUALITY: [
                LLMJudgeEvaluator(llm_provider, config.judge_model if config else "gpt-4o", "quality"),
            ],
            EvaluationType.RELEVANCE: [
                LLMJudgeEvaluator(llm_provider, config.judge_model if config else "gpt-4o", "relevance"),
            ],
            EvaluationType.HELPFULNESS: [
                LLMJudgeEvaluator(llm_provider, config.judge_model if config else "gpt-4o", "helpfulness"),
            ],
            EvaluationType.ACCURACY: [
                FactualityEvaluator(),
                KeywordEvaluator(),
            ],
            EvaluationType.SAFETY: [
                ToxicityEvaluator(),
            ],
            EvaluationType.LATENCY: [
                LatencyEvaluator(config.max_latency_ms if config else 5000),
            ],
        }

        # Add semantic similarity if embeddings available
        if embedding_provider:
            self.evaluators[EvaluationType.ACCURACY].append(
                SemanticSimilarityEvaluator(embedding_provider)
            )

    async def run_suite(
        self,
        suite: TestSuite,
        config: EvaluationConfig = None,
        progress_callback: Callable[[float], None] = None,
    ) -> EvaluationRun:
        """Run evaluation on a test suite.

        Args:
            suite: Test suite to evaluate
            config: Override config for this run
            progress_callback: Optional callback for progress updates

        Returns:
            EvaluationRun with all results
        """
        config = config or self.config

        run = EvaluationRun(
            name=f"Evaluation of {suite.name}",
            test_suite_id=suite.id,
            test_case_ids=[tc.id for tc in suite.test_cases],
            evaluation_types=suite.evaluation_types or config.evaluation_types,
            model=suite.default_model,
            status=EvaluationStatus.RUNNING,
            started_at=datetime.utcnow(),
        )

        try:
            # Optionally sample test cases
            test_cases = suite.test_cases
            if config.sample_size and len(test_cases) > config.sample_size:
                import random
                if config.sample_seed:
                    random.seed(config.sample_seed)
                test_cases = random.sample(test_cases, config.sample_size)

            # Run evaluations with concurrency limit
            semaphore = asyncio.Semaphore(config.max_concurrent)
            tasks = []

            for i, test_case in enumerate(test_cases):
                task = self._run_with_semaphore(
                    semaphore,
                    test_case,
                    run,
                    config,
                )
                tasks.append(task)

            # Process results as they complete
            completed = 0
            for coro in asyncio.as_completed(tasks):
                result = await coro
                run.results.append(result)
                completed += 1

                run.progress = completed / len(test_cases)
                if progress_callback:
                    progress_callback(run.progress)

            # Calculate aggregates
            run.calculate_aggregates()
            run.status = EvaluationStatus.COMPLETED
            run.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Evaluation run failed: {e}")
            run.status = EvaluationStatus.FAILED
            run.metadata["error"] = str(e)

        return run

    async def _run_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        test_case: TestCase,
        run: EvaluationRun,
        config: EvaluationConfig,
    ) -> EvaluationResult:
        """Run a single test case with semaphore for concurrency control."""
        async with semaphore:
            return await self.run_single(test_case, run, config)

    async def run_single(
        self,
        test_case: TestCase,
        run: EvaluationRun = None,
        config: EvaluationConfig = None,
    ) -> EvaluationResult:
        """Run evaluation on a single test case.

        Args:
            test_case: Test case to evaluate
            run: Optional parent run
            config: Evaluation config

        Returns:
            EvaluationResult with scores
        """
        config = config or self.config
        run_id = run.id if run else None
        evaluation_types = run.evaluation_types if run else config.evaluation_types

        result = EvaluationResult(
            test_case_id=test_case.id,
            run_id=run_id,
            started_at=datetime.utcnow(),
        )

        try:
            # Get the model output
            start_time = time.time()

            if self.assistant_runner:
                actual_output = await self.assistant_runner(test_case)
            else:
                actual_output = await self._default_runner(test_case, run)

            elapsed_ms = (time.time() - start_time) * 1000

            result.actual_output = actual_output
            result.latency_ms = elapsed_ms
            result.model_used = test_case.model or (run.model if run else "unknown")

            # Run evaluators for each evaluation type
            for eval_type in evaluation_types:
                evaluators = self.evaluators.get(eval_type, [])

                for evaluator in evaluators:
                    try:
                        score = await asyncio.wait_for(
                            evaluator.evaluate(
                                test_case,
                                actual_output,
                                latency_ms=elapsed_ms,
                            ),
                            timeout=config.timeout_seconds,
                        )
                        result.scores.append(score)
                    except asyncio.TimeoutError:
                        logger.warning(f"Evaluator {evaluator.name} timed out")
                    except Exception as e:
                        logger.warning(f"Evaluator {evaluator.name} failed: {e}")

            # Calculate overall score (average of all scores)
            if result.scores:
                # Normalize all scores to 0-1 range
                normalized_scores = []
                for score in result.scores:
                    if score.metric_type == MetricType.LATENCY_MS:
                        # For latency, use the performance score from details
                        perf_score = score.details.get("performance_score", 0.5)
                        normalized_scores.append(perf_score)
                    elif score.metric_type == MetricType.TOXICITY_SCORE:
                        # For toxicity, lower is better (invert)
                        normalized_scores.append(1.0 - score.value)
                    else:
                        normalized_scores.append(score.value)

                result.overall_score = sum(normalized_scores) / len(normalized_scores)

                # Determine pass/fail
                result.passed = (
                    result.overall_score >= config.min_quality_score
                    and result.latency_ms <= config.max_latency_ms
                )

            result.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Test case {test_case.id} failed: {e}")
            result.error = str(e)
            result.passed = False
            result.completed_at = datetime.utcnow()

        return result

    async def _default_runner(
        self,
        test_case: TestCase,
        run: EvaluationRun = None,
    ) -> str:
        """Default runner using LLM directly."""
        from src.llm.providers.base import CompletionRequest, Message

        # Build messages
        messages = []
        if test_case.input_messages:
            messages = [Message(**m) for m in test_case.input_messages]
        else:
            messages = [Message(role="user", content=test_case.input_text)]

        # Add context if available (for RAG evaluation)
        if test_case.context:
            context_text = "\n\n".join(test_case.context)
            system_msg = f"Use the following context to answer the question:\n\n{context_text}"
            messages.insert(0, Message(role="system", content=system_msg))

        model = test_case.model or (run.model if run else "gpt-4o")

        request = CompletionRequest(
            messages=messages,
            model=model,
            temperature=test_case.temperature,
            max_tokens=4096,
        )

        response = await self.llm.complete(request)
        return response.content or ""

    async def compare_models(
        self,
        test_cases: list[TestCase],
        model_a: str,
        model_b: str,
        config: EvaluationConfig = None,
    ) -> dict:
        """Run A/B comparison between two models.

        Args:
            test_cases: Test cases to evaluate
            model_a: First model (baseline)
            model_b: Second model (challenger)
            config: Evaluation config

        Returns:
            Comparison results with per-model scores
        """
        config = config or self.config

        # Create test suites for each model
        suite_a = TestSuite(
            name=f"Model A ({model_a})",
            test_cases=[
                TestCase(**{**tc.__dict__, "model": model_a})
                for tc in test_cases
            ],
            evaluation_types=config.evaluation_types,
        )

        suite_b = TestSuite(
            name=f"Model B ({model_b})",
            test_cases=[
                TestCase(**{**tc.__dict__, "model": model_b})
                for tc in test_cases
            ],
            evaluation_types=config.evaluation_types,
        )

        # Run both
        results_a, results_b = await asyncio.gather(
            self.run_suite(suite_a, config),
            self.run_suite(suite_b, config),
        )

        # Compare
        comparison = {
            "model_a": {
                "name": model_a,
                "average_score": results_a.average_score,
                "average_latency_ms": results_a.average_latency_ms,
                "passed_tests": results_a.passed_tests,
                "total_tests": results_a.total_tests,
                "pass_rate": results_a.passed_tests / results_a.total_tests if results_a.total_tests > 0 else 0,
            },
            "model_b": {
                "name": model_b,
                "average_score": results_b.average_score,
                "average_latency_ms": results_b.average_latency_ms,
                "passed_tests": results_b.passed_tests,
                "total_tests": results_b.total_tests,
                "pass_rate": results_b.passed_tests / results_b.total_tests if results_b.total_tests > 0 else 0,
            },
            "winner": None,
            "score_difference": results_b.average_score - results_a.average_score,
            "latency_difference_ms": results_b.average_latency_ms - results_a.average_latency_ms,
        }

        # Determine winner (higher score wins, latency as tiebreaker)
        if results_a.average_score > results_b.average_score + 0.05:
            comparison["winner"] = model_a
        elif results_b.average_score > results_a.average_score + 0.05:
            comparison["winner"] = model_b
        elif results_a.average_latency_ms < results_b.average_latency_ms:
            comparison["winner"] = model_a
        else:
            comparison["winner"] = model_b

        return comparison

    async def run_regression_test(
        self,
        test_cases: list[TestCase],
        current_model: str,
        baseline_results: list[EvaluationResult],
        config: EvaluationConfig = None,
        regression_threshold: float = 0.05,
    ) -> dict:
        """Run regression test against baseline.

        Args:
            test_cases: Test cases to evaluate
            current_model: Current model to test
            baseline_results: Previous baseline results
            config: Evaluation config
            regression_threshold: Max acceptable score decrease

        Returns:
            Regression test results
        """
        config = config or self.config

        # Run current model
        suite = TestSuite(
            name=f"Regression test for {current_model}",
            test_cases=[
                TestCase(**{**tc.__dict__, "model": current_model})
                for tc in test_cases
            ],
            evaluation_types=config.evaluation_types,
        )

        current_run = await self.run_suite(suite, config)

        # Build baseline lookup
        baseline_by_case = {r.test_case_id: r for r in baseline_results}

        # Compare each result
        regressions = []
        improvements = []

        for current_result in current_run.results:
            baseline = baseline_by_case.get(current_result.test_case_id)
            if not baseline:
                continue

            score_diff = current_result.overall_score - baseline.overall_score

            if score_diff < -regression_threshold:
                regressions.append({
                    "test_case_id": str(current_result.test_case_id),
                    "baseline_score": baseline.overall_score,
                    "current_score": current_result.overall_score,
                    "regression": abs(score_diff),
                })
            elif score_diff > regression_threshold:
                improvements.append({
                    "test_case_id": str(current_result.test_case_id),
                    "baseline_score": baseline.overall_score,
                    "current_score": current_result.overall_score,
                    "improvement": score_diff,
                })

        # Calculate baseline average
        baseline_avg = sum(r.overall_score for r in baseline_results) / len(baseline_results) if baseline_results else 0

        return {
            "passed": len(regressions) == 0,
            "current_average_score": current_run.average_score,
            "baseline_average_score": baseline_avg,
            "score_change": current_run.average_score - baseline_avg,
            "regressions": regressions,
            "improvements": improvements,
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
            "total_tests": current_run.total_tests,
        }
