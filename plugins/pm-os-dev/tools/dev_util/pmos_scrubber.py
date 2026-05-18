"""
PM-OS Dev Scrubber (v5.0)

Sanitize PM-OS codebase for public distribution. Supports scan (dry-run),
scrub (apply replacements), and verify (post-scrub check) modes.

Usage:
    from pm_os_dev.tools.dev_util.pmos_scrubber import ScrubEngine, ScrubConfig

CLI:
    python3 pmos_scrubber.py --scan /path/to/dir --rules scrub_rules.yaml
    python3 pmos_scrubber.py --scrub /path/to/dir --rules scrub_rules.yaml
    python3 pmos_scrubber.py --verify /path/to/dir --rules scrub_rules.yaml
"""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

try:
    from pm_os_base.tools.core.path_resolver import get_paths
except ImportError:
    try:
        from core.path_resolver import get_paths
    except ImportError:
        get_paths = None


@dataclass
class ScrubRule:
    """A single find/replace rule."""

    pattern: str
    replacement: str
    category: str
    case_sensitive: bool = True
    regex: bool = False
    word_boundary: bool = False
    _compiled: Optional[re.Pattern] = field(default=None, repr=False)

    def compile(self):
        if self.regex:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            self._compiled = re.compile(self.pattern, flags)
        elif self.word_boundary:
            escaped = re.escape(self.pattern)
            flags = 0 if self.case_sensitive else re.IGNORECASE
            self._compiled = re.compile(rf"\b{escaped}\b", flags)
        else:
            if self.case_sensitive:
                self._compiled = re.compile(re.escape(self.pattern))
            else:
                self._compiled = re.compile(re.escape(self.pattern), re.IGNORECASE)

    def apply(self, text: str) -> tuple:
        """Apply this rule to text. Returns (new_text, match_count)."""
        if self._compiled is None:
            self.compile()
        new_text, count = self._compiled.subn(self.replacement, text)
        return new_text, count


@dataclass
class VerifyPattern:
    """A detection-only pattern for verify mode."""

    pattern: str
    category: str
    case_insensitive: bool = False
    regex: bool = False
    _compiled: Optional[re.Pattern] = field(default=None, repr=False)

    def compile(self):
        flags = re.IGNORECASE if self.case_insensitive else 0
        if self.regex:
            self._compiled = re.compile(self.pattern, flags)
        else:
            self._compiled = re.compile(re.escape(self.pattern), flags)

    def search(self, text: str) -> list:
        if self._compiled is None:
            self.compile()
        return list(self._compiled.finditer(text))


