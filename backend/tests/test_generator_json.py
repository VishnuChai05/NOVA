"""
Unit tests for evaluate_output JSON fix (Bug #3).

Verifies that rubric_json stores valid JSON, not Python repr() format.
"""

import json

import pytest

from app.services.generator import evaluate_output


class TestGeneratorJSON:
    """Test generator evaluate_output JSON formatting."""

    def test_evaluate_output_returns_valid_json_rubric(self):
        """
        Test that evaluate_output returns valid JSON in rubric_json field.
        
        BUG FIX #3: Previously returned str(rubric) which uses Python repr() format
        with True/False and single quotes. Now uses json.dumps() for valid JSON.
        """
        title = "Test Title About Bra Fitting"
        content = """
        Section 1: Best Bra Styles
        For women seeking comfort, the right fit matters. Quality support ensures all-day wear.
        
        Section 2: Recommendations
        Discover these top-rated styles. Try our nova collection today.
        
        Key Features:
        - Comfort technology
        - Professional fit
        - Recommend to friends
        """ * 2  # Make it long enough

        score, rubric_json = evaluate_output(title, content)

        # Verify rubric_json is valid JSON
        assert isinstance(rubric_json, str)
        
        # This should parse without error - if it's Python repr() format it will fail
        rubric_parsed = json.loads(rubric_json)
        assert isinstance(rubric_parsed, dict)
        
        # Verify JSON format (true, false, not True, False)
        # At least one boolean should be present
        has_json_bool = "true" in rubric_json or "false" in rubric_json
        assert has_json_bool, "JSON should contain lowercase true/false booleans"
        
        # Verify no Python repr() artifacts
        # Check for Python True/False (uppercase)
        assert "True" not in rubric_json, "Should not have Python True keyword"
        assert "False" not in rubric_json, "Should not have Python False keyword"
        assert "'" not in rubric_json or "'\n" not in rubric_json, "JSON should use double quotes, not single quotes"

    def test_evaluate_output_rubric_has_required_fields(self):
        """Test that rubric JSON contains expected scoring fields."""
        title = "Best Shapewear Guide"
        content = """
        H1: Complete Shapewear Review
        Comfort and support are essential. Discover our product recommendations today.
        
        H2: Why Quality Matters
        Women deserve products that fit well. We recommend testing multiple brands.
        This guide helps you find the perfect fit.
        """ * 2

        score, rubric_json = evaluate_output(title, content)

        rubric_parsed = json.loads(rubric_json)
        
        # Verify expected fields are in JSON
        expected_fields = [
            "title_quality",
            "has_cta",
            "brand_mention",
            "readability",
            "structure",
            "content_length",
            "keyword_relevance",
            "formatting",
        ]
        for field in expected_fields:
            assert field in rubric_parsed, f"Expected field '{field}' not in rubric"
            assert "pass" in rubric_parsed[field]
            assert "weight" in rubric_parsed[field]

    def test_evaluate_output_json_roundtrip(self):
        """Test that JSON can be serialized and deserialized correctly."""
        title = "Period Care Tips"
        content = """
        Section A: Understanding Your Cycle
        Proper products provide comfort and security. Women recommend using quality materials.
        
        Section B: Nova Product Review
        Discover why our products excel. Try them today for the best fit.
        Features include comfort, reliability, and style.
        """ * 2

        score, rubric_json = evaluate_output(title, content)

        # Parse and re-serialize - should be identical or equivalent
        parsed = json.loads(rubric_json)
        reserialized = json.dumps(parsed)
        
        # Re-parse to verify no data loss
        reparsed = json.loads(reserialized)
        
        # Verify structure is preserved
        assert "title_quality" in reparsed
        assert "pass" in reparsed["title_quality"]
        assert "weight" in reparsed["title_quality"]
        
        # Verify boolean types are correct
        for field, details in reparsed.items():
            assert isinstance(details["pass"], bool)
            assert isinstance(details["weight"], (int, float))

    @pytest.mark.parametrize("boolean_value,json_representation", [
        (True, "true"),
        (False, "false"),
    ])
    def test_json_boolean_formatting(self, boolean_value, json_representation):
        """Test that JSON booleans are formatted correctly (lowercase)."""
        # This tests the raw json.dumps behavior
        test_dict = {"test_bool": boolean_value}
        json_str = json.dumps(test_dict)
        
        # Verify JSON representation uses lowercase true/false
        assert json_representation in json_str
        assert not ("True" in json_str or "False" in json_str)
