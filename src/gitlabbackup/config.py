"""Configuration loading from TOML file, env vars, and CLI flags."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "gitlabbackup" / "config.toml"


@dataclass
class Config:
    backup_dir: Path = field(default_factory=Path.cwd)
    gitlab_host: str = ""
    protocol: str = "ssh"
    workers: int = 4
    dry_run: bool = False
    verbose: bool = False
    include_subgroups: bool = True
    include_wiki: bool = False
    include_lfs: bool = False
    skip_forks: bool = False
    forks_only: bool = False
    exclude_patterns: list[str] = field(default_factory=list)
    include_patterns: list[str] = field(default_factory=list)
    post_hook: str = ""

    @classmethod
    def load(cls, config_path: Path | None = None) -> Config:
        """Load config from TOML file, then overlay env vars."""
        config = cls()
        path = config_path or DEFAULT_CONFIG_PATH
        if path.exists():
            with open(path, "rb") as f:
                data = tomllib.load(f)
            config._apply_toml(data)
        config._apply_env()
        return config

    def _apply_toml(self, data: dict) -> None:
        if "backup_dir" in data:
            self.backup_dir = Path(data["backup_dir"]).expanduser()
        if "gitlab_host" in data:
            self.gitlab_host = data["gitlab_host"]
        if "protocol" in data:
            self.protocol = data["protocol"]
        if "workers" in data:
            self.workers = int(data["workers"])
        if "include_subgroups" in data:
            self.include_subgroups = bool(data["include_subgroups"])
        if "include_wiki" in data:
            self.include_wiki = bool(data["include_wiki"])
        if "include_lfs" in data:
            self.include_lfs = bool(data["include_lfs"])
        if "skip_forks" in data:
            self.skip_forks = bool(data["skip_forks"])
        if "exclude_patterns" in data:
            self.exclude_patterns = list(data["exclude_patterns"])
        if "include_patterns" in data:
            self.include_patterns = list(data["include_patterns"])
        if "post_hook" in data:
            self.post_hook = data["post_hook"]

    def _apply_env(self) -> None:
        if val := os.environ.get("GLBACKUP_DIR"):
            self.backup_dir = Path(val)
        if val := os.environ.get("GLBACKUP_HOST"):
            self.gitlab_host = val
        if val := os.environ.get("GLBACKUP_PROTOCOL"):
            self.protocol = val
        if val := os.environ.get("GLBACKUP_WORKERS"):
            self.workers = int(val)
