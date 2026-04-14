"""
PM-OS CCE Brain Entity Creator (v5.0)

Creates and manages Brain entity files for features at
user/brain/Entities/{Feature_Name}.md using v2 schema format.
Brain plugin is OPTIONAL - all operations guard with HAS_BRAIN check.

Usage:
    from pm_os_cce.tools.feature.brain_entity_creator import BrainEntityCreator, BrainEntityResult
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

# Optional Brain plugin integration
HAS_BRAIN = False
try:
    from pm_os_brain.tools.core.brain_writer import BrainWriter
    HAS_BRAIN = True
except ImportError:
    try:
        from brain.brain_writer import BrainWriter
        HAS_BRAIN = True
    except ImportError:
        BrainWriter = None

logger = logging.getLogger(__name__)


@dataclass
class BrainEntityResult:
    """Result of Brain entity creation or lookup."""

    success: bool
    entity_path: Path
    entity_name: str
    created: bool
    message: str = ""


def generate_entity_name(title: str) -> str:
    """Generate Brain entity file name from feature title.

    Converts title to Title_Case_With_Underscores format.

    Args:
        title: Feature title (e.g., "OTP Checkout Recovery")

    Returns:
        Entity name suitable for file path (e.g., "Otp_Checkout_Recovery")
    """
    cleaned = re.sub(r"[^\w\s-]", "", title)
    cleaned = cleaned.replace("-", " ")
    words = cleaned.split()
    return "_".join(word.capitalize() for word in words if word)


def generate_entity_slug(title: str) -> str:
    """Generate URL-safe slug from feature title for $id field."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug


class BrainEntityCreator:
    """Creates and manages Brain entity files for features.

    Brain entities are created at user/brain/Entities/{Feature_Name}.md
    using the v2 schema format with proper YAML frontmatter.
    All operations gracefully degrade if Brain plugin is not available.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """Initialize the Brain entity creator.

        Args:
            user_path: Path to user/ directory. If None, auto-detected from config.
        """
        self.user_path = user_path
        self.entities_dir = None
        self.products_dir = None

        if get_config is not None:
            try:
                config = get_config()
                self.user_path = user_path or Path(config.user_path)
                self.entities_dir = self.user_path / "brain" / "Entities"
                self.products_dir = self.user_path / "brain" / "Products"
            except Exception:
                pass

        if self.user_path and self.entities_dir is None:
            self.entities_dir = self.user_path / "brain" / "Entities"
            self.products_dir = self.user_path / "brain" / "Products"

    def entity_exists(self, title: str) -> Tuple[bool, Optional[Path]]:
        """Check if a Brain entity already exists for the given title."""
        if self.entities_dir is None:
            return False, None

        entity_name = generate_entity_name(title)
        entity_path = self.entities_dir / f"{entity_name}.md"
        return entity_path.exists(), entity_path if entity_path.exists() else None

    def create_feature_entity(
        self,
        title: str,
        slug: str,
        product_id: str,
        product_name: Optional[str] = None,
        organization_id: Optional[str] = None,
        description: Optional[str] = None,
        source: str = "context_engine",
        confidence: float = 0.8,
    ) -> BrainEntityResult:
        """Create a Brain entity file for a feature.

        If Brain plugin is not available or entities_dir is not configured,
        returns a non-blocking result.
        """
        if self.entities_dir is None:
            entity_name = generate_entity_name(title)
            return BrainEntityResult(
                success=False,
                entity_path=Path(f"brain/Entities/{entity_name}.md"),
                entity_name=entity_name,
                created=False,
                message="Brain entities directory not configured",
            )

        entity_name = generate_entity_name(title)
        entity_path = self.entities_dir / f"{entity_name}.md"

        if entity_path.exists():
            return BrainEntityResult(
                success=True,
                entity_path=entity_path,
                entity_name=entity_name,
                created=False,
                message=f"Entity already exists at {entity_path}",
            )

        self.entities_dir.mkdir(parents=True, exist_ok=True)

        content = self._generate_entity_content(
            title=title,
            slug=slug,
            entity_name=entity_name,
            product_id=product_id,
            product_name=product_name or product_id,
            organization_id=organization_id,
            description=description,
            source=source,
            confidence=confidence,
        )

        try:
            entity_path.write_text(content, encoding="utf-8")
            return BrainEntityResult(
                success=True,
                entity_path=entity_path,
                entity_name=entity_name,
                created=True,
                message=f"Entity created at {entity_path}",
            )
        except (PermissionError, OSError) as e:
            return BrainEntityResult(
                success=False,
                entity_path=entity_path,
                entity_name=entity_name,
                created=False,
                message=f"Failed to create entity: {e}",
            )

    def _generate_entity_content(
        self,
        title: str,
        slug: str,
        entity_name: str,
        product_id: str,
        product_name: str,
        organization_id: Optional[str],
        description: Optional[str],
        source: str,
        confidence: float,
    ) -> str:
        """Generate the complete entity file content with v2 schema frontmatter."""
        now = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        iso_timestamp = now.isoformat() + "Z"
        entity_slug = generate_entity_slug(title)

        product_entity = f"Entities/Products/{product_name.replace(' ', '_')}"
        desc_text = description or "Feature managed by Context Creation Engine"
        org_path = f"{organization_id}/" if organization_id else ""

        frontmatter = f"""---
