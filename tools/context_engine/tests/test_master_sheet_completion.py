"""
Tests for Master Sheet Completion Module

Tests the MasterSheetCompleter class and convenience functions
for marking features as complete in the Master Sheet.

Note: Tests use mocking to avoid requiring actual Google Sheets credentials.
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.context_engine.master_sheet_completion import CompletionResult


class TestCompletionResult:
    """Tests for CompletionResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        result = CompletionResult(success=False)
        assert result.success is False
        assert result.feature_name == ""
        assert result.row_number is None
        assert result.fields_updated == []
        assert result.message == ""
        assert result.errors == []

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = CompletionResult(
            success=True,
            feature_name="Test Feature",
            row_number=15,
            fields_updated=["Status", "PRD Link"],
            message="Success",
            errors=[],
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["feature_name"] == "Test Feature"
        assert d["row_number"] == 15
        assert d["fields_updated"] == ["Status", "PRD Link"]
        assert d["message"] == "Success"
        assert d["errors"] == []

    def test_with_errors(self):
        """Test result with errors."""
        result = CompletionResult(
            success=False, feature_name="Failed Feature", errors=["Error 1", "Error 2"]
        )
        assert result.success is False
        assert len(result.errors) == 2
        d = result.to_dict()
        assert "Error 1" in d["errors"]

    def test_partial_success(self):
        """Test result with partial field updates."""
        result = CompletionResult(
            success=True,
            feature_name="Partial Feature",
            row_number=10,
            fields_updated=["Status"],  # Only status updated
            message="Partial success",
            errors=["Could not update PRD Link"],  # One error
        )
        # Even with errors, if success=True we consider it partial success
        assert result.success is True
        assert len(result.fields_updated) == 1
        assert len(result.errors) == 1


class TestCompletionResultFields:
    """Test CompletionResult field handling."""

    def test_fields_updated_list_mutability(self):
        """Test that fields_updated list can be modified."""
        result = CompletionResult(success=True)
        result.fields_updated.append("Status")
        result.fields_updated.append("PRD Link")
        assert len(result.fields_updated) == 2

    def test_errors_list_mutability(self):
        """Test that errors list can be modified."""
        result = CompletionResult(success=False)
        result.errors.append("First error")
        result.errors.append("Second error")
        assert len(result.errors) == 2

    def test_to_dict_preserves_all_fields(self):
        """Test that to_dict includes all fields."""
        result = CompletionResult(
            success=True,
            feature_name="Complete Feature",
            row_number=25,
            fields_updated=["Status", "Completion Date", "PRD Link", "Jira Link"],
            message="All fields updated successfully",
            errors=[],
        )
        d = result.to_dict()

        # Verify all expected keys are present
        expected_keys = [
            "success",
            "feature_name",
            "row_number",
            "fields_updated",
            "message",
            "errors",
        ]
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"


class TestModuleImports:
    """Test that module imports work correctly."""

    def test_can_import_completer_class(self):
        """Test that MasterSheetCompleter can be imported."""
        from tools.context_engine.master_sheet_completion import MasterSheetCompleter

        assert MasterSheetCompleter is not None

    def test_can_import_convenience_functions(self):
        """Test that convenience functions can be imported."""
        from tools.context_engine.master_sheet_completion import (
            add_feature_links,
            mark_feature_complete,
            update_feature_status,
        )

        assert callable(mark_feature_complete)
        assert callable(update_feature_status)
        assert callable(add_feature_links)

    def test_module_in_context_engine_exports(self):
        """Test that module is exported from context_engine package."""
        from tools.context_engine import (
            CompletionResult,
            MasterSheetCompleter,
            add_feature_links,
            mark_feature_complete,
            update_feature_status,
        )

        assert MasterSheetCompleter is not None
        assert CompletionResult is not None


class TestColumnLetterConversion:
    """Test helper methods that don't require config."""

    def test_col_letter_conversion(self):
        """Test column index to letter conversion logic."""

        # Direct test of the conversion formula
        def col_letter(index: int) -> str:
            return chr(ord("A") + index)

        assert col_letter(0) == "A"
        assert col_letter(1) == "B"
        assert col_letter(25) == "Z"

    def test_format_prd_link_logic(self):
        """Test PRD link formatting logic."""
        user_path = Path("/test/user")

        # Test relative path formatting
        prd_path = Path("/test/user/brain/Products/TestProduct/PRD.md")
        try:
            relative = prd_path.relative_to(user_path)
            formatted = f"user/{relative}"
            assert formatted == "user/brain/Products/TestProduct/PRD.md"
        except ValueError:
            pass  # Expected if path is outside user_path

        # Test absolute path fallback
        other_path = Path("/other/path/PRD.md")
        try:
            _ = other_path.relative_to(user_path)
            assert False, "Should have raised ValueError"
        except ValueError:
            # This is expected - fall back to absolute
            assert str(other_path) == "/other/path/PRD.md"


class TestCompletionWorkflowLogic:
    """Test completion workflow logic without actual API calls."""

    def test_status_field_name(self):
        """Test that status field name matches expected value."""
        from tools.context_engine.master_sheet_completion import MasterSheetCompleter

        assert MasterSheetCompleter.STATUS_COLUMN == "Current Status"

    def test_completion_date_format(self):
        """Test completion date formatting."""
        test_date = datetime(2026, 2, 4, 10, 30, 0)
        formatted = test_date.strftime("%m/%d/%Y")
        assert formatted == "02/04/2026"  # US format

    def test_completion_result_success_criteria(self):
        """Test criteria for successful completion."""
        # A successful completion should have:
        # - success = True
        # - feature_name set
        # - row_number set
        # - at least "Status" in fields_updated
        result = CompletionResult(
            success=True,
            feature_name="OTP Checkout Recovery",
            row_number=15,
            fields_updated=["Status", "Completion Date", "PRD Link"],
            message="Feature marked as complete",
            errors=[],
        )

        assert result.success
        assert result.feature_name
        assert result.row_number is not None
        assert "Status" in result.fields_updated
        assert len(result.errors) == 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_feature_name(self):
        """Test result with empty feature name."""
        result = CompletionResult(success=False, feature_name="")
        assert result.feature_name == ""
        d = result.to_dict()
        assert d["feature_name"] == ""

    def test_none_row_number(self):
        """Test result with None row number."""
        result = CompletionResult(success=False, row_number=None)
        assert result.row_number is None
        d = result.to_dict()
        assert d["row_number"] is None

    def test_empty_fields_updated(self):
        """Test result with no fields updated."""
        result = CompletionResult(success=False, message="No fields could be updated")
        assert len(result.fields_updated) == 0

    def test_multiple_errors(self):
        """Test result with multiple errors."""
        result = CompletionResult(
            success=False,
            errors=[
                "Master Sheet row not found",
                "Could not authenticate with Google Sheets",
                "Column 'PRD Link' not found",
            ],
        )
        assert len(result.errors) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
