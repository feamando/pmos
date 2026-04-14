"""
PM-OS CCE ArtifactManager (v5.0)

Manages external artifacts like Figma designs, Jira epics,
Confluence pages, and wireframes. Validates URLs, extracts metadata,
and updates feature state and context files.

Usage:
    from pm_os_cce.tools.documents.artifact_manager import ArtifactManager, ArtifactType
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pm_os_base.tools.core.connector_bridge import get_connector_client
except ImportError:
    try:
        from core.connector_bridge import get_connector_client
    except ImportError:
        get_connector_client = None

logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """Types of external artifacts."""

    FIGMA = "figma"
    WIREFRAMES = "wireframes_url"
    JIRA_EPIC = "jira_epic"
    CONFLUENCE_PAGE = "confluence_page"
    STAKEHOLDER_APPROVAL = "stakeholder_approval"
    ENGINEERING_ESTIMATE = "engineering_estimate"
    MEETING_NOTES = "meeting_notes"
    GDOCS = "gdocs"
    OTHER = "other"


@dataclass
class ArtifactValidation:
    """Result of validating an artifact."""

    valid: bool
    artifact_type: ArtifactType
    url: str
    title: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Artifact:
    """Represents an attached artifact."""

    artifact_type: ArtifactType
    url: str
    title: Optional[str] = None
    attached_at: datetime = None
    attached_by: Optional[str] = None
    validated: bool = False
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.attached_at is None:
            self.attached_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.artifact_type.value,
            "url": self.url,
            "title": self.title,
            "attached_at": self.attached_at.isoformat(),
            "attached_by": self.attached_by,
            "validated": self.validated,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Artifact":
        """Create from dictionary."""
        return cls(
            artifact_type=ArtifactType(data["type"]),
            url=data["url"],
            title=data.get("title"),
            attached_at=datetime.fromisoformat(data["attached_at"]),
            attached_by=data.get("attached_by"),
            validated=data.get("validated", False),
            metadata=data.get("metadata", {}),
        )


class ArtifactManager:
    """
    Manages external artifacts for features.

    Handles validation, attachment, and updates to context files
    when artifacts are added.
    """

    # URL validation patterns with named groups for metadata extraction
    URL_PATTERNS = {
        ArtifactType.FIGMA: [
            r"https?://(?:www\.)?figma\.com/(?:file|design)/(?P<file_id>[a-zA-Z0-9]+)(?:/(?P<node_id>[^/?]+))?",
            r"https?://(?:www\.)?figma\.com/proto/(?P<file_id>[a-zA-Z0-9]+)",
            r"https?://(?:www\.)?figma\.com/board/(?P<file_id>[a-zA-Z0-9]+)",
        ],
        ArtifactType.JIRA_EPIC: [
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/browse/(?P<ticket_key>[A-Z]+-\d+)",
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/jira/software/(?:c/)?projects/(?P<project>[A-Z]+)/boards/\d+\?selectedIssue=(?P<ticket_key>[A-Z]+-\d+)",
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/jira/software/(?:c/)?projects/(?P<project>[A-Z]+)(?:/boards/\d+)?",
            r"^(?P<ticket_key>[A-Z]+-\d+)$",
        ],
        ArtifactType.CONFLUENCE_PAGE: [
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/wiki/spaces/(?P<space>[A-Za-z0-9]+)/pages/(?P<page_id>\d+)(?:/(?P<page_title>[^?]+))?",
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/wiki/display/(?P<space>[A-Za-z0-9]+)/(?P<page_title>[^?]+)",
        ],
        ArtifactType.GDOCS: [
            r"https?://docs\.google\.com/document/d/(?P<doc_id>[a-zA-Z0-9_-]+)",
            r"https?://docs\.google\.com/spreadsheets/d/(?P<doc_id>[a-zA-Z0-9_-]+)",
            r"https?://docs\.google\.com/presentation/d/(?P<doc_id>[a-zA-Z0-9_-]+)",
        ],
    }

    GDOCS_TYPE_PATTERNS = {
        "document": r"docs\.google\.com/document/",
        "spreadsheet": r"docs\.google\.com/spreadsheets/",
        "presentation": r"docs\.google\.com/presentation/",
    }

    def __init__(self, figma_token: Optional[str] = None):
        """
        Initialize artifact manager.

        Args:
            figma_token: Optional Figma API token for fetching metadata.
                        Falls back to connector_bridge or env var.
        """
        self.figma_token = figma_token
        if not self.figma_token and get_connector_client is not None:
            try:
                client = get_connector_client("figma")
                if client:
                    self.figma_token = getattr(client, "token", None)
            except Exception:
                pass
        if not self.figma_token:
            self.figma_token = os.environ.get("FIGMA_TOKEN")

    def validate(
        self, artifact_type: ArtifactType, url: str, fetch_metadata: bool = True
    ) -> ArtifactValidation:
        """Validate an artifact URL and extract metadata."""
        if not url or not url.strip():
            return ArtifactValidation(
                valid=False, artifact_type=artifact_type, url=url,
                message="URL is empty",
            )

        url = url.strip()

        is_ticket_key_only = artifact_type == ArtifactType.JIRA_EPIC and re.match(
            r"^[A-Z]+-\d+$", url
        )

        if not is_ticket_key_only:
            url_pattern = r"https?://[^\s]+"
            if not re.match(url_pattern, url):
                return ArtifactValidation(
                    valid=False, artifact_type=artifact_type, url=url,
                    message="Invalid URL format. Expected https:// URL.",
                )

        patterns = self.URL_PATTERNS.get(artifact_type, [])
        metadata = {}
        matched = False

        if patterns:
            for pattern in patterns:
                match = re.match(pattern, url)
                if match:
                    matched = True
                    metadata = {
                        k: v for k, v in match.groupdict().items() if v is not None
                    }
                    break
            if not matched:
                return ArtifactValidation(
                    valid=False, artifact_type=artifact_type, url=url,
                    message=self._get_pattern_error_message(artifact_type),
                )

        title = None

        if artifact_type == ArtifactType.FIGMA:
            if fetch_metadata and self.figma_token and metadata.get("file_id"):
                figma_meta = self._fetch_figma_metadata(metadata["file_id"])
                if figma_meta:
                    title = figma_meta.get("name")
                    metadata["figma_name"] = figma_meta.get("name")
                    metadata["last_modified"] = figma_meta.get("lastModified")
        elif artifact_type == ArtifactType.GDOCS:
            for doc_type, pattern in self.GDOCS_TYPE_PATTERNS.items():
                if re.search(pattern, url):
                    metadata["doc_type"] = doc_type
                    break
        elif artifact_type == ArtifactType.CONFLUENCE_PAGE:
            if metadata.get("page_title"):
                try:
                    from urllib.parse import unquote
                    metadata["page_title"] = unquote(metadata["page_title"]).replace("+", " ")
                except Exception:
                    pass

        return ArtifactValidation(
            valid=True, artifact_type=artifact_type, url=url,
            title=title, message="Valid", metadata=metadata,
        )

    def _get_pattern_error_message(self, artifact_type: ArtifactType) -> str:
        """Get user-friendly error message for invalid URL pattern."""
        messages = {
            ArtifactType.FIGMA: (
                "Invalid Figma URL. Expected format: "
                "figma.com/file/{id} or figma.com/design/{id}"
            ),
            ArtifactType.JIRA_EPIC: (
                "Invalid Jira URL or ticket key. Expected format: "
                "{org}.atlassian.net/browse/{KEY-123} or ticket key like PROJ-123"
            ),
            ArtifactType.CONFLUENCE_PAGE: (
                "Invalid Confluence URL. Expected format: "
                "{org}.atlassian.net/wiki/spaces/{space}/pages/{id}"
            ),
            ArtifactType.GDOCS: (
                "Invalid Google Docs URL. Expected format: "
                "docs.google.com/document/d/{id}, docs.google.com/spreadsheets/d/{id}, "
                "or docs.google.com/presentation/d/{id}"
            ),
        }
        return messages.get(
            artifact_type, f"URL does not match expected {artifact_type.value} pattern"
        )

    def _fetch_figma_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Fetch metadata from Figma API."""
        if not self.figma_token:
            return None
        try:
            request = urllib.request.Request(
                f"https://api.figma.com/v1/files/{file_id}?depth=1",
                headers={
                    "X-Figma-Token": self.figma_token,
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
                return {
                    "name": data.get("name"),
                    "lastModified": data.get("lastModified"),
                    "version": data.get("version"),
                }
        except Exception:
            return None

    def attach(
        self,
        feature_path: Path,
        artifact_type: ArtifactType,
        url: str,
        attached_by: Optional[str] = None,
    ) -> ArtifactValidation:
        """Validate and attach an artifact to a feature."""
        validation = self.validate(artifact_type, url)
        if not validation.valid:
            return validation

        try:
            from pm_os_cce.tools.feature.feature_state import FeatureState
        except ImportError:
            try:
                from feature.feature_state import FeatureState
            except ImportError:
                return ArtifactValidation(
                    valid=False, artifact_type=artifact_type, url=url,
                    message="FeatureState module unavailable",
                )

        state = FeatureState.load(feature_path)
        if not state:
            return ArtifactValidation(
                valid=False, artifact_type=artifact_type, url=url,
                message="Feature state not found",
            )

        state.add_artifact(artifact_type.value, url)
        state.save(feature_path)

        self._update_context_file(feature_path, state, artifact_type, url)

        validation.message = f"Artifact attached to {feature_path.name}"
        return validation

    def _update_context_file(self, feature_path, state, artifact_type, url):
        """Update the context file's References section."""
        context_file = feature_path / state.context_file
        if not context_file.exists():
            return

        content = context_file.read_text()

        refs = []
        artifact_labels = {
            ArtifactType.FIGMA: "Figma Design",
            ArtifactType.WIREFRAMES: "Wireframes",
            ArtifactType.JIRA_EPIC: "Jira Epic",
            ArtifactType.CONFLUENCE_PAGE: "Confluence",
            ArtifactType.GDOCS: "Google Doc",
            ArtifactType.MEETING_NOTES: "Meeting Notes",
            ArtifactType.STAKEHOLDER_APPROVAL: "Stakeholder Approval",
            ArtifactType.ENGINEERING_ESTIMATE: "Engineering Estimate",
            ArtifactType.OTHER: "Reference",
        }

        for atype in ArtifactType:
            artifact_url = state.artifacts.get(atype.value)
            if artifact_url:
                label = artifact_labels.get(atype, atype.value)
                link_title = self._generate_link_title(atype, artifact_url)
                refs.append(f"- **{label}**: [{link_title}]({artifact_url})")

        if not refs:
            refs.append("*Links to artifacts will be added as they are attached*")

        refs_text = "\n".join(refs)
        pattern = r"(## References\n).*?(\n## |\Z)"
        replacement = f"\\1{refs_text}\n\n\\2"
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

        if new_content != content:
            context_file.write_text(new_content)

    def _generate_link_title(self, artifact_type: ArtifactType, url: str) -> str:
        """Generate a user-friendly link title from artifact type and URL."""
        patterns = self.URL_PATTERNS.get(artifact_type, [])
        metadata = {}
        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                metadata = {k: v for k, v in match.groupdict().items() if v is not None}
                break

        if artifact_type == ArtifactType.JIRA_EPIC:
            ticket_key = metadata.get("ticket_key")
            return ticket_key if ticket_key else "Epic"
        elif artifact_type == ArtifactType.FIGMA:
            node_id = metadata.get("node_id", "")
            if node_id and node_id not in ["edit", "view"]:
                title = node_id.replace("-", " ").replace("_", " ")
                return " ".join(word.capitalize() for word in title.split())
            return "Design"
        elif artifact_type == ArtifactType.WIREFRAMES:
            return "Wireframes"
        elif artifact_type == ArtifactType.CONFLUENCE_PAGE:
            page_title = metadata.get("page_title")
            if page_title:
                try:
                    from urllib.parse import unquote
                    return unquote(page_title).replace("+", " ").replace("-", " ")
                except Exception:
                    pass
            return "Page"
        elif artifact_type == ArtifactType.GDOCS:
            for doc_type, pattern in self.GDOCS_TYPE_PATTERNS.items():
                if re.search(pattern, url):
                    return doc_type.capitalize()
            return "Document"
        elif artifact_type == ArtifactType.MEETING_NOTES:
            return "Meeting Notes"
        elif artifact_type == ArtifactType.STAKEHOLDER_APPROVAL:
            return "Approval Record"
        elif artifact_type == ArtifactType.ENGINEERING_ESTIMATE:
            return "Estimate"
        return "Link"

    def get_artifact(
        self, feature_path: Path, artifact_type: ArtifactType
    ) -> Optional[str]:
        """Get an artifact URL from a feature."""
        try:
            from pm_os_cce.tools.feature.feature_state import FeatureState
        except ImportError:
            try:
                from feature.feature_state import FeatureState
            except ImportError:
                return None
        state = FeatureState.load(feature_path)
        if not state:
            return None
        return state.artifacts.get(artifact_type.value)

    def list_artifacts(self, feature_path: Path) -> Dict[str, Optional[str]]:
        """List all artifacts for a feature."""
        try:
            from pm_os_cce.tools.feature.feature_state import FeatureState
        except ImportError:
            try:
                from feature.feature_state import FeatureState
            except ImportError:
                return {}
        state = FeatureState.load(feature_path)
        if not state:
            return {}
        return state.artifacts.copy()

    def get_missing_artifacts(
        self, feature_path: Path, phase: str
    ) -> List[ArtifactType]:
        """Get list of missing artifacts required for a phase."""
        phase_requirements = {
            "design_track": [ArtifactType.WIREFRAMES, ArtifactType.FIGMA],
            "decision_gate": [ArtifactType.FIGMA],
        }
        required = phase_requirements.get(phase, [])
        if not required:
            return []

        artifacts = self.list_artifacts(feature_path)
        return [
            artifact_type
            for artifact_type in required
            if not artifacts.get(artifact_type.value)
        ]


def guess_artifact_type(url: str) -> Optional[ArtifactType]:
    """Guess artifact type from URL."""
    url_lower = url.lower()
    if "figma.com" in url_lower:
        return ArtifactType.FIGMA
    elif "atlassian.net/browse" in url_lower or "atlassian.net/jira" in url_lower:
        return ArtifactType.JIRA_EPIC
    elif "atlassian.net/wiki" in url_lower:
        return ArtifactType.CONFLUENCE_PAGE
    elif "docs.google.com" in url_lower:
        return ArtifactType.GDOCS
    return None
