"""
Tests for ProductIdentifier module.

Tests the product identification logic following PRD Section C.6 priority order:
1. Explicit flag
2. Master Sheet lookup
3. Daily context
4. Channel inference
5. User selection
"""

import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from context_engine.product_identifier import (
    IdentificationResult,
    IdentificationSource,
    ProductInfo,
)


class TestProductInfo:
    """Tests for ProductInfo dataclass."""

    def test_product_info_creation(self):
        """Test creating a ProductInfo object."""
        product = ProductInfo(
            id="meal-kit",
            name="Meal Kit",
            type="brand",
            jira_project="MK",
            squad="Meal Kit Squad",
            market="US",
            status="active",
            abbreviation="MK",
        )

        assert product.id == "meal-kit"
        assert product.name == "Meal Kit"
        assert product.jira_project == "MK"
        assert product.status == "active"

    def test_product_info_to_dict(self):
        """Test converting ProductInfo to dictionary."""
        product = ProductInfo(
            id="wellness-brand",
            name="Wellness Brand",
        )

        result = product.to_dict()

        assert result["id"] == "wellness-brand"
        assert result["name"] == "Wellness Brand"
        assert result["type"] == "brand"  # Default
        assert result["status"] == "active"  # Default


class TestIdentificationResult:
    """Tests for IdentificationResult dataclass."""

    def test_found_result(self):
        """Test a successful identification result."""
        product = ProductInfo(id="meal-kit", name="Meal Kit")
        result = IdentificationResult(
            found=True,
            product_id="meal-kit",
            product_info=product,
            source=IdentificationSource.EXPLICIT,
            confidence=1.0,
            message="Product explicitly specified",
        )

        assert result.found is True
        assert result.product_id == "meal-kit"
        assert result.source == IdentificationSource.EXPLICIT
        assert result.confidence == 1.0

    def test_not_found_result(self):
        """Test a failed identification result."""
        products = [
            ProductInfo(id="meal-kit", name="Meal Kit"),
            ProductInfo(id="wellness-brand", name="Wellness Brand"),
        ]
        result = IdentificationResult(
            found=False,
            source=IdentificationSource.USER_SELECTION,
            message="Please select a product",
            available_products=products,
        )

        assert result.found is False
        assert result.source == IdentificationSource.USER_SELECTION
        assert len(result.available_products) == 2

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        product = ProductInfo(id="growth-platform", name="Growth Platform")
        result = IdentificationResult(
            found=True,
            product_id="growth-platform",
            product_info=product,
            source=IdentificationSource.CHANNEL_INFERENCE,
            confidence=0.85,
        )

        d = result.to_dict()

        assert d["found"] is True
        assert d["product_id"] == "growth-platform"
        assert d["source"] == "channel_inference"
        assert d["confidence"] == 0.85


# Helper function to create a configured ProductIdentifier for tests
def create_test_identifier(mock_config):
    """Create a ProductIdentifier with mocked config for testing."""
    # Import config_loader and patch it before importing ProductIdentifier
    import config_loader as real_config_loader

    # Create mock config object
    mock_cfg = MagicMock()
    mock_cfg.user_path = "/tmp/test"
    mock_cfg.raw_config = mock_config

    # Patch get_config
    original_get_config = real_config_loader.get_config

    def patched_get_config():
        return mock_cfg

    real_config_loader.get_config = patched_get_config

    try:
        # Now import and create ProductIdentifier
        from context_engine.product_identifier import ProductIdentifier

        identifier = ProductIdentifier(user_path=Path("/tmp/test"))
        return identifier
    finally:
        # Restore original
        real_config_loader.get_config = original_get_config


