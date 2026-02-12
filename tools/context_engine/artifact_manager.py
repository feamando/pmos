"""
Artifact Manager - External Artifact Handling

Manages external artifacts like Figma designs, Jira epics,
Confluence pages, and wireframes.

Artifact Types:
    - figma: Figma design URLs
    - wireframes: Wireframe URLs or files
    - jira_epic: Jira epic links
    - confluence_page: Confluence page links
    - stakeholder_approval: Approval records
    - engineering_estimate: Effort estimates
    - meeting_notes: Meeting note links
    - other: Generic document links

URL Validation:
    - Figma: figma.com/file/{id} or figma.com/design/{id}
    - Jira: {org}.atlassian.net/browse/{KEY} or ticket key format (e.g., MK-123)
    - Confluence: {org}.atlassian.net/wiki/spaces/{space}/pages/{id}
    - GDocs: docs.google.com/document/d/{id}

Usage:
    from tools.context_engine import ArtifactManager, ArtifactType

    manager = ArtifactManager()

    # Validate and attach artifact
    result = manager.attach(
        feature_path=Path("/path/to/feature"),
        artifact_type=ArtifactType.FIGMA,
        url="https://figma.com/file/abc123"
    )

    if result.valid:
        print(f"Attached: {result.title}")

    # Validate URL with metadata extraction
    validation = manager.validate(ArtifactType.FIGMA, "https://figma.com/file/abc123")
    if validation.valid:
        print(f"File ID: {validation.metadata.get('file_id')}")
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent))


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
            # Standard file URL: figma.com/file/{id} or figma.com/design/{id}
            r"https?://(?:www\.)?figma\.com/(?:file|design)/(?P<file_id>[a-zA-Z0-9]+)(?:/(?P<node_id>[^/?]+))?",
            # Prototype URL: figma.com/proto/{id}
            r"https?://(?:www\.)?figma\.com/proto/(?P<file_id>[a-zA-Z0-9]+)",
            # Board URL: figma.com/board/{id}
            r"https?://(?:www\.)?figma\.com/board/(?P<file_id>[a-zA-Z0-9]+)",
        ],
        ArtifactType.JIRA_EPIC: [
            # Browse URL: {org}.atlassian.net/browse/{KEY-123}
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/browse/(?P<ticket_key>[A-Z]+-\d+)",
            # Jira software projects URL with selectedIssue query param
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/jira/software/(?:c/)?projects/(?P<project>[A-Z]+)/boards/\d+\?selectedIssue=(?P<ticket_key>[A-Z]+-\d+)",
            # Jira software projects URL without selectedIssue
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/jira/software/(?:c/)?projects/(?P<project>[A-Z]+)(?:/boards/\d+)?",
            # Standalone ticket key format (e.g., MK-123)
            r"^(?P<ticket_key>[A-Z]+-\d+)$",
        ],
        ArtifactType.CONFLUENCE_PAGE: [
            # Standard wiki page URL with space and page ID
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/wiki/spaces/(?P<space>[A-Za-z0-9]+)/pages/(?P<page_id>\d+)(?:/(?P<page_title>[^?]+))?",
            # Wiki page with display view
            r"https?://(?P<org>[a-zA-Z0-9.-]+)\.atlassian\.net/wiki/display/(?P<space>[A-Za-z0-9]+)/(?P<page_title>[^?]+)",
        ],
        ArtifactType.GDOCS: [
            # Google Docs document
            r"https?://docs\.google\.com/document/d/(?P<doc_id>[a-zA-Z0-9_-]+)",
            # Google Sheets spreadsheet
            r"https?://docs\.google\.com/spreadsheets/d/(?P<doc_id>[a-zA-Z0-9_-]+)",
            # Google Slides presentation
            r"https?://docs\.google\.com/presentation/d/(?P<doc_id>[a-zA-Z0-9_-]+)",
        ],
    }

    # Document type detection for GDocs
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
                        Can also be set via FIGMA_TOKEN environment variable.
        """
        self.figma_token = figma_token or os.environ.get("FIGMA_TOKEN")

    def validate(
        self, artifact_type: ArtifactType, url: str, fetch_metadata: bool = True
    ) -> ArtifactValidation:
        """
        Validate an artifact URL and extract metadata.

        Args:
            artifact_type: Type of artifact
            url: URL to validate
            fetch_metadata: Whether to fetch external metadata (e.g., Figma title)

        Returns:
            ArtifactValidation result with:
                - valid: bool
                - message: str (error message if invalid)
                - metadata: dict (extracted info like file_id, ticket_key)
        """
        # Basic URL validation
        if not url or not url.strip():
            return ArtifactValidation(
                valid=False,
                artifact_type=artifact_type,
                url=url,
                message="URL is empty",
            )

        url = url.strip()

        # For Jira, allow standalone ticket key format (e.g., MK-123)
        is_ticket_key_only = artifact_type == ArtifactType.JIRA_EPIC and re.match(
            r"^[A-Z]+-\d+$", url
        )

        # Check URL format (skip for standalone Jira ticket keys)
        if not is_ticket_key_only:
            url_pattern = r"https?://[^\s]+"
            if not re.match(url_pattern, url):
                return ArtifactValidation(
                    valid=False,
                    artifact_type=artifact_type,
                    url=url,
                    message="Invalid URL format. Expected https:// URL.",
                )

        # Type-specific validation and metadata extraction
        patterns = self.URL_PATTERNS.get(artifact_type, [])
        metadata = {}
        matched = False

        if patterns:
            for pattern in patterns:
                match = re.match(pattern, url)
                if match:
                    matched = True
                    # Extract named groups as metadata
                    metadata = {
                        k: v for k, v in match.groupdict().items() if v is not None
                    }
                    break

            if not matched:
                return ArtifactValidation(
                    valid=False,
                    artifact_type=artifact_type,
                    url=url,
                    message=self._get_pattern_error_message(artifact_type),
                )

        # Add artifact-specific metadata
        title = None

        if artifact_type == ArtifactType.FIGMA:
            # Optionally fetch Figma metadata via API
            if fetch_metadata and self.figma_token and metadata.get("file_id"):
                figma_meta = self._fetch_figma_metadata(metadata["file_id"])
                if figma_meta:
                    title = figma_meta.get("name")
                    metadata["figma_name"] = figma_meta.get("name")
                    metadata["last_modified"] = figma_meta.get("lastModified")

        elif artifact_type == ArtifactType.GDOCS:
            # Detect document type
            for doc_type, pattern in self.GDOCS_TYPE_PATTERNS.items():
                if re.search(pattern, url):
                    metadata["doc_type"] = doc_type
                    break

        elif artifact_type == ArtifactType.CONFLUENCE_PAGE:
            # Decode page title if present (URL encoded)
            if metadata.get("page_title"):
                try:
                    from urllib.parse import unquote

                    metadata["page_title"] = unquote(metadata["page_title"]).replace(
                        "+", " "
                    )
                except Exception:
                    pass

        return ArtifactValidation(
            valid=True,
            artifact_type=artifact_type,
            url=url,
            title=title,
            message="Valid",
            metadata=metadata,
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
                "{org}.atlassian.net/browse/{KEY-123} or ticket key like MK-123"
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
        """
        Fetch metadata from Figma API.

        Args:
            file_id: Figma file ID

        Returns:
            Dict with name, lastModified, etc. or None on failure
        """
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
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
            TimeoutError,
            Exception,
        ):
            # Silently fail - metadata fetch is optional
            return None

    def attach(
        self,
        feature_path: Path,
        artifact_type: ArtifactType,
        url: str,
        attached_by: Optional[str] = None,
    ) -> ArtifactValidation:
        """
        Validate and attach an artifact to a feature.

        Updates both feature-state.yaml and the context file.

        Args:
            feature_path: Path to feature folder
            artifact_type: Type of artifact
            url: URL to the artifact
            attached_by: Who is attaching

        Returns:
            ArtifactValidation result
        """
        # Validate the URL
        validation = self.validate(artifact_type, url)

        if not validation.valid:
            return validation

        # Load feature state
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            return ArtifactValidation(
                valid=False,
                artifact_type=artifact_type,
                url=url,
                message="Feature state not found",
            )

        # Update artifacts in state
        state.add_artifact(artifact_type.value, url)
        state.save(feature_path)

        # Update context file
        self._update_context_file(feature_path, state, artifact_type, url)

        validation.message = f"Artifact attached to {feature_path.name}"
        return validation

    def _update_context_file(
        self,
        feature_path: Path,
        state,  # FeatureState
        artifact_type: ArtifactType,
        url: str,
    ) -> None:
        """
        Update the context file's References section.

        Formats links with bold labels and markdown links:
        - **Figma Design**: [Design Name](https://figma.com/file/abc123)
        - **Jira Epic**: [MK-1234](https://atlassian.net/browse/MK-1234)

        Args:
            feature_path: Path to feature folder
            state: Feature state
            artifact_type: Type of artifact
            url: URL of artifact
        """
        context_file = feature_path / state.context_file
        if not context_file.exists():
            return

        content = context_file.read_text()

        # Build references list with proper markdown formatting
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

        # Replace references section
        refs_text = "\n".join(refs)
        pattern = r"(## References\n).*?(\n## |\Z)"
        replacement = f"\\1{refs_text}\n\n\\2"
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

        if new_content != content:
            context_file.write_text(new_content)

    def _generate_link_title(self, artifact_type: ArtifactType, url: str) -> str:
        """
        Generate a user-friendly link title from artifact type and URL.

        Extracts meaningful information from the URL when possible:
        - Jira: Extracts ticket key (e.g., "MK-1234")
        - Figma: Uses "Design" or extracts project name from URL
        - Confluence: Extracts page title if in URL
        - GDocs: Uses document type (Document, Spreadsheet, Presentation)

        Args:
            artifact_type: Type of artifact
            url: URL to the artifact

        Returns:
            Human-friendly link title
        """
        # Extract metadata from URL patterns
        patterns = self.URL_PATTERNS.get(artifact_type, [])
        metadata = {}

        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                metadata = {k: v for k, v in match.groupdict().items() if v is not None}
                break

        # Generate title based on artifact type and extracted metadata
        if artifact_type == ArtifactType.JIRA_EPIC:
            ticket_key = metadata.get("ticket_key")
            if ticket_key:
                return ticket_key
            return "Epic"

        elif artifact_type == ArtifactType.FIGMA:
            # Try to extract project name from URL path
            # URL format: figma.com/file/{id}/{project-name}
            file_id = metadata.get("file_id", "")
            node_id = metadata.get("node_id", "")
            if node_id and node_id not in ["edit", "view"]:
                # node_id might be the project name
                title = node_id.replace("-", " ").replace("_", " ")
                # Capitalize first letter of each word
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
            # Detect document type
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

        else:
            return "Link"

    def get_artifact(
        self, feature_path: Path, artifact_type: ArtifactType
    ) -> Optional[str]:
        """
        Get an artifact URL from a feature.

        Args:
            feature_path: Path to feature folder
            artifact_type: Type of artifact

        Returns:
            Artifact URL or None
        """
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            return None

        return state.artifacts.get(artifact_type.value)

    def list_artifacts(self, feature_path: Path) -> Dict[str, Optional[str]]:
        """
        List all artifacts for a feature.

        Args:
            feature_path: Path to feature folder

        Returns:
            Dictionary of artifact type -> URL
        """
        from .feature_state import FeatureState

        state = FeatureState.load(feature_path)
        if not state:
            return {}

        return state.artifacts.copy()

    def get_missing_artifacts(
        self, feature_path: Path, phase: str
    ) -> List[ArtifactType]:
        """
        Get list of missing artifacts required for a phase.

        Args:
            feature_path: Path to feature folder
            phase: Current phase

        Returns:
            List of missing artifact types
        """
        # Phase-specific required artifacts
        phase_requirements = {
            "design_track": [ArtifactType.WIREFRAMES, ArtifactType.FIGMA],
            "decision_gate": [ArtifactType.FIGMA],
        }

        required = phase_requirements.get(phase, [])
        if not required:
            return []

        artifacts = self.list_artifacts(feature_path)
        missing = []

        for artifact_type in required:
            if not artifacts.get(artifact_type.value):
                missing.append(artifact_type)

        return missing


def guess_artifact_type(url: str) -> Optional[ArtifactType]:
    """
    Guess artifact type from URL.

    Args:
        url: URL to analyze

    Returns:
        Guessed ArtifactType or None
    """
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
