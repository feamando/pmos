#!/usr/bin/env python3
"""
PM-OS Feature Index Generator

Scans user/products/ folder structure, captures context file metadata for all
features currently being worked on, and generates a compressed FEATURES.md index
for agent context loading.

Output: pipe-delimited compressed index with:
  - Product-level entries with status, owner, priority
  - Feature-level entries nested under products
  - Active features highlighted, archived/completed dimmed

Usage:
    python3 feature_index_generator.py                      # Generate to default path
    python3 feature_index_generator.py --output PATH        # Custom output path
    python3 feature_index_generator.py --products-path PATH # Custom products directory
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.config_loader import get_config, get_root_path
except ImportError:
    try:
        _PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(_PLUGIN_ROOT.parent / "pm-os-base" / "tools" / "core"))
        from config_loader import get_config, get_root_path
    except ImportError:
        get_config = None
        get_root_path = None


def _get_root_path() -> Path:
    """Resolve PM-OS root path."""
    if get_root_path:
        return get_root_path()
    # Fallback
    return Path.home() / "pm-os"


def parse_context_header(filepath: Path) -> Dict[str, str]:
    """Parse the header metadata from a feature context file.

    Context files have a simple key-value header:
        **Key:** Value
    """
    metadata: Dict[str, str] = {}
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return metadata

    # Extract title from H1
    title_match = re.match(r"^#\s+(.+)", content)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    # Extract **Key:** Value pairs from header
    for match in re.finditer(r"\*\*(\w[\w\s]*?):\*\*\s*(.+)", content):
        key = match.group(1).strip().lower().replace(" ", "_")
        value = match.group(2).strip()
        metadata[key] = value

    # Extract description if present
    desc_match = re.search(r"## Description\s*\n+(.+?)(?:\n\n|\n##)", content, re.DOTALL)
    if desc_match:
        desc = desc_match.group(1).strip()
        if desc and not desc.startswith("*Feature context"):
            metadata["description"] = desc[:200]

    # Count action log entries and extract latest
    action_rows = re.findall(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+)\|\s*([^|]+)\|[^|]*\|[^|]*\|$", content, re.MULTILINE)
    if action_rows:
        metadata["action_count"] = str(len(action_rows))
        # Latest action is the first row (most recent date at top)
        latest = action_rows[0]
        metadata["latest_action_date"] = latest[0].strip()
        metadata["latest_action_text"] = latest[1].strip()
        metadata["latest_action_status"] = latest[2].strip()
    else:
        # Fallback: count pipe-delimited rows
        action_count = len(re.findall(r"^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|$", content, re.MULTILINE)) - 1
        if action_count > 0:
            metadata["action_count"] = str(action_count)

    return metadata


def scan_products(products_path: Path) -> List[Dict[str, Any]]:
    """Scan products directory and build feature hierarchy."""
    if not products_path.exists():
        return []

    products: List[Dict[str, Any]] = []

    # Walk top-level org folders (e.g., new-ventures/)
    for org_dir in sorted(products_path.iterdir()):
        if not org_dir.is_dir() or org_dir.name.startswith("."):
            continue

        # Walk product folders within org
        for product_dir in sorted(org_dir.iterdir()):
            if not product_dir.is_dir() or product_dir.name.startswith("."):
                continue

            product_context = product_dir / f"{product_dir.name}-context.md"
            product_meta = parse_context_header(product_context) if product_context.exists() else {}

            features: List[Dict[str, Any]] = []

            # Walk feature folders within product
            for feature_dir in sorted(product_dir.iterdir()):
                if not feature_dir.is_dir() or feature_dir.name.startswith("."):
                    continue
                # Skip standard subfolders
                if feature_dir.name in ("discovery", "planning", "execution", "reporting", "presentations", "discussions", "specs"):
                    continue

                feature_context = feature_dir / f"{feature_dir.name}-context.md"
                if feature_context.exists():
                    feature_meta = parse_context_header(feature_context)
                    features.append({
                        "id": feature_dir.name,
                        "path": str(feature_dir.relative_to(products_path)),
                        "meta": feature_meta,
                    })

            products.append({
                "id": product_dir.name,
                "org": org_dir.name,
                "path": str(product_dir.relative_to(products_path)),
                "meta": product_meta,
                "features": features,
            })

    return products


def generate_features_md(products: List[Dict[str, Any]], generated_at: str) -> str:
    """Generate compressed FEATURES.md index."""
    lines: List[str] = []
    lines.append(f"# Feature Index")
    lines.append(f"")
    lines.append(f"Generated: {generated_at}")
    lines.append(f"")

    total_products = len(products)
    total_features = sum(len(p["features"]) for p in products)
    active_features = sum(
        1 for p in products for f in p["features"]
        if f["meta"].get("status", "").lower() in ("in progress", "active", "discovery", "planning")
    )

    lines.append(f"Products: {total_products} | Features: {total_features} | Active: {active_features}")
    lines.append(f"")
    lines.append(f"---")

    for product in products:
        pm = product["meta"]
        status = pm.get("status", "-")
        owner = pm.get("owner", "-")
        title = pm.get("title", product["id"].replace("-", " ").title())

        lines.append(f"")
        lines.append(f"## {title}")
        lines.append(f"ID: {product['id']} | Org: {product['org']} | Status: {status} | Owner: {owner}")

        if product["features"]:
            lines.append(f"")
            lines.append(f"| Feature | Status | Owner | Priority | Last Updated |")
            lines.append(f"|---------|--------|-------|----------|--------------|")

            for feat in product["features"]:
                fm = feat["meta"]
                f_name = fm.get("title", feat["id"].replace("-", " ").title())
                f_status = fm.get("status", "-")
                f_owner = fm.get("owner", "-")
                f_priority = fm.get("priority", "-")
                f_updated = fm.get("last_updated", "-")
                lines.append(f"| {f_name} | {f_status} | {f_owner} | {f_priority} | {f_updated} |")
        else:
            lines.append(f"No tracked features.")

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*Auto-generated by feature_index_generator.py*")

    return "\n".join(lines)


def generate_features_json(products: List[Dict[str, Any]], generated_at: str) -> str:
    """Generate JSON output with full feature metadata."""
    total_features = sum(len(p["features"]) for p in products)
    active_features = sum(
        1 for p in products for f in p["features"]
        if f["meta"].get("status", "").lower() in ("in progress", "active", "discovery", "planning")
    )

    def build_feature(f: Dict[str, Any]) -> Dict[str, Any]:
        fm = f["meta"]
        latest_action = None
        if fm.get("latest_action_date"):
            latest_action = {
                "date": fm["latest_action_date"],
                "action": fm.get("latest_action_text", ""),
                "status": fm.get("latest_action_status", ""),
            }
        return {
            "id": f["id"],
            "name": fm.get("title", f["id"].replace("-", " ").title()),
            "path": f["path"],
            "meta": {
                "title": fm.get("title", f["id"].replace("-", " ").title()),
                "status": fm.get("status", ""),
                "owner": fm.get("owner"),
                "priority": fm.get("priority"),
                "deadline": fm.get("deadline"),
                "last_updated": fm.get("last_updated"),
                "description": fm.get("description"),
                "action_count": int(fm.get("action_count", 0)),
                "latest_action": latest_action,
            },
        }

    def build_product(p: Dict[str, Any]) -> Dict[str, Any]:
        pm = p["meta"]
        return {
            "id": p["id"],
            "name": pm.get("title", p["id"].replace("-", " ").title()),
            "org": p["org"],
            "path": p["path"],
            "meta": {
                "status": pm.get("status"),
                "owner": pm.get("owner"),
                "type": pm.get("type"),
                "last_updated": pm.get("last_updated"),
            },
            "features": [build_feature(f) for f in p["features"]],
        }

    output = {
        "generated_at": generated_at,
        "summary": {
            "products": len(products),
            "features": total_features,
            "active": active_features,
        },
        "products": [build_product(p) for p in products],
    }
    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Generate FEATURES.md index")
    parser.add_argument("--output", type=str, help="Output file path")
    parser.add_argument("--products-path", type=str, help="Products directory path")
    parser.add_argument("--format", type=str, choices=["md", "json"], default="md",
                        help="Output format: md (default) or json")
    args = parser.parse_args()

    root = _get_root_path()
    products_path = Path(args.products_path) if args.products_path else root / "user" / "products"

    if not products_path.exists():
        print(f"Products directory not found: {products_path}", file=sys.stderr)
        sys.exit(1)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    products = scan_products(products_path)

    if args.format == "json":
        content = generate_features_json(products, generated_at)
        if args.output:
            Path(args.output).write_text(content, encoding="utf-8")
        else:
            print(content)
    else:
        output_path = Path(args.output) if args.output else root / "user" / "FEATURES.md"
        content = generate_features_md(products, generated_at)
        output_path.write_text(content, encoding="utf-8")
        print(f"Feature index generated: {output_path} ({len(products)} products, "
              f"{sum(len(p['features']) for p in products)} features)")


if __name__ == "__main__":
    main()
