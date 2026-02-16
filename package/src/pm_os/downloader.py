"""
PM-OS Common Directory Downloader

Downloads the common/ directory from GitHub releases.
Supports tarball download with git clone fallback.

Repo hierarchy:
  1. feamando/pmos (private, enterprise) - preferred for authenticated users
  2. feamando/pmos (public) - fallback for pip install users
"""

import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import requests


# GitHub repositories (tried in order)
GITHUB_REPOS = [
    "feamando/pmos",  # Private enterprise repo (requires auth)
    "feamando/pmos",         # Public repo (always accessible)
]
GITHUB_API_BASE = "https://api.github.com"


class DownloadError(Exception):
    """Error during download."""
    pass


class CommonDownloader:
    """Downloads common/ directory from GitHub."""

    def __init__(self, version: str = "latest", verbose: bool = False, repo: Optional[str] = None):
        """Initialize downloader.

        Args:
            version: Version to download ('latest' or a tag like 'v3.3.0')
            verbose: Show detailed progress
            repo: Override GitHub repo (e.g., 'feamando/pmos')
        """
        self.version = version
        self.verbose = verbose
        self.repo = repo  # If set, only try this repo
        self._resolved_version: Optional[str] = None
        self._resolved_repo: Optional[str] = None

    def _get_github_token(self) -> Optional[str]:
        """Get GitHub token from environment or gh CLI."""
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_HF_PM_OS")
        if token:
            return token

        # Try gh CLI
        if shutil.which("gh"):
            try:
                result = subprocess.run(
                    ["gh", "auth", "token"],
                    capture_output=True, text=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass

        return None

    def _request_headers(self) -> dict:
        """Build HTTP headers with optional auth."""
        headers = {"Accept": "application/vnd.github+json"}
        token = self._get_github_token()
        if token:
            headers["Authorization"] = f"token {token}"
        return headers

    def _try_repo(self, repo: str) -> bool:
        """Check if a repo is accessible."""
        try:
            resp = requests.get(
                f"{GITHUB_API_BASE}/repos/{repo}",
                timeout=10,
                headers=self._request_headers(),
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _resolve_repo(self) -> str:
        """Find the best accessible repo."""
        if self._resolved_repo:
            return self._resolved_repo

        if self.repo:
            self._resolved_repo = self.repo
            return self._resolved_repo

        for repo in GITHUB_REPOS:
            if self._try_repo(repo):
                self._resolved_repo = repo
                if self.verbose:
                    print(f"  Using repo: {repo}")
                return self._resolved_repo

        # Default to public repo even if API check failed (tarball might still work)
        self._resolved_repo = GITHUB_REPOS[-1]
        return self._resolved_repo

    def get_latest_version(self) -> str:
        """Query GitHub API for latest release tag."""
        repo = self._resolve_repo()
        try:
            resp = requests.get(
                f"{GITHUB_API_BASE}/repos/{repo}/releases/latest",
                timeout=15,
                headers=self._request_headers(),
            )
            if resp.status_code == 200:
                return resp.json()["tag_name"]

            # No releases - try tags
            resp = requests.get(
                f"{GITHUB_API_BASE}/repos/{repo}/tags",
                timeout=15,
                headers=self._request_headers(),
                params={"per_page": 1},
            )
            if resp.status_code == 200:
                tags = resp.json()
                if tags:
                    return tags[0]["name"]

            # Fallback: use current pip package version
            try:
                from importlib.metadata import version as pkg_version
                v = pkg_version("pm-os")
                return f"v{v}"
            except Exception:
                pass

            raise DownloadError("Could not determine latest version")

        except requests.RequestException as e:
            raise DownloadError(f"Failed to check latest version: {e}")

    def resolve_version(self) -> str:
        """Resolve 'latest' to actual version tag."""
        if self._resolved_version:
            return self._resolved_version

        if self.version == "latest":
            self._resolved_version = self.get_latest_version()
        else:
            self._resolved_version = self.version if self.version.startswith("v") else f"v{self.version}"

        return self._resolved_version

    def download(self, target_dir: Path) -> bool:
        """Download common/ to target_dir/common/.

        Args:
            target_dir: Root directory (e.g., ~/pm-os/). common/ will be created inside.

        Returns:
            True if successful.
        """
        common_dir = target_dir / "common"

        # Try each repo with both strategies
        repos_to_try = [self.repo] if self.repo else list(GITHUB_REPOS)
        last_error = None

        for repo in repos_to_try:
            # Strategy 1: GitHub archive tarball (fast, no git needed)
            try:
                return self._download_tarball(target_dir, common_dir, repo)
            except DownloadError as e:
                last_error = e
                if self.verbose:
                    print(f"  Tarball from {repo} failed: {e}")

            # Strategy 2: Git shallow clone
            try:
                return self._git_clone(target_dir, common_dir, repo)
            except DownloadError as e:
                last_error = e
                if self.verbose:
                    print(f"  Git clone from {repo} failed: {e}")

        raise DownloadError(
            "Failed to download common/ directory. "
            "Check your internet connection and try again.\n"
            "If you already have common/, use: pm-os init --common-path /path/to/common"
        )

    def _download_tarball(self, target_dir: Path, common_dir: Path, repo: Optional[str] = None) -> bool:
        """Download via GitHub archive tarball."""
        repo = repo or self._resolve_repo()
        version = self.resolve_version()
        tarball_url = f"https://github.com/{repo}/archive/refs/tags/{version}.tar.gz"

        if self.verbose:
            print(f"  Downloading: {tarball_url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            tarball_path = tmp_path / "common.tar.gz"

            try:
                resp = requests.get(
                    tarball_url,
                    stream=True,
                    timeout=120,
                    headers=self._request_headers(),
                    allow_redirects=True,
                )
                resp.raise_for_status()

                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(tarball_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)

            except requests.RequestException as e:
                raise DownloadError(f"Download failed: {e}")

            # Extract tarball
            try:
                with tarfile.open(tarball_path, "r:gz") as tar:
                    tar.extractall(path=tmp_path, filter="data")
            except (tarfile.TarError, TypeError):
                # filter="data" requires Python 3.12+, fall back
                try:
                    with tarfile.open(tarball_path, "r:gz") as tar:
                        tar.extractall(path=tmp_path)
                except tarfile.TarError as e:
                    raise DownloadError(f"Extraction failed: {e}")

            # Find extracted directory
            # GitHub archives extract to {repo-name}-{version}/ or {repo-name}-{sha}/
            extracted_dirs = [
                d for d in tmp_path.iterdir()
                if d.is_dir() and d.name != tarball_path.name
            ]

            if not extracted_dirs:
                raise DownloadError("No extracted directory found in tarball")

            extracted_dir = extracted_dirs[0]

            # Move extracted content to common/
            if common_dir.exists():
                shutil.rmtree(common_dir)

            shutil.move(str(extracted_dir), str(common_dir))

        return True

    def _git_clone(self, target_dir: Path, common_dir: Path, repo: Optional[str] = None) -> bool:
        """Fallback: shallow git clone."""
        repo = repo or self._resolve_repo()
        version = self.resolve_version()

        if not shutil.which("git"):
            raise DownloadError("git not available")

        if self.verbose:
            print(f"  Cloning {repo} (tag: {version})...")

        if common_dir.exists():
            shutil.rmtree(common_dir)

        try:
            # Try cloning with the specific tag first
            result = subprocess.run(
                [
                    "git", "clone",
                    "--depth", "1",
                    "--branch", version,
                    f"https://github.com/{repo}.git",
                    str(common_dir),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                # Tag might not exist on this repo; try default branch
                if common_dir.exists():
                    shutil.rmtree(common_dir)
                result = subprocess.run(
                    [
                        "git", "clone",
                        "--depth", "1",
                        f"https://github.com/{repo}.git",
                        str(common_dir),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            if result.returncode != 0:
                raise DownloadError(f"git clone failed: {result.stderr[:200]}")

            # Remove .git directory to save space
            git_dir = common_dir / ".git"
            if git_dir.exists():
                shutil.rmtree(git_dir)

            return True

        except subprocess.TimeoutExpired:
            raise DownloadError("git clone timed out")
        except FileNotFoundError:
            raise DownloadError("git not available")

    def verify_download(self, common_dir: Path) -> Tuple[bool, list]:
        """Verify common/ has expected structure.

        Returns:
            (success, list of missing items)
        """
        expected = [
            "tools",
            ".claude/commands",
            "scripts",
            "AGENT.md",
            "config.yaml.example",
            ".env.example",
        ]

        missing = []
        for item in expected:
            if not (common_dir / item).exists():
                missing.append(item)

        return len(missing) == 0, missing

    def create_markers(self, root_dir: Path, user_dir: Path, common_dir: Path):
        """Create marker files for path resolution."""
        root_marker = root_dir / ".pm-os-root"
        root_marker.write_text(f"PM-OS root directory\nversion: {self.resolve_version()}\n")

        common_marker = common_dir / ".pm-os-common"
        if not common_marker.exists():
            common_marker.write_text("PM-OS common directory\n")

        user_marker = user_dir / ".pm-os-user"
        user_marker.write_text("PM-OS user directory\n")

    def pin_version(self, root_dir: Path):
        """Write version to .pm-os-version file."""
        version = self.resolve_version()
        version_file = root_dir / ".pm-os-version"
        version_file.write_text(f"{version}\n")

    @staticmethod
    def get_installed_version(root_dir: Path) -> Optional[str]:
        """Read installed version from .pm-os-version."""
        version_file = root_dir / ".pm-os-version"
        if version_file.exists():
            return version_file.read_text().strip()
        return None
