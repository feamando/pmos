"""
PM-OS CCE FrameworkMatcher (v5.0)

Matches PM frameworks to features by context. Uses semantic search
(Brain vector index) when available, with keyword matching as fallback.
Returns ranked list of relevant frameworks for document injection.

Usage:
    from pm_os_cce.tools.util.framework_matcher import FrameworkMatcher
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# --- v5 imports: base plugin ---
try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

# --- v5 imports: Brain (optional) ---
try:
    from pm_os_brain.tools.brain_core.brain_search import BrainSearch
    HAS_BRAIN = True
except ImportError:
    HAS_BRAIN = False

logger = logging.getLogger(__name__)


class FrameworkMatcher:
    """
    Match PM frameworks to features by context.

    Uses semantic similarity (Brain vector index) when available,
    with keyword matching as fallback.
    """

    def __init__(self, brain_path: Optional[Path] = None):
        """
        Initialize the framework matcher.

        Args:
            brain_path: Path to user/brain/ directory (auto-resolved if None)
        """
        if brain_path:
            self.brain_path = brain_path
        else:
            try:
                paths = get_paths()
                self.brain_path = Path(paths.get("brain_path", "")) / "brain"
            except Exception:
                self.brain_path = Path(".")

        self.frameworks_dir = self.brain_path / "Frameworks"
        self._frameworks_cache: Optional[List[Dict[str, Any]]] = None

    @property
    def available(self) -> bool:
        """Check if any frameworks are installed."""
        return self.frameworks_dir.exists() and any(
            self.frameworks_dir.glob("*.md")
        )

    def _load_frameworks(self) -> List[Dict[str, Any]]:
        """Load and cache all framework entities."""
        if self._frameworks_cache is not None:
            return self._frameworks_cache

        frameworks: List[Dict[str, Any]] = []
        if not self.frameworks_dir.exists():
            self._frameworks_cache = []
            return []

        for md_file in sorted(self.frameworks_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                fm = self._parse_frontmatter(content)
                if fm and fm.get("$type") == "framework":
                    frameworks.append({
                        "entity_id": fm.get("$id", ""),
                        "name": fm.get("name", md_file.stem),
                        "author": fm.get("author", ""),
                        "category": fm.get("category", ""),
                        "use_case": fm.get("use_case", ""),
                        "key_steps": fm.get("key_steps", []),
                        "tags": fm.get("$tags", []),
                        "file_path": str(md_file),
                    })
            except Exception as e:
                logger.debug("Failed to parse %s: %s", md_file.name, e)

        self._frameworks_cache = frameworks
        return frameworks

    @staticmethod
    def _parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
        """Parse YAML frontmatter from a markdown file."""
        if not YAML_AVAILABLE:
            return None
        match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
        if not match:
            return None
        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None

    def match(
        self,
        feature_context: str,
        top_k: int = 3,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find frameworks most relevant to a feature context.

        Args:
            feature_context: Feature description or context text
            top_k: Maximum number of frameworks to return
            category_filter: Optional category to filter by

        Returns:
            Ranked list of framework match dicts with:
                framework_id, framework_name, author, relevance_score,
                use_case, key_steps_summary
        """
        if not self.available:
            return []

        results = self._semantic_match(feature_context, top_k, category_filter)
        if results:
            return results

        return self._keyword_match(feature_context, top_k, category_filter)

    def _semantic_match(
        self,
        query: str,
        top_k: int,
        category_filter: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Try semantic matching via BrainSearch (optional Brain plugin)."""
        if not HAS_BRAIN:
            return []

        try:
            search = BrainSearch(brain_path=self.brain_path)
            results = search.semantic_search(
                query, limit=top_k * 2, entity_type="framework"
            )
            if not results:
                return []

            frameworks = self._load_frameworks()
            fw_by_id = {fw["entity_id"]: fw for fw in frameworks}

            matches: List[Dict[str, Any]] = []
            for r in results:
                fw = fw_by_id.get(r.entity_id)
                if not fw:
                    continue
                if category_filter and fw["category"] != category_filter:
                    continue
                matches.append(self._build_match_result(fw, r.score))
                if len(matches) >= top_k:
                    break

            return matches

        except Exception as e:
            logger.debug("Semantic search unavailable: %s", e)
            return []

    def _keyword_match(
        self,
        query: str,
        top_k: int,
        category_filter: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Keyword-based matching on framework metadata."""
        frameworks = self._load_frameworks()
        if not frameworks:
            return []

        query_lower = query.lower()
        query_tokens = set(re.findall(r"\w+", query_lower))

        scored: List[tuple] = []
        for fw in frameworks:
            if category_filter and fw["category"] != category_filter:
                continue
            score = self._compute_keyword_score(fw, query_tokens, query_lower)
            if score > 0:
                scored.append((fw, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        return [
            self._build_match_result(fw, score)
            for fw, score in scored[:top_k]
        ]

    @staticmethod
    def _compute_keyword_score(
        fw: Dict[str, Any],
        query_tokens: set,
        query_lower: str,
    ) -> float:
        """Compute keyword relevance score for a framework."""
        score = 0.0

        # Name match
        name_lower = fw["name"].lower()
        name_tokens = set(re.findall(r"\w+", name_lower))
        name_overlap = len(query_tokens & name_tokens)
        if name_overlap:
            score += 0.4 * (name_overlap / max(len(query_tokens), 1))

        # Use case match
        use_case_lower = fw.get("use_case", "").lower()
        use_tokens = set(re.findall(r"\w+", use_case_lower))
        use_overlap = len(query_tokens & use_tokens)
        if use_overlap:
            score += 0.3 * (use_overlap / max(len(query_tokens), 1))

        # Category match
        category = fw.get("category", "").lower()
        if category in query_lower:
            score += 0.15

        # Tags match
        tags = [t.lower() for t in fw.get("tags", [])]
        tag_overlap = len(query_tokens & set(tags))
        if tag_overlap:
            score += 0.15 * (tag_overlap / max(len(query_tokens), 1))

        return min(score, 1.0)

    @staticmethod
    def _build_match_result(
        fw: Dict[str, Any], score: float
    ) -> Dict[str, Any]:
        """Build a standardized match result dict."""
        key_steps = fw.get("key_steps", [])
        steps_summary = "; ".join(key_steps[:3]) if key_steps else ""

        return {
            "framework_id": fw["entity_id"],
            "framework_name": fw["name"],
            "author": fw.get("author", ""),
            "relevance_score": round(score, 3),
            "use_case": fw.get("use_case", ""),
            "key_steps_summary": steps_summary,
            "category": fw.get("category", ""),
        }
