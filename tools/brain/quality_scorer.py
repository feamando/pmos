#!/usr/bin/env python3
"""
PM-OS Brain Quality Scorer

Calculates completeness and quality scores for Brain entities.
"""

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class QualityScore:
    """Quality score breakdown for an entity."""

    entity_id: str
    entity_type: str
    overall_score: float
    completeness_score: float
    freshness_score: float
    relationship_score: float
    source_reliability_score: float
    kappa_score: float = 0.0  # TKS κ - weighted field completeness
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class QualityScorer:
    """
    Calculates quality scores for Brain entities.

    Scoring formula:
    - Completeness: 40% (required + optional fields)
    - Source reliability: 40% (based on data source)
    - Freshness: 20% (decay 0.01/week)
    """

    # Required fields for each entity type
    REQUIRED_FIELDS = {
        "person": ["$type", "$id", "role"],
        "team": ["$type", "$id", "owner"],
        "squad": ["$type", "$id", "owner", "tribe"],
        "project": ["$type", "$id", "owner", "status"],
        "domain": ["$type", "$id", "description"],
        "experiment": ["$type", "$id", "hypothesis", "status"],
        "system": ["$type", "$id", "owner"],
        "brand": ["$type", "$id", "description"],
        "default": ["$type", "$id"],
    }

    # Optional fields that improve completeness (with weights for κ scoring)
    # TKS-derived: weighted field coverage per Def 3.6.1
    OPTIONAL_FIELDS = {
        "person": [
            "team",
            "email",
            "slack_handle",
            "expertise",
            "manager",
            "$relationships",
        ],
        "team": ["description", "members", "mission", "$relationships"],
        "squad": ["description", "members", "mission", "tech_stack", "$relationships"],
        "project": [
            "description",
            "team",
            "start_date",
            "target_date",
            "$relationships",
        ],
        "domain": ["owner", "systems", "$relationships"],
        "experiment": ["owner", "start_date", "end_date", "results", "$relationships"],
        "system": ["description", "tech_stack", "dependencies", "$relationships"],
        "brand": ["owner", "market", "status", "$relationships"],
        "default": ["description", "$relationships"],
    }

    # TKS κ (kappa) field weights - higher = more important for completeness
    # Based on TKS Def 3.6.1: κ(e) ∈ [0,1] with type-specific weights
    FIELD_WEIGHTS = {
        "person": {
            "team": 1.0,  # Critical for org structure
            "manager": 0.9,  # Important for hierarchy
            "email": 0.7,  # Contact info
            "slack_handle": 0.5,  # Secondary contact
            "expertise": 0.8,  # Domain knowledge
            "$relationships": 1.0,  # Graph connectivity
        },
        "team": {
            "description": 0.6,
            "members": 1.0,  # Critical
            "mission": 0.7,
            "$relationships": 0.9,
        },
        "squad": {
            "description": 0.6,
            "members": 1.0,
            "mission": 0.7,
            "tech_stack": 0.5,
            "$relationships": 0.9,
        },
        "project": {
            "description": 0.8,
            "team": 0.9,
            "start_date": 0.6,
            "target_date": 0.7,
            "$relationships": 0.8,
        },
        "domain": {
            "owner": 0.9,
            "systems": 0.7,
            "$relationships": 0.8,
        },
        "experiment": {
            "owner": 0.8,
            "start_date": 0.6,
            "end_date": 0.5,
            "results": 0.9,
            "$relationships": 0.6,
        },
        "system": {
            "description": 0.7,
            "tech_stack": 0.8,
            "dependencies": 0.9,
            "$relationships": 0.8,
        },
        "brand": {
            "owner": 0.8,
            "market": 0.7,
            "status": 0.6,
            "$relationships": 0.7,
        },
        "default": {
            "description": 0.7,
            "$relationships": 0.8,
        },
    }

    # Source reliability scores
    SOURCE_RELIABILITY = {
        "hr_system": 0.95,
        "jira": 0.90,
        "github": 0.85,
        "gdocs": 0.85,
        "confluence": 0.80,
        "slack": 0.65,
        "manual": 0.70,
        "auto": 0.50,
        "unknown": 0.40,
    }

    def __init__(self, brain_path: Path):
        """
        Initialize the quality scorer.

        Args:
            brain_path: Path to the brain directory
        """
        self.brain_path = brain_path

    def score_entity(self, entity_path: Path) -> QualityScore:
        """
        Calculate quality score for a single entity.

        Args:
            entity_path: Path to entity file

        Returns:
            QualityScore with breakdown
        """
        content = entity_path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_content(content)

        entity_id = str(entity_path.relative_to(self.brain_path))
        entity_type = frontmatter.get("$type", "unknown")

        # Calculate component scores
        completeness = self._score_completeness(frontmatter, body, entity_type)
        freshness = self._score_freshness(frontmatter)
        relationships = self._score_relationships(frontmatter)
        source_reliability = self._score_source_reliability(frontmatter)
        kappa = self.compute_kappa(frontmatter, entity_type)

        # Overall score
        overall = completeness * 0.40 + source_reliability * 0.40 + freshness * 0.20

        # Identify issues and recommendations
        issues, recommendations = self._analyze_issues(
            frontmatter, body, entity_type, completeness, freshness
        )

        return QualityScore(
            entity_id=entity_id,
            entity_type=entity_type,
            overall_score=round(overall, 2),
            completeness_score=round(completeness, 2),
            freshness_score=round(freshness, 2),
            relationship_score=round(relationships, 2),
            source_reliability_score=round(source_reliability, 2),
            kappa_score=kappa,
            issues=issues,
            recommendations=recommendations,
        )

    def score_all_entities(
        self,
        entity_type: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> List[QualityScore]:
        """
        Score all entities in the brain.

        Args:
            entity_type: Filter by entity type
            min_score: Only return entities with score >= this value

        Returns:
            List of quality scores
        """
        scores = []

        entity_files = list(self.brain_path.rglob("*.md"))
        entity_files = [
            f
            for f in entity_files
            if f.name.lower() not in ("readme.md", "index.md", "_index.md")
            and ".snapshots" not in str(f)
            and ".schema" not in str(f)
        ]

        for entity_path in entity_files:
            try:
                score = self.score_entity(entity_path)

                if entity_type and score.entity_type != entity_type:
                    continue
                if min_score and score.overall_score < min_score:
                    continue

                scores.append(score)
            except Exception:
                continue

        return sorted(scores, key=lambda s: s.overall_score)

    def get_summary(
        self, scores: Optional[List[QualityScore]] = None
    ) -> Dict[str, Any]:
        """
        Get summary statistics for quality scores.

        Args:
            scores: Pre-computed scores (or will compute all)

        Returns:
            Summary statistics
        """
        if scores is None:
            scores = self.score_all_entities()

        if not scores:
            return {"total": 0}

        total = len(scores)
        avg_overall = sum(s.overall_score for s in scores) / total
        avg_completeness = sum(s.completeness_score for s in scores) / total
        avg_freshness = sum(s.freshness_score for s in scores) / total

        # Score distribution
        excellent = sum(1 for s in scores if s.overall_score >= 0.8)
        good = sum(1 for s in scores if 0.6 <= s.overall_score < 0.8)
        fair = sum(1 for s in scores if 0.4 <= s.overall_score < 0.6)
        poor = sum(1 for s in scores if s.overall_score < 0.4)

        # By type
        by_type: Dict[str, List[float]] = {}
        for score in scores:
            if score.entity_type not in by_type:
                by_type[score.entity_type] = []
            by_type[score.entity_type].append(score.overall_score)

        type_averages = {
            t: round(sum(vals) / len(vals), 2) for t, vals in by_type.items()
        }

        # Common issues
        all_issues: Dict[str, int] = {}
        for score in scores:
            for issue in score.issues:
                all_issues[issue] = all_issues.get(issue, 0) + 1

        top_issues = sorted(all_issues.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total": total,
            "average_overall": round(avg_overall, 2),
            "average_completeness": round(avg_completeness, 2),
            "average_freshness": round(avg_freshness, 2),
            "distribution": {
                "excellent": excellent,
                "good": good,
                "fair": fair,
                "poor": poor,
            },
            "by_type": type_averages,
            "top_issues": top_issues,
        }

    def _score_completeness(
        self, frontmatter: Dict[str, Any], body: str, entity_type: str
    ) -> float:
        """Calculate completeness score using TKS κ (kappa) weighted formula."""
        required = self.REQUIRED_FIELDS.get(
            entity_type, self.REQUIRED_FIELDS["default"]
        )
        optional = self.OPTIONAL_FIELDS.get(
            entity_type, self.OPTIONAL_FIELDS["default"]
        )
        weights = self.FIELD_WEIGHTS.get(entity_type, self.FIELD_WEIGHTS["default"])

        # Required fields score (60% of completeness) - all equal weight
        required_present = sum(
            1 for f in required if f in frontmatter and frontmatter[f]
        )
        required_score = required_present / len(required) if required else 1.0

        # Optional fields score (30% of completeness) - TKS weighted by importance
        # κ formula: Σ(weight[f] * present[f]) / Σ(weight[f])
        weighted_sum = 0.0
        total_weight = 0.0
        for field in optional:
            field_weight = weights.get(field, 0.5)  # Default weight 0.5
            total_weight += field_weight
            if field in frontmatter and frontmatter[field]:
                weighted_sum += field_weight

        optional_score = weighted_sum / total_weight if total_weight > 0 else 0

        # Body content score (10% of completeness)
        body_score = min(len(body.strip()) / 500, 1.0)  # Max at 500 chars

        return required_score * 0.6 + optional_score * 0.3 + body_score * 0.1

    def compute_kappa(self, frontmatter: Dict[str, Any], entity_type: str) -> float:
        """
        Compute TKS κ (kappa) score - pure weighted field coverage.

        κ(e) ∈ [0,1] per TKS Def 3.6.1
        Formula: 0.7 * required_coverage + 0.3 * weighted_optional_coverage

        Args:
            frontmatter: Entity YAML frontmatter
            entity_type: Type of entity

        Returns:
            κ score in [0, 1]
        """
        required = self.REQUIRED_FIELDS.get(
            entity_type, self.REQUIRED_FIELDS["default"]
        )
        optional = self.OPTIONAL_FIELDS.get(
            entity_type, self.OPTIONAL_FIELDS["default"]
        )
        weights = self.FIELD_WEIGHTS.get(entity_type, self.FIELD_WEIGHTS["default"])

        # Required fields coverage
        required_present = sum(
            1 for f in required if f in frontmatter and frontmatter[f]
        )
        required_coverage = required_present / len(required) if required else 1.0

        # Weighted optional fields coverage
        weighted_sum = 0.0
        total_weight = 0.0
        for field in optional:
            field_weight = weights.get(field, 0.5)
            total_weight += field_weight
            if field in frontmatter and frontmatter[field]:
                weighted_sum += field_weight

        optional_coverage = weighted_sum / total_weight if total_weight > 0 else 0

        # κ = 0.7 * required + 0.3 * optional (per TKS spec)
        kappa = 0.7 * required_coverage + 0.3 * optional_coverage
        return round(kappa, 3)

    def _score_freshness(self, frontmatter: Dict[str, Any]) -> float:
        """Calculate freshness score."""
        updated = frontmatter.get("$updated", frontmatter.get("updated", ""))

        if not updated:
            return 0.5  # Unknown freshness

        try:
            if isinstance(updated, str):
                updated_dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            else:
                return 0.5

            days_old = (datetime.now(updated_dt.tzinfo) - updated_dt).days
            weeks_old = days_old / 7

            # Decay 0.01 per week, max 0.2 decay
            decay = min(weeks_old * 0.01, 0.2)
            return max(0, 1.0 - decay)

        except (ValueError, TypeError):
            return 0.5

    def _score_relationships(self, frontmatter: Dict[str, Any]) -> float:
        """Calculate relationship score."""
        relationships = frontmatter.get("$relationships", [])

        if not relationships:
            return 0.3  # No relationships defined

        # Score based on number and diversity of relationships
        count = len(relationships)
        types = set(r.get("type", "") for r in relationships if isinstance(r, dict))

        count_score = min(count / 5, 1.0)  # Max at 5 relationships
        diversity_score = min(len(types) / 3, 1.0)  # Max at 3 types

        return count_score * 0.6 + diversity_score * 0.4

    def _score_source_reliability(self, frontmatter: Dict[str, Any]) -> float:
        """Calculate source reliability score."""
        source = frontmatter.get("$source", "unknown")

        # Check for specific source patterns
        source_lower = source.lower()
        for source_key, reliability in self.SOURCE_RELIABILITY.items():
            if source_key in source_lower:
                return reliability

        return self.SOURCE_RELIABILITY["unknown"]

    def _analyze_issues(
        self,
        frontmatter: Dict[str, Any],
        body: str,
        entity_type: str,
        completeness: float,
        freshness: float,
    ) -> Tuple[List[str], List[str]]:
        """Identify issues and generate recommendations."""
        issues = []
        recommendations = []

        # Check required fields
        required = self.REQUIRED_FIELDS.get(
            entity_type, self.REQUIRED_FIELDS["default"]
        )
        for field in required:
            if field not in frontmatter or not frontmatter[field]:
                issues.append(f"Missing required field: {field}")
                recommendations.append(f"Add {field} to improve completeness")

        # Check freshness
        if freshness < 0.5:
            issues.append("Entity may be stale (not updated recently)")
            recommendations.append("Review and update entity information")

        # Check relationships
        if "$relationships" not in frontmatter or not frontmatter["$relationships"]:
            issues.append("No relationships defined")
            recommendations.append("Add relationships to connect entity to others")

        # Check body content
        if len(body.strip()) < 100:
            issues.append("Minimal body content")
            recommendations.append("Add descriptive content to body section")

        # Check for v2 schema
        if "$schema" not in frontmatter:
            issues.append("Not using v2 schema")
            recommendations.append("Migrate to v2 schema format")

        # Check confidence
        confidence = frontmatter.get("$confidence", 0)
        if confidence < 0.5:
            issues.append(f"Low confidence score ({confidence})")
            recommendations.append("Enrich from authoritative sources")

        return issues, recommendations

    def _parse_content(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse frontmatter and body from content."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        try:
            frontmatter = yaml.safe_load(parts[1]) or {}
            return frontmatter, parts[2]
        except yaml.YAMLError:
            return {}, content


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Score Brain entity quality")
    parser.add_argument(
        "action",
        choices=["score", "summary", "report"],
        help="Action to perform",
    )
    parser.add_argument(
        "--brain-path",
        type=Path,
        help="Path to brain directory",
    )
    parser.add_argument(
        "--entity",
        type=Path,
        help="Specific entity to score",
    )
    parser.add_argument(
        "--type",
        type=str,
        help="Filter by entity type",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        help="Minimum score threshold",
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    # Default brain path
    if not args.brain_path:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from path_resolver import get_paths

        paths = get_paths()
        args.brain_path = paths.user / "brain"

    scorer = QualityScorer(args.brain_path)

    if args.action == "score":
        if args.entity:
            score = scorer.score_entity(args.entity)
            print(f"Entity: {score.entity_id}")
            print(f"Type: {score.entity_type}")
            print(f"Overall: {score.overall_score}")
            print(f"Completeness: {score.completeness_score}")
            print(f"Freshness: {score.freshness_score}")
            print(f"Relationships: {score.relationship_score}")
            if score.issues:
                print(f"Issues: {', '.join(score.issues)}")
        else:
            scores = scorer.score_all_entities(
                entity_type=args.type,
                min_score=args.min_score,
            )
            for s in scores[:20]:
                print(f"{s.overall_score:.2f} | {s.entity_type:10} | {s.entity_id}")

    elif args.action == "summary":
        summary = scorer.get_summary()
        print(f"Total entities: {summary['total']}")
        print(f"Average score: {summary['average_overall']}")
        print(f"Distribution: {summary['distribution']}")
        print(f"By type: {summary['by_type']}")

    elif args.action == "report":
        scores = scorer.score_all_entities()
        summary = scorer.get_summary(scores)

        print("Brain Quality Report")
        print("=" * 60)
        print(f"Total entities: {summary['total']}")
        print(f"Average quality: {summary['average_overall']}/1.0")
        print()
        print("Distribution:")
        for level, count in summary["distribution"].items():
            pct = count / summary["total"] * 100
            print(f"  {level}: {count} ({pct:.1f}%)")
        print()
        print("Top issues:")
        for issue, count in summary["top_issues"][:5]:
            print(f"  - {issue}: {count} entities")

    return 0


if __name__ == "__main__":
    sys.exit(main())
