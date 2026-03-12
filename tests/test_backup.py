"""Tests for BackupEngine with mocked git operations."""

import subprocess
from pathlib import Path

import pytest

from gitlabbackup.backup import BackupEngine
from gitlabbackup.config import Config
from gitlabbackup.models import BackupStatus, GitLabProject


@pytest.fixture
def engine(tmp_path: Path) -> BackupEngine:
    config = Config(backup_dir=tmp_path, protocol="ssh")
    return BackupEngine(config)


@pytest.fixture
def project() -> GitLabProject:
    return GitLabProject(
        id=1, name="myproject", path_with_namespace="group/myproject",
        ssh_url="git@gitlab.com:group/myproject.git",
        http_url="https://gitlab.com/group/myproject.git",
    )


def test_get_clone_url_ssh(engine, project):
    assert engine._get_clone_url(project) == "git@gitlab.com:group/myproject.git"


def test_get_clone_url_http(tmp_path: Path, project):
    config = Config(backup_dir=tmp_path, protocol="http")
    engine = BackupEngine(config)
    assert engine._get_clone_url(project) == "https://gitlab.com/group/myproject.git"


def test_get_backup_path(engine, project):
    path = engine._get_backup_path(project)
    assert path == engine.config.backup_dir / "group" / "myproject.git"


def test_is_valid_mirror_empty(tmp_path: Path):
    assert BackupEngine._is_valid_mirror(tmp_path / "nonexistent") is False


def test_is_valid_mirror_valid(tmp_path: Path):
    repo = tmp_path / "test.git"
    repo.mkdir()
    (repo / "HEAD").write_text("ref: refs/heads/main")
    (repo / "objects").mkdir()
    (repo / "refs").mkdir()
    assert BackupEngine._is_valid_mirror(repo) is True


def test_backup_project_clone(engine, project, mocker):
    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="abc123def456", stderr=""
    ))
    result = engine.backup_project(project)
    assert result.status == BackupStatus.CLONED
    assert result.project.id == 1


def test_backup_project_fetch(engine, project, mocker):
    # Create a valid mirror so it takes the fetch path
    backup_path = engine._get_backup_path(project)
    backup_path.mkdir(parents=True)
    (backup_path / "HEAD").write_text("ref: refs/heads/main")
    (backup_path / "objects").mkdir()
    (backup_path / "refs").mkdir()

    mocker.patch("subprocess.run", return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="abc123", stderr=""
    ))
    result = engine.backup_project(project)
    assert result.status in (BackupStatus.UPDATED, BackupStatus.UNCHANGED)


def test_backup_project_failure(engine, project, mocker):
    mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(
        128, "git", stderr="fatal: repository not found"
    ))
    result = engine.backup_project(project)
    assert result.status == BackupStatus.FAILED
    assert result.error  # has some error message
