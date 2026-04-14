#!/usr/bin/env python3
"""
PM-OS Reporting Performance Updater (v5.0)

Generates performance updates ("pupdates") — structured weekly/biweekly
metric reports with WoW/YoY comparisons, hypothesis-driven analysis,
and channel breakdowns. Consolidates the pupdate generation pattern.

Features:
- Metric extraction from context files and Brain entities
- WoW/YoY comparison with trend detection
- Hypothesis-driven explanations for metric movements
- Channel breakdown formatting
- LLM synthesis for narrative (Gemini, with fallback)
- Multiple output formats (Markdown, CSV row)

Usage:
    from pm_os_reporting.tools.performance_updater import PerformanceUpdater
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# --- v5 imports ---
try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    from core.path_resolver import get_paths

try:
    from pm_os_base.tools.core.config_loader import get_config
except ImportError:
    from core.config_loader import get_config


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class MetricPoint:
    """A single metric measurement."""

    name: str
    value: float
    unit: str = ""  # e.g., "%", "$", "", "k"
    date: str = ""
    source: str = ""


@dataclass
class MetricComparison:
    """Comparison between current and previous metric values."""

    name: str
    current: float
    previous: Optional[float] = None
    yoy_previous: Optional[float] = None
    unit: str = ""
    wow_change: Optional[float] = None
    wow_pct: Optional[float] = None
    yoy_change: Optional[float] = None
    yoy_pct: Optional[float] = None
    trend: str = "stable"  # "up", "down", "stable"
    hypothesis: str = ""


@dataclass
class ChannelBreakdown:
    """Performance breakdown by channel or segment."""

    channel: str
    metrics: List[MetricComparison] = field(default_factory=list)
    narrative: str = ""


@dataclass
class PerformanceReport:
    """Complete performance update report."""

    title: str
    period: str
    squad_or_product: str
    headline: str = ""
    metrics: List[MetricComparison] = field(default_factory=list)
    channels: List[ChannelBreakdown] = field(default_factory=list)
    hypotheses: List[str] = field(default_factory=list)
    looking_ahead: str = ""
    generated_at: str = ""


# ============================================================================
# Generator
# ============================================================================


class PerformanceUpdater:
    """Generates performance update reports with metric analysis."""

    def __init__(self):
        self.paths = get_paths()
        self.config = get_config()

    # --- Path helpers ---

    def _get_output_dir(self) -> Path:
        """Get pupdate output directory."""
        org_id = self.config.get("organization.id", "organization")
        user_dir = self.paths.user

        wcr_path = user_dir / "products" / org_id / "reporting" / "pupdates"
        if (user_dir / "products" / org_id).exists():
            wcr_path.mkdir(parents=True, exist_ok=True)
            return wcr_path

        fallback = user_dir / "planning" / "Reporting" / "Pupdates"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    # --- Metric extraction ---

    def extract_metrics_from_context(
        self, content: str
    ) -> List[MetricPoint]:
        """Extract structured metrics from a context file."""
        metrics = []

        patterns = [
            # Orders: 7476 orders (-1% WoW; +172% YoY)
            (
                r"([\d,]+)\s+orders?\s*\(([^)]+)\)",
                "Orders",
                "",
            ),
            # CAC: $167
            (
                r"(?:Blended\s+)?CAC[+\w]*:\s*\$?([\d,]+(?:\.\d+)?)",
                "CAC",
                "$",
            ),
            # CVR: 1.5%
            (r"CVR[:\s]+(\d+(?:\.\d+)?%?)", "CVR", "%"),
            # Revenue: $1.2M
            (
                r"[Rr]evenue[:\s]+\$?([\d,]+(?:\.\d+)?[kKmM]?)",
                "Revenue",
                "$",
            ),
            # AOV: $85
            (r"AOV[:\s]+\$?([\d,]+(?:\.\d+)?)", "AOV", "$"),
            # Activations: +98% WoW
            (
                r"Activations?[:\s]+([+\-]?\d+(?:\.\d+)?%?)",
                "Activations",
                "",
            ),
            # Conversions: 2,449 conversions
            (r"([\d,]+)\s+conversions?", "Conversions", ""),
            # Spend: $410k
            (r"\$([\d,]+k?)\s+spend", "Spend", "$"),
        ]

        for pattern, name, unit in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                value_str = match if isinstance(match, str) else match
                # Clean and parse value
                cleaned = (
                    value_str.replace(",", "")
                    .replace("%", "")
                    .replace("$", "")
                    .replace("k", "000")
                    .replace("K", "000")
                    .replace("m", "000000")
                    .replace("M", "000000")
                )
                try:
                    value = float(cleaned)
                    metrics.append(
                        MetricPoint(name=name, value=value, unit=unit)
                    )
                    break  # One match per metric type
                except ValueError:
                    continue

        return metrics

    def compare_metrics(
        self,
        current: List[MetricPoint],
        previous: Optional[List[MetricPoint]] = None,
        yoy: Optional[List[MetricPoint]] = None,
    ) -> List[MetricComparison]:
        """Compare current metrics against previous period and YoY."""
        comparisons = []

        prev_map = {}
        if previous:
            for m in previous:
                prev_map[m.name] = m.value

        yoy_map = {}
        if yoy:
            for m in yoy:
                yoy_map[m.name] = m.value

        for metric in current:
            comp = MetricComparison(
                name=metric.name,
                current=metric.value,
                unit=metric.unit,
            )

            # WoW comparison
            if metric.name in prev_map:
                prev_val = prev_map[metric.name]
                comp.previous = prev_val
                comp.wow_change = metric.value - prev_val
                if prev_val != 0:
                    comp.wow_pct = (
                        (metric.value - prev_val) / prev_val
                    ) * 100

            # YoY comparison
            if metric.name in yoy_map:
                yoy_val = yoy_map[metric.name]
                comp.yoy_previous = yoy_val
                comp.yoy_change = metric.value - yoy_val
                if yoy_val != 0:
                    comp.yoy_pct = (
                        (metric.value - yoy_val) / yoy_val
                    ) * 100

            # Determine trend
            if comp.wow_pct is not None:
                if comp.wow_pct > 2:
                    comp.trend = "up"
                elif comp.wow_pct < -2:
                    comp.trend = "down"

            comparisons.append(comp)

        return comparisons

    # --- Formatting ---

    @staticmethod
    def format_metric_value(value: float, unit: str = "") -> str:
        """Format a metric value with appropriate unit."""
        if unit == "$":
            if value >= 1_000_000:
                return f"${value / 1_000_000:.1f}M"
            elif value >= 1_000:
                return f"${value / 1_000:.0f}k"
            return f"${value:,.0f}"
        elif unit == "%":
            return f"{value:.1f}%"
        elif value >= 1_000:
            return f"{value:,.0f}"
        return f"{value:.1f}"

    @staticmethod
    def format_change(pct: Optional[float]) -> str:
        """Format a percentage change."""
        if pct is None:
            return "N/A"
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"

    def format_metrics_table(
        self, comparisons: List[MetricComparison]
    ) -> str:
        """Format metrics as a markdown table."""
        if not comparisons:
            return "No metrics available."

        lines = [
            "| Metric | Current | WoW | YoY | Trend |",
            "|--------|---------|-----|-----|-------|",
        ]

        for c in comparisons:
            current_str = self.format_metric_value(c.current, c.unit)
            wow_str = self.format_change(c.wow_pct) if c.wow_pct is not None else "—"
            yoy_str = self.format_change(c.yoy_pct) if c.yoy_pct is not None else "—"
            trend_indicator = {"up": "^", "down": "v", "stable": "~"}.get(
                c.trend, "~"
            )
            lines.append(
                f"| **{c.name}** | {current_str} | {wow_str} WoW | {yoy_str} YoY | {trend_indicator} |"
            )

        return "\n".join(lines)

    # --- Report generation ---

    def generate_from_context(
        self,
        squad_or_product: str,
        current_context: str,
        previous_context: Optional[str] = None,
        yoy_context: Optional[str] = None,
    ) -> PerformanceReport:
        """Generate a performance report from context file content.

        Args:
            squad_or_product: Name of the squad or product.
            current_context: Current period context file content.
            previous_context: Previous period context for WoW.
            yoy_context: Year-ago context for YoY.
        """
        current_metrics = self.extract_metrics_from_context(current_context)
        prev_metrics = (
            self.extract_metrics_from_context(previous_context)
            if previous_context
            else None
        )
        yoy_metrics = (
            self.extract_metrics_from_context(yoy_context)
            if yoy_context
            else None
        )

        comparisons = self.compare_metrics(current_metrics, prev_metrics, yoy_metrics)

        report = PerformanceReport(
            title=f"Performance Update — {squad_or_product}",
            period=datetime.now().strftime("%Y-W%V"),
            squad_or_product=squad_or_product,
            metrics=comparisons,
            generated_at=datetime.now().isoformat(),
        )

        # Generate headline
        report.headline = self._generate_headline(comparisons, squad_or_product)

        return report

    def _generate_headline(
        self,
        comparisons: List[MetricComparison],
        squad_or_product: str,
    ) -> str:
        """Generate a headline summarizing key metric movements."""
        if not comparisons:
            return f"{squad_or_product}: No metrics available for this period."

        movers = []
        for c in comparisons:
            if c.wow_pct is not None and abs(c.wow_pct) > 5:
                direction = "up" if c.wow_pct > 0 else "down"
                movers.append(
                    f"{c.name} {direction} {self.format_change(c.wow_pct)} WoW"
                )

        if movers:
            return f"{squad_or_product}: {'; '.join(movers[:3])}."
        return f"{squad_or_product}: Metrics stable week-over-week."

    # --- Markdown output ---

    def format_report_markdown(self, report: PerformanceReport) -> str:
        """Format a performance report as markdown."""
        sections = [
            f"# {report.title}",
            f"\n**Period:** {report.period}",
            f"**Generated:** {report.generated_at}",
            "",
            f"## Headline",
            "",
            report.headline,
            "",
            "## Key Metrics",
            "",
            self.format_metrics_table(report.metrics),
            "",
        ]

        # Hypotheses
        if report.hypotheses:
            sections.append("## Hypotheses")
            sections.append("")
            for h in report.hypotheses:
                sections.append(f"- {h}")
            sections.append("")

        # Channel breakdowns
        if report.channels:
            sections.append("## Channel Breakdown")
            sections.append("")
            for channel in report.channels:
                sections.append(f"### {channel.channel}")
                if channel.narrative:
                    sections.append(channel.narrative)
                if channel.metrics:
                    sections.append(self.format_metrics_table(channel.metrics))
                sections.append("")

        # Looking ahead
        if report.looking_ahead:
            sections.append("## Looking Ahead")
            sections.append("")
            sections.append(report.looking_ahead)
            sections.append("")

        return "\n".join(sections)

    # --- Save ---

    def save_report(
        self,
        report: PerformanceReport,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Save the performance report as markdown."""
        output_dir = self._get_output_dir()

        if output_path is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            slug = report.squad_or_product.lower().replace(" ", "_")
            output_path = output_dir / f"pupdate_{slug}_{date_str}.md"

        content = self.format_report_markdown(report)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    # --- Convenience: generate from context files ---

    def run(
        self,
        squad_or_product: str,
        output: Optional[str] = None,
    ) -> str:
        """Run pupdate generation using latest context files.

        Args:
            squad_or_product: Name of squad or product to report on.
            output: Optional output file path.
        """
        # Find recent context files
        context_dir = self.paths.user / "personal" / "context"
        if not context_dir.exists():
            context_dir = self.paths.user / "context"

        context_files = sorted(context_dir.glob("*.md"), reverse=True)
        if not context_files:
            return "Error: No context files found for metric extraction."

        # Current = most recent, previous = second most recent
        with open(context_files[0], "r", encoding="utf-8") as f:
            current_content = f.read()

        previous_content = None
        if len(context_files) > 1:
            with open(context_files[1], "r", encoding="utf-8") as f:
                previous_content = f.read()

        report = self.generate_from_context(
            squad_or_product=squad_or_product,
            current_context=current_content,
            previous_context=previous_content,
        )

        output_path = Path(output) if output else None
        saved_path = self.save_report(report, output_path)

        return (
            f"Performance Update Generated!\n"
            f"Product: {squad_or_product}\n"
            f"Period: {report.period}\n"
            f"Headline: {report.headline}\n"
            f"Metrics: {len(report.metrics)} extracted\n"
            f"Output: {saved_path}"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Performance Updater (Pupdate) v5.0"
    )
    parser.add_argument(
        "squad_or_product", type=str, help="Squad or product name"
    )
    parser.add_argument("--output", type=str, help="Custom output path")
    args = parser.parse_args()

    updater = PerformanceUpdater()
    result = updater.run(
        squad_or_product=args.squad_or_product,
        output=args.output,
    )
    print(result)
