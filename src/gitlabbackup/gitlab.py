"""GitLab API client wrapping the glab CLI."""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.parse
from typing import Any

from .models import GitLabGroup, GitLabProject

log = logging.getLogger(__name__)


class GlabError(Exception):
    """Raised when a glab CLI call fails."""


class GlabClient:
    """Wraps the glab CLI for GitLab API access."""

    def __init__(self, host: str = "") -> None:
        self.host = host

    def _run(self, args: list[str], *, paginate: bool = False) -> str:
        cmd = ["glab", "api"]
        if paginate:
            cmd.append("--paginate")
        if self.host:
            cmd.extend(["--hostname", self.host])
        cmd.extend(args)
        log.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise GlabError(
                f"glab command failed (exit {result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout

    def _get_json(self, endpoint: str, *, paginate: bool = True) -> Any:
        raw = self._run([endpoint], paginate=paginate)
        if not raw.strip():
            return []
        return json.loads(raw)

    def check_auth(self) -> bool:
        """Verify glab is installed and authenticated."""
        try:
            cmd = ["glab", "auth", "status"]
            host = self.get_host()
            if host:
                cmd.extend(["--hostname", host])
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def get_host(self) -> str:
        """Get the configured GitLab hostname."""
        if self.host:
            return self.host
        try:
            result = subprocess.run(
                ["glab", "config", "get", "host"],
                capture_output=True, text=True, timeout=30,
            )
            host = result.stdout.strip()
            if host:
                return host
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return "gitlab.com"

    def get_group_by_path(self, full_path: str) -> GitLabGroup:
        """Look up a group by its full path."""
        encoded = urllib.parse.quote(full_path, safe="")
        data = self._get_json(f"/groups/{encoded}", paginate=False)
        return GitLabGroup.from_api(data)

    def list_group_projects(
        self, group_id: int, *, include_subgroups: bool = True
    ) -> list[GitLabProject]:
        """List all projects in a group."""
        params = "include_subgroups=true" if include_subgroups else ""
        endpoint = f"/groups/{group_id}/projects?{params}&per_page=100"
        data = self._get_json(endpoint)
        return [GitLabProject.from_api(p) for p in data]

    def list_starred_projects(self) -> list[GitLabProject]:
        data = self._get_json("/projects?starred=true&per_page=100")
        return [GitLabProject.from_api(p) for p in data]

    def list_member_projects(self) -> list[GitLabProject]:
        data = self._get_json("/projects?membership=true&per_page=100")
        return [GitLabProject.from_api(p) for p in data]

    def list_all_projects(self) -> list[GitLabProject]:
        data = self._get_json("/projects?per_page=100")
        return [GitLabProject.from_api(p) for p in data]
