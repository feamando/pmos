"""
PM-OS CCE Alias Manager (v5.0)

Feature name fuzzy matching and consolidation. Uses Levenshtein distance,
SequenceMatcher, and Jaccard similarity with adaptive weighting.
Config-driven product code prefixes.

Usage:
    from pm_os_cce.tools.feature.alias_manager import AliasManager, combined_similarity
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    try:
        from core.config_loader import get_config
    except ImportError:
        get_config = None

logger = logging.getLogger(__name__)


def _load_product_code_prefixes() -> List[str]:
    """Load product code prefixes from config, with empty default."""
    if get_config is None:
        return []
    try:
        config = get_config()
        raw = config.config if hasattr(config, "config") else {}
        master_sheet = raw.get("master_sheet", {})
        mapping = master_sheet.get("product_mapping", {})
        # Keys are the abbreviations (e.g., GOC, TPT)
        prefixes = []
        for abbr in mapping.keys():
            prefixes.append(abbr.upper())
            prefixes.append(abbr.lower())
        return prefixes
    except Exception:
        return []


# Loaded once at import; updated by config
PRODUCT_CODE_PREFIXES: List[str] = _load_product_code_prefixes()

# Common words to remove during normalization (generic, OK to keep)
STOPWORDS = {
    "the", "a", "an", "for", "to", "of", "in", "on", "with",
    "and", "or", "but", "is", "are", "be", "was", "were",
    "feature", "project", "initiative", "improvement", "implementation",
}

# Minimum length for meaningful comparison
MIN_MEANINGFUL_LENGTH = 3


@dataclass
class MatchResult:
    """Result of a feature matching operation."""

    type: str  # "auto_consolidate", "ask_user", "new_feature"
    existing_name: Optional[str] = None
    existing_slug: Optional[str] = None
    similarity: float = 0.0
    message: str = ""
    question: Optional[str] = None
    master_sheet_row: Optional[int] = None


class AliasManager:
    """Manages feature aliases and detects potential duplicates.

    Uses fuzzy matching to compare feature names and suggest
    consolidation when similar features are found.
    """

    AUTO_CONSOLIDATE_THRESHOLD = 0.90
    ASK_USER_THRESHOLD = 0.70

    def __init__(self):
        self._cached_features: Optional[List[Dict[str, Any]]] = None

    def fuzzy_match(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings."""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        if not is_meaningful_name(s1) or not is_meaningful_name(s2):
            s1_lower = s1.strip().lower() if s1 else ""
            s2_lower = s2.strip().lower() if s2 else ""
            if s1_lower == s2_lower:
                return 1.0
            return 0.0
        return combined_similarity(s1, s2, normalize=True)

    def _normalize(self, s: str) -> str:
        return normalize_feature_name(s, strip_product_codes=True)

    def find_existing_feature(self, new_title: str, product_id: str) -> MatchResult:
        """Check if a feature with similar name already exists."""
        existing = self._get_existing_features(product_id)
        best_match: Optional[Dict[str, Any]] = None
        best_similarity = 0.0
        for feature in existing:
            feature_name = feature.get("name", "")
            similarity = self.fuzzy_match(new_title, feature_name)
            for alias in feature.get("aliases", []):
                alias_similarity = self.fuzzy_match(new_title, alias)
                similarity = max(similarity, alias_similarity)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = feature
        if best_similarity >= self.AUTO_CONSOLIDATE_THRESHOLD and best_match:
            return MatchResult(
                type="auto_consolidate",
                existing_name=best_match.get("name"),
                existing_slug=best_match.get("slug"),
                similarity=best_similarity,
                message=f"Auto-linked to existing: {best_match.get('name')}",
                master_sheet_row=best_match.get("row"),
            )
        elif best_similarity >= self.ASK_USER_THRESHOLD and best_match:
            return MatchResult(
                type="ask_user",
                existing_name=best_match.get("name"),
                existing_slug=best_match.get("slug"),
                similarity=best_similarity,
                question=f"Is '{new_title}' the same as '{best_match.get('name')}'?",
                master_sheet_row=best_match.get("row"),
            )
        else:
            return MatchResult(type="new_feature", similarity=best_similarity)

    def _get_existing_features(self, product_id: str) -> List[Dict[str, Any]]:
        features = []
        try:
            features.extend(self._get_features_from_master_sheet(product_id))
        except Exception:
            pass
        try:
            features.extend(self._get_features_from_folders(product_id))
        except Exception:
            pass
        return features

    def _get_features_from_master_sheet(self, product_id: str) -> List[Dict[str, Any]]:
        try:
            from pm_os_cce.tools.integration.master_sheet_reader import MasterSheetReader
        except ImportError:
            try:
                from integration.master_sheet_reader import MasterSheetReader
            except ImportError:
                return []
        try:
            reader = MasterSheetReader()
            return reader.get_features_for_alias_matching(product_id)
        except Exception:
            return []

    def _get_features_from_folders(self, product_id: str) -> List[Dict[str, Any]]:
        features = []
        try:
            if get_config is None:
                return features
            config = get_config()
            user_path = Path(config.user_path)
            products_path = user_path / "products"
            if not products_path.exists():
                return features
            for org_path in products_path.iterdir():
                if not org_path.is_dir():
                    continue
                product_path = org_path / product_id
                if not product_path.exists():
                    continue
                for feature_path in product_path.iterdir():
                    if not feature_path.is_dir():
                        continue
                    state_file = feature_path / "feature-state.yaml"
                    if state_file.exists():
                        try:
                            from pm_os_cce.tools.feature.feature_state import FeatureState
                        except ImportError:
                            from feature.feature_state import FeatureState
                        state = FeatureState.load(feature_path)
                        if state:
                            aliases = []
                            if state.aliases:
                                aliases = state.aliases.known_aliases
                            features.append({
                                "name": state.title,
                                "slug": state.slug,
                                "aliases": aliases,
                                "row": state.master_sheet_row,
                                "source": "feature_folder",
                            })
        except Exception:
            pass
        return features

    def add_alias(self, feature_path: Path, alias: str, source: str = "manual") -> bool:
        """Add an alias to a feature."""
        try:
            from pm_os_cce.tools.feature.feature_state import AliasInfo, FeatureState
        except ImportError:
            from feature.feature_state import AliasInfo, FeatureState
        state = FeatureState.load(feature_path)
        if not state:
            return False
        if not state.aliases:
            state.aliases = AliasInfo(primary_name=state.title)
        if alias not in state.aliases.known_aliases:
            state.aliases.known_aliases.append(alias)
        state.save(feature_path)
        return True

    def consolidate_features(
        self, primary_path: Path, secondary_title: str, merge_aliases: bool = True
    ) -> bool:
        """Consolidate a secondary feature name as an alias of the primary."""
        try:
            from pm_os_cce.tools.feature.feature_state import FeatureState
        except ImportError:
            from feature.feature_state import FeatureState
        state = FeatureState.load(primary_path)
        if not state:
            return False
        self.add_alias(primary_path, secondary_title, source="consolidation")
        return True


