#!/usr/bin/env python3
"""
Pre-Flight Check Result Data Structures

Follows the pattern from migration/validate.py for consistent result handling.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ToolResult:
    """Result of checking a single tool."""

    tool_name: str
    category: str
    success: bool
    checks_passed: int = 0
    checks_total: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def status(self) -> str:
        """Get status string."""
        if self.success:
            if self.warnings:
                return "PASS_WITH_WARNINGS"
            return "PASS"
        return "FAIL"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "tool_name": self.tool_name,
            "category": self.category,
            "success": self.success,
            "status": self.status,
            "checks_passed": self.checks_passed,
            "checks_total": self.checks_total,
            "errors": self.errors,
            "warnings": self.warnings,
            "skipped": self.skipped,
            "duration_ms": self.duration_ms,
        }


@dataclass
class CategoryResult:
    """Result of checking a category of tools."""

    category: str
    tools: List[ToolResult] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Category passes if all tools pass."""
        return all(t.success for t in self.tools)

    @property
    def passed_count(self) -> int:
        """Number of tools that passed."""
        return sum(1 for t in self.tools if t.success)

    @property
    def total_count(self) -> int:
        """Total number of tools in category."""
        return len(self.tools)

    @property
    def checks_passed(self) -> int:
        """Total checks passed across all tools."""
        return sum(t.checks_passed for t in self.tools)

    @property
    def checks_total(self) -> int:
        """Total checks across all tools."""
        return sum(t.checks_total for t in self.tools)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "category": self.category,
            "success": self.success,
            "passed": self.passed_count,
            "total": self.total_count,
            "tools": [t.to_dict() for t in self.tools],
        }


@dataclass
class PreflightResult:
    """Overall pre-flight check result."""

    success: bool = True
    categories: List[CategoryResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    mode: str = "full"  # full, quick, category

    @property
    def tools_passed(self) -> int:
        """Total tools that passed."""
        return sum(c.passed_count for c in self.categories)

    @property
    def tools_total(self) -> int:
        """Total tools checked."""
        return sum(c.total_count for c in self.categories)

    @property
    def checks_passed(self) -> int:
        """Total individual checks passed."""
        return sum(c.checks_passed for c in self.categories)

    @property
    def checks_total(self) -> int:
        """Total individual checks run."""
        return sum(c.checks_total for c in self.categories)

    @property
    def duration_ms(self) -> float:
        """Total duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0

    @property
    def all_errors(self) -> List[str]:
        """Collect all errors from all tools."""
        errors = []
        for cat in self.categories:
            for tool in cat.tools:
                for err in tool.errors:
                    errors.append(f"[{tool.category}/{tool.tool_name}] {err}")
        return errors

    @property
    def all_warnings(self) -> List[str]:
        """Collect all warnings from all tools."""
        warnings = []
        for cat in self.categories:
            for tool in cat.tools:
                for warn in tool.warnings:
                    warnings.append(f"[{tool.category}/{tool.tool_name}] {warn}")
        return warnings

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON output."""
        return {
            "success": self.success,
            "mode": self.mode,
            "tools_passed": self.tools_passed,
            "tools_total": self.tools_total,
            "checks_passed": self.checks_passed,
            "checks_total": self.checks_total,
            "duration_ms": self.duration_ms,
            "categories": [c.to_dict() for c in self.categories],
            "errors": self.all_errors,
            "warnings": self.all_warnings,
        }
