#!/usr/bin/env python3
"""
PM-OS Path Router

Centralized path resolution for the workflow-centric workspace.
Tools use this to determine where files should be written.

Usage:
    from workspace.path_router import PathRouter

    router = PathRouter()
    path = router.get_sprint_report_path()
    path = router.get_meeting_prep_path(meeting_type='1on1', attendees=['email@...'])
    path = router.get_career_planning_path(person_id='alice-engineer')

Author: PM-OS Team
Version: 1.0.0
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config_loader


class PathRouter:
    """Routes files to correct workspace locations."""

    def __init__(self, user_path: Optional[Path] = None):
        """Initialize path router."""
        config = config_loader.get_config()
        self.user_path = (
            user_path or config.user_path or Path(os.environ.get("PM_OS_USER", ""))
        )

        # Core paths
        self.products_path = self.user_path / "products"
        self.team_path = self.user_path / "team"
        self.personal_path = self.user_path / "personal"
        self.planning_path = self.user_path / "planning"  # Legacy

    def _get_org_id(self) -> Optional[str]:
        """Get organization ID from config."""
        org_config = config_loader.get_organization_config()
        return org_config.get("id") if org_config else None

    def get_product_path(self, product_id: str) -> Path:
        """Get path for a specific product."""
        org_id = self._get_org_id()
        if org_id:
            return self.products_path / org_id / product_id
        return self.products_path / product_id

    def get_sprint_report_path(self, product_id: Optional[str] = None) -> Path:
        """
        Get path for sprint reports.

        Args:
            product_id: If specified, route to that product. Otherwise use org-level.

        Returns:
            Path to sprint-reports folder.
        """
        org_id = self._get_org_id()

        if product_id:
            base = self.get_product_path(product_id)
        elif org_id:
            base = self.products_path / org_id
        else:
            # Fallback to legacy
            return self.planning_path / "Reporting" / "Sprint_Reports"

        path = base / "reporting" / "sprint-reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_meeting_prep_path(
        self,
        meeting_type: str = "other",
        attendees: Optional[List[str]] = None,
        meeting_title: Optional[str] = None,
    ) -> Path:
        """
        Get path for meeting prep files.

        Args:
            meeting_type: Type of meeting (1on1, standup, planning, etc.)
            attendees: List of attendee emails
            meeting_title: Meeting title for product matching

        Returns:
            Path to appropriate discussions/1on1s folder.
        """
        attendees = attendees or []

        # Get user email
        try:
            user_email = config_loader.get_user_email().lower()
        except:
            user_email = ""

        # Filter out user from attendees
        other_attendees = [a.lower() for a in attendees if a.lower() != user_email]

        # 1:1 routing
        if meeting_type == "1on1" and len(other_attendees) == 1:
            other_email = other_attendees[0]

            # Check direct report
            report = config_loader.get_report_by_email(other_email)
            if report:
                path = self.team_path / "reports" / report["id"] / "1on1s"
                if path.exists():
                    return path

            # Check manager
            manager = config_loader.get_manager_config()
            if manager and manager.get("email", "").lower() == other_email:
                path = self.team_path / "manager" / manager["id"] / "1on1s"
                if path.exists():
                    return path

            # Check stakeholders
            for stakeholder in config_loader.get_stakeholders():
                if stakeholder.get("email", "").lower() == other_email:
                    path = self.team_path / "stakeholders" / stakeholder["id"] / "1on1s"
                    if path.exists():
                        return path

        # Product-related meeting routing
        if meeting_title:
            title_lower = meeting_title.lower()
            for product in config_loader.get_products_config().get("items", []):
                product_name = product.get("name", "").lower()
                product_id = product.get("id", "")
                if product_name and product_name in title_lower:
                    path = self.get_product_path(product_id) / "discussions"
                    if path.exists():
                        return path

        # Default to legacy path
        return self.planning_path / "Meeting_Prep"

    def get_career_planning_path(self, person_id: str) -> Path:
        """
        Get path for career planning documents.

        Args:
            person_id: Person identifier (e.g., 'alice-engineer')

        Returns:
            Path to career folder.
        """
        # Check if person is a direct report
        report = config_loader.get_report_by_id(person_id)
        if report:
            path = self.team_path / "reports" / person_id / "career"
            if path.exists():
                return path

        # Fallback to legacy
        return self.planning_path / "Career" / person_id.replace("-", "_").title()

    def get_prd_path(self, product_id: str) -> Path:
        """Get path for PRD documents."""
        return self.get_product_path(product_id) / "planning"

    def get_discovery_path(self, product_id: str) -> Path:
        """Get path for discovery documents."""
        return self.get_product_path(product_id) / "discovery"

    def get_execution_path(self, product_id: str) -> Path:
        """Get path for execution documents (RFCs, ADRs)."""
        return self.get_product_path(product_id) / "execution"

    def get_presentations_path(self, product_id: str) -> Path:
        """Get path for presentations."""
        return self.get_product_path(product_id) / "presentations"

    def get_personal_learning_path(self) -> Path:
        """Get path for personal learning content."""
        return self.personal_path / "learning"

    def get_personal_development_path(self) -> Path:
        """Get path for personal development content."""
        return self.personal_path / "development"

    def resolve_legacy_path(self, legacy_path: Path) -> Path:
        """
        Resolve a legacy path to new WCR location.

        Args:
            legacy_path: Old-style path

        Returns:
            New WCR path if mappable, else original path.
        """
        path_str = str(legacy_path)

        # Sprint reports
        if "Sprint_Reports" in path_str or "sprint-report" in path_str:
            return self.get_sprint_report_path()

        # Meeting prep
        if "Meeting_Prep" in path_str:
            return self.planning_path / "Meeting_Prep"  # No context, can't route

        # Career
        if "/Career/" in path_str:
            # Extract person name from path
            parts = path_str.split("/Career/")
            if len(parts) > 1:
                person_dir = parts[1].split("/")[0]
                person_id = person_dir.lower().replace("_", "-")
                return self.get_career_planning_path(person_id)

        return legacy_path


# Singleton instance
_router: Optional[PathRouter] = None


def get_router() -> PathRouter:
    """Get the path router singleton."""
    global _router
    if _router is None:
        _router = PathRouter()
    return _router


# Convenience functions
def route_sprint_report(product_id: Optional[str] = None) -> Path:
    """Route sprint report to correct location."""
    return get_router().get_sprint_report_path(product_id)


def route_meeting_prep(
    meeting_type: str = "other", attendees: List[str] = None, title: str = None
) -> Path:
    """Route meeting prep to correct location."""
    return get_router().get_meeting_prep_path(meeting_type, attendees, title)


def route_career_planning(person_id: str) -> Path:
    """Route career planning to correct location."""
    return get_router().get_career_planning_path(person_id)


def route_prd(product_id: str) -> Path:
    """Route PRD to correct location."""
    return get_router().get_prd_path(product_id)


# CLI
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="PM-OS Path Router")
    parser.add_argument(
        "--sprint-report", action="store_true", help="Get sprint report path"
    )
    parser.add_argument(
        "--meeting-prep", nargs="*", help="Get meeting prep path (attendee emails)"
    )
    parser.add_argument(
        "--career", type=str, help="Get career planning path for person"
    )
    parser.add_argument("--product", type=str, help="Product ID for routing")

    args = parser.parse_args()

    router = PathRouter()

    if args.sprint_report:
        print(router.get_sprint_report_path(args.product))
    elif args.meeting_prep is not None:
        print(router.get_meeting_prep_path(attendees=args.meeting_prep))
    elif args.career:
        print(router.get_career_planning_path(args.career))
    else:
        # Show all paths
        print(
            json.dumps(
                {
                    "products": str(router.products_path),
                    "team": str(router.team_path),
                    "personal": str(router.personal_path),
                    "sprint_reports": str(router.get_sprint_report_path()),
                    "meeting_prep": str(router.get_meeting_prep_path()),
                },
                indent=2,
            )
        )
