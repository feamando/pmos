"""
Product Identifier - Intelligent Product Detection for Context Engine

Identifies the relevant product for a feature based on multiple signals
following a priority order specified in PRD Section C.6:

Priority Order:
1. Explicit flag: if user provides --product "Meal Kit"
2. Master Sheet lookup: If topic already exists, use its product
3. Current daily context: What product appeared in today's context?
4. Signal source: If insight from #meal-kit channel -> Meal Kit
5. Ask user: Present list from config.yaml products.items[]

Usage:
    from tools.context_engine import ProductIdentifier

    identifier = ProductIdentifier()

    # Get all available products
    products = identifier.get_products_from_config()

    # Identify product from various signals
    result = identifier.identify_product(
        explicit_product=None,
        topic_name="OTP Checkout Recovery",
        channel_name="#meal-kit"
    )

    if result.found:
        print(f"Product: {result.product_id}")
    else:
        print(f"Choose from: {result.available_products}")

Author: PM-OS Team
Version: 1.0.0
"""

import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logger = logging.getLogger(__name__)


class IdentificationSource(Enum):
    """Source of product identification."""

    EXPLICIT = "explicit"  # User provided --product flag
    MASTER_SHEET = "master_sheet"  # Found in Master Sheet topics
    DAILY_CONTEXT = "daily_context"  # Found in recent daily context
    CHANNEL_INFERENCE = "channel_inference"  # Inferred from Slack channel
    USER_SELECTION = "user_selection"  # User needs to select
    NOT_FOUND = "not_found"


@dataclass
class ProductInfo:
    """
    Information about a product from config.yaml.

    Attributes:
        id: Product identifier (e.g., "meal-kit")
        name: Display name (e.g., "Meal Kit")
        type: Type (brand, product, feature, project)
        jira_project: Jira project code (e.g., "MK")
        squad: Associated squad name
        market: Market (e.g., "US", "GLOBAL")
        status: Status (active, archived, paused)
        abbreviation: Short form used in Master Sheet (e.g., "MK")
    """

    id: str
    name: str
    type: str = "brand"
    jira_project: Optional[str] = None
    squad: Optional[str] = None
    market: str = "US"
    status: str = "active"
    abbreviation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "jira_project": self.jira_project,
            "squad": self.squad,
            "market": self.market,
            "status": self.status,
            "abbreviation": self.abbreviation,
        }


@dataclass
class IdentificationResult:
    """
    Result of product identification.

    Attributes:
        found: Whether a product was identified
        product_id: Identified product ID (if found)
        product_info: Full product information (if found)
        source: How the product was identified
        confidence: Confidence level (0.0 to 1.0)
        message: Human-readable explanation
        available_products: List of products for user selection (if not found)
        recent_activity: Recent activity info for products
    """

    found: bool
    product_id: Optional[str] = None
    product_info: Optional[ProductInfo] = None
    source: IdentificationSource = IdentificationSource.NOT_FOUND
    confidence: float = 0.0
    message: str = ""
    available_products: List[ProductInfo] = field(default_factory=list)
    recent_activity: Dict[str, datetime] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "found": self.found,
            "product_id": self.product_id,
            "product_info": self.product_info.to_dict() if self.product_info else None,
            "source": self.source.value,
            "confidence": self.confidence,
            "message": self.message,
            "available_products": [p.to_dict() for p in self.available_products],
        }


# Channel name patterns mapped to product IDs
# These patterns handle common Slack channel naming conventions
CHANNEL_PRODUCT_PATTERNS = {
    # Exact matches
    "meal-kit": "meal-kit",
    "goodchop": "meal-kit",
    "goc": "meal-kit",
    "wellness-brand": "wellness-brand",
    "wellness-brand": "wellness-brand",
    "tpt": "wellness-brand",
    "growth-platform": "growth-platform",
    "factorform": "growth-platform",
    "ff": "growth-platform",
    "factor": "growth-platform",
    "product-innovation": "product-innovation",
    "marketinnovation": "product-innovation",
    "mio": "product-innovation",
    # Common prefixes/suffixes in channel names
}


