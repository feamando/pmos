"""
PM-OS Brain Entity Schema

Defines the standardized frontmatter schema for brain entities.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
import yaml


# Entity type definitions with required and optional fields
ENTITY_TYPES = {
    "person": {
        "required": ["name", "email"],
        "optional": ["role", "team", "department", "is_self", "slack_id", "github_username", "jira_account_id"],
        "path": "Entities/People"
    },
    "project": {
        "required": ["name"],
        "optional": ["source", "jira_key", "github_repo", "status", "owner", "description", "start_date", "end_date"],
        "path": "Entities/Projects"
    },
    "issue": {
        "required": ["title", "source"],
        "optional": ["key", "status", "assignee", "reporter", "priority", "issue_type", "project", "sprint", "labels", "created_date", "updated_date", "due_date"],
        "path": "Entities/Issues"
    },
    "sprint": {
        "required": ["name", "project"],
        "optional": ["start_date", "end_date", "status", "goal", "board_id"],
        "path": "Entities/Sprints"
    },
    "channel": {
        "required": ["name", "source"],
        "optional": ["channel_id", "is_private", "topic", "purpose", "member_count"],
        "path": "Entities/Channels"
    },
    "repository": {
        "required": ["name", "full_name"],
        "optional": ["url", "description", "default_branch", "is_private", "language", "stars", "forks", "open_issues"],
        "path": "Entities/Repositories"
    },
    "pull_request": {
        "required": ["title", "number", "repository"],
        "optional": ["state", "author", "url", "base_branch", "head_branch", "created_date", "merged_date", "labels"],
        "path": "Entities/PullRequests"
    },
    "document": {
        "required": ["title", "source"],
        "optional": ["url", "space", "page_id", "author", "last_modified", "parent"],
        "path": "Entities/Documents"
    },
    "meeting": {
        "required": ["title", "date"],
        "optional": ["calendar_id", "event_id", "start_time", "end_time", "attendees", "location", "description", "recurring"],
        "path": "Entities/Meetings"
    }
}


@dataclass
class EntitySchema:
    """Schema for a brain entity."""
    type: str
    name: str
    source: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    last_sync: Optional[str] = None
    sync_id: Optional[str] = None  # External system ID for incremental sync
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_frontmatter(self) -> str:
        """Convert to YAML frontmatter string."""
        data = {
            "type": self.type,
            "name": self.name
        }

        if self.source:
            data["source"] = self.source
        if self.created:
            data["created"] = self.created
        if self.updated:
            data["updated"] = self.updated
        if self.last_sync:
            data["last_sync"] = self.last_sync
        if self.sync_id:
            data["sync_id"] = self.sync_id
        if self.relationships:
            data["relationships"] = self.relationships

        # Add extra fields
        data.update(self.extra)

        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    @classmethod
    def from_frontmatter(cls, frontmatter: dict) -> "EntitySchema":
        """Create schema from parsed frontmatter."""
        known_fields = {'type', 'name', 'source', 'created', 'updated', 'last_sync', 'sync_id', 'relationships'}
        extra = {k: v for k, v in frontmatter.items() if k not in known_fields}

        return cls(
            type=frontmatter.get('type', ''),
            name=frontmatter.get('name', ''),
            source=frontmatter.get('source'),
            created=frontmatter.get('created'),
            updated=frontmatter.get('updated'),
            last_sync=frontmatter.get('last_sync'),
            sync_id=frontmatter.get('sync_id'),
            relationships=frontmatter.get('relationships', {}),
            extra=extra
        )


def create_entity_content(
    entity_type: str,
    name: str,
    source: str,
    body: str = "",
    sync_id: Optional[str] = None,
    relationships: Optional[Dict[str, List[str]]] = None,
    **extra_fields
) -> str:
    """Create full markdown content for an entity.

    Args:
        entity_type: Type of entity (person, project, issue, etc.)
        name: Entity name
        source: Source system (jira, slack, github, etc.)
        body: Markdown body content
        sync_id: External system ID for tracking
        relationships: Dict of relationship type -> list of related entity names
        **extra_fields: Additional frontmatter fields

    Returns:
        Complete markdown content with frontmatter
    """
    now = datetime.now().strftime("%Y-%m-%d")

    schema = EntitySchema(
        type=entity_type,
        name=name,
        source=source,
        created=now,
        updated=now,
        last_sync=datetime.now().isoformat(),
        sync_id=sync_id,
        relationships=relationships or {},
        extra=extra_fields
    )

    frontmatter = schema.to_frontmatter()

    # Build content
    content = f"---\n{frontmatter}---\n\n"

    if body:
        content += body
    else:
        content += f"# {name}\n\n"
        content += f"*Synced from {source} on {now}*\n"

    return content


def parse_entity_file(content: str) -> tuple:
    """Parse an entity markdown file.

    Args:
        content: File content with YAML frontmatter

    Returns:
        Tuple of (EntitySchema, body_content)
    """
    if not content.startswith("---"):
        return None, content

    # Find end of frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, content

    try:
        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].strip()
        schema = EntitySchema.from_frontmatter(frontmatter)
        return schema, body
    except yaml.YAMLError:
        return None, content


def get_entity_path(entity_type: str) -> str:
    """Get the relative path for an entity type."""
    type_info = ENTITY_TYPES.get(entity_type)
    if type_info:
        return type_info["path"]
    return "Entities/Other"


def sanitize_filename(name: str) -> str:
    """Convert a name to a safe filename."""
    # Replace problematic characters
    safe = name.replace("/", "-").replace("\\", "-").replace(":", "-")
    safe = safe.replace("<", "").replace(">", "").replace("|", "")
    safe = safe.replace("?", "").replace("*", "").replace('"', "")

    # Replace spaces with underscores
    safe = safe.replace(" ", "_")

    # Remove consecutive underscores/dashes
    while "__" in safe:
        safe = safe.replace("__", "_")
    while "--" in safe:
        safe = safe.replace("--", "-")

    # Limit length
    if len(safe) > 100:
        safe = safe[:100]

    return safe
