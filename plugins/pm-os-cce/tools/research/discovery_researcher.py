"""
PM-OS CCE DiscoveryResearcher (v5.0)

Pre-v1 knowledge discovery for the Context Engine. Searches existing PM-OS
knowledge sources (Brain entities, Master Sheet, vector search, daily context,
session research) to gather relevant information before generating the
context document draft.

Usage:
    from pm_os_cce.tools.research.discovery_researcher import DiscoveryResearcher
"""

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

# Brain plugin is OPTIONAL
HAS_BRAIN = False
try:
    from pm_os_brain.tools.brain.vector_index import BrainVectorIndex, VECTOR_AVAILABLE
    HAS_BRAIN = True
except ImportError:
    try:
        from brain.vector_index import BrainVectorIndex, VECTOR_AVAILABLE
        HAS_BRAIN = True
    except ImportError:
        VECTOR_AVAILABLE = False

logger = logging.getLogger(__name__)


class Confidence(Enum):
    """Source confidence level for discovery findings."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingCategory(Enum):
    """Category of a discovery finding."""

    PRIOR_ART = "prior_art"
    STAKEHOLDER = "stakeholder"
    TECHNICAL = "technical"
    RISK = "risk"
    DECISION = "decision"


@dataclass
class DiscoveryFinding:
    """
    A single finding from a discovery researcher.

    Attributes:
        title: Brief title of the finding
        content: Detailed content/description
        source_type: Which researcher produced this (brain, master_sheet, etc.)
        source_ref: File path, entity ID, or reference identifier
        confidence: Confidence level based on source authority
        category: What kind of finding this is
    """

    title: str
    content: str
    source_type: str
    source_ref: str
    confidence: Confidence
    category: FindingCategory

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "content": self.content,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "confidence": self.confidence.value,
            "category": self.category.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscoveryFinding":
        """Create DiscoveryFinding from dictionary."""
        return cls(
            title=data.get("title", ""),
            content=data.get("content", ""),
            source_type=data.get("source_type", ""),
            source_ref=data.get("source_ref", ""),
            confidence=Confidence(data.get("confidence", "low")),
            category=FindingCategory(data.get("category", "prior_art")),
        )


@dataclass
class DiscoveryResult:
    """
    Aggregated result from all discovery researchers.

    Attributes:
        findings: All findings from all researchers
        related_entities: Brain entity IDs that are related to this feature
        related_features: Existing features in same product (from Master Sheet)
        known_stakeholders: People connected to this domain
        open_questions: Gaps identified during discovery
        sources_searched: Which researchers were run
        coverage: Boolean checklist of discovery dimensions
    """

    findings: List[DiscoveryFinding] = field(default_factory=list)
    related_entities: List[str] = field(default_factory=list)
    related_features: List[str] = field(default_factory=list)
    known_stakeholders: List[Dict[str, str]] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    sources_searched: List[str] = field(default_factory=list)
    coverage: Dict[str, bool] = field(default_factory=lambda: {
        "brain_entities_found": False,
        "vector_search_found": False,
        "master_sheet_match": False,
        "stakeholders_identified": False,
        "prior_art_found": False,
        "risks_identified": False,
    })

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "findings": [f.to_dict() for f in self.findings],
            "related_entities": self.related_entities,
            "related_features": self.related_features,
            "known_stakeholders": self.known_stakeholders,
            "open_questions": self.open_questions,
            "sources_searched": self.sources_searched,
            "coverage": self.coverage,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DiscoveryResult":
        """Create DiscoveryResult from dictionary."""
        findings = [
            DiscoveryFinding.from_dict(f) for f in data.get("findings", [])
        ]
        return cls(
            findings=findings,
            related_entities=data.get("related_entities", []),
            related_features=data.get("related_features", []),
            known_stakeholders=data.get("known_stakeholders", []),
            open_questions=data.get("open_questions", []),
            sources_searched=data.get("sources_searched", []),
            coverage=data.get("coverage", {
                "brain_entities_found": False,
                "master_sheet_match": False,
                "stakeholders_identified": False,
                "prior_art_found": False,
                "risks_identified": False,
            }),
        )

    def get_findings_by_category(self, category: FindingCategory) -> List[DiscoveryFinding]:
        """Get findings filtered by category."""
        return [f for f in self.findings if f.category == category]

    def get_findings_by_confidence(self, min_confidence: Confidence) -> List[DiscoveryFinding]:
        """Get findings at or above a confidence level."""
        levels = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}
        min_level = levels[min_confidence]
        return [f for f in self.findings if levels[f.confidence] >= min_level]


def _tokenize(text: str) -> Set[str]:
    """
    Tokenize text into lowercase words, removing stopwords.

    Args:
        text: Input text to tokenize

    Returns:
        Set of lowercase word tokens
    """
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "shall",
        "this", "that", "these", "those", "it", "its",
    }
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in stopwords and len(w) > 1}


def _token_overlap(search_tokens: Set[str], candidate_tokens: Set[str]) -> float:
    """
    Calculate what fraction of search tokens appear in candidate tokens.

    Uses coverage ratio (not Jaccard) to handle asymmetric set sizes.

    Args:
        search_tokens: Tokens we're looking for
        candidate_tokens: Tokens from the candidate entity

    Returns:
        Coverage ratio between 0.0 and 1.0
    """
    if not search_tokens or not candidate_tokens:
        return 0.0
    intersection = search_tokens & candidate_tokens
    return len(intersection) / len(search_tokens)


class BrainEntityScanner:
    """
    Scans Brain entities for knowledge related to a feature.

    Searches across the brain directory for entities matching the
    feature title, product, and related terms. Extracts relationships,
    events, and metadata from YAML frontmatter.
    """

    MATCH_THRESHOLD = 0.5
    EXCLUDE_DIRS = {"Inbox", "Archive", "__pycache__"}

    def __init__(self, brain_path: Path):
        self.brain_path = brain_path

    def scan(
        self,
        feature_title: str,
        product_id: str,
        product_name: str = "",
    ) -> List[DiscoveryFinding]:
        """
        Scan Brain entities for relevant knowledge.

        Args:
            feature_title: Feature title to search for
            product_id: Product identifier
            product_name: Human-readable product name

        Returns:
            List of DiscoveryFinding from Brain entities
        """
        findings: List[DiscoveryFinding] = []

        search_tokens = _tokenize(feature_title)
        if product_name:
            search_tokens |= _tokenize(product_name)
        if product_id:
            search_tokens |= _tokenize(product_id.replace("-", " "))

        if not search_tokens:
            logger.warning("No search tokens generated from feature title")
            return findings

        all_files = list(self.brain_path.glob("**/*.md"))
        entity_files = [
            f for f in all_files
            if not any(excluded in f.parts for excluded in self.EXCLUDE_DIRS)
        ]
        logger.debug(
            f"Scanning {len(entity_files)} Brain entity files "
            f"(excluded {len(all_files) - len(entity_files)} from Inbox/Archive)"
        )

        for entity_file in entity_files:
            if entity_file.name == "BRAIN.md":
                continue

            try:
                finding = self._check_entity(entity_file, search_tokens)
                if finding:
                    findings.append(finding)
            except Exception as e:
                logger.debug(f"Error scanning {entity_file}: {e}")
                continue

        logger.debug(f"Brain scan found {len(findings)} relevant entities")
        return findings

    def _check_entity(
        self, entity_file: Path, search_tokens: Set[str]
    ) -> Optional[DiscoveryFinding]:
        """Check a single Brain entity file for relevance."""
        content = entity_file.read_text(errors="replace")

        entity_name = entity_file.stem.replace("_", " ")
        entity_tokens = _tokenize(entity_name)

        name_overlap = _token_overlap(search_tokens, entity_tokens)

        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                body = parts[2]

        body_tokens = _tokenize(body[:2000])
        all_entity_tokens = entity_tokens | body_tokens

        full_overlap = _token_overlap(search_tokens, all_entity_tokens)
        overlap = max(name_overlap, full_overlap)

        if overlap < self.MATCH_THRESHOLD:
            return None

        metadata = self._parse_frontmatter(content)

        entity_confidence = float(metadata.get("$confidence", 0))
        if entity_confidence >= 0.7:
            confidence = Confidence.HIGH
        elif entity_confidence >= 0.4:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW

        entity_type = metadata.get("$type", "unknown")
        category = self._categorize_entity(entity_type, metadata)

        content_parts = []
        if metadata.get("name"):
            content_parts.append(f"Entity: {metadata['name']}")
        content_parts.append(f"Type: {entity_type}")
        content_parts.append(f"Status: {metadata.get('$status', 'unknown')}")

        relationships = metadata.get("$relationships", [])
        if relationships and isinstance(relationships, list):
            rel_summary = []
            for rel in relationships[:5]:
                if isinstance(rel, dict):
                    rel_type = rel.get("type", "")
                    target = rel.get("target", "")
                    if rel_type and target:
                        rel_summary.append(f"{rel_type}: {target}")
            if rel_summary:
                content_parts.append(f"Relationships: {', '.join(rel_summary)}")

        events = metadata.get("$events", [])
        if events and isinstance(events, list):
            recent_events = [
                e for e in events
                if isinstance(e, dict) and e.get("type") == "research_discovery"
            ]
            for event in recent_events[:3]:
                msg = event.get("message", "")
                if msg:
                    content_parts.append(f"Research: {msg[:200]}")

        return DiscoveryFinding(
            title=entity_name,
            content="\n".join(content_parts),
            source_type="brain",
            source_ref=str(entity_file.relative_to(self.brain_path)),
            confidence=confidence,
            category=category,
        )

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from a markdown file."""
        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        try:
            import yaml
            return yaml.safe_load(parts[1]) or {}
        except Exception:
            return {}

    def _categorize_entity(
        self, entity_type: str, metadata: Dict[str, Any]
    ) -> FindingCategory:
        """Determine finding category from entity type."""
        type_map = {
            "person": FindingCategory.STAKEHOLDER,
            "squad": FindingCategory.STAKEHOLDER,
            "project": FindingCategory.PRIOR_ART,
            "system": FindingCategory.TECHNICAL,
            "brand": FindingCategory.PRIOR_ART,
            "experiment": FindingCategory.PRIOR_ART,
        }
        return type_map.get(entity_type, FindingCategory.PRIOR_ART)

    def extract_stakeholders(
        self, findings: List[DiscoveryFinding]
    ) -> List[Dict[str, str]]:
        """Extract stakeholder information from Brain findings."""
        stakeholders = []
        seen_names: Set[str] = set()

        for finding in findings:
            if finding.category == FindingCategory.STAKEHOLDER:
                name = finding.title
                if name not in seen_names:
                    seen_names.add(name)
                    role = "Related"
                    content_lower = finding.content.lower()
                    if "type: person" in content_lower:
                        role = "Team Member"
                    elif "type: squad" in content_lower:
                        role = "Squad"
                    stakeholders.append({"name": name, "role": role})

        return stakeholders


