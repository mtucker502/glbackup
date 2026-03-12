"""Data models for GitLab projects, groups, and backup state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BackupStatus(Enum):
    CLONED = "cloned"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"
    UNCHANGED = "unchanged"


@dataclass
class GitLabGroup:
    id: int
    name: str
    full_path: str
    description: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitLabGroup:
        return cls(
            id=data["id"],
            name=data["name"],
            full_path=data["full_path"],
            description=data.get("description") or "",
        )


@dataclass
class GitLabProject:
    id: int
    name: str
    path_with_namespace: str
    ssh_url: str
    http_url: str
    description: str = ""
    archived: bool = False
    forked_from: str | None = None
    wiki_enabled: bool = False

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitLabProject:
        forked_from = None
        if "forked_from_project" in data and data["forked_from_project"]:
            forked_from = data["forked_from_project"].get("path_with_namespace", "unknown")
        return cls(
            id=data["id"],
            name=data["name"],
            path_with_namespace=data["path_with_namespace"],
            ssh_url=data.get("ssh_url_to_repo", ""),
            http_url=data.get("http_url_to_repo", ""),
            description=data.get("description") or "",
            archived=data.get("archived", False),
            forked_from=forked_from,
            wiki_enabled=data.get("wiki_enabled", False),
        )

    @property
    def is_fork(self) -> bool:
        return self.forked_from is not None


@dataclass
class BackupResult:
    project: GitLabProject
    status: BackupStatus
    backup_path: str = ""
    head_sha: str = ""
    size_bytes: int = 0
    error: str = ""
    wiki_status: BackupStatus | None = None
    duration_seconds: float = 0.0


@dataclass
class ManifestProject:
    project_id: int
    last_backup: str
    backup_path: str
    status: str
    head_sha: str = ""
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "last_backup": self.last_backup,
            "backup_path": self.backup_path,
            "status": self.status,
            "head_sha": self.head_sha,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManifestProject:
        return cls(
            project_id=data["project_id"],
            last_backup=data["last_backup"],
            backup_path=data["backup_path"],
            status=data["status"],
            head_sha=data.get("head_sha", ""),
            size_bytes=data.get("size_bytes", 0),
        )


@dataclass
class BackupManifest:
    version: str = "1"
    last_run: str = ""
    gitlab_host: str = ""
    projects: dict[str, ManifestProject] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "last_run": self.last_run,
            "gitlab_host": self.gitlab_host,
            "projects": {k: v.to_dict() for k, v in self.projects.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupManifest:
        projects = {}
        for path, proj_data in data.get("projects", {}).items():
            projects[path] = ManifestProject.from_dict(proj_data)
        return cls(
            version=data.get("version", "1"),
            last_run=data.get("last_run", ""),
            gitlab_host=data.get("gitlab_host", ""),
            projects=projects,
        )

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
