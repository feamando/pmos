"""
Alias Manager - Feature Name Matching and Consolidation

Implements fuzzy matching for feature name comparison to detect
potential duplicates and consolidate aliases.

Matching Rules:
    - >90% similarity: Auto-consolidate as alias, notify user
    - 70-90% similarity: Ask user if same feature
    - <70% similarity: Treat as new feature

Alias Sources:
    - Manual consolidation (user confirmed)
    - Master Sheet feature names
    - Slack mentions with similar keywords
    - Jira ticket titles referencing same epic
    - Brain entity aliases

Usage:
    from tools.context_engine import AliasManager

    manager = AliasManager()
    result = manager.find_existing_feature("OTP Checkout Recovery", "meal-kit")

    if result.type == "auto_consolidate":
        # Link to existing feature
        pass
    elif result.type == "ask_user":
        # Prompt user for confirmation
        print(result.question)

Fuzzy Matching Algorithm:
    Uses a combination of:
    1. Levenshtein distance (edit distance) - handles typos and character changes
    2. Token-based Jaccard similarity - handles word reordering
    3. SequenceMatcher ratio - handles substring matching

    These are combined with adaptive weighting based on string length.
"""

import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Common product code prefixes to strip during normalization
PRODUCT_CODE_PREFIXES = [
    "MK",
    "WB",
    "FF",
    "PROJ2",  # From config.yaml product_mapping
    "goc",
    "tpt",
    "ff",
    "mio",
]