class MasterSheetScanner:
    """
    Scans Master Sheet for features related to the current feature.

    Uses the existing MasterSheetReader to find matching topics,
    extract priority/owner/deadline info, and identify related features.
    """

    def __init__(self):
        self._reader = None

    def _get_reader(self):
        """Lazy-load MasterSheetReader, returning None if unavailable."""
        if self._reader is not None:
            return self._reader

        try:
            from pm_os_cce.tools.documents.master_sheet_reader import MasterSheetReader
            self._reader = MasterSheetReader()
            return self._reader
        except ImportError:
            try:
                from documents.master_sheet_reader import MasterSheetReader
                self._reader = MasterSheetReader()
                return self._reader
            except Exception as e:
                logger.debug(f"MasterSheetReader unavailable: {e}")
                return None

    def scan(
        self,
        feature_title: str,
        product_id: str,
    ) -> List[DiscoveryFinding]:
        """Scan Master Sheet for relevant features."""
        findings: List[DiscoveryFinding] = []
        reader = self._get_reader()

        if not reader:
            logger.debug("Master Sheet reader not available, skipping scan")
            return findings

        try:
            topics = reader.get_topics_for_product(product_id)
            if not topics:
                logger.debug(f"No Master Sheet topics found for {product_id}")
                return findings

            feature_tokens = _tokenize(feature_title)

            for topic in topics:
                topic_tokens = _tokenize(topic.feature)
                overlap = _token_overlap(feature_tokens, topic_tokens)

                if overlap >= 0.2 or topic.feature.lower() == feature_title.lower():
                    content_parts = [
                        f"Feature: {topic.feature}",
                        f"Priority: {topic.priority}",
                        f"Status: {topic.status}",
                    ]
                    if topic.owner:
                        content_parts.append(f"Owner: {topic.owner}")
                    if topic.deadline:
                        content_parts.append(
                            f"Deadline: {topic.deadline.strftime('%Y-%m-%d')}"
                        )
                    if topic.action:
                        content_parts.append(f"Action: {topic.action}")

                    is_exact = topic.feature.lower() == feature_title.lower()

                    findings.append(DiscoveryFinding(
                        title=f"Master Sheet: {topic.feature}",
                        content="\n".join(content_parts),
                        source_type="master_sheet",
                        source_ref=f"row:{topic.row_number}",
                        confidence=Confidence.HIGH if is_exact else Confidence.MEDIUM,
                        category=FindingCategory.PRIOR_ART,
                    ))

        except Exception as e:
            logger.warning(f"Master Sheet scan failed: {e}")

        logger.debug(f"Master Sheet scan found {len(findings)} relevant topics")
        return findings

    def get_related_features(
        self, feature_title: str, product_id: str
    ) -> List[str]:
        """Get names of related features in the same product."""
        reader = self._get_reader()
        if not reader:
            return []

        try:
            topics = reader.get_topics_for_product(product_id)
            feature_tokens = _tokenize(feature_title)
            related = []

            for topic in topics:
                if topic.feature.lower() == feature_title.lower():
                    continue
                topic_tokens = _tokenize(topic.feature)
                overlap = _token_overlap(feature_tokens, topic_tokens)
                if overlap >= 0.1:
                    related.append(topic.feature)

            return related

        except Exception:
            return []


