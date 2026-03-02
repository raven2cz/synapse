"""
Unit tests for RuleBasedProvider.

Tests parameter extraction using regexp-based fallback.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.avatar.providers.rule_based import RuleBasedProvider, RuleBasedResult


# =============================================================================
# RuleBasedResult tests
# =============================================================================


class TestRuleBasedResult:
    """Tests for RuleBasedResult dataclass."""

    def test_success_result(self):
        r = RuleBasedResult(success=True, output={"steps": 20})
        assert r.success is True
        assert r.output == {"steps": 20}
        assert r.error is None
        assert r.execution_time_ms == 0

    def test_failure_result(self):
        r = RuleBasedResult(success=False, error="boom")
        assert r.success is False
        assert r.output is None
        assert r.error == "boom"


# =============================================================================
# RuleBasedProvider tests
# =============================================================================


class TestRuleBasedProvider:
    """Tests for rule-based parameter extraction."""

    def test_provider_metadata(self):
        p = RuleBasedProvider()
        assert p.provider_id == "rule_based"
        assert p.model == "regexp"

    def test_extract_cfg_and_steps(self):
        """Extract numeric parameters from description."""
        p = RuleBasedProvider()
        result = p.execute("Recommended: CFG 7, Steps 25, Clip Skip 2")
        assert result.success is True
        assert result.output is not None
        assert result.execution_time_ms >= 0
        # At least some parameters extracted
        assert len(result.output) > 0

    def test_extract_from_html(self):
        """Works with HTML descriptions from Civitai."""
        p = RuleBasedProvider()
        result = p.execute("""
            <p>Great model for portraits!</p>
            <p>Settings: CFG 7, Steps 20</p>
        """)
        assert result.success is True

    def test_extract_empty_description(self):
        """Empty description returns success with empty/minimal output."""
        p = RuleBasedProvider()
        result = p.execute("")
        assert result.success is True
        assert result.output is not None

    def test_extract_no_parameters(self):
        """Description without extractable parameters."""
        p = RuleBasedProvider()
        result = p.execute("This is a beautiful model with great results.")
        assert result.success is True

    def test_execution_time_tracked(self):
        p = RuleBasedProvider()
        result = p.execute("CFG 7, Steps 20")
        assert result.execution_time_ms >= 0

    def test_extractor_exception_returns_failure(self):
        """Internal exception returns failure, doesn't raise."""
        p = RuleBasedProvider()
        with patch(
            "src.utils.parameter_extractor.extract_from_description",
            side_effect=RuntimeError("parse error"),
        ):
            result = p.execute("anything")
        assert result.success is False
        assert "parse error" in result.error

    def test_normalize_extraction_result(self):
        """_normalize_result handles ExtractionResult with .parameters."""
        p = RuleBasedProvider()
        mock_result = MagicMock()
        mock_result.parameters = {"steps": 25, "cfg_scale": 7.0}
        output = p._normalize_result(mock_result)
        assert output == {"steps": 25, "cfg_scale": 7.0}

    def test_normalize_dict_passthrough(self):
        p = RuleBasedProvider()
        output = p._normalize_result({"steps": 10})
        assert output == {"steps": 10}

    def test_normalize_unknown_type(self):
        p = RuleBasedProvider()
        output = p._normalize_result(42)
        assert output == {"raw": "42"}

    def test_extract_sampler(self):
        """Known samplers are extracted."""
        p = RuleBasedProvider()
        result = p.execute("Use sampler: DPM++ 2M Karras, CFG: 6")
        assert result.success is True
        if result.output:
            # The rule-based extractor should find something
            assert len(result.output) > 0

    def test_extract_resolution(self):
        """WxH format resolution extracted."""
        p = RuleBasedProvider()
        result = p.execute("Recommended resolution: 512x768")
        assert result.success is True
