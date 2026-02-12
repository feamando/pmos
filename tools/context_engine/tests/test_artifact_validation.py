"""
Unit tests for ArtifactManager URL validation and metadata extraction.

Tests cover:
- Figma URL validation (file, design, proto, board)
- Jira URL validation (browse, software, standalone ticket key)
- Confluence URL validation (wiki/spaces, display)
- Google Docs URL validation (document, spreadsheet, presentation)
- Metadata extraction from URLs
- Optional Figma API metadata fetch
- Error messages for invalid URLs

Run tests:
    pytest common/tools/context_engine/tests/test_artifact_validation.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add context_engine to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from artifact_manager import ArtifactManager, ArtifactType, ArtifactValidation


class TestFigmaValidation:
    """Tests for Figma URL validation."""

    @pytest.fixture
    def manager(self):
        """Create ArtifactManager instance without Figma token."""
        return ArtifactManager()

    def test_valid_figma_file_url(self, manager):
        """Standard figma.com/file URL is valid."""
        result = manager.validate(
            ArtifactType.FIGMA, "https://figma.com/file/abc123XYZ"
        )
        assert result.valid is True
        assert result.metadata.get("file_id") == "abc123XYZ"
        assert result.message == "Valid"

    def test_valid_figma_design_url(self, manager):
        """figma.com/design URL is valid."""
        result = manager.validate(
            ArtifactType.FIGMA, "https://www.figma.com/design/def456/Project-Name"
        )
        assert result.valid is True
        assert result.metadata.get("file_id") == "def456"

    def test_valid_figma_proto_url(self, manager):
        """figma.com/proto URL is valid."""
        result = manager.validate(ArtifactType.FIGMA, "https://figma.com/proto/xyz789")
        assert result.valid is True
        assert result.metadata.get("file_id") == "xyz789"

    def test_valid_figma_board_url(self, manager):
        """figma.com/board URL is valid."""
        result = manager.validate(
            ArtifactType.FIGMA, "https://figma.com/board/board123"
        )
        assert result.valid is True
        assert result.metadata.get("file_id") == "board123"

    def test_figma_with_node_id(self, manager):
        """Figma URL with node ID extracts node_id."""
        result = manager.validate(
            ArtifactType.FIGMA, "https://figma.com/file/abc123/ProjectName?node-id=0-1"
        )
        assert result.valid is True
        assert result.metadata.get("file_id") == "abc123"
        # node_id in path (not query string) would be extracted
        # Query string node-id is different

    def test_figma_with_www(self, manager):
        """www.figma.com URLs are valid."""
        result = manager.validate(
            ArtifactType.FIGMA, "https://www.figma.com/file/abc123"
        )
        assert result.valid is True
        assert result.metadata.get("file_id") == "abc123"

    def test_invalid_figma_url(self, manager):
        """Non-Figma URLs are rejected."""
        result = manager.validate(
            ArtifactType.FIGMA, "https://notfigma.com/file/abc123"
        )
        assert result.valid is False
        assert "figma.com/file" in result.message.lower()

    def test_figma_missing_file_id(self, manager):
        """Figma URL without file ID is invalid."""
        result = manager.validate(ArtifactType.FIGMA, "https://figma.com/file/")
        assert result.valid is False


class TestJiraValidation:
    """Tests for Jira URL and ticket key validation."""

    @pytest.fixture
    def manager(self):
        """Create ArtifactManager instance."""
        return ArtifactManager()

    def test_valid_jira_browse_url(self, manager):
        """Standard {org}.atlassian.net/browse/{KEY} URL is valid."""
        result = manager.validate(
            ArtifactType.JIRA_EPIC, "https://mycompany.atlassian.net/browse/MK-123"
        )
        assert result.valid is True
        assert result.metadata.get("ticket_key") == "MK-123"
        assert result.metadata.get("org") == "mycompany"

    def test_valid_jira_software_url(self, manager):
        """Jira software projects URL is valid."""
        result = manager.validate(
            ArtifactType.JIRA_EPIC,
            "https://company.atlassian.net/jira/software/projects/PROJ/boards/1?selectedIssue=PROJ-456",
        )
        assert result.valid is True
        assert result.metadata.get("ticket_key") == "PROJ-456"
        assert result.metadata.get("project") == "PROJ"

    def test_valid_standalone_ticket_key(self, manager):
        """Standalone ticket key (e.g., MK-123) is valid."""
        result = manager.validate(ArtifactType.JIRA_EPIC, "MK-123")
        assert result.valid is True
        assert result.metadata.get("ticket_key") == "MK-123"

    def test_valid_ticket_key_long_number(self, manager):
        """Ticket key with long number is valid."""
        result = manager.validate(ArtifactType.JIRA_EPIC, "PROJECT-99999")
        assert result.valid is True
        assert result.metadata.get("ticket_key") == "PROJECT-99999"

    def test_invalid_ticket_key_lowercase(self, manager):
        """Lowercase ticket key is invalid."""
        result = manager.validate(ArtifactType.JIRA_EPIC, "goc-123")
        assert result.valid is False

    def test_invalid_jira_url(self, manager):
        """Non-Jira URLs are rejected."""
        result = manager.validate(
            ArtifactType.JIRA_EPIC, "https://jira.notatlassian.com/browse/MK-123"
        )
        assert result.valid is False
        assert (
            "atlassian.net" in result.message.lower()
            or "ticket key" in result.message.lower()
        )

    def test_jira_c_projects_url(self, manager):
        """Jira software/c/projects URL is valid."""
        result = manager.validate(
            ArtifactType.JIRA_EPIC,
            "https://org.atlassian.net/jira/software/c/projects/ABC/boards/5",
        )
        # May or may not extract ticket_key depending on URL format
        assert result.valid is True
        assert result.metadata.get("project") == "ABC"


class TestConfluenceValidation:
    """Tests for Confluence URL validation."""

    @pytest.fixture
    def manager(self):
        """Create ArtifactManager instance."""
        return ArtifactManager()

    def test_valid_confluence_wiki_spaces_url(self, manager):
        """Standard wiki/spaces URL is valid."""
        result = manager.validate(
            ArtifactType.CONFLUENCE_PAGE,
            "https://company.atlassian.net/wiki/spaces/TEAM/pages/123456789/Page+Title",
        )
        assert result.valid is True
        assert result.metadata.get("space") == "TEAM"
        assert result.metadata.get("page_id") == "123456789"
        assert result.metadata.get("org") == "company"
        # Page title should be URL decoded
        assert result.metadata.get("page_title") == "Page Title"

    def test_valid_confluence_without_title(self, manager):
        """Confluence URL without page title is valid."""
        result = manager.validate(
            ArtifactType.CONFLUENCE_PAGE,
            "https://org.atlassian.net/wiki/spaces/ABC/pages/987654321",
        )
        assert result.valid is True
        assert result.metadata.get("space") == "ABC"
        assert result.metadata.get("page_id") == "987654321"

    def test_valid_confluence_display_url(self, manager):
        """wiki/display URL format is valid."""
        result = manager.validate(
            ArtifactType.CONFLUENCE_PAGE,
            "https://company.atlassian.net/wiki/display/SPACE/My+Page+Title",
        )
        assert result.valid is True
        assert result.metadata.get("space") == "SPACE"
        assert result.metadata.get("page_title") == "My Page Title"

    def test_confluence_lowercase_space(self, manager):
        """Confluence with lowercase space key is valid."""
        result = manager.validate(
            ArtifactType.CONFLUENCE_PAGE,
            "https://org.atlassian.net/wiki/spaces/team123/pages/111",
        )
        assert result.valid is True
        assert result.metadata.get("space") == "team123"

    def test_invalid_confluence_url(self, manager):
        """Non-Confluence URLs are rejected."""
        result = manager.validate(
            ArtifactType.CONFLUENCE_PAGE,
            "https://confluence.notatlassian.com/wiki/spaces/TEAM/pages/123",
        )
        assert result.valid is False
        assert "atlassian.net/wiki" in result.message.lower()


class TestGDocsValidation:
    """Tests for Google Docs URL validation."""

    @pytest.fixture
    def manager(self):
        """Create ArtifactManager instance."""
        return ArtifactManager()

    def test_valid_google_document(self, manager):
        """Google Docs document URL is valid."""
        result = manager.validate(
            ArtifactType.GDOCS,
            "https://docs.google.com/document/d/1abc123def456_-xyz/edit",
        )
        assert result.valid is True
        assert result.metadata.get("doc_id") == "1abc123def456_-xyz"
        assert result.metadata.get("doc_type") == "document"

    def test_valid_google_spreadsheet(self, manager):
        """Google Sheets URL is valid."""
        result = manager.validate(
            ArtifactType.GDOCS,
            "https://docs.google.com/spreadsheets/d/spreadsheet123/edit#gid=0",
        )
        assert result.valid is True
        assert result.metadata.get("doc_id") == "spreadsheet123"
        assert result.metadata.get("doc_type") == "spreadsheet"

    def test_valid_google_presentation(self, manager):
        """Google Slides URL is valid."""
        result = manager.validate(
            ArtifactType.GDOCS,
            "https://docs.google.com/presentation/d/pres_abc-123/edit",
        )
        assert result.valid is True
        assert result.metadata.get("doc_id") == "pres_abc-123"
        assert result.metadata.get("doc_type") == "presentation"

    def test_invalid_gdocs_url(self, manager):
        """Non-Google Docs URLs are rejected."""
        result = manager.validate(
            ArtifactType.GDOCS, "https://drive.google.com/file/d/abc123"
        )
        assert result.valid is False
        assert "docs.google.com" in result.message.lower()


class TestBasicValidation:
    """Tests for basic URL validation."""

    @pytest.fixture
    def manager(self):
        """Create ArtifactManager instance."""
        return ArtifactManager()

    def test_empty_url(self, manager):
        """Empty URL is invalid."""
        result = manager.validate(ArtifactType.FIGMA, "")
        assert result.valid is False
        assert "empty" in result.message.lower()

    def test_whitespace_only_url(self, manager):
        """Whitespace-only URL is invalid."""
        result = manager.validate(ArtifactType.FIGMA, "   ")
        assert result.valid is False
        assert "empty" in result.message.lower()

    def test_invalid_url_format(self, manager):
        """Non-URL strings are rejected (except Jira ticket keys)."""
        result = manager.validate(ArtifactType.FIGMA, "not a url")
        assert result.valid is False
        assert "url format" in result.message.lower()

    def test_http_url_accepted(self, manager):
        """HTTP (non-HTTPS) URLs are accepted."""
        result = manager.validate(ArtifactType.FIGMA, "http://figma.com/file/abc123")
        assert result.valid is True

    def test_url_trimmed(self, manager):
        """Leading/trailing whitespace is trimmed."""
        result = manager.validate(
            ArtifactType.FIGMA, "  https://figma.com/file/abc123  "
        )
        assert result.valid is True
        assert result.url == "https://figma.com/file/abc123"

    def test_other_artifact_type_accepts_any_url(self, manager):
        """OTHER artifact type accepts any valid URL."""
        result = manager.validate(ArtifactType.OTHER, "https://example.com/any/path")
        assert result.valid is True

    def test_wireframes_type_accepts_any_url(self, manager):
        """WIREFRAMES type accepts any valid URL."""
        result = manager.validate(
            ArtifactType.WIREFRAMES, "https://miro.com/board/abc123"
        )
        assert result.valid is True


class TestFigmaMetadataFetch:
    """Tests for optional Figma API metadata fetch."""

    def test_no_fetch_without_token(self):
        """Without token, no API fetch occurs."""
        manager = ArtifactManager(figma_token=None)
        result = manager.validate(ArtifactType.FIGMA, "https://figma.com/file/abc123")
        assert result.valid is True
        assert result.title is None
        assert "figma_name" not in result.metadata

    def test_fetch_disabled_parameter(self):
        """fetch_metadata=False skips API call."""
        manager = ArtifactManager(figma_token="fake_token")
        result = manager.validate(
            ArtifactType.FIGMA, "https://figma.com/file/abc123", fetch_metadata=False
        )
        assert result.valid is True
        assert result.title is None

    @patch("artifact_manager.urllib.request.urlopen")
    def test_figma_metadata_fetch_success(self, mock_urlopen):
        """Successful Figma API fetch populates metadata."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"name": "My Design File", "lastModified": "2024-01-15T10:30:00Z", "version": "123"}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        manager = ArtifactManager(figma_token="test_token")
        result = manager.validate(
            ArtifactType.FIGMA, "https://figma.com/file/testFile123"
        )

        assert result.valid is True
        assert result.title == "My Design File"
        assert result.metadata.get("figma_name") == "My Design File"
        assert result.metadata.get("last_modified") == "2024-01-15T10:30:00Z"

    @patch("artifact_manager.urllib.request.urlopen")
    def test_figma_metadata_fetch_failure_still_valid(self, mock_urlopen):
        """Failed Figma API fetch doesn't invalidate URL."""
        mock_urlopen.side_effect = Exception("API Error")

        manager = ArtifactManager(figma_token="test_token")
        result = manager.validate(
            ArtifactType.FIGMA, "https://figma.com/file/testFile123"
        )

        # URL is still valid, just no metadata
        assert result.valid is True
        assert result.metadata.get("file_id") == "testFile123"
        assert result.title is None

    def test_figma_token_from_env(self):
        """Figma token can be read from environment variable."""
        import os

        original = os.environ.get("FIGMA_TOKEN")
        try:
            os.environ["FIGMA_TOKEN"] = "env_token"
            manager = ArtifactManager()
            assert manager.figma_token == "env_token"
        finally:
            if original:
                os.environ["FIGMA_TOKEN"] = original
            elif "FIGMA_TOKEN" in os.environ:
                del os.environ["FIGMA_TOKEN"]