class DailyContextScanner:
    """
    Scans recent daily context files for mentions of a feature topic.

    Searches personal context files from the last 14 days, extracting
    blockers, action items, and decisions that mention the feature or product.
    """

    def __init__(self, user_path: Path):
        self.context_dir = user_path / "personal" / "context"

    def scan(
        self,
        feature_title: str,
        product_id: str,
        product_name: str = "",
        days_back: int = 14,
    ) -> List[DiscoveryFinding]:
        """Scan recent daily context files for relevant mentions."""
        findings: List[DiscoveryFinding] = []

        if not self.context_dir.exists():
            logger.debug(f"Daily context directory not found: {self.context_dir}")
            return findings

        search_terms = _tokenize(feature_title)
        if product_name:
            search_terms |= _tokenize(product_name)
        if product_id:
            search_terms |= _tokenize(product_id.replace("-", " "))

        if not search_terms:
            return findings

        all_files = sorted(self.context_dir.glob("*-context.md"), reverse=True)

        cutoff = datetime.now() - timedelta(days=days_back)
        recent_files = []
        for f in all_files:
            try:
                date_part = f.stem.rsplit("-context", 1)[0]
                date_str = "-".join(date_part.split("-")[:3])
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date >= cutoff:
                    recent_files.append(f)
            except (ValueError, IndexError):
                continue

        logger.debug(f"Scanning {len(recent_files)} daily context files (last {days_back} days)")

        for context_file in recent_files:
            try:
                content = context_file.read_text(errors="replace")
                content_tokens = _tokenize(content[:5000])

                overlap = _token_overlap(search_terms, content_tokens)
                if overlap < 0.3:
                    continue

                extracted = self._extract_relevant_sections(content, search_terms)
                if not extracted:
                    continue

                findings.append(DiscoveryFinding(
                    title=f"Daily Context: {context_file.stem}",
                    content=extracted,
                    source_type="daily_context",
                    source_ref=str(context_file.name),
                    confidence=Confidence.MEDIUM,
                    category=FindingCategory.DECISION,
                ))

            except Exception as e:
                logger.debug(f"Error scanning {context_file}: {e}")
                continue

        logger.debug(f"Daily context scan found {len(findings)} relevant entries")
        return findings

    def _extract_relevant_sections(
        self, content: str, search_terms: Set[str]
    ) -> str:
        """Extract sections mentioning the feature from a daily context file."""
        relevant_lines: List[str] = []
        lines = content.split("\n")

        in_relevant_section = False
        section_buffer: List[str] = []

        for line in lines:
            is_header = line.strip().startswith("#") or line.strip().startswith("**")

            if is_header:
                if in_relevant_section and section_buffer:
                    relevant_lines.extend(section_buffer)
                    relevant_lines.append("")

                line_tokens = _tokenize(line)
                section_overlap = _token_overlap(search_terms, line_tokens)
                in_relevant_section = section_overlap > 0

                action_keywords = {"blocker", "decision", "action", "todo", "risk", "open"}
                if action_keywords & line_tokens:
                    in_relevant_section = True

                section_buffer = [line.strip()] if in_relevant_section else []
            elif in_relevant_section:
                stripped = line.strip()
                if stripped:
                    section_buffer.append(stripped)

        if in_relevant_section and section_buffer:
            relevant_lines.extend(section_buffer)

        return "\n".join(relevant_lines[:30])


