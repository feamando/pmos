"""
Brain Entity Creator for Context Creation Engine

Creates and manages Brain entity files for features at user/brain/Entities/{Feature_Name}.md.
Uses the v2 schema format with proper frontmatter ($type, $id, $schema, $events, etc.).

Brain Entity Format:
    The entity file follows the standard Brain v2 schema used across PM-OS:
    - YAML frontmatter with $schema, $id, $type, $version, $created, $updated,
      $confidence, $source, $status, $relationships, $tags, $aliases, $events
    - Markdown body with Overview, Product, Context, Relationships, References sections

Usage:
    from tools.context_engine.brain_entity_creator import BrainEntityCreator

    creator = BrainEntityCreator()

    # Create entity for a feature
    entity_path = creator.create_feature_entity(
        title="OTP Checkout Recovery",
        slug="mk-feature-recovery",
        product_id="meal-kit",
        product_name="Meal Kit",
        organization_id="growth-division"
    )

    # Check if entity exists
    exists, path = creator.entity_exists("OTP Checkout Recovery")

    # Update an existing entity
    creator.update_entity_status(entity_path, "active")

See Also:
    - Brain unified_brain_writer.py for similar entity creation logic
    - PRD Section C.3: Brain Integration

Author: PM-OS Context Engine
"""

import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class BrainEntityResult:
    """Result of Brain entity creation or lookup."""

    success: bool
    entity_path: Path
    entity_name: str
    created: bool  # True if newly created, False if already existed
    message: str = ""


def generate_entity_name(title: str) -> str:
    """
    Generate Brain entity file name from feature title.

    Converts title to Title_Case_With_Underscores format.

    Args:
        title: Feature title (e.g., "OTP Checkout Recovery")

    Returns:
        Entity name suitable for file path (e.g., "Otp_Checkout_Recovery")

    Examples:
        >>> generate_entity_name("OTP Checkout Recovery")
        "Otp_Checkout_Recovery"
        >>> generate_entity_name("New Feature - v2")
        "New_Feature_V2"
    """
    # Remove special characters except spaces and hyphens
    cleaned = re.sub(r"[^\w\s-]", "", title)
    # Replace hyphens with spaces for uniform processing
    cleaned = cleaned.replace("-", " ")
    # Split into words and capitalize each
    words = cleaned.split()
    # Join with underscores, capitalizing first letter of each word
    return "_".join(word.capitalize() for word in words if word)


def generate_entity_slug(title: str) -> str:
    """
    Generate URL-safe slug from feature title for $id field.

    Args:
        title: Feature title

    Returns:
        Lowercase slug with hyphens (e.g., "otp-checkout-recovery")
    """
    # Remove special characters
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    # Replace spaces and underscores with hyphens
    slug = re.sub(r"[\s_]+", "-", slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r"-+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug


class BrainEntityCreator:
    """
    Creates and manages Brain entity files for features.

    Brain entities are created at user/brain/Entities/{Feature_Name}.md
    using the v2 schema format with proper YAML frontmatter.
    """

    def __init__(self, user_path: Optional[Path] = None):
        """
        Initialize the Brain entity creator.

        Args:
            user_path: Path to user/ directory. If None, auto-detected from config.
        """
        import config_loader

        self.config = config_loader.get_config()
        self.user_path = user_path or Path(self.config.user_path)
        self.entities_dir = self.user_path / "brain" / "Entities"
        self.products_dir = self.user_path / "brain" / "Products"

    def entity_exists(self, title: str) -> Tuple[bool, Optional[Path]]:
        """
        Check if a Brain entity already exists for the given title.

        Args:
            title: Feature title

        Returns:
            Tuple of (exists: bool, path: Optional[Path])
        """
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
        """
        Create a Brain entity file for a feature.

        If the entity already exists, returns without modification (unless force=True).

        Args:
            title: Feature title (e.g., "OTP Checkout Recovery")
            slug: Feature slug (e.g., "mk-feature-recovery")
            product_id: Product ID (e.g., "meal-kit")
            product_name: Human-readable product name (e.g., "Meal Kit")
            organization_id: Organization ID (e.g., "growth-division")
            description: Optional feature description
            source: Source of entity creation (default: "context_engine")
            confidence: Initial confidence score (default: 0.8)

        Returns:
            BrainEntityResult with creation details
        """
        entity_name = generate_entity_name(title)
        entity_path = self.entities_dir / f"{entity_name}.md"

        # Check if already exists
        if entity_path.exists():
            return BrainEntityResult(
                success=True,
                entity_path=entity_path,
                entity_name=entity_name,
                created=False,
                message=f"Entity already exists at {entity_path}",
            )

        # Ensure directory exists
        self.entities_dir.mkdir(parents=True, exist_ok=True)

        # Generate entity content
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

        # Write entity file
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
        """
        Generate the complete entity file content with v2 schema frontmatter.

        Args:
            title: Feature title
            slug: Feature slug
            entity_name: Generated entity name
            product_id: Product ID
            product_name: Human-readable product name
            organization_id: Organization ID (optional)
            description: Feature description (optional)
            source: Source of creation
            confidence: Confidence score

        Returns:
            Complete markdown content with YAML frontmatter
        """
        now = datetime.utcnow()
        date_str = now.strftime("%Y-%m-%d")
        iso_timestamp = now.isoformat() + "Z"
        entity_slug = generate_entity_slug(title)

        # Build the product relationship reference
        product_entity = f"Entities/Products/{product_name.replace(' ', '_')}"

        # Build description placeholder
        desc_text = description or "Feature managed by Context Creation Engine"

        # Build organization path if available
        org_path = f"{organization_id}/" if organization_id else ""

        # YAML frontmatter following v2 schema
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

        # Markdown body
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
        """
        Update the status field of an existing entity.

        Args:
            entity_path: Path to the entity file
            entity_name: Entity file name (without .md)
            new_status: New status value (e.g., "active", "complete", "archived")
            actor: Who is making the change

        Returns:
            True if update was successful
        """
        if not entity_path.exists():
            return False

        try:
            content = entity_path.read_text(encoding="utf-8")
            now = datetime.utcnow()
            iso_timestamp = now.isoformat() + "Z"

            # Update $status field
            content = re.sub(
                r"^\$status: \w+", f"$status: {new_status}", content, flags=re.MULTILINE
            )

            # Update $updated timestamp
            content = re.sub(
                r"^\$updated: '[^']*'",
                f"$updated: '{iso_timestamp}'",
                content,
                flags=re.MULTILINE,
            )

            # Update the Status line in body
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
        """
        Update the entity to link to a specific context file.

        Args:
            entity_path: Path to the entity file
            context_file_path: Relative path to the context file

        Returns:
            True if update was successful
        """
        if not entity_path.exists():
            return False

        try:
            content = entity_path.read_text(encoding="utf-8")

            # Update the context file link
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
        """
        Get the wiki-link reference for a feature entity.

        Args:
            title: Feature title

        Returns:
            Wiki-link format reference (e.g., "[[Entities/Otp_Checkout_Recovery]]")
        """
        entity_name = generate_entity_name(title)
        return f"[[Entities/{entity_name}]]"

    def get_entity_path(self, title: str) -> Path:
        """
        Get the expected path for a feature entity.

        Args:
            title: Feature title

        Returns:
            Path to where the entity file would be located
        """
        entity_name = generate_entity_name(title)
        return self.entities_dir / f"{entity_name}.md"