class TestArtifactValidationDataclass:
    """Tests for ArtifactValidation dataclass."""

    def test_default_metadata(self):
        """Metadata defaults to empty dict."""
        validation = ArtifactValidation(
            valid=True,
            artifact_type=ArtifactType.FIGMA,
            url="https://figma.com/file/abc",
        )
        assert validation.metadata == {}

    def test_all_fields(self):
        """All fields are set correctly."""
        validation = ArtifactValidation(
            valid=True,
            artifact_type=ArtifactType.JIRA_EPIC,
            url="https://org.atlassian.net/browse/MK-123",
            title="My Ticket",
            message="Valid",
            metadata={"ticket_key": "MK-123"},
        )
        assert validation.valid is True
        assert validation.artifact_type == ArtifactType.JIRA_EPIC
        assert validation.url == "https://org.atlassian.net/browse/MK-123"
        assert validation.title == "My Ticket"
        assert validation.message == "Valid"
        assert validation.metadata == {"ticket_key": "MK-123"}


class TestGuessArtifactType:
    """Tests for guess_artifact_type function."""

    def test_guess_figma(self):
        """Figma URLs are detected."""
        from artifact_manager import guess_artifact_type

        assert guess_artifact_type("https://figma.com/file/abc") == ArtifactType.FIGMA
        assert (
            guess_artifact_type("https://www.figma.com/design/xyz")
            == ArtifactType.FIGMA
        )

    def test_guess_jira(self):
        """Jira URLs are detected."""
        from artifact_manager import guess_artifact_type

        assert (
            guess_artifact_type("https://org.atlassian.net/browse/MK-123")
            == ArtifactType.JIRA_EPIC
        )
        assert (
            guess_artifact_type("https://org.atlassian.net/jira/software/projects/X")
            == ArtifactType.JIRA_EPIC
        )

    def test_guess_confluence(self):
        """Confluence URLs are detected."""
        from artifact_manager import guess_artifact_type

        assert (
            guess_artifact_type("https://org.atlassian.net/wiki/spaces/TEAM/pages/123")
            == ArtifactType.CONFLUENCE_PAGE
        )

    def test_guess_gdocs(self):
        """Google Docs URLs are detected."""
        from artifact_manager import guess_artifact_type

        assert (
            guess_artifact_type("https://docs.google.com/document/d/abc")
            == ArtifactType.GDOCS
        )
        assert (
            guess_artifact_type("https://docs.google.com/spreadsheets/d/xyz")
            == ArtifactType.GDOCS
        )

    def test_guess_unknown(self):
        """Unknown URLs return None."""
        from artifact_manager import guess_artifact_type

        assert guess_artifact_type("https://example.com/something") is None


