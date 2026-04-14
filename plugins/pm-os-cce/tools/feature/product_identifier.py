"""
PM-OS CCE Product Identifier (v5.0)

Intelligent product detection following PRD Section C.6 priority order:
1. Explicit flag (--product)
2. Master Sheet lookup
3. Current daily context
4. Signal source (channel inference)
5. Ask user (present list from config)

All product names, abbreviations, and channel patterns are config-driven.
No hardcoded product values.

Usage:
    from pm_os_cce.tools.feature.product_identifier import ProductIdentifier, ProductInfo
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

logger = logging.getLogger(__name__)


class IdentificationSource(Enum):
    """Source of product identification."""

    EXPLICIT = "explicit"
    MASTER_SHEET = "master_sheet"
    DAILY_CONTEXT = "daily_context"
    CHANNEL_INFERENCE = "channel_inference"
    USER_SELECTION = "user_selection"
    NOT_FOUND = "not_found"


@dataclass
class ProductInfo:
    """Information about a product from config."""

    id: str
    name: str
    type: str = "brand"
    jira_project: Optional[str] = None
    squad: Optional[str] = None
    market: str = "US"
    status: str = "active"
    abbreviation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
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
    """Result of product identification."""

    found: bool
    product_id: Optional[str] = None
    product_info: Optional[ProductInfo] = None
    source: IdentificationSource = IdentificationSource.NOT_FOUND
    confidence: float = 0.0
    message: str = ""
    available_products: List[ProductInfo] = field(default_factory=list)
    recent_activity: Dict[str, datetime] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "found": self.found,
            "product_id": self.product_id,
            "product_info": self.product_info.to_dict() if self.product_info else None,
            "source": self.source.value,
            "confidence": self.confidence,
            "message": self.message,
            "available_products": [p.to_dict() for p in self.available_products],
        }


class ProductIdentifier:
    """Intelligent product identification for the Context Creation Engine.

    All product names, abbreviations, and channel patterns are loaded from config.
    No hardcoded product values.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """Initialize the product identifier.

        Args:
            user_path: Path to user/ directory. If None, auto-detected from config.
        """
        self._config = None
        self._user_path = user_path
        self._raw_config = {}

        if get_config is not None:
            try:
                self._config = get_config()
                self._user_path = user_path or Path(self._config.user_path)
                self._raw_config = self._config.config if hasattr(self._config, "config") else {}
            except Exception:
                pass

        self._products_cache: Optional[List[ProductInfo]] = None
        self._product_mapping: Optional[Dict[str, str]] = None
        self._channel_patterns: Dict[str, str] = {}

        self._load_product_mapping()

    def _load_product_mapping(self) -> None:
        """Load product abbreviation mapping and channel patterns from config."""
        master_sheet_config = self._raw_config.get("master_sheet", {})
        self._product_mapping = master_sheet_config.get("product_mapping", {})

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

        # Also add abbreviation patterns from product_mapping
        if self._product_mapping:
            for abbr, product_id in self._product_mapping.items():
                self._channel_patterns[abbr.lower()] = product_id

    def get_products_from_config(self, active_only: bool = True) -> List[ProductInfo]:
        """Get list of available products from config."""
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
        """Get product details by ID."""
        products = self.get_products_from_config(active_only=False)
        for product in products:
            if product.id == product_id:
                return product
        return None

    def get_product_by_abbreviation(self, abbreviation: str) -> Optional[ProductInfo]:
        """Get product by abbreviation (e.g., "PRD" -> product)."""
        abbr_upper = abbreviation.upper()

        if self._product_mapping and abbr_upper in self._product_mapping:
            product_id = self._product_mapping[abbr_upper]
            return self.get_product_by_id(product_id)

        products = self.get_products_from_config(active_only=False)
        for product in products:
            if product.jira_project and product.jira_project.upper() == abbr_upper:
                return product

        return None

    def infer_product_from_channel(self, channel_name: str) -> Optional[ProductInfo]:
        """Infer product from a Slack channel name using config-driven patterns."""
        if not channel_name:
            return None

        channel = channel_name.lower().strip()
        if channel.startswith("#"):
            channel = channel[1:]

        # Try exact match first
        if channel in self._channel_patterns:
            product_id = self._channel_patterns[channel]
            return self.get_product_by_id(product_id)

        # Try prefix match
        for pattern, product_id in self._channel_patterns.items():
            if channel.startswith(f"{pattern}-") or channel.startswith(f"{pattern}_"):
                return self.get_product_by_id(product_id)

        # Try finding product keywords anywhere in channel name
        for pattern, product_id in self._channel_patterns.items():
            if len(pattern) >= 3 and pattern in channel:
                return self.get_product_by_id(product_id)

        return None

    def get_recent_products_from_context(
        self, days: int = 1, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get products mentioned in recent daily context files."""
        if self._user_path is None:
            return []

        context_dir = self._user_path / "personal" / "context"
        if not context_dir.exists():
            logger.debug(f"Context directory not found: {context_dir}")
            return []

        products = self.get_products_from_config()
        product_mentions: Dict[str, Dict[str, Any]] = {}

        today = datetime.now().date()
        start_date = today - timedelta(days=days)

        for context_file in context_dir.glob("*-context.md"):
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

            try:
                content = context_file.read_text()
            except (IOError, UnicodeDecodeError):
                continue

            for product in products:
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

        results = sorted(
            product_mentions.values(),
            key=lambda x: (x["last_seen"], x["mention_count"]),
            reverse=True,
        )

        return results[:limit]

    def _lookup_in_master_sheet(self, topic_name: str) -> Optional[ProductInfo]:
        """Look up product for a topic in Master Sheet."""
        try:
            try:
                from pm_os_cce.tools.integration.master_sheet_reader import MasterSheetReader
            except ImportError:
                from integration.master_sheet_reader import MasterSheetReader

            reader = MasterSheetReader()
            topics = reader.get_topics()

            topic_lower = topic_name.lower().strip()
            for topic in topics:
                if topic.feature.lower().strip() == topic_lower:
                    product_abbr = topic.product.upper()
                    return self.get_product_by_abbreviation(product_abbr)

            # Try fuzzy matching if no exact match
            try:
                from pm_os_cce.tools.feature.alias_manager import combined_similarity
            except ImportError:
                from feature.alias_manager import combined_similarity

            best_match = None
            best_score = 0.0

            for topic in topics:
                score = combined_similarity(topic_name, topic.feature)
                if score > best_score and score > 0.8:
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
        """Identify the relevant product following priority order."""
        all_products = self.get_products_from_config()

        # Priority 1: Explicit flag
        if explicit_product:
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
        """Format a product selection prompt for user display."""
        if result.found:
            return f"Product: {result.product_info.name} ({result.product_id})"

        lines = ["Product not specified. Which product is this for?", ""]
        lines.append("From config:")

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