class SessionResearchScanner:
    """
    Scans session research findings for product/entity mentions.

    Searches session JSON files for findings that match the feature's
    product or related entities.
    """

    def __init__(self, user_path: Path):
        self.inbox_dir = user_path / "brain" / "Inbox" / "ClaudeSession" / "Raw"

    def scan(
        self,
        feature_title: str,
        product_id: str,
        product_name: str = "",
    ) -> List[DiscoveryFinding]:
        """Scan session research files for relevant findings."""
        findings: List[DiscoveryFinding] = []

        if not self.inbox_dir.exists():
            logger.debug(f"Session inbox not found: {self.inbox_dir}")
            return findings

        search_terms = _tokenize(feature_title)
        if product_name:
            search_terms |= _tokenize(product_name)
        if product_id:
            search_terms |= _tokenize(product_id.replace("-", " "))

        if not search_terms:
            return findings

        session_files = sorted(self.inbox_dir.glob("session_*.json"), reverse=True)
        session_files = session_files[:10]

        logger.debug(f"Scanning {len(session_files)} session research files")

        for session_file in session_files:
            try:
                data = json.loads(session_file.read_text(errors="replace"))
                research_entries = data.get("research", [])

                for entry in research_entries:
                    title = entry.get("title", "")
                    finding_text = entry.get("finding", "")
                    entities = entry.get("entities", [])
                    category_str = entry.get("category", "technical")
                    confidence_str = entry.get("confidence", "medium")

                    entry_tokens = _tokenize(f"{title} {finding_text}")
                    entity_tokens: Set[str] = set()
                    for entity in entities:
                        entity_tokens |= _tokenize(entity.replace("_", " "))

                    combined_tokens = entry_tokens | entity_tokens
                    overlap = _token_overlap(search_terms, combined_tokens)

                    if overlap < 0.3:
                        continue

                    conf_map = {
                        "high": Confidence.HIGH,
                        "medium": Confidence.MEDIUM,
                        "low": Confidence.LOW,
                    }
                    confidence = conf_map.get(confidence_str, Confidence.MEDIUM)

                    cat_map = {
                        "technical": FindingCategory.TECHNICAL,
                        "market": FindingCategory.PRIOR_ART,
                        "competitive": FindingCategory.PRIOR_ART,
                        "internal": FindingCategory.DECISION,
                        "discovery": FindingCategory.PRIOR_ART,
                    }
                    finding_category = cat_map.get(category_str, FindingCategory.PRIOR_ART)

                    content_parts = [f"Title: {title}"]
                    if finding_text:
                        content_parts.append(f"Finding: {finding_text[:500]}")
                    source = entry.get("source", "")
                    if source:
                        content_parts.append(f"Source: {source}")

                    findings.append(DiscoveryFinding(
                        title=f"Session Research: {title[:80]}",
                        content="\n".join(content_parts),
                        source_type="session_research",
                        source_ref=str(session_file.name),
                        confidence=confidence,
                        category=finding_category,
                    ))

            except Exception as e:
                logger.debug(f"Error scanning {session_file}: {e}")
                continue

        logger.debug(f"Session research scan found {len(findings)} relevant findings")
        return findings