class TestProductIdentifierChannelInference:
    """Tests for channel name to product inference."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return {
            "products": {
                "organization": {"id": "growth-division"},
                "items": [
                    {
                        "id": "meal-kit",
                        "name": "Meal Kit",
                        "jira_project": "MK",
                        "status": "active",
                    },
                    {
                        "id": "wellness-brand",
                        "name": "Wellness Brand",
                        "jira_project": "WB",
                        "status": "active",
                    },
                    {
                        "id": "growth-platform",
                        "name": "Growth Platform",
                        "jira_project": "PROJ1",
                        "status": "active",
                    },
                    {
                        "id": "product-innovation",
                        "name": "Product Innovation",
                        "jira_project": "PROJ2",
                        "status": "active",
                    },
                ],
            },
            "master_sheet": {
                "enabled": True,
                "product_mapping": {
                    "MK": "meal-kit",
                    "WB": "wellness-brand",
                    "FF": "growth-platform",
                    "PROJ2": "product-innovation",
                },
            },
        }

    @pytest.fixture
    def identifier(self, mock_config):
        """Create a ProductIdentifier with mocked config."""
        return create_test_identifier(mock_config)

    def test_infer_Meal_Kit_from_channel(self, identifier):
        """Test inferring Meal Kit from channel name."""
        result = identifier.infer_product_from_channel("#meal-kit")
        assert result is not None
        assert result.id == "meal-kit"

    def test_infer_Meal_Kit_from_prefixed_channel(self, identifier):
        """Test inferring Meal Kit from prefixed channel."""
        result = identifier.infer_product_from_channel("#meal-kit-planning")
        assert result is not None
        assert result.id == "meal-kit"

    def test_infer_from_abbreviation_channel(self, identifier):
        """Test inferring from abbreviation in channel name."""
        result = identifier.infer_product_from_channel("#goc-standup")
        assert result is not None
        assert result.id == "meal-kit"

    def test_infer_Wellness_Brand(self, identifier):
        """Test inferring Wellness Brand."""
        result = identifier.infer_product_from_channel("#wellness-brand")
        assert result is not None
        assert result.id == "wellness-brand"

    def test_infer_tpt_abbreviation(self, identifier):
        """Test inferring from WB abbreviation."""
        result = identifier.infer_product_from_channel("#tpt-engineering")
        assert result is not None
        assert result.id == "wellness-brand"

    def test_no_inference_for_general_channel(self, identifier):
        """Test that general channels return None."""
        result = identifier.infer_product_from_channel("#general")
        assert result is None

    def test_handles_channel_without_hash(self, identifier):
        """Test that channels without # are handled."""
        result = identifier.infer_product_from_channel("meal-kit")
        assert result is not None
        assert result.id == "meal-kit"


class TestProductIdentifierExplicitProduct:
    """Tests for explicit product specification."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return {
            "products": {
                "organization": {"id": "growth-division"},
                "items": [
                    {
                        "id": "meal-kit",
                        "name": "Meal Kit",
                        "jira_project": "MK",
                        "status": "active",
                    },
                    {
                        "id": "wellness-brand",
                        "name": "Wellness Brand",
                        "jira_project": "WB",
                        "status": "active",
                    },
                ],
            },
            "master_sheet": {
                "enabled": True,
                "product_mapping": {
                    "MK": "meal-kit",
                    "WB": "wellness-brand",
                },
            },
        }

    @pytest.fixture
    def identifier(self, mock_config):
        """Create a ProductIdentifier with mocked config."""
        return create_test_identifier(mock_config)

    def test_explicit_product_by_id(self, identifier):
        """Test explicit product by ID."""
        result = identifier.identify_product(
            explicit_product="meal-kit",
            check_master_sheet=False,
            check_daily_context=False,
        )

        assert result.found is True
        assert result.product_id == "meal-kit"
        assert result.source == IdentificationSource.EXPLICIT
        assert result.confidence == 1.0

    def test_explicit_product_by_abbreviation(self, identifier):
        """Test explicit product by abbreviation."""
        result = identifier.identify_product(
            explicit_product="MK",
            check_master_sheet=False,
            check_daily_context=False,
        )

        assert result.found is True
        assert result.product_id == "meal-kit"
        assert result.source == IdentificationSource.EXPLICIT

    def test_explicit_product_by_partial_name(self, identifier):
        """Test explicit product by partial name match."""
        result = identifier.identify_product(
            explicit_product="Good",
            check_master_sheet=False,
            check_daily_context=False,
        )

        assert result.found is True
        assert result.product_id == "meal-kit"
        assert result.confidence == 0.9

    def test_explicit_product_not_found(self, identifier):
        """Test explicit product that doesn't exist."""
        result = identifier.identify_product(
            explicit_product="nonexistent",
            check_master_sheet=False,
            check_daily_context=False,
        )

        assert result.found is False
        assert result.source == IdentificationSource.NOT_FOUND
        assert len(result.available_products) > 0


