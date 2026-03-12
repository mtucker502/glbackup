"""Backup engine — clone, fetch, wiki, and LFS operations."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from .config import Config
from .models import BackupResult, BackupStatus, GitLabProject

log = logging.getLogger(__name__)


class BackupEngine:
    """Performs git mirror clone and incremental fetch operations."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def backup_project(self, project: GitLabProject) -> BackupResult:
        """Back up a single project (clone or update)."""
        start = time.monotonic()
        backup_path = self._get_backup_path(project)
        clone_url = self._get_clone_url(project)

        try:
            if self._is_valid_mirror(backup_path):
                status = self._fetch_update(backup_path)
            else:
                # Remove partial/corrupt directory from a previous failed clone
                if backup_path.exists():
                    log.warning("Removing invalid mirror at %s", backup_path)
                    shutil.rmtree(backup_path)
                self._clone_mirror(clone_url, backup_path)
                status = BackupStatus.CLONED

            head_sha = self._get_head_sha(backup_path)
            size_bytes = self._get_dir_size(backup_path)

            result = BackupResult(
                project=project,
                status=status,
                backup_path=str(backup_path.relative_to(self.config.backup_dir)),
                head_sha=head_sha,
                size_bytes=size_bytes,
            )
        except Exception as e:
            log.error("Failed to back up %s: %s", project.path_with_namespace, e)
            result = BackupResult(
                project=project,
                status=BackupStatus.FAILED,
                error=str(e),
            )

        # Wiki backup
        if self.config.include_wiki and project.wiki_enabled:
            wiki_result = self._backup_wiki(project)
            result.wiki_status = wiki_result

        # LFS fetch
        if self.config.include_lfs and result.status != BackupStatus.FAILED:
            self._fetch_lfs(backup_path)

        result.duration_seconds = time.monotonic() - start
        return result

    def _clone_mirror(self, url: str, dest: Path) -> None:
        """Run git clone --mirror."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        log.info("Cloning %s → %s", url, dest)
        subprocess.run(
            ["git", "clone", "--mirror", url, str(dest)],
            capture_output=True, text=True, check=True, timeout=600,
        )

    def _fetch_update(self, repo_path: Path) -> BackupStatus:
        """Run git fetch --prune origin on an existing mirror."""
        log.info("Fetching updates for %s", repo_path)
        old_sha = self._get_head_sha(repo_path)
        subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "--prune", "origin"],
            capture_output=True, text=True, check=True, timeout=600,
        )
        new_sha = self._get_head_sha(repo_path)
        if old_sha == new_sha:
            return BackupStatus.UNCHANGED
        return BackupStatus.UPDATED

    def _backup_wiki(self, project: GitLabProject) -> BackupStatus:
        """Back up the wiki repository if it exists."""
        wiki_path = self._get_backup_path(project).parent / (project.name + ".wiki.git")
        wiki_url = self._get_clone_url(project).replace(".git", ".wiki.git")

        try:
            if self._is_valid_mirror(wiki_path):
                return self._fetch_update(wiki_path)
            else:
                self._clone_mirror(wiki_url, wiki_path)
                return BackupStatus.CLONED
        except subprocess.CalledProcessError:
            # Wiki may not exist — not an error
            log.debug("Wiki not available for %s", project.path_with_namespace)
            if wiki_path.exists():
                shutil.rmtree(wiki_path)
            return BackupStatus.SKIPPED

    def _fetch_lfs(self, repo_path: Path) -> None:
        """Fetch all LFS objects if git-lfs is available."""
        if not shutil.which("git-lfs"):
            log.warning("git-lfs not found, skipping LFS fetch")
            return
        try:
            subprocess.run(
                ["git", "-C", str(repo_path), "lfs", "fetch", "--all"],
                capture_output=True, text=True, check=True, timeout=600,
            )
        except subprocess.CalledProcessError as e:
            log.warning("LFS fetch failed for %s: %s", repo_path, e.stderr)

    def _get_clone_url(self, project: GitLabProject) -> str:
        if self.config.protocol == "http":
            return project.http_url
        return project.ssh_url

    def _get_backup_path(self, project: GitLabProject) -> Path:
        return self.config.backup_dir / (project.path_with_namespace + ".git")

    @staticmethod
    def _is_valid_mirror(path: Path) -> bool:
        """Check if a path contains a valid bare git repo."""
        if not path.is_dir():
            return False
        return (path / "HEAD").exists() and (path / "objects").is_dir()

    @staticmethod
    def _get_head_sha(repo_path: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=30,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    @staticmethod
    def _get_dir_size(path: Path) -> int:
        total = 0
        try:
            for f in path.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        except OSError:
            pass
        return total
