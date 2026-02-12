"""
PM-OS Jira Brain Sync

Syncs projects, issues, sprints, and boards from Jira.
"""

from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from datetime import datetime

from pm_os.wizard.brain_sync.base import BaseSyncer, SyncResult, SyncProgress
from pm_os.wizard.exceptions import CredentialError, SyncError, NetworkError


class JiraSyncer(BaseSyncer):
    """Sync brain entities from Jira."""

    def __init__(
        self,
        brain_path: Path,
        url: str,
        email: str,
        token: str,
        projects: Optional[List[str]] = None
    ):
        """Initialize Jira syncer.

        Args:
            brain_path: Path to brain directory
            url: Jira instance URL
            email: User email for auth
            token: API token
            projects: Optional list of project keys to sync (None = all)
        """
        super().__init__(brain_path)
        self.url = url.rstrip("/")
        self.email = email
        self.token = token
        self.projects = projects
        self._client = None

    def _get_client(self):
        """Get or create Jira client."""
        if self._client is None:
            try:
                import requests
                from requests.auth import HTTPBasicAuth
            except ImportError:
                raise SyncError(
                    "requests library not installed",
                    service="Jira",
                    remediation="pip install requests"
                )

            self._auth = HTTPBasicAuth(self.email, self.token)
            self._session = requests.Session()
            self._session.auth = self._auth
            self._session.headers.update({"Accept": "application/json"})
            self._client = self._session

        return self._client

    def test_connection(self) -> tuple:
        """Test connection to Jira."""
        try:
            client = self._get_client()
            response = client.get(f"{self.url}/rest/api/3/myself", timeout=10)

            if response.status_code == 200:
                data = response.json()
                return True, f"Connected as {data.get('displayName', 'user')}"
            elif response.status_code == 401:
                return False, "Invalid credentials"
            else:
                return False, f"Jira returned status {response.status_code}"

        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def sync(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        incremental: bool = True
    ) -> SyncResult:
        """Sync Jira data to brain.

        Args:
            progress_callback: Progress callback (current, total, phase)
            incremental: Only sync changes since last sync

        Returns:
            SyncResult with details
        """
        result = SyncResult(success=True, message="")
        progress = SyncProgress(callback=progress_callback)

        try:
            client = self._get_client()

            # Phase 1: Get projects
            progress.phase = "Fetching projects"
            projects = self._fetch_projects(client)

            if self.projects:
                projects = [p for p in projects if p['key'] in self.projects]

            progress.total = len(projects) * 3  # projects, issues, sprints

            # Phase 2: Sync projects
            for project in projects:
                progress.update(progress.current, f"Syncing project: {project['key']}")
                self._sync_project(project, result)
                progress.increment()

            # Phase 3: Sync issues for each project
            for project in projects:
                progress.update(progress.current, f"Syncing issues: {project['key']}")
                last_sync = self.get_last_sync_time(f"jira_issues_{project['key']}") if incremental else None
                self._sync_issues(client, project['key'], last_sync, result)
                self.set_last_sync_time(f"jira_issues_{project['key']}")
                progress.increment()

            # Phase 4: Sync sprints for each project
            for project in projects:
                progress.update(progress.current, f"Syncing sprints: {project['key']}")
                self._sync_sprints(client, project['key'], result)
                progress.increment()

            # Build summary message
            total_entities = result.entities_created + result.entities_updated
            result.message = f"Synced {total_entities} entities from {len(projects)} projects"

        except CredentialError:
            raise
        except SyncError:
            raise
        except Exception as e:
            result.success = False
            result.message = f"Sync failed: {str(e)}"
            result.errors.append(str(e))

        return result

    def _fetch_projects(self, client) -> List[Dict]:
        """Fetch all accessible projects."""
        try:
            response = client.get(
                f"{self.url}/rest/api/3/project/search",
                params={"maxResults": 100},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("values", [])
            else:
                raise SyncError(
                    f"Failed to fetch projects: {response.status_code}",
                    service="Jira"
                )

        except Exception as e:
            if "Jira" in str(type(e).__name__):
                raise
            raise NetworkError(
                f"Network error fetching projects: {str(e)}",
                endpoint=f"{self.url}/rest/api/3/project/search"
            )

    def _sync_project(self, project: Dict, result: SyncResult):
        """Sync a single project entity."""
        name = project.get("name", project.get("key"))
        key = project.get("key")

        body = f"""# {name}

## Overview

- **Key**: {key}
- **Type**: {project.get('projectTypeKey', 'software')}
- **Lead**: {project.get('lead', {}).get('displayName', 'Unknown')}

## Description

{project.get('description', 'No description provided.')}

## Links

- [View in Jira]({self.url}/browse/{key})
"""

        self.write_entity(
            entity_type="project",
            name=name,
            source="jira",
            body=body,
            sync_id=project.get("id"),
            jira_key=key,
            project_type=project.get("projectTypeKey"),
            url=f"{self.url}/browse/{key}"
        )

        result.entities_created += 1

    def _sync_issues(
        self,
        client,
        project_key: str,
        last_sync: Optional[str],
        result: SyncResult,
        max_results: int = 100
    ):
        """Sync issues for a project."""
        # Build JQL query
        jql = f"project = {project_key}"
        if last_sync:
            jql += f" AND updated > '{last_sync[:10]}'"
        jql += " ORDER BY updated DESC"

        try:
            response = client.get(
                f"{self.url}/rest/api/3/search",
                params={
                    "jql": jql,
                    "maxResults": max_results,
                    "fields": "summary,status,assignee,reporter,priority,issuetype,created,updated,duedate,labels,sprint"
                },
                timeout=60
            )

            if response.status_code != 200:
                result.errors.append(f"Failed to fetch issues for {project_key}")
                return

            data = response.json()
            issues = data.get("issues", [])

            for issue in issues:
                self._sync_issue(issue, project_key, result)

        except Exception as e:
            result.errors.append(f"Error syncing issues for {project_key}: {str(e)}")

    def _sync_issue(self, issue: Dict, project_key: str, result: SyncResult):
        """Sync a single issue entity."""
        key = issue.get("key")
        fields = issue.get("fields", {})
        title = fields.get("summary", "Untitled")

        # Build relationships
        relationships = {"project": [project_key]}

        assignee = fields.get("assignee")
        if assignee:
            relationships["assignee"] = [assignee.get("displayName", "")]

        reporter = fields.get("reporter")
        if reporter:
            relationships["reporter"] = [reporter.get("displayName", "")]

        # Get status
        status = fields.get("status", {}).get("name", "Unknown")
        priority = fields.get("priority", {}).get("name", "Medium")
        issue_type = fields.get("issuetype", {}).get("name", "Task")

        body = f"""# {title}

## Details

- **Key**: [{key}]({self.url}/browse/{key})
- **Status**: {status}
- **Priority**: {priority}
- **Type**: {issue_type}
- **Assignee**: {assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'}
- **Reporter**: {reporter.get('displayName', 'Unknown') if reporter else 'Unknown'}

## Dates

- **Created**: {fields.get('created', 'Unknown')[:10]}
- **Updated**: {fields.get('updated', 'Unknown')[:10]}
- **Due**: {fields.get('duedate', 'Not set')}
"""

        self.write_entity(
            entity_type="issue",
            name=f"{key}: {title}",
            source="jira",
            body=body,
            sync_id=issue.get("id"),
            key=key,
            title=title,
            status=status,
            priority=priority,
            issue_type=issue_type,
            project=project_key,
            relationships=relationships,
            url=f"{self.url}/browse/{key}"
        )

        result.entities_created += 1

    def _sync_sprints(self, client, project_key: str, result: SyncResult):
        """Sync sprints for a project using the Agile API."""
        # First, find boards for the project
        try:
            response = client.get(
                f"{self.url}/rest/agile/1.0/board",
                params={"projectKeyOrId": project_key, "maxResults": 10},
                timeout=30
            )

            if response.status_code != 200:
                # Agile API not available or project has no boards
                return

            data = response.json()
            boards = data.get("values", [])

            for board in boards:
                self._sync_board_sprints(client, board, project_key, result)

        except Exception as e:
            # Sprints are optional - don't fail the whole sync
            result.errors.append(f"Could not sync sprints for {project_key}: {str(e)}")

    def _sync_board_sprints(
        self,
        client,
        board: Dict,
        project_key: str,
        result: SyncResult
    ):
        """Sync sprints from a board."""
        board_id = board.get("id")
        board_name = board.get("name", "Unknown Board")

        try:
            response = client.get(
                f"{self.url}/rest/agile/1.0/board/{board_id}/sprint",
                params={"maxResults": 20, "state": "active,closed"},
                timeout=30
            )

            if response.status_code != 200:
                return

            data = response.json()
            sprints = data.get("values", [])

            for sprint in sprints:
                self._sync_sprint(sprint, project_key, board_name, result)

        except Exception:
            pass  # Sprints optional

    def _sync_sprint(
        self,
        sprint: Dict,
        project_key: str,
        board_name: str,
        result: SyncResult
    ):
        """Sync a single sprint entity."""
        name = sprint.get("name", "Unnamed Sprint")
        state = sprint.get("state", "unknown")

        body = f"""# {name}

## Details

- **State**: {state}
- **Board**: {board_name}
- **Project**: {project_key}

## Dates

- **Start**: {sprint.get('startDate', 'Not set')[:10] if sprint.get('startDate') else 'Not set'}
- **End**: {sprint.get('endDate', 'Not set')[:10] if sprint.get('endDate') else 'Not set'}

## Goal

{sprint.get('goal', 'No goal set')}
"""

        self.write_entity(
            entity_type="sprint",
            name=name,
            source="jira",
            body=body,
            sync_id=str(sprint.get("id")),
            project=project_key,
            status=state,
            start_date=sprint.get("startDate"),
            end_date=sprint.get("endDate"),
            goal=sprint.get("goal"),
            relationships={"project": [project_key]}
        )

        result.entities_created += 1
