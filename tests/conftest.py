"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from gitlabbackup.config import Config
from gitlabbackup.models import GitLabProject


@pytest.fixture
def sample_projects() -> list[GitLabProject]:
    return [
        GitLabProject(
            id=1, name="alpha", path_with_namespace="group/alpha",
            ssh_url="git@gitlab.com:group/alpha.git",
            http_url="https://gitlab.com/group/alpha.git",
            wiki_enabled=True,
        ),
        GitLabProject(
            id=2, name="beta", path_with_namespace="group/beta",
            ssh_url="git@gitlab.com:group/beta.git",
            http_url="https://gitlab.com/group/beta.git",
            forked_from="other/beta",
        ),
        GitLabProject(
            id=3, name="gamma", path_with_namespace="group/sub/gamma",
            ssh_url="git@gitlab.com:group/sub/gamma.git",
            http_url="https://gitlab.com/group/sub/gamma.git",
            archived=True,
        ),
        GitLabProject(
            id=4, name="delta", path_with_namespace="other/delta",
            ssh_url="git@gitlab.com:other/delta.git",
            http_url="https://gitlab.com/other/delta.git",
        ),
    ]


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(backup_dir=tmp_path)


@pytest.fixture
def api_project_data() -> dict:
    return {
        "id": 42,
        "name": "myproject",
        "path_with_namespace": "mygroup/myproject",
        "ssh_url_to_repo": "git@gitlab.com:mygroup/myproject.git",
        "http_url_to_repo": "https://gitlab.com/mygroup/myproject.git",
        "description": "A test project",
        "archived": False,
        "wiki_enabled": True,
    }
