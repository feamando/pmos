#!/usr/bin/env python3
"""
Participant Context Resolver (v5.0)

Looks up meeting participants in Brain (if installed), gathers
participant-specific context (projects, roles, recent activity),
and detects internal vs. external domains from config.

Extracted from v4.x meeting_prep.py to isolate participant intelligence.

Usage:
    from meeting.participant_context import ParticipantContextResolver

    resolver = ParticipantContextResolver(config, paths, brain_available=True)
    context = resolver.resolve_participants(participants)
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from config_loader import get_config
    except ImportError:
        get_config = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from path_resolver import get_paths
    except ImportError:
        get_paths = None

try:
    from pm_os_base.tools.core.plugin_deps import check_plugin
except ImportError:
    try:
        from plugin_deps import check_plugin
    except ImportError:
        def check_plugin(name: str) -> bool:
            return False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_frontmatter(content: str) -> Dict:
    """Extract YAML frontmatter from markdown file."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end < 0:
        return {}
    if not HAS_YAML:
        return {}
    try:
        return yaml.safe_load(content[3:end]) or {}
    except Exception:
        return {}


def extract_section(content: str, section_name: str) -> str:
    """Extract a markdown section by header name."""
    pattern = rf"##\s*{re.escape(section_name)}[^\n]*\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()[:500]
    return ""


# ---------------------------------------------------------------------------
# Brain Index
# ---------------------------------------------------------------------------


def build_alias_index(registry: Dict) -> Dict[str, Tuple[str, str, str]]:
    """Build a lookup index from Brain registry: alias -> (category, entity_id, file_path)."""
    index: Dict[str, Tuple[str, str, str]] = {}
    for category in ("projects", "entities", "architecture"):
        if category not in registry or registry[category] is None:
            continue
        for entity_id, entity_data in registry[category].items():
            if not isinstance(entity_data, dict):
                continue
            file_path = entity_data.get("file", "")
            aliases = entity_data.get("aliases", [])
            all_aliases = [entity_id] + (aliases if aliases else [])
            for alias in all_aliases:
                if alias:
                    index[alias.lower()] = (category, entity_id, file_path)
    return index


def resolve_participant_to_brain(
    name: str, email: str, alias_index: Dict
) -> Optional[Dict]:
    """Resolve a participant name/email to a Brain entity."""
    name_lower = name.lower()
    if name_lower in alias_index:
        cat, eid, path = alias_index[name_lower]
        return {"entity_id": eid, "category": cat, "file_path": path}
    first_name = name.split()[0].lower() if name else ""
    if first_name and first_name in alias_index:
        cat, eid, path = alias_index[first_name]
        return {"entity_id": eid, "category": cat, "file_path": path}
    email_prefix = email.split("@")[0].lower().replace(".", "_") if email else ""
    if email_prefix and email_prefix in alias_index:
        cat, eid, path = alias_index[email_prefix]
        return {"entity_id": eid, "category": cat, "file_path": path}
    return None


def load_brain_file(brain_dir: Path, file_path: str) -> str:
    """Load a file relative to brain_dir."""
    full_path = brain_dir / file_path
    if full_path.exists() and full_path.is_file():
        try:
            return full_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not read brain file %s: %s", full_path, exc)
    return ""


# ---------------------------------------------------------------------------
# Participant Context Resolver
# ---------------------------------------------------------------------------


