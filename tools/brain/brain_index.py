#!/usr/bin/env python3
"""
Brain Index - Inverted Index Builder for Content Search

Builds an inverted index from all Brain entity files for O(1) content lookup.
Includes Porter stemming for word normalization.

Usage:
    python brain_index.py                    # Build index
    python brain_index.py --stats            # Show index statistics
    python brain_index.py --search "query"   # Test search (debug)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add tools directory to path for config_loader
sys.path.insert(0, str(Path(__file__).parent.parent))
import config_loader

# Try to import yaml
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# --- Configuration ---
ROOT_PATH = config_loader.get_root_path()
USER_PATH = ROOT_PATH / "user"
BRAIN_DIR = USER_PATH / "brain"
INDEX_FILE = BRAIN_DIR / "content_index.json"
REGISTRY_FILE = BRAIN_DIR / "registry.yaml"

# Directories to index
INDEX_DIRS = [
    "Entities",
    "Projects",
    "Experiments",
    "Architecture",
    "Decisions",
    "Strategy",
    "Technical",
]

# --- Porter Stemmer (simplified) ---
# Using a basic implementation to avoid external dependencies


class PorterStemmer:
    """Simplified Porter stemmer for English word normalization."""

    def __init__(self):
        self.cache = {}

    def stem(self, word: str) -> str:
        """Stem a word to its root form."""
        if word in self.cache:
            return self.cache[word]

        word = word.lower()
        if len(word) <= 2:
            return word

        # Basic suffix stripping
        original = word

        # Step 1a: SSES -> SS, IES -> I, SS -> SS, S -> ''
        if word.endswith("sses"):
            word = word[:-2]
        elif word.endswith("ies"):
            word = word[:-2]
        elif word.endswith("ss"):
            pass
        elif word.endswith("s"):
            word = word[:-1]

        # Step 1b: (m>0) EED -> EE, (*v*) ED -> '', (*v*) ING -> ''
        if word.endswith("eed"):
            if len(word) > 4:
                word = word[:-1]
        elif word.endswith("ed"):
            if self._has_vowel(word[:-2]):
                word = word[:-2]
                word = self._step1b_fixup(word)
        elif word.endswith("ing"):
            if self._has_vowel(word[:-3]):
                word = word[:-3]
                word = self._step1b_fixup(word)

        # Step 2: Common suffix replacements
        replacements = [
            ("ational", "ate"),
            ("tional", "tion"),
            ("enci", "ence"),
            ("anci", "ance"),
            ("izer", "ize"),
            ("ation", "ate"),
            ("ator", "ate"),
            ("alism", "al"),
            ("iveness", "ive"),
            ("fulness", "ful"),
            ("ousness", "ous"),
            ("aliti", "al"),
            ("iviti", "ive"),
            ("biliti", "ble"),
        ]
        for suffix, replacement in replacements:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                word = word[: -len(suffix)] + replacement
                break

        # Step 3-5: Additional simplification
        if word.endswith("icate") and len(word) > 7:
            word = word[:-3]
        elif word.endswith("ative") and len(word) > 7:
            word = word[:-5]
        elif word.endswith("alize") and len(word) > 7:
            word = word[:-3]
        elif word.endswith("ful") and len(word) > 5:
            word = word[:-3]
        elif word.endswith("ness") and len(word) > 6:
            word = word[:-4]

        self.cache[original] = word
        return word

    def _has_vowel(self, word: str) -> bool:
        """Check if word contains a vowel."""
        return bool(re.search(r"[aeiou]", word))

    def _step1b_fixup(self, word: str) -> str:
        """Fix up word after step 1b."""
        if word.endswith(("at", "bl", "iz")):
            return word + "e"
        if len(word) > 2 and word[-1] == word[-2] and word[-1] not in "lsz":
            return word[:-1]
        return word


class BrainIndex:
    """Builds and manages inverted index for Brain content search."""

    def __init__(self, brain_path: Optional[Path] = None):
        self.brain_path = Path(brain_path) if brain_path else BRAIN_DIR
        self.index_file = self.brain_path / "content_index.json"
        self.stemmer = PorterStemmer()
        self.index: Dict[str, List[str]] = {}
        self.meta: Dict[str, Any] = {}

        # Stopwords to exclude
        self.stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "they",
            "them",
            "their",
            "we",
            "our",
            "you",
            "your",
            "he",
            "she",
            "his",
            "her",
            "i",
            "my",
            "me",
            "not",
            "no",
            "yes",
            "all",
            "any",
            "some",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "such",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "also",
            "now",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "what",
            "which",
            "who",
            "whom",
            "whose",
        }

    def build(self) -> Dict[str, Any]:
        """Build inverted index from all entity files."""
        print(f"Building index from {self.brain_path}...")

        index = defaultdict(set)
        entity_count = 0
        token_count = 0
        errors = []

        for dir_name in INDEX_DIRS:
            dir_path = self.brain_path / dir_name
            if not dir_path.exists():
                continue

            for md_file in dir_path.rglob("*.md"):
                try:
                    entity_id = self._file_to_entity_id(md_file)
                    content = self._extract_text(md_file)
                    tokens = self._tokenize_and_stem(content)

                    for token in tokens:
                        index[token].add(entity_id)
                        token_count += 1

                    entity_count += 1

                except Exception as e:
                    errors.append(f"{md_file}: {e}")

        # Convert sets to sorted lists for JSON serialization
        self.index = {k: sorted(v) for k, v in index.items()}

        self.meta = {
            "built": datetime.now().isoformat(),
            "brain_path": str(self.brain_path),
            "entity_count": entity_count,
            "token_count": len(self.index),
            "total_postings": token_count,
            "errors": errors[:10] if errors else [],
        }

        print(f"Indexed {entity_count} entities, {len(self.index)} unique tokens")

        return {"meta": self.meta, "index": self.index}

    def save(self, path: Optional[Path] = None):
        """Save index to JSON file."""
        save_path = Path(path) if path else self.index_file

        data = {"meta": self.meta, "index": self.index}

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        size_kb = save_path.stat().st_size / 1024
        print(f"Saved index to {save_path} ({size_kb:.1f} KB)")

    def load(self, path: Optional[Path] = None) -> bool:
        """Load index from JSON file."""
        load_path = Path(path) if path else self.index_file

        if not load_path.exists():
            return False

        try:
            with open(load_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.meta = data.get("meta", {})
            self.index = data.get("index", {})
            return True

        except Exception as e:
            print(f"Error loading index: {e}", file=sys.stderr)
            return False

    def search(self, query: str, mode: str = "and") -> List[str]:
        """
        Search index for query tokens.

        Args:
            query: Search query string
            mode: "and" (all tokens must match) or "or" (any token matches)

        Returns:
            List of matching entity IDs
        """
        tokens = self._tokenize_and_stem(query)

        if not tokens:
            return []

        # Get posting lists for each token
        posting_lists = []
        for token in tokens:
            if token in self.index:
                posting_lists.append(set(self.index[token]))
            elif mode == "and":
                # Token not found and we need all tokens - no results
                return []

        if not posting_lists:
            return []

        # Combine based on mode
        if mode == "and":
            result = posting_lists[0]
            for pl in posting_lists[1:]:
                result = result.intersection(pl)
        else:  # or
            result = set()
            for pl in posting_lists:
                result = result.union(pl)

        return sorted(result)

    def _file_to_entity_id(self, file_path: Path) -> str:
        """Convert file path to entity ID."""
        # Get relative path from brain directory
        rel_path = file_path.relative_to(self.brain_path)

        # Convert to entity ID format: Entities/People/John_Doe.md -> entity/person/john-doe
        parts = rel_path.parts

        # Get type from directory
        type_map = {
            "Entities": "entity",
            "Projects": "project",
            "Experiments": "experiment",
            "Architecture": "architecture",
            "Decisions": "decision",
            "Strategy": "strategy",
            "Technical": "technical",
        }

        entity_type = type_map.get(parts[0], parts[0].lower())

        # Get name from filename (without .md)
        name = file_path.stem.lower().replace("_", "-").replace(" ", "-")

        # Include subtype if present (e.g., Entities/People/ -> entity/person/)
        if len(parts) > 2:
            subtype = parts[1].lower().rstrip("s")  # People -> person
            return f"{entity_type}/{subtype}/{name}"

        return f"{entity_type}/{name}"

    def _extract_text(self, file_path: Path) -> str:
        """Extract searchable text from markdown file, stripping frontmatter."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Remove YAML frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3 :]

        # Remove markdown formatting
        # Remove code blocks
        content = re.sub(r"```[\s\S]*?```", "", content)
        # Remove inline code
        content = re.sub(r"`[^`]+`", "", content)
        # Remove links but keep text
        content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
        # Remove wiki-links but keep text
        content = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", content)
        # Remove headers markers
        content = re.sub(r"^#+\s+", "", content, flags=re.MULTILINE)
        # Remove emphasis markers
        content = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", content)

        return content

    def _tokenize_and_stem(self, text: str) -> Set[str]:
        """Tokenize text and stem each token."""
        # Extract words (letters and numbers)
        words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9]*\b", text.lower())

        tokens = set()
        for word in words:
            # Skip stopwords and very short words
            if word in self.stopwords or len(word) < 3:
                continue

            # Stem the word
            stemmed = self.stemmer.stem(word)
            if len(stemmed) >= 2:
                tokens.add(stemmed)

        return tokens

    def stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        if not self.index:
            self.load()

        if not self.index:
            return {"error": "No index loaded"}

        # Top 20 most common tokens
        token_counts = [
            (token, len(entities)) for token, entities in self.index.items()
        ]
        token_counts.sort(key=lambda x: -x[1])

        return {
            "meta": self.meta,
            "top_tokens": token_counts[:20],
            "total_tokens": len(self.index),
            "avg_postings_per_token": (
                sum(len(v) for v in self.index.values()) / len(self.index)
                if self.index
                else 0
            ),
        }


def main():
    parser = argparse.ArgumentParser(description="Brain Inverted Index Builder")
    parser.add_argument("--stats", action="store_true", help="Show index statistics")
    parser.add_argument("--search", type=str, help="Test search query")
    parser.add_argument(
        "--rebuild", action="store_true", help="Force rebuild even if index exists"
    )
    parser.add_argument("--brain-path", type=str, help="Path to brain directory")

    args = parser.parse_args()

    brain_path = Path(args.brain_path) if args.brain_path else BRAIN_DIR
    indexer = BrainIndex(brain_path)

    if args.stats:
        stats = indexer.stats()
        print(json.dumps(stats, indent=2, default=str))
        return

    if args.search:
        if not indexer.load():
            print("Index not found. Building...")
            indexer.build()
            indexer.save()

        results = indexer.search(args.search)
        print(f"Query: {args.search}")
        print(f"Results ({len(results)}):")
        for entity_id in results[:20]:
            print(f"  - {entity_id}")
        return

    # Build or rebuild index
    if args.rebuild or not indexer.index_file.exists():
        indexer.build()
        indexer.save()
    else:
        print(f"Index already exists at {indexer.index_file}")
        print("Use --rebuild to force rebuild")


if __name__ == "__main__":
    main()
