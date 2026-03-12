"""Tests for ManifestManager."""

import json
from pathlib import Path

import pytest

from gitlabbackup.manifest import ManifestManager
from gitlabbackup.models import BackupManifest, BackupResult, BackupStatus, GitLabProject


@pytest.fixture
def manager(tmp_path: Path) -> ManifestManager:
    return ManifestManager(tmp_path)


@pytest.fixture
def project() -> GitLabProject:
    return GitLabProject(
        id=1, name="myproject", path_with_namespace="group/myproject",
        ssh_url="", http_url="",
    )


def test_load_empty(manager):
    manifest = manager.load()
    assert manifest.version == "1"
    assert manifest.projects == {}


def test_save_and_load(manager):
    manifest = BackupManifest(
        version="1",
        last_run="2026-03-12T14:00:00+00:00",
        gitlab_host="gitlab.example.com",
    )
    manager.save(manifest)
    assert manager.path.exists()

    loaded = manager.load()
    assert loaded.gitlab_host == "gitlab.example.com"


def test_update_from_results(manager, project):
    manifest = manager.load()
    results = [
        BackupResult(
            project=project,
            status=BackupStatus.CLONED,
            backup_path="group/myproject.git",
            head_sha="abc123",
            size_bytes=1024,
        )
    ]
    updated = manager.update_from_results(manifest, results, "gitlab.example.com")
    assert "group/myproject" in updated.projects
    assert updated.projects["group/myproject"].head_sha == "abc123"
    assert updated.gitlab_host == "gitlab.example.com"

    # Verify it was saved
    loaded = manager.load()
    assert "group/myproject" in loaded.projects


def test_failed_results_not_overwrite(manager, project):
    """Failed backups should not overwrite existing entries."""
    manifest = manager.load()
    # First: successful backup
    results = [
        BackupResult(
            project=project, status=BackupStatus.CLONED,
            backup_path="group/myproject.git", head_sha="abc123",
        )
    ]
    manifest = manager.update_from_results(manifest, results, "gitlab.example.com")

    # Second: failed backup — should not overwrite
    fail_results = [
        BackupResult(project=project, status=BackupStatus.FAILED, error="timeout")
    ]
    manifest = manager.update_from_results(manifest, fail_results, "gitlab.example.com")
    assert manifest.projects["group/myproject"].head_sha == "abc123"


def test_atomic_write(manager):
    """Verify manifest file is valid JSON after save."""
    manifest = BackupManifest(version="1", last_run="now", gitlab_host="test")
    manager.save(manifest)
    data = json.loads(manager.path.read_text())
    assert data["version"] == "1"