class ParticipantContextResolver:
    """Resolve meeting participants to enriched context using Brain and config."""

    def __init__(
        self,
        config: Any,
        paths: Any,
        brain_available: Optional[bool] = None,
    ):
        """
        Args:
            config: PM-OS ConfigLoader instance.
            paths: PM-OS ResolvedPaths instance.
            brain_available: Whether Brain plugin is installed (auto-detected if None).
        """
        self.config = config
        self.paths = paths
        self.brain_available = (
            brain_available if brain_available is not None else check_plugin("pm-os-brain")
        )
        self._internal_domains: Optional[List[str]] = None
        self._alias_index: Optional[Dict] = None
        self._registry: Optional[Dict] = None

    # -- Lazy properties -----------------------------------------------------

    @property
    def internal_domains(self) -> List[str]:
        """Config-driven list of internal email domains."""
        if self._internal_domains is None:
            self._internal_domains = self.config.get(
                "meeting_prep.internal_domains", []
            )
        return self._internal_domains

    @property
    def brain_dir(self) -> Path:
        return self.paths.user / "brain"

    @property
    def registry(self) -> Dict:
        if self._registry is None:
            self._registry = self._load_brain_registry()
        return self._registry

    @property
    def alias_index(self) -> Dict:
        if self._alias_index is None:
            self._alias_index = build_alias_index(self.registry)
        return self._alias_index

    # -- Public API ----------------------------------------------------------

    def is_internal(self, email: str) -> bool:
        """Determine if an email belongs to an internal domain."""
        if not email or "@" not in email:
            return False
        domain = email.split("@")[-1].lower()
        return domain in self.internal_domains

    def classify_attendees(
        self, attendees: List[Dict]
    ) -> Tuple[List[Dict], int]:
        """
        Classify attendees as internal/external and build participant list.

        Args:
            attendees: Raw attendees from calendar event.

        Returns:
            (participants list, external_count)
        """
        participants: List[Dict] = []
        external_count = 0

        for attendee in attendees:
            if attendee.get("self", False):
                continue
            email = attendee.get("email", "")
            if "resource.calendar.google.com" in email:
                continue

            name = attendee.get("displayName") or email.split("@")[0]
            is_external = not self.is_internal(email)
            if is_external:
                external_count += 1

            participants.append(
                {"name": name, "email": email, "is_external": is_external}
            )

        return participants, external_count

    def resolve_participants(
        self, participants: List[Dict]
    ) -> List[Dict]:
        """
        Enrich participants with Brain context (if available).

        Args:
            participants: List of {"name", "email", "is_external"} dicts.

        Returns:
            Enriched list with 'role', 'summary', 'current_topics', 'key_topics'.
        """
        if not self.brain_available:
            logger.debug("Brain plugin not installed; skipping participant enrichment")
            return []

        enriched: List[Dict] = []
        for p in participants:
            match = resolve_participant_to_brain(
                p["name"], p["email"], self.alias_index
            )
            if not match:
                continue

            content = load_brain_file(self.brain_dir, match["file_path"])
            if not content:
                continue

            frontmatter = extract_frontmatter(content)
            enriched.append(
                {
                    "name": p["name"],
                    "role": frontmatter.get("role", "Unknown"),
                    "summary": content[:1500],
                    "current_topics": extract_section(content, "Current Discussions"),
                    "key_topics": extract_section(content, "Key Topics"),
                }
            )

        return enriched

    def get_related_projects(
        self, participant_names: List[str]
    ) -> List[Dict]:
        """Find projects related to participants from Brain registry."""
        if not self.brain_available:
            return []

        projects: List[Dict] = []
        seen_projects: set = set()

        for name in participant_names:
            entity_match = resolve_participant_to_brain(name, "", self.alias_index)
            if not entity_match:
                continue

            entity_content = load_brain_file(self.brain_dir, entity_match["file_path"])
            if not entity_content:
                continue

            frontmatter = extract_frontmatter(entity_content)
            related = frontmatter.get("related", [])

            for rel in related:
                if "Projects/" not in rel:
                    continue
                project_path = (
                    rel.replace("[[", "").replace("]]", "").replace('"', "")
                )
                if project_path in seen_projects:
                    continue
                seen_projects.add(project_path)

                project_content = load_brain_file(self.brain_dir, project_path)
                if not project_content:
                    continue

                project_fm = extract_frontmatter(project_content)
                summary = extract_section(project_content, "Executive Summary")
                if not summary:
                    summary = extract_section(project_content, "Overview")
                if not summary:
                    body_start = project_content.find("---", 3)
                    if body_start > 0:
                        summary = project_content[body_start + 3: body_start + 503].strip()

                projects.append(
                    {
                        "name": project_fm.get(
                            "title",
                            os.path.basename(project_path).replace(".md", ""),
                        ),
                        "status": project_fm.get("status", "Unknown"),
                        "summary": summary[:400],
                    }
                )

        return projects

    # -- Private helpers -----------------------------------------------------

    def _load_brain_registry(self) -> Dict:
        """Load Brain registry.yaml."""
        if not self.brain_available or not HAS_YAML:
            return {}
        registry_file = self.brain_dir / "registry.yaml"
        if not registry_file.exists():
            return {}
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("Failed to load brain registry: %s", exc)
            return {}


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(description="Test participant context resolution")
    parser.add_argument("--name", type=str, required=True, help="Participant name")
    parser.add_argument("--email", type=str, default="", help="Participant email")
    args = parser.parse_args()

    config_instance = get_config() if get_config else None
    paths_instance = get_paths() if get_paths else None

    if config_instance and paths_instance:
        resolver = ParticipantContextResolver(config_instance, paths_instance)
        result = resolver.resolve_participants(
            [{"name": args.name, "email": args.email, "is_external": False}]
        )
        print(_json.dumps(result, indent=2, default=str))
    else:
        print("Error: Could not load config/paths.", file=__import__("sys").stderr)