$schema: brain://entity/feature/v1
$id: entity/feature/{entity_slug}
$type: feature
$version: 1
$created: '{iso_timestamp}'
$updated: '{iso_timestamp}'
$confidence: {confidence}
$source: {source}
$status: active
$relationships:
- type: belongs_to
  target: entity/product/{product_id}
  since: '{date_str}'
  until: null
  role: feature
  metadata: null
$tags:
- feature
- {product_id}
$aliases:
- {title.lower()}
$events:
- event_id: evt-{now.strftime('%Y%m%d')}-001
  timestamp: '{iso_timestamp}'
  type: entity_create
  actor: system/context_engine
  changes:
  - field: $schema
    operation: set
    value: brain://entity/feature/v1
  message: Created by Context Creation Engine
name: {title}
description: "{desc_text}"
---"""

        body = f"""

# {title}

## Overview
{desc_text}

## Product
- **Product**: {product_name}
- **Product ID**: {product_id}

## Context
- **Context File**: [[{slug}-context.md]]
- **Status**: To Do

## Relationships
- [[{product_entity}]]

## References
- Feature folder: user/products/{org_path}{product_id}/{slug}/
"""

        return frontmatter + body

    def update_entity_status(
        self, entity_path: Path, new_status: str, actor: str = "system/context_engine"
    ) -> bool:
        """Update the status field of an existing entity."""
        if not entity_path.exists():
            return False

        try:
            content = entity_path.read_text(encoding="utf-8")
            now = datetime.utcnow()
            iso_timestamp = now.isoformat() + "Z"

            content = re.sub(
                r"^\$status: \w+", f"$status: {new_status}", content, flags=re.MULTILINE
            )

            content = re.sub(
                r"^\$updated: '[^']*'",
                f"$updated: '{iso_timestamp}'",
                content,
                flags=re.MULTILINE,
            )

            content = re.sub(
                r"^- \*\*Status\*\*: .+$",
                f'- **Status**: {new_status.replace("_", " ").title()}',
                content,
                flags=re.MULTILINE,
            )

            entity_path.write_text(content, encoding="utf-8")
            return True
        except (PermissionError, OSError):
            return False

    def link_context_file(self, entity_path: Path, context_file_path: str) -> bool:
        """Update the entity to link to a specific context file."""
        if not entity_path.exists():
            return False

        try:
            content = entity_path.read_text(encoding="utf-8")

            content = re.sub(
                r"^\- \*\*Context File\*\*: .+$",
                f"- **Context File**: [[{context_file_path}]]",
                content,
                flags=re.MULTILINE,
            )

            entity_path.write_text(content, encoding="utf-8")
            return True
        except (PermissionError, OSError):
            return False

    def get_entity_reference(self, title: str) -> str:
        """Get the wiki-link reference for a feature entity."""
        entity_name = generate_entity_name(title)
        return f"[[Entities/{entity_name}]]"

    def get_entity_path(self, title: str) -> Path:
        """Get the expected path for a feature entity."""
        entity_name = generate_entity_name(title)
        if self.entities_dir:
            return self.entities_dir / f"{entity_name}.md"
        return Path(f"brain/Entities/{entity_name}.md")