class TestProductIdentifierPriorityOrder:
    """Tests for the priority order of identification."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return {
            "products": {
                "organization": {"id": "growth-division"},
                "items": [
                    {
                        "id": "meal-kit",
                        "name": "Meal Kit",
                        "jira_project": "MK",
                        "status": "active",
                    },
                    {
                        "id": "wellness-brand",
                        "name": "Wellness Brand",
                        "jira_project": "WB",
                        "status": "active",
                    },
                ],
            },
            "master_sheet": {
                "enabled": True,
                "product_mapping": {
                    "MK": "meal-kit",
                    "WB": "wellness-brand",
                },
            },
        }

    @pytest.fixture
    def identifier(self, mock_config):
        """Create a ProductIdentifier with mocked config."""
        return create_test_identifier(mock_config)

    def test_explicit_beats_channel(self, identifier):
        """Test that explicit product beats channel inference."""
        result = identifier.identify_product(
            explicit_product="wellness-brand",
            channel_name="#meal-kit",  # This should be ignored
            check_master_sheet=False,
            check_daily_context=False,
        )

        assert result.found is True
        assert result.product_id == "wellness-brand"
        assert result.source == IdentificationSource.EXPLICIT

    def test_channel_used_when_no_explicit(self, identifier):
        """Test that channel is used when no explicit product."""
        result = identifier.identify_product(
            explicit_product=None,
            channel_name="#meal-kit",
            check_master_sheet=False,
            check_daily_context=False,
        )

        assert result.found is True
        assert result.product_id == "meal-kit"
        assert result.source == IdentificationSource.CHANNEL_INFERENCE

    def test_user_selection_when_nothing_matches(self, identifier):
        """Test that user selection is returned when nothing matches."""
        result = identifier.identify_product(
            explicit_product=None,
            channel_name="#general",
            check_master_sheet=False,
            check_daily_context=False,
        )

        assert result.found is False
        assert result.source == IdentificationSource.USER_SELECTION
        assert len(result.available_products) == 2


class TestProductSelectionFormatting:
    """Tests for product selection prompt formatting."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return {
            "products": {
                "organization": {"id": "growth-division"},
                "items": [
                    {
                        "id": "meal-kit",
                        "name": "Meal Kit",
                        "jira_project": "MK",
                        "status": "active",
                    },
                    {
                        "id": "wellness-brand",
                        "name": "Wellness Brand",
                        "jira_project": "WB",
                        "status": "active",
                    },
                ],
            },
            "master_sheet": {
                "enabled": True,
                "product_mapping": {
                    "MK": "meal-kit",
                    "WB": "wellness-brand",
                },
            },
        }

    @pytest.fixture
    def identifier(self, mock_config):
        """Create a ProductIdentifier with mocked config."""
        return create_test_identifier(mock_config)

    def test_format_selection_not_found(self, identifier):
        """Test formatting when product not found."""
        result = identifier.identify_product(
            explicit_product=None,
            check_master_sheet=False,
            check_daily_context=False,
        )

        formatted = identifier.format_product_selection(result)

        assert "Product not specified" in formatted
        assert "Meal Kit" in formatted
        assert "Wellness Brand" in formatted
        assert "1." in formatted
        assert "2." in formatted

    def test_format_selection_when_found(self, identifier):
        """Test formatting when product is found."""
        result = identifier.identify_product(
            explicit_product="meal-kit",
            check_master_sheet=False,
            check_daily_context=False,
        )

        formatted = identifier.format_product_selection(result)

        assert "Product: Meal Kit" in formatted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
