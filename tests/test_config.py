"""Tests for config loading."""

from pathlib import Path

from gitlabbackup.config import Config


def test_default_config():
    config = Config()
    assert config.protocol == "ssh"
    assert config.workers == 4
    assert config.dry_run is False
    assert config.include_subgroups is True
    assert config.exclude_patterns == []


def test_load_toml(tmp_path: Path):
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        'backup_dir = "/tmp/backups"\n'
        'protocol = "http"\n'
        "workers = 8\n"
        'gitlab_host = "gitlab.example.com"\n'
        'exclude_patterns = ["test/*", "temp/*"]\n'
    )
    config = Config.load(toml_file)
    assert config.backup_dir == Path("/tmp/backups")
    assert config.protocol == "http"
    assert config.workers == 8
    assert config.gitlab_host == "gitlab.example.com"
    assert config.exclude_patterns == ["test/*", "temp/*"]


def test_load_missing_file(tmp_path: Path):
    config = Config.load(tmp_path / "nonexistent.toml")
    assert config.protocol == "ssh"


def test_env_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GLBACKUP_DIR", str(tmp_path))
    monkeypatch.setenv("GLBACKUP_WORKERS", "16")
    config = Config.load(tmp_path / "nonexistent.toml")
    assert config.backup_dir == tmp_path
    assert config.workers == 16
