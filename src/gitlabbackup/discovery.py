"""Repository discovery — find, filter, and deduplicate projects."""

from __future__ import annotations

import fnmatch
import logging

from .config import Config
from .gitlab import GlabClient
from .models import GitLabProject

log = logging.getLogger(__name__)


class RepoDiscovery:
    """Discovers and filters GitLab projects for backup."""

    def __init__(self, client: GlabClient, config: Config) -> None:
        self.client = client
        self.config = config

    def discover_group(self, group_path: str) -> list[GitLabProject]:
        """Discover all projects in a group."""
        group = self.client.get_group_by_path(group_path)
        projects = self.client.list_group_projects(
            group.id, include_subgroups=self.config.include_subgroups
        )
        return self._filter(projects)

    def discover_starred(self) -> list[GitLabProject]:
        projects = self.client.list_starred_projects()
        return self._filter(projects)

    def discover_member(self) -> list[GitLabProject]:
        projects = self.client.list_member_projects()
        return self._filter(projects)

    def discover_owned(self) -> list[GitLabProject]:
        projects = self.client.list_owned_projects()
        return self._filter(projects)

    def discover_all(self) -> list[GitLabProject]:
        projects = self.client.list_all_projects()
        return self._filter(projects)

    def _filter(self, projects: list[GitLabProject]) -> list[GitLabProject]:
        """Apply dedup, fork handling, and include/exclude patterns."""
        # Deduplicate by project ID
        seen: set[int] = set()
        unique: list[GitLabProject] = []
        for p in projects:
            if p.id not in seen:
                seen.add(p.id)
                unique.append(p)
        projects = unique

        # Fork handling
        if self.config.skip_forks:
            projects = [p for p in projects if not p.is_fork]
        elif self.config.forks_only:
            projects = [p for p in projects if p.is_fork]

        # Include patterns (if any specified, only matching projects kept)
        if self.config.include_patterns:
            projects = [
                p for p in projects
                if any(
                    fnmatch.fnmatch(p.path_with_namespace, pat)
                    for pat in self.config.include_patterns
                )
            ]

        # Exclude patterns
        if self.config.exclude_patterns:
            projects = [
                p for p in projects
                if not any(
                    fnmatch.fnmatch(p.path_with_namespace, pat)
                    for pat in self.config.exclude_patterns
                )
            ]

        projects.sort(key=lambda p: p.path_with_namespace)
        log.info("Discovered %d projects after filtering", len(projects))
        return projects