class VectorSearchScanner:
    """
    Scans Brain entities using semantic vector similarity.

    Gracefully degrades: if chromadb/sentence-transformers not installed,
    scan() returns an empty list with a warning.
    """

    HIGH_THRESHOLD = 0.8
    MEDIUM_THRESHOLD = 0.6

    def __init__(self, brain_path: Path):
        self.brain_path = brain_path
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """Check if vector search dependencies are installed."""
        if self._available is None:
            self._available = HAS_BRAIN and VECTOR_AVAILABLE
        return self._available

    def scan(
        self,
        feature_title: str,
        product_id: str,
        product_name: str = "",
    ) -> List[DiscoveryFinding]:
        """Scan Brain entities using vector similarity search."""
        if not self.available:
            logger.debug("Vector search unavailable (dependencies not installed)")
            return []

        try:
            index = BrainVectorIndex(self.brain_path)

            query_parts = [feature_title]
            if product_name:
                query_parts.append(product_name)
            elif product_id:
                query_parts.append(product_id.replace("-", " "))
            query_text = " ".join(query_parts)

            results = index.query(query_text, top_k=15)

            findings: List[DiscoveryFinding] = []
            for r in results:
                confidence = self._score_to_confidence(r["score"])
                category = self._categorize_entity_type(
                    r["metadata"].get("entity_type", "unknown")
                )

                findings.append(DiscoveryFinding(
                    title=f"[Vector] {r['metadata'].get('name', r['entity_id'])}",
                    content=(
                        f"Semantic match (score: {r['score']:.3f}) for "
                        f"'{query_text}'. {r.get('snippet', '')}"
                    ),
                    source_type="vector_search",
                    source_ref=r.get("entity_path", r["entity_id"]),
                    confidence=confidence,
                    category=category,
                ))

            logger.debug(f"Vector search found {len(findings)} relevant entities")
            return findings

        except Exception as e:
            logger.warning(f"Vector search scan failed: {e}")
            return []

    def _score_to_confidence(self, score: float) -> Confidence:
        """Map similarity score to Confidence enum."""
        if score >= self.HIGH_THRESHOLD:
            return Confidence.HIGH
        elif score >= self.MEDIUM_THRESHOLD:
            return Confidence.MEDIUM
        return Confidence.LOW

    def _categorize_entity_type(self, entity_type: str) -> FindingCategory:
        """Map entity $type to FindingCategory."""
        type_map = {
            "person": FindingCategory.STAKEHOLDER,
            "squad": FindingCategory.STAKEHOLDER,
            "team": FindingCategory.STAKEHOLDER,
            "system": FindingCategory.TECHNICAL,
            "project": FindingCategory.PRIOR_ART,
            "brand": FindingCategory.PRIOR_ART,
            "experiment": FindingCategory.PRIOR_ART,
            "research": FindingCategory.PRIOR_ART,
            "decision": FindingCategory.DECISION,
        }
        return type_map.get(entity_type.lower(), FindingCategory.PRIOR_ART)