@dataclass
class ScrubReport:
    """Report from a scan, scrub, or verify operation."""

    mode: str
    directory: str
    files_scanned: int = 0
    files_modified: int = 0
    files_skipped: int = 0
    total_matches: int = 0
    matches_by_category: Dict[str, int] = field(default_factory=dict)
    matches: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[Dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


class ScrubConfig:
    """Load and manage scrubber configuration."""

    def __init__(self, rules_path: str):
        if yaml is None:
            raise ImportError("PyYAML required for scrubber configuration")

        with open(rules_path) as f:
            raw = yaml.safe_load(f)

        self.exclude_paths: List[str] = raw.get("exclude_paths", [])
        self.exclude_extensions: List[str] = raw.get("exclude_extensions", [])
        self.text_extensions: List[str] = raw.get("text_extensions", [])

        # Parse replacement rules
        self.rules: List[ScrubRule] = []
        for r in raw.get("rules", []):
            rule = ScrubRule(
                pattern=r["pattern"],
                replacement=r["replacement"],
                category=r["category"],
                case_sensitive=r.get("case_sensitive", True),
                regex=r.get("regex", False),
                word_boundary=r.get("word_boundary", False),
            )
            rule.compile()
            self.rules.append(rule)

        # Sort: longest plain pattern first
        self.rules.sort(key=lambda r: len(r.pattern) if not r.regex else 0, reverse=True)

        # Parse verify patterns
        self.verify_patterns: List[VerifyPattern] = []
        for vp in raw.get("verify_patterns", []):
            pattern = VerifyPattern(
                pattern=vp["pattern"],
                category=vp["category"],
                case_insensitive=vp.get("case_insensitive", False),
                regex=vp.get("regex", False),
            )
            pattern.compile()
            self.verify_patterns.append(pattern)

    def should_exclude(self, rel_path: str) -> bool:
        for excl in self.exclude_paths:
            if rel_path.startswith(excl) or f"/{excl}" in rel_path:
                return True
        return False

    def is_text_file(self, path: Path) -> bool:
        ext = path.suffix.lower()
        if ext in self.exclude_extensions:
            return False
        if self.text_extensions and ext in self.text_extensions:
            return True
        if not ext:
            return True
        if path.name.endswith(".example"):
            return True
        return ext in self.text_extensions if self.text_extensions else False


class ScrubEngine:
    """Core engine for scanning, scrubbing, and verifying."""

    def __init__(self, config: ScrubConfig):
        self.config = config

    def _collect_files(self, directory: Path) -> List[Path]:
        files = []
        for root, dirs, filenames in os.walk(directory):
            rel_root = os.path.relpath(root, directory)
            if rel_root == ".":
                rel_root = ""

            dirs[:] = [
                d for d in dirs
                if not self.config.should_exclude(
                    os.path.join(rel_root, d) + "/" if rel_root else d + "/"
                )
            ]

            for fname in filenames:
                full_path = Path(root) / fname
                rel_path = os.path.join(rel_root, fname) if rel_root else fname
                if self.config.should_exclude(rel_path):
                    continue
                if self.config.is_text_file(full_path):
                    files.append(full_path)

        return sorted(files)

    def scan(self, directory: str) -> ScrubReport:
        """Dry-run: find all matches without modifying files."""
        report = ScrubReport(mode="scan", directory=directory)
        dir_path = Path(directory)
        files = self._collect_files(dir_path)

        for fpath in files:
            report.files_scanned += 1
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                report.files_skipped += 1
                continue

            lines = content.split("\n")
            file_has_match = False

            for rule in self.config.rules:
                for i, line in enumerate(lines, 1):
                    if rule._compiled and rule._compiled.search(line):
                        report.matches.append({
                            "file": str(fpath.relative_to(dir_path)),
                            "line_num": i,
                            "category": rule.category,
                            "pattern": rule.pattern,
                            "snippet": line.strip()[:120],
                            "replacement": rule.replacement,
                        })
                        report.total_matches += 1
                        report.matches_by_category[rule.category] = (
                            report.matches_by_category.get(rule.category, 0) + 1
                        )
                        file_has_match = True

            if file_has_match:
                report.files_modified += 1

        return report

    def scrub(self, directory: str) -> ScrubReport:
        """Apply all replacements to files in directory."""
        report = ScrubReport(mode="scrub", directory=directory)
        dir_path = Path(directory)
        files = self._collect_files(dir_path)

        for fpath in files:
            report.files_scanned += 1
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                report.files_skipped += 1
                continue

            original = content
            file_matches = 0

            for rule in self.config.rules:
                new_content, count = rule.apply(content)
                if count > 0:
                    old_lines = content.split("\n")
                    new_lines = new_content.split("\n")
                    for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines), 1):
                        if old_line != new_line:
                            report.matches.append({
                                "file": str(fpath.relative_to(dir_path)),
                                "line_num": i,
                                "category": rule.category,
                                "pattern": rule.pattern,
                                "snippet": old_line.strip()[:120],
                                "replacement": rule.replacement,
                            })
                    file_matches += count
                    content = new_content

            if content != original:
                fpath.write_text(content, encoding="utf-8")
                report.files_modified += 1

            report.total_matches += file_matches
            report.matches_by_category = {}
            for m in report.matches:
                cat = m["category"]
                report.matches_by_category[cat] = report.matches_by_category.get(cat, 0) + 1

        return report

    def verify(self, directory: str, strict: bool = False) -> ScrubReport:
        """Post-scrub verification: check for remaining sensitive data."""
        report = ScrubReport(mode="verify", directory=directory)
        dir_path = Path(directory)
        files = self._collect_files(dir_path)

        patterns = list(self.config.verify_patterns)

        if strict:
            for rule in self.config.rules:
                vp = VerifyPattern(
                    pattern=rule.pattern,
                    category=rule.category,
                    case_insensitive=not rule.case_sensitive,
                    regex=rule.regex,
                )
                vp.compile()
                patterns.append(vp)

        for fpath in files:
            report.files_scanned += 1
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                report.files_skipped += 1
                continue

            lines = content.split("\n")
            for vp in patterns:
                for i, line in enumerate(lines, 1):
                    matches = vp.search(line)
                    for _m in matches:
                        report.violations.append({
                            "file": str(fpath.relative_to(dir_path)),
                            "line_num": i,
                            "category": vp.category,
                            "pattern": vp.pattern,
                            "snippet": line.strip()[:120],
                        })
                        report.total_matches += 1
                        report.matches_by_category[vp.category] = (
                            report.matches_by_category.get(vp.category, 0) + 1
                        )

        return report


def main():
    parser = argparse.ArgumentParser(description="PM-OS Scrubber — Sanitize for distribution")
    parser.add_argument("directory", help="Directory to scan/scrub/verify")
    parser.add_argument("--rules", default=str(Path(__file__).parent / "scrub_rules.yaml"))

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--scan", action="store_true")
    mode.add_argument("--scrub", action="store_true")
    mode.add_argument("--verify", action="store_true")

    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--report", help="Write JSON report to file")
    parser.add_argument("--summary", action="store_true")

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.rules):
        print(f"Error: Rules file not found: {args.rules}", file=sys.stderr)
        sys.exit(1)

    config = ScrubConfig(args.rules)
    engine = ScrubEngine(config)

    if args.scan:
        report = engine.scan(args.directory)
        print(f"\nSCAN REPORT: {args.directory}")
        print(f"Files scanned: {report.files_scanned}")
        print(f"Files with matches: {report.files_modified}")
        print(f"Total matches: {report.total_matches}")
        if report.matches_by_category:
            print("\nBy category:")
            for cat, count in sorted(report.matches_by_category.items(), key=lambda x: -x[1]):
                print(f"  {cat:20s} {count:5d}")

    elif args.scrub:
        report = engine.scrub(args.directory)
        print(f"\nSCRUB REPORT: {args.directory}")
        print(f"Files scanned: {report.files_scanned}")
        print(f"Files modified: {report.files_modified}")
        print(f"Total replacements: {report.total_matches}")

    elif args.verify:
        report = engine.verify(args.directory, strict=args.strict)
        violations = report.violations
        print(f"\nVERIFY REPORT: {args.directory}")
        print(f"Files scanned: {report.files_scanned}")
        print(f"Violations: {len(violations)}")

        if violations:
            print(f"\nRESULT: FAIL — {len(violations)} violation(s) found")
            sys.exit(1)
        else:
            print("\nRESULT: PASS — 0 violations")

    if args.report:
        Path(args.report).write_text(report.to_json())
        print(f"\nReport written to: {args.report}")


if __name__ == "__main__":
    main()
