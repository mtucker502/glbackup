"""Tests for data models."""

from gitlabbackup.models import (
    BackupManifest,
    GitLabGroup,
    GitLabProject,
    ManifestProject,
)


def test_project_from_api(api_project_data):
    proj = GitLabProject.from_api(api_project_data)
    assert proj.id == 42
    assert proj.name == "myproject"
    assert proj.path_with_namespace == "mygroup/myproject"
    assert proj.ssh_url == "git@gitlab.com:mygroup/myproject.git"
    assert proj.is_fork is False
    assert proj.wiki_enabled is True


def test_project_from_api_with_fork(api_project_data):
    api_project_data["forked_from_project"] = {
        "path_with_namespace": "upstream/myproject"
    }
    proj = GitLabProject.from_api(api_project_data)
    assert proj.is_fork is True
    assert proj.forked_from == "upstream/myproject"


def test_group_from_api():
    data = {"id": 10, "name": "mygroup", "full_path": "org/mygroup", "description": "desc"}
    group = GitLabGroup.from_api(data)
    assert group.id == 10
    assert group.full_path == "org/mygroup"


def test_manifest_round_trip():
    manifest = BackupManifest(
        version="1",
        last_run="2026-03-12T14:00:00+00:00",
        gitlab_host="gitlab.example.com",
        projects={
            "group/project": ManifestProject(
                project_id=1,
                last_backup="2026-03-12T14:00:00+00:00",
                backup_path="group/project.git",
                status="cloned",
                head_sha="abc123",
                size_bytes=1024,
            )
        },
    )
    data = manifest.to_dict()
    restored = BackupManifest.from_dict(data)
    assert restored.gitlab_host == "gitlab.example.com"
    assert restored.projects["group/project"].head_sha == "abc123"
    assert restored.projects["group/project"].size_bytes == 1024