class BrainMCPScanner:
    """
    Scans Brain knowledge via the Brain MCP server (CLI mode).

    Enables remote Brain access -- when brain-mcp server is available,
    discovery can query via MCP protocol instead of direct file reads.
    Falls back gracefully if server is not available.
    """

    def __init__(self, server_path: Optional[Path] = None, brain_path: Optional[Path] = None):
        self.brain_path = brain_path
        if server_path:
            self.server_path = server_path
        else:
            # Auto-resolve via path_resolver
            try:
                paths = get_paths()
                tools_dir = Path(paths.get("tools", ""))
                self.server_path = tools_dir / "mcp" / "brain_mcp" / "server.py"
            except Exception:
                self.server_path = Path("/dev/null")  # Will fail availability check
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """Check if brain-mcp server CLI is accessible."""
        if self._available is None:
            self._available = self.server_path.exists()
        return self._available

    def scan(
        self,
        feature_title: str,
        product_id: str,
        product_name: str = "",
    ) -> List[DiscoveryFinding]:
        """Query Brain via MCP server CLI mode."""
        if not self.available:
            logger.debug("Brain MCP server not available")
            return []

        import subprocess

        query_parts = [feature_title]
        if product_name:
            query_parts.append(product_name)
        elif product_id:
            query_parts.append(product_id.replace("-", " "))
        query_text = " ".join(query_parts)

        try:
            env = dict(os.environ)
            if self.brain_path:
                env["PM_OS_BRAIN_PATH"] = str(self.brain_path)

            result = subprocess.run(
                [sys.executable, str(self.server_path), "--cli",
                 "search_entities", query_text, "--limit", "10"],
                capture_output=True, text=True, timeout=120, env=env,
            )

            if result.returncode != 0 and not result.stdout.strip():
                logger.warning(f"Brain MCP CLI failed: {result.stderr[:200]}")
                return []

            return self._parse_search_output(result.stdout)

        except subprocess.TimeoutExpired:
            logger.warning("Brain MCP CLI timed out")
            return []
        except Exception as e:
            logger.warning(f"Brain MCP scan failed: {e}")
            return []

    def _parse_search_output(self, output: str) -> List[DiscoveryFinding]:
        """Parse search_entities CLI output into DiscoveryFinding objects."""
        findings: List[DiscoveryFinding] = []
        if not output or "No entities found" in output:
            return findings

        blocks = re.split(r"\n\n+", output.strip())

        for block in blocks:
            if block.startswith("Search results"):
                continue

            score_match = re.match(r"\[(\d+\.\d+)\]\s+(.+)", block)
            if not score_match:
                continue

            score = float(score_match.group(1))
            name = score_match.group(2).strip()

            id_match = re.search(r"ID:\s*(\S+)", block)
            entity_id = id_match.group(1) if id_match else name

            type_match = re.search(r"Type:\s*(\w+)", block)
            entity_type = type_match.group(1) if type_match else "unknown"

            snippet_match = re.search(r"Snippet:\s*(.+?)\.{3}$", block, re.MULTILINE)
            snippet = snippet_match.group(1) if snippet_match else ""

            confidence = self._score_to_confidence(score)
            category = self._categorize_entity_type(entity_type)

            findings.append(DiscoveryFinding(
                title=f"[MCP] {name}",
                content=(
                    f"Brain MCP match (score: {score:.3f}) -- "
                    f"{snippet[:200]}"
                ),
                source_type="brain_mcp",
                source_ref=entity_id,
                confidence=confidence,
                category=category,
            ))

        logger.debug(f"Brain MCP scan found {len(findings)} findings")
        return findings

    def _score_to_confidence(self, score: float) -> Confidence:
        """Map similarity score to Confidence enum."""
        if score >= 0.8:
            return Confidence.HIGH
        elif score >= 0.6:
            return Confidence.MEDIUM
        return Confidence.LOW

    def _categorize_entity_type(self, entity_type: str) -> FindingCategory:
        """Map entity type to FindingCategory."""
        type_map = {
            "person": FindingCategory.STAKEHOLDER,
            "squad": FindingCategory.STAKEHOLDER,
            "team": FindingCategory.STAKEHOLDER,
            "system": FindingCategory.TECHNICAL,
            "project": FindingCategory.PRIOR_ART,
            "brand": FindingCategory.PRIOR_ART,
            "experiment": FindingCategory.PRIOR_ART,
            "research": FindingCategory.PRIOR_ART,
            "decision": FindingCategory.DECISION,
        }
        return type_map.get(entity_type.lower(), FindingCategory.PRIOR_ART)


class PatternOutputScanner:
    """
    Scans outputs from pattern commands for discovery evidence.

    Reads previously generated pattern analysis outputs and converts
    their findings into DiscoveryFinding objects for the discovery pipeline.
    """

    PATTERN_CATEGORY_MAP = {
        "analyze-feedback": FindingCategory.PRIOR_ART,
        "analyze-risk": FindingCategory.RISK,
        "analyze-sales-call": FindingCategory.PRIOR_ART,
        "analyze-presentation": FindingCategory.PRIOR_ART,
        "summarize-meeting": FindingCategory.DECISION,
        "create-user-story": FindingCategory.PRIOR_ART,
    }

    def __init__(self, user_path: Path):
        self.user_path = user_path

    def scan(
        self,
        feature_title: str,
        product_id: str,
        product_name: str = "",
    ) -> List[DiscoveryFinding]:
        """Scan session notes for pattern-generated findings."""
        findings: List[DiscoveryFinding] = []
        brain_path = self.user_path / "brain"
        inbox_dir = brain_path / "Inbox" / "ClaudeSession" / "Raw"

        if not inbox_dir.exists():
            return findings

        search_terms = {feature_title.lower()}
        if product_name:
            search_terms.add(product_name.lower())
        if product_id:
            search_terms.add(product_id.replace("-", " ").lower())

        try:
            for json_file in sorted(inbox_dir.glob("session_*.json"), reverse=True)[:14]:
                try:
                    entries = json.loads(json_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, IOError):
                    continue

                for entry in entries:
                    query = entry.get("query", "")
                    if not query or "Pattern:" not in query:
                        continue

                    finding_text = f"{entry.get('title', '')} {entry.get('finding', '')}".lower()
                    if not any(term in finding_text for term in search_terms):
                        continue

                    pattern_name = query.replace("Pattern:", "").strip()
                    category = self.PATTERN_CATEGORY_MAP.get(
                        pattern_name, FindingCategory.PRIOR_ART
                    )

                    findings.append(DiscoveryFinding(
                        title=f"[Pattern] {entry.get('title', 'Unknown')}",
                        content=entry.get("finding", ""),
                        source_type="fabric_pattern",
                        source_ref=f"{pattern_name}:{json_file.name}",
                        confidence=Confidence(entry.get("confidence", "medium")),
                        category=category,
                    ))

        except Exception as e:
            logger.warning(f"Pattern output scan failed: {e}")

        logger.debug(f"Pattern output scan found {len(findings)} findings")
        return findings


