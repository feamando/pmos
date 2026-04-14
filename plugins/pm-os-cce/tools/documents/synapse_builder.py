"""
PM-OS CCE SynapseBuilder (v5.0)

Bi-directional link enforcer for Brain files. Scans Brain files for
'relationships' in frontmatter and ensures reciprocity.
If A -> 'owner' -> B, then B -> 'owns' -> A.

Supports both entity relationships and FPF reasoning relationships.

Usage:
    from pm_os_cce.tools.documents.synapse_builder import SynapseBuilder
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

# Brain plugin is OPTIONAL
try:
    from pm_os_brain.tools.brain_core.brain_loader import BrainLoader
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False

logger = logging.getLogger(__name__)

# Relationship Mapping (Forward -> Inverse)
RELATIONSHIP_MAP = {
    # Entity relationships
    "owner": "owns",
    "owns": "owner",
    "member_of": "has_member",
    "has_member": "member_of",
    "blocked_by": "blocks",
    "blocks": "blocked_by",
    "depends_on": "dependency_for",
    "dependency_for": "depends_on",
    "relates_to": "relates_to",
    "part_of": "has_part",
    "has_part": "part_of",
    # FPF Reasoning relationships
    "supports": "supported_by",
    "supported_by": "supports",
    "invalidates": "invalidated_by",
    "invalidated_by": "invalidates",
    "decides": "decided_by",
    "decided_by": "decides",
    "evidence_for": "has_evidence",
    "has_evidence": "evidence_for",
    "derived_from": "derives",
    "derives": "derived_from",
    "supersedes": "superseded_by",
    "superseded_by": "supersedes",
    "informs": "informed_by",
    "informed_by": "informs",
}


def _resolve_brain_dir() -> str:
    """Resolve the Brain directory path."""
    try:
        paths = get_paths()
        return str(paths.user / "brain")
    except Exception:
        return str(Path.home() / "pm-os" / "user" / "brain")


def parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """Extract YAML frontmatter and body."""
    if not HAS_YAML:
        return {}, content
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
    if match:
        try:
            return yaml.safe_load(match.group(1)) or {}, match.group(2)
        except yaml.YAMLError:
            return {}, content
    return {}, content


def normalize_link(link: str) -> str:
    """Clean wiki link to just the relative path."""
    clean = link.replace("[[", "").replace("]]", "")
    for prefix in ["user/brain/"]:
        if clean.startswith(prefix):
            clean = clean.replace(prefix, "")
            break
    return clean


def format_link(path: str) -> str:
    """Format path as wiki link."""
    clean = normalize_link(path)
    return f"[[{clean}]]"


def read_file_safe(path: str) -> str:
    """Read file with encoding fallback."""
    encodings = ["utf-8", "utf-16", "latin-1"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.warning("Error reading %s: %s", path, e)
            return ""
    logger.warning("Failed to decode %s", path)
    return ""


class SynapseBuilder:
    """
    Bi-directional link enforcer for Brain files.

    Scans all Brain markdown files, reads frontmatter relationships,
    and ensures every forward link has a corresponding inverse link
    in the target file.
    """

    def __init__(self, brain_dir: Optional[str] = None):
        """
        Initialize the synapse builder.

        Args:
            brain_dir: Path to Brain directory. If None, resolved via config.
        """
        self._brain_dir = brain_dir or _resolve_brain_dir()

    def get_brain_files(self) -> List[str]:
        """Get all .md files in Brain subdirectories."""
        files = []
        for root, _, filenames in os.walk(self._brain_dir):
            for filename in filenames:
                if filename.endswith(".md") and filename != "README.md":
                    files.append(os.path.join(root, filename))
        return files

    def build_graph(self) -> Dict[str, Dict[str, Set[str]]]:
        """
        Build a relationship graph from all Brain files.

        Returns:
            Dict mapping source file -> {rel_type -> set of target files}
        """
        files = self.get_brain_files()
        file_map = {
            os.path.relpath(f, self._brain_dir).replace("\\", "/"): f
            for f in files
        }

        graph: Dict[str, Dict[str, Set[str]]] = {}

        for rel_path, full_path in file_map.items():
            content = read_file_safe(full_path)
            if not content:
                continue

            fm, _ = parse_frontmatter(content)
            if not fm or "relationships" not in fm:
                continue

            if rel_path not in graph:
                graph[rel_path] = {}

            rels = fm["relationships"]
            if isinstance(rels, list):
                rels_dict: Dict[str, List] = {}
                for rel in rels:
                    if isinstance(rel, dict) and "type" in rel and "target" in rel:
                        rt = rel["type"]
                        if rt not in rels_dict:
                            rels_dict[rt] = []
                        rels_dict[rt].append(rel["target"])
                rels = rels_dict

            for rel_type, targets in rels.items():
                if rel_type not in RELATIONSHIP_MAP:
                    continue

                if rel_type not in graph[rel_path]:
                    graph[rel_path][rel_type] = set()

                for target in targets:
                    target_clean = normalize_link(target)
                    if target_clean not in file_map and (target_clean + ".md") in file_map:
                        target_clean += ".md"

                    if target_clean in file_map:
                        graph[rel_path][rel_type].add(target_clean)

        return graph

    def run(self, dry_run: bool = False) -> int:
        """
        Run synapse builder to enforce bidirectional links.

        Args:
            dry_run: If True, only report what would be changed

        Returns:
            Number of files modified
        """
        if not HAS_YAML:
            logger.error("PyYAML is required for synapse_builder. Install with: pip install pyyaml")
            return 0

        logger.info("Scanning Brain in %s...", self._brain_dir)

        files = self.get_brain_files()
        file_map = {
            os.path.relpath(f, self._brain_dir).replace("\\", "/"): f
            for f in files
        }

        graph = self.build_graph()

        # Calculate inverses needed
        updates_needed: Dict[str, Dict[str, Set[str]]] = {}

        for source, relations in graph.items():
            for rel_type, targets in relations.items():
                inverse_type = RELATIONSHIP_MAP[rel_type]
                for target in targets:
                    if target not in updates_needed:
                        updates_needed[target] = {}
                    if inverse_type not in updates_needed[target]:
                        updates_needed[target][inverse_type] = set()
                    updates_needed[target][inverse_type].add(source)

        # Apply updates
        modified_count = 0

        for target_file, needed_rels in updates_needed.items():
            if target_file not in file_map:
                continue

            full_path = file_map[target_file]
            content = read_file_safe(full_path)
            if not content:
                continue

            fm, body = parse_frontmatter(content)
            if "relationships" not in fm:
                fm["relationships"] = {}

            changed = False

            for rel_type, sources in needed_rels.items():
                if rel_type not in fm["relationships"]:
                    fm["relationships"][rel_type] = []

                current_values = set(
                    normalize_link(x) for x in fm["relationships"][rel_type]
                )

                for source in sources:
                    if source not in current_values:
                        fm["relationships"][rel_type].append(format_link(source))
                        changed = True
                        logger.info(
                            "  [+] %s: Adding '%s' -> %s",
                            target_file, rel_type, source,
                        )

            if changed:
                modified_count += 1
                if not dry_run:
                    new_fm = yaml.dump(fm, sort_keys=False, allow_unicode=True).strip()
                    new_content = f"---\n{new_fm}\n---\n{body}"
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

        logger.info("Done. Modified %d files.", modified_count)
        return modified_count


# Module-level convenience function

def run_synapse(brain_dir: Optional[str] = None, dry_run: bool = False) -> int:
    """Run synapse builder to enforce bidirectional links."""
    builder = SynapseBuilder(brain_dir)
    return builder.run(dry_run)