# ========== Similarity Functions ==========


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein (edit) distance between two strings."""
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    prev_row = list(range(len(s1) + 1))
    curr_row = [0] * (len(s1) + 1)
    for i, c2 in enumerate(s2):
        curr_row[0] = i + 1
        for j, c1 in enumerate(s1):
            cost = 0 if c1 == c2 else 1
            curr_row[j + 1] = min(
                prev_row[j + 1] + 1,
                curr_row[j] + 1,
                prev_row[j] + cost,
            )
        prev_row, curr_row = curr_row, prev_row
    return prev_row[len(s1)]


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Calculate normalized Levenshtein similarity between two strings."""
    if not s1 and not s2:
        return 1.0
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0
    distance = levenshtein_distance(s1, s2)
    return 1.0 - (distance / max_len)


def tokenize(text: str) -> List[str]:
    """Tokenize text into words for comparison."""
    if not text:
        return []
    text = text.lower()
    tokens = re.findall(r"\b\w+\b", text)
    return tokens


def jaccard_similarity(s1: str, s2: str) -> float:
    """Calculate Jaccard similarity between two strings."""
    tokens1 = set(tokenize(s1))
    tokens2 = set(tokenize(s2))
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union)


def normalize_feature_name(name: str, strip_product_codes: bool = True) -> str:
    """Normalize a feature name for comparison."""
    if not name:
        return ""
    result = name.strip().lower()
    if strip_product_codes:
        for prefix in PRODUCT_CODE_PREFIXES:
            prefix_lower = prefix.lower()
            pattern = rf"^{re.escape(prefix_lower)}[\s\-_]+"
            result = re.sub(pattern, "", result)
            if result.startswith(prefix_lower + " "):
                result = result[len(prefix_lower) + 1:]
            elif result.startswith(prefix_lower + "-"):
                result = result[len(prefix_lower) + 1:]
            elif result.startswith(prefix_lower + "_"):
                result = result[len(prefix_lower) + 1:]
    result = re.sub(r"[^a-z0-9\s]", " ", result)
    words = result.split()
    words = [w for w in words if w not in STOPWORDS]
    result = " ".join(words)
    return result


def combined_similarity(s1: str, s2: str, normalize: bool = True) -> float:
    """Calculate combined similarity using multiple methods."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if normalize:
        s1_norm = normalize_feature_name(s1)
        s2_norm = normalize_feature_name(s2)
    else:
        s1_norm = s1.lower().strip()
        s2_norm = s2.lower().strip()
    if not s1_norm and not s2_norm:
        return 1.0
    if not s1_norm or not s2_norm:
        return 0.0
    lev_sim = levenshtein_similarity(s1_norm, s2_norm)
    seq_sim = SequenceMatcher(None, s1_norm, s2_norm).ratio()
    jac_sim = jaccard_similarity(s1_norm, s2_norm)
    avg_len = (len(s1_norm) + len(s2_norm)) / 2
    token_count = (len(s1_norm.split()) + len(s2_norm.split())) / 2
    if avg_len < 10:
        weights = (0.5, 0.3, 0.2)
    elif token_count <= 2:
        weights = (0.4, 0.4, 0.2)
    elif token_count >= 5:
        weights = (0.2, 0.3, 0.5)
    else:
        weights = (0.35, 0.35, 0.3)
    return lev_sim * weights[0] + seq_sim * weights[1] + jac_sim * weights[2]


def is_meaningful_name(name: str) -> bool:
    """Check if a name is meaningful enough for comparison."""
    if not name:
        return False
    normalized = normalize_feature_name(name)
    return len(normalized) >= MIN_MEANINGFUL_LENGTH


def get_similarity_category(
    similarity: float, auto_threshold: float = 0.90, ask_threshold: float = 0.70
) -> str:
    """Categorize similarity score into action type."""
    if similarity >= auto_threshold:
        return "auto_consolidate"
    elif similarity >= ask_threshold:
        return "ask_user"
    else:
        return "new_feature"


def extract_key_terms(name: str) -> List[str]:
    """Extract key terms from a feature name for matching."""
    normalized = normalize_feature_name(name)
    terms = [t for t in normalized.split() if t]
    return sorted(set(terms))
