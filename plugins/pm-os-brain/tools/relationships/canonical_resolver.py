#!/usr/bin/env python3
"""
PM-OS Brain Canonical Resolver (v5.0)

Resolves any entity reference format to canonical $id format.

Canonical format: entity/{type}/{slug}
Examples:
  - entity/person/jane-smith
  - entity/project/factor-form
  - entity/team/new-ventures

Usage:
    from pm_os_brain.tools.relationships.canonical_resolver import CanonicalResolver
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

logger = logging.getLogger(__name__)

# Cache file name
RESOLVER_CACHE_FILE = "resolver_cache.json"
CACHE_MAX_AGE_HOURS = 24  # Rebuild cache after 24 hours


class CanonicalResolver:
    """
    Resolves any entity reference to canonical $id format.

    Supports resolution from:
    - Slug: onboarding-flow
    - Path: Projects/Onboarding_Flow.md
    - $id: entity/project/onboarding-flow
    - Alias: Onboarding Flow, OF
    """

    # Type inference from directory structure
    TYPE_FROM_DIR = {
        "people": "person",
        "persons": "person",
        "person": "person",
        "teams": "team",
        "team": "team",
        "squads": "squad",
        "squad": "squad",
        "domains": "domain",
        "domain": "domain",
        "systems": "system",
        "system": "system",
        "brands": "brand",
        "brand": "brand",
        "experiments": "experiment",
        "experiment": "experiment",
        "projects": "project",
        "project": "project",
        "entities": "entity",
        "reasoning": "reasoning",
    }

    def __init__(self, brain_path: Path):
        """
        Initialize the resolver.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = (
            Path(brain_path) if not isinstance(brain_path, Path) else brain_path
        )
        self._index: Dict[str, str] = {}  # any_ref -> canonical_id
        self._reverse_index: Dict[str, Set[str]] = {}  # canonical_id -> all_refs
        self._entity_paths: Dict[str, Path] = {}  # canonical_id -> file_path
        self._built = False
        self._cache_file = self.brain_path / RESOLVER_CACHE_FILE

    def _load_cache(self) -> bool:
        """Load index from cache file if valid."""
        if not self._cache_file.exists():
            return False

        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check cache age
            built_at = datetime.fromisoformat(data.get("built_at", "2000-01-01"))
            age_hours = (datetime.now() - built_at).total_seconds() / 3600
            if age_hours > CACHE_MAX_AGE_HOURS:
                return False

            # Load data
            self._index = data.get("index", {})
            self._reverse_index = {
                k: set(v) for k, v in data.get("reverse_index", {}).items()
            }
            self._entity_paths = {
                k: Path(v) for k, v in data.get("entity_paths", {}).items()
            }
            self._built = True

            return True

        except Exception:
            return False

    def _save_cache(self):
        """Save index to cache file."""
        try:
            data = {
                "built_at": datetime.now().isoformat(),
                "brain_path": str(self.brain_path),
                "index": self._index,
                "reverse_index": {k: list(v) for k, v in self._reverse_index.items()},
                "entity_paths": {k: str(v) for k, v in self._entity_paths.items()},
            }

            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

        except Exception:
            pass  # Cache save failure is not critical

    def build_index(self, force: bool = False) -> int:
        """
        Build the comprehensive reference index.

        Args:
            force: Rebuild even if already built

        Returns:
            Number of entities indexed
        """
        if self._built and not force:
            return len(self._entity_paths)

        # Try to load from cache first (unless force rebuild)
        if not force and self._load_cache():
            return len(self._entity_paths)

        self._index.clear()
        self._reverse_index.clear()
        self._entity_paths.clear()

        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
            and ".events" not in str(f)
        ]

        for entity_path in entity_files:
            self._index_entity(entity_path)

        self._built = True

        # Save to cache for next time
        self._save_cache()

        return len(self._entity_paths)

    def _index_entity(self, entity_path: Path):
        """Index a single entity with all its reference formats."""
        try:
            content = entity_path.read_text(encoding="utf-8")
            frontmatter = self._parse_frontmatter(content)
        except Exception:
            frontmatter = {}

        # Determine canonical $id
        canonical_id = frontmatter.get("$id")

        if not canonical_id:
            # Infer from path
            canonical_id = self._infer_canonical_id(entity_path)

        if not canonical_id:
            return

        # Store entity path
        self._entity_paths[canonical_id] = entity_path

        # Initialize reverse index
        if canonical_id not in self._reverse_index:
            self._reverse_index[canonical_id] = set()

        # Index all reference formats
        refs_to_index = self._get_all_refs(entity_path, frontmatter, canonical_id)

        for ref in refs_to_index:
            ref_lower = ref.lower()
            # Store lowercase for case-insensitive lookup
            self._index[ref_lower] = canonical_id
            self._reverse_index[canonical_id].add(ref)

    def _infer_canonical_id(self, entity_path: Path) -> Optional[str]:
        """Infer canonical $id from file path."""
        relative = entity_path.relative_to(self.brain_path)
        parts = relative.parts

        # Determine type from directory
        entity_type = "entity"
        for part in parts:
            part_lower = part.lower()
            if part_lower in self.TYPE_FROM_DIR:
                entity_type = self.TYPE_FROM_DIR[part_lower]
                break

        # Generate slug from filename
        slug = entity_path.stem.lower()
        slug = re.sub(r"[_\s]+", "-", slug)
        slug = re.sub(r"[^a-z0-9-]", "", slug)

        return f"entity/{entity_type}/{slug}"

    def _get_all_refs(
        self,
        entity_path: Path,
        frontmatter: Dict[str, Any],
        canonical_id: str,
    ) -> List[str]:
        """Get all possible reference formats for an entity."""
        refs = [canonical_id]

        # Extract slug from canonical id
        parts = canonical_id.split("/")
        if len(parts) >= 3:
            slug = parts[-1]
            refs.append(slug)

        # Add path-based references
        relative = str(entity_path.relative_to(self.brain_path))
        refs.append(relative)
        refs.append(relative.replace(".md", ""))

        # Add filename variations
        stem = entity_path.stem
        refs.append(stem)
        refs.append(stem.lower())
        refs.append(stem.replace("_", "-"))
        refs.append(stem.replace("_", " "))

        # Add aliases from frontmatter
        aliases = frontmatter.get("$aliases", []) or []
        if isinstance(aliases, list):
            refs.extend(aliases)

        # Add name field if present
        for name_field in ["name", "title", "$name", "$title"]:
            if name_field in frontmatter:
                refs.append(str(frontmatter[name_field]))

        # Normalize and deduplicate
        normalized_refs = []
        seen = set()
        for ref in refs:
            if ref and isinstance(ref, str):
                ref_lower = ref.lower().strip()
                if ref_lower and ref_lower not in seen:
                    normalized_refs.append(ref)
                    seen.add(ref_lower)

        return normalized_refs

    def resolve(self, reference: str) -> Optional[str]:
        """
        Resolve any reference to canonical $id.

        Args:
            reference: Any reference format (slug, path, alias, etc.)

        Returns:
            Canonical $id or None if not found
        """
        if not self._built:
            self.build_index()

        if not reference:
            return None

        # Normalize reference
        ref_lower = reference.lower().strip()

        # Direct lookup
        if ref_lower in self._index:
            return self._index[ref_lower]

        # Try variations
        variations = [
            ref_lower,
            ref_lower.replace("_", "-"),
            ref_lower.replace("-", "_"),
            ref_lower.replace(" ", "-"),
            ref_lower.replace(" ", "_"),
            re.sub(r"[^a-z0-9-]", "", ref_lower),
        ]

        # Handle path references
        if "/" in reference:
            # Try without extension
            without_ext = reference.rsplit(".", 1)[0]
            variations.append(without_ext.lower())
            # Try just the filename
            filename = reference.split("/")[-1]
            variations.append(filename.lower())
            variations.append(filename.rsplit(".", 1)[0].lower())

        for var in variations:
            if var in self._index:
                return self._index[var]

        return None

    def resolve_or_flag(self, reference: str) -> Tuple[Optional[str], bool]:
        """
        Resolve reference, flagging if orphan.

        Args:
            reference: Any reference format

        Returns:
            Tuple of (canonical_id or None, is_orphan)
        """
        canonical = self.resolve(reference)
        is_orphan = canonical is None
        return (canonical, is_orphan)

    def get_all_references(self, canonical_id: str) -> List[str]:
        """
        Get all known references for an entity.

        Args:
            canonical_id: The canonical $id

        Returns:
            List of all reference formats
        """
        if not self._built:
            self.build_index()

        return list(self._reverse_index.get(canonical_id, set()))

    def get_entity_path(self, canonical_id: str) -> Optional[Path]:
        """
        Get file path for a canonical ID.

        Args:
            canonical_id: The canonical $id

        Returns:
            Path to entity file or None
        """
        if not self._built:
            self.build_index()

        return self._entity_paths.get(canonical_id)

    def normalize_target(self, target: str) -> Optional[str]:
        """
        Normalize a relationship target to canonical format.

        Args:
            target: Original target reference

        Returns:
            Canonical $id or None if unresolvable
        """
        return self.resolve(target)

    def find_similar(
        self, reference: str, max_results: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Find similar entity references (fuzzy matching).

        Args:
            reference: Reference to match
            max_results: Maximum results to return

        Returns:
            List of (canonical_id, similarity_score) tuples
        """
        if not self._built:
            self.build_index()

        ref_lower = reference.lower().strip()
        results = []

        for indexed_ref, canonical_id in self._index.items():
            score = self._similarity_score(ref_lower, indexed_ref)
            if score > 0.5:
                results.append((canonical_id, score))

        # Deduplicate by canonical_id, keep highest score
        best_scores: Dict[str, float] = {}
        for canonical_id, score in results:
            if canonical_id not in best_scores or score > best_scores[canonical_id]:
                best_scores[canonical_id] = score

        sorted_results = sorted(best_scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_results[:max_results]

    def _similarity_score(self, s1: str, s2: str) -> float:
        """Calculate simple similarity score between two strings."""
        if s1 == s2:
            return 1.0

        # Containment check
        if s1 in s2 or s2 in s1:
            return 0.8

        # Common prefix
        common_len = 0
        for c1, c2 in zip(s1, s2):
            if c1 == c2:
                common_len += 1
            else:
                break

        if common_len > 3:
            return 0.6 + (common_len / max(len(s1), len(s2))) * 0.3

        # Word overlap
        words1 = set(s1.split("-"))
        words2 = set(s2.split("-"))
        if words1 and words2:
            overlap = len(words1 & words2) / max(len(words1), len(words2))
            if overlap > 0:
                return 0.5 + overlap * 0.3

        return 0.0

    def get_stats(self) -> Dict[str, int]:
        """Get resolver statistics."""
        if not self._built:
            self.build_index()

        return {
            "total_entities": len(self._entity_paths),
            "total_references": len(self._index),
            "avg_refs_per_entity": (
                len(self._index) // len(self._entity_paths) if self._entity_paths else 0
            ),
        }

    def parse_entity_name(self, name: str, entity_type: str) -> List[str]:
        """
        Generate alias candidates from an entity name, type-aware.

        Args:
            name: Entity display name (e.g., "Jane Smith", "Onboarding Flow")
            entity_type: Entity type (person, project, system, etc.)

        Returns:
            List of alias strings
        """
        if not name:
            return []

        aliases = []
        # Normalize: remove underscores, clean whitespace
        clean = name.replace("_", " ").strip()
        words = clean.split()

        if not words:
            return []

        # Lowercase slug
        slug = re.sub(r"[^a-z0-9\s-]", "", clean.lower()).strip()
        slug_dash = re.sub(r"\s+", "-", slug)
        aliases.append(slug_dash)

        if entity_type == "person":
            if len(words) >= 2:
                first = words[0].lower()
                last = words[-1].lower()
                # first-last
                aliases.append(f"{first}-{last}")
                # first initial + last
                aliases.append(f"{first[0]}-{last}")
                # initials
                aliases.append("".join(w[0].lower() for w in words if w))
                # just first name
                aliases.append(first)
                # just last name
                aliases.append(last)
            elif len(words) == 1:
                aliases.append(words[0].lower())

            # Handle email-derived names: extract name part before domain
            # Uses config-driven domain list instead of hardcoded values
            email_domains = []
            if get_config is not None:
                try:
                    cfg = get_config()
                    email_domains = cfg.get("organization.email_domains", [])
                except Exception:
                    pass

            if "@" in clean:
                # Extract name part before domain
                domain_pattern = "|".join(re.escape(d) for d in email_domains) if email_domains else ""
                strip_pattern = r"(@|\.)"
                if domain_pattern:
                    strip_pattern = rf"({domain_pattern}|com|@|\.)"
                email_name = re.sub(strip_pattern, " ", clean.lower()).strip()
                email_words = email_name.split()
                if email_words:
                    aliases.append("-".join(email_words))

        elif entity_type in ("project", "system", "brand", "component"):
            # Acronym from words
            if len(words) >= 2:
                acronym = "".join(w[0].lower() for w in words if w and w[0].isalpha())
                if len(acronym) >= 2:
                    aliases.append(acronym)
            # Each significant word
            for w in words:
                wl = w.lower()
                if len(wl) >= 3 and wl not in ("the", "and", "for", "with"):
                    aliases.append(wl)
            # No-space version
            no_space = "".join(w.lower() for w in words)
            if no_space != slug_dash.replace("-", ""):
                aliases.append(no_space)

        elif entity_type == "squad":
            # Remove "Squad" prefix if present
            stripped = [w for w in words if w.lower() != "squad"]
            if stripped:
                aliases.append("-".join(w.lower() for w in stripped))
                if len(stripped) >= 2:
                    acronym = "".join(w[0].lower() for w in stripped if w[0].isalpha())
                    if len(acronym) >= 2:
                        aliases.append(acronym)

        # Deduplicate, filter empties
        seen = set()
        unique = []
        for a in aliases:
            al = a.lower().strip()
            if al and al not in seen and len(al) >= 2:
                unique.append(al)
                seen.add(al)

        return unique

    def auto_generate_aliases(self, entity_id: str) -> List[str]:
        """
        Generate aliases for a single entity.

        Args:
            entity_id: Canonical entity ID

        Returns:
            List of suggested new aliases (filtered against existing + conflicts)
        """
        if not self._built:
            self.build_index()

        entity_path = self._entity_paths.get(entity_id)
        if not entity_path or not entity_path.exists():
            return []

        content = entity_path.read_text(encoding="utf-8")
        fm = self._parse_frontmatter(content)

        name = fm.get("name", "")
        entity_type = fm.get("$type", "entity")
        existing_aliases = set(a.lower() for a in (fm.get("$aliases", []) or []))

        candidates = self.parse_entity_name(name, entity_type)

        # Filter: remove already-existing aliases and conflict with other entities
        new_aliases = []
        for candidate in candidates:
            cl = candidate.lower()
            if cl in existing_aliases:
                continue
            # Check if this alias already resolves to a DIFFERENT entity
            resolved = self._index.get(cl)
            if resolved and resolved != entity_id:
                continue  # Skip -- would conflict
            new_aliases.append(candidate)

        return new_aliases

    def batch_add_aliases(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Generate and apply aliases to all entities with empty $aliases.

        Args:
            dry_run: If True, report without applying

        Returns:
            Stats dict: entities_processed, aliases_added, conflicts_detected
        """
        try:
            from pm_os_brain.tools.relationships.safe_write import atomic_write
        except ImportError:
            try:
                from brain_core.safe_write import atomic_write
            except ImportError:
                def atomic_write(p, c, **kw):
                    Path(p).write_text(c, encoding=kw.get("encoding", "utf-8"))

        if not self._built:
            self.build_index()

        stats = {
            "entities_processed": 0,
            "entities_modified": 0,
            "aliases_added": 0,
            "conflicts_detected": 0,
            "dry_run": dry_run,
        }

        for entity_id, entity_path in self._entity_paths.items():
            if not entity_path.exists():
                continue

            try:
                content = entity_path.read_text(encoding="utf-8")
                fm = self._parse_frontmatter(content)

                if not fm.get("$type"):
                    continue

                current_aliases = fm.get("$aliases", []) or []
                stats["entities_processed"] += 1

                new_aliases = self.auto_generate_aliases(entity_id)
                if not new_aliases:
                    continue

                combined = list(current_aliases) + new_aliases
                stats["aliases_added"] += len(new_aliases)
                stats["entities_modified"] += 1

                if not dry_run:
                    fm["$aliases"] = combined
                    # Re-serialize
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        body = parts[2]
                        fm_str = yaml.dump(
                            fm, default_flow_style=False,
                            allow_unicode=True, sort_keys=False,
                        )
                        new_content = f"---\n{fm_str}---{body}"
                        atomic_write(entity_path, new_content)

                        # Update index for new aliases
                        for alias in new_aliases:
                            self._index[alias.lower()] = entity_id
                            if entity_id in self._reverse_index:
                                self._reverse_index[entity_id].add(alias)

            except Exception:
                continue

        return stats

    def validate_alias_uniqueness(self) -> List[Dict[str, Any]]:
        """
        Report alias collisions across entities.

        Returns:
            List of {alias, entities: [entity_ids]} for collisions
        """
        if not self._built:
            self.build_index()

        # Build alias -> entity mapping
        alias_map: Dict[str, List[str]] = {}
        for entity_id, entity_path in self._entity_paths.items():
            if not entity_path.exists():
                continue
            try:
                content = entity_path.read_text(encoding="utf-8")
                fm = self._parse_frontmatter(content)
                aliases = fm.get("$aliases", []) or []
                for alias in aliases:
                    al = alias.lower()
                    if al not in alias_map:
                        alias_map[al] = []
                    alias_map[al].append(entity_id)
            except Exception:
                continue

        collisions = []
        for alias, entities in alias_map.items():
            if len(entities) > 1:
                collisions.append({"alias": alias, "entities": entities})

        return collisions

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter."""
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        try:
            return yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return {}


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Canonical reference resolver for Brain entities"
    )
    parser.add_argument(
        "action",
        choices=["build", "resolve", "stats", "similar", "generate-aliases", "validate-aliases"],
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--reference",
        "-r",
        help="Reference to resolve",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without applying changes (for generate-aliases)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (for generate-aliases)",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        try:
            paths = get_paths()
            args.brain_path = paths.user / "brain"
        except Exception:
            args.brain_path = Path.cwd() / "user" / "brain"

    resolver = CanonicalResolver(args.brain_path)

    if args.action == "build":
        count = resolver.build_index()
        print(f"Indexed {count} entities")
        stats = resolver.get_stats()
        print(f"Total references: {stats['total_references']}")
        print(f"Avg refs per entity: {stats['avg_refs_per_entity']}")

    elif args.action == "resolve":
        if not args.reference:
            print("Error: --reference required for resolve action")
            return 1

        canonical = resolver.resolve(args.reference)
        if canonical:
            print(f"Resolved: {args.reference} -> {canonical}")
            path = resolver.get_entity_path(canonical)
            if path:
                print(f"Path: {path}")
        else:
            print(f"Could not resolve: {args.reference}")
            print("Similar matches:")
            for match, score in resolver.find_similar(args.reference):
                print(f"  {match} (score: {score:.2f})")

    elif args.action == "stats":
        resolver.build_index()
        stats = resolver.get_stats()
        print(f"Total entities: {stats['total_entities']}")
        print(f"Total references: {stats['total_references']}")
        print(f"Avg refs per entity: {stats['avg_refs_per_entity']}")

    elif args.action == "similar":
        if not args.reference:
            print("Error: --reference required for similar action")
            return 1

        results = resolver.find_similar(args.reference)
        print(f"Similar to '{args.reference}':")
        for canonical, score in results:
            print(f"  {canonical} (score: {score:.2f})")

    elif args.action == "generate-aliases":
        dry_run = not args.apply
        resolver.build_index(force=True)
        stats = resolver.batch_add_aliases(dry_run=dry_run)
        print(f"Alias generation {'(dry run)' if dry_run else ''}:")
        print(f"  Entities processed: {stats['entities_processed']}")
        print(f"  Entities modified: {stats['entities_modified']}")
        print(f"  Aliases added: {stats['aliases_added']}")
        if dry_run:
            print(f"\nDry run -- no changes applied. Use --apply to write aliases.")

    elif args.action == "validate-aliases":
        resolver.build_index(force=True)
        collisions = resolver.validate_alias_uniqueness()
        if collisions:
            print(f"Found {len(collisions)} alias collisions:")
            for c in collisions[:20]:
                print(f"  '{c['alias']}': {', '.join(c['entities'])}")
        else:
            print("No alias collisions found.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