class DiscoveryResearcher:
    """
    Orchestrates feature-scoped discovery across PM-OS knowledge sources.

    Runs configured researchers and aggregates results into a single
    DiscoveryResult. Default researchers (Brain + Master Sheet) always run.
    Optional researchers can be enabled with extended=True.

    Usage:
        researcher = DiscoveryResearcher(brain_path=Path("user/brain"))
        result = researcher.run_discovery("Feature Title", "product-id")
    """

    def __init__(self, brain_path: Path, user_path: Optional[Path] = None,
                 mcp_mode: bool = False):
        self.brain_path = brain_path
        self.user_path = user_path or brain_path.parent
        self.brain_scanner = BrainEntityScanner(brain_path)
        self.master_sheet_scanner = MasterSheetScanner()
        self.daily_context_scanner = DailyContextScanner(self.user_path)
        self.session_research_scanner = SessionResearchScanner(self.user_path)
        self.vector_scanner = VectorSearchScanner(brain_path)
        self.pattern_scanner = PatternOutputScanner(self.user_path)
        self.mcp_scanner = BrainMCPScanner(brain_path=brain_path) if mcp_mode else None

    def run_discovery(
        self,
        feature_title: str,
        product_id: str,
        product_name: str = "",
        extended: bool = False,
        rlm: bool = False,
    ) -> DiscoveryResult:
        """
        Run discovery researchers and aggregate results.

        Args:
            feature_title: Feature title to discover knowledge about
            product_id: Product identifier
            product_name: Human-readable product name
            extended: If True, run optional researchers too
            rlm: If True, use RLM decomposition for richer coverage

        Returns:
            DiscoveryResult with aggregated findings
        """
        if rlm:
            return self._run_discovery_rlm(
                feature_title, product_id, product_name, extended
            )
        result = DiscoveryResult()
        all_findings: List[DiscoveryFinding] = []

        # --- Default researcher 1: Brain entity scan ---
        try:
            brain_findings = self.brain_scanner.scan(
                feature_title, product_id, product_name
            )
            all_findings.extend(brain_findings)
            result.sources_searched.append("brain")

            if brain_findings:
                result.coverage["brain_entities_found"] = True
                result.related_entities = [
                    f.source_ref for f in brain_findings
                ]
                result.known_stakeholders = (
                    self.brain_scanner.extract_stakeholders(brain_findings)
                )
                if result.known_stakeholders:
                    result.coverage["stakeholders_identified"] = True

        except Exception as e:
            logger.warning(f"Brain entity scan failed: {e}")

        # --- Default researcher 1b: Vector search scan ---
        try:
            vector_findings = self.vector_scanner.scan(
                feature_title, product_id, product_name
            )
            if vector_findings:
                all_findings.extend(vector_findings)
                result.sources_searched.append("vector_search")
                result.coverage["vector_search_found"] = True
            else:
                result.coverage["vector_search_found"] = False
        except Exception as e:
            logger.warning(f"Vector search scan failed: {e}")
            result.coverage["vector_search_found"] = False

        # --- Optional: Brain MCP scan (remote Brain access) ---
        if self.mcp_scanner and self.mcp_scanner.available:
            try:
                mcp_findings = self.mcp_scanner.scan(
                    feature_title, product_id, product_name
                )
                if mcp_findings:
                    existing_refs = {f.source_ref for f in all_findings}
                    new_findings = [
                        f for f in mcp_findings if f.source_ref not in existing_refs
                    ]
                    all_findings.extend(new_findings)
                    result.sources_searched.append("brain_mcp")
                    result.coverage["brain_mcp_found"] = True
                else:
                    result.coverage["brain_mcp_found"] = False
            except Exception as e:
                logger.warning(f"Brain MCP scan failed: {e}")
                result.coverage["brain_mcp_found"] = False

        # --- Default researcher 2: Master Sheet scan ---
        try:
            ms_findings = self.master_sheet_scanner.scan(
                feature_title, product_id
            )
            all_findings.extend(ms_findings)
            result.sources_searched.append("master_sheet")

            if ms_findings:
                result.coverage["master_sheet_match"] = True

            related = self.master_sheet_scanner.get_related_features(
                feature_title, product_id
            )
            result.related_features = related

        except Exception as e:
            logger.warning(f"Master Sheet scan failed: {e}")

        # --- Optional researcher 3: Daily context scan ---
        if extended:
            try:
                dc_findings = self.daily_context_scanner.scan(
                    feature_title, product_id, product_name
                )
                all_findings.extend(dc_findings)
                result.sources_searched.append("daily_context")
            except Exception as e:
                logger.warning(f"Daily context scan failed: {e}")

        # --- Optional researcher 4: Session research scan ---
        if extended:
            try:
                sr_findings = self.session_research_scanner.scan(
                    feature_title, product_id, product_name
                )
                all_findings.extend(sr_findings)
                result.sources_searched.append("session_research")
            except Exception as e:
                logger.warning(f"Session research scan failed: {e}")

        # --- Optional researcher 5: Pattern output scan ---
        if extended:
            try:
                pattern_findings = self.pattern_scanner.scan(
                    feature_title, product_id, product_name
                )
                if pattern_findings:
                    all_findings.extend(pattern_findings)
                    result.sources_searched.append("fabric_patterns")
                    result.coverage["pattern_evidence_found"] = True
            except Exception as e:
                logger.warning(f"Pattern output scan failed: {e}")

        # --- Aggregate findings ---
        result.findings = all_findings

        for finding in all_findings:
            if finding.category == FindingCategory.PRIOR_ART:
                result.coverage["prior_art_found"] = True
            elif finding.category == FindingCategory.RISK:
                result.coverage["risks_identified"] = True

        if not result.coverage["risks_identified"]:
            result.open_questions.append(
                "No known risks found in Brain or Master Sheet -- "
                "consider identifying risks during context iteration"
            )
        if not result.coverage["stakeholders_identified"]:
            result.open_questions.append(
                "No stakeholders found beyond product config -- "
                "confirm who should be consulted"
            )

        logger.info(
            f"Discovery complete: {len(all_findings)} findings, "
            f"{len(result.related_entities)} related entities, "
            f"coverage: {sum(result.coverage.values())}/{len(result.coverage)}"
        )

        return result

    def _run_discovery_rlm(
        self,
        feature_title: str,
        product_id: str,
        product_name: str,
        extended: bool,
    ) -> DiscoveryResult:
        """
        Run RLM-enhanced discovery with entity-type decomposition.

        Decomposes the feature discovery into per-entity-type subtasks,
        runs focused searches per type, and recomposes into a unified result.
        """
        try:
            from pm_os_cce.tools.reasoning.rlm_engine import RLMEngine, ByEntityType
        except ImportError:
            try:
                from reasoning.rlm_engine import RLMEngine, ByEntityType
            except ImportError:
                logger.warning("RLM engine not available, falling back to standard discovery")
                return self.run_discovery(
                    feature_title, product_id, product_name, extended, rlm=False
                )

        engine = RLMEngine(total_budget=10000)
        strategy = ByEntityType()
        subtasks = strategy.decompose(
            feature_title, feature_title=feature_title
        )
        engine._allocate_budgets(subtasks)

        def context_fn(query: str):
            findings = []
            try:
                brain_findings = self.brain_scanner.scan(
                    query, product_id, product_name
                )
                findings.extend(brain_findings)
            except Exception:
                pass
            try:
                vec_findings = self.vector_scanner.scan(
                    query, product_id, product_name
                )
                findings.extend(vec_findings)
            except Exception:
                pass
            return findings

        subtask_results = engine.execute(subtasks, context_fn=context_fn)
        engine.compose(subtask_results)

        result = DiscoveryResult()
        result.sources_searched.append("rlm_discovery")
        all_findings: List[DiscoveryFinding] = []
        seen_refs: set = set()

        for sr in subtask_results:
            if sr.context_used and isinstance(sr.context_used, list):
                for finding in sr.context_used:
                    if isinstance(finding, DiscoveryFinding):
                        if finding.source_ref not in seen_refs:
                            seen_refs.add(finding.source_ref)
                            all_findings.append(finding)

        result.findings = all_findings
        result.related_entities = [f.source_ref for f in all_findings]
        result.known_stakeholders = self.brain_scanner.extract_stakeholders(
            all_findings
        )

        for finding in all_findings:
            if finding.category == FindingCategory.PRIOR_ART:
                result.coverage["prior_art_found"] = True
            elif finding.category == FindingCategory.RISK:
                result.coverage["risks_identified"] = True
            elif finding.category == FindingCategory.STAKEHOLDER:
                result.coverage["stakeholders_identified"] = True
        if all_findings:
            result.coverage["brain_entities_found"] = True

        if extended:
            standard = self.run_discovery(
                feature_title, product_id, product_name,
                extended=True, rlm=False,
            )
            for f in standard.findings:
                if f.source_ref not in seen_refs:
                    result.findings.append(f)
                    seen_refs.add(f.source_ref)
            result.sources_searched.extend(standard.sources_searched)
            result.related_features = standard.related_features

        logger.info(
            f"RLM discovery complete: {len(result.findings)} findings "
            f"from {len(subtask_results)} subtasks"
        )
        return result
