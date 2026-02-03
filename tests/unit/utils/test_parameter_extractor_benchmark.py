"""
Parameter Extraction Algorithm Benchmark Test

This test module provides a benchmark framework for tracking the improvement
of the parameter extraction algorithm over time.

Features:
- Loads sample descriptions from compressed JSON
- Applies current algorithm to all samples
- Compares extracted vs expected parameters
- Calculates success metrics (precision, recall, accuracy)
- Optionally saves results to tracking file for historical comparison

Usage:
    # Run benchmark and see results
    pytest tests/unit/utils/test_parameter_extractor_benchmark.py -v

    # Run and save results to tracking file
    pytest tests/unit/utils/test_parameter_extractor_benchmark.py -v --save-benchmark

Author: Synapse Team
License: MIT
"""

import gzip
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pytest

from src.utils.parameter_extractor import extract_from_description

logger = logging.getLogger(__name__)


# =============================================================================
# Paths
# =============================================================================

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "civitai"
BENCHMARK_FILE = FIXTURES_DIR / "descriptions_benchmark.json.gz"
RESULTS_FILE = FIXTURES_DIR / "extraction_results.json"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def benchmark_data() -> Dict[str, Any]:
    """Load benchmark samples from compressed JSON."""
    with gzip.open(BENCHMARK_FILE, "rt", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def samples(benchmark_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get list of sample descriptions."""
    return benchmark_data["samples"]


# =============================================================================
# Metrics Calculation
# =============================================================================

def calculate_param_match(
    extracted: Dict[str, Any],
    expected: Dict[str, Any]
) -> Tuple[int, int, int, int]:
    """
    Calculate matching statistics between extracted and expected parameters.

    Returns:
        Tuple of (true_positives, false_positives, false_negatives, exact_matches)
    """
    extracted_keys = set(extracted.keys())
    expected_keys = set(expected.keys())

    # True positives: keys that exist in both
    tp_keys = extracted_keys & expected_keys
    true_positives = len(tp_keys)

    # False positives: extracted but not expected
    false_positives = len(extracted_keys - expected_keys)

    # False negatives: expected but not extracted
    false_negatives = len(expected_keys - extracted_keys)

    # Exact matches: key exists and value matches
    exact_matches = 0
    for key in tp_keys:
        extracted_val = extracted[key]
        expected_val = expected[key]

        # Handle float comparison with tolerance
        if isinstance(expected_val, float) and isinstance(extracted_val, (int, float)):
            if abs(float(extracted_val) - expected_val) < 0.01:
                exact_matches += 1
        elif extracted_val == expected_val:
            exact_matches += 1

    return true_positives, false_positives, false_negatives, exact_matches


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculate overall benchmark metrics from individual results.

    Returns:
        Dictionary with precision, recall, f1_score, exact_match_rate, etc.
    """
    total_tp = sum(r["true_positives"] for r in results)
    total_fp = sum(r["false_positives"] for r in results)
    total_fn = sum(r["false_negatives"] for r in results)
    total_exact = sum(r["exact_matches"] for r in results)
    total_expected = sum(len(r["expected"]) for r in results)
    total_samples = len(results)

    # Samples with all parameters correctly extracted
    perfect_samples = sum(
        1 for r in results
        if r["exact_matches"] == len(r["expected"]) and r["false_positives"] == 0
    )

    # Samples with at least one correct extraction
    partial_samples = sum(1 for r in results if r["true_positives"] > 0)

    # Precision: of what we extracted, how many were correct keys
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0

    # Recall: of what we should have extracted, how many did we get
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0

    # F1 Score
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Exact match rate: values that match exactly
    exact_rate = total_exact / total_expected if total_expected > 0 else 0.0

    return {
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1_score": round(f1 * 100, 2),
        "exact_match_rate": round(exact_rate * 100, 2),
        "perfect_samples": perfect_samples,
        "partial_samples": partial_samples,
        "total_samples": total_samples,
        "total_expected_params": total_expected,
        "total_extracted_params": total_tp + total_fp,
        "total_exact_matches": total_exact,
    }


# =============================================================================
# Benchmark Test
# =============================================================================

class TestParameterExtractionBenchmark:
    """Benchmark tests for parameter extraction algorithm."""

    def test_benchmark_file_exists(self):
        """Verify benchmark file exists."""
        assert BENCHMARK_FILE.exists(), f"Benchmark file not found: {BENCHMARK_FILE}"

    def test_benchmark_file_valid(self, benchmark_data):
        """Verify benchmark file structure."""
        assert "version" in benchmark_data
        assert "samples" in benchmark_data
        assert len(benchmark_data["samples"]) > 0

    def test_run_full_benchmark(self, samples, request):
        """
        Run the full benchmark and report results.

        This test:
        1. Applies algorithm to all samples
        2. Calculates metrics
        3. Reports summary
        4. Optionally saves to results file
        """
        results = []

        for sample in samples:
            sample_id = sample["id"]
            description = sample["description"]
            expected = sample.get("expected", {})

            # Run extraction
            extraction_result = extract_from_description(description)
            extracted = extraction_result.parameters

            # Calculate match statistics
            tp, fp, fn, exact = calculate_param_match(extracted, expected)

            results.append({
                "id": sample_id,
                "expected": expected,
                "extracted": extracted,
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "exact_matches": exact,
            })

            # Log individual failures for debugging
            if fn > 0 or fp > 0:
                logger.info(
                    f"[{sample_id}] Expected: {expected}, Got: {extracted}, "
                    f"TP={tp}, FP={fp}, FN={fn}, Exact={exact}"
                )

        # Calculate overall metrics
        metrics = calculate_metrics(results)

        # Print summary
        print("\n" + "=" * 70)
        print("PARAMETER EXTRACTION BENCHMARK RESULTS")
        print("=" * 70)
        print(f"Total Samples:        {metrics['total_samples']}")
        print(f"Perfect Extractions:  {metrics['perfect_samples']} ({metrics['perfect_samples']/metrics['total_samples']*100:.1f}%)")
        print(f"Partial Extractions:  {metrics['partial_samples']} ({metrics['partial_samples']/metrics['total_samples']*100:.1f}%)")
        print("-" * 70)
        print(f"Precision:            {metrics['precision']:.2f}%")
        print(f"Recall:               {metrics['recall']:.2f}%")
        print(f"F1 Score:             {metrics['f1_score']:.2f}%")
        print(f"Exact Match Rate:     {metrics['exact_match_rate']:.2f}%")
        print("-" * 70)
        print(f"Expected Params:      {metrics['total_expected_params']}")
        print(f"Extracted Params:     {metrics['total_extracted_params']}")
        print(f"Exact Value Matches:  {metrics['total_exact_matches']}")
        print("=" * 70)

        # Check if we should save results
        if request.config.getoption("--save-benchmark", default=False):
            self._save_results(metrics, results)

        # Assert minimum quality threshold
        # This can be adjusted as algorithm improves
        assert metrics["recall"] >= 50.0, f"Recall too low: {metrics['recall']}%"
        assert metrics["precision"] >= 50.0, f"Precision too low: {metrics['precision']}%"

    def _save_results(self, metrics: Dict[str, float], details: List[Dict]) -> None:
        """Save benchmark results to tracking file."""
        run_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "algorithm_version": "1.0.0",  # Update when algorithm changes
            "metrics": metrics,
            "sample_count": len(details),
        }

        # Load existing results
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, "r") as f:
                history = json.load(f)
        else:
            history = {"description": "Historical benchmark results", "runs": []}

        # Append new run
        history["runs"].append(run_data)

        # Save
        with open(RESULTS_FILE, "w") as f:
            json.dump(history, f, indent=2)

        print(f"\nResults saved to: {RESULTS_FILE}")


# =============================================================================
# Individual Sample Tests (for debugging)
# =============================================================================

class TestIndividualSamples:
    """Test individual samples for debugging extraction issues."""

    @pytest.mark.parametrize("sample_id", [
        "sample_001",
        "sample_002",
        "sample_003",
        "sample_008",
        "sample_011",
    ])
    def test_specific_sample(self, samples, sample_id):
        """Test a specific sample by ID."""
        sample = next((s for s in samples if s["id"] == sample_id), None)
        assert sample is not None, f"Sample {sample_id} not found"

        result = extract_from_description(sample["description"])
        expected = sample.get("expected", {})

        # Check that at least some expected params were found
        found_keys = set(result.parameters.keys()) & set(expected.keys())

        # Log for debugging
        print(f"\n[{sample_id}]")
        print(f"  Description: {sample['description'][:80]}...")
        print(f"  Expected: {expected}")
        print(f"  Extracted: {result.parameters}")
        print(f"  Found: {found_keys}")

        # For now, just check that extraction runs without error
        # Specific assertions can be added per sample


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--save-benchmark",
        action="store_true",
        default=False,
        help="Save benchmark results to tracking file",
    )