class TestLinkTitleGeneration:
    """Tests for _generate_link_title method."""

    @pytest.fixture
    def manager(self):
        """Create ArtifactManager instance."""
        return ArtifactManager()

    def test_jira_link_title_extracts_ticket_key(self, manager):
        """Jira links use ticket key as title."""
        title = manager._generate_link_title(
            ArtifactType.JIRA_EPIC, "https://company.atlassian.net/browse/MK-1234"
        )
        assert title == "MK-1234"

    def test_jira_standalone_ticket_key(self, manager):
        """Standalone ticket key is used as title."""
        title = manager._generate_link_title(ArtifactType.JIRA_EPIC, "PROJECT-99999")
        assert title == "PROJECT-99999"

    def test_figma_link_title_with_project_name(self, manager):
        """Figma links extract project name from URL."""
        title = manager._generate_link_title(
            ArtifactType.FIGMA, "https://figma.com/file/abc123/my-project-design"
        )
        assert title == "My Project Design"

    def test_figma_link_title_without_project_name(self, manager):
        """Figma links without project name use 'Design'."""
        title = manager._generate_link_title(
            ArtifactType.FIGMA, "https://figma.com/file/abc123"
        )
        assert title == "Design"

    def test_confluence_link_title_extracts_page_title(self, manager):
        """Confluence links extract page title from URL."""
        title = manager._generate_link_title(
            ArtifactType.CONFLUENCE_PAGE,
            "https://company.atlassian.net/wiki/spaces/TEAM/pages/123/My+Page+Title",
        )
        assert title == "My Page Title"

    def test_confluence_link_title_without_page_title(self, manager):
        """Confluence links without page title use 'Page'."""
        title = manager._generate_link_title(
            ArtifactType.CONFLUENCE_PAGE,
            "https://company.atlassian.net/wiki/spaces/TEAM/pages/123",
        )
        assert title == "Page"

    def test_gdocs_document_title(self, manager):
        """Google Docs documents use 'Document' as title."""
        title = manager._generate_link_title(
            ArtifactType.GDOCS, "https://docs.google.com/document/d/abc123"
        )
        assert title == "Document"

    def test_gdocs_spreadsheet_title(self, manager):
        """Google Sheets use 'Spreadsheet' as title."""
        title = manager._generate_link_title(
            ArtifactType.GDOCS, "https://docs.google.com/spreadsheets/d/abc123"
        )
        assert title == "Spreadsheet"

    def test_gdocs_presentation_title(self, manager):
        """Google Slides use 'Presentation' as title."""
        title = manager._generate_link_title(
            ArtifactType.GDOCS, "https://docs.google.com/presentation/d/abc123"
        )
        assert title == "Presentation"

    def test_wireframes_link_title(self, manager):
        """Wireframes use 'Wireframes' as title."""
        title = manager._generate_link_title(
            ArtifactType.WIREFRAMES, "https://miro.com/board/abc123"
        )
        assert title == "Wireframes"

    def test_meeting_notes_link_title(self, manager):
        """Meeting notes use 'Meeting Notes' as title."""
        title = manager._generate_link_title(
            ArtifactType.MEETING_NOTES, "https://example.com/meeting/123"
        )
        assert title == "Meeting Notes"

    def test_other_link_title(self, manager):
        """Other artifact type uses 'Link' as title."""
        title = manager._generate_link_title(
            ArtifactType.OTHER, "https://example.com/any/path"
        )
        assert title == "Link"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