# Common words to remove during normalization (stopwords)
STOPWORDS = {
    "the",
    "a",
    "an",
    "for",
    "to",
    "of",
    "in",
    "on",
    "with",
    "and",
    "or",
    "but",
    "is",
    "are",
    "be",
    "was",
    "were",
    "feature",
    "project",
    "initiative",
    "improvement",
    "implementation",
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
    """
    Manages feature aliases and detects potential duplicates.

    Uses fuzzy matching to compare feature names and suggest
    consolidation when similar features are found.
    """

    # Similarity thresholds
    AUTO_CONSOLIDATE_THRESHOLD = 0.90  # >90% auto-consolidate
    ASK_USER_THRESHOLD = 0.70  # 70-90% ask user

    def __init__(self):
        """Initialize the alias manager."""
        self._cached_features: Optional[List[Dict[str, Any]]] = None

    def fuzzy_match(self, s1: str, s2: str) -> float:
        """
        Calculate similarity ratio between two strings.

        Uses a combined similarity algorithm that incorporates:
        - Levenshtein (edit) distance for typo detection
        - SequenceMatcher for substring matching
        - Jaccard similarity for word-level matching

        Handles edge cases:
        - Empty strings return 0.0 (unless both empty, then 1.0)
        - Very short names (< 3 chars after normalization) return 0.0
        - Product code prefixes are stripped before comparison

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity ratio between 0.0 and 1.0

        Examples:
            >>> manager = AliasManager()
            >>> manager.fuzzy_match("OTP Checkout Recovery", "OTP checkout recovery")
            # ~1.0 (case difference only)
            >>> manager.fuzzy_match("MK OTP Flow", "OTP Flow Improvements")
            # ~0.7-0.8 (partial match with prefix stripped)
        """
        # Handle edge cases
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Check if both names are meaningful
        if not is_meaningful_name(s1) or not is_meaningful_name(s2):
            # For very short/empty names after normalization,
            # fall back to basic comparison
            s1_lower = s1.strip().lower() if s1 else ""
            s2_lower = s2.strip().lower() if s2 else ""
            if s1_lower == s2_lower:
                return 1.0
            return 0.0

        # Use combined similarity with normalization
        return combined_similarity(s1, s2, normalize=True)

    def _normalize(self, s: str) -> str:
        """
        Normalize a string for comparison.

        Converts to lowercase, removes product code prefixes,
        strips stopwords, removes special characters,
        and normalizes whitespace.

        This is a legacy method - use normalize_feature_name() directly
        for more control over normalization options.

        Args:
            s: String to normalize

        Returns:
            Normalized string
        """
        return normalize_feature_name(s, strip_product_codes=True)

    def find_existing_feature(self, new_title: str, product_id: str) -> MatchResult:
        """
        Check if a feature with similar name already exists.

        Args:
            new_title: Title of the new feature
            product_id: Product to check in

        Returns:
            MatchResult indicating action to take
        """
        # Get existing features for this product
        existing = self._get_existing_features(product_id)

        best_match: Optional[Dict[str, Any]] = None
        best_similarity = 0.0

        for feature in existing:
            feature_name = feature.get("name", "")
            similarity = self.fuzzy_match(new_title, feature_name)

            # Also check aliases
            for alias in feature.get("aliases", []):
                alias_similarity = self.fuzzy_match(new_title, alias)
                similarity = max(similarity, alias_similarity)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = feature

        # Determine action based on similarity
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
        """
        Get existing features for a product.

        Combines data from:
        1. Master Sheet
        2. Existing feature-state.yaml files
        3. Brain entities

        Args:
            product_id: Product to get features for

        Returns:
            List of feature info dicts
        """
        features = []

        # Try to get from Master Sheet
        try:
            features.extend(self._get_features_from_master_sheet(product_id))
        except Exception:
            pass

        # Try to get from existing feature folders
        try:
            features.extend(self._get_features_from_folders(product_id))
        except Exception:
            pass

        return features

    def _get_features_from_master_sheet(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Get features from Master Sheet "topics" tab.

        Uses the MasterSheetReader from context_engine for reading topics.

        Args:
            product_id: Product to filter by

        Returns:
            List of feature info from Master Sheet
        """
        try:
            from .master_sheet_reader import MasterSheetReader

            reader = MasterSheetReader()
            return reader.get_features_for_alias_matching(product_id)

        except Exception:
            # Master Sheet not available - continue without it
            return []

    def _get_features_from_folders(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Get features from existing feature folders.

        Args:
            product_id: Product to get features for

        Returns:
            List of feature info from folders
        """
        features = []

        try:
            import config_loader

            config = config_loader.get_config()
            user_path = Path(config.user_path)
            products_path = user_path / "products"

            if not products_path.exists():
                return features

            # Search through organization/product structure
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
                        from .feature_state import FeatureState

                        state = FeatureState.load(feature_path)
                        if state:
                            aliases = []
                            if state.aliases:
                                aliases = state.aliases.known_aliases

                            features.append(
                                {
                                    "name": state.title,
                                    "slug": state.slug,
                                    "aliases": aliases,
                                    "row": state.master_sheet_row,
                                    "source": "feature_folder",
                                }
                            )

        except Exception:
            pass

        return features

    def add_alias(self, feature_path: Path, alias: str, source: str = "manual") -> bool:
        """
        Add an alias to a feature.

        Args:
            feature_path: Path to the feature folder
            alias: New alias to add
            source: Source of the alias (manual, slack, jira)

        Returns:
            True if successful
        """
        from .feature_state import AliasInfo, FeatureState

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
        """
        Consolidate a secondary feature name as an alias of the primary.

        Args:
            primary_path: Path to the primary feature
            secondary_title: Title of the feature to consolidate as alias
            merge_aliases: Whether to merge any existing aliases

        Returns:
            True if successful
        """
        from .feature_state import FeatureState

        state = FeatureState.load(primary_path)
        if not state:
            return False

        # Add the secondary title as an alias
        self.add_alias(primary_path, secondary_title, source="consolidation")

        return True


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein (edit) distance between two strings.

    The Levenshtein distance is the minimum number of single-character
    edits (insertions, deletions, substitutions) required to transform
    one string into the other.

    Uses dynamic programming with O(min(m,n)) space complexity.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Edit distance (non-negative integer)

    Examples:
        >>> levenshtein_distance("kitten", "sitting")
        3
        >>> levenshtein_distance("", "abc")
        3
        >>> levenshtein_distance("same", "same")
        0
    """
    # Handle empty strings
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    # Make s1 the shorter string for space efficiency
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    # Previous and current row of distances
    prev_row = list(range(len(s1) + 1))
    curr_row = [0] * (len(s1) + 1)

    for i, c2 in enumerate(s2):
        curr_row[0] = i + 1
        for j, c1 in enumerate(s1):
            # Cost is 0 if characters match, 1 otherwise
            cost = 0 if c1 == c2 else 1
            curr_row[j + 1] = min(
                prev_row[j + 1] + 1,  # Deletion
                curr_row[j] + 1,  # Insertion
                prev_row[j] + cost,  # Substitution
            )
        prev_row, curr_row = curr_row, prev_row

    return prev_row[len(s1)]


def levenshtein_similarity(s1: str, s2: str) -> float:
    """
    Calculate normalized Levenshtein similarity between two strings.

    Converts edit distance to a similarity score between 0.0 and 1.0.
    Formula: 1 - (distance / max_length)

    Args:
        s1: First string
        s2: Second string

    Returns:
        Similarity ratio between 0.0 and 1.0

    Examples:
        >>> levenshtein_similarity("hello", "hello")
        1.0
        >>> levenshtein_similarity("hello", "hallo")
        0.8
    """
    if not s1 and not s2:
        return 1.0

    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 1.0

    distance = levenshtein_distance(s1, s2)
    return 1.0 - (distance / max_len)


def tokenize(text: str) -> List[str]:
    """
    Tokenize text into words for comparison.

    Args:
        text: Text to tokenize

    Returns:
        List of tokens (lowercase, filtered)

    Examples:
        >>> tokenize("OTP Checkout Recovery")
        ['otp', 'checkout', 'recovery']
        >>> tokenize("MK-OTP-Flow")
        ['goc', 'otp', 'flow']
    """
    if not text:
        return []

    # Convert to lowercase
    text = text.lower()

    # Split on non-alphanumeric characters
    tokens = re.findall(r"\b\w+\b", text)

    return tokens


def jaccard_similarity(s1: str, s2: str) -> float:
    """
    Calculate Jaccard similarity between two strings.

    Jaccard similarity is the size of the intersection divided by
    the size of the union of two token sets.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Jaccard similarity between 0.0 and 1.0

    Examples:
        >>> jaccard_similarity("checkout flow", "flow checkout")
        1.0
        >>> jaccard_similarity("otp recovery", "otp checkout recovery")
        0.666...
    """
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
    """
    Normalize a feature name for comparison.

    Performs the following normalizations:
    1. Convert to lowercase
    2. Strip leading/trailing whitespace
    3. Remove common product code prefixes (MK, WB, FF, etc.)
    4. Remove stopwords (the, a, for, etc.)
    5. Remove special characters except alphanumeric and spaces
    6. Normalize whitespace (multiple spaces to single)

    Args:
        name: Feature name to normalize
        strip_product_codes: Whether to remove product code prefixes

    Returns:
        Normalized name string

    Examples:
        >>> normalize_feature_name("MK OTP Checkout Recovery")
        'otp checkout recovery'
        >>> normalize_feature_name("  The Feature Implementation  ")
        'feature implementation'
        >>> normalize_feature_name("MK-OTP-Flow-v2")
        'otp flow v2'
    """
    if not name:
        return ""

    result = name.strip().lower()

    # Remove product code prefixes (case-insensitive)
    if strip_product_codes:
        for prefix in PRODUCT_CODE_PREFIXES:
            prefix_lower = prefix.lower()
            # Match prefix at start followed by space, hyphen, or underscore
            pattern = rf"^{re.escape(prefix_lower)}[\s\-_]+"
            result = re.sub(pattern, "", result)
            # Also match just the prefix followed by space
            if result.startswith(prefix_lower + " "):
                result = result[len(prefix_lower) + 1 :]
            elif result.startswith(prefix_lower + "-"):
                result = result[len(prefix_lower) + 1 :]
            elif result.startswith(prefix_lower + "_"):
                result = result[len(prefix_lower) + 1 :]

    # Replace non-alphanumeric with spaces
    result = re.sub(r"[^a-z0-9\s]", " ", result)

    # Remove stopwords
    words = result.split()
    words = [w for w in words if w not in STOPWORDS]

    # Rejoin and normalize whitespace
    result = " ".join(words)

    return result


def combined_similarity(s1: str, s2: str, normalize: bool = True) -> float:
    """
    Calculate combined similarity using multiple methods.

    Uses a weighted combination of:
    - Levenshtein similarity (edit distance) - good for typos, minor changes
    - SequenceMatcher ratio - good for substring matching
    - Jaccard similarity (token-based) - good for word reordering

    The weights are adaptive based on string characteristics:
    - Shorter strings: favor edit distance (typo detection)
    - Longer strings: favor Jaccard (word-level matching)
    - Medium strings: balanced approach

    Args:
        s1: First string
        s2: Second string
        normalize: Whether to normalize strings before comparison

    Returns:
        Combined similarity between 0.0 and 1.0

    Examples:
        >>> combined_similarity("OTP Checkout Recovery", "OTP checkout recovery")
        # High similarity (case difference only)
        >>> combined_similarity("checkout flow", "flow checkout")
        # High similarity (word reorder)
        >>> combined_similarity("MK OTP", "OTP recovery")
        # Lower similarity (different terms)
    """
    # Handle edge cases
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Normalize if requested
    if normalize:
        s1_norm = normalize_feature_name(s1)
        s2_norm = normalize_feature_name(s2)
    else:
        s1_norm = s1.lower().strip()
        s2_norm = s2.lower().strip()

    # Handle edge case where normalization removes everything
    if not s1_norm and not s2_norm:
        return 1.0
    if not s1_norm or not s2_norm:
        return 0.0

    # Calculate individual similarities
    lev_sim = levenshtein_similarity(s1_norm, s2_norm)
    seq_sim = SequenceMatcher(None, s1_norm, s2_norm).ratio()
    jac_sim = jaccard_similarity(s1_norm, s2_norm)

    # Adaptive weighting based on string length
    avg_len = (len(s1_norm) + len(s2_norm)) / 2
    token_count = (len(s1_norm.split()) + len(s2_norm.split())) / 2

    if avg_len < 10:
        # Short strings: favor edit distance
        weights = (0.5, 0.3, 0.2)  # lev, seq, jac
    elif token_count <= 2:
        # Few tokens: favor edit distance and sequence
        weights = (0.4, 0.4, 0.2)
    elif token_count >= 5:
        # Many tokens: favor Jaccard (word-level)
        weights = (0.2, 0.3, 0.5)
    else:
        # Medium: balanced
        weights = (0.35, 0.35, 0.3)

    return lev_sim * weights[0] + seq_sim * weights[1] + jac_sim * weights[2]


def is_meaningful_name(name: str) -> bool:
    """
    Check if a name is meaningful enough for comparison.

    A name is considered meaningful if it has at least MIN_MEANINGFUL_LENGTH
    characters after normalization, excluding stopwords and product codes.

    Args:
        name: Feature name to check

    Returns:
        True if meaningful, False otherwise

    Examples:
        >>> is_meaningful_name("OTP Recovery")
        True
        >>> is_meaningful_name("the")
        False
        >>> is_meaningful_name("")
        False
    """
    if not name:
        return False

    normalized = normalize_feature_name(name)
    return len(normalized) >= MIN_MEANINGFUL_LENGTH


def get_similarity_category(
    similarity: float, auto_threshold: float = 0.90, ask_threshold: float = 0.70
) -> str:
    """
    Categorize similarity score into action type.

    Args:
        similarity: Similarity score (0.0 to 1.0)
        auto_threshold: Threshold for auto-consolidation (default 0.90)
        ask_threshold: Threshold for asking user (default 0.70)

    Returns:
        One of: "auto_consolidate", "ask_user", "new_feature"

    Examples:
        >>> get_similarity_category(0.95)
        'auto_consolidate'
        >>> get_similarity_category(0.80)
        'ask_user'
        >>> get_similarity_category(0.50)
        'new_feature'
    """
    if similarity >= auto_threshold:
        return "auto_consolidate"
    elif similarity >= ask_threshold:
        return "ask_user"
    else:
        return "new_feature"


def extract_key_terms(name: str) -> List[str]:
    """
    Extract key terms from a feature name for matching.

    Removes stopwords and product codes, returns significant terms.

    Args:
        name: Feature name

    Returns:
        List of key terms (lowercase, sorted)

    Examples:
        >>> extract_key_terms("MK OTP Checkout Recovery Feature")
        ['checkout', 'otp', 'recovery']
    """
    normalized = normalize_feature_name(name)
    terms = [t for t in normalized.split() if t]
    return sorted(set(terms))
