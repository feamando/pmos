"""
PM-OS GitHub Brain Sync

Syncs repositories, issues, and pull requests from GitHub.
"""

from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from datetime import datetime

from pm_os.wizard.brain_sync.base import BaseSyncer, SyncResult, SyncProgress
from pm_os.wizard.exceptions import CredentialError, SyncError, NetworkError


class GitHubSyncer(BaseSyncer):
    """Sync brain entities from GitHub."""

    API_BASE = "https://api.github.com"

    def __init__(
        self,
        brain_path: Path,
        token: str,
        repos: Optional[List[str]] = None,
        username: Optional[str] = None
    ):
        """Initialize GitHub syncer.

        Args:
            brain_path: Path to brain directory
            token: GitHub personal access token
            repos: Optional list of repo full names to sync (owner/repo)
            username: Optional username (will be fetched if not provided)
        """
        super().__init__(brain_path)
        self.token = token
        self.repos = repos
        self.username = username
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def _api_call(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """Make a GitHub API call."""
        try:
            import requests
        except ImportError:
            raise SyncError(
                "requests library not installed",
                service="GitHub",
                remediation="pip install requests"
            )

        url = f"{self.API_BASE}{endpoint}"

        response = requests.get(
            url,
            headers=self._headers,
            params=params or {},
            timeout=30
        )

        if response.status_code == 401:
            raise CredentialError(
                "GitHub authentication failed: Invalid or expired token",
                credential_type="GitHub"
            )
        elif response.status_code == 403:
            raise CredentialError(
                "GitHub access denied: Token may lack required permissions",
                credential_type="GitHub"
            )
        elif response.status_code != 200:
            raise NetworkError(
                f"GitHub API error: {response.status_code}",
                endpoint=url
            )

        return response.json()

    def test_connection(self) -> tuple:
        """Test connection to GitHub."""
        try:
            data = self._api_call("/user")
            username = data.get("login", "user")
            self.username = username
            return True, f"Connected as @{username}"
        except CredentialError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def sync(
        self,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        incremental: bool = True
    ) -> SyncResult:
        """Sync GitHub data to brain.

        Args:
            progress_callback: Progress callback (current, total, phase)
            incremental: Only sync changes since last sync

        Returns:
            SyncResult with details
        """
        result = SyncResult(success=True, message="")
        progress = SyncProgress(callback=progress_callback)

        try:
            # Get user info if not set
            if not self.username:
                user_data = self._api_call("/user")
                self.username = user_data.get("login")

            # Phase 1: Get repositories
            progress.phase = "Fetching repositories"
            repos = self._fetch_repos()

            if self.repos:
                repos = [r for r in repos if r['full_name'] in self.repos]

            progress.total = len(repos) * 3  # repos + issues + PRs

            # Phase 2: Sync repositories
            for repo in repos:
                progress.update(progress.current, f"Syncing repo: {repo['name']}")
                self._sync_repo(repo, result)
                progress.increment()

            # Phase 3: Sync issues
            for repo in repos:
                progress.update(progress.current, f"Syncing issues: {repo['name']}")
                last_sync = self.get_last_sync_time(f"github_issues_{repo['full_name']}") if incremental else None
                self._sync_issues(repo, last_sync, result)
                self.set_last_sync_time(f"github_issues_{repo['full_name']}")
                progress.increment()

            # Phase 4: Sync PRs
            for repo in repos:
                progress.update(progress.current, f"Syncing PRs: {repo['name']}")
                last_sync = self.get_last_sync_time(f"github_prs_{repo['full_name']}") if incremental else None
                self._sync_pull_requests(repo, last_sync, result)
                self.set_last_sync_time(f"github_prs_{repo['full_name']}")
                progress.increment()

            # Build summary message
            total_entities = result.entities_created + result.entities_updated
            result.message = f"Synced {total_entities} entities from {len(repos)} repositories"

        except CredentialError:
            raise
        except SyncError:
            raise
        except Exception as e:
            result.success = False
            result.message = f"Sync failed: {str(e)}"
            result.errors.append(str(e))

        return result

    def _fetch_repos(self) -> List[Dict]:
        """Fetch accessible repositories."""
        repos = []

        # Get repos the user has access to
        data = self._api_call(
            "/user/repos",
            params={"per_page": 100, "sort": "updated"}
        )

        # Filter to recent/relevant repos
        for repo in data:
            if not repo.get("archived"):
                repos.append(repo)

        return repos[:50]  # Limit to 50 most recent

    def _sync_repo(self, repo: Dict, result: SyncResult):
        """Sync a single repository entity."""
        name = repo.get("name")
        full_name = repo.get("full_name")

        body = f"""# {name}

## Overview

- **Full Name**: {full_name}
- **Visibility**: {'Private' if repo.get('private') else 'Public'}
- **Default Branch**: {repo.get('default_branch', 'main')}
- **Language**: {repo.get('language', 'Not specified')}

## Description

{repo.get('description', 'No description provided.')}

## Stats

- **Stars**: {repo.get('stargazers_count', 0)}
- **Forks**: {repo.get('forks_count', 0)}
- **Open Issues**: {repo.get('open_issues_count', 0)}

## Links

- [View on GitHub]({repo.get('html_url')})
"""

        self.write_entity(
            entity_type="repository",
            name=name,
            source="github",
            body=body,
            sync_id=str(repo.get("id")),
            full_name=full_name,
            url=repo.get("html_url"),
            description=repo.get("description"),
            default_branch=repo.get("default_branch"),
            is_private=repo.get("private", False),
            language=repo.get("language"),
            stars=repo.get("stargazers_count", 0),
            forks=repo.get("forks_count", 0),
            open_issues=repo.get("open_issues_count", 0)
        )

        result.entities_created += 1

    def _sync_issues(
        self,
        repo: Dict,
        last_sync: Optional[str],
        result: SyncResult
    ):
        """Sync issues for a repository."""
        full_name = repo.get("full_name")

        params = {"per_page": 50, "state": "all", "sort": "updated"}
        if last_sync:
            params["since"] = last_sync

        try:
            issues = self._api_call(f"/repos/{full_name}/issues", params=params)

            for issue in issues:
                # Skip pull requests (they come through issues API but have pull_request key)
                if "pull_request" in issue:
                    continue

                self._sync_issue(issue, repo, result)

        except Exception as e:
            result.errors.append(f"Error syncing issues for {full_name}: {str(e)}")

    def _sync_issue(self, issue: Dict, repo: Dict, result: SyncResult):
        """Sync a single issue entity."""
        number = issue.get("number")
        title = issue.get("title", "Untitled")
        repo_name = repo.get("name")
        full_name = repo.get("full_name")

        # Build relationships
        relationships = {"repository": [repo_name]}

        assignees = issue.get("assignees", [])
        if assignees:
            relationships["assignee"] = [a.get("login") for a in assignees]

        user = issue.get("user", {})

        body = f"""# {title}

## Details

- **Number**: [#{number}]({issue.get('html_url')})
- **State**: {issue.get('state', 'unknown')}
- **Author**: @{user.get('login', 'unknown')}
- **Labels**: {', '.join(l.get('name', '') for l in issue.get('labels', [])) or 'None'}

## Description

{(issue.get('body') or 'No description')[:500]}

## Links

- [View on GitHub]({issue.get('html_url')})
"""

        self.write_entity(
            entity_type="issue",
            name=f"{repo_name}#{number}: {title}",
            source="github",
            body=body,
            sync_id=str(issue.get("id")),
            key=f"{repo_name}#{number}",
            title=title,
            status=issue.get("state"),
            repository=full_name,
            url=issue.get("html_url"),
            labels=[l.get("name") for l in issue.get("labels", [])],
            relationships=relationships
        )

        result.entities_created += 1

    def _sync_pull_requests(
        self,
        repo: Dict,
        last_sync: Optional[str],
        result: SyncResult
    ):
        """Sync pull requests for a repository."""
        full_name = repo.get("full_name")

        params = {"per_page": 30, "state": "all", "sort": "updated"}

        try:
            prs = self._api_call(f"/repos/{full_name}/pulls", params=params)

            for pr in prs:
                # Filter by last sync if incremental
                if last_sync:
                    updated = pr.get("updated_at", "")
                    if updated < last_sync:
                        continue

                self._sync_pull_request(pr, repo, result)

        except Exception as e:
            result.errors.append(f"Error syncing PRs for {full_name}: {str(e)}")

    def _sync_pull_request(self, pr: Dict, repo: Dict, result: SyncResult):
        """Sync a single pull request entity."""
        number = pr.get("number")
        title = pr.get("title", "Untitled")
        repo_name = repo.get("name")
        full_name = repo.get("full_name")

        user = pr.get("user", {})
        state = pr.get("state")
        if pr.get("merged_at"):
            state = "merged"

        body = f"""# {title}

## Details

- **Number**: [#{number}]({pr.get('html_url')})
- **State**: {state}
- **Author**: @{user.get('login', 'unknown')}
- **Base**: {pr.get('base', {}).get('ref', 'unknown')}
- **Head**: {pr.get('head', {}).get('ref', 'unknown')}

## Description

{(pr.get('body') or 'No description')[:500]}

## Links

- [View on GitHub]({pr.get('html_url')})
"""

        self.write_entity(
            entity_type="pull_request",
            name=f"{repo_name}#{number}: {title}",
            source="github",
            body=body,
            sync_id=str(pr.get("id")),
            number=number,
            title=title,
            state=state,
            repository=full_name,
            author=user.get("login"),
            url=pr.get("html_url"),
            base_branch=pr.get("base", {}).get("ref"),
            head_branch=pr.get("head", {}).get("ref"),
            created_date=pr.get("created_at"),
            merged_date=pr.get("merged_at"),
            labels=[l.get("name") for l in pr.get("labels", [])],
            relationships={"repository": [repo_name]}
        )

        result.entities_created += 1