class ProductIdentifier:
    """
    Intelligent product identification for the Context Creation Engine.

    Identifies the relevant product for a feature based on multiple signals,
    following a priority order: explicit flag > Master Sheet > daily context >
    channel inference > user selection.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the product identifier.

        Args:
            user_path: Path to user/ directory. If None, auto-detected.
        """
        import config_loader

        self._config = config_loader.get_config()
        self._user_path = user_path or Path(self._config.user_path)
        self._raw_config = self._config.config

        # Cache for products
        self._products_cache: Optional[List[ProductInfo]] = None
        self._product_mapping: Optional[Dict[str, str]] = None
        self._channel_patterns: Dict[str, str] = {}

        # Load product mapping from config
        self._load_product_mapping()

    def _load_product_mapping(self) -> None:
        """Load product abbreviation mapping from config."""
        master_sheet_config = self._raw_config.get("master_sheet", {})
        self._product_mapping = master_sheet_config.get("product_mapping", {})

        # Build channel patterns from product mapping and product IDs
        products_config = self._raw_config.get("products", {})
        items = products_config.get("items", [])

        for product in items:
            product_id = product.get("id", "")
            product_name = product.get("name", "").lower()
            jira_project = product.get("jira_project", "")

            # Add ID-based patterns
            if product_id:
                self._channel_patterns[product_id.lower()] = product_id
                self._channel_patterns[product_id.lower().replace("-", "")] = product_id

            # Add name-based patterns
            if product_name:
                self._channel_patterns[product_name.replace(" ", "-")] = product_id
                self._channel_patterns[product_name.replace(" ", "")] = product_id

            # Add Jira project patterns
            if jira_project:
                self._channel_patterns[jira_project.lower()] = product_id

    def get_products_from_config(self, active_only: bool = True) -> List[ProductInfo]:
        """
        Get list of available products from config.yaml.

        Args:
            active_only: If True, only return active products

        Returns:
            List of ProductInfo objects
        """
        if self._products_cache is not None and active_only:
            return self._products_cache

        products_config = self._raw_config.get("products", {})
        items = products_config.get("items", [])

        products = []
        for item in items:
            if active_only and item.get("status", "active") != "active":
                continue

            product_id = item.get("id", "")
            jira_project = item.get("jira_project")

            # Find abbreviation from product_mapping
            abbreviation = None
            if self._product_mapping:
                for abbr, pid in self._product_mapping.items():
                    if pid == product_id:
                        abbreviation = abbr
                        break

            products.append(
                ProductInfo(
                    id=product_id,
                    name=item.get("name", product_id),
                    type=item.get("type", "brand"),
                    jira_project=jira_project,
                    squad=item.get("squad"),
                    market=item.get("market", "US"),
                    status=item.get("status", "active"),
                    abbreviation=abbreviation
                    or (jira_project.upper() if jira_project else None),
                )
            )

        if active_only:
            self._products_cache = products

        return products

    def get_product_by_id(self, product_id: str) -> Optional[ProductInfo]:
        """
        Get product details by ID.

        Args:
            product_id: Product identifier (e.g., "meal-kit")

        Returns:
            ProductInfo if found, None otherwise
        """
        products = self.get_products_from_config(active_only=False)
        for product in products:
            if product.id == product_id:
                return product
        return None

    def get_product_by_abbreviation(self, abbreviation: str) -> Optional[ProductInfo]:
        """
        Get product by abbreviation (e.g., "MK" -> Meal Kit).

        Args:
            abbreviation: Product abbreviation

        Returns:
            ProductInfo if found, None otherwise
        """
        abbr_upper = abbreviation.upper()

        # Check product mapping
        if self._product_mapping and abbr_upper in self._product_mapping:
            product_id = self._product_mapping[abbr_upper]
            return self.get_product_by_id(product_id)

        # Check Jira projects
        products = self.get_products_from_config(active_only=False)
        for product in products:
            if product.jira_project and product.jira_project.upper() == abbr_upper:
                return product

        return None

    def infer_product_from_channel(self, channel_name: str) -> Optional[ProductInfo]:
        """
        Infer product from a Slack channel name.

        Maps common channel naming patterns to products:
        - #meal-kit-* -> Meal Kit
        - #goc-* -> Meal Kit
        - #tpt-* -> Wellness Brand
        - #factor-* -> Growth Platform

        Args:
            channel_name: Slack channel name (with or without #)

        Returns:
            ProductInfo if inferred, None otherwise
        """
        if not channel_name:
            return None

        # Normalize channel name
        channel = channel_name.lower().strip()
        if channel.startswith("#"):
            channel = channel[1:]

        # Try exact match first
        if channel in self._channel_patterns:
            product_id = self._channel_patterns[channel]
            return self.get_product_by_id(product_id)

        # Try prefix match (e.g., "meal-kit-planning" -> "meal-kit")
        for pattern, product_id in self._channel_patterns.items():
            if channel.startswith(f"{pattern}-") or channel.startswith(f"{pattern}_"):
                return self.get_product_by_id(product_id)

        # Try finding product keywords anywhere in channel name
        for pattern, product_id in self._channel_patterns.items():
            # Only match if it's a substantial part of the channel name
            if len(pattern) >= 3 and pattern in channel:
                return self.get_product_by_id(product_id)

        return None

    def get_recent_products_from_context(
        self, days: int = 1, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get products mentioned in recent daily context files.

        Scans daily context files for product mentions and returns
        products sorted by most recent activity.

        Args:
            days: Number of days to look back
            limit: Maximum number of products to return

        Returns:
            List of dicts with product_id, product_info, last_seen, mention_count
        """
        context_dir = self._user_path / "personal" / "context"
        if not context_dir.exists():
            logger.debug(f"Context directory not found: {context_dir}")
            return []

        # Get products for matching
        products = self.get_products_from_config()
        product_mentions: Dict[str, Dict[str, Any]] = {}

        # Calculate date range
        today = datetime.now().date()
        start_date = today - timedelta(days=days)

        # Find context files in date range
        for context_file in context_dir.glob("*-context.md"):
            # Parse date from filename (YYYY-MM-DD-context.md or YYYY-MM-DD-NN-context.md)
            filename = context_file.name
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", filename)
            if not date_match:
                continue

            try:
                file_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
            except ValueError:
                continue

            if file_date < start_date:
                continue

            # Read and scan for product mentions
            try:
                content = context_file.read_text()
            except (IOError, UnicodeDecodeError):
                continue

            for product in products:
                # Check for product name, ID, abbreviation mentions
                patterns_to_check = [
                    product.name,
                    product.id.replace("-", " "),
                    product.id,
                ]
                if product.abbreviation:
                    patterns_to_check.append(product.abbreviation)
                if product.jira_project:
                    patterns_to_check.append(product.jira_project)

                mentioned = False
                for pattern in patterns_to_check:
                    # Case-insensitive search with word boundaries
                    if re.search(rf"\b{re.escape(pattern)}\b", content, re.IGNORECASE):
                        mentioned = True
                        break

                if mentioned:
                    if product.id not in product_mentions:
                        product_mentions[product.id] = {
                            "product_id": product.id,
                            "product_info": product,
                            "last_seen": file_date,
                            "mention_count": 1,
                        }
                    else:
                        product_mentions[product.id]["mention_count"] += 1
                        if file_date > product_mentions[product.id]["last_seen"]:
                            product_mentions[product.id]["last_seen"] = file_date

        # Sort by last_seen (most recent first), then by mention_count
        results = sorted(
            product_mentions.values(),
            key=lambda x: (x["last_seen"], x["mention_count"]),
            reverse=True,
        )

        return results[:limit]

    def _lookup_in_master_sheet(self, topic_name: str) -> Optional[ProductInfo]:
        """
        Look up product for a topic in Master Sheet.

        Args:
            topic_name: Feature/topic name to look up

        Returns:
            ProductInfo if found in Master Sheet, None otherwise
        """
        try:
            from .master_sheet_reader import MasterSheetReader

            reader = MasterSheetReader()
            topics = reader.get_topics()

            # Search for matching topic
            topic_lower = topic_name.lower().strip()
            for topic in topics:
                if topic.feature.lower().strip() == topic_lower:
                    # Found exact match - get product from abbreviation
                    product_abbr = topic.product.upper()
                    return self.get_product_by_abbreviation(product_abbr)

            # Try fuzzy matching if no exact match
            from .alias_manager import combined_similarity

            best_match = None
            best_score = 0.0

            for topic in topics:
                score = combined_similarity(topic_name, topic.feature)
                if score > best_score and score > 0.8:  # High confidence threshold
                    best_score = score
                    best_match = topic

            if best_match:
                product_abbr = best_match.product.upper()
                return self.get_product_by_abbreviation(product_abbr)

        except Exception as e:
            logger.debug(f"Master Sheet lookup failed: {e}")

        return None

    def identify_product(
        self,
        explicit_product: Optional[str] = None,
        topic_name: Optional[str] = None,
        channel_name: Optional[str] = None,
        check_master_sheet: bool = True,
        check_daily_context: bool = True,
    ) -> IdentificationResult:
        """
        Identify the relevant product following priority order.

        Priority:
        1. Explicit flag (--product)
        2. Master Sheet lookup (if topic exists)
        3. Daily context (recent mentions)
        4. Channel inference (Slack channel name)
        5. Return list for user selection

        Args:
            explicit_product: Explicitly specified product ID or name
            topic_name: Feature/topic name for Master Sheet lookup
            channel_name: Slack channel name for inference
            check_master_sheet: Whether to check Master Sheet
            check_daily_context: Whether to check daily context

        Returns:
            IdentificationResult with product info or selection options
        """
        all_products = self.get_products_from_config()

        # Priority 1: Explicit flag
        if explicit_product:
            # Try as product ID
            product = self.get_product_by_id(explicit_product)
            if product:
                return IdentificationResult(
                    found=True,
                    product_id=product.id,
                    product_info=product,
                    source=IdentificationSource.EXPLICIT,
                    confidence=1.0,
                    message=f"Product explicitly specified: {product.name}",
                )

            # Try as abbreviation
            product = self.get_product_by_abbreviation(explicit_product)
            if product:
                return IdentificationResult(
                    found=True,
                    product_id=product.id,
                    product_info=product,
                    source=IdentificationSource.EXPLICIT,
                    confidence=1.0,
                    message=f"Product explicitly specified: {product.name}",
                )

            # Try fuzzy matching against product names
            explicit_lower = explicit_product.lower().strip()
            for product in all_products:
                if explicit_lower in product.name.lower():
                    return IdentificationResult(
                        found=True,
                        product_id=product.id,
                        product_info=product,
                        source=IdentificationSource.EXPLICIT,
                        confidence=0.9,
                        message=f"Product matched by name: {product.name}",
                    )

            # Explicit product not found
            return IdentificationResult(
                found=False,
                source=IdentificationSource.NOT_FOUND,
                confidence=0.0,
                message=f"Specified product '{explicit_product}' not found in config",
                available_products=all_products,
            )

        # Priority 2: Master Sheet lookup
        if check_master_sheet and topic_name:
            product = self._lookup_in_master_sheet(topic_name)
            if product:
                return IdentificationResult(
                    found=True,
                    product_id=product.id,
                    product_info=product,
                    source=IdentificationSource.MASTER_SHEET,
                    confidence=0.95,
                    message=f"Product found in Master Sheet: {product.name}",
                )

        # Priority 3: Daily context
        if check_daily_context:
            recent_products = self.get_recent_products_from_context(days=1)
            if recent_products:
                # If only one product mentioned today, high confidence
                if len(recent_products) == 1:
                    product_info = recent_products[0]["product_info"]
                    return IdentificationResult(
                        found=True,
                        product_id=product_info.id,
                        product_info=product_info,
                        source=IdentificationSource.DAILY_CONTEXT,
                        confidence=0.8,
                        message=f"Product from today's context: {product_info.name}",
                        recent_activity={
                            p["product_id"]: p["last_seen"] for p in recent_products
                        },
                    )

        # Priority 4: Channel inference
        if channel_name:
            product = self.infer_product_from_channel(channel_name)
            if product:
                return IdentificationResult(
                    found=True,
                    product_id=product.id,
                    product_info=product,
                    source=IdentificationSource.CHANNEL_INFERENCE,
                    confidence=0.85,
                    message=f"Product inferred from channel '{channel_name}': {product.name}",
                )

        # Priority 5: User selection needed
        # Enhance available_products with recent activity info
        recent_products = self.get_recent_products_from_context(days=7)
        recent_activity = {p["product_id"]: p["last_seen"] for p in recent_products}

        return IdentificationResult(
            found=False,
            source=IdentificationSource.USER_SELECTION,
            confidence=0.0,
            message="Product could not be determined. Please select from available products.",
            available_products=all_products,
            recent_activity=recent_activity,
        )

    def format_product_selection(self, result: IdentificationResult) -> str:
        """
        Format a product selection prompt for user display.

        Args:
            result: IdentificationResult with available products

        Returns:
            Formatted string for display
        """
        if result.found:
            return f"Product: {result.product_info.name} ({result.product_id})"

        lines = ["Product not specified. Which product is this for?", ""]
        lines.append("From config.yaml:")

        for i, product in enumerate(result.available_products, 1):
            activity_str = ""
            if product.id in result.recent_activity:
                last_seen = result.recent_activity[product.id]
                if isinstance(last_seen, datetime):
                    last_seen = last_seen.date()
                today = datetime.now().date()
                days_ago = (today - last_seen).days
                if days_ago == 0:
                    activity_str = " - recent activity: today"
                elif days_ago == 1:
                    activity_str = " - recent activity: yesterday"
                else:
                    activity_str = f" - recent activity: {days_ago} days ago"

            abbr = f"({product.abbreviation})" if product.abbreviation else ""
            lines.append(f"  {i}. {product.name} {abbr}{activity_str}")

        return "\n".join(lines)
